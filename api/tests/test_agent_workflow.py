from collections import Counter
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents.contracts import HarnessEvent, ModelUsage, ProductContext
from app.agents.definitions import HUMAN_REVIEW_GATE, require_tool_permission
from app.agents.evaluation import load_fixed_eval_cases
from app.agents.graph import AgentWorkflowDependencies, build_product_operation_graph
from app.agents.harness import AgentBudgetExceededError, redact_snapshot, remaining_model_tokens
from app.agents.specialists import ModelCallResult


class FakeCompletionClient:
    def __init__(
        self,
        *,
        duplicate_first_angles: bool = False,
        always_duplicate_angles: bool = False,
    ) -> None:
        """初始化 FakeCompletionClient 的依赖与运行状态，避免执行阶段临时拼装共享资源。"""
        self.duplicate_first_angles = duplicate_first_angles
        self.always_duplicate_angles = always_duplicate_angles
        self.calls: list[str] = []

    def __call__(
        self,
        *,
        agent_name: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> ModelCallResult:
        """执行 FakeCompletionClient 封装的调用协议，并返回本次处理结果。"""
        # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
        self.calls.append(agent_name)
        if agent_name == "diagnosis_agent":
            return ModelCallResult(
                output=_diagnosis_output(),
                model="fake-diagnosis",
                usage=ModelUsage(input_tokens=100, output_tokens=80, total_tokens=180, calls=1),
            )
        creative_call_count = self.calls.count("creative_strategy_agent")
        duplicate_angles = self.always_duplicate_angles or (
            self.duplicate_first_angles and creative_call_count == 1
        )
        return ModelCallResult(
            output={"plans": _creative_plans(duplicate_angles=duplicate_angles)},
            model="fake-creative",
            usage=ModelUsage(input_tokens=120, output_tokens=160, total_tokens=280, calls=1),
        )


def test_workflow_pauses_for_human_review_with_structured_draft() -> None:
    """验证“工作流pausesfor人工审核withstructureddraft”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    graph, config, client, events, finalized = _graph()

    graph.invoke(_initial_state(), config=config)
    snapshot = graph.get_state(config)

    assert snapshot.next == (HUMAN_REVIEW_GATE,)
    assert snapshot.values["revision_count"] == 0
    assert len(snapshot.values["creative_plans"]) == 4
    assert snapshot.values["quality_report"]["passed"] is True
    assert Counter(client.calls) == {"diagnosis_agent": 1, "creative_strategy_agent": 1}
    assert not any(event.event_type == "revision_requested" for event in events)
    assert finalized == []


def test_quality_failure_is_revised_once_then_passes() -> None:
    """验证首次质检失败只触发一次返修，返修通过后进入人工审核。"""
    # 先制造首轮创意重复，再检查返修次数、模型调用次数和返修事件是否同时符合上限。
    graph, config, client, events, _ = _graph(duplicate_first_angles=True)

    graph.invoke(_initial_state(), config=config)
    snapshot = graph.get_state(config)

    assert snapshot.next == (HUMAN_REVIEW_GATE,)
    assert snapshot.values["revision_count"] == 1
    assert snapshot.values["quality_report"]["passed"] is True
    assert Counter(client.calls) == {"diagnosis_agent": 2, "creative_strategy_agent": 2}
    assert any(event.event_type == "revision_requested" for event in events)


def test_quality_failure_triggers_only_one_revision() -> None:
    """验证“质量failuretriggersonlyone返修”场景，确保重构后仍满足预期业务与安全边界。"""
    graph, config, client, _, _ = _graph(always_duplicate_angles=True)

    graph.invoke(_initial_state(), config=config)
    snapshot = graph.get_state(config)

    assert snapshot.next == (HUMAN_REVIEW_GATE,)
    assert snapshot.values["revision_count"] == 1
    assert snapshot.values["quality_report"]["passed"] is False
    assert Counter(client.calls) == {"diagnosis_agent": 2, "creative_strategy_agent": 2}


def test_approve_resume_completes_workflow() -> None:
    """验证人工批准后从 checkpoint 恢复，并只持久化被批准的结构化产物。"""
    # 首次调用停在审批节点，第二次用 Command.resume 恢复，避免把审批误写成新任务。
    graph, config, _, _, finalized = _graph()
    graph.invoke(_initial_state(), config=config)

    graph.invoke(Command(resume={"decision": "approve"}), config=config)
    snapshot = graph.get_state(config)

    assert snapshot.next == ()
    assert snapshot.values["final_status"] == "completed"
    assert finalized[0]["decision"] == "approve"
    assert finalized[0]["approved_output"]["diagnosis"]["positioning"] == "适合通勤人群的控油底妆"


def test_edit_and_approve_uses_human_edited_output() -> None:
    """验证“editandapproveuses人工编辑后输出”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    graph, config, _, _, finalized = _graph()
    graph.invoke(_initial_state(), config=config)
    draft = graph.get_state(config).values
    edited_output = {
        "diagnosis": {**draft["diagnosis"], "positioning": "人工调整后的商品定位"},
        "creative_plans": draft["creative_plans"],
    }

    graph.invoke(
        Command(
            resume={
                "decision": "edit_and_approve",
                "edited_output": edited_output,
                "note": "运营已校正文案",
            }
        ),
        config=config,
    )

    assert finalized[0]["approved_output"]["diagnosis"]["positioning"] == "人工调整后的商品定位"


def test_reject_resume_does_not_persist_draft() -> None:
    """验证“rejectresumedoesnot持久化draft”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    graph, config, _, _, finalized = _graph()
    graph.invoke(_initial_state(), config=config)

    graph.invoke(
        Command(resume={"decision": "reject", "note": "商品资料不足"}),
        config=config,
    )
    snapshot = graph.get_state(config)

    assert snapshot.values["final_status"] == "rejected"
    assert finalized == [
        {"decision": "reject", "approved_output": None, "note": "商品资料不足"}
    ]


def test_harness_redacts_secrets_and_enforces_budget() -> None:
    """验证“harnessredactssecretsandenforces预算”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    snapshot = redact_snapshot(
        {
            "product_id": 1,
            "authorization": "Bearer secret",
            "nested": {"api_key": "secret-key", "safe": "kept"},
            "usage": {"total_tokens": 12},
        }
    )

    assert snapshot == {
        "product_id": 1,
        "authorization": "[redacted]",
        "nested": {"api_key": "[redacted]", "safe": "kept"},
        "usage": {"total_tokens": 12},
    }
    assert remaining_model_tokens(
        {"max_total_tokens": 1000},
        {"total_tokens": 900},
        300,
    ) == 100
    with pytest.raises(AgentBudgetExceededError):
        remaining_model_tokens({"max_total_tokens": 1000}, {"total_tokens": 1000}, 300)


def test_harness_rejects_tool_outside_agent_allowlist() -> None:
    """验证“harnessrejects工具outsideAgent白名单”场景，确保重构后仍满足预期业务与安全边界。"""
    with pytest.raises(RuntimeError, match="not allowed"):
        require_tool_permission("diagnosis_agent", "agent_output.persist")


def test_fixed_eval_manifest_has_at_least_six_versioned_cases() -> None:
    """验证“固定评测清单hasatleastsixversioned用例”场景，确保重构后仍满足预期业务与安全边界。"""
    cases = load_fixed_eval_cases()

    assert len(cases) >= 6
    assert len({case.case_id for case in cases}) == len(cases)
    assert {case.category for case in cases} >= {"workflow", "quality", "human_review", "policy"}


def _graph(
    *,
    duplicate_first_angles: bool = False,
    always_duplicate_angles: bool = False,
):
    """构造或执行测试所需的工作流图，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    events: list[HarnessEvent] = []
    finalized: list[dict[str, Any]] = []
    client = FakeCompletionClient(
        duplicate_first_angles=duplicate_first_angles,
        always_duplicate_angles=always_duplicate_angles,
    )

    def finalize(run_id, review, approved_output):
        """构造或执行测试所需的完成落库，让测试数据、依赖替身与断言保持集中。"""
        # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
        finalized.append(
            {
                "decision": review.decision,
                "approved_output": (
                    approved_output.model_dump(mode="json")
                    if approved_output is not None
                    else None
                ),
                "note": review.note,
            }
        )
        return approved_output.model_dump(mode="json") if approved_output is not None else {}

    deps = AgentWorkflowDependencies(
        load_product_context=lambda product_id: _product_context(product_id),
        completion_client=client,
        record_event=lambda run_id, event: events.append(event),
        finalize_run=finalize,
    )
    graph = build_product_operation_graph(checkpointer=InMemorySaver(), deps=deps)
    config = {"configurable": {"thread_id": "fixed-eval-thread"}, "recursion_limit": 24}
    return graph, config, client, events, finalized


def _initial_state() -> dict[str, Any]:
    """构造或执行测试所需的initial状态，让测试数据、依赖替身与断言保持集中。"""
    return {
        "run_id": 1,
        "product_id": 10,
        "revision_count": 0,
        "max_revisions": 1,
        "budget": {"max_total_tokens": 5000},
        "usage": {},
    }


def _product_context(product_id: int) -> ProductContext:
    """构造或执行测试所需的商品上下文，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    return ProductContext(
        product_id=product_id,
        name="控油气垫",
        platform="douyin",
        category="美妆",
        price="129.00",
        cost="49.00",
        target_audience="通勤人群",
        selling_points=["轻薄", "控油", "持妆"],
        competitors=[
            {
                "name": "竞品 A",
                "platform": "tmall",
                "price": "139.00",
                "selling_points": ["持妆"],
            }
        ],
    )


def _diagnosis_output() -> dict[str, Any]:
    """构造或执行测试所需的商品诊断输出，让测试数据、依赖替身与断言保持集中。"""
    return {
        "positioning": "适合通勤人群的控油底妆",
        "price_band": "位于竞品中位价格带",
        "audience_insights": ["通勤时间长", "关注持妆稳定"],
        "pain_points": ["易出油", "补妆麻烦"],
        "selling_point_analysis": ["控油对应核心痛点", "轻薄降低使用负担"],
        "risks": ["需要真实持妆素材证明"],
        "recommendations": ["先测试控油场景主图", "再测试轻薄妆效主图"],
    }


def _creative_plans(*, duplicate_angles: bool) -> list[dict[str, Any]]:
    """构造或执行测试所需的创意plans，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    angles = ["通勤场景", "成分证明", "妆效对比", "价格价值"]
    if duplicate_angles:
        angles = ["通勤场景"] * 4
    return [
        {
            "title": f"方案 {index + 1}",
            "angle": angle,
            "layout": "商品居中，文案置顶，证明标签置底",
            "headline": f"通勤持妆方向 {index + 1}",
            "sub_headline": "轻薄控油，具体效果以实际使用为准",
            "visual_focus": "展示商品主体与通勤补妆场景",
            "proof_points": ["用户授权实拍", "产品参数"],
            "suitable_audience": "通勤人群",
            "image_prompt": "干净明亮的电商主图，气垫商品主体，通勤场景",
        }
        for index, angle in enumerate(angles)
    ]
