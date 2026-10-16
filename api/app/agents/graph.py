from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from opentelemetry import trace

from app.agents.contracts import (
    AgentDraftOutput,
    AgentWorkflowState,
    CreativePlanDraft,
    DiagnosisDraft,
    HarnessEvent,
    ProductContext,
    QualityReport,
    ReviewResumePayload,
)
from app.agents.definitions import (
    CREATIVE_STRATEGY_AGENT,
    DIAGNOSIS_AGENT,
    FINALIZE_NODE,
    HUMAN_REVIEW_GATE,
    PRODUCT_CONTEXT_AGENT,
    QUALITY_REVIEW_AGENT,
    require_tool_permission,
)
from app.agents.harness import merge_model_usage, redact_snapshot, remaining_model_tokens
from app.agents.specialists import (
    CompletionClient,
    CreativeStrategyAgent,
    DiagnosisAgent,
    QualityReviewAgent,
)


ProductContextLoader = Callable[[int], ProductContext]
EventRecorder = Callable[[int, HarnessEvent], None]
WorkflowFinalizer = Callable[[int, ReviewResumePayload, AgentDraftOutput | None], dict[str, Any]]


@dataclass(frozen=True)
class AgentWorkflowDependencies:
    load_product_context: ProductContextLoader
    completion_client: CompletionClient
    record_event: EventRecorder
    finalize_run: WorkflowFinalizer


