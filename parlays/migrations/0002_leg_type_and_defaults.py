from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="parlayleg",
            name="leg_type",
            field=models.CharField(
                choices=[
                    ("moneyline", "Moneyline"),
                    ("spread", "Spread"),
                    ("total", "Total (O/U)"),
                    ("player_prop", "Player prop"),
                    ("team_prop", "Team prop"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="parlay",
            name="sportsbook",
            field=models.CharField(
                choices=[
                    ("fanduel", "FanDuel"),
                    ("draftkings", "DraftKings"),
                    ("betmgm", "BetMGM"),
                    ("caesars", "Caesars"),
                    ("espnbet", "ESPN BET"),
                    ("other", "Other"),
                ],
                default="fanduel",
                max_length=32,
            ),
        ),
    ]
