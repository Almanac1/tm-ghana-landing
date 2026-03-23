from django import forms

from .models import LeadCapture, Reservation


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
    def __init__(self, *args, **kwargs):
        is_locked = kwargs.pop("is_locked", False)
        super().__init__(*args, **kwargs)
        self.fields["session_date"].choices = Reservation.SessionDate.choices
        self.fields["session_date"].disabled = is_locked

    class Meta:
        model = Reservation
        fields = ["session_date", "session_type"]
        widgets = {
            "session_date": forms.RadioSelect(),
            "session_type": forms.HiddenInput(attrs={"id": "reservation-session-type"}),
        }
