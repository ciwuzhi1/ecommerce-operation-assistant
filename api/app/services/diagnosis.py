import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.models import Product
from app.services.llm import (
    LLMNotConfiguredError,
    LLMResponseError,
    create_json_chat_completion,
)


class ProductDiagnosisOutput(BaseModel):
    positioning: str = Field(min_length=1)
    price_band: str = Field(min_length=1)
    audience_insights: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    selling_point_analysis: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


def generate_product_diagnosis(product: Product) -> dict[str, Any]:
    """生成商品商品诊断；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    try:
        return generate_llm_diagnosis(product)
    except (LLMNotConfiguredError, LLMResponseError, ValidationError) as exc:
        # 诊断是素材和投放建议的上游，模型不可用时用规则版保持单品运营链路可继续。
        fallback = generate_rule_based_diagnosis(product)
        fallback["raw_output"]["fallback_reason"] = str(exc)
        return fallback


def generate_llm_diagnosis(product: Product) -> dict[str, Any]:
    """生成llm商品诊断；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed, raw_response = create_json_chat_completion(
        _build_diagnosis_messages(product),
        max_tokens=2200,
        temperature=0.25,
    )
    diagnosis = ProductDiagnosisOutput.model_validate(parsed)

    return {
        "source": "llm",
        **diagnosis.model_dump(),
        "raw_output": {
            "provider": "deepseek",
            "model": raw_response.get("model"),
            "usage": raw_response.get("usage", {}),
            "llm_output": parsed,
        },
    }


