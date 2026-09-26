from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("landing", "0013_copy_classdate_meeting_link_to_settings"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="classdate",
            name="meeting_link",
        ),
    ]
