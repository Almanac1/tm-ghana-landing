"""Email audit: isolated delivery checks and expected failures for confirmed defects.

Expected failures describe desired behavior, rather than endorsing current defects.
All messages use Django's in-memory backend; no real recipients are contacted.
"""
from datetime import datetime, time, timedelta
from io import StringIO
from smtplib import SMTPException
from unittest import expectedFailure
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .emailing import send_template_email
from .forms import get_active_class_date_options
from .models import ClassDate, EmailTemplate, MeetingSettings, Submission
from .views import _send_submission_emails


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="sender@example.com",
    LANDING_ADMIN_EMAIL="admin@example.com",
    TIME_ZONE="UTC",
)
class EmailAuditTests(TestCase):
    commands = (
        ("send_session_reminders", 24, "reminder_sent"),
        ("send_session_1h_reminders", 1, "reminder_1h_sent"),
    )

    def setUp(self):
        self.now = timezone.make_aware(datetime(2030, 1, 1, 18))
        MeetingSettings.objects.update_or_create(
            pk=1, defaults={"meeting_link": "https://example.com/meeting"}
        )
        mail.get_connection()  # Initialize the isolated outbox.
        mail.outbox.clear()

    def submission(self, session_date, **extra):
        data = dict(name="Ada O'Neil", email="ada@example.com", phone="8035550102",
                    session_type="online", session_date=session_date.isoformat())
        data.update(extra)
        return Submission.objects.create(**data)

    def scheduled(self, hours, offset=timedelta()):
        when = self.now + timedelta(hours=hours) + offset
        session = ClassDate.objects.create(date=when.date(), time=when.time(), session_type="online")
        return session, self.submission(when.date())

    def run_reminder(self, command, now=None, **options):
        with patch(f"landing.management.commands.{command}.timezone.now", return_value=now or self.now):
            call_command(command, stdout=StringIO(), stderr=StringIO(), **options)

    def render_email(self, slug=EmailTemplate.Slug.REGISTRATION_COMPLETE):
        send_template_email(slug=slug, to=["ada@example.com"], context={
            "user_first_name": "Ada", "session_date": "Wednesday, January 2, 2030",
            "session_time": "6:00 PM", "meeting_link": "https://example.com/meeting",
        })

    def test_registration_recipients_sender_reply_to_and_content(self):
        session, submission = self.scheduled(24)
        _send_submission_emails(submission)
        self.assertEqual(len(mail.outbox), 2)
        admin, visitor = mail.outbox
        self.assertEqual(admin.to, ["admin@example.com"])
        self.assertEqual(admin.reply_to, [submission.email])
        self.assertEqual(visitor.to, [submission.email])
        for message in mail.outbox:
            self.assertEqual(message.from_email, "sender@example.com")
            self.assertIn("January 2, 2030", message.body)
            self.assertIn("6:00 PM", message.body)
        self.assertIn("Hi Ada", visitor.body)

    def test_missing_templates_fall_back_for_all_slugs(self):
        EmailTemplate.objects.all().delete()
        with self.assertLogs("landing.emailing", level="ERROR"):
            for slug in EmailTemplate.Slug.values:
                self.render_email(slug)
        self.assertEqual(len(mail.outbox), 3)
        self.assertTrue(all("Ada" in message.body for message in mail.outbox))

    def test_invalid_template_syntax_falls_back(self):
        for slug in EmailTemplate.Slug.values:
            EmailTemplate.objects.filter(slug=slug).update(body="{% broken_tag %}")
            with self.assertLogs("landing.emailing", level="ERROR"):
                self.render_email(slug)
        self.assertTrue(all("{%" not in message.body for message in mail.outbox))

    def test_send_failure_propagates(self):
        with patch("landing.emailing.EmailMultiAlternatives.send", side_effect=SMTPException("unavailable")):
            with self.assertRaises(SMTPException):
                self.render_email()

    def test_reminder_boundaries_and_sequential_deduplication(self):
        for command, hours, flag in self.commands:
            for minutes, expected in ((-1, 0), (0, 1), (4, 1), (5, 0), (6, 0)):
                with self.subTest(command=command, minutes=minutes):
                    ClassDate.objects.all().delete()
                    Submission.objects.all().delete()
                    mail.outbox.clear()
                    _, submission = self.scheduled(hours)
                    now = self.now + timedelta(minutes=minutes)
                    self.run_reminder(command, now)
                    self.run_reminder(command, now)
                    self.assertEqual(len(mail.outbox), expected)
                    submission.refresh_from_db()
                    self.assertEqual(getattr(submission, flag), bool(expected))

    def test_missing_meeting_link_skips_both_reminders(self):
        MeetingSettings.objects.all().delete()
        for command, hours, flag in self.commands:
            _, submission = self.scheduled(hours)
            self.run_reminder(command)
            submission.refresh_from_db()
            self.assertFalse(getattr(submission, flag))
        self.assertEqual(mail.outbox, [])

    def test_inactive_and_non_online_sessions_are_skipped(self):
        for command, hours, _ in self.commands:
            session, _ = self.scheduled(hours)
            session.is_active = False
            session.save()
            self.run_reminder(command)
            session.is_active = True
            session.session_type = "physical"
            session.save()
            self.run_reminder(command)
        self.assertEqual(mail.outbox, [])

    def test_invalid_windows_rejected(self):
        for command, _, _ in self.commands:
            for minutes in (0, -5):
                with self.assertRaises(ValueError):
                    self.run_reminder(command, window_minutes=minutes)

    def test_failed_reminder_keeps_pending_flag_and_can_retry(self):
        for command, hours, flag in self.commands:
            ClassDate.objects.all().delete()
            Submission.objects.all().delete()
            mail.outbox.clear()
            _, submission = self.scheduled(hours)
            with patch(f"landing.management.commands.{command}.send_template_email", side_effect=SMTPException("down")):
                with self.assertRaises(SMTPException):
                    self.run_reminder(command)
            submission.refresh_from_db()
            self.assertFalse(getattr(submission, flag))
            self.run_reminder(command)
            self.assertEqual(len(mail.outbox), 1)

    @expectedFailure
    def test_defect_admin_failure_should_not_block_visitor_confirmation(self):
        _, submission = self.scheduled(24)
        with patch("landing.views.EmailMultiAlternatives.send", side_effect=SMTPException("admin rejected")):
            with patch("landing.views.send_template_email") as visitor_send:
                try:
                    _send_submission_emails(submission)
                except SMTPException:
                    pass
                visitor_send.assert_called_once()

    @expectedFailure
    def test_defect_failure_for_one_recipient_should_not_abort_batch(self):
        self.scheduled(24)
        self.submission((self.now + timedelta(hours=24)).date(), email="second@example.com")
        with patch("landing.management.commands.send_session_reminders.send_template_email",
                   side_effect=[SMTPException("recipient rejected"), None]) as send:
            try:
                self.run_reminder("send_session_reminders")
            except SMTPException:
                pass
            self.assertEqual(send.call_count, 2)

    def test_unscheduled_dates_are_not_bookable_and_do_not_send_reminders(self):
        ClassDate.objects.all().delete()
        self.now = timezone.make_aware(datetime(2030, 1, 1, 18))
        self.submission((self.now + timedelta(hours=24)).date())
        with patch("landing.forms.timezone.now", return_value=self.now):
            self.assertEqual(get_active_class_date_options(), [])
        self.run_reminder("send_session_reminders")
        self.assertEqual(len(mail.outbox), 0)

    @expectedFailure
    def test_defect_24h_midnight_crossing_should_still_send_within_window(self):
        self.now = timezone.make_aware(datetime(2030, 1, 1, 23, 58))
        self.scheduled(24)
        self.run_reminder("send_session_reminders", self.now + timedelta(minutes=3))
        self.assertEqual(len(mail.outbox), 1)

    @expectedFailure
    def test_defect_1h_date_filter_should_include_session_before_midnight(self):
        self.now = timezone.make_aware(datetime(2030, 1, 1, 22, 58))
        self.scheduled(1)
        self.run_reminder("send_session_1h_reminders", self.now + timedelta(minutes=3))
        self.assertEqual(len(mail.outbox), 1)

    @expectedFailure
    def test_defect_zero_send_result_should_not_mark_reminder_sent(self):
        _, submission = self.scheduled(24)
        with patch("landing.emailing.EmailMultiAlternatives.send", return_value=0):
            self.run_reminder("send_session_reminders")
        submission.refresh_from_db()
        self.assertFalse(submission.reminder_sent)

    @expectedFailure
    def test_defect_unknown_template_variables_should_trigger_fallback(self):
        EmailTemplate.objects.filter(slug="registration_complete").update(body="Hello {{ typo_first_name }}")
        self.render_email()
        self.assertIn("Ada", mail.outbox[0].body)

    @expectedFailure
    def test_defect_lead_edit_should_validate_recipient_before_sending(self):
        self.now = timezone.make_aware(datetime(2030, 1, 1, 18))
        self.scheduled(24)
        with patch("landing.forms.timezone.now", return_value=self.now):
            self.client.post(reverse("home"), {"form_type": "lead", "ui_action": "edit",
                "payload_name": "Ada", "payload_email": "invalid-address", "payload_phone": "123"})
            response = self.client.post(reverse("home"), {"form_type": "reservation",
                "reservation-session_date": "2030-01-02"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(any("invalid-address" in message.to for message in mail.outbox))
