from django.apps import AppConfig


class ParlaysConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "parlays"
    verbose_name = "ParlaySplit"

    def ready(self):
        import parlays.signals  # noqa: F401