def build_product_operation_graph(*, checkpointer: Any, deps: AgentWorkflowDependencies):
    """构建商品操作工作流图，注册节点、条件路由、人审中断和 checkpoint，返回可执行编排图。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    diagnosis_agent = DiagnosisAgent(deps.completion_client)
    creative_agent = CreativeStrategyAgent(deps.completion_client)
    quality_agent = QualityReviewAgent()

    def product_context_node(state: AgentWorkflowState) -> dict[str, Any]:
        """执行商品上下文节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        require_tool_permission(PRODUCT_CONTEXT_AGENT, "product_context.read")

        def execute() -> dict[str, Any]:
            """执行商品上下文节点的受观测业务步骤，并把结构化增量交回图节点。"""
            context = deps.load_product_context(state["product_id"])
            return {"context": context.model_dump(mode="json")}

        return _run_observed(
            state,
            deps,
            agent_name=PRODUCT_CONTEXT_AGENT,
            operation_name="product_context.read",
            input_snapshot={"product_id": state["product_id"]},
            execute=execute,
        )

    def diagnosis_node(state: AgentWorkflowState) -> dict[str, Any]:
        """执行商品诊断节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        require_tool_permission(DIAGNOSIS_AGENT, "model.complete")
        context = ProductContext.model_validate(state["context"])
        max_tokens = remaining_model_tokens(state.get("budget"), state.get("usage"), 2200)

        def execute() -> dict[str, Any]:
            """执行商品诊断节点的受观测业务步骤，并把结构化增量交回图节点。"""
            result = diagnosis_agent.run(
                context,
                max_tokens=max_tokens,
                revision_feedback=state.get("revision_feedback"),
            )
            return {
                "diagnosis": result.output,
                "usage": merge_model_usage(state.get("usage"), result.usage),
            }

        return _run_observed(
            state,
            deps,
            agent_name=DIAGNOSIS_AGENT,
            operation_name="model.complete",
            input_snapshot={
                "product_id": state["product_id"],
                "revision_count": state.get("revision_count", 0),
            },
            execute=execute,
        )

    def creative_strategy_node(state: AgentWorkflowState) -> dict[str, Any]:
        """执行创意策略节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        require_tool_permission(CREATIVE_STRATEGY_AGENT, "model.complete")
        context = ProductContext.model_validate(state["context"])
        diagnosis = DiagnosisDraft.model_validate(state["diagnosis"])
        max_tokens = remaining_model_tokens(state.get("budget"), state.get("usage"), 3000)

        def execute() -> dict[str, Any]:
            """执行创意策略节点的受观测业务步骤，并把结构化增量交回图节点。"""
            # 创意 Agent 只消费已校验的商品上下文与诊断草稿，模型用量随后合并回共享状态。
            result = creative_agent.run(
                context,
                diagnosis,
                max_tokens=max_tokens,
                revision_feedback=state.get("revision_feedback"),
            )
            return {
                "creative_plans": result.output,
                "usage": merge_model_usage(state.get("usage"), result.usage),
            }

        return _run_observed(
            state,
            deps,
            agent_name=CREATIVE_STRATEGY_AGENT,
            operation_name="model.complete",
            input_snapshot={
                "product_id": state["product_id"],
                "revision_count": state.get("revision_count", 0),
            },
            execute=execute,
        )

    def quality_review_node(state: AgentWorkflowState) -> dict[str, Any]:
        """执行质量审核节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        diagnosis = DiagnosisDraft.model_validate(state["diagnosis"])
        creative_plans = [
            CreativePlanDraft.model_validate(item) for item in state["creative_plans"]
        ]

        def execute() -> dict[str, Any]:
            """执行质量审核节点的受观测业务步骤，并把结构化增量交回图节点。"""
            report = quality_agent.run(diagnosis, creative_plans)
            return {"quality_report": report.model_dump(mode="json")}

        return _run_observed(
            state,
            deps,
            agent_name=QUALITY_REVIEW_AGENT,
            operation_name="quality_rules.evaluate",
            input_snapshot={
                "creative_plan_count": len(creative_plans),
                "revision_count": state.get("revision_count", 0),
            },
            execute=execute,
        )

    def prepare_revision_node(state: AgentWorkflowState) -> dict[str, Any]:
        """执行准备返修节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        report = QualityReport.model_validate(state["quality_report"])
        update = {
            "revision_count": state.get("revision_count", 0) + 1,
            "revision_feedback": [issue.model_dump(mode="json") for issue in report.issues],
        }
        deps.record_event(
            state["run_id"],
            HarnessEvent(
                event_type="revision_requested",
                agent_name=QUALITY_REVIEW_AGENT,
                operation_name="workflow.route",
                status="completed",
                message="质量审核触发一次受控返修。",
                output_snapshot=redact_snapshot(update),
            ),
        )
        return update

    def human_review_node(state: AgentWorkflowState) -> dict[str, Any]:
        """执行人工审核节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        draft = _draft_from_state(state)
        # interrupt 之前不能产生副作用，否则恢复时节点从头执行会重复写入。
        resume_value = interrupt(
            {
                "run_id": state["run_id"],
                "draft_output": draft.model_dump(mode="json"),
                "quality_report": state["quality_report"],
                "revision_count": state.get("revision_count", 0),
            }
        )
        review = ReviewResumePayload.model_validate(resume_value)
        approved_output = None
        if review.decision == "approve":
            approved_output = draft
        elif review.decision == "edit_and_approve":
            approved_output = review.edited_output

        deps.record_event(
            state["run_id"],
            HarnessEvent(
                event_type="human_review_received",
                agent_name=HUMAN_REVIEW_GATE,
                operation_name="interrupt.resume",
                status="completed",
                message=f"收到人工审核决定：{review.decision}",
                input_snapshot={"decision": review.decision, "note": review.note},
            ),
        )
        return {
            "review": review.model_dump(mode="json"),
            "approved_output": (
                approved_output.model_dump(mode="json") if approved_output is not None else {}
            ),
        }

    def finalize_node(state: AgentWorkflowState) -> dict[str, Any]:
        """执行完成落库节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        require_tool_permission(FINALIZE_NODE, "agent_output.persist")
        review = ReviewResumePayload.model_validate(state["review"])
        approved_output = None
        if review.decision != "reject":
            approved_output = AgentDraftOutput.model_validate(state["approved_output"])

        def execute() -> dict[str, Any]:
            """执行完成落库节点的受观测业务步骤，并把结构化增量交回图节点。"""
            final_output = deps.finalize_run(state["run_id"], review, approved_output)
            return {
                "final_output": final_output,
                "final_status": "rejected" if review.decision == "reject" else "completed",
            }

        return _run_observed(
            state,
            deps,
            agent_name=FINALIZE_NODE,
            operation_name="agent_output.persist",
            input_snapshot={"decision": review.decision},
            execute=execute,
        )

    graph = StateGraph(AgentWorkflowState)
    graph.add_node(PRODUCT_CONTEXT_AGENT, product_context_node)
    graph.add_node(DIAGNOSIS_AGENT, diagnosis_node)
    graph.add_node(CREATIVE_STRATEGY_AGENT, creative_strategy_node)
    graph.add_node(QUALITY_REVIEW_AGENT, quality_review_node)
    graph.add_node("prepare_revision", prepare_revision_node)
    graph.add_node(HUMAN_REVIEW_GATE, human_review_node)
    graph.add_node(FINALIZE_NODE, finalize_node)

    graph.add_edge(START, PRODUCT_CONTEXT_AGENT)
    graph.add_edge(PRODUCT_CONTEXT_AGENT, DIAGNOSIS_AGENT)
    graph.add_edge(DIAGNOSIS_AGENT, CREATIVE_STRATEGY_AGENT)
    graph.add_edge(CREATIVE_STRATEGY_AGENT, QUALITY_REVIEW_AGENT)
    graph.add_conditional_edges(
        QUALITY_REVIEW_AGENT,
        _quality_route,
        {"revise": "prepare_revision", "review": HUMAN_REVIEW_GATE},
    )
    graph.add_edge("prepare_revision", DIAGNOSIS_AGENT)
    graph.add_edge(HUMAN_REVIEW_GATE, FINALIZE_NODE)
    graph.add_edge(FINALIZE_NODE, END)
    return graph.compile(checkpointer=checkpointer)


