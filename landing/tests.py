from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Reservation, Submission


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
            "reservation-session_date": Reservation.SessionDate.NOV12,
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
        self.assertEqual(submission.session_date, Reservation.SessionDate.NOV12)

        self.assertEqual(len(mail.outbox), 2)

        admin_email = mail.outbox[0]
        visitor_email = mail.outbox[1]

        self.assertEqual(admin_email.to, ["instructor@test.local"])
        self.assertIn("Full name: Ada Lovelace", admin_email.body)
        self.assertIn("First name: Ada", admin_email.body)
        self.assertIn("Email: ada@example.com", admin_email.body)
        self.assertIn("Phone: 2335550102", admin_email.body)
        self.assertIn("Session mode: Physical Session", admin_email.body)
        self.assertIn("Reservation date: Wednesday, November 12", admin_email.body)

        self.assertEqual(visitor_email.to, ["ada@example.com"])
        self.assertIn("Hi Ada,", visitor_email.body)
        self.assertIn("Selected session: Physical Session", visitor_email.body)
        self.assertIn("Selected date: Wednesday, November 12", visitor_email.body)

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
            "reservation-session_date": Reservation.SessionDate.NOV19,
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
            "reservation-session_date": Reservation.SessionDate.NOV19,
            "measured_height": "480",
        }
        response = self.client.post(reverse("home"), data=reservation_payload)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 2)
        visitor_email = mail.outbox[1]
        self.assertIn("Selected session: Online Session", visitor_email.body)
        self.assertIn("Selected date: Saturday, November 22", visitor_email.body)
