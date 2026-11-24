import os

from celery import Celery
from django.conf import settings
from kombu import Exchange, Queue

from pipeline.config import GROUPS

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mice.settings")
app = Celery("mice")
task_exchange = Exchange("mice.tasks", type="direct", durable=True)
dead_exchange = Exchange("mice.dead", type="direct", durable=True)
queues = []
for group in GROUPS:
    queues.extend(
        [
            Queue(
                group,
                task_exchange,
                routing_key=group,
                durable=True,
                queue_arguments={
                    "x-queue-type": "quorum",
                    "x-dead-letter-exchange": "mice.dead",
                    "x-dead-letter-routing-key": group,
                    "x-delivery-limit": 8,
                    "x-dead-letter-strategy": "at-least-once",
                    "x-overflow": "reject-publish",
                },
            ),
            Queue(
                group + ".dead",
                dead_exchange,
                routing_key=group,
                durable=True,
                queue_arguments={"x-queue-type": "quorum"},
            ),
        ]
    )
app.conf.update(
    broker_url=settings.MICE_BROKER_URL,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=5,
    broker_transport_options={"confirm_publish": True, "confirm_timeout": 5},
    broker_heartbeat=30,
    task_queues=queues,
    task_default_queue="maintenance",
    task_default_exchange="mice.tasks",
    task_default_exchange_type="direct",
    task_default_routing_key="maintenance",
    task_create_missing_queues=False,
    task_default_delivery_mode="persistent",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=True,
    worker_prefetch_multiplier=1,
    worker_detect_quorum_queues=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_publish_retry=False,
    enable_utc=True,
    timezone="UTC",
    beat_schedule={
        "retention-cleanup": {
            "task": "pipeline.periodic",
            "schedule": 3600.0,
            "args": ["9f644100-0000-4000-8000-000000000003"],
            "options": {"queue": "maintenance", "routing_key": "maintenance"},
        },
        "resource-samples": {
            "task": "pipeline.periodic",
            "schedule": 30.0,
            "args": ["9f644100-0000-4000-8000-000000000001"],
            "options": {"queue": "maintenance", "routing_key": "maintenance"},
        },
        "delivery-recovery": {
            "task": "pipeline.periodic",
            "schedule": 30.0,
            "args": ["9f644100-0000-4000-8000-000000000002"],
            "options": {"queue": "maintenance", "routing_key": "maintenance"},
        },
    },
)
app.autodiscover_tasks(["pipeline"])
