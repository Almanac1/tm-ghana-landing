from unittest.mock import patch

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import BlogArticle, Reservation, Submission


class PrivacyPolicyPageTests(TestCase):
    def test_privacy_policy_page_renders_expected_content(self):
        response = self.client.get(reverse("privacy_policy"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "landing/privacy_policy.html")
        self.assertTemplateUsed(response, "landing/base.html")
        self.assertContains(response, "<h1>Privacy Policy</h1>", html=True)
        self.assertContains(response, "Last updated:</strong> July 23, 2026")

    def test_global_footer_links_to_named_privacy_policy_url(self):
        for route_name in ("home", "blog_list", "privacy_policy"):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    f'<a href="{reverse("privacy_policy")}">Privacy Policy</a>',
                    html=True,
                )

    def test_landing_form_contains_linked_privacy_notice(self):
        response = self.client.get(reverse("home"))

        self.assertContains(
            response,
            "TM Nigeria may use the information you provide to process your registration",
        )
        self.assertContains(
            response,
            f'<a href="{reverse("privacy_policy")}">Privacy Policy</a>',
            html=True,
            count=2,
        )

    def test_existing_public_pages_continue_to_load(self):
        article = BlogArticle.objects.create(
            title="A calmer day",
            excerpt="A short introduction.",
            body="Article content.",
            is_published=True,
        )

        for url in (reverse("home"), reverse("blog_list"), article.get_absolute_url()):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@test.local",
    LANDING_ADMIN_EMAIL="instructor@test.local",
)
class ReservationEmailFlowTests(TestCase):
    def test_successful_reservation_sends_visitor_and_admin_emails(self):
        lead_payload = {
            "form_type": "lead",
            "lead-name": "Ada Lovelace",
            "lead-email": "ada@example.com",
            "lead-country": "GH",
            "lead-phone": "2335550102",
        }
        lead_response = self.client.post(reverse("home"), data=lead_payload)
        self.assertEqual(lead_response.status_code, 302)

        reservation_payload = {
            "form_type": "reservation",
            "reservation-session_type": Reservation.SessionType.PHYSICAL,
            "reservation-session_date": Reservation.SessionDate.JUL18_2026,
            "measured_height": "450",
        }
        reservation_response = self.client.post(reverse("home"), data=reservation_payload)
        self.assertEqual(reservation_response.status_code, 302)
        self.assertEqual(reservation_response.url, f"{reverse('home')}#booking")

        self.assertEqual(Submission.objects.count(), 1)
        submission = Submission.objects.get()
        self.assertEqual(submission.name, "Ada Lovelace")
        self.assertEqual(submission.email, "ada@example.com")
        self.assertEqual(submission.phone, "2335550102")
        self.assertEqual(submission.session_type, Reservation.SessionType.PHYSICAL)
        self.assertEqual(submission.session_date, Reservation.SessionDate.JUL18_2026)

        self.assertEqual(len(mail.outbox), 2)

        admin_email = mail.outbox[0]
        visitor_email = mail.outbox[1]

        self.assertEqual(admin_email.to, ["instructor@test.local"])
        self.assertEqual(admin_email.reply_to, ["ada@example.com"])
        self.assertEqual(admin_email.subject, "New registration entry from Ada Lovelace")
        self.assertIn("A new registration entry has been made.", admin_email.body)
        self.assertIn("Full name: Ada Lovelace", admin_email.body)
        self.assertIn("First name: Ada", admin_email.body)
        self.assertIn("Email: ada@example.com", admin_email.body)
        self.assertIn("Phone: 2335550102", admin_email.body)
        self.assertIn("Session mode: Physical Session", admin_email.body)
        self.assertIn("Reservation date: Saturday, July 18, 2026", admin_email.body)

        self.assertEqual(visitor_email.to, ["ada@example.com"])
        self.assertEqual(visitor_email.subject, "We received your meditation reservation")
        self.assertIn("Hi Ada,", visitor_email.body)
        self.assertIn("Your registration has been received.", visitor_email.body)
        self.assertIn("Selected session: Physical Session", visitor_email.body)
        self.assertIn("Selected date: Saturday, July 18, 2026", visitor_email.body)

    def test_submission_still_succeeds_when_email_sending_fails(self):
        lead_payload = {
            "form_type": "lead",
            "lead-name": "Grace Hopper",
            "lead-email": "grace@example.com",
            "lead-country": "GH",
            "lead-phone": "2335550103",
        }
        self.client.post(reverse("home"), data=lead_payload)

        reservation_payload = {
            "form_type": "reservation",
            "reservation-session_type": Reservation.SessionType.ONLINE,
            "reservation-session_date": Reservation.SessionDate.JUL15_2026,
            "measured_height": "500",
        }

        with patch("landing.views._send_submission_emails", side_effect=RuntimeError("mail down")):
            response = self.client.post(reverse("home"), data=reservation_payload)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('home')}#booking")
        self.assertEqual(Submission.objects.count(), 1)

    def test_online_reservation_email_uses_online_date_labels(self):
        lead_payload = {
            "form_type": "lead",
            "lead-name": "Linus Torvalds",
            "lead-email": "linus@example.com",
            "lead-country": "GH",
            "lead-phone": "2335550104",
        }
        self.client.post(reverse("home"), data=lead_payload)

        reservation_payload = {
            "form_type": "reservation",
            "reservation-session_type": Reservation.SessionType.ONLINE,
            "reservation-session_date": Reservation.SessionDate.JUL15_2026,
            "measured_height": "480",
        }
        response = self.client.post(reverse("home"), data=reservation_payload)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 2)
        visitor_email = mail.outbox[1]
        self.assertIn("Selected session: Online Session", visitor_email.body)
        self.assertIn("Selected date: Wednesday, July 15, 2026", visitor_email.body)

    def test_all_online_dates_can_be_submitted(self):
        online_dates = [
            Reservation.SessionDate.JUL1_2026,
            Reservation.SessionDate.JUL8_2026,
            Reservation.SessionDate.JUL15_2026,
            Reservation.SessionDate.JUL22_2026,
            Reservation.SessionDate.JUL29_2026,
        ]

        for index, session_date in enumerate(online_dates, start=1):
            with self.subTest(session_date=session_date):
                client = Client()
                lead_payload = {
                    "form_type": "lead",
                    "lead-name": f"Online Guest {index}",
                    "lead-email": f"online{index}@example.com",
                    "lead-country": "GH",
                    "lead-phone": f"23355501{index:02d}",
                }
                lead_response = client.post(reverse("home"), data=lead_payload)
                self.assertEqual(lead_response.status_code, 302)

                reservation_payload = {
                    "form_type": "reservation",
                    "reservation-session_type": Reservation.SessionType.ONLINE,
                    "reservation-session_date": session_date,
                    "measured_height": "480",
                }
                response = client.post(reverse("home"), data=reservation_payload)

                self.assertEqual(response.status_code, 302)
                self.assertTrue(
                    Submission.objects.filter(
                        email=f"online{index}@example.com",
                        session_type=Reservation.SessionType.ONLINE,
                        session_date=session_date,
                    ).exists()
                )
