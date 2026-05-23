import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("parlaysplit")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "clear-expired-host-codes": {
        "task": "parlays.tasks.clear_expired_host_codes_task",
        "schedule": 3600.0,
    },
}
