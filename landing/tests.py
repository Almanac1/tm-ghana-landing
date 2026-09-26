from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import BlogArticle, ClassDate, Reservation, Submission


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
class OnlineReservationFlowTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        days_until_wednesday = (2 - today.weekday()) % 7
        self.session_date = today + timedelta(days=days_until_wednesday)
        self.class_date = ClassDate.objects.create(
            session_type=Reservation.SessionType.ONLINE,
            date=self.session_date,
            time=time(18, 0),
            meeting_link="https://meet.example.com/tm-session",
        )

    def complete_lead_form(self, name="Ada Lovelace", email="ada@example.com"):
        response = self.client.post(
            reverse("home"),
            data={
                "form_type": "lead",
                "lead-name": name,
                "lead-email": email,
                "lead-country": "NG",
                "lead-phone": "8035550102",
            },
        )
        self.assertEqual(response.status_code, 302)

    def reserve(self, **overrides):
        payload = {
            "form_type": "reservation",
            "reservation-session_date": self.session_date.isoformat(),
            "measured_height": "450",
        }
        payload.update(overrides)
        return self.client.post(reverse("home"), data=payload)

    def test_booking_form_only_offers_upcoming_online_wednesdays(self):
        ClassDate.objects.create(
            session_type="physical",
            date=self.session_date + timedelta(weeks=1),
            time=time(18, 0),
        )
        ClassDate.objects.create(
            session_type=Reservation.SessionType.ONLINE,
            date=self.session_date + timedelta(days=1),
            time=time(18, 0),
        )
        ClassDate.objects.create(
            session_type=Reservation.SessionType.ONLINE,
            date=self.session_date - timedelta(weeks=2),
            time=time(18, 0),
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(len(response.context["reservation_date_options"]), 5)
        self.assertContains(response, "Reserve Your Spot")
        self.assertContains(response, "Select a Wednesday to join our online introductory session")
        self.assertContains(response, self.session_date.isoformat())
        self.assertContains(response, (self.session_date + timedelta(weeks=1)).isoformat())
        self.assertNotContains(response, (self.session_date + timedelta(days=1)).isoformat())
        self.assertNotContains(response, (self.session_date - timedelta(weeks=2)).isoformat())
        self.assertNotContains(response, "Physical Session")
        self.assertNotContains(response, "reservation_session_mode_ui")
        self.assertNotContains(response, "reservation-session_type")

    def test_fallback_dates_are_always_upcoming_wednesdays(self):
        self.class_date.delete()

        response = self.client.get(reverse("home"))
        options = response.context["reservation_date_options"]

        self.assertEqual(len(options), 5)
        for option in options:
            session_date = date.fromisoformat(option["value"])
            self.assertGreaterEqual(session_date, timezone.localdate())
            self.assertEqual(session_date.weekday(), 2)

    def test_reservation_without_session_type_is_saved_as_online_and_sends_emails(self):
        self.complete_lead_form()

        response = self.reserve()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('home')}#booking")
        reservation = Reservation.objects.get()
        submission = Submission.objects.get()
        self.assertEqual(reservation.session_type, Reservation.SessionType.ONLINE)
        self.assertEqual(submission.session_type, Reservation.SessionType.ONLINE)
        self.assertEqual(submission.session_date, self.session_date.isoformat())
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].subject, "Your Transcendental Meditation Session Reservation")
        self.assertIn("Session mode: Online Session", mail.outbox[0].body)
        self.assertIn("🌿 Format: Online", mail.outbox[1].body)
        self.assertIn("📅 Date: " + self.session_date.strftime("%A, %B %-d, %Y"), mail.outbox[1].body)
        self.assertIn("⏰ Time: 6:00 PM", mail.outbox[1].body)
        self.assertIn(self.class_date.meeting_link, mail.outbox[1].body)
        self.assertIn(self.class_date.full_display_label, mail.outbox[0].body)

    def test_posted_physical_session_type_is_ignored(self):
        self.complete_lead_form()

        response = self.reserve(**{"reservation-session_type": "physical"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reservation.objects.get().session_type, Reservation.SessionType.ONLINE)
        self.assertEqual(Submission.objects.get().session_type, Reservation.SessionType.ONLINE)

    def test_unavailable_date_is_rejected(self):
        self.complete_lead_form()

        response = self.reserve(
            **{"reservation-session_date": (self.session_date + timedelta(days=1)).isoformat()}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(Submission.objects.exists())

    def test_submission_still_succeeds_when_email_sending_fails(self):
        self.complete_lead_form(name="Grace Hopper", email="grace@example.com")

        with patch("landing.views._send_submission_emails", side_effect=RuntimeError("mail down")):
            response = self.reserve()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('home')}#booking")
        self.assertEqual(Submission.objects.count(), 1)

    def test_reminder_command_sends_one_dynamic_reminder_24_hours_before_session(self):
        now = timezone.make_aware(datetime(2030, 1, 1, 19, 0))
        session_time = time(19, 0)
        session_date = (now + timedelta(hours=24)).date()
        self.class_date.date = session_date
        self.class_date.time = session_time
        self.class_date.meeting_link = "https://meet.example.com/updated-session"
        self.class_date.save()
        submission = Submission.objects.create(
            name="Ada Lovelace",
            email="ada@example.com",
            phone="8035550102",
            session_type=Reservation.SessionType.ONLINE,
            session_date=session_date.isoformat(),
        )

        with patch("landing.management.commands.send_session_reminders.timezone.now", return_value=now):
            call_command("send_session_reminders")
            call_command("send_session_reminders")

        submission.refresh_from_db()
        self.assertTrue(submission.reminder_sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            "Reminder: Your Transcendental Meditation session is tomorrow 🌿",
        )
        self.assertIn("Hi Ada, 🌿", mail.outbox[0].body)
        self.assertIn("📅 Wednesday, January 2, 2030", mail.outbox[0].body)
        self.assertIn("⏰ 7:00 PM", mail.outbox[0].body)
        self.assertIn("https://meet.example.com/updated-session", mail.outbox[0].body)

    def test_one_hour_reminder_command_sends_once_with_current_meeting_link(self):
        now = timezone.make_aware(datetime(2030, 1, 1, 18, 0))
        session_time = time(19, 0)
        self.class_date.date = now.date()
        self.class_date.time = session_time
        self.class_date.meeting_link = "https://meet.example.com/final-reminder"
        self.class_date.save()
        submission = Submission.objects.create(
            name="Grace Hopper",
            email="grace@example.com",
            phone="8035550103",
            session_type=Reservation.SessionType.ONLINE,
            session_date=now.date().isoformat(),
        )

        with patch("landing.management.commands.send_session_1h_reminders.timezone.now", return_value=now):
            call_command("send_session_1h_reminders")
            call_command("send_session_1h_reminders")

        submission.refresh_from_db()
        self.assertTrue(submission.reminder_1h_sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            "Starting in 1 hour: Your Transcendental Meditation session 🌿",
        )
        self.assertIn("Hi Grace, 🌿", mail.outbox[0].body)
        self.assertIn("⏰ 7:00 PM", mail.outbox[0].body)
        self.assertIn("https://meet.example.com/final-reminder", mail.outbox[0].body)
