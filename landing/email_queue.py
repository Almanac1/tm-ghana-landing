"""Durable outbox. All workers claim with conditional UPDATE (including on SQLite).

SMTP has no idempotency API: ambiguous delivery is held for manual review rather
than retried automatically. A stable Message-ID assists provider reconciliation.
"""
import hashlib
import logging
import smtplib
import socket
from datetime import timedelta
from email.utils import make_msgid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives

from .emailing import send_template_email
from .meeting_settings import get_meeting_link
from .models import ClassDate, EmailTemplate, Reservation, ScheduledEmail, Submission, EmailWorkerHeartbeat

logger = logging.getLogger(__name__)
CONFIRMATION = EmailTemplate.Slug.REGISTRATION_COMPLETE
ADMIN = "admin_notification"
REMINDERS = {EmailTemplate.Slug.MEETING_REMINDER_24H: 24, EmailTemplate.Slug.MEETING_REMINDER_1H: 1}
MAX_ATTEMPTS = 4


def reconcile(submission, now=None, include_registration=False):
    now = now or timezone.now()
    session = submission.class_date
    active = (session and session.is_active and session.session_type == "online"
              and not submission.is_cancelled
              and not (submission.reservation_id and submission.reservation.is_cancelled))
    if not active:
        submission.scheduled_emails.filter(status="pending").update(status="cancelled", error="Reservation or session cancelled/unavailable")
        return
    starts = session.starts_at
    for kind in [CONFIRMATION, ADMIN, *REMINDERS]:
        due = starts - timedelta(hours=REMINDERS[kind]) if kind in REMINDERS else now
        job = submission.scheduled_emails.filter(kind=kind).first()
        if job is None:
            # Editing a historical submission must never replay its confirmation.
            if kind in (CONFIRMATION, ADMIN) and not include_registration:
                continue
            if (kind == "meeting_reminder_24h" and submission.reminder_sent) or (kind == "meeting_reminder_1h" and submission.reminder_1h_sent):
                continue
            # Late registrations do not receive already-due reminders.
            if kind in REMINDERS and due <= now:
                continue
            ScheduledEmail.objects.get_or_create(submission=submission, kind=kind, defaults={
                "scheduled_at": due, "next_attempt_at": due, "session_at": starts,
                "message_id": make_msgid(domain="tmnigeria.com"),
            })
        elif job.status in ("pending", "cancelled") and (job.session_at != starts or job.status == "cancelled"):
            status = "cancelled" if kind in REMINDERS and due <= now else "pending"
            submission.scheduled_emails.filter(pk=job.pk, status=job.status).update(
                session_at=starts, scheduled_at=due if kind in REMINDERS else job.scheduled_at,
                next_attempt_at=due if kind in REMINDERS else now,
                status=status, error="Reminder time has passed" if status == "cancelled" else "")


def book(*, session_date, name, email, phone, message=""):
    """One reservation per normalized email/session; repeated POSTs are idempotent."""
    email = email.strip().lower()
    validate_email(email)
    with transaction.atomic():
        sessions = list(ClassDate.objects.filter(date=session_date, is_active=True, session_type="online"))
        if len(sessions) != 1 or sessions[0].starts_at <= timezone.now():
            raise ValidationError("This session is no longer available. Please select another date.")
        session = sessions[0]
        key = hashlib.sha256(f"{email}:{session.pk}".encode()).hexdigest()
        submission, created = Submission.objects.get_or_create(registration_key=key, defaults={
            "name": name, "email": email, "phone": phone, "message": message,
            "class_date": session, "session_date": session_date,
        })
        if created:
            reservation = Reservation.objects.create(session_date=session_date, session_type="online")
            submission.reservation = reservation
            submission.save(update_fields=["reservation"])
        # Delivery only after the complete reservation transaction commits.
        transaction.on_commit(lambda: deliver_immediate_safely(submission.pk))
    return submission


def deliver_immediate_safely(submission_id):
    try:
        process_due(submission_id=submission_id, kinds=[ADMIN, CONFIRMATION], record_heartbeat=False)
    except Exception:
        # The committed outbox remains available to the standalone worker.
        logger.exception("Immediate email dispatch failed for submission %s", submission_id)


