from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import AdExperiment, Base, Platform, Product, Store, User, UserRole
from app.models import ProductSku, ProductSkuStatus


def test_anonymous_cannot_read_business_data() -> None:
    """验证“anonymouscannot读取business数据”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    try:
        client = TestClient(app)
        product_response = client.get("/api/v1/products")
        store_response = client.get("/api/v1/stores")
    finally:
        app.dependency_overrides.clear()

    assert product_response.status_code == 401
    assert store_response.status_code == 401


def test_viewer_can_read_business_data() -> None:
    """验证“viewercan读取business数据”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, store_id = _seed_product_and_store(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.VIEWER)
    try:
        client = TestClient(app)
        product_list_response = client.get("/api/v1/products", headers={"Authorization": "Bearer test"})
        product_detail_response = client.get(f"/api/v1/products/{product_id}", headers={"Authorization": "Bearer test"})
        store_list_response = client.get("/api/v1/stores", headers={"Authorization": "Bearer test"})
        store_detail_response = client.get(f"/api/v1/stores/{store_id}", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert product_list_response.status_code == 200
    assert product_detail_response.status_code == 200
    assert store_list_response.status_code == 200
    assert store_detail_response.status_code == 200


def test_viewer_cannot_create_store() -> None:
    """验证“viewercannot创建店铺”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = TestClient(app).post(
            "/api/v1/stores",
            json={"name": "Viewer Shop", "platform": "douyin"},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_operator_can_create_store() -> None:
    """验证“operatorcan创建店铺”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            "/api/v1/stores",
            json={"name": "Operator Shop", "platform": "douyin"},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["name"] == "Operator Shop"


def test_viewer_cannot_create_product() -> None:
    """验证“viewercannot创建商品”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = TestClient(app).post(
            "/api/v1/products",
            json={"name": "Viewer Product", "platform": "douyin"},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_operator_can_create_product() -> None:
    """验证“operatorcan创建商品”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            "/api/v1/products",
            json={"name": "Operator Product", "platform": "douyin"},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["name"] == "Operator Product"


def test_operator_can_update_product_sku_status_and_warning_threshold() -> None:
    """验证“operatorcan更新商品SKU状态andwarningthreshold”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, sku_id = _seed_sku(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).patch(
            f"/api/v1/products/{product_id}/skus/{sku_id}",
            json={
                "status": "inactive",
                "warning_threshold": 8,
                "location": "B-01",
            },
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "inactive"
    assert payload["inventory_item"]["warning_threshold"] == 8
    assert payload["inventory_item"]["location"] == "B-01"


def test_viewer_cannot_confirm_ad_experiment_status() -> None:
    """验证“viewercannotconfirm投放实验状态”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, experiment_id = _seed_ad_experiment(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = TestClient(app).patch(
            f"/api/v1/products/{product_id}/ad-experiments/{experiment_id}",
            json={"status": "active"},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_operator_can_confirm_ad_experiment_status() -> None:
    """验证“operatorcanconfirm投放实验状态”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, experiment_id = _seed_ad_experiment(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).patch(
            f"/api/v1/products/{product_id}/ad-experiments/{experiment_id}",
            json={"status": "active"},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "active"


def _seed_ad_experiment(engine) -> tuple[int, int]:
    """构造或执行测试所需的测试数据投放实验，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with Session(engine) as db:
        product = Product(name="oil control cushion", platform=Platform.DOUYIN)
        experiment = AdExperiment(
            product=product,
            name="Test experiment",
            objective="Validate creative",
            status="draft",
        )
        db.add(experiment)
        db.commit()
        return product.id, experiment.id


def _seed_sku(engine) -> tuple[int, int]:
    """构造或执行测试所需的测试数据SKU，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with Session(engine) as db:
        product = Product(name="oil control cushion", platform=Platform.DOUYIN)
        sku = ProductSku(
            product=product,
            sku_code="SKU-1",
            name="Natural",
            status=ProductSkuStatus.ACTIVE,
        )
        db.add(sku)
        db.commit()
        return product.id, sku.id


def _seed_product_and_store(engine) -> tuple[int, int]:
    """构造或执行测试所需的测试数据商品and店铺，让测试数据、依赖替身与断言保持集中。"""
    with Session(engine) as db:
        product = Product(name="oil control cushion", platform=Platform.DOUYIN)
        store = Store(name="Douyin Flagship", platform=Platform.DOUYIN)
        db.add_all([product, store])
        db.commit()
        return product.id, store.id


def _override_db(engine):
    """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
    def override_db():
        """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
        with Session(engine) as db:
            yield db

    return override_db


def _user(role: UserRole) -> User:
    """构造或执行测试所需的用户，让测试数据、依赖替身与断言保持集中。"""
    return User(id=1, email=f"{role}@example.com", display_name=str(role), role=role)


def _engine():
    """构造或执行测试所需的engine，让测试数据、依赖替身与断言保持集中。"""
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
