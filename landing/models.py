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
        NOV5 = "nov5", "Wednesday, November 5"
        NOV12 = "nov12", "Wednesday, November 12"
        NOV19 = "nov19", "Wednesday, November 19"
        NOV25 = "nov25", "Wednesday, November 25"

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
