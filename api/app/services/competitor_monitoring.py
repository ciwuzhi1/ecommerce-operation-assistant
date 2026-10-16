from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Competitor, CompetitorMonitor, CompetitorMonitorSnapshot
from app.services.link_extraction import LinkExtractionError, fetch_competitor_profile


def next_check_time(interval_days: int, base: datetime | None = None) -> datetime:
    """下次检查time；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    base_time = base or datetime.now(UTC)
    return base_time + timedelta(days=interval_days)


def run_competitor_monitor(db: Session, monitor: CompetitorMonitor) -> CompetitorMonitorSnapshot:
    """执行竞品监控；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    competitor = monitor.competitor
    checked_at = datetime.now(UTC)

    if not competitor.url:
        snapshot = _failed_snapshot(monitor, checked_at, "Competitor URL is empty")
    else:
        try:
            profile = fetch_competitor_profile(competitor.url)
        except LinkExtractionError as exc:
            snapshot = _failed_snapshot(monitor, checked_at, str(exc))
        else:
            payload = profile.model_payload()
            changes = compare_competitor_changes(competitor, payload)
            # 每次监控都先写快照，再更新竞品当前档案，保留历史变化线索供运营复盘。
            snapshot = CompetitorMonitorSnapshot(
                monitor_id=monitor.id,
                product_id=monitor.product_id,
                competitor_id=monitor.competitor_id,
                checked_at=checked_at,
                status="succeeded",
                title=profile.title,
                price=profile.price,
                sales_hint=profile.sales_hint,
                main_image=profile.main_image,
                selling_points=profile.selling_points,
                changes=changes,
                raw_payload=_json_payload(payload),
            )
            _apply_profile_to_competitor(competitor, payload)

    db.add(snapshot)
    db.flush()
    # 无论成功失败都推进下次检查时间，避免异常链接在同一轮调度里被无限重复拉取。
    monitor.last_checked_at = checked_at
    monitor.next_check_at = next_check_time(monitor.interval_days, checked_at)
    return snapshot


def compare_competitor_changes(competitor: Competitor, payload: dict) -> list[str]:
    # 这里只做价格、标题、销量提示和卖点的轻量对比，不推断平台真实销量或库存。
    """比较竞品changes；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    changes: list[str] = []
    next_title = payload.get("title")
    next_price = payload.get("price")
    next_sales_hint = payload.get("sales_hint")
    next_points = payload.get("selling_points") or []

    if next_title and next_title != competitor.title:
        changes.append(f"Title changed: {competitor.title or '-'} -> {next_title}")
    if _decimal_or_none(next_price) != _decimal_or_none(competitor.price):
        changes.append(f"Price changed: {_format_value(competitor.price)} -> {_format_value(next_price)}")
    if next_sales_hint and next_sales_hint != competitor.sales_hint:
        changes.append(f"Sales hint changed: {competitor.sales_hint or '-'} -> {next_sales_hint}")

    new_points = [point for point in next_points if point not in (competitor.selling_points or [])]
    if new_points:
        changes.append(f"New selling points: {', '.join(new_points[:3])}")

    return changes or ["No obvious change detected"]


def _failed_snapshot(
    monitor: CompetitorMonitor,
    checked_at: datetime,
    error: str,
) -> CompetitorMonitorSnapshot:
    """失败快照，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    return CompetitorMonitorSnapshot(
        monitor_id=monitor.id,
        product_id=monitor.product_id,
        competitor_id=monitor.competitor_id,
        checked_at=checked_at,
        status="failed",
        changes=[],
        raw_payload={},
        error=error,
    )


def _apply_profile_to_competitor(competitor: Competitor, payload: dict) -> None:
    """应用资料to竞品，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    for field in ("name", "title", "price", "sales_hint", "main_image", "selling_points"):
        value = payload.get(field)
        if value not in (None, "", []):
            # 空值不覆盖已有资料，防止一次解析失败把运营手工补充的竞品信息抹掉。
            setattr(competitor, field, value)


def _decimal_or_none(value: object) -> Decimal | None:
    """小数ornone，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _format_value(value: object) -> str:
    """格式化值，统一主流程中的格式、默认值和异常边界。"""
    if value is None or value == "":
        return "-"
    return str(value)


def _json_payload(payload: dict) -> dict:
    """JSON载荷，统一主流程中的格式、默认值和异常边界。"""
    return {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in payload.items()
    }
