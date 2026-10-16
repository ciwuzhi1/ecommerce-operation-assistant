from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CompetitorMonitor
from app.schemas import CompetitorMonitorSchedulerRunResult
from app.services.competitor_monitoring import run_competitor_monitor


def run_due_competitor_monitors(
    db: Session,
    *,
    limit: int = 20,
    now: datetime | None = None,
) -> CompetitorMonitorSchedulerRunResult:
    """执行到期竞品monitors；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    current_time = now or datetime.now(UTC)
    # 每轮只取到期且 active 的监控，并按 next_check_at 排序，避免一次调度扫全量竞品。
    statement = (
        select(CompetitorMonitor)
        .where(
            CompetitorMonitor.status == "active",
            CompetitorMonitor.next_check_at.is_not(None),
            CompetitorMonitor.next_check_at <= current_time,
        )
        .options(selectinload(CompetitorMonitor.competitor))
        .order_by(CompetitorMonitor.next_check_at.asc(), CompetitorMonitor.id.asc())
        .limit(limit)
    )
    monitors = list(db.scalars(statement).all())
    result = CompetitorMonitorSchedulerRunResult(
        checked_count=0,
        succeeded_count=0,
        failed_count=0,
        skipped_count=0,
        monitor_ids=[],
        errors=[],
    )

    for monitor in monitors:
        # 调度器只消费到期监控，不主动创建新监控；单个竞品解析失败会写入失败快照并继续下一条。
        try:
            snapshot = run_competitor_monitor(db, monitor)
            result.checked_count += 1
            result.monitor_ids.append(monitor.id)
            if snapshot.status == "succeeded":
                result.succeeded_count += 1
            else:
                result.failed_count += 1
                if snapshot.error:
                    result.errors.append(f"monitor#{monitor.id}: {snapshot.error}")
        except Exception as exc:
            result.failed_count += 1
            result.errors.append(f"monitor#{monitor.id}: {exc}")

    db.commit()
    return result
