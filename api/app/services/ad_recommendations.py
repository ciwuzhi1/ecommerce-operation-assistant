import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.models import CreativePlanStatus, CreativePlanType, PerformanceRecord, Product
from app.services.llm import (
    LLMNotConfiguredError,
    LLMResponseError,
    create_json_chat_completion,
)


class AudienceSegmentOutput(BaseModel):
    name: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    targeting: list[str] = Field(min_length=1, max_length=8)


class BudgetPlanOutput(BaseModel):
    daily_budget: str = Field(min_length=1)
    allocation: list[str] = Field(min_length=1, max_length=8)
    stop_loss_rule: str = Field(min_length=1)


class CreativeTestOutput(BaseModel):
    name: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    asset_direction: str = Field(min_length=1)
    success_metric: str = Field(min_length=1)


class AdRecommendationOutput(BaseModel):
    summary: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    audience_segments: list[AudienceSegmentOutput] = Field(min_length=1, max_length=5)
    budget_plan: BudgetPlanOutput
    creative_tests: list[CreativeTestOutput] = Field(min_length=1, max_length=6)
    bid_strategy: list[str] = Field(min_length=1, max_length=8)
    risk_controls: list[str] = Field(min_length=1, max_length=8)
    next_steps: list[str] = Field(min_length=1, max_length=8)


def generate_ad_recommendation(product: Product) -> dict[str, Any]:
    """生成投放建议；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    try:
        return generate_llm_ad_recommendation(product)
    except (LLMNotConfiguredError, LLMResponseError, ValidationError) as exc:
        # 投放建议不能因为模型波动而中断运营流程，规则兜底仍明确要求小预算和人工确认。
        fallback = generate_rule_based_ad_recommendation(product)
        fallback["content"]["risk_controls"].append(f"本次使用规则版兜底，原因：{exc}")
        return fallback


def generate_llm_ad_recommendation(product: Product) -> dict[str, Any]:
    """生成llm投放建议；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed, raw_response = create_json_chat_completion(
        _build_ad_messages(product),
        max_tokens=2600,
        temperature=0.35,
    )
    recommendation = AdRecommendationOutput.model_validate(parsed)
    content = recommendation.model_dump()
    # 模型名可用于后续复盘生成质量，但投放建议本身仍按结构化字段保存，方便人工编辑。
    content["llm_model"] = raw_response.get("model")

    return {
        "source": "llm",
        "summary": recommendation.summary,
        "content": content,
    }


def generate_rule_based_ad_recommendation(product: Product) -> dict[str, Any]:
    """生成rulebased投放建议；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    latest_record = _latest_record(product.performance_records)
    # 已选素材优先进入建议，未选时也保留主图/视频脚本方向，帮助运营继续做可编辑测试计划。
    selected_plans = [
        plan
        for plan in product.creative_plans
        if plan.status == CreativePlanStatus.SELECTED
        or plan.type in {CreativePlanType.MAIN_IMAGE, CreativePlanType.VIDEO_SCRIPT}
    ][:4]
    primary_selling_point = product.selling_points[0] if product.selling_points else "核心卖点"
    objective = _objective(latest_record)

    content = {
        "summary": f"围绕「{primary_selling_point}」先做小预算素材测试，再根据 CTR、转化率和 ROI 决定放量。",
        "objective": objective,
        "audience_segments": [
            {
                "name": "核心需求人群",
                "rationale": f"已对「{product.category or product.name}」有明确需求，最适合验证基础转化。",
                "targeting": [
                    product.target_audience or "近期浏览同类商品人群",
                    f"关注{primary_selling_point}相关内容的人群",
                    "近 7-30 天互动/加购相似商品人群",
                ],
            },
            {
                "name": "竞品兴趣人群",
                "rationale": "竞品用户已经被市场教育，适合用价格、利益点或场景差异切入。",
                "targeting": [
                    "同类目爆品互动人群",
                    "竞品关键词兴趣人群",
                    "相似价格带消费人群",
                ],
            },
        ],
        "budget_plan": {
            "daily_budget": _budget(latest_record),
            "allocation": [
                "60% 用于已选中素材验证",
                "30% 用于新主图/视频 A/B 测试",
                "10% 预留给临时表现突出的素材加码",
            ],
            "stop_loss_rule": "单素材花费达到目标客单价 1-1.5 倍仍无转化时暂停。",
        },
        "creative_tests": [
            {
                "name": plan.title,
                "hypothesis": plan.rationale or f"验证 {primary_selling_point} 是否能拉动点击和转化。",
                "asset_direction": _plan_direction(plan.content),
                "success_metric": "CTR、点击成本、转化率、ROI 同时观察，至少跑满 1000 曝光再判断。",
            }
            for plan in selected_plans[:3]
        ]
        or [
            {
                "name": "基础卖点素材",
                "hypothesis": f"直接突出 {primary_selling_point} 能带来第一批点击。",
                "asset_direction": "商品主体清晰，首屏突出价格、利益点和使用场景。",
                "success_metric": "先看 CTR，再看点击到成交转化。",
            }
        ],
        "bid_strategy": _bid_strategy(latest_record),
        "risk_controls": [
            "不要在样本太小时直接放量，至少观察点击和转化两层指标。",
            "同一素材连续 2 个观察周期衰减时，优先换首屏表达而不是只加预算。",
            "素材承诺必须和详情页证明一致，避免高点击低转化。",
        ],
        "next_steps": [
            "选择 2-3 个主图/视频素材建立第一轮 A/B 测试。",
            "为每个素材绑定独立投放计划或标记，方便复盘。",
            "跑满一个观察周期后录入数据，再生成复盘报告。",
        ],
    }
    return {
        "source": "rules",
        "summary": content["summary"],
        "content": content,
    }


def _build_ad_messages(product: Product) -> list[dict[str, str]]:
    """构建投放消息，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    return [
        {
            "role": "system",
            "content": (
                "你是资深电商投放策略专家，擅长把商品诊断、素材方案和经营数据转成可执行的投放计划。"
                "你必须只输出合法 JSON，不要输出 markdown。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于以下商品上下文生成投放建议。输出 JSON 必须符合：\n"
                "{\n"
                '  "summary": "一句话策略摘要",\n'
                '  "objective": "本轮投放目标",\n'
                '  "audience_segments": [{"name": "人群名", "rationale": "为什么投", "targeting": ["定向建议"]}],\n'
                '  "budget_plan": {"daily_budget": "日预算建议", "allocation": ["预算分配"], "stop_loss_rule": "止损规则"},\n'
                '  "creative_tests": [{"name": "测试名", "hypothesis": "假设", "asset_direction": "素材方向", "success_metric": "成功指标"}],\n'
                '  "bid_strategy": ["出价/优化目标建议"],\n'
                '  "risk_controls": ["风险控制"],\n'
                '  "next_steps": ["下一步动作"]\n'
                "}\n\n"
                "要求：内容使用简体中文；建议必须可执行；不要假装知道平台后台真实数据；"
                "如果数据不足，要明确用小预算测试。\n\n"
                f"商品上下文 JSON：{_ad_context_payload(product)}"
            ),
        },
    ]


