from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "rationundo",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=False,
)

# Run every 3 hours between 6 AM and 9 PM IST
celery_app.conf.beat_schedule = {
    "scrape-stock-status": {
        "task": "app.worker.tasks.scrape_all_shops",
        "schedule": crontab(minute=0, hour="6,9,12,15,18,21"),
    },
}
