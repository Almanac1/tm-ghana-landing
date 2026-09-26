from django.db import migrations


EMAIL_TEMPLATES = {
    "registration_complete": {
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
    "meeting_reminder_24h": {
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
    "meeting_reminder_1h": {
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


def seed_email_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("landing", "EmailTemplate")
    for slug, defaults in EMAIL_TEMPLATES.items():
        EmailTemplate.objects.get_or_create(slug=slug, defaults=defaults)


def remove_seeded_email_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("landing", "EmailTemplate")
    EmailTemplate.objects.filter(slug__in=EMAIL_TEMPLATES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("landing", "0010_emailtemplate"),
    ]

    operations = [
        migrations.RunPython(seed_email_templates, remove_seeded_email_templates),
    ]
