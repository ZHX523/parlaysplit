from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0002_leg_type_and_defaults"),
    ]

    operations = [
        migrations.AlterField(
            model_name="parlay",
            name="creator_nickname",
            field=models.CharField(default="Host", max_length=64),
        ),
    ]
