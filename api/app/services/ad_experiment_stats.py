from datetime import date
from decimal import Decimal
from typing import Any

from app.models import AdExperiment, PerformanceRecord, Product


ZERO = Decimal("0")


def build_ad_experiment_dashboard(product: Product) -> dict[str, Any]:
    # 仪表盘只汇总用户回填的实验数据，用于复盘与人工决策，不代表平台实时消耗。
    """构建投放实验看板；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    rows = [
        _summarize_experiment(experiment, product.performance_records)
        for experiment in product.ad_experiments
    ]
    rows.sort(
        key=lambda row: (
            row["record_count"] > 0,
            row["roi"] if row["roi"] is not None else Decimal("-1"),
            row["revenue"],
        ),
        reverse=True,
    )

    measured_rows = [row for row in rows if row["record_count"] > 0]
    total_spend = sum((row["spend"] for row in measured_rows), ZERO)
    total_revenue = sum((row["revenue"] for row in measured_rows), ZERO)

    return {
        "product_id": product.id,
        "total_experiments": len(rows),
        "active_experiments": sum(1 for item in product.ad_experiments if item.status == "active"),
        "measured_experiments": len(measured_rows),
        "total_spend": total_spend,
        "total_revenue": total_revenue,
        "overall_roi": _ratio(total_revenue, total_spend),
        "best_experiment": measured_rows[0] if measured_rows else None,
        "rows": rows,
    }


def _summarize_experiment(
    experiment: AdExperiment,
    records: list[PerformanceRecord],
) -> dict[str, Any]:
    """汇总实验，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    linked_records = [record for record in records if record.ad_experiment_id == experiment.id]
    impressions = sum((record.impressions or 0 for record in linked_records), 0)
    clicks = sum((record.clicks or 0 for record in linked_records), 0)
    conversions = sum((record.conversions or 0 for record in linked_records), 0)
    spend = sum((record.spend or ZERO for record in linked_records), ZERO)
    revenue = sum((record.revenue or ZERO for record in linked_records), ZERO)
    period_start = _min_date(record.period_start for record in linked_records)
    period_end = _max_date(record.period_end for record in linked_records)
    ctr = _ratio(Decimal(clicks), Decimal(impressions))
    conversion_rate = _ratio(Decimal(conversions), Decimal(clicks))
    roi = _ratio(revenue, spend)

    decision, decision_reason = _experiment_decision(
        status=experiment.status,
        record_count=len(linked_records),
        ctr=ctr,
        roi=roi,
        spend=spend,
    )

    return {
        "ad_experiment_id": experiment.id,
        "name": experiment.name,
        "status": experiment.status,
        "generated_asset_id": experiment.generated_asset_id,
        "promotion_link_id": experiment.promotion_link_id,
        "daily_budget": experiment.daily_budget,
        "record_count": len(linked_records),
        "period_start": period_start,
        "period_end": period_end,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "spend": spend,
        "revenue": revenue,
        "ctr": ctr,
        "conversion_rate": conversion_rate,
        "roi": roi,
        "cpc": _ratio(spend, Decimal(clicks)),
        "cpa": _ratio(spend, Decimal(conversions)),
        "decision": decision,
        "decision_reason": decision_reason,
    }


def _experiment_decision(
    status: str,
    record_count: int,
    ctr: Decimal | None,
    roi: Decimal | None,
    spend: Decimal,
) -> tuple[str, str]:
    # 决策标签是运营提示，不会触发自动暂停、加预算或资金动作，所有执行都留给人工确认。
    """实验decision，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if record_count == 0:
        return "needs_data", "暂无回填数据，先补充实验维度经营数据再判断。"
    if status in {"paused", "archived"}:
        return "observe", "实验已暂停或归档，适合保留为历史样本对照。"
    if roi is not None and roi >= Decimal("3") and (ctr is None or ctr >= Decimal("0.04")):
        return "scale", "ROI 和点击表现达到小幅放量观察线，建议人工确认后复制或加预算。"
    if roi is not None and roi >= Decimal("2"):
        return "keep", "ROI 具备继续观察价值，建议维持预算并补充 1-2 个对照样本。"
    if spend > ZERO and (roi is None or roi < Decimal("1")):
        return "pause", "已有花费但 ROI 偏低，建议暂停或回到素材、链接、人群侧优化。"
    return "observe", "样本仍偏少，继续观察点击与成交稳定性。"


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """比率，统一主流程中的格式、默认值和异常边界。"""
    if denominator <= ZERO:
        return None
    return numerator / denominator


def _min_date(values: Any) -> date | None:
    """最小日期，统一主流程中的格式、默认值和异常边界。"""
    items = [value for value in values if value is not None]
    return min(items) if items else None


def _max_date(values: Any) -> date | None:
    """max日期，统一主流程中的格式、默认值和异常边界。"""
    items = [value for value in values if value is not None]
    return max(items) if items else None
