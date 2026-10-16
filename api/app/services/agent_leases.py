from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AgentRun, AgentRunStatus


LEASE_DURATION = timedelta(minutes=5)
HEARTBEAT_INTERVAL_SECONDS = 60


class AgentLeaseLostError(RuntimeError):
    pass


def create_lease_owner(prefix: str, run_id: int) -> str:
    """创建租约owner；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    return f"{prefix}:{run_id}:{uuid4()}"


def require_active_lease(
    db: Session,
    *,
    run_id: int,
    lease_owner: str | None,
    for_update: bool = False,
) -> AgentRun:
    """校验并获取有效租约；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    statement = select(AgentRun).where(AgentRun.id == run_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    run = db.scalar(statement)
    now = datetime.now(UTC)
    if run is None:
        raise AgentLeaseLostError("Agent run does not exist")
    if run.status != AgentRunStatus.RUNNING:
        raise AgentLeaseLostError(f"Agent run is no longer running: {run.status.value}")
    if lease_owner is not None and run.lease_owner != lease_owner:
        raise AgentLeaseLostError("Agent run lease has been replaced")
    if run.cancel_requested_at is not None:
        raise AgentLeaseLostError("Agent run cancellation was requested")
    if run.timeout_at is not None and _is_due(run.timeout_at, now):
        raise AgentLeaseLostError("Agent run exceeded timeout")
    return run


def renew_active_lease(db: Session, *, run: AgentRun) -> None:
    """renew有效租约；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    run.lease_expires_at = datetime.now(UTC) + LEASE_DURATION


@contextmanager
def agent_lease_heartbeat(run_id: int, lease_owner: str) -> Generator[None, None, None]:
    # 长耗时模型或供应商调用期间独立续租；fencing token 防止旧 Worker 在回收后写回终态。
    """Agent租约心跳续租；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    stopped = Event()

    def heartbeat() -> None:
        """心跳续租；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        while not stopped.wait(HEARTBEAT_INTERVAL_SECONDS):
            now = datetime.now(UTC)
            try:
                with SessionLocal() as db:
                    result = db.execute(
                        update(AgentRun)
                        .where(
                            AgentRun.id == run_id,
                            AgentRun.status == AgentRunStatus.RUNNING,
                            AgentRun.lease_owner == lease_owner,
                            AgentRun.cancel_requested_at.is_(None),
                            or_(AgentRun.timeout_at.is_(None), AgentRun.timeout_at > now),
                        )
                        .values(lease_expires_at=now + LEASE_DURATION)
                    )
                    db.commit()
                    if result.rowcount != 1:
                        return
            except Exception:
                # 心跳失败不伪造成功；现有 lease 到期后由 maintenance 回收并用 fencing 阻止旧写入。
                continue

    thread = Thread(target=heartbeat, name=f"agent-lease-{run_id}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=1)


def _is_due(value: datetime, now: datetime) -> bool:
    """判断到期；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    if value.tzinfo is None:
        return value <= now.replace(tzinfo=None)
    return value <= now
