from celery import Celery
from app.config import settings

celery_app = Celery(
    "ocr_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Автоматический импорт задач
celery_app.autodiscover_tasks(["app.tasks"])

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tashkent",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_max_retries=3,
    task_default_retry_delay=60,
    task_routes={
        "app.tasks.ocr_task.process_ocr": {"queue": "ocr"},
    },
    worker_max_tasks_per_child=500,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_send_task_events=True,
    task_send_sent_event=True,
    result_expires=3600,
)
