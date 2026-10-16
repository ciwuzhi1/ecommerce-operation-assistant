from dataclasses import dataclass

from app.agents.definitions import AgentPolicyError, require_tool_permission
from app.agents.registry import AGENT_REGISTRY, TOOL_REGISTRY
from app.models import AgentRiskLevel, UserRole

# 本模块是策略层的对外门面：AgentPolicyError 与 require_tool_permission 从 definitions
# 再导出，调用方（含测试）统一从这里取。显式声明 __all__ 是为了让静态检查知道
# 这两个名字是「有意再导出」而非未使用导入，避免被自动清理误删。
__all__ = [
    "AgentPolicyError",
    "PolicyDecision",
    "authorize_tool",
    "require_tool_permission",
]


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    risk_level: AgentRiskLevel
    reason: str


def authorize_tool(
    *,
    agent_key: str,
    tool_key: str,
    workspace_role: UserRole,
) -> PolicyDecision:
    """授权校验工具，依据 Agent 白名单、Workspace 角色与 R0–R3 风险返回确定性决策。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    agent = AGENT_REGISTRY.get(agent_key)
    tool = TOOL_REGISTRY.get(tool_key)
    if agent is None:
        raise AgentPolicyError(f"Agent is not registered: {agent_key}")
    if tool is None:
        raise AgentPolicyError(f"Tool is not registered: {tool_key}")
    if tool_key not in agent.tool_allowlist:
        raise AgentPolicyError(f"Agent {agent_key} is not allowed to use tool {tool_key}")
    if workspace_role == UserRole.VIEWER and tool.risk_level != AgentRiskLevel.R0:
        return PolicyDecision(False, False, tool.risk_level, "Viewer 只能执行只读分析")
    if tool.owner_only and workspace_role != UserRole.OWNER:
        return PolicyDecision(False, False, tool.risk_level, "该高风险动作仅 Workspace Owner 可执行")
    requires_approval = tool.risk_level in {AgentRiskLevel.R2, AgentRiskLevel.R3}
    return PolicyDecision(True, requires_approval, tool.risk_level, "策略校验通过")
