from django.db import migrations


def copy_existing_meeting_link(apps, schema_editor):
    ClassDate = apps.get_model("landing", "ClassDate")
    MeetingSettings = apps.get_model("landing", "MeetingSettings")
    existing_link = (
        ClassDate.objects.exclude(meeting_link="")
        .order_by("display_order", "date", "time", "id")
        .values_list("meeting_link", flat=True)
        .first()
        or ""
    )
    MeetingSettings.objects.get_or_create(pk=1, defaults={"meeting_link": existing_link})


def remove_meeting_settings(apps, schema_editor):
    apps.get_model("landing", "MeetingSettings").objects.filter(pk=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("landing", "0012_meetingsettings_remove_classdate_meeting_link"),
    ]

    operations = [
        migrations.RunPython(copy_existing_meeting_link, remove_meeting_settings),
    ]
