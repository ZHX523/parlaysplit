from django.db import migrations, models


def migrate_leg_types_forward(apps, schema_editor):
    ParlayLeg = apps.get_model("parlays", "ParlayLeg")
    mapping = {
        "moneyline": "moneyline",
        "over": "over",
        "under": "under",
        "spread": "moneyline",
        "total": "over",
        "player_prop": "moneyline",
        "team_prop": "moneyline",
        "other": "moneyline",
    }
    for leg in ParlayLeg.objects.all():
        new_type = mapping.get(leg.leg_type, "moneyline")
        if leg.leg_type != new_type:
            leg.leg_type = new_type
            leg.save(update_fields=["leg_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0004_parlay_split_offered_percent"),
    ]

    operations = [
        migrations.RunPython(migrate_leg_types_forward, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="parlayleg",
            name="leg_type",
            field=models.CharField(
                choices=[
                    ("moneyline", "Money Line"),
                    ("over", "Over"),
                    ("under", "Under"),
                ],
                default="moneyline",
                max_length=32,
            ),
        ),
    ]
