from django import forms
from django.utils import timezone

from .models import ClassDate, LeadCapture, Reservation


def get_active_class_date_options():
    """Return active, upcoming Wednesday dates for online introductory sessions."""
    today = timezone.localdate()
    class_dates = ClassDate.objects.filter(
        is_active=True,
        session_type=Reservation.SessionType.ONLINE,
        date__gte=today,
    ).order_by("display_order", "date", "time")

    options_by_date = {}
    for class_date in class_dates:
        if class_date.date.weekday() != 2:
            continue
        options_by_date[class_date.value] = {
            "value": class_date.value,
            "label": class_date.display_label,
            "full_label": class_date.full_display_label,
        }

    return sorted(options_by_date.values(), key=lambda option: option["value"])


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
        class_date_options = kwargs.pop("class_date_options", None)
        if class_date_options is None:
            class_date_options = get_active_class_date_options()
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
