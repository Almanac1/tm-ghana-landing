from django import forms

from .models import ClassDate, LeadCapture, Reservation


FALLBACK_CLASS_DATES = {
    Reservation.SessionType.PHYSICAL: [
        {"value": "2026-07-04", "label": "Saturday, July 4", "full_label": "Saturday, July 4, 2026"},
        {"value": "2026-07-11", "label": "Saturday, July 11", "full_label": "Saturday, July 11, 2026"},
        {"value": "2026-07-18", "label": "Saturday, July 18", "full_label": "Saturday, July 18, 2026"},
        {"value": "2026-07-25", "label": "Saturday, July 25", "full_label": "Saturday, July 25, 2026"},
    ],
    Reservation.SessionType.ONLINE: [
        {"value": "2026-07-01", "label": "Wednesday, July 1", "full_label": "Wednesday, July 1, 2026"},
        {"value": "2026-07-08", "label": "Wednesday, July 8", "full_label": "Wednesday, July 8, 2026"},
        {"value": "2026-07-15", "label": "Wednesday, July 15", "full_label": "Wednesday, July 15, 2026"},
        {"value": "2026-07-22", "label": "Wednesday, July 22", "full_label": "Wednesday, July 22, 2026"},
        {"value": "2026-07-29", "label": "Wednesday, July 29", "full_label": "Wednesday, July 29, 2026"},
    ],
}


def get_active_class_date_options():
    options = {Reservation.SessionType.PHYSICAL: [], Reservation.SessionType.ONLINE: []}
    class_dates = ClassDate.objects.filter(is_active=True).order_by("display_order", "date", "time")

    for class_date in class_dates:
        options[class_date.session_type].append(
            {
                "value": class_date.value,
                "label": class_date.display_label,
                "full_label": class_date.full_display_label,
            }
        )

    if not options[Reservation.SessionType.PHYSICAL] and not options[Reservation.SessionType.ONLINE]:
        return FALLBACK_CLASS_DATES
    return options


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
        class_date_options = kwargs.pop("class_date_options", None) or get_active_class_date_options()
        super().__init__(*args, **kwargs)
        self.class_date_options = class_date_options
        self.fields["session_date"].choices = [
            (option["value"], option["full_label"])
            for mode_options in class_date_options.values()
            for option in mode_options
        ]
        self.fields["session_date"].disabled = is_locked

    class Meta:
        model = Reservation
        fields = ["session_date", "session_type"]
        widgets = {
            "session_date": forms.RadioSelect(),
            "session_type": forms.HiddenInput(attrs={"id": "reservation-session-type"}),
        }
