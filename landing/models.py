from django.db import models


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
    class SessionType(models.TextChoices):
        PHYSICAL = "physical", "Physical Session"
        ONLINE = "online", "Online Session"

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

    session_date = models.CharField(max_length=10, choices=SessionDate.choices)
    session_type = models.CharField(max_length=12, choices=SessionType.choices, default=SessionType.PHYSICAL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.get_session_date_display()} - {self.get_session_type_display()}"


class Submission(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    session_type = models.CharField(max_length=12, choices=Reservation.SessionType.choices, blank=True)
    session_date = models.CharField(max_length=10, choices=Reservation.SessionDate.choices)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} - {self.get_session_date_display()}"
