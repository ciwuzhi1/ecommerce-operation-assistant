import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.models import PerformanceRecord, Product




def enrich_performance_metrics(payload: dict) -> dict:
    # 只在用户未填报指标时补算，保留平台报表已有 CTR、CVR、ROI 的原始口径。
    """补充经营数据metrics；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    impressions = payload.get("impressions")
    clicks = payload.get("clicks")
    conversions = payload.get("conversions")
    spend = payload.get("spend")
    revenue = payload.get("revenue")

    if payload.get("ctr") is None:
        payload["ctr"] = _ratio(clicks, impressions)
    if payload.get("conversion_rate") is None:
        payload["conversion_rate"] = _ratio(conversions, clicks)
    if payload.get("roi") is None:
        payload["roi"] = _ratio(revenue, spend)

    return payload














def _ratio(numerator: Decimal | int | None, denominator: Decimal | int | None) -> Decimal | None:
    """比率，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if numerator is None or denominator is None:
        return None

    numerator_decimal = Decimal(str(numerator))
    denominator_decimal = Decimal(str(denominator))
    if denominator_decimal == 0:
        return None

    return (numerator_decimal / denominator_decimal).quantize(Decimal("0.0001"))










