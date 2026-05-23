from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0008_participant_status"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="parlay",
            name="sportsbook",
        ),
    ]
