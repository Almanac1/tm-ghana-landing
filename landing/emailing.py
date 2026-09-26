import logging
from collections.abc import Mapping

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template, TemplateSyntaxError

from .models import EmailTemplate


logger = logging.getLogger(__name__)


DEFAULT_EMAIL_TEMPLATES = {
    EmailTemplate.Slug.REGISTRATION_COMPLETE: {
        "subject": "Your Transcendental Meditation Session Reservation",
        "body": """Hi {{ user_first_name }},

Thank you for reserving your place with us. ✨

We’re delighted to welcome you to your introductory Transcendental Meditation session.

Your session details
🌿 Format: Online
📅 Date: {{ session_date }}
⏰ Time: {{ session_time }}

This will be a gentle introduction to Transcendental Meditation—an opportunity to learn more about the practice, how it works, and how it can become a simple part of your everyday life.

We’ll send you the meeting details ({{ meeting_link }}) and a few helpful notes before your session.

We look forward to meeting you and sharing this experience with you.

Warmly,
Transcendental Meditation Team""",
    },
    EmailTemplate.Slug.MEETING_REMINDER_24H: {
        "subject": "Reminder: Your Transcendental Meditation session is tomorrow 🌿",
        "body": """Hi {{ user_first_name }}, 🌿

Just a gentle reminder that your introductory Transcendental Meditation session is tomorrow.

📅 {{ session_date }}
⏰ {{ session_time }}
💻 Online

Join your session:
{{ meeting_link }}

We recommend joining a few minutes early so you can settle in comfortably before we begin.

Come as you are. There’s nothing you need to prepare—just bring your curiosity and an open mind. ✨

We look forward to welcoming you.

Warmly,
Transcendental Meditation Team""",
    },
    EmailTemplate.Slug.MEETING_REMINDER_1H: {
        "subject": "Starting in 1 hour: Your Transcendental Meditation session 🌿",
        "body": """Hi {{ user_first_name }}, 🌿

A little reminder that your introductory Transcendental Meditation session begins in 1 hour.

⏰ {{ session_time }}
💻 Online

Join here:
{{ meeting_link }}

Please find a quiet, comfortable space where you can relax and be present for the session. You may also have a notepad and pen close by to jot down anything you’d like to remember.

Take a few moments to settle in before we begin.

See you soon. ✨

Warmly,
Transcendental Meditation Team""",
    },
}


def send_template_email(*, slug: str, to: list[str], context: Mapping[str, object]) -> None:
    """Render an admin-managed email template, using a safe default if it is unavailable."""
    default = DEFAULT_EMAIL_TEMPLATES[slug]
    try:
        email_template = EmailTemplate.objects.get(slug=slug)
        subject_source = email_template.subject
        body_source = email_template.body
    except EmailTemplate.DoesNotExist:
        logger.error("Email template '%s' is missing; sending the built-in fallback.", slug)
        subject_source = default["subject"]
        body_source = default["body"]

    try:
        template_context = Context(dict(context), autoescape=False)
        subject = Template(subject_source).render(template_context).strip()
        body = Template(body_source).render(template_context)
    except TemplateSyntaxError:
        logger.exception("Email template '%s' has invalid Django template syntax; using fallback.", slug)
        template_context = Context(dict(context), autoescape=False)
        subject = Template(default["subject"]).render(template_context).strip()
        body = Template(default["body"]).render(template_context)

    EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    ).send(fail_silently=False)
