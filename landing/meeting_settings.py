from .models import MeetingSettings


def get_meeting_link() -> str:
    """Return the shared meeting URL without creating configuration during email delivery."""
    return MeetingSettings.objects.filter(pk=1).values_list("meeting_link", flat=True).first() or ""
