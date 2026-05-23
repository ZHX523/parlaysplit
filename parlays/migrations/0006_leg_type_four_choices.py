from django.db import migrations, models


def migrate_leg_types_forward(apps, schema_editor):
    ParlayLeg = apps.get_model("parlays", "ParlayLeg")
    mapping = {
        "moneyline": "moneyline",
        "spread": "spread",
        "total_points": "total_points",
        "player_prop": "player_prop",
        "over": "total_points",
        "under": "total_points",
        "total": "total_points",
        "team_prop": "player_prop",
        "other": "moneyline",
    }
    for leg in ParlayLeg.objects.all():
        new_type = mapping.get(leg.leg_type, "moneyline")
        if leg.leg_type != new_type:
            leg.leg_type = new_type
            leg.save(update_fields=["leg_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0005_leg_type_moneyline_over_under"),
    ]

    operations = [
        migrations.RunPython(migrate_leg_types_forward, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="parlayleg",
            name="leg_type",
            field=models.CharField(
                choices=[
                    ("moneyline", "Moneyline"),
                    ("spread", "Spread"),
                    ("total_points", "Total Points"),
                    ("player_prop", "Player Prop"),
                ],
                default="moneyline",
                max_length=32,
            ),
        ),
    ]
