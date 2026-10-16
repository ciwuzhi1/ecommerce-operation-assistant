from dataclasses import dataclass
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.registry import QUALITY_COMPLIANCE_AGENT, WorkflowDefinition


class PlatformWorkflowState(TypedDict, total=False):
    run_id: int
    task_id: int
    workspace_id: int
    context_scope: dict[str, Any]
    context: dict[str, Any]
    agent_outputs: dict[str, Any]
    quality_report: dict[str, Any]
    approval: dict[str, Any]
    final_output: dict[str, Any]
    final_status: str
    # 各环节模型用量累计，终结时写入运行记录（PRD FR-33 / DesignSpec §8）
    usage: dict[str, Any]


@dataclass(frozen=True)
class PlatformWorkflowDependencies:
    load_context: Callable[[int], dict[str, Any]]
    # 返回（输出, 本次实际执行的操作名）
    run_specialist: Callable[[str, dict[str, Any], dict[str, Any]], tuple[dict[str, Any], str]]
    evaluate_quality: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
    finalize: Callable[[int, dict[str, Any], dict[str, Any]], dict[str, Any]]
    record_event: Callable[..., None]


# 用量累计时参与的字段；不同供应商字段名不一致，统一归一到这些键。
_USAGE_TOKEN_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")


def _extract_usage(output: dict[str, Any]) -> dict[str, Any]:
    """从环节输出中取出模型用量；没有模型调用时返回空字典。"""
    if not isinstance(output, dict):
        return {}
    raw = output.get("raw_output")
    if isinstance(raw, dict) and isinstance(raw.get("usage"), dict):
        return raw["usage"]
    if isinstance(output.get("usage"), dict):
        return output["usage"]
    return {}


def _accumulate_usage(total: dict[str, Any], addition: dict[str, Any]) -> dict[str, Any]:
    """把一次调用的用量并入累计值；token 类字段相加，其余保留最后一次的取值。"""
    if not addition:
        return total
    merged = dict(total)
    for key, value in addition.items():
        if key in _USAGE_TOKEN_KEYS and isinstance(value, int) and isinstance(merged.get(key), int):
            merged[key] = merged[key] + value
        else:
            merged[key] = value
    return merged


def build_platform_workflow_graph(
    *,
    workflow: WorkflowDefinition,
    checkpointer: Any,
    deps: PlatformWorkflowDependencies,
):
    """构建平台工作流工作流图，注册节点、条件路由、人审中断和 checkpoint，返回可执行编排图。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    def load_context_node(state: PlatformWorkflowState) -> dict[str, Any]:
        """执行加载上下文节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        context = deps.load_context(state["task_id"])
        deps.record_event(
            state["run_id"],
            "context_loaded",
            None,
            {"context": context},
            "workflow.load_context",
        )
        return {"context": context, "agent_outputs": {}}

    def specialist_node(agent_key: str):
        """执行领域 Agent节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        def execute(state: PlatformWorkflowState) -> dict[str, Any]:
            """执行领域 Agent节点的受观测业务步骤，并把结构化增量交回图节点。"""
            # 每个领域 Agent 只追加自己的输出键，保留前序结果供后续节点与质量门读取。
            outputs = dict(state.get("agent_outputs", {}))
            output, operation_name = deps.run_specialist(agent_key, state["context"], outputs)
            outputs[agent_key] = output
            deps.record_event(
                state["run_id"],
                "agent_step_completed",
                agent_key,
                {"output": output},
                operation_name,
            )
            # 用量按环节累加，终结时随运行记录落库。
            usage = _accumulate_usage(state.get("usage") or {}, _extract_usage(output))
            return {"agent_outputs": outputs, "usage": usage}

        return execute

    def quality_node(state: PlatformWorkflowState) -> dict[str, Any]:
        """执行质量节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        report = deps.evaluate_quality(state["context"], state.get("agent_outputs", {}))
        deps.record_event(
            state["run_id"],
            "quality_review_completed",
            QUALITY_COMPLIANCE_AGENT,
            {"quality_report": report},
            "workflow.quality_review",
        )
        return {"quality_report": report}

    def approval_node(state: PlatformWorkflowState) -> dict[str, Any]:
        """执行审批节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        # interrupt 把草稿和风险快照持久化到 checkpoint，审批后由同一 thread_id 恢复。
        decision = interrupt(
            {
                "action_key": "workflow.accept_result",
                "risk_level": workflow.default_risk_level.value,
                "workflow_key": workflow.key,
                "draft_output": state.get("agent_outputs", {}),
                "quality_report": state.get("quality_report", {}),
            }
        )
        return {"approval": decision}

    def finalize_node(state: PlatformWorkflowState) -> dict[str, Any]:
        """执行完成落库节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        outputs = state.get("agent_outputs", {})
        edited_output = state.get("approval", {}).get("edited_output")
        if isinstance(edited_output, dict):
            outputs = edited_output
            report = deps.evaluate_quality(state["context"], outputs)
            deps.record_event(
                state["run_id"],
                "edited_output_quality_review_completed",
                QUALITY_COMPLIANCE_AGENT,
                {"quality_report": report},
                "workflow.quality_review",
            )
            if report.get("passed") is not True:
                return {
                    "agent_outputs": outputs,
                    "quality_report": report,
                    "final_status": "quality_failed",
                }
        final_output = deps.finalize(state["run_id"], outputs, state.get("usage") or {})
        return {
            "agent_outputs": outputs,
            "final_output": final_output,
            "final_status": "completed",
        }

    def quality_failed_node(_state: PlatformWorkflowState) -> dict[str, Any]:
        """执行质量失败节点，从共享状态读取必要输入，并只返回当前节点负责的增量字段。"""
        return {"final_status": "quality_failed"}

    def route_after_quality(state: PlatformWorkflowState) -> str:
        """路由after质量，依据结构化状态选择下一个已注册节点，避免隐式或无界跳转。"""
        return "passed" if state.get("quality_report", {}).get("passed") is True else "failed"

    graph = StateGraph(PlatformWorkflowState)
    graph.add_node("load_context", load_context_node)
    graph.add_node("quality_compliance", quality_node)
    graph.add_node("approval_gate", approval_node)
    graph.add_node("finalize", finalize_node)
    graph.add_node("quality_failed", quality_failed_node)
    graph.add_edge(START, "load_context")

    previous_node = "load_context"
    for agent_key in workflow.agents:
        if agent_key == QUALITY_COMPLIANCE_AGENT:
            continue
        graph.add_node(agent_key, specialist_node(agent_key))
        graph.add_edge(previous_node, agent_key)
        previous_node = agent_key
    graph.add_edge(previous_node, "quality_compliance")
    if workflow.default_risk_level.value in {"R2", "R3"}:
        graph.add_conditional_edges(
            "quality_compliance",
            route_after_quality,
            {"passed": "approval_gate", "failed": "quality_failed"},
        )
        graph.add_edge("approval_gate", "finalize")
    else:
        graph.add_conditional_edges(
            "quality_compliance",
            route_after_quality,
            {"passed": "finalize", "failed": "quality_failed"},
        )
    graph.add_edge("finalize", END)
    graph.add_edge("quality_failed", END)
    return graph.compile(checkpointer=checkpointer)
