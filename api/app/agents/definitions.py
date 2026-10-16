from typing import Final


WORKFLOW_KEY: Final = "product_operation"
WORKFLOW_VERSION: Final = "1.0.0"

PRODUCT_CONTEXT_AGENT: Final = "product_context_agent"
DIAGNOSIS_AGENT: Final = "diagnosis_agent"
CREATIVE_STRATEGY_AGENT: Final = "creative_strategy_agent"
QUALITY_REVIEW_AGENT: Final = "quality_review_agent"
HUMAN_REVIEW_GATE: Final = "human_review_gate"
FINALIZE_NODE: Final = "finalize_output"

AGENT_TOOL_ALLOWLIST: Final[dict[str, frozenset[str]]] = {
    PRODUCT_CONTEXT_AGENT: frozenset({"product_context.read"}),
    DIAGNOSIS_AGENT: frozenset({"model.complete"}),
    CREATIVE_STRATEGY_AGENT: frozenset({"model.complete"}),
    QUALITY_REVIEW_AGENT: frozenset(),
    HUMAN_REVIEW_GATE: frozenset(),
    FINALIZE_NODE: frozenset({"agent_output.persist"}),
}

VERSION_MANIFEST: Final = {
    "workflow": {"key": WORKFLOW_KEY, "version": WORKFLOW_VERSION},
    "agents": {
        PRODUCT_CONTEXT_AGENT: "1.0.0",
        DIAGNOSIS_AGENT: "1.0.0",
        CREATIVE_STRATEGY_AGENT: "1.0.0",
        QUALITY_REVIEW_AGENT: "1.0.0",
    },
    "prompts": {"diagnosis": "1.0.0", "creative_strategy": "1.0.0"},
    "policies": {"tool_allowlist": "1.0.0", "quality_rules": "1.0.0"},
}


class AgentPolicyError(RuntimeError):
    pass


def require_tool_permission(agent_name: str, tool_name: str) -> None:
    """校验并获取工具权限，只从版本化注册表解析职责、工具白名单和工作流定义。"""
    allowed_tools = AGENT_TOOL_ALLOWLIST.get(agent_name, frozenset())
    if tool_name not in allowed_tools:
        raise AgentPolicyError(f"Agent {agent_name} is not allowed to use tool {tool_name}")