def _build_diagnosis_messages(product: Product) -> list[dict[str, str]]:
    """构建商品诊断消息，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    return [
        {
            "role": "system",
            "content": (
                "你是一个资深电商运营策略助手，擅长商品定位、竞品拆解、素材测试和投放复盘。"
                "你必须只输出合法 json，不要输出 markdown，不要输出解释性前后缀。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于以下商品和竞品信息，生成电商运营诊断。输出 json 必须严格符合示例结构：\n"
                "{\n"
                '  "positioning": "一句话定位建议",\n'
                '  "price_band": "价格带判断",\n'
                '  "audience_insights": ["人群洞察1", "人群洞察2"],\n'
                '  "pain_points": ["痛点1", "痛点2"],\n'
                '  "selling_point_analysis": ["卖点分析1", "卖点分析2"],\n'
                '  "risks": ["风险1", "风险2"],\n'
                '  "recommendations": ["下一步动作1", "下一步动作2"]\n'
                "}\n\n"
                "要求：\n"
                "- 所有内容使用简体中文。\n"
                "- 建议要可执行，适合运营人员马上拿去改主图、短视频脚本或投放测试。\n"
                "- 如果信息不足，请明确指出需要补充哪些数据。\n"
                "- 每个数组建议输出 2 到 5 条。\n\n"
                f"商品信息 json：{_product_payload(product)}"
            ),
        },
    ]


def _product_payload(product: Product) -> str:
    # 诊断只使用系统内已有商品与竞品资料，不假设平台后台真实成交、评价或库存数据。
    """商品载荷，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    payload = {
        "name": product.name,
        "platform": product.platform,
        "category": product.category,
        "price": str(product.price) if product.price is not None else None,
        "cost": str(product.cost) if product.cost is not None else None,
        "target_audience": product.target_audience,
        "selling_points": product.selling_points,
        "product_url": product.product_url,
        "competitors": [
            {
                "name": competitor.name,
                "platform": competitor.platform,
                "price": str(competitor.price) if competitor.price is not None else None,
                "sales_hint": competitor.sales_hint,
                "title": competitor.title,
                "selling_points": competitor.selling_points,
                "review_keywords": competitor.review_keywords,
            }
            for competitor in product.competitors
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def generate_rule_based_diagnosis(product: Product) -> dict:
    # 规则诊断只做启发式判断，重点提示缺口和下一步测试方向，不替代真实经营分析。
    """生成rulebased商品诊断；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    competitor_prices = [
        competitor.price for competitor in product.competitors if competitor.price is not None
    ]
    price_band = _price_band(product.price, competitor_prices)
    competitor_points = _flatten([competitor.selling_points for competitor in product.competitors])
    overlap_points = sorted(set(product.selling_points).intersection(competitor_points))
    differentiated_points = [
        point for point in product.selling_points if point not in set(competitor_points)
    ]

    positioning = _positioning(product, differentiated_points, overlap_points)
    audience_insights = _audience_insights(product)
    pain_points = _pain_points(product, competitor_points)
    selling_point_analysis = _selling_point_analysis(
        product.selling_points,
        differentiated_points,
        overlap_points,
    )
    risks = _risks(product, competitor_prices, overlap_points)
    recommendations = _recommendations(product, competitor_prices, differentiated_points)

    return {
        "source": "rules",
        "positioning": positioning,
        "price_band": price_band,
        "audience_insights": audience_insights,
        "pain_points": pain_points,
        "selling_point_analysis": selling_point_analysis,
        "risks": risks,
        "recommendations": recommendations,
        "raw_output": {
            "competitor_count": len(product.competitors),
            "competitor_prices": [str(price) for price in competitor_prices],
            "overlap_points": overlap_points,
            "differentiated_points": differentiated_points,
        },
    }


def _price_band(product_price: Decimal | None, competitor_prices: list[Decimal]) -> str:
    """价格band，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if product_price is None:
        return "商品售价未录入，暂时无法判断价格带。"

    if not competitor_prices:
        return f"当前商品售价为 {product_price}，还缺少竞品价格样本。"

    min_price = min(competitor_prices)
    max_price = max(competitor_prices)
    avg_price = sum(competitor_prices, Decimal("0")) / Decimal(len(competitor_prices))

    if product_price < min_price:
        position = "低于现有竞品样本，适合测试性价比或引流定位"
    elif product_price > max_price:
        position = "高于现有竞品样本，需要更强卖点证明和信任背书"
    elif product_price > avg_price:
        position = "处于偏高价格带，需要突出差异化价值"
    else:
        position = "处于中低价格带，可优先测试转化效率"

    return f"{position}；竞品样本价格区间为 {min_price}-{max_price}，均价约 {avg_price:.2f}。"


def _positioning(
    product: Product,
    differentiated_points: list[str],
    overlap_points: list[str],
) -> str:
    """positioning，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    audience = product.target_audience or "目标人群未明确"
    category = product.category or "当前类目"

    if differentiated_points:
        point_text = "、".join(differentiated_points[:3])
        return f"{category}商品可围绕“{point_text}”做差异化表达，优先面向{audience}。"

    if overlap_points:
        point_text = "、".join(overlap_points[:3])
        return f"{category}商品目前与竞品共同卖点集中在“{point_text}”，需要补充更具体的使用场景或信任证明。"

    return f"{category}商品信息还偏基础，建议先明确核心卖点和目标人群，再做素材测试。"


def _audience_insights(product: Product) -> list[str]:
    """根据商品目标人群生成可执行洞察；缺失人群时返回补录建议而不是臆测。"""
    # 只使用用户录入的人群事实；没有事实时明确提示补充，不让规则兜底伪造画像。
    audience = product.target_audience
    if audience:
        return [
            f"当前目标人群为“{audience}”，素材表达应直接对应其高频场景。",
            "建议把人群从宽泛标签细化到使用场景、购买动机和决策顾虑。",
        ]
    return [
        "目标人群尚未明确，后续主图和视频脚本容易变得泛泛。",
        "建议补充年龄段、使用场景、购买理由和价格敏感度。",
    ]


def _pain_points(product: Product, competitor_points: list[str]) -> list[str]:
    """painpoints，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    points = list(product.selling_points) + competitor_points
    if not points:
        return [
            "缺少卖点和竞品关键词，暂时无法稳定推断用户痛点。",
            "建议从评价区补充差评、追评和问大家中的真实顾虑。",
        ]

    pain_points = []
    joined = " ".join(points)
    if any(word in joined for word in ["便携", "轻薄", "小巧"]):
        pain_points.append("用户可能在意携带方便、通勤补用或使用负担。")
    if any(word in joined for word in ["控油", "持妆", "不卡粉"]):
        pain_points.append("用户可能在意使用效果稳定，以及长时间使用后的表现。")
    if any(word in joined for word in ["低糖", "低脂", "健康"]):
        pain_points.append("用户可能在意健康负担、成分安全和长期复购理由。")
    if any(word in joined for word in ["低价", "大规格", "买一送一"]):
        pain_points.append("用户可能在意价格是否划算，以及规格和赠品带来的确定收益。")

    if pain_points:
        return pain_points

    return [
        "用户痛点需要通过评论、客服咨询和竞品标题进一步提炼。",
        "建议把卖点改写成用户能感知的结果，而不只是商品属性。",
    ]


def _selling_point_analysis(
    selling_points: list[str],
    differentiated_points: list[str],
    overlap_points: list[str],
) -> list[str]:
    """sellingpointanalysis，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if not selling_points:
        return ["商品核心卖点缺失，建议先补 3-5 个可被画面证明的卖点。"]

    analysis = [f"当前已录入 {len(selling_points)} 个卖点，可用于生成素材测试方向。"]
    if differentiated_points:
        analysis.append(f"差异化卖点包括：{'、'.join(differentiated_points[:5])}。")
    if overlap_points:
        analysis.append(f"与竞品重合卖点包括：{'、'.join(overlap_points[:5])}，需要更具体的证明方式。")
    return analysis


def _risks(
    product: Product,
    competitor_prices: list[Decimal],
    overlap_points: list[str],
) -> list[str]:
    """risks，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    risks = []
    if len(product.competitors) < 3:
        risks.append("竞品样本少于 3 个，价格带和卖点判断还不够稳定。")
    if product.price is None:
        risks.append("商品售价缺失，无法判断价格竞争力。")
    if product.price is not None and competitor_prices and product.price > max(competitor_prices):
        risks.append("当前售价高于竞品样本最高价，需要加强利益点、品牌信任或赠品机制。")
    if overlap_points and len(overlap_points) >= len(product.selling_points):
        risks.append("卖点与竞品重合度较高，素材容易陷入同质化。")
    if not product.target_audience:
        risks.append("目标人群缺失，投放和内容测试会缺少方向。")
    return risks or ["暂无明显结构性风险，下一步重点是用素材测试验证判断。"]


def _recommendations(
    product: Product,
    competitor_prices: list[Decimal],
    differentiated_points: list[str],
) -> list[str]:
    """recommendations，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    recommendations = []
    if len(product.competitors) < 3:
        recommendations.append("继续补充至少 3 个竞品，覆盖同价位爆款、低价引流款和高价标杆款。")
    if differentiated_points:
        recommendations.append(f"优先用“{differentiated_points[0]}”做一版主图首屏测试。")
    elif product.selling_points:
        recommendations.append(f"先把“{product.selling_points[0]}”改写成用户结果，再做主图和短视频钩子。")
    if competitor_prices and product.price is not None:
        min_price = min(competitor_prices)
        if product.price > min_price:
            recommendations.append("投放素材中避免只打低价，应增加效果证明、场景证明或赠品机制。")
    recommendations.append("下一步生成 3 个主图方向和 3 条短视频脚本，用点击率和转化率做判断。")
    return recommendations


def _flatten(values: list[list[str]]) -> list[str]:
    """展平，统一主流程中的格式、默认值和异常边界。"""
    return [item for sublist in values for item in sublist]
