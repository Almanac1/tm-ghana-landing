"""Send four clearly marked synthetic audit messages to an explicitly supplied inbox.

Usage: .venv/bin/python scripts/email_audit_live.py recipient@example.com
Reads current email templates/settings; does not create registrations or change sent flags.
"""
import json
import os
from pathlib import Path
import sys
from datetime import timedelta
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.core import mail
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.test import override_settings
from django.utils import timezone
from landing.emailing import send_template_email
from landing.models import EmailTemplate, Submission


def main():
    recipient = sys.argv[1]
    validate_email(recipient)
    audit_id = uuid4().hex[:10]
    session_date = (timezone.now() + timedelta(days=7)).date()
    submission = Submission(name="Email Audit Test", email=recipient, phone="TEST ONLY",
                            session_type="online", session_date=session_date.isoformat(),
                            message="Synthetic email audit; no booking was created.", created_at=timezone.now())
    context = dict(submission=submission, user=submission, user_first_name="Email", first_name="Email",
                   name=submission.name, session_type="Online Session",
                   session_date=session_date.strftime("%A, %B %d, %Y"), session_time="6:00 PM (test only)",
                   meeting_link="https://example.com/email-audit-test-only")
    with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
        mail.get_connection()
        mail.outbox.clear()
        mail.EmailMultiAlternatives(subject="Administrator registration alert",
            body=render_to_string("landing/emails/admin_submission_notification.txt", context),
            to=[recipient], reply_to=[recipient]).send()
        for slug in EmailTemplate.Slug.values:
            send_template_email(slug=slug, to=[recipient], context=context)
        messages = list(mail.outbox)

    labels = ["admin_registration", *EmailTemplate.Slug.values]
    connection = mail.get_connection(timeout=20)
    for label, message in zip(labels, messages):
        message.subject = f"[TM Nigeria EMAIL AUDIT {audit_id}] {message.subject}"
        message.body = "TEST ONLY: This is a synthetic notification audit. No session has been booked.\n\n" + message.body
        message.connection = connection
        try:
            count = message.send(fail_silently=False)
            print(json.dumps({"audit_id": audit_id, "notification": label, "recipient": recipient,
                              "smtp_accepted": count == 1}), flush=True)
        except Exception as exc:
            print(json.dumps({"audit_id": audit_id, "notification": label, "recipient": recipient,
                              "smtp_accepted": False, "error_type": type(exc).__name__,
                              "smtp_code": getattr(exc, "smtp_code", None)}), flush=True)
    connection.close()


if __name__ == "__main__":
    main()
