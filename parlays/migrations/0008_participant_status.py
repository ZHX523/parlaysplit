from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0007_parlay_host_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                ],
                db_index=True,
                default="approved",
                max_length=16,
            ),
        ),
    ]
