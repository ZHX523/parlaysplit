import random

from django.db import migrations, models


def populate_host_codes(apps, schema_editor):
    Parlay = apps.get_model("parlays", "Parlay")
    used = set()
    for parlay in Parlay.objects.order_by("pk"):
        for _ in range(500):
            code = f"{random.randint(0, 99999):05d}"
            if code not in used:
                parlay.host_code = code
                parlay.save(update_fields=["host_code"])
                used.add(code)
                break
        else:
            raise RuntimeError(f"Could not assign host_code for parlay {parlay.pk}")


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0006_leg_type_four_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="parlay",
            name="host_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="5-digit code for the host to find and manage this parlay.",
                max_length=5,
                null=True,
            ),
        ),
        migrations.RunPython(populate_host_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="parlay",
            name="host_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="5-digit code for the host to find and manage this parlay.",
                max_length=5,
                unique=True,
            ),
        ),
    ]
