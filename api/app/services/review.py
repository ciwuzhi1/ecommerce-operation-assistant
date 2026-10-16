import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.models import PerformanceRecord, Product
from app.services.llm import (
    LLMNotConfiguredError,
    LLMResponseError,
    create_json_chat_completion,
)


class ReviewReportOutput(BaseModel):
    summary: str = Field(min_length=1)
    insights: list[str] = Field(min_length=1, max_length=8)
    next_actions: list[str] = Field(min_length=1, max_length=8)


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


def generate_review(product: Product) -> dict:
    """生成经营复盘；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    try:
        return generate_llm_review(product)
    except (LLMNotConfiguredError, LLMResponseError, ValidationError) as exc:
        # 复盘是投放闭环的末端，模型失败时也要产出规则版下一步动作，方便继续人工决策。
        fallback = generate_rule_based_review(product)
        fallback["insights"].append(f"本次复盘使用规则版兜底，原因：{exc}")
        return fallback


def generate_llm_review(product: Product) -> dict[str, Any]:
    """生成llm经营复盘；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    latest_record = _latest_record(product.performance_records)
    if latest_record is None:
        raise ValueError("No performance records available")

    # 只复盘最近一个经营周期，并带上近几期数据作上下文，避免模型把历史样本混成实时结论。
    parsed, _raw_response = create_json_chat_completion(
        _build_review_messages(product, latest_record),
        max_tokens=2400,
        temperature=0.35,
    )
    report = ReviewReportOutput.model_validate(parsed)

    return {
        "period_start": latest_record.period_start,
        "period_end": latest_record.period_end,
        **report.model_dump(),
    }


def _build_review_messages(
    product: Product,
    latest_record: PerformanceRecord,
) -> list[dict[str, str]]:
    """构建经营复盘消息，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    return [
        {
            "role": "system",
            "content": (
                "你是一个资深电商投放复盘和增长分析专家。"
                "你擅长根据曝光、点击、转化、花费、收入、ROI 和素材内容，判断下一步应该放量、换素材、改详情页、调价或补数据。"
                "你必须只输出合法 json，不要输出 markdown，不要输出解释性前后缀。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于以下商品和经营数据，生成一份运营复盘报告。"
                "输出 json 必须严格符合以下结构：\n"
                "{\n"
                '  "summary": "一句话总结本周期表现，必须包含曝光、点击、成交和 ROI",\n'
                '  "insights": ["洞察1", "洞察2"],\n'
                '  "next_actions": ["下一步动作1", "下一步动作2"]\n'
                "}\n\n"
                "要求：\n"
                "- 所有内容使用简体中文。\n"
                "- insights 要解释为什么，不要只复述数字。\n"
                "- next_actions 必须可执行，适合运营马上安排下一轮素材或投放实验。\n"
                "- 如果样本量太小或数据缺失，要明确提醒，不要过度下结论。\n"
                "- 如果 latest_record 关联了 ad_experiment，summary、insights 或 next_actions 至少一处必须点名该实验，并判断继续、暂停还是复制。\n"
                "- 如果 CTR 好但转化弱，要优先建议检查详情页、价格、信任证明或人群匹配。\n"
                "- 如果 ROI 好且样本不太小，可以建议小步放量和复制素材结构。\n\n"
                f"复盘上下文 json：{_review_context_payload(product, latest_record)}"
            ),
        },
    ]


def generate_rule_based_review(product: Product) -> dict:
    """生成rulebased经营复盘；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    latest_record = _latest_record(product.performance_records)
    if latest_record is None:
        raise ValueError("No performance records available")

    creative_title = latest_record.creative_plan.title if latest_record.creative_plan else "未关联素材"
    experiment_name = latest_record.ad_experiment.name if latest_record.ad_experiment else None
    summary = (
        f"{latest_record.period_start} 至 {latest_record.period_end}，"
        f"商品《{product.name}》累计曝光 {latest_record.impressions or 0}，"
        f"点击 {latest_record.clicks or 0}，成交 {latest_record.conversions or 0}，"
        f"ROI 为 {_format_decimal(latest_record.roi)}。"
    )

    return {
        "period_start": latest_record.period_start,
        "period_end": latest_record.period_end,
        "summary": summary,
        "insights": _insights(latest_record, creative_title, experiment_name),
        "next_actions": _next_actions(latest_record, product, experiment_name),
    }


