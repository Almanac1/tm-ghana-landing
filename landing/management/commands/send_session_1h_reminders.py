from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from landing.models import ClassDate, Reservation, Submission


REMINDER_SUBJECT = "Starting in 1 hour: Your Transcendental Meditation session 🌿"


def _first_name(name: str) -> str:
    return name.strip().split(maxsplit=1)[0] if name.strip() else "there"


class Command(BaseCommand):
    help = "Send final reservation reminders when a session is one hour away."

    def add_arguments(self, parser):
        parser.add_argument(
            "--window-minutes",
            type=int,
            default=5,
            help="Send reminders due within this many minutes after their one-hour reminder time.",
        )

    def handle(self, *args, **options):
        window_minutes = options["window_minutes"]
        if window_minutes <= 0:
            raise ValueError("--window-minutes must be greater than zero.")

        now = timezone.localtime()
        window = timedelta(minutes=window_minutes)
        earliest_session_date = (now + timedelta(hours=1)).date()
        latest_session_date = (now + timedelta(hours=1) + window).date()
        class_dates = ClassDate.objects.filter(
            is_active=True,
            session_type=Reservation.SessionType.ONLINE,
            date__range=(earliest_session_date, latest_session_date),
        ).order_by("date", "time", "id")

        sent_count = 0
        for class_date in class_dates:
            scheduled_at = timezone.make_aware(
                datetime.combine(class_date.date, class_date.time),
                timezone.get_current_timezone(),
            )
            reminder_at = scheduled_at - timedelta(hours=1)
            if not reminder_at <= now < reminder_at + window:
                continue
            if not class_date.meeting_link:
                self.stderr.write(
                    self.style.WARNING(
                        f"Skipped {class_date.date} {class_date.time}: no meeting link is configured."
                    )
                )
                continue

            pending_submission_ids = Submission.objects.filter(
                session_type=Reservation.SessionType.ONLINE,
                session_date=class_date.date.isoformat(),
                reminder_1h_sent=False,
            ).values_list("id", flat=True)
            for submission_id in pending_submission_ids:
                if self._send_reminder(submission_id, class_date):
                    sent_count += 1

        self.stdout.write(self.style.SUCCESS(f"Sent {sent_count} one-hour session reminder(s)."))

    def _send_reminder(self, submission_id: int, class_date: ClassDate) -> bool:
        with transaction.atomic():
            submission = Submission.objects.select_for_update().filter(
                id=submission_id,
                reminder_1h_sent=False,
            ).first()
            if submission is None:
                return False

            body = render_to_string(
                "landing/emails/visitor_session_1h_reminder.txt",
                {
                    "name": submission.name,
                    "user_first_name": _first_name(submission.name),
                    "session_time": class_date.time.strftime("%-I:%M %p"),
                    "meeting_link": class_date.meeting_link,
                },
            )
            EmailMultiAlternatives(
                subject=REMINDER_SUBJECT,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[submission.email],
            ).send(fail_silently=False)
            submission.reminder_1h_sent = True
            submission.save(update_fields=["reminder_1h_sent"])
        return True
