import logging
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import LeadCaptureForm, ReservationForm
from .models import Reservation, Submission


BENEFITS = [
    "Lower stress & anxiety levels",
    "Improve focus & decision making",
    "Sleep better & wakeup energized",
    "Sustain peak mental performance",
]

FAQS = [
    {
        "question": '"Dont you have to believe in TM for it to work?"',
        "answer": "No, belief is not required. TM is a technique based on simple mechanics. Research shows that TM works regardless of belief, expectations, or concentration. It's the practice itself that produces the benefits.",
    },
    {
        "question": '"Is TM a religious or spiritual practice?"',
        "answer": "No, TM is not a religion or spiritual practice. It's a simple, natural technique based on science. People of all faiths and no faith practice TM, and it complements any belief system.",
    },
    {
        "question": '"Meditation is for people who have time?"',
        "answer": "TM only requires 20 minutes, twice a day. Many busy professionals find that TM actually saves time by increasing productivity and reducing stress-related issues.",
    },
    {
        "question": "\"Isn't mediation about clearing the mind?\"",
        "answer": "No. TM is not about clearing the mind or concentrating. It's a natural, effortless technique that allows the mind to settle to a state of deep rest and coherence.",
    },
    {
        "question": '"Do I have to sit cross-legged or chant out loud?"',
        "answer": "No. TM is practiced sitting comfortably in any chair with eyes closed. There's no chanting, no special postures, and no complex techniques to learn.",
    },
]


SUCCESS_STATE_SESSION_KEY = "landing_form_success_state"
LEAD_DETAILS_SESSION_KEY = "landing_lead_details_completed"
logger = logging.getLogger(__name__)


SESSION_DATE_LABELS = {
    Reservation.SessionType.PHYSICAL: {
        Reservation.SessionDate.NOV5: "Wednesday, November 5",
        Reservation.SessionDate.NOV12: "Wednesday, November 12",
        Reservation.SessionDate.NOV19: "Wednesday, November 19",
        Reservation.SessionDate.NOV25: "Wednesday, November 25",
    },
    Reservation.SessionType.ONLINE: {
        Reservation.SessionDate.NOV5: "Saturday, November 5",
        Reservation.SessionDate.NOV12: "Saturday, November 15",
        Reservation.SessionDate.NOV19: "Saturday, November 22",
        Reservation.SessionDate.NOV25: "Saturday, November 29",
    },
}


def _extract_first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else "there"


def _sanitize_measured_height(value: Optional[str]) -> Optional[int]:
    if not value:
        return None

    try:
        height = int(float(value))
    except (TypeError, ValueError):
        return None

    if 200 <= height <= 1200:
        return height
    return None


def _first_form_error(form) -> Optional[str]:
    if not form:
        return None
    if form.non_field_errors():
        return " ".join(form.non_field_errors())
    for _, errors in form.errors.items():
        if errors:
            return errors[0]
    return None


def _send_submission_emails(submission: Submission) -> None:
    from_email = settings.DEFAULT_FROM_EMAIL
    admin_to = [settings.LANDING_ADMIN_EMAIL]
    first_name = _extract_first_name(submission.name)
    session_type = submission.get_session_type_display() if submission.session_type else "Not provided"
    session_date = SESSION_DATE_LABELS.get(submission.session_type, {}).get(
        submission.session_date, submission.get_session_date_display()
    )

    admin_subject = f"New TM landing submission from {submission.name}"
    admin_body = render_to_string(
        "landing/emails/admin_submission_notification.txt",
        {
            "submission": submission,
            "first_name": first_name,
            "session_type": session_type,
            "session_date": session_date,
        },
    )

    visitor_subject = "We received your meditation reservation"
    visitor_body = render_to_string(
        "landing/emails/visitor_reservation_confirmation.txt",
        {
            "submission": submission,
            "first_name": first_name,
            "session_type": session_type,
            "session_date": session_date,
        },
    )

    EmailMultiAlternatives(
        subject=admin_subject,
        body=admin_body,
        from_email=from_email,
        to=admin_to,
    ).send(fail_silently=False)

    EmailMultiAlternatives(
        subject=visitor_subject,
        body=visitor_body,
        from_email=from_email,
        to=[submission.email],
    ).send(fail_silently=False)


