import logging
from celery.beat import PersistentScheduler
from django.utils import timezone
from .models import EmailWorkerHeartbeat

logger = logging.getLogger(__name__)


class MonitoredScheduler(PersistentScheduler):
    """Beat heartbeat is independent of tasks executing on the worker."""
    def tick(self, *args, **kwargs):
        try:
            EmailWorkerHeartbeat.objects.update_or_create(
                name="email_scheduler", defaults={"last_seen_at": timezone.now()})
        except Exception:
            logger.exception("Could not record Celery Beat heartbeat")
        return super().tick(*args, **kwargs)
