from django.core.management.base import BaseCommand
from landing.tasks import dispatch_due_emails


class Command(BaseCommand):
    help = "Compatibility alias: ask Celery to dispatch due outbox records."

    def add_arguments(self, parser):
        parser.add_argument("--window-minutes", type=int, default=5,
                            help="Deprecated: reminders expire after five minutes.")

    def handle(self, *args, **options):
        if options["window_minutes"] <= 0:
            raise ValueError("--window-minutes must be greater than zero")
        dispatch_due_emails.delay()
        self.stdout.write("Requested Celery dispatch of due emails.")
