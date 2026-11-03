"""Short Celery tasks; durable scheduling and retry state live in SQL."""
from celery import shared_task
from django.utils import timezone
from .models import EmailWorkerHeartbeat, ScheduledEmail


def worker_seen():
    EmailWorkerHeartbeat.objects.update_or_create(
        name="email_worker", defaults={"last_seen_at": timezone.now()})


@shared_task(soft_time_limit=60, time_limit=90)
def send_scheduled_email(job_id):
    from .email_queue import process_due
    worker_seen()
    return process_due(job_id=job_id, limit=1, record_heartbeat=False)


@shared_task(soft_time_limit=60, time_limit=90)
def dispatch_due_emails():
    from .email_queue import recover_stale_claims
    worker_seen()
    now = timezone.now()
    recover_stale_claims(now)
    ids = list(ScheduledEmail.objects.filter(status="pending", next_attempt_at__lte=now)
               .order_by("scheduled_at", "pk").values_list("pk", flat=True)[:1000])
    for job_id in ids:
        # Publishing does not change outbox state. A failed publish is recovered next tick.
        send_scheduled_email.delay(job_id)
    return len(ids)
