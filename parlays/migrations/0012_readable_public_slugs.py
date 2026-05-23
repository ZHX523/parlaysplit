import re
import secrets

from django.db import migrations, models
from django.utils.text import slugify

_LEGACY_SLUG_RE = re.compile(r"^[0-9a-f]{12}$")


def _build_slug(parlay, used: set[str]) -> str:
    host = slugify(parlay.creator_nickname or "host") or "host"
    host = host[:32].strip("-")
    leg_count = parlay.legs.count()
    for _ in range(80):
        suffix = secrets.token_hex(3)
        candidate = f"{host}-parlay-{leg_count}-legs-{suffix}"
        if candidate not in used and len(candidate) <= 96:
            return candidate
    raise RuntimeError(f"Could not assign slug for parlay {parlay.pk}")


def backfill_readable_slugs(apps, schema_editor):
    Parlay = apps.get_model("parlays", "Parlay")
    used = set(Parlay.objects.values_list("slug", flat=True))
    for parlay in Parlay.objects.prefetch_related("legs").order_by("pk"):
        slug = parlay.slug or ""
        if slug and not _LEGACY_SLUG_RE.match(slug) and not slug.startswith("pending-"):
            continue
        new_slug = _build_slug(parlay, used)
        used.add(new_slug)
        Parlay.objects.filter(pk=parlay.pk).update(slug=new_slug)


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0011_backfill_parlay_expiry"),
    ]

    operations = [
        migrations.AlterField(
            model_name="parlay",
            name="slug",
            field=models.SlugField(
                editable=False,
                help_text="Public URL segment, e.g. jordan-parlay-3-legs-x7k2m9.",
                max_length=96,
                unique=True,
            ),
        ),
        migrations.RunPython(backfill_readable_slugs, migrations.RunPython.noop),
    ]
