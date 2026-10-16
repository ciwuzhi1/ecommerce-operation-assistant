import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"


class FixedEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: Literal["workflow", "quality", "human_review", "policy"]
    description: str
    fake_model_profile: str
    resume_decision: Literal["approve", "edit_and_approve", "reject"] | None = None
    expected: dict[str, Any] = Field(default_factory=dict)


def load_fixed_eval_cases() -> list[FixedEvalCase]:
    """加载固定评测用例，返回带版本、工作流和结构化断言的固定评测用例。"""
    path = EVALS_DIR / "product_operation_cases.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [FixedEvalCase.model_validate(item) for item in payload]


class PlatformEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    workflow_key: str
    category: Literal["routing", "context", "policy", "quality", "resilience", "approval"]
    description: str
    expected: dict[str, Any] = Field(default_factory=dict)


PLATFORM_WORKFLOW_EXPECTATIONS = {
    "product_diagnosis_optimization": {"context": "product_id", "risk": "R2"},
    "creative_content_production": {"context": "product_id", "risk": "R1"},
    "competitor_continuous_monitoring": {"context": "product_id|store_id", "risk": "R1"},
    "growth_ad_experiment_loop": {"context": "product_id", "risk": "R2"},
    "periodic_performance_review": {"context": "product_id|store_id", "risk": "R1"},
    "inventory_operations": {"context": "product_id|store_id", "risk": "R1"},
    "store_portfolio_inspection": {"context": "store_id", "risk": "R1"},
}


def load_platform_eval_cases() -> list[PlatformEvalCase]:
    # 每个工作流固定覆盖路由、租户上下文、策略、质量、恢复和审批六类生产边界。
    """加载平台评测用例，返回带版本、工作流和结构化断言的固定评测用例。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    scenario_templates = (
        ("routing", "意图必须路由到已注册版本", {"registered_only": True}),
        ("context", "上下文必须属于当前 Workspace", {"cross_workspace_blocked": True}),
        ("policy", "Agent 只能调用工具白名单", {"tool_allowlist_enforced": True}),
        ("quality", "输出必须通过结构与禁止表达检查", {"quality_gate": True}),
        ("resilience", "重复投递和 Worker 中断不得重复副作用", {"idempotent": True}),
        ("approval", "风险级别必须匹配审批边界", {}),
    )
    cases = []
    for workflow_key, workflow_expected in PLATFORM_WORKFLOW_EXPECTATIONS.items():
        for category, description, expected in scenario_templates:
            cases.append(
                PlatformEvalCase(
                    case_id=f"{workflow_key}.{category}.v1",
                    workflow_key=workflow_key,
                    category=category,
                    description=description,
                    expected={**expected, **workflow_expected},
                )
            )
    return cases
