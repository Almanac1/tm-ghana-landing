from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone
from landing.models import EmailWorkerHeartbeat, ScheduledEmail


class Command(BaseCommand):
    help = "Read-only worker heartbeat and queue health; exits nonzero for stale heartbeat or delivery failures."

    def add_arguments(self, parser):
        parser.add_argument("--max-age", type=int, default=120, help="Maximum heartbeat age in seconds")

    def handle(self, *args, **options):
        now = timezone.now()
        heartbeat = EmailWorkerHeartbeat.objects.filter(pk="email_worker").first()
        self.stdout.write(f"Last completed queue poll: {heartbeat.last_seen_at if heartbeat else 'never'}")
        self.stdout.write(str(list(ScheduledEmail.objects.values("status").annotate(count=Count("pk")))))
        overdue = ScheduledEmail.objects.filter(status="pending", next_attempt_at__lt=now-timedelta(seconds=options["max_age"])).count()
        self.stdout.write(f"Overdue messages: {overdue}")
        if not heartbeat or heartbeat.last_seen_at < now-timedelta(seconds=options["max_age"]):
            raise CommandError("Worker heartbeat missing or stale")
        if overdue or ScheduledEmail.objects.filter(status__in=["failed", "uncertain"]).exists():
            raise CommandError("Email queue needs attention; inspect Scheduled emails in admin")
