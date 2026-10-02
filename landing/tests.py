from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.core import mail
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import BlogArticle, ClassDate, EmailTemplate, MeetingSettings, Reservation, Submission


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


class BlogAuthorTests(TestCase):
    def setUp(self):
        self.article = BlogArticle.objects.create(
            title="A quiet moment", excerpt="An introduction.", body="Article content.",
            author="Ada Okafor", is_published=True,
            publication_date=timezone.now() - timedelta(days=1),
        )

    def test_author_names_on_all_public_pages(self):
        for url in (reverse("home"), reverse("blog_list"), self.article.get_absolute_url()):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "By Ada Okafor")

    def test_unassigned_articles_remain_public_without_empty_byline(self):
        self.article.author = ""
        self.article.save()
        for url in (reverse("home"), reverse("blog_list"), self.article.get_absolute_url()):
            response = self.client.get(url)
            self.assertContains(response, self.article.title)
            self.assertNotContains(response, 'class="blog-card-author"')
            self.assertNotContains(response, 'class="blog-detail-meta">By ')
        self.assertContains(response, self.article.publication_date.strftime("%B %-d, %Y"))

    def test_public_pages_fetch_authors_without_extra_queries(self):
        BlogArticle.objects.create(
            title="Another moment", author="Another Writer", is_published=True,
            excerpt="Introduction", body="Content",
        )
        with self.assertNumQueries(1):
            self.assertEqual(len([article.author for article in BlogArticle.objects.public()]), 2)
        with self.assertNumQueries(1):
            self.client.get(reverse("blog_list"))
        with self.assertNumQueries(1):
            self.client.get(self.article.get_absolute_url())

    def test_admin_can_type_and_save_author(self):
        admin_user = get_user_model().objects.create_superuser(
            username="editor", email="editor@example.com", password="test-password"
        )
        self.client.force_login(admin_user)
        response = self.client.get(reverse("admin:landing_blogarticle_add"))
        self.assertEqual(response.context["adminform"].form.fields["author"].widget.input_type, "text")
        url = reverse("admin:landing_blogarticle_change", args=[self.article.pk])
        response = self.client.post(url, {
            "title": self.article.title, "slug": self.article.slug,
            "excerpt": self.article.excerpt, "body": self.article.body,
            "author": "Independent Writer", "publication_date_0": "2026-10-02",
            "publication_date_1": "12:00:00", "carousel_order": "0",
        })
        self.assertEqual(response.status_code, 302)
        self.article.refresh_from_db()
        self.assertEqual(self.article.author, "Independent Writer")
        self.assertContains(self.client.get(reverse("admin:landing_blogarticle_changelist")), "Independent Writer")


