from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import ClassDate, LeadCapture, Reservation


FALLBACK_SESSION_COUNT = 5


def _date_option(session_date):
    return {
        "value": session_date.isoformat(),
        "label": session_date.strftime("%A, %B %-d"),
        "full_label": session_date.strftime("%A, %B %-d, %Y"),
    }


def _next_wednesday_options(count=FALLBACK_SESSION_COUNT):
    today = timezone.localdate()
    days_until_wednesday = (2 - today.weekday()) % 7
    first_wednesday = today + timedelta(days=days_until_wednesday)
    return [_date_option(first_wednesday + timedelta(weeks=index)) for index in range(count)]


def get_active_class_date_options():
    """Return active, upcoming Wednesday dates for online introductory sessions."""
    today = timezone.localdate()
    class_dates = ClassDate.objects.filter(
        is_active=True,
        session_type=Reservation.SessionType.ONLINE,
        date__gte=today,
    ).order_by("display_order", "date", "time")

    options = [
        {
            "value": class_date.value,
            "label": class_date.display_label,
            "full_label": class_date.full_display_label,
        }
        for class_date in class_dates
        if class_date.date.weekday() == 2
    ]
    return options or _next_wednesday_options()


class LeadCaptureForm(forms.ModelForm):
    class Meta:
        model = LeadCapture
        fields = ["name", "email", "country", "phone"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "id": "lead-name",
                    "placeholder": "Enter your name",
                    "required": True,
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "id": "lead-email",
                    "placeholder": "Enter your email address",
                    "required": True,
                }
            ),
            "country": forms.Select(
                attrs={
                    "id": "lead-country",
                    "aria-label": "Select your country",
                    "required": True,
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "id": "lead-phone",
                    "placeholder": "Phone number",
                    "inputmode": "numeric",
                    "autocomplete": "tel-national",
                    "aria-label": "Phone number",
                    "required": True,
                }
            ),
        }


class ReservationForm(forms.ModelForm):
    session_date = forms.ChoiceField(widget=forms.RadioSelect())

    def __init__(self, *args, **kwargs):
        is_locked = kwargs.pop("is_locked", False)
        class_date_options = kwargs.pop("class_date_options", None) or get_active_class_date_options()
        super().__init__(*args, **kwargs)
        self.class_date_options = class_date_options
        self.fields["session_date"].choices = [
            (option["value"], option["full_label"]) for option in class_date_options
        ]
        self.fields["session_date"].disabled = is_locked

    def save(self, commit=True):
        reservation = super().save(commit=False)
        reservation.session_type = Reservation.SessionType.ONLINE
        if commit:
            reservation.save()
        return reservation

    class Meta:
        model = Reservation
        fields = ["session_date"]
