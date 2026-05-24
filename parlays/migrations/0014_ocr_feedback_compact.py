from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0013_ocr_scan_feedback"),
    ]

    operations = [
        migrations.AddField(
            model_name="ocrscanfeedback",
            name="predicted_leg_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="ocrscanfeedback",
            name="submitted_leg_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="ocrscanfeedback",
            name="corrections",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Compact deltas only, e.g. {"f": {"odds_american": ["335","750"]}, "legs": [...]}.',
            ),
        ),
        migrations.AlterField(
            model_name="ocrscanfeedback",
            name="parser_sportsbook",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.RemoveField(
            model_name="ocrscanfeedback",
            name="diff",
        ),
        migrations.RemoveField(
            model_name="ocrscanfeedback",
            name="predicted_snapshot",
        ),
        migrations.RemoveField(
            model_name="ocrscanfeedback",
            name="submitted_snapshot",
        ),
    ]