def _send(job):
    submission = job.submission
    session = submission.class_date
    context = {
        "submission": submission, "user": submission, "name": submission.name,
        "first_name": submission.name.split()[0] if submission.name.strip() else "there",
        "user_first_name": submission.name.split()[0] if submission.name.strip() else "there",
        "session_type": submission.get_session_type_display(),
        "session_date": session.date.strftime("%A, %B %-d, %Y"),
        "session_time": session.time.strftime("%-I:%M %p") + " WAT (Africa/Lagos)",
        "meeting_link": get_meeting_link(),
    }
    if job.kind == ADMIN:
        context["session_date"] += " at " + session.time.strftime("%-I:%M %p")
        message = EmailMultiAlternatives(
            subject=f"New registration entry from {submission.name}",
            body=render_to_string("landing/emails/admin_submission_notification.txt", context),
            from_email=settings.DEFAULT_FROM_EMAIL, to=[settings.LANDING_ADMIN_EMAIL],
            reply_to=[submission.email], headers={"Message-ID": job.message_id},
        )
        if message.send(fail_silently=False) != 1:
            raise smtplib.SMTPConnectError(421, "Backend accepted zero messages")
    else:
        if job.kind in REMINDERS and not context["meeting_link"]:
            raise smtplib.SMTPConnectError(421, "No meeting link configured")
        send_template_email(slug=job.kind, to=[submission.email], context=context,
                            headers={"Message-ID": job.message_id})


def process_due(*, now=None, submission_id=None, kinds=None, limit=100, record_heartbeat=True):
    now = now or timezone.now()
    # Never automatically resend a job whose process may have died after SMTP acceptance.
    ScheduledEmail.objects.filter(status="sending", claimed_at__lt=now-timedelta(minutes=5)).update(
        status="uncertain", error="Worker stopped during send; check provider logs before retrying")
    jobs = ScheduledEmail.objects.filter(status="pending", next_attempt_at__lte=now)
    if submission_id is not None:
        jobs = jobs.filter(submission_id=submission_id)
    if kinds:
        jobs = jobs.filter(kind__in=kinds)
    ids = list(jobs.order_by("scheduled_at", "pk").values_list("pk", flat=True)[:limit])
    sent = 0
    for pk in ids:
        # Autocommitted claim; never hold a database transaction open over SMTP.
        claimed = ScheduledEmail.objects.filter(pk=pk, status="pending", next_attempt_at__lte=now).update(
            status="sending", claimed_at=now, attempts=F("attempts") + 1)
        if not claimed:
            continue
        job = ScheduledEmail.objects.select_related("submission__class_date", "submission__reservation").get(pk=pk)
        submission = job.submission
        session = submission.class_date
        if (submission.is_cancelled or not session or not session.is_active or session.session_type != "online"
                or (submission.reservation_id and submission.reservation.is_cancelled)
                or (job.kind in REMINDERS and session.starts_at <= now)):
            ScheduledEmail.objects.filter(pk=pk, status="sending").update(status="cancelled", error="Cancelled/unavailable or session has started")
            continue
        if job.session_at != session.starts_at:
            ScheduledEmail.objects.filter(pk=pk, status="sending").update(status="pending")
            reconcile(submission, now=now)
            continue
        try:
            _send(job)
        except Exception as exc:
            # A 4xx SMTP reply explicitly rejects delivery; connection refusal is also safe to retry.
            code = getattr(exc, "smtp_code", None)
            temporary = isinstance(exc, (ConnectionRefusedError, socket.gaierror))
            temporary = temporary or (code is not None and 400 <= code < 500)
            if isinstance(exc, smtplib.SMTPRecipientsRefused):
                temporary = all(400 <= value[0] < 500 for value in exc.recipients.values())
            ambiguous = isinstance(exc, (TimeoutError, ConnectionResetError, BrokenPipeError, smtplib.SMTPServerDisconnected))
            status = "uncertain" if ambiguous else "pending" if temporary and job.attempts < MAX_ATTEMPTS else "failed"
            ScheduledEmail.objects.filter(pk=pk, status="sending").update(
                status=status, error=f"{type(exc).__name__}: {exc}"[:2000],
                next_attempt_at=now + timedelta(minutes=2 ** (job.attempts - 1)))
            logger.warning("Email %s attempt %s: %s", pk, job.attempts, status)
            continue
        ScheduledEmail.objects.filter(pk=pk, status="sending").update(status="sent", sent_at=timezone.now(), error="")
        flag = {EmailTemplate.Slug.MEETING_REMINDER_24H: "reminder_sent", EmailTemplate.Slug.MEETING_REMINDER_1H: "reminder_1h_sent"}.get(job.kind)
        if flag:
            Submission.objects.filter(pk=submission.pk).update(**{flag: True})
        sent += 1
    if record_heartbeat:
        EmailWorkerHeartbeat.objects.update_or_create(name="email_worker", defaults={"last_seen_at": timezone.now()})
    return sent
