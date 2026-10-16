import pytest

from app.agents.contracts import AgentWorkflowState
from app.agents.definitions import PRODUCT_CONTEXT_AGENT
from app.agents.harness import redact_snapshot
from app.agents.policy import AgentPolicyError, require_tool_permission


def test_foundation_import_and_allowed_tool():
    state: AgentWorkflowState = {"product_id": 1}
    assert state["product_id"] == 1
    require_tool_permission(PRODUCT_CONTEXT_AGENT, "product_context.read")


def test_forbidden_tool_is_rejected():
    with pytest.raises(AgentPolicyError):
        require_tool_permission(PRODUCT_CONTEXT_AGENT, "model.complete")


def test_unknown_agent_is_rejected():
    with pytest.raises(AgentPolicyError):
        require_tool_permission("unknown_agent", "product_context.read")


def test_snapshot_redacts_nested_secrets():
    result = redact_snapshot({"api_key": "test-key", "nested": {"password": "test-password"}})
    assert result["api_key"] == "[redacted]"
    assert result["nested"]["password"] == "[redacted]"
