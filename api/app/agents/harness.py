import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.agents.contracts import ModelUsage


SENSITIVE_KEY_PATTERN = re.compile(
    r"(api[_-]?key|authorization|password|secret|cookie|credential|"
    r"(access|refresh|auth|bearer|api)[_-]?token)",
    re.IGNORECASE,
)
MAX_SNAPSHOT_STRING_LENGTH = 2000
MAX_SNAPSHOT_DEPTH = 8
MAX_SNAPSHOT_ITEMS = 200


class AgentBudgetExceededError(RuntimeError):
    pass


def redact_snapshot(value: Any, *, depth: int = 0) -> Any:
    """保留可回放结构，同时移除密钥类字段并限制异常大文本。"""
    # 递归深度、集合长度和文本长度都设硬上限，防止观测快照泄密或拖垮事件存储。
    if depth >= MAX_SNAPSHOT_DEPTH:
        return "[truncated-depth]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_SNAPSHOT_ITEMS:
                result["[truncated-items]"] = len(value) - MAX_SNAPSHOT_ITEMS
                break
            key_text = str(key)[:200]
            if key_text.lower() == "token" or SENSITIVE_KEY_PATTERN.search(key_text):
                result[key_text] = "[redacted]"
            else:
                result[key_text] = redact_snapshot(item, depth=depth + 1)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        result = []
        for index, item in enumerate(value):
            if index >= MAX_SNAPSHOT_ITEMS:
                break
            result.append(redact_snapshot(item, depth=depth + 1))
        if len(value) > MAX_SNAPSHOT_ITEMS:
            result.append(f"[truncated-items:{len(value) - MAX_SNAPSHOT_ITEMS}]")
        return result
    if isinstance(value, str) and len(value) > MAX_SNAPSHOT_STRING_LENGTH:
        return f"{value[:MAX_SNAPSHOT_STRING_LENGTH]}...[truncated]"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def normalize_model_usage(raw_usage: Mapping[str, Any] | None) -> ModelUsage:
    """归一化模型用量，统一执行预算、脱敏和模型用量边界，避免供应商差异泄漏到节点。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    raw_usage = raw_usage or {}
    input_tokens = _non_negative_int(
        raw_usage.get("prompt_tokens", raw_usage.get("input_tokens", 0))
    )
    output_tokens = _non_negative_int(
        raw_usage.get("completion_tokens", raw_usage.get("output_tokens", 0))
    )
    total_tokens = _non_negative_int(raw_usage.get("total_tokens", input_tokens + output_tokens))
    return ModelUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        calls=1,
    )


def merge_model_usage(current: Mapping[str, Any] | None, addition: ModelUsage) -> dict[str, int]:
    """合并模型用量，统一执行预算、脱敏和模型用量边界，避免供应商差异泄漏到节点。"""
    existing = ModelUsage.model_validate(current or {})
    return ModelUsage(
        input_tokens=existing.input_tokens + addition.input_tokens,
        output_tokens=existing.output_tokens + addition.output_tokens,
        total_tokens=existing.total_tokens + addition.total_tokens,
        calls=existing.calls + addition.calls,
    ).model_dump()


def remaining_model_tokens(
    budget: Mapping[str, Any] | None,
    usage: Mapping[str, Any] | None,
    requested_output_tokens: int,
) -> int:
    """计算本次模型调用可用的输出 Token，并在总预算耗尽时阻止继续调用。"""
    # 以已累计总用量扣减运行预算，再与节点申请量取较小值，避免单节点绕过全局预算。
    max_total = _non_negative_int((budget or {}).get("max_total_tokens", 12000))
    consumed = ModelUsage.model_validate(usage or {}).total_tokens
    remaining = max_total - consumed
    if remaining <= 0:
        raise AgentBudgetExceededError("Agent run token budget exhausted")
    return min(requested_output_tokens, remaining)


def _non_negative_int(value: Any) -> int:
    """非negativeint，统一执行预算、脱敏和模型用量边界，避免供应商差异泄漏到节点。"""
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0
