from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def backfill_expiry(apps, schema_editor):
    Parlay = apps.get_model("parlays", "Parlay")
    ttl = timedelta(hours=48)
    for parlay in Parlay.objects.filter(host_code_expires_at__isnull=True):
        base = parlay.created_at or timezone.now()
        Parlay.objects.filter(pk=parlay.pk).update(host_code_expires_at=base + ttl)


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0010_host_code_expiry_and_alphanumeric"),
    ]

    operations = [
        migrations.RunPython(backfill_expiry, migrations.RunPython.noop),
    ]
