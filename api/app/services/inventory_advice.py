import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.models import Store
from app.schemas import StoreInventoryRow
from app.services.llm import LLMNotConfiguredError, LLMResponseError, create_json_chat_completion


class InventoryAdviceOutput(BaseModel):
    summary: str = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    replenishment_actions: list[str] = Field(default_factory=list)
    operation_actions: list[str] = Field(default_factory=list)
    ad_controls: list[str] = Field(default_factory=list)


def generate_inventory_advice(store: Store, rows: list[StoreInventoryRow]) -> dict[str, Any]:
    """生成库存建议；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    try:
        return generate_llm_inventory_advice(store, rows)
    except (LLMNotConfiguredError, LLMResponseError, ValidationError) as exc:
        # 库存预警属于高频运营能力，模型不可用时也要给出规则版建议，避免工作台空白。
        fallback = generate_rule_based_inventory_advice(store, rows)
        fallback["raw_output"]["fallback_reason"] = str(exc)
        return fallback


def generate_llm_inventory_advice(store: Store, rows: list[StoreInventoryRow]) -> dict[str, Any]:
    """生成llm库存建议；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed, raw_response = create_json_chat_completion(
        _build_inventory_messages(store, rows),
        max_tokens=1800,
        temperature=0.25,
    )
    advice = InventoryAdviceOutput.model_validate(parsed)
    # 只保存模型、用量和结构化输出，不保存供应商请求头或密钥相关内容。
    return {
        "source": "llm",
        **advice.model_dump(),
        "raw_output": {
            "model": raw_response.get("model"),
            "usage": raw_response.get("usage", {}),
            "llm_output": parsed,
        },
    }


def generate_rule_based_inventory_advice(store: Store, rows: list[StoreInventoryRow]) -> dict[str, Any]:
    # 规则版只基于用户录入/导入的库存字段，不推断平台后台真实销量或订单明细。
    """生成rulebased库存建议；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    low_stock_rows = [row for row in rows if row.is_low_stock]
    locked_risk_rows = [
        row for row in rows if row.quantity > 0 and row.locked_quantity / row.quantity >= 0.5
    ]
    no_stock_rows = [row for row in rows if row.available_quantity <= 0]

    if not rows:
        summary = "当前店铺还没有 SKU 库存数据，建议先补齐 SKU 和初始库存。"
    elif low_stock_rows:
        summary = f"{store.name} 有 {len(low_stock_rows)} 个 SKU 低于预警线，需要优先处理补货和投放节奏。"
    else:
        summary = f"{store.name} 当前没有低库存 SKU，库存风险较低。"

    risks = []
    if low_stock_rows:
        risks.append(f"{len(low_stock_rows)} 个 SKU 可用库存低于或等于预警线。")
    if no_stock_rows:
        risks.append(f"{len(no_stock_rows)} 个 SKU 可用库存为 0 或负数，可能影响成交履约。")
    if locked_risk_rows:
        risks.append(f"{len(locked_risk_rows)} 个 SKU 锁定库存占比较高，需要检查未发货订单或释放异常锁定。")
    if not risks:
        risks.append("暂未发现明显库存异常，建议保持每日巡检。")

    replenishment_actions = [
        f"优先补货 {row.product_name} / {row.sku_code}，当前可用 {row.available_quantity}，预警线 {row.warning_threshold}。"
        for row in low_stock_rows[:5]
    ] or ["为核心商品设置预警线，并补齐供应商交期和安全库存。"]

    operation_actions = [
        "检查低库存 SKU 是否仍在主推素材、直播间或投放计划中。",
        "核对锁定库存较高的 SKU，确认是否存在订单未发货或异常占用。",
        "对无平台映射的商品补齐平台商品 ID 和平台 SKU ID，避免跨平台库存对账断点。",
    ]
    ad_controls = [
        "低库存 SKU 暂缓放量，避免投放带来履约压力。",
        "如果必须继续投放，优先把预算转向库存充足的同款或替代 SKU。",
    ]

    return {
        "source": "rules",
        "summary": summary,
        "risks": risks,
        "replenishment_actions": replenishment_actions,
        "operation_actions": operation_actions,
        "ad_controls": ad_controls,
        "raw_output": {
            "store_id": store.id,
            "sku_count": len(rows),
            "low_stock_sku_ids": [row.sku_id for row in low_stock_rows],
            "locked_risk_sku_ids": [row.sku_id for row in locked_risk_rows],
        },
    }


def _build_inventory_messages(store: Store, rows: list[StoreInventoryRow]) -> list[dict[str, str]]:
    """构建库存消息，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    return [
        {
            "role": "system",
            "content": (
                "你是资深电商 ERP 和投放协同运营助手。你必须只输出合法 JSON，"
                "不要输出 markdown，不要输出解释性前后缀。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于店铺 SKU 库存数据，生成库存异常运营建议。输出 JSON 必须符合结构：\n"
                "{\n"
                '  "summary": "总体判断",\n'
                '  "risks": ["风险1"],\n'
                '  "replenishment_actions": ["补货动作1"],\n'
                '  "operation_actions": ["运营动作1"],\n'
                '  "ad_controls": ["投放控制1"]\n'
                "}\n\n"
                "要求：\n"
                "- 所有内容使用简体中文。\n"
                "- 只能给建议，不要建议自动扣费、自动投放或自动资金操作。\n"
                "- 建议要能被运营人员立刻执行。\n\n"
                f"库存数据 JSON：{_inventory_payload(store, rows)}"
            ),
        },
    ]


def _inventory_payload(store: Store, rows: list[StoreInventoryRow]) -> str:
    """库存载荷，统一主流程中的格式、默认值和异常边界。"""
    # 只发送店铺摘要与结构化 SKU 库存行，并关闭 ASCII 转义，便于模型理解中文字段。
    payload = {
        "store": {
            "id": store.id,
            "name": store.name,
            "platform": store.platform,
            "status": store.status,
        },
        "skus": [row.model_dump(mode="json") for row in rows],
    }
    return json.dumps(payload, ensure_ascii=False)
