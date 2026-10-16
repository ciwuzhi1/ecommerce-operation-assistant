from datetime import UTC, datetime

from sqlalchemy import or_, select

from app.db.session import SessionLocal
from app.models import (
    AgentApproval,
    AgentApprovalStatus,
    AgentMemory,
    AgentMemoryStatus,
    AgentRun,
    AgentRunEvent,
    AgentRunStatus,
    AgentTask,
    AgentTaskStatus,
    OutboxEvent,
)


def maintain_agent_runtime() -> dict[str, int]:
    """维护Agentruntime；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    now = datetime.now(UTC)
    counters = {
        "timed_out": 0,
        "cancelled": 0,
        "recovered": 0,
        "approvals_expired": 0,
        "memories_expired": 0,
    }
    with SessionLocal() as db:
        running = db.scalars(
            select(AgentRun)
            .where(
                AgentRun.status == AgentRunStatus.RUNNING,
                or_(
                    AgentRun.cancel_requested_at.is_not(None),
                    AgentRun.timeout_at <= now,
                    AgentRun.lease_expires_at <= now,
                ),
            )
            .with_for_update(skip_locked=True)
        ).all()
        for run in running:
            task = db.get(AgentTask, run.task_id) if run.task_id else None
            if run.cancel_requested_at is not None:
                _finish_run(run, task, AgentRunStatus.CANCELLED, AgentTaskStatus.CANCELLED, now)
                counters["cancelled"] += 1
                event_type = "cancelled"
                message = "运行响应取消请求并停止恢复。"
            elif _is_due(run.timeout_at, now):
                _finish_run(run, task, AgentRunStatus.FAILED, AgentTaskStatus.FAILED, now)
                run.error = "Agent run exceeded timeout"
                if task is not None:
                    task.error = run.error
                counters["timed_out"] += 1
                event_type = "timed_out"
                message = "运行超过超时边界，已停止自动重试。"
            else:
                run.attempt += 1
                run.status = AgentRunStatus.QUEUED
                run.lease_owner = None
                run.lease_expires_at = None
                if task is not None:
                    task.status = AgentTaskStatus.QUEUED
                db.add(
                    OutboxEvent(
                        workspace_id=run.workspace_id,
                        aggregate_type="agent_run",
                        aggregate_id=str(run.id),
                        event_type="workflow.run.requested",
                        payload={"run_id": run.id, "resume_payload": None},
                        idempotency_key=f"agent-run:{run.id}:recovery:{run.attempt}",
                        status="pending",
                        attempts=0,
                        available_at=now,
                    )
                )
                counters["recovered"] += 1
                event_type = "lease_recovered"
                message = "Worker lease 已过期，运行重新进入幂等队列。"
            db.add(
                AgentRunEvent(
                    run_id=run.id,
                    event_type=event_type,
                    status=run.status.value,
                    message=message,
                )
            )

        approvals = db.scalars(
            select(AgentApproval)
            .where(
                AgentApproval.status == AgentApprovalStatus.PENDING,
                AgentApproval.expires_at.is_not(None),
                AgentApproval.expires_at <= now,
            )
            .with_for_update(skip_locked=True)
        ).all()
        for approval in approvals:
            approval.status = AgentApprovalStatus.EXPIRED
            approval.decided_at = now
            approval.note = "审批超过有效期，未执行受控动作。"
            run = db.get(AgentRun, approval.run_id)
            task = db.get(AgentTask, approval.task_id)
            if run is not None:
                _finish_run(run, task, AgentRunStatus.CANCELLED, AgentTaskStatus.CANCELLED, now)
                db.add(
                    AgentRunEvent(
                        run_id=run.id,
                        event_type="approval_expired",
                        status=AgentRunStatus.CANCELLED.value,
                        message=approval.note,
                    )
                )
            counters["approvals_expired"] += 1

        memories = db.scalars(
            select(AgentMemory)
            .where(
                AgentMemory.status == AgentMemoryStatus.ACTIVE,
                AgentMemory.expires_at.is_not(None),
                AgentMemory.expires_at <= now,
            )
            .with_for_update(skip_locked=True)
        ).all()
        for memory in memories:
            memory.status = AgentMemoryStatus.EXPIRED
            counters["memories_expired"] += 1
        db.commit()
    return counters


def _finish_run(
    run: AgentRun,
    task: AgentTask | None,
    run_status: AgentRunStatus,
    task_status: AgentTaskStatus,
    now: datetime,
) -> None:
    """结束执行；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    run.status = run_status
    run.finished_at = now
    run.lease_owner = None
    run.lease_expires_at = None
    if task is not None:
        task.status = task_status
        task.finished_at = now


def _is_due(value: datetime | None, now: datetime) -> bool:
    """判断到期；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    if value is None:
        return False
    if value.tzinfo is None:
        return value <= now.replace(tzinfo=None)
    return value <= now
