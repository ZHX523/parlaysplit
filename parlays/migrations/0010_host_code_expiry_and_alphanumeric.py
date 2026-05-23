from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def set_host_code_expiry(apps, schema_editor):
    Parlay = apps.get_model("parlays", "Parlay")
    now = timezone.now()
    for parlay in Parlay.objects.exclude(host_code="").exclude(host_code__isnull=True):
        Parlay.objects.filter(pk=parlay.pk).update(
            host_code_expires_at=parlay.created_at + timedelta(hours=48)
            if parlay.created_at
            else now + timedelta(hours=48)
        )


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0009_remove_parlay_sportsbook"),
    ]

    operations = [
        migrations.AddField(
            model_name="parlay",
            name="host_code_expires_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="When set, host_code stops working after this time.",
            ),
        ),
        migrations.AlterField(
            model_name="parlay",
            name="host_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Alphanumeric code for the host to find and manage this parlay (expires after 48h).",
                max_length=8,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(set_host_code_expiry, migrations.RunPython.noop),
    ]
