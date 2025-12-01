"""Celery application factory."""

from celery import Celery

from .config import settings

celery_app = Celery(
    "jobrunner",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["jobrunner.tasks"],
)

celery_app.conf.task_default_queue = settings.default_queue
celery_app.conf.result_expires = 3600
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1

# Ensure task modules register with the worker
celery_app.autodiscover_tasks(["jobrunner"])

__all__ = ["celery_app"]
