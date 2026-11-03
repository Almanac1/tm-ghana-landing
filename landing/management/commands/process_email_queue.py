from django.core.management.base import BaseCommand, CommandError
from landing.tasks import dispatch_due_emails


class Command(BaseCommand):
    help = "Ask Celery to dispatch due outbox records once. Run Celery Beat for continuous scheduling."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Removed; use Celery Beat")
        parser.add_argument("--interval", type=int, default=30, help="Deprecated")
        parser.add_argument("--limit", type=int, default=100, help="Deprecated")

    def handle(self, *args, **options):
        if options["loop"]:
            raise CommandError("Standalone polling removed. Run a Celery worker and one Celery Beat scheduler.")
        dispatch_due_emails.delay()
        self.stdout.write("Requested Celery dispatch; inspect Scheduled emails for provider acceptance.")
