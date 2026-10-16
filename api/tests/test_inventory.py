import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Base,
    InventoryMovementType,
    Platform,
    PlatformProductMapping,
    Product,
    ProductSku,
    Store,
)
from app.services.inventory import InventoryAdjustmentError, adjust_inventory, create_inventory_item_for_sku


def test_inventory_adjustment_writes_movement_and_updates_quantity() -> None:
    """验证“库存adjustmentwrites流水andupdatesquantity”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        sku = _sku(db)
        item = create_inventory_item_for_sku(db, sku, initial_quantity=10, warning_threshold=3)
        movement = adjust_inventory(
            db,
            item,
            movement_type=InventoryMovementType.OUTBOUND,
            quantity_delta=-2,
            reason="测试出库",
            operator_name="运营",
        )
        db.commit()

        assert item.quantity == 8
        assert item.warning_threshold == 3
        assert movement.before_quantity == 10
        assert movement.after_quantity == 8
        assert movement.reason == "测试出库"


def test_inventory_lock_cannot_exceed_available_quantity() -> None:
    """验证“库存锁定cannotexceedavailablequantity”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        sku = _sku(db)
        item = create_inventory_item_for_sku(db, sku, initial_quantity=2)

        with pytest.raises(InventoryAdjustmentError):
            adjust_inventory(
                db,
                item,
                movement_type=InventoryMovementType.LOCK,
                locked_delta=3,
            )


def test_platform_mapping_links_store_product_and_sku() -> None:
    """验证“平台mappinglinks店铺商品andSKU”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        store = Store(name="Douyin Shop", platform=Platform.DOUYIN)
        product = Product(name="oil control cushion", platform=Platform.DOUYIN, store=store)
        sku = ProductSku(product=product, sku_code="SKU-1", name="Natural")
        mapping = PlatformProductMapping(
            store=store,
            product=product,
            sku=sku,
            platform=Platform.DOUYIN,
            external_product_id="item-1",
            external_sku_id="sku-1",
        )
        db.add(mapping)
        db.commit()
        db.refresh(mapping)

        assert mapping.store_id == store.id
        assert mapping.product_id == product.id
        assert mapping.sku_id == sku.id


def _sku(db: Session) -> ProductSku:
    """构造或执行测试所需的SKU，让测试数据、依赖替身与断言保持集中。"""
    product = Product(name="oil control cushion", platform=Platform.DOUYIN)
    sku = ProductSku(product=product, sku_code="SKU-1", name="Natural")
    db.add(sku)
    db.flush()
    return sku


def _session() -> Session:
    """构造或执行测试所需的会话，让测试数据、依赖替身与断言保持集中。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)