def _review_context_payload(product: Product, latest_record: PerformanceRecord) -> str:
    """经营复盘上下文载荷，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    records = sorted(
        product.performance_records,
        key=lambda record: (record.period_end, record.created_at),
        reverse=True,
    )
    latest_diagnosis = product.diagnoses[0] if product.diagnoses else None
    # 复盘 prompt 只提供经营记录、诊断和素材实验上下文，不包含广告账号凭据或资金操作入口。
    payload = {
        "product": {
            "name": product.name,
            "platform": product.platform,
            "category": product.category,
            "price": str(product.price) if product.price is not None else None,
            "cost": str(product.cost) if product.cost is not None else None,
            "target_audience": product.target_audience,
            "selling_points": product.selling_points,
        },
        "latest_diagnosis": None
        if latest_diagnosis is None
        else {
            "source": latest_diagnosis.source,
            "positioning": latest_diagnosis.positioning,
            "price_band": latest_diagnosis.price_band,
            "pain_points": latest_diagnosis.pain_points,
            "risks": latest_diagnosis.risks,
            "recommendations": latest_diagnosis.recommendations,
        },
        "latest_record": _performance_record_payload(latest_record),
        "recent_records": [_performance_record_payload(record) for record in records[:5]],
    }
    return json.dumps(payload, ensure_ascii=False)


def _performance_record_payload(record: PerformanceRecord) -> dict[str, Any]:
    """经营数据记录载荷，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    creative_plan = record.creative_plan
    ad_experiment = record.ad_experiment
    return {
        "period_start": str(record.period_start),
        "period_end": str(record.period_end),
        "impressions": record.impressions,
        "clicks": record.clicks,
        "ctr": str(record.ctr) if record.ctr is not None else None,
        "conversions": record.conversions,
        "conversion_rate": str(record.conversion_rate)
        if record.conversion_rate is not None
        else None,
        "spend": str(record.spend) if record.spend is not None else None,
        "revenue": str(record.revenue) if record.revenue is not None else None,
        "roi": str(record.roi) if record.roi is not None else None,
        "notes": record.notes,
        "ad_experiment": None
        if ad_experiment is None
        else {
            "id": ad_experiment.id,
            "name": ad_experiment.name,
            "status": ad_experiment.status,
            "objective": ad_experiment.objective,
            "success_metric": ad_experiment.success_metric,
            "hypothesis": ad_experiment.hypothesis,
        },
        "creative_plan": None
        if creative_plan is None
        else {
            "id": creative_plan.id,
            "type": creative_plan.type,
            "title": creative_plan.title,
            "rationale": creative_plan.rationale,
            "content": creative_plan.content,
        },
    }


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


def _latest_record(records: list[PerformanceRecord]) -> PerformanceRecord | None:
    """最新记录，统一主流程中的格式、默认值和异常边界。"""
    if not records:
        return None
    return max(records, key=lambda record: (record.period_end, record.created_at))


def _insights(
    record: PerformanceRecord,
    creative_title: str,
    experiment_name: str | None = None,
) -> list[str]:
    """洞察，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    insights = [f"本次复盘关联素材：{creative_title}。"]
    if experiment_name:
        insights.insert(0, f"本次数据来自投放实验「{experiment_name}」，可以直接用于判断该实验是否继续、暂停或复制。")

    if record.ctr is not None:
        if record.ctr < Decimal("0.0200"):
            insights.append(f"点击率 {_format_percent(record.ctr)} 偏低，首屏卖点或画面吸引力需要优先优化。")
        elif record.ctr >= Decimal("0.0500"):
            insights.append(f"点击率 {_format_percent(record.ctr)} 表现较好，素材有继续放量测试价值。")
        else:
            insights.append(f"点击率 {_format_percent(record.ctr)} 处于可测试区间，需要结合转化判断。")

    if record.conversion_rate is not None:
        if record.conversion_rate < Decimal("0.0200"):
            insights.append(
                f"点击到成交转化率 {_format_percent(record.conversion_rate)} 偏低，详情页、价格或信任证明可能拖后腿。"
            )
        elif record.conversion_rate >= Decimal("0.0500"):
            insights.append(f"转化率 {_format_percent(record.conversion_rate)} 较好，可优先复制素材结构。")
        else:
            insights.append(f"转化率 {_format_percent(record.conversion_rate)} 中等，建议继续测试不同卖点。")

    if record.roi is not None:
        if record.roi < Decimal("1.0000"):
            insights.append(f"ROI {_format_decimal(record.roi)} 未覆盖投放成本，暂不建议盲目加预算。")
        elif record.roi >= Decimal("2.0000"):
            insights.append(f"ROI {_format_decimal(record.roi)} 有放量潜力，但仍需观察稳定性。")
        else:
            insights.append(f"ROI {_format_decimal(record.roi)} 接近临界区，需要优化点击成本或转化效率。")

    return insights


def _next_actions(
    record: PerformanceRecord,
    product: Product,
    experiment_name: str | None = None,
) -> list[str]:
    # 下一步动作只给运营建议，不会在这里改变实验状态、预算或素材审核结果。
    """下次actions，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    actions = []

    if record.ctr is not None and record.ctr < Decimal("0.0200"):
        actions.append("优先换主图首屏：把核心卖点前置到 3 秒内能看懂的位置。")
    if record.conversion_rate is not None and record.conversion_rate < Decimal("0.0200"):
        actions.append("检查详情页承接：补充效果证明、评价背书、价格权益和售后信息。")
    if record.roi is not None and record.roi < Decimal("1.0000"):
        actions.append("控制预算，先小额测试新素材，不建议直接扩大投放。")
    if record.ctr is not None and record.ctr >= Decimal("0.0500"):
        actions.append("保留当前素材结构，复制 2-3 个同结构不同卖点版本继续测。")
    if experiment_name and record.roi is not None and record.roi >= Decimal("2.5000"):
        actions.append(f"实验「{experiment_name}」达到放量观察线，可标记完成并新建一条复制结构的放量实验。")
    if experiment_name and record.roi is not None and record.roi < Decimal("1.0000"):
        actions.append(f"实验「{experiment_name}」暂不放量，建议标记暂停并回到素材或承接页优化。")
    if product.selling_points:
        actions.append(f"下一版素材优先围绕“{product.selling_points[0]}”做更直接的画面证明。")

    return actions or ["继续补充更多周期数据，再判断是否换图、调价或调整投放人群。"]


def _format_decimal(value: Decimal | None) -> str:
    """格式化小数，统一主流程中的格式、默认值和异常边界。"""
    if value is None:
        return "-"
    return f"{value:.2f}"


def _format_percent(value: Decimal | None) -> str:
    """格式化percent，统一主流程中的格式、默认值和异常边界。"""
    if value is None:
        return "-"
    return f"{value * Decimal('100'):.2f}%"
