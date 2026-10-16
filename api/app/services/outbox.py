from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from app.db.session import SessionLocal
from app.core.config import get_settings
from app.models import OutboxEvent, OutboxEventStatus


def dispatch_pending_outbox_events(*, limit: int = 50) -> int:
    """调度pendingOutboxevents；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    now = datetime.now(UTC)
    with SessionLocal() as db:
        events = list(
            db.scalars(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status == OutboxEventStatus.PENDING,
                    or_(OutboxEvent.available_at.is_(None), OutboxEvent.available_at <= now),
                )
                .order_by(OutboxEvent.id.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
        )
        published = 0
        for event in events:
            try:
                _publish_event(event)
            except Exception as exc:
                event.attempts += 1
                event.error = str(exc)[:2000]
                if event.attempts >= 10:
                    event.status = OutboxEventStatus.FAILED
                else:
                    event.available_at = now + timedelta(seconds=min(2**event.attempts, 300))
            else:
                event.attempts += 1
                event.status = OutboxEventStatus.PUBLISHED
                event.published_at = now
                event.error = None
                published += 1
        db.commit()
        return published


def kick_outbox_dispatcher() -> None:
    """kickOutboxdispatcher；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    from app.worker.tasks import dispatch_outbox_events_task

    dispatch_outbox_events_task.apply_async(queue=get_settings().celery_maintenance_queue)


def _publish_event(event: OutboxEvent) -> None:
    """publish事件，统一主流程中的格式、默认值和异常边界。"""
    if event.event_type != "workflow.run.requested":
        raise RuntimeError(f"Unsupported outbox event type: {event.event_type}")
    from app.worker.tasks import run_registered_agent_workflow_task

    run_registered_agent_workflow_task.apply_async(
        args=[event.payload["run_id"], event.payload.get("resume_payload")],
        queue=get_settings().celery_agent_workflow_queue,
    )
