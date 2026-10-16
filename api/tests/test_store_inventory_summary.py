from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.api.routes.auth import get_current_user
from app.models import Base, InventoryItem, InventoryMovementType, Platform, Product, ProductSku, Store, User, UserRole
from app.services.inventory import adjust_inventory


def test_store_inventory_summary_counts_low_stock_and_available_quantity() -> None:
    """验证“店铺库存汇总countslow库存andavailablequantity”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        store = Store(name="Douyin Shop", platform=Platform.DOUYIN)
        product = Product(name="oil control cushion", platform=Platform.DOUYIN, store=store)
        sku = ProductSku(product=product, sku_code="SKU-1", name="Natural")
        inventory_item = InventoryItem(
            sku=sku,
            quantity=5,
            locked_quantity=2,
            warning_threshold=3,
            location="A-01",
        )
        db.add(inventory_item)
        db.commit()
        store_id = store.id

    def override_db():
        """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        email="viewer@example.com",
        display_name="Viewer",
        role=UserRole.VIEWER,
    )
    try:
        response = TestClient(app).get(f"/api/v1/stores/{store_id}/inventory-summary")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["sku_count"] == 1
    assert payload["total_quantity"] == 5
    assert payload["total_locked_quantity"] == 2
    assert payload["total_available_quantity"] == 3
    assert payload["low_stock_count"] == 1
    assert payload["rows"][0]["is_low_stock"] is True
    assert payload["rows"][0]["location"] == "A-01"


def test_store_inventory_movements_include_product_and_sku_context() -> None:
    """验证“店铺库存movementsinclude商品andSKU上下文”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        store = Store(name="Douyin Shop", platform=Platform.DOUYIN)
        product = Product(name="oil control cushion", platform=Platform.DOUYIN, store=store)
        sku = ProductSku(product=product, sku_code="SKU-1", name="Natural")
        inventory_item = InventoryItem(sku=sku, quantity=10, locked_quantity=0, warning_threshold=3)
        db.add(inventory_item)
        db.flush()
        adjust_inventory(
            db,
            inventory_item,
            movement_type=InventoryMovementType.OUTBOUND,
            quantity_delta=-2,
            reason="测试出库",
        )
        db.commit()
        store_id = store.id

    def override_db():
        """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        email="viewer@example.com",
        display_name="Viewer",
        role=UserRole.VIEWER,
    )
    try:
        response = TestClient(app).get(f"/api/v1/stores/{store_id}/inventory-movements")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["product_name"] == "oil control cushion"
    assert payload[0]["sku_code"] == "SKU-1"
    assert payload[0]["quantity_delta"] == -2


def test_store_inventory_advice_uses_rule_fallback_for_low_stock() -> None:
    """验证“店铺库存建议usesrulefallbackforlow库存”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    store_id = _seed_low_stock_store(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        email="operator@example.com",
        display_name="Operator",
        role=UserRole.OPERATOR,
    )
    try:
        response = TestClient(app).post(
            f"/api/v1/stores/{store_id}/inventory-advice",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] in {"rules", "llm"}
    assert payload["summary"]
    assert payload["risks"]
    assert payload["replenishment_actions"]


def test_viewer_cannot_generate_store_inventory_advice() -> None:
    """验证“viewercannot生成店铺库存建议”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    store_id = _seed_low_stock_store(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        email="viewer@example.com",
        display_name="Viewer",
        role=UserRole.VIEWER,
    )
    try:
        response = TestClient(app).post(
            f"/api/v1/stores/{store_id}/inventory-advice",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def _override_db(engine):
    """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
    def override_db():
        """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
        with Session(engine) as db:
            yield db

    return override_db


def _seed_low_stock_store(engine) -> int:
    """构造或执行测试所需的测试数据low库存店铺，让测试数据、依赖替身与断言保持集中。"""
    with Session(engine) as db:
        store = Store(name="Douyin Shop", platform=Platform.DOUYIN)
        product = Product(name="oil control cushion", platform=Platform.DOUYIN, store=store)
        sku = ProductSku(product=product, sku_code="SKU-1", name="Natural")
        db.add(InventoryItem(sku=sku, quantity=5, locked_quantity=2, warning_threshold=3))
        db.commit()
        return store.id
