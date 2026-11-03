import smtplib
from collections.abc import Mapping

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Engine

from .models import EmailTemplate


def send_template_email(*, slug: str, to: list[str], context: Mapping[str, object], headers=None) -> None:
    """Read the latest database template; configuration errors must remain visible."""
    try:
        email_template = EmailTemplate.objects.get(slug=slug)
    except EmailTemplate.DoesNotExist as exc:
        raise ValueError(f"Required email template '{slug}' is missing") from exc
    template_context = Context(dict(context), autoescape=False)
    engine = Engine(string_if_invalid="__UNKNOWN_EMAIL_VARIABLE__")
    subject = engine.from_string(email_template.subject).render(template_context).strip()
    body = engine.from_string(email_template.body).render(template_context)
    if "__UNKNOWN_EMAIL_VARIABLE__" in subject + body:
        raise ValueError(f"Unknown or missing variable in email template '{slug}'")
    if not subject or not body.strip():
        raise ValueError(f"Email template '{slug}' requires a nonempty subject and body")

    subject = " ".join(subject.splitlines())
    result = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        headers=headers,
    ).send(fail_silently=False)

    if result != 1:
        raise smtplib.SMTPConnectError(421, "Backend accepted zero messages")
