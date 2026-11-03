from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
from smtplib import SMTPConnectError, SMTPDataError, SMTPServerDisconnected
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from .email_queue import book, process_due, reconcile, CONFIRMATION, ADMIN, REMINDERS
from .models import ClassDate, EmailTemplate, MeetingSettings, Reservation, ScheduledEmail, Submission, EmailWorkerHeartbeat


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   DEFAULT_FROM_EMAIL="sender@example.com", LANDING_ADMIN_EMAIL="admin@example.com")
class EmailQueueTests(TestCase):
    def setUp(self):
        publisher = patch("landing.tasks.send_scheduled_email.delay", side_effect=lambda pk: process_due(job_id=pk, record_heartbeat=False))
        publisher.start()
        self.addCleanup(publisher.stop)
        from .tasks import dispatch_due_emails
        dispatcher = patch("landing.tasks.dispatch_due_emails.delay", side_effect=dispatch_due_emails.run)
        dispatcher.start()
        self.addCleanup(dispatcher.stop)
        self.now = datetime(2030, 1, 1, 12, tzinfo=dt_timezone.utc)
        self.clock = patch("django.utils.timezone.now", return_value=self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.session = ClassDate.objects.create(date="2030-01-02", time="18:00")
        self.session.refresh_from_db()
        MeetingSettings.objects.update_or_create(pk=1, defaults={"meeting_link": "https://example.com/meeting"})
        mail.get_connection()
        mail.outbox.clear()

    def register(self, email="ada@example.com", immediate=True):
        with self.captureOnCommitCallbacks(execute=immediate):
            return book(session_date="2030-01-02", name="Ada Okafor", email=email, phone="8035550102")

    def job(self, kind=CONFIRMATION):
        return ScheduledEmail.objects.filter(kind=kind).order_by("-pk").first()

    def test_confirmation_admin_and_both_reminders_use_admin_templates(self):
        for kind in EmailTemplate.Slug.values:
            EmailTemplate.objects.filter(slug=kind).update(subject="Saved template {{ user_first_name }}", body="{{ session_time }} {{ meeting_link }}")
        sub = self.register()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, [sub.email])
        self.assertEqual(mail.outbox[0].subject, "Saved template Ada")
        self.assertIn("6:00 PM WAT (Africa/Lagos)", mail.outbox[0].body)
        self.assertEqual(mail.outbox[1].to, ["admin@example.com"])
        self.assertEqual(mail.outbox[1].reply_to, [sub.email])
        self.assertEqual(self.job().status, "sent")
        self.assertEqual(self.job().sent_at, self.now)
        self.assertFalse(EmailWorkerHeartbeat.objects.exists())  # Web requests must not masquerade as a worker
        for kind, hours in REMINDERS.items():
            due = self.session.starts_at - timedelta(hours=hours)
            self.assertEqual(self.job(kind).scheduled_at, due)
            self.assertTrue(timezone.is_aware(due))
            self.assertEqual(process_due(now=due-timedelta(microseconds=1)), 0)
            self.assertEqual(process_due(now=due), 1)
            self.assertEqual(process_due(now=due), 0)
            self.assertEqual(self.job(kind).status, "sent")
        sub.refresh_from_db()
        self.assertTrue(sub.reminder_sent and sub.reminder_1h_sent)
        self.assertEqual(len(mail.outbox), 4)

    @override_settings(TIME_ZONE="America/Toronto")
    def test_session_timezone_independent_of_current_django_timezone(self):
        self.register()
        self.assertEqual(self.session.starts_at.astimezone(dt_timezone.utc).hour, 17)
        self.assertEqual(self.job("meeting_reminder_24h").scheduled_at, datetime(2030, 1, 1, 17, tzinfo=dt_timezone.utc))

    def test_no_send_before_commit_or_after_rollback(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.register(immediate=False)
                raise RuntimeError("rollback")
        self.assertFalse(Submission.objects.exists())
        self.assertFalse(ScheduledEmail.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_repeated_submissions_case_normalized_and_repeated_workers(self):
        first = self.register(email="ADA@example.com")
        second = self.register(email="ada@example.com")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(ScheduledEmail.objects.count(), 4)
        process_due(now=self.session.starts_at-timedelta(minutes=30))
        process_due(now=self.session.starts_at-timedelta(minutes=30))
        self.assertEqual(len(mail.outbox), 2)

    def test_late_registrations_only_queue_future_reminders(self):
        for remaining, expected in [(25, 2), (24, 1), (2, 1), (1, 0), (0.5, 0)]:
            with self.subTest(remaining=remaining):
                with patch("django.utils.timezone.now", return_value=self.session.starts_at-timedelta(hours=remaining)):
                    sub = self.register(email=f"late{remaining}@example.com")
                self.assertEqual(sub.scheduled_emails.filter(kind__in=REMINDERS).count(), expected)
                self.assertEqual(sub.scheduled_emails.get(kind=CONFIRMATION).status, "sent")

    def test_past_and_ambiguous_sessions_rejected(self):
        with patch("django.utils.timezone.now", return_value=self.session.starts_at):
            with self.assertRaises(ValidationError):
                self.register()
        ClassDate.objects.create(date=self.session.date, time="19:00")
        with self.assertRaises(ValidationError):
            self.register()

    def test_reservation_cancellation_prevents_pending_sends(self):
        sub = self.register()
        reservation = sub.reservation
        reservation.is_cancelled = True
        reservation.save()
        self.assertEqual(sub.scheduled_emails.filter(status="cancelled").count(), 2)
        process_due(now=self.session.starts_at-timedelta(minutes=30))
        self.assertEqual(len(mail.outbox), 2)

    def test_submission_cancellation(self):
        sub = self.register()
        sub.is_cancelled = True
        sub.save()
        self.assertEqual(sub.scheduled_emails.filter(status="cancelled").count(), 2)

    def test_session_cancellation_and_deletion_and_reservation_deletion(self):
        sub = self.register()
        self.session.is_active = False
        self.session.save()
        self.assertEqual(sub.scheduled_emails.filter(status="pending").count(), 0)
        self.session.is_active = True
        self.session.save()
        self.assertEqual(sub.scheduled_emails.filter(status="pending").count(), 2)
        sub.reservation.delete()
        self.assertEqual(sub.scheduled_emails.filter(status="pending").count(), 0)
        self.session.delete()
        process_due(now=self.now+timedelta(days=1))
        self.assertEqual(len(mail.outbox), 2)

    def test_session_reschedule_recalculates_pending_without_reconfirming(self):
        sub = self.register()
        confirmation_sent_at = self.job().sent_at
        self.session.date += timedelta(days=7)
        self.session.time = datetime.strptime("20:00", "%H:%M").time()
        self.session.save()
        for kind, hours in REMINDERS.items():
            self.assertEqual(self.job(kind).scheduled_at, self.session.starts_at-timedelta(hours=hours))
        sub.refresh_from_db()
        sub.reservation.refresh_from_db()
        self.assertEqual(sub.session_date, self.session.date.isoformat())
        self.assertEqual(sub.reservation.session_date, sub.session_date)
        self.assertEqual(self.job().sent_at, confirmation_sent_at)
        self.assertEqual(len(mail.outbox), 2)

    def test_reservation_date_edit_moves_linked_session(self):
        sub = self.register()
        other = ClassDate.objects.create(date="2030-01-09", time="20:00")
        other.refresh_from_db()
        reservation = sub.reservation
        reservation.session_date = "2030-01-09"
        reservation.save()
        sub.refresh_from_db()
        self.assertEqual(sub.class_date_id, other.pk)
        self.assertEqual(self.job("meeting_reminder_1h").scheduled_at, other.starts_at-timedelta(hours=1))

    def test_reschedule_to_near_future_cancels_elapsed_reminder(self):
        self.register()
        self.session.date = self.now.date()
        self.session.time = datetime.strptime("14:00", "%H:%M").time()  # 13:00 UTC; one hour away
        self.session.save()
        self.assertEqual(self.job("meeting_reminder_24h").status, "cancelled")
        self.assertEqual(self.job("meeting_reminder_1h").status, "cancelled")

    def test_temporary_failures_retry_with_backoff_then_succeed(self):
        self.register(immediate=False)
        with patch("landing.email_queue._send", side_effect=SMTPConnectError(421, "temporarily unavailable")):
            process_due(now=self.now, kinds=[CONFIRMATION])
        job = self.job()
        self.assertEqual((job.status, job.attempts), ("pending", 1))
        self.assertIn("421", job.error)
        self.assertEqual(job.next_attempt_at, self.now+timedelta(minutes=1))
        self.assertEqual(process_due(now=self.now+timedelta(seconds=59), kinds=[CONFIRMATION]), 0)
        self.assertEqual(process_due(now=job.next_attempt_at, kinds=[CONFIRMATION]), 1)
        self.assertEqual(self.job().attempts, 2)
        self.assertEqual(self.job().error, "")

    def test_limited_retries_permanent_failure_and_zero_send_result(self):
        self.register(immediate=False)
        for attempt in range(4):
            with patch("landing.emailing.EmailMultiAlternatives.send", return_value=0):
                process_due(now=self.job().next_attempt_at, kinds=[CONFIRMATION])
        self.assertEqual((self.job().status, self.job().attempts), ("failed", 4))
        process_due(now=self.now+timedelta(days=10), kinds=[CONFIRMATION])
        self.assertEqual(self.job().attempts, 4)
        with patch("landing.email_queue._send", side_effect=SMTPDataError(550, "rejected")):
            process_due(now=self.now, kinds=[ADMIN])
        self.assertEqual(self.job(ADMIN).status, "failed")
        self.assertEqual(self.job(ADMIN).attempts, 1)

    def test_admin_failure_does_not_block_confirmation(self):
        self.register(immediate=False)
        original_send = __import__("landing.email_queue", fromlist=["_send"])._send
        def selectively_fail(job):
            if job.kind == ADMIN:
                raise SMTPDataError(550, "admin rejected")
            original_send(job)
        with patch("landing.email_queue._send", side_effect=selectively_fail):
            process_due(now=self.now)
        self.assertEqual(self.job().status, "sent")
        self.assertEqual(self.job(ADMIN).status, "failed")
        self.assertEqual(len(mail.outbox), 1)

    def test_failure_for_one_recipient_does_not_abort_batch(self):
        first = self.register(immediate=False)
        second = self.register(email="second@example.com", immediate=False)
        with patch("landing.email_queue._send", side_effect=[SMTPDataError(550, "recipient rejected"), None]):
            process_due(now=self.now, kinds=[CONFIRMATION])
        self.assertEqual(first.scheduled_emails.get(kind=CONFIRMATION).status, "failed")
        self.assertEqual(second.scheduled_emails.get(kind=CONFIRMATION).status, "sent")

    def test_ambiguous_disconnect_or_process_crash_never_auto_resends(self):
        self.register(immediate=False)
        with patch("landing.email_queue._send", side_effect=SMTPServerDisconnected("lost response")):
            process_due(now=self.now, kinds=[CONFIRMATION])
        self.assertEqual(self.job().status, "uncertain")
        ScheduledEmail.objects.filter(kind=ADMIN).update(status="sending", claimed_at=self.now)
        process_due(now=self.now+timedelta(minutes=6))
        self.assertEqual(self.job(ADMIN).status, "uncertain")
        self.assertEqual(mail.outbox, [])

    def test_overlapping_workers_cannot_claim_same_message(self):
        self.register(immediate=False)
        def overlapping_worker(job):
            self.assertEqual(process_due(now=self.now, kinds=[CONFIRMATION]), 0)
        with patch("landing.email_queue._send", side_effect=overlapping_worker) as send:
            self.assertEqual(process_due(now=self.now, kinds=[CONFIRMATION]), 1)
        send.assert_called_once()
        self.assertEqual(self.job().attempts, 1)

    def test_worker_restart_uses_persisted_queue_and_catches_up_across_midnight(self):
        self.register()
        # Pending records survive restarts; only reminders within grace are sent.
        call_command("process_email_queue", stdout=StringIO())
        with patch("django.utils.timezone.now", return_value=self.session.starts_at-timedelta(minutes=30)):
            call_command("process_email_queue", stdout=StringIO())
            call_command("process_email_queue", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(ScheduledEmail.objects.filter(status="expired").count(), 2)

    def test_never_sends_reminders_after_session_starts(self):
        self.register()
        process_due(now=self.session.starts_at)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(ScheduledEmail.objects.filter(status="expired").count(), 2)

    def test_missing_link_records_error_and_can_retry_after_configuration(self):
        self.register()
        MeetingSettings.objects.all().delete()
        due = self.job("meeting_reminder_24h").scheduled_at
        process_due(now=due)
        self.assertIn("No meeting link", self.job("meeting_reminder_24h").error)
        MeetingSettings.objects.create(meeting_link="https://example.com/new")
        process_due(now=due+timedelta(minutes=1))
        self.assertEqual(self.job("meeting_reminder_24h").status, "sent")
        self.assertIn("https://example.com/new", mail.outbox[-1].body)

    def test_status_command_reports_missing_fresh_and_stale_heartbeat(self):
        with self.assertRaises(CommandError):
            call_command("email_queue_status", stdout=StringIO())
        process_due(now=self.now)
        EmailWorkerHeartbeat.objects.create(name="email_scheduler", last_seen_at=self.now)
        call_command("email_queue_status", stdout=StringIO())
        with patch("django.utils.timezone.now", return_value=self.now+timedelta(minutes=3)):
            with self.assertRaises(CommandError):
                call_command("email_queue_status", stdout=StringIO())

    def test_legacy_enrollment_is_opt_in_and_does_not_replay_confirmation(self):
        sub = Submission.objects.create(name="Legacy", email="legacy@example.com", phone="123", session_date="2030-01-02", reminder_sent=True)
        call_command("enroll_legacy_reminders", stdout=StringIO())
        self.assertFalse(sub.scheduled_emails.exists())
        call_command("enroll_legacy_reminders", apply=True, stdout=StringIO())
        call_command("enroll_legacy_reminders", apply=True, stdout=StringIO())
        self.assertEqual(sub.scheduled_emails.get(kind=CONFIRMATION).status, "skipped")
        self.assertEqual(sub.scheduled_emails.get(kind="meeting_reminder_24h").status, "skipped")
        process_due(now=self.session.starts_at-timedelta(hours=1))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [sub.email])

    def test_editing_historical_submission_never_replays_confirmation(self):
        sub = Submission.objects.create(name="Legacy", email="legacy@example.com", phone="123", session_date="2030-01-02", reminder_sent=True)
        sub.class_date = self.session
        sub.save()
        self.assertFalse(sub.scheduled_emails.filter(kind__in=[CONFIRMATION, ADMIN, "meeting_reminder_24h"]).exists())
        self.assertEqual(sub.scheduled_emails.get().kind, "meeting_reminder_1h")

    def test_resolve_uncertain_without_sending_and_preserve_attempts(self):
        self.register(immediate=False)
        ScheduledEmail.objects.filter(kind=CONFIRMATION).update(status="uncertain", attempts=1)
        call_command("resolve_email_delivery", self.job().pk, retry=True, note="Provider confirms rejection", stdout=StringIO())
        self.assertEqual((self.job().status, self.job().attempts), ("pending", 1))
        self.assertEqual(mail.outbox, [])
        process_due(now=self.now, kinds=[CONFIRMATION])
        self.assertEqual((self.job().status, self.job().attempts), ("sent", 2))
        with self.assertRaises(CommandError):
            call_command("resolve_email_delivery", self.job().pk, retry=True, note="already sent", stdout=StringIO())

    def test_cancellation_rechecked_when_job_already_selected(self):
        sub = self.register(immediate=False)
        # Even bulk cancellation bypassing hooks is checked before transport.
        Submission.objects.filter(pk=sub.pk).update(is_cancelled=True)
        process_due(now=self.now)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(sub.scheduled_emails.filter(status="pending").count(), 2)  # future reminders are not due yet
        process_due(now=self.session.starts_at-timedelta(minutes=30))
        self.assertEqual(sub.scheduled_emails.filter(status="cancelled").count(), 4)

    def test_broker_failure_keeps_committed_records_and_beat_recovers(self):
        from .tasks import dispatch_due_emails, send_scheduled_email
        with patch.object(send_scheduled_email, "delay", side_effect=ConnectionError("broker down")):
            with self.assertLogs("landing.email_queue", level="ERROR"):
                sub = self.register()
        self.assertEqual(sub.scheduled_emails.filter(status="pending").count(), 4)
        self.assertEqual(mail.outbox, [])
        dispatch_due_emails()
        self.assertEqual(sub.scheduled_emails.filter(status="sent").count(), 2)
        dispatch_due_emails()
        self.assertEqual(len(mail.outbox), 2)

    def test_model_creation_also_enqueues_after_commit(self):
        from .tasks import send_scheduled_email
        with patch.object(send_scheduled_email, "delay") as publish:
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    sub = Submission.objects.create(name="Direct", email="direct@example.com", phone="123", class_date=self.session)
                    self.assertEqual(sub.scheduled_emails.count(), 4)
                    publish.assert_not_called()
            self.assertEqual(publish.call_count, 2)
        self.assertEqual(mail.outbox, [])

    def test_unique_registration_occurrence_kind_constraint(self):
        from django.db import IntegrityError
        sub = self.register(immediate=False)
        job = self.job()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ScheduledEmail.objects.create(submission=sub, occurrence=self.session, kind=CONFIRMATION,
                scheduled_at=self.now, next_attempt_at=self.now, session_at=job.session_at)

    def test_latest_template_and_all_compatible_placeholders(self):
        self.register(immediate=False)
        EmailTemplate.objects.filter(slug=CONFIRMATION).update(subject="Updated {{ name }}", body=
            "{{ user_first_name }}|{{ first_name }}|{{ user.name }}|{{ submission.name }}|{{ session_date }}|{{ session_time }}|{{ timezone }}|{{ meeting_link }}")
        process_due(kinds=[CONFIRMATION])
        self.assertEqual(mail.outbox[0].subject, "Updated Ada Okafor")
        self.assertIn("Ada|Ada|Ada Okafor|Ada Okafor|Wednesday, January 2, 2030|6:00 PM WAT (Africa/Lagos)|Africa/Lagos|https://example.com/meeting", mail.outbox[0].body)
        self.assertEqual(self.job().provider_accepted_at, self.now)
        self.assertEqual(self.job().last_attempt_at, self.now)

    def test_five_minute_grace_boundary(self):
        for seconds, expected in [(0, "sent"), (300, "sent"), (301, "expired")]:
            sub = self.register(email=f"grace{seconds}@example.com", immediate=False)
            job = sub.scheduled_emails.get(kind="meeting_reminder_1h")
            process_due(job_id=job.pk, now=job.scheduled_at+timedelta(seconds=seconds))
            job.refresh_from_db()
            self.assertEqual(job.status, expected)

    def test_restart_recovers_due_reminder_inside_grace(self):
        from .tasks import dispatch_due_emails
        sub = self.register()
        due = sub.scheduled_emails.get(kind="meeting_reminder_24h").scheduled_at
        with patch("django.utils.timezone.now", return_value=due+timedelta(minutes=2)):
            dispatch_due_emails()
            dispatch_due_emails()
        self.assertEqual(len(mail.outbox), 3)

    def test_bulk_reschedule_is_rechecked_before_transport(self):
        self.register(immediate=False)
        job = self.job("meeting_reminder_24h")
        ClassDate.objects.filter(pk=self.session.pk).update(date="2030-01-09")
        process_due(job_id=job.pk, now=job.scheduled_at)
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.scheduled_at.date().isoformat(), "2030-01-08")
        self.assertEqual(mail.outbox, [])

    def test_missing_template_error_is_saved_without_fallback(self):
        self.register(immediate=False)
        EmailTemplate.objects.filter(slug=CONFIRMATION).delete()
        process_due(kinds=[CONFIRMATION])
        self.assertEqual(self.job().status, "failed")
        self.assertIn("registration_complete", self.job().error)
        self.assertIn("missing", self.job().error)
        self.assertIsNone(self.job().provider_accepted_at)
        self.assertEqual(mail.outbox, [])

    def test_scheduler_heartbeat_does_not_masquerade_as_worker(self):
        from landing.scheduler import MonitoredScheduler
        from celery.beat import PersistentScheduler
        with patch.object(PersistentScheduler, "tick", return_value=30):
            self.assertEqual(MonitoredScheduler.tick(object.__new__(MonitoredScheduler)), 30)
        self.assertTrue(EmailWorkerHeartbeat.objects.filter(pk="email_scheduler").exists())
        self.assertFalse(EmailWorkerHeartbeat.objects.filter(pk="email_worker").exists())
        with self.assertRaisesMessage(CommandError, "email_worker"):
            call_command("email_queue_status", stdout=StringIO())

    def test_celery_task_claims_one_record_and_redelivery_is_safe(self):
        from landing.tasks import send_scheduled_email
        self.register(immediate=False)
        job = self.job()
        self.assertEqual(send_scheduled_email.apply(args=[job.pk]).get(), 1)
        self.assertEqual(send_scheduled_email.apply(args=[job.pk]).get(), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_expired_reminder_is_recalculated_after_reschedule(self):
        self.register()
        process_due(now=self.session.starts_at-timedelta(minutes=30))
        self.assertEqual(self.job("meeting_reminder_1h").status, "expired")
        self.session.date += timedelta(days=7)
        self.session.save()
        self.assertEqual(self.job("meeting_reminder_1h").status, "pending")
        self.assertEqual(self.job("meeting_reminder_1h").scheduled_at, self.session.starts_at-timedelta(hours=1))

    def test_invalid_early_deadline_is_corrected_without_send(self):
        sub = self.register(immediate=False)
        job = sub.scheduled_emails.get(kind="meeting_reminder_1h")
        ScheduledEmail.objects.filter(pk=job.pk).update(scheduled_at=self.now, next_attempt_at=self.now)
        process_due(job_id=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.attempts, 0)
        self.assertEqual(job.next_attempt_at, self.session.starts_at-timedelta(hours=1))
        self.assertEqual(mail.outbox, [])

    def test_latest_recipient_is_recorded_when_transport_accepts(self):
        sub = self.register(immediate=False)
        Submission.objects.filter(pk=sub.pk).update(email="new-address@example.com")
        process_due(kinds=[CONFIRMATION])
        self.assertEqual(self.job().recipient, "new-address@example.com")
        self.assertEqual(mail.outbox[0].to, ["new-address@example.com"])

    def test_pending_confirmation_follows_registration_moved_to_other_occurrence(self):
        sub = self.register(immediate=False)
        other = ClassDate.objects.create(date="2030-01-09", time="20:00")
        other.refresh_from_db()
        sub.class_date = other
        sub.save()
        self.assertEqual(sub.scheduled_emails.filter(kind=CONFIRMATION).count(), 1)
        self.assertEqual(self.job().occurrence_id, other.pk)
        process_due(kinds=[CONFIRMATION])
        self.assertEqual(self.job().status, "sent")
        self.assertIn("January 9, 2030", mail.outbox[0].body)
