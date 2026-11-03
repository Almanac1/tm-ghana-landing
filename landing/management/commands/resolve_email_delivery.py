from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from landing.models import ScheduledEmail, Submission


class Command(BaseCommand):
    help = "Resolve a failed/uncertain message after reviewing provider logs. Does not send email itself."

    def add_arguments(self, parser):
        parser.add_argument("id", type=int)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--accepted", action="store_true", help="Provider logs prove SMTP accepted this message")
        group.add_argument("--retry", action="store_true", help="Requeue within remaining retry budget (or authorize one extra attempt if exhausted); provider logs prove no acceptance")
        parser.add_argument("--note", required=True, help="Provider investigation evidence (no credentials)")

    def handle(self, *args, **options):
        job = ScheduledEmail.objects.filter(pk=options["id"], status__in=["failed", "uncertain"]).first()
        if not job:
            raise CommandError("Only failed or uncertain jobs can be resolved")
        now = timezone.now()
        if options["retry"]:
            changed = ScheduledEmail.objects.filter(pk=job.pk, status=job.status).update(
                status="pending", next_attempt_at=now,
                error=f"Manual retry authorized: {options['note']}; previous error: {job.error}"[:2000])
        else:
            changed = ScheduledEmail.objects.filter(pk=job.pk, status=job.status).update(
                status="sent", sent_at=now, provider_accepted_at=now, error=f"Operator verified provider acceptance: {options['note']}"[:2000])
            flag = {"meeting_reminder_24h": "reminder_sent", "meeting_reminder_1h": "reminder_1h_sent"}.get(job.kind)
            if changed and flag:
                Submission.objects.filter(pk=job.submission_id).update(**{flag: True})
        if not changed:
            raise CommandError("Job changed concurrently; inspect current status")
        self.stdout.write("Recorded resolution. Attempt count preserved; a manual retry authorizes one additional attempt if retry limit was reached.")
