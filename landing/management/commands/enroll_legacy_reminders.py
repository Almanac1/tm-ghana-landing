import hashlib
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from landing.email_queue import reconcile, ADMIN, CONFIRMATION, REMINDERS
from landing.models import ClassDate, Submission, ScheduledEmail


class Command(BaseCommand):
    help = "Preview legacy future bookings; --apply links unambiguous sessions and queues future reminders only. Never replays confirmations."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        now = timezone.now()
        for submission in Submission.objects.filter(class_date__isnull=True, is_cancelled=False):
            matches = list(ClassDate.objects.filter(date=submission.session_date, session_type=submission.session_type, is_active=True))
            if len(matches) != 1 or matches[0].starts_at <= now:
                self.stdout.write(f"Skipped submission {submission.pk}: no unique future session")
                continue
            session = matches[0]
            key = hashlib.sha256(f"{submission.email.strip().lower()}:{session.pk}".encode()).hexdigest()
            if Submission.objects.filter(registration_key=key).exclude(pk=submission.pk).exists():
                self.stdout.write(f"Skipped submission {submission.pk}: duplicate recipient/session; review manually")
                continue
            if options["apply"]:
                with transaction.atomic():
                    Submission.objects.filter(pk=submission.pk).update(class_date=session, registration_key=key, email=submission.email.strip().lower())
                    submission.class_date = session
                    for kind in [ADMIN, CONFIRMATION, *REMINDERS]:
                        already_sent = (kind == "meeting_reminder_24h" and submission.reminder_sent) or (kind == "meeting_reminder_1h" and submission.reminder_1h_sent)
                        if kind in [ADMIN, CONFIRMATION] or already_sent:
                            ScheduledEmail.objects.get_or_create(submission=submission, kind=kind, defaults={
                                "scheduled_at": submission.created_at, "next_attempt_at": submission.created_at,
                                "session_at": session.starts_at, "status": "skipped",
                                "error": "Historical notification; delivery unknown, deliberately not replayed",
                            })
                    reconcile(submission, now=now)
            self.stdout.write(f"{'Enrolled' if options['apply'] else 'Would enroll'} submission {submission.pk} in session {session.pk}")
