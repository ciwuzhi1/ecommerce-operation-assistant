from sqlalchemy.orm import Session

from app.models import InventoryItem, InventoryMovement, InventoryMovementType, ProductSku


class InventoryAdjustmentError(ValueError):
    pass


def create_inventory_item_for_sku(
    db: Session,
    sku: ProductSku,
    *,
    initial_quantity: int = 0,
    warning_threshold: int = 0,
    location: str | None = None,
    operator_name: str | None = None,
) -> InventoryItem:
    # SKU 创建时同步初始化库存档案，哪怕初始库存为 0，也能后续设置预警线和库位。
    """创建库存条目forSKU；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    item = InventoryItem(
        sku=sku,
        quantity=0,
        locked_quantity=0,
        warning_threshold=warning_threshold,
        location=location,
    )
    db.add(item)
    db.flush()
    if initial_quantity > 0:
        adjust_inventory(
            db,
            item,
            movement_type=InventoryMovementType.INBOUND,
            quantity_delta=initial_quantity,
            reason="初始库存",
            operator_name=operator_name,
        )
    return item


def adjust_inventory(
    db: Session,
    item: InventoryItem,
    *,
    movement_type: InventoryMovementType,
    quantity_delta: int = 0,
    locked_delta: int = 0,
    reason: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
    operator_name: str | None = None,
) -> InventoryMovement:
    # 库存不能直接覆盖，所有变化都必须写流水，方便后续 ERP 对账和异常追踪。
    """adjust库存；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    before_quantity = item.quantity
    before_locked_quantity = item.locked_quantity
    after_quantity = before_quantity + quantity_delta
    after_locked_quantity = before_locked_quantity + locked_delta

    if after_quantity < 0:
        raise InventoryAdjustmentError("库存数量不能小于 0")
    if after_locked_quantity < 0:
        raise InventoryAdjustmentError("锁定库存不能小于 0")
    if after_locked_quantity > after_quantity:
        raise InventoryAdjustmentError("锁定库存不能超过总库存")
    if movement_type == InventoryMovementType.LOCK and locked_delta <= 0:
        # 锁库存只表达订单占用等预留动作，不在这里扣减真实库存，避免和出库动作重复计算。
        raise InventoryAdjustmentError("锁定库存时 locked_delta 必须大于 0")
    if movement_type == InventoryMovementType.RELEASE and locked_delta >= 0:
        # 释放库存只减少占用量，真实库存仍由入库、出库或盘点调整维护。
        raise InventoryAdjustmentError("释放库存时 locked_delta 必须小于 0")

    item.quantity = after_quantity
    item.locked_quantity = after_locked_quantity
    movement = InventoryMovement(
        inventory_item=item,
        sku_id=item.sku_id,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        locked_delta=locked_delta,
        before_quantity=before_quantity,
        after_quantity=after_quantity,
        before_locked_quantity=before_locked_quantity,
        after_locked_quantity=after_locked_quantity,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        operator_name=operator_name,
    )
    db.add(movement)
    return movement
