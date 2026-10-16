import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agents.contracts import (
    CreativePlanDraft,
    DiagnosisDraft,
    ModelUsage,
    ProductContext,
    QualityIssue,
    QualityReport,
)
from app.agents.harness import normalize_model_usage
from app.services.diagnosis import ProductDiagnosisOutput
from app.services.llm import (
    LLMNotConfiguredError,
    LLMResponseError,
    create_json_chat_completion,
)


class ModelCallResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: dict[str, Any]
    model: str | None = None
    usage: ModelUsage = Field(default_factory=ModelUsage)


class CompletionClient(Protocol):
    def __call__(
        self,
        *,
        agent_name: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> ModelCallResult:
        """执行 CompletionClient 封装的调用协议，并返回本次处理结果。"""
        ...


def default_completion_client(
    *,
    agent_name: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> ModelCallResult:
    """默认模型补全client，把领域输入转换为结构化候选结果，并保留规则兜底和模型用量。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    parsed, raw_response = create_json_chat_completion(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return ModelCallResult(
        output=parsed,
        model=raw_response.get("model"),
        usage=normalize_model_usage(raw_response.get("usage")),
    )


@dataclass(frozen=True)
class SpecialistResult:
    output: dict[str, Any] | list[dict[str, Any]]
    usage: ModelUsage


class DiagnosisAgent:
    def __init__(self, completion_client: CompletionClient) -> None:
        """初始化 DiagnosisAgent 的依赖与运行状态，避免执行阶段临时拼装共享资源。"""
        self.completion_client = completion_client

    def run(
        self,
        context: ProductContext,
        *,
        max_tokens: int,
        revision_feedback: list[dict[str, Any]] | None = None,
    ) -> SpecialistResult:
        """执行，把领域输入转换为结构化候选结果，并保留规则兜底和模型用量。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        try:
            result = self.completion_client(
                agent_name="diagnosis_agent",
                messages=_diagnosis_messages(context, revision_feedback or []),
                max_tokens=max_tokens,
                temperature=0.25,
            )
            validated = ProductDiagnosisOutput.model_validate(result.output)
            diagnosis = DiagnosisDraft(
                source="llm",
                **validated.model_dump(),
                provenance={"model": result.model},
            )
            return SpecialistResult(diagnosis.model_dump(), result.usage)
        except (LLMNotConfiguredError, LLMResponseError, ValidationError) as exc:
            fallback = _rule_based_diagnosis(context, fallback_reason=str(exc))
            return SpecialistResult(fallback.model_dump(), ModelUsage())


class _CreativePlansOutput(BaseModel):
    plans: list[dict[str, Any]] = Field(min_length=3, max_length=6)


class CreativeStrategyAgent:
    def __init__(self, completion_client: CompletionClient) -> None:
        """初始化 CreativeStrategyAgent 的依赖与运行状态，避免执行阶段临时拼装共享资源。"""
        self.completion_client = completion_client

    def run(
        self,
        context: ProductContext,
        diagnosis: DiagnosisDraft,
        *,
        max_tokens: int,
        revision_feedback: list[dict[str, Any]] | None = None,
    ) -> SpecialistResult:
        """执行，把领域输入转换为结构化候选结果，并保留规则兜底和模型用量。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        try:
            result = self.completion_client(
                agent_name="creative_strategy_agent",
                messages=_creative_messages(context, diagnosis, revision_feedback or []),
                max_tokens=max_tokens,
                temperature=0.35,
            )
            parsed = _CreativePlansOutput.model_validate(result.output)
            plans = [
                CreativePlanDraft(
                    **plan,
                    source="llm",
                    provenance={"model": result.model},
                ).model_dump()
                for plan in parsed.plans
            ]
            return SpecialistResult(plans, result.usage)
        except (LLMNotConfiguredError, LLMResponseError, ValidationError) as exc:
            plans = [
                plan.model_dump()
                for plan in _rule_based_creative_plans(
                    context,
                    diagnosis,
                    fallback_reason=str(exc),
                )
            ]
            return SpecialistResult(plans, ModelUsage())


class QualityReviewAgent:
    BANNED_CLAIMS = ("全网第一", "百分百", "100%有效", "绝对", "保证治愈", "永久")

    def run(
        self,
        diagnosis: DiagnosisDraft,
        creative_plans: list[CreativePlanDraft],
    ) -> QualityReport:
        """执行，把领域输入转换为结构化候选结果，并保留规则兜底和模型用量。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        issues: list[QualityIssue] = []
        if len(diagnosis.recommendations) < 2:
            issues.append(
                QualityIssue(
                    code="diagnosis.actions.insufficient",
                    severity="error",
                    field="diagnosis.recommendations",
                    message="诊断至少需要两条可执行建议。",
                )
            )
        if len(creative_plans) < 3:
            issues.append(
                QualityIssue(
                    code="creative.count.insufficient",
                    severity="error",
                    field="creative_plans",
                    message="至少需要三个可测试的创意方向。",
                )
            )

        angles = [plan.angle.strip().lower() for plan in creative_plans]
        if len(set(angles)) != len(angles):
            issues.append(
                QualityIssue(
                    code="creative.angle.duplicate",
                    severity="error",
                    field="creative_plans.angle",
                    message="创意测试角度存在重复，需要拉开差异。",
                )
            )

        for index, plan in enumerate(creative_plans):
            claim_text = " ".join([plan.headline, plan.sub_headline, plan.visual_focus])
            for banned_claim in self.BANNED_CLAIMS:
                if banned_claim.lower() in claim_text.lower():
                    issues.append(
                        QualityIssue(
                            code="creative.claim.prohibited",
                            severity="error",
                            field=f"creative_plans.{index}",
                            message=f"包含不可证明或绝对化表达：{banned_claim}",
                        )
                    )
            if len(plan.proof_points) < 1:
                issues.append(
                    QualityIssue(
                        code="creative.proof.missing",
                        severity="warning",
                        field=f"creative_plans.{index}.proof_points",
                        message="创意方向缺少证明点，人工审核时应补充。",
                    )
                )

        error_count = sum(issue.severity == "error" for issue in issues)
        warning_count = sum(issue.severity == "warning" for issue in issues)
        score = max(0, 100 - error_count * 20 - warning_count * 5)
        return QualityReport(
            passed=error_count == 0,
            score=score,
            issues=issues,
            revision_recommended=error_count > 0,
            checked_rules=[
                "diagnosis_actionability",
                "creative_count",
                "creative_angle_diversity",
                "prohibited_claims",
                "proof_points",
            ],
        )


def _diagnosis_messages(
    context: ProductContext,
    revision_feedback: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """商品诊断消息，把领域输入转换为结构化候选结果，并保留规则兜底和模型用量。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    return [
        {
            "role": "system",
            "content": (
                "你是商品运营 Agent 内部的诊断专家。只输出合法 JSON，不输出 Markdown；"
                "不得臆造销量、评价、库存或平台后台数据。"
            ),
        },
        {
            "role": "user",
            "content": (
                "根据商品上下文生成结构化诊断，字段必须为 positioning、price_band、"
                "audience_insights、pain_points、selling_point_analysis、risks、recommendations。"
                "数组各给出 2-5 条，建议必须可执行。\n"
                f"商品上下文：{context.model_dump_json()}\n"
                f"上一轮质量反馈：{json.dumps(revision_feedback, ensure_ascii=False)}"
            ),
        },
    ]


def _creative_messages(
    context: ProductContext,
    diagnosis: DiagnosisDraft,
    revision_feedback: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """创意消息，把领域输入转换为结构化候选结果，并保留规则兜底和模型用量。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    return [
        {
            "role": "system",
            "content": (
                "你是商品运营 Agent 内部的创意策略专家。只输出合法 JSON，不输出 Markdown；"
                "不得使用绝对化、医疗功效或无法证明的承诺。"
            ),
        },
        {
            "role": "user",
            "content": (
                "输出 plans 数组，包含 4 个明显不同的主图测试方向。每项字段必须为 title、"
                "angle、layout、headline、sub_headline、visual_focus、proof_points、"
                "suitable_audience、image_prompt。\n"
                f"商品上下文：{context.model_dump_json()}\n"
                f"诊断：{diagnosis.model_dump_json()}\n"
                f"上一轮质量反馈：{json.dumps(revision_feedback, ensure_ascii=False)}"
            ),
        },
    ]


def _rule_based_diagnosis(context: ProductContext, *, fallback_reason: str) -> DiagnosisDraft:
    """rulebased商品诊断，把领域输入转换为结构化候选结果，并保留规则兜底和模型用量。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    competitor_prices = [_decimal(item.price) for item in context.competitors]
    competitor_prices = [price for price in competitor_prices if price is not None]
    product_price = _decimal(context.price)
    if product_price is None:
        price_band = "商品售价未录入，暂时无法判断价格带。"
    elif not competitor_prices:
        price_band = f"当前商品售价为 {product_price}，还缺少竞品价格样本。"
    else:
        price_band = (
            f"当前售价 {product_price}；竞品样本区间为 "
            f"{min(competitor_prices)}-{max(competitor_prices)}。"
        )

    primary_point = context.selling_points[0] if context.selling_points else "核心使用价值"
    audience = context.target_audience or "目标人群"
    return DiagnosisDraft(
        source="rules",
        positioning=f"围绕“{primary_point}”建立差异化表达，优先面向{audience}。",
        price_band=price_band,
        audience_insights=[
            f"当前目标人群为“{audience}”，素材应对应具体使用场景。",
            "需要继续补充购买动机、决策顾虑和价格敏感度。",
        ],
        pain_points=[
            "用户需要快速理解商品能解决的具体问题。",
            "用户需要价格、效果或使用场景方面的可信证明。",
        ],
        selling_point_analysis=[
            f"优先把“{primary_point}”改写为用户可感知的结果。",
            "其余卖点应作为证明点，而不是堆叠在同一主文案中。",
        ],
        risks=[
            "规则诊断未使用平台后台经营数据，需要人工结合真实表现复核。",
        ],
        recommendations=[
            f"先用“{primary_point}”制作一个场景型主图方向。",
            "再制作对比型和证明型方向，用点击率与转化率验证。",
        ],
        provenance={"fallback_reason": fallback_reason[:500]},
    )


def _rule_based_creative_plans(
    context: ProductContext,
    diagnosis: DiagnosisDraft,
    *,
    fallback_reason: str,
) -> list[CreativePlanDraft]:
    """rulebased创意plans，把领域输入转换为结构化候选结果，并保留规则兜底和模型用量。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    focus_points = list(context.selling_points[:3])
    while len(focus_points) < 3:
        focus_points.append(["场景价值", "差异对比", "可信证明"][len(focus_points)])
    audience = context.target_audience or "目标用户"
    price_text = context.price or "当前售价"
    templates = [
        ("场景首屏", "场景需求", f"{focus_points[0]}，使用更轻松", "具体使用场景"),
        ("差异对比", "竞品差异", f"重点看{focus_points[1]}", "左右对比结构"),
        ("痛点结果", "痛点结果", f"想要{focus_points[0]}，先看这一款", "痛点到结果"),
        ("价值组合", "价格理由", f"{price_text} 看懂这组价值", "价格与权益组合"),
    ]
    return [
        CreativePlanDraft(
            title=title,
            angle=angle,
            layout="商品主体居中，主文案置顶，证明标签置于底部，保持移动端可读。",
            headline=headline,
            sub_headline=diagnosis.positioning,
            visual_focus=visual_focus,
            proof_points=focus_points[:2],
            suitable_audience=audience,
            image_prompt=f"电商主图，{context.name}，{visual_focus}，干净背景，清晰商品主体",
            source="rules",
            provenance={"fallback_reason": fallback_reason[:500]},
        )
        for title, angle, headline, visual_focus in templates
    ]


def _decimal(value: str | None) -> Decimal | None:
    """小数，把领域输入转换为结构化候选结果，并保留规则兜底和模型用量。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None