@require_http_methods(["GET", "POST"])
def home(request):
    success_state = request.session.pop(SUCCESS_STATE_SESSION_KEY, None)
    lead_success = None
    reservation_success = None
    lead_error_message = None
    reservation_gate_message = None

    if success_state:
        if success_state.get("form_type") == "lead":
            lead_success = success_state
        elif success_state.get("form_type") == "reservation":
            reservation_success = success_state

    lead_form = LeadCaptureForm(prefix="lead")
    lead_details_completed = bool(request.session.get(LEAD_DETAILS_SESSION_KEY))

    # Keep reservation locked by default on fresh visits.
    # Unlock state should only persist while the lead success state is active in this flow.
    if request.method == "GET" and not lead_success and not reservation_success:
        request.session.pop(LEAD_DETAILS_SESSION_KEY, None)
        lead_details_completed = False
    reservation_form = ReservationForm(
        prefix="reservation",
        initial={"session_type": Reservation.SessionType.PHYSICAL},
        is_locked=not lead_details_completed,
    )

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        ui_action = request.POST.get("ui_action")

        if form_type == "lead":
            if ui_action == "edit":
                lead_form = LeadCaptureForm(
                    prefix="lead",
                    initial={
                        "name": request.POST.get("payload_name", ""),
                        "email": request.POST.get("payload_email", ""),
                        "country": request.POST.get("payload_country", "GH"),
                        "phone": request.POST.get("payload_phone", ""),
                    },
                )
                lead_success = None
                request.session[LEAD_DETAILS_SESSION_KEY] = {
                    "name": request.POST.get("payload_name", ""),
                    "email": request.POST.get("payload_email", ""),
                    "country": request.POST.get("payload_country", "GH"),
                    "phone": request.POST.get("payload_phone", ""),
                }
                lead_details_completed = True
            elif ui_action == "reset":
                lead_form = LeadCaptureForm(prefix="lead")
                lead_success = None
                request.session.pop(LEAD_DETAILS_SESSION_KEY, None)
                lead_details_completed = False
            else:
                lead_form = LeadCaptureForm(request.POST, prefix="lead")
                if lead_form.is_valid():
                    lead_form.save()
                    request.session[LEAD_DETAILS_SESSION_KEY] = {
                        "name": lead_form.cleaned_data["name"],
                        "email": lead_form.cleaned_data["email"],
                        "country": lead_form.cleaned_data["country"],
                        "phone": lead_form.cleaned_data["phone"],
                    }
                    lead_details_completed = True
                    request.session[SUCCESS_STATE_SESSION_KEY] = {
                        "form_type": "lead",
                        "first_name": _extract_first_name(lead_form.cleaned_data["name"]),
                        "payload": {
                            "name": lead_form.cleaned_data["name"],
                            "email": lead_form.cleaned_data["email"],
                            "country": lead_form.cleaned_data["country"],
                            "phone": lead_form.cleaned_data["phone"],
                        },
                    }
                    return redirect(f"{reverse('home')}#booking")
                lead_error_message = _first_form_error(lead_form) or "Please correct the highlighted details and try again."
        elif form_type == "reservation":
            if ui_action == "edit":
                reservation_form = ReservationForm(
                    prefix="reservation",
                    initial={
                        "session_type": request.POST.get("payload_session_type", Reservation.SessionType.PHYSICAL),
                        "session_date": request.POST.get("payload_session_date", ""),
                    },
                    is_locked=not lead_details_completed,
                )
                reservation_success = None
            elif ui_action == "reset":
                reservation_form = ReservationForm(
                    prefix="reservation",
                    initial={"session_type": Reservation.SessionType.PHYSICAL},
                    is_locked=not lead_details_completed,
                )
                reservation_success = None
            else:
                if not lead_details_completed:
                    reservation_form = ReservationForm(request.POST, prefix="reservation", is_locked=True)
                    reservation_gate_message = "Complete your details in the form above before reserving a spot."
                else:
                    reservation_form = ReservationForm(request.POST, prefix="reservation", is_locked=False)
                    if reservation_form.is_valid():
                        lead_details = request.session.get(LEAD_DETAILS_SESSION_KEY) or {}
                        lead_name = str(lead_details.get("name", "")).strip()
                        lead_email = str(lead_details.get("email", "")).strip()
                        lead_phone = str(lead_details.get("phone", "")).strip()

                        if not all([lead_name, lead_email, lead_phone]):
                            reservation_gate_message = "Please complete your contact details before final submission."
                            lead_details_completed = False
                            request.session.pop(LEAD_DETAILS_SESSION_KEY, None)
                            reservation_form = ReservationForm(request.POST, prefix="reservation", is_locked=True)
                            return render(
                                request,
                                "landing/home.html",
                                {
                                    "lead_form": lead_form,
                                    "reservation_form": reservation_form,
                                    "lead_success": lead_success,
                                    "reservation_success": reservation_success,
                                    "lead_details_completed": lead_details_completed,
                                    "lead_error_message": lead_error_message,
                                    "reservation_gate_message": reservation_gate_message,
                                    "benefits": BENEFITS,
                                    "faqs": FAQS,
                                },
                            )

                        measured_height = _sanitize_measured_height(request.POST.get("measured_height"))
                        reservation_form.save()
                        submission = Submission.objects.create(
                            name=lead_name,
                            email=lead_email,
                            phone=lead_phone,
                            session_type=reservation_form.cleaned_data.get("session_type", ""),
                            session_date=reservation_form.cleaned_data["session_date"],
                            message=(request.POST.get("message") or "").strip(),
                        )
                        try:
                            _send_submission_emails(submission)
                        except Exception:  # noqa: BLE001 - capture email backend issues without blocking success UI
                            logger.exception("Failed to send submission emails for submission id=%s", submission.id)
                        request.session[SUCCESS_STATE_SESSION_KEY] = {
                            "form_type": "reservation",
                            "payload": {
                                "session_type": reservation_form.cleaned_data["session_type"],
                                "session_date": reservation_form.cleaned_data["session_date"],
                                "measured_height": measured_height,
                            },
                        }
                        return redirect(f"{reverse('home')}#booking")
                    reservation_gate_message = _first_form_error(reservation_form) or "Please choose a reservation date."

    context = {
        "lead_form": lead_form,
        "reservation_form": reservation_form,
        "lead_success": lead_success,
        "reservation_success": reservation_success,
        "lead_details_completed": lead_details_completed,
        "lead_error_message": lead_error_message,
        "reservation_gate_message": reservation_gate_message,
        "benefits": BENEFITS,
        "faqs": FAQS,
    }
    return render(request, "landing/home.html", context)