def _quality_route(state: AgentWorkflowState) -> str:
    """质量路由，依据结构化状态选择下一个已注册节点，避免隐式或无界跳转。"""
    report = QualityReport.model_validate(state["quality_report"])
    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 1)
    if not report.passed and revision_count < max_revisions:
        return "revise"
    return "review"


def _draft_from_state(state: AgentWorkflowState) -> AgentDraftOutput:
    """draftfrom状态；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    return AgentDraftOutput(
        diagnosis=DiagnosisDraft.model_validate(state["diagnosis"]),
        creative_plans=[
            CreativePlanDraft.model_validate(item) for item in state["creative_plans"]
        ],
    )


def _run_observed(
    state: AgentWorkflowState,
    deps: AgentWorkflowDependencies,
    *,
    agent_name: str,
    operation_name: str,
    input_snapshot: dict[str, Any],
    execute: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """执行可观测；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    tracer = trace.get_tracer("ecommerce_operation.agent_runtime")
    started_at = perf_counter()
    with tracer.start_as_current_span(f"agent.{agent_name}.{operation_name}") as span:
        trace_id, span_id = _span_ids(span)
        deps.record_event(
            state["run_id"],
            HarnessEvent(
                event_type="agent_step_started",
                agent_name=agent_name,
                operation_name=operation_name,
                status="running",
                input_snapshot=redact_snapshot(input_snapshot),
                trace_id=trace_id,
                span_id=span_id,
            ),
        )
        try:
            output = execute()
        except Exception as exc:
            deps.record_event(
                state["run_id"],
                HarnessEvent(
                    event_type="agent_step_failed",
                    agent_name=agent_name,
                    operation_name=operation_name,
                    status="failed",
                    message=str(exc)[:1000],
                    metrics={"latency_ms": round((perf_counter() - started_at) * 1000, 2)},
                    trace_id=trace_id,
                    span_id=span_id,
                ),
            )
            raise
        deps.record_event(
            state["run_id"],
            HarnessEvent(
                event_type="agent_step_completed",
                agent_name=agent_name,
                operation_name=operation_name,
                status="completed",
                output_snapshot=redact_snapshot(output),
                metrics={"latency_ms": round((perf_counter() - started_at) * 1000, 2)},
                trace_id=trace_id,
                span_id=span_id,
            ),
        )
        return output


def _span_ids(span: Any) -> tuple[str | None, str | None]:
    """spanids；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    context = span.get_span_context()
    if not context.is_valid:
        return None, None
    return f"{context.trace_id:032x}", f"{context.span_id:016x}"
