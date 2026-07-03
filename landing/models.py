from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class ClassDate(models.Model):
    class SessionType(models.TextChoices):
        PHYSICAL = "physical", "Physical Session"
        ONLINE = "online", "Online Session"

    session_type = models.CharField(max_length=12, choices=SessionType.choices)
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


class BlogArticle(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.TextField()
    body = models.TextField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
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
        JUL4_2026 = "2026-07-04", "Saturday, July 4, 2026"
        JUL8_2026 = "2026-07-08", "Wednesday, July 8, 2026"
        JUL11_2026 = "2026-07-11", "Saturday, July 11, 2026"
        JUL15_2026 = "2026-07-15", "Wednesday, July 15, 2026"
        JUL18_2026 = "2026-07-18", "Saturday, July 18, 2026"
        JUL22_2026 = "2026-07-22", "Wednesday, July 22, 2026"
        JUL25_2026 = "2026-07-25", "Saturday, July 25, 2026"
        JUL29_2026 = "2026-07-29", "Wednesday, July 29, 2026"

    session_date = models.CharField(max_length=10)
    session_type = models.CharField(max_length=12, choices=SessionType.choices, default=SessionType.PHYSICAL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.session_date} - {self.get_session_type_display()}"


class Submission(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    session_type = models.CharField(max_length=12, choices=Reservation.SessionType.choices, blank=True)
    session_date = models.CharField(max_length=10)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} - {self.session_date}"