def _ad_context_payload(product: Product) -> str:
    # Prompt 只喂入本系统已有的商品、诊断、素材和经营记录，不拼接平台账号密钥或未授权抓取数据。
    """投放上下文载荷，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    latest_diagnosis = product.diagnoses[0] if product.diagnoses else None
    records = sorted(product.performance_records, key=lambda item: item.created_at, reverse=True)[:5]
    plans = sorted(product.creative_plans, key=lambda item: item.created_at, reverse=True)[:8]
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
        "diagnosis": None
        if latest_diagnosis is None
        else {
            "positioning": latest_diagnosis.positioning,
            "price_band": latest_diagnosis.price_band,
            "pain_points": latest_diagnosis.pain_points,
            "risks": latest_diagnosis.risks,
            "recommendations": latest_diagnosis.recommendations,
        },
        "creative_plans": [
            {
                "type": plan.type,
                "title": plan.title,
                "status": plan.status,
                "rationale": plan.rationale,
                "content": plan.content,
            }
            for plan in plans
        ],
        "performance_records": [
            {
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
            }
            for record in records
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _latest_record(records: list[PerformanceRecord]) -> PerformanceRecord | None:
    """最新记录，统一主流程中的格式、默认值和异常边界。"""
    if not records:
        return None
    return max(records, key=lambda record: (record.period_end, record.created_at))


def _objective(record: PerformanceRecord | None) -> str:
    """目标，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if record is None:
        return "冷启动验证：用小预算确认人群、卖点和素材方向。"
    if record.roi is not None and record.roi >= Decimal("2.0000"):
        return "小步放量：保持 ROI 稳定的前提下扩大优质素材预算。"
    if record.ctr is not None and record.ctr < Decimal("0.0200"):
        return "提升点击：优先测试首屏卖点和画面吸引力。"
    if record.conversion_rate is not None and record.conversion_rate < Decimal("0.0200"):
        return "提升转化：检查素材承诺、详情页证明和价格权益匹配度。"
    return "持续测试：保留当前有效素材，同时补充新卖点版本。"


def _budget(record: PerformanceRecord | None) -> str:
    """预算，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if record is None or record.spend is None:
        return "先用小预算测试，每个素材日预算控制在可承受试错范围内。"
    if record.roi is not None and record.roi >= Decimal("2.0000"):
        return f"可在当前日消耗基础上小步增加 20%-30%，参考最近消耗 {record.spend}。"
    return f"暂不明显放量，参考最近消耗 {record.spend} 做平行素材测试。"


def _bid_strategy(record: PerformanceRecord | None) -> list[str]:
    """bid策略，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if record is None:
        return ["冷启动先选择点击或成交浅层目标，等有样本后再切深度转化。", "每个测试组保持同一出价策略，避免变量混杂。"]
    if record.roi is not None and record.roi >= Decimal("2.0000"):
        return ["优先复制高 ROI 素材结构并小步加预算。", "观察加预算后的点击成本和转化成本是否同步恶化。"]
    return ["先控预算测素材，不建议直接提高出价抢量。", "如果 CTR 高但转化低，优先优化承接页而不是继续抬价。"]


def _plan_direction(content: dict) -> str:
    """方案direction，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    for key in ("visual_focus", "layout", "angle", "hook"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "围绕核心卖点制作清晰、可对比、易理解的首屏素材。"
