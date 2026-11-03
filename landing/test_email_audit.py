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

    def test_missing_templates_fail_visibly_for_all_slugs(self):
        EmailTemplate.objects.all().delete()
        for slug in EmailTemplate.Slug.values:
            with self.assertRaisesMessage(ValueError, "missing"):
                self.render_email(slug)
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_template_syntax_fails_visibly(self):
        from django.template import TemplateSyntaxError
        for slug in EmailTemplate.Slug.values:
            EmailTemplate.objects.filter(slug=slug).update(body="{% broken_tag %}")
            with self.assertRaises(TemplateSyntaxError):
                self.render_email(slug)

    def test_send_failure_propagates(self):
        with patch("landing.emailing.EmailMultiAlternatives.send", side_effect=SMTPException("unavailable")):
            with self.assertRaises(SMTPException):
                self.render_email()

    def test_zero_send_result_raises(self):
        with patch("landing.emailing.EmailMultiAlternatives.send", return_value=0):
            with self.assertRaises(SMTPException):
                self.render_email()

    def test_unknown_template_variables_fail_visibly(self):
        EmailTemplate.objects.filter(slug="registration_complete").update(body="Hello {{ typo_first_name }}")
        with self.assertRaisesMessage(ValueError, "missing variable"):
            self.render_email()