class BlogCarouselTests(TestCase):
    def create_article(self, **overrides):
        defaults = {
            "title": "A calmer day",
            "excerpt": "A short introduction.",
            "body": "Article content.",
            "is_published": True,
            "publication_date": timezone.now() - timedelta(days=1),
            "include_in_carousel": True,
            "carousel_order": 0,
        }
        defaults.update(overrides)
        return BlogArticle.objects.create(**defaults)

    def test_homepage_carousel_uses_published_articles_in_admin_order(self):
        second = self.create_article(
            title="Second article",
            slug="second-article",
            carousel_order=2,
        )
        first = self.create_article(
            title="First article",
            slug="first-article",
            carousel_order=1,
            card_image="blog_cards/first-card.jpg",
            image_alt="A peaceful sunrise",
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(list(response.context["carousel_articles"]), [first, second])
        self.assertContains(response, first.get_absolute_url())
        self.assertContains(response, second.get_absolute_url())
        self.assertContains(response, "/media/blog_cards/first-card.jpg")
        self.assertContains(response, 'alt="A peaceful sunrise"')

    def test_drafts_future_and_non_carousel_articles_are_not_public(self):
        draft = self.create_article(title="Draft", slug="draft", is_published=False)
        future = self.create_article(
            title="Future",
            slug="future",
            publication_date=timezone.now() + timedelta(days=1),
        )
        excluded = self.create_article(
            title="Excluded",
            slug="excluded",
            include_in_carousel=False,
        )

        response = self.client.get(reverse("home"))
        self.assertNotContains(response, draft.title)
        self.assertNotContains(response, future.title)
        self.assertNotContains(response, excluded.title)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(future.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(excluded.get_absolute_url()).status_code, 200)

    def test_blog_section_shows_an_empty_state_when_no_articles_are_eligible_for_carousel(self):
        self.create_article(include_in_carousel=False)

        response = self.client.get(reverse("home"))

        self.assertContains(response, 'id="blogs"')
        self.assertContains(response, "New articles are on the way")


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
        )
        self.meeting_settings, _ = MeetingSettings.objects.update_or_create(
            pk=1,
            defaults={"meeting_link": "https://meet.example.com/tm-session"},
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
        template = EmailTemplate.objects.get(slug=EmailTemplate.Slug.REGISTRATION_COMPLETE)
        template.subject = "Confirmation for {{ user_first_name }}"
        template.body = "Hello {{ user_first_name }} — {{ session_time }}"
        template.save()
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
        self.assertEqual(mail.outbox[1].subject, "Confirmation for Ada")
        self.assertIn("Session mode: Online Session", mail.outbox[0].body)
        self.assertIn("Hello Ada", mail.outbox[1].body)
        self.assertIn("6:00 PM", mail.outbox[1].body)
        self.assertNotIn(self.meeting_settings.meeting_link, mail.outbox[1].body)
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
        self.meeting_settings.meeting_link = "https://meet.example.com/updated-session"
        self.meeting_settings.save()
        self.class_date.save()
        submission = Submission.objects.create(
            name="Ada Lovelace",
            email="ada@example.com",
            phone="8035550102",
            session_type=Reservation.SessionType.ONLINE,
            session_date=session_date.isoformat(),
        )
        template = EmailTemplate.objects.get(slug=EmailTemplate.Slug.MEETING_REMINDER_24H)
        template.subject = "24h reminder for {{ user_first_name }}"
        template.body = "24h {{ user_first_name }} {{ session_date }} {{ session_time }} {{ meeting_link }}"
        template.save()

        with patch("landing.management.commands.send_session_reminders.timezone.now", return_value=now):
            call_command("send_session_reminders")
            call_command("send_session_reminders")

        submission.refresh_from_db()
        self.assertTrue(submission.reminder_sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            "24h reminder for Ada",
        )
        self.assertIn("24h Ada", mail.outbox[0].body)
        self.assertIn("Wednesday, January 2, 2030", mail.outbox[0].body)
        self.assertIn("7:00 PM", mail.outbox[0].body)
        self.assertIn("https://meet.example.com/updated-session", mail.outbox[0].body)

    def test_one_hour_reminder_command_sends_once_with_current_meeting_link(self):
        now = timezone.make_aware(datetime(2030, 1, 1, 18, 0))
        session_time = time(19, 0)
        self.class_date.date = now.date()
        self.class_date.time = session_time
        self.meeting_settings.meeting_link = "https://meet.example.com/final-reminder"
        self.meeting_settings.save()
        self.class_date.save()
        submission = Submission.objects.create(
            name="Grace Hopper",
            email="grace@example.com",
            phone="8035550103",
            session_type=Reservation.SessionType.ONLINE,
            session_date=now.date().isoformat(),
        )
        template = EmailTemplate.objects.get(slug=EmailTemplate.Slug.MEETING_REMINDER_1H)
        template.subject = "1h reminder for {{ user_first_name }}"
        template.body = "1h {{ user_first_name }} {{ session_time }} {{ meeting_link }}"
        template.save()

        with patch("landing.management.commands.send_session_1h_reminders.timezone.now", return_value=now):
            call_command("send_session_1h_reminders")
            call_command("send_session_1h_reminders")

        submission.refresh_from_db()
        self.assertTrue(submission.reminder_1h_sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            "1h reminder for Grace",
        )
        self.assertIn("1h Grace", mail.outbox[0].body)
        self.assertIn("7:00 PM", mail.outbox[0].body)
        self.assertIn("https://meet.example.com/final-reminder", mail.outbox[0].body)
