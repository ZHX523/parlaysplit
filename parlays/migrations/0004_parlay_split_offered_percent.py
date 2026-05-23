from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0003_alter_parlay_creator_nickname"),
    ]

    operations = [
        migrations.AddField(
            model_name="parlay",
            name="split_offered_percent",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("100.00"),
                help_text="Max percent of the wager friends may claim in total.",
                max_digits=5,
            ),
        ),
    ]
