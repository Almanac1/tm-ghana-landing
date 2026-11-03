from django.core.management.base import BaseCommand
from landing.email_queue import process_due


class Command(BaseCommand):
    help = "Compatibility command: process persisted meeting_reminder_1h jobs. Use process_email_queue for all email."

    def add_arguments(self, parser):
        parser.add_argument("--window-minutes", type=int, default=5,
                            help="Deprecated: persisted jobs catch up until the session starts.")

    def handle(self, *args, **options):
        if options["window_minutes"] <= 0:
            raise ValueError("--window-minutes must be greater than zero")
        self.stdout.write(f"Sent {process_due(kinds=['meeting_reminder_1h'])} reminder(s).")
