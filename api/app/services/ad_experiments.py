from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from app.models import GeneratedAsset, PerformanceRecord, Product, PromotionLink


def build_ad_experiment_payload(product: Product) -> dict[str, Any]:
    # 实验计划从已有素材、链接和回填数据中挑候选项，产出 draft，真实投放仍由运营人工创建或确认。
    """构建投放实验载荷；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    best_asset = _best_asset(product.generated_assets, product.performance_records)
    best_link = _best_link(product.promotion_links, product.performance_records)
    primary_selling_point = product.selling_points[0] if product.selling_points else "核心卖点"

    asset_name = best_asset["item"].title if best_asset is not None else None
    link_name = best_link["item"].label if best_link is not None else None
    name = f"{date.today():%m%d} 小预算素材承接实验"

    objective = "验证推荐素材和承接链接在小预算投放下的点击、转化与 ROI 稳定性"
    if best_asset is not None and (best_asset["roi"] or Decimal("0")) >= Decimal("3"):
        objective = "验证高 ROI 素材小幅加预算后的转化稳定性"

    hypothesis_parts = [f"围绕「{primary_selling_point}」继续放大表达"]
    if asset_name:
        hypothesis_parts.append(f"优先使用素材「{asset_name}」")
    if link_name:
        hypothesis_parts.append(f"搭配链接「{link_name}」")

    return {
        "generated_asset_id": best_asset["item"].id if best_asset is not None else None,
        "promotion_link_id": best_link["item"].id if best_link is not None else None,
        "name": name,
        "objective": objective,
        "audience": product.target_audience or "近期浏览、互动或加购同类商品的核心目标人群",
        "daily_budget": Decimal("300.00"),
        "status": "draft",
        "success_metric": "连续 2 天 ROI >= 2.5 且 CTR >= 4%，再进入人工确认放量",
        "hypothesis": "；".join(hypothesis_parts),
        "note": "仅生成实验计划，不自动创建广告计划或执行资金操作；投放前需要人工确认。",
    }


def _best_asset(
    assets: list[GeneratedAsset],
    records: list[PerformanceRecord],
) -> dict[str, Any] | None:
    """最佳素材，统一主流程中的格式、默认值和异常边界。"""
    return _best_by_records(assets, records, "generated_asset_id")


def _best_link(
    links: list[PromotionLink],
    records: list[PerformanceRecord],
) -> dict[str, Any] | None:
    """最佳链接，统一主流程中的格式、默认值和异常边界。"""
    return _best_by_records(links, records, "promotion_link_id")


def _best_by_records(
    items: list[GeneratedAsset] | list[PromotionLink],
    records: list[PerformanceRecord],
    record_field: str,
) -> dict[str, Any] | None:
    """最佳byrecords，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if not items:
        return None

    item_by_id = {item.id: item for item in items if item.id is not None}
    summaries: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "clicks": 0,
            "impressions": 0,
            "record_count": 0,
            "revenue": Decimal("0"),
            "spend": Decimal("0"),
        }
    )

    for record in records:
        item_id = getattr(record, record_field)
        if item_id is None or item_id not in item_by_id:
            continue

        summary = summaries[item_id]
        summary["clicks"] += record.clicks or 0
        summary["impressions"] += record.impressions or 0
        summary["record_count"] += 1
        summary["revenue"] += record.revenue or Decimal("0")
        summary["spend"] += record.spend or Decimal("0")

    if not summaries:
        # 没有历史数据时不伪造效果判断，只返回首个候选项作为冷启动默认值。
        return {"item": items[0], "ctr": None, "roi": None, "record_count": 0}

    rows = []
    for item_id, summary in summaries.items():
        spend = summary["spend"]
        impressions = summary["impressions"]
        rows.append(
            {
                "item": item_by_id[item_id],
                "ctr": Decimal(summary["clicks"]) / Decimal(impressions)
                if impressions > 0
                else None,
                "roi": summary["revenue"] / spend if spend > 0 else None,
                "record_count": summary["record_count"],
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            row["roi"] if row["roi"] is not None else Decimal("-1"),
            row["ctr"] if row["ctr"] is not None else Decimal("-1"),
            row["record_count"],
        ),
        reverse=True,
    )[0]
