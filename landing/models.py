from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class ClassDate(models.Model):
    class SessionType(models.TextChoices):
        ONLINE = "online", "Online Session"

    session_type = models.CharField(max_length=12, choices=SessionType.choices, default=SessionType.ONLINE)
    date = models.DateField()
    time = models.TimeField()
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "date", "time")
        verbose_name = "Class date"
        verbose_name_plural = "Class dates"

    def __str__(self) -> str:
        return f"{self.get_session_type_display()} - {self.display_label}"

    @property
    def value(self) -> str:
        return self.date.isoformat()

    @property
    def display_label(self) -> str:
        return self.date.strftime("%A, %B %-d")

    @property
    def full_display_label(self) -> str:
        return f"{self.date.strftime('%A, %B %-d, %Y')} at {self.time.strftime('%-I:%M %p')}"


class BlogArticleQuerySet(models.QuerySet):
    def public(self):
        return self.filter(is_published=True, publication_date__lte=timezone.now())


class BlogArticle(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=320, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.TextField()
    body = models.TextField()
    card_image = models.ImageField(upload_to="blog_cards/", blank=True)
    image_alt = models.CharField(max_length=255, blank=True)
    is_published = models.BooleanField(default=False)
    publication_date = models.DateTimeField(default=timezone.now)
    carousel_order = models.PositiveIntegerField(default=0)
    include_in_carousel = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BlogArticleQuerySet.as_manager()

    class Meta:
        ordering = ("-publication_date", "-created_at")
        verbose_name = "Blog article"
        verbose_name_plural = "Blog articles"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("blog_detail", kwargs={"slug": self.slug})

    @property
    def card_image_alt(self) -> str:
        return self.image_alt or self.title



class HomePageContent(models.Model):
    hero_headline = models.TextField(default="Think Clearly.\nFeel Balance.\nWork Better.")
    hero_subtitle = models.TextField(
        blank=True,
        default="A simple, effortless technique to reduce stress, sharpen focus, and support better living.",
    )
    cta_button_text = models.CharField(max_length=80, default="Watch Video")
    cta_button_link = models.CharField(max_length=255, blank=True)
    hero_youtube_url = models.URLField(default="https://www.youtube.com/embed/AL_c-sV9zXc?enablejsapi=1")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = "Homepage content"
        verbose_name_plural = "Homepage content"

    def __str__(self) -> str:
        return f"Homepage content updated {self.updated_at:%Y-%m-%d %H:%M}"


class EmailTemplate(models.Model):
    class Slug(models.TextChoices):
        REGISTRATION_COMPLETE = "registration_complete", "Registration completion"
        MEETING_REMINDER_24H = "meeting_reminder_24h", "24-hour meeting reminder"
        MEETING_REMINDER_1H = "meeting_reminder_1h", "1-hour meeting reminder"

    slug = models.SlugField(max_length=64, unique=True, choices=Slug.choices)
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="Django template syntax is supported, for example {{ user_first_name }}.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("slug",)
        verbose_name = "Email template"
        verbose_name_plural = "Email templates"

    def __str__(self) -> str:
        return self.get_slug_display()


class MeetingSettings(models.Model):
    """The single online meeting link shared by all scheduled sessions."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    meeting_link = models.URLField(
        blank=True,
        help_text="This link is included in every registration and reminder email.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Meeting settings"
        verbose_name_plural = "Meeting settings"

    def __str__(self) -> str:
        return "Online meeting link"


class LeadCapture(models.Model):
    class Country(models.TextChoices):
        GHANA = "GH", "Ghana"
        NIGERIA = "NG", "Nigeria"

    name = models.CharField(max_length=150)
    email = models.EmailField()
    country = models.CharField(max_length=2, choices=Country.choices, default=Country.GHANA)
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_country_display()})"


class Reservation(models.Model):
    SessionType = ClassDate.SessionType

    class SessionDate(models.TextChoices):
        JUL1_2026 = "2026-07-01", "Wednesday, July 1, 2026"
        JUL8_2026 = "2026-07-08", "Wednesday, July 8, 2026"
        JUL15_2026 = "2026-07-15", "Wednesday, July 15, 2026"
        JUL22_2026 = "2026-07-22", "Wednesday, July 22, 2026"
        JUL29_2026 = "2026-07-29", "Wednesday, July 29, 2026"

    session_date = models.CharField(max_length=10)
    session_type = models.CharField(max_length=12, choices=SessionType.choices, default=SessionType.ONLINE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.session_date} - {self.get_session_type_display()}"


class Submission(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    session_type = models.CharField(
        max_length=12,
        choices=Reservation.SessionType.choices,
        default=Reservation.SessionType.ONLINE,
        blank=True,
    )
    session_date = models.CharField(max_length=10)
    message = models.TextField(blank=True)
    reminder_sent = models.BooleanField(default=False)
    reminder_1h_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} - {self.session_date}"
