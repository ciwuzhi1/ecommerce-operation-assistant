"""Celery 应用（DesignSpec §3、§8 高可用 / PRD FR-57、FR-58）。

队列隔离与可靠性配置：
- task_acks_late + task_reject_on_worker_lost：执行者异常退出时由队列重投
- worker_prefetch_multiplier=1：防止慢任务霸占 Worker
- 软超时 / 硬超时双阈值（PRD M8：硬超时 <= 1800s）
- Beat 周期任务：投递派发（5s）与运行维护（30s）

实现任务：T-15、T-35。
"""
from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# 队列名（DesignSpec §4 部署拓扑）
QUEUE_GENERATION = "generation"
QUEUE_AGENT = "agent"
QUEUE_AGENT_WORKFLOW = "agent.workflow"
QUEUE_MAINTENANCE = "maintenance"

celery_app = Celery(
    "ecommerce_operation",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_default_queue=settings.celery_task_default_queue,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "generation.*": {"queue": settings.celery_task_default_queue},
        "agent.run_product_operation": {"queue": settings.celery_agent_queue},
        "agent.run_registered_workflow": {"queue": settings.celery_agent_workflow_queue},
        "maintenance.*": {"queue": settings.celery_maintenance_queue},
    },
    task_annotations={
        "agent.run_product_operation": {"soft_time_limit": 1700, "time_limit": 1800},
        "agent.run_registered_workflow": {"soft_time_limit": 1700, "time_limit": 1800},
    },
    beat_schedule={
        "dispatch-agent-outbox": {
            "task": "maintenance.dispatch_outbox",
            "schedule": 5.0,
            "options": {"queue": settings.celery_maintenance_queue},
        },
        "maintain-agent-runtime": {
            "task": "maintenance.agent_runtime",
            "schedule": 30.0,
            "options": {"queue": settings.celery_maintenance_queue},
        },
    },
)
