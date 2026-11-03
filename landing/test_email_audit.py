"""Template regressions from the original audit. Queue workflow tests are in test_email_queue."""
from smtplib import SMTPException
from unittest.mock import patch
from django.core import mail
from django.test import TestCase, override_settings
from .emailing import send_template_email
from .models import EmailTemplate


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="sender@example.com")
class EmailTemplateTests(TestCase):
    def render_email(self, slug=EmailTemplate.Slug.REGISTRATION_COMPLETE):
        send_template_email(slug=slug, to=["ada@example.com"], context={
            "user_first_name": "Ada", "session_date": "Wednesday, January 2, 2030",
            "session_time": "6:00 PM", "meeting_link": "https://example.com/meeting",
        })

    def test_missing_templates_fall_back_for_all_slugs(self):
        EmailTemplate.objects.all().delete()
        with self.assertLogs("landing.emailing", level="ERROR"):
            for slug in EmailTemplate.Slug.values:
                self.render_email(slug)
        self.assertEqual(len(mail.outbox), 3)
        self.assertTrue(all("Ada" in message.body for message in mail.outbox))

    def test_invalid_template_syntax_falls_back(self):
        for slug in EmailTemplate.Slug.values:
            EmailTemplate.objects.filter(slug=slug).update(body="{% broken_tag %}")
            with self.assertLogs("landing.emailing", level="ERROR"):
                self.render_email(slug)
        self.assertTrue(all("{%" not in message.body for message in mail.outbox))

    def test_send_failure_propagates(self):
        with patch("landing.emailing.EmailMultiAlternatives.send", side_effect=SMTPException("unavailable")):
            with self.assertRaises(SMTPException):
                self.render_email()

    def test_zero_send_result_raises(self):
        with patch("landing.emailing.EmailMultiAlternatives.send", return_value=0):
            with self.assertRaises(SMTPException):
                self.render_email()

    def test_unknown_template_variables_trigger_fallback(self):
        EmailTemplate.objects.filter(slug="registration_complete").update(body="Hello {{ typo_first_name }}")
        with self.assertLogs("landing.emailing", level="ERROR"):
            self.render_email()
        self.assertIn("Ada", mail.outbox[0].body)
