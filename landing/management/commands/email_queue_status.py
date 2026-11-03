from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone
from landing.models import EmailWorkerHeartbeat, ScheduledEmail


class Command(BaseCommand):
    help = "Read-only worker/scheduler heartbeat and queue health."

    def add_arguments(self, parser):
        parser.add_argument("--max-age", type=int, default=120)

    def handle(self, *args, **options):
        now = timezone.now()
        threshold = now - timedelta(seconds=options["max_age"])
        stale = []
        for name in ("email_worker", "email_scheduler"):
            heartbeat = EmailWorkerHeartbeat.objects.filter(pk=name).first()
            self.stdout.write(f"{name}: {heartbeat.last_seen_at if heartbeat else 'never'}")
            if not heartbeat or heartbeat.last_seen_at < threshold:
                stale.append(name)
        self.stdout.write(str(list(ScheduledEmail.objects.values("status").annotate(count=Count("pk")))))
        overdue = ScheduledEmail.objects.filter(status="pending", next_attempt_at__lt=threshold).count()
        self.stdout.write(f"Overdue messages: {overdue}")
        if stale:
            raise CommandError("Heartbeat missing or stale: " + ", ".join(stale))
        if overdue or ScheduledEmail.objects.filter(status__in=["failed", "uncertain"]).exists():
            raise CommandError("Email queue needs attention; inspect Scheduled emails in admin")
