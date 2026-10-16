from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompetitorContext(StrictModel):
    name: str
    platform: str | None = None
    price: str | None = None
    sales_hint: str | None = None
    title: str | None = None
    selling_points: list[str] = Field(default_factory=list)
    review_keywords: list[str] = Field(default_factory=list)


class ProductContext(StrictModel):
    product_id: int
    name: str
    platform: str
    category: str | None = None
    price: str | None = None
    cost: str | None = None
    target_audience: str | None = None
    selling_points: list[str] = Field(default_factory=list)
    product_url: str | None = None
    images: list[str] = Field(default_factory=list)
    competitors: list[CompetitorContext] = Field(default_factory=list)


class DiagnosisDraft(StrictModel):
    source: Literal["llm", "rules"]
    positioning: str = Field(min_length=1)
    price_band: str = Field(min_length=1)
    audience_insights: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    selling_point_analysis: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class CreativePlanDraft(StrictModel):
    title: str = Field(min_length=1)
    angle: str = Field(min_length=1)
    layout: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    sub_headline: str = Field(min_length=1)
    visual_focus: str = Field(min_length=1)
    proof_points: list[str] = Field(default_factory=list)
    suitable_audience: str = Field(min_length=1)
    image_prompt: str = Field(min_length=1)
    source: Literal["llm", "rules"]
    provenance: dict[str, Any] = Field(default_factory=dict)


class AgentDraftOutput(StrictModel):
    diagnosis: DiagnosisDraft
    creative_plans: list[CreativePlanDraft] = Field(min_length=3, max_length=6)


class QualityIssue(StrictModel):
    code: str
    severity: Literal["warning", "error"]
    message: str
    field: str | None = None


class QualityReport(StrictModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    issues: list[QualityIssue] = Field(default_factory=list)
    revision_recommended: bool = False
    checked_rules: list[str] = Field(default_factory=list)


class ModelUsage(StrictModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    calls: int = Field(default=0, ge=0)


class ReviewResumePayload(StrictModel):
    decision: Literal["approve", "edit_and_approve", "reject"]
    edited_output: AgentDraftOutput | None = None
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_edited_output(self) -> "ReviewResumePayload":
        """校验编辑后输出，保证 Agent 输入、草稿和审批恢复载荷满足可序列化合同。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        if self.decision == "edit_and_approve" and self.edited_output is None:
            raise ValueError("edit_and_approve requires edited_output")
        if self.decision != "edit_and_approve" and self.edited_output is not None:
            raise ValueError("edited_output is only allowed for edit_and_approve")
        return self


class HarnessEvent(StrictModel):
    event_type: str
    agent_name: str | None = None
    operation_name: str | None = None
    status: str | None = None
    message: str | None = None
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    output_snapshot: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None


class AgentWorkflowState(TypedDict, total=False):
    run_id: int
    product_id: int
    context: dict[str, Any]
    diagnosis: dict[str, Any]
    creative_plans: list[dict[str, Any]]
    quality_report: dict[str, Any]
    revision_feedback: list[dict[str, Any]]
    revision_count: int
    max_revisions: int
    budget: dict[str, Any]
    usage: dict[str, Any]
    review: dict[str, Any]
    approved_output: dict[str, Any]
    final_output: dict[str, Any]
    final_status: str
