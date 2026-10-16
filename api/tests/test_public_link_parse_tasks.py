from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import Base, Competitor, Platform, Product, PublicLinkParseTask, User, UserRole
from app.services.link_extraction import LinkProfile


def test_create_competitor_url_import_task_requires_edit_permission() -> None:
    """验证“创建竞品URL导入任务requiresedit权限”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id = _seed_product(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = TestClient(app).post(
            f"/api/v1/products/{product_id}/competitors/import-url-tasks",
            headers={"Authorization": "Bearer test"},
            json={"url": "https://example.com/item/1", "platform": "douyin"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_create_competitor_url_import_task_enqueues_pending_task() -> None:
    """验证“创建竞品URL导入任务enqueuespending任务”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id = _seed_product(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            f"/api/v1/products/{product_id}/competitors/import-url-tasks",
            headers={"Authorization": "Bearer test"},
            json={"url": "https://example.com/item/1", "platform": "douyin"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["task_type"] == "competitor_import"
    with Session(engine) as db:
        assert db.query(PublicLinkParseTask).count() == 1
        assert db.query(Competitor).count() == 0


def test_run_competitor_url_import_task_creates_competitor(monkeypatch) -> None:
    """验证“执行竞品URL导入任务creates竞品”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id = _seed_product(engine)
    task_id = _seed_task(engine, product_id)

    def fake_fetch_profile(url: str) -> LinkProfile:
        """构造或执行测试所需的fake获取资料，让测试数据、依赖替身与断言保持集中。"""
        assert url == "https://example.com/item/1"
        return LinkProfile(
            name="竞品饼干",
            title="低糖竞品饼干",
            price=Decimal("19.90"),
            sales_hint="月销 1 万+",
            main_image="https://example.com/a.png",
            selling_points=["低糖", "高颜值"],
        )

    monkeypatch.setattr("app.services.public_link_parse_tasks.fetch_competitor_profile", fake_fetch_profile)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            f"/api/v1/products/{product_id}/link-parse-tasks/{task_id}/run",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["result"]["competitor_id"] > 0
    with Session(engine) as db:
        competitor = db.query(Competitor).one()
        assert competitor.name == "竞品饼干"
        assert competitor.url == "https://example.com/item/1"


def _seed_product(engine) -> int:
    """构造或执行测试所需的测试数据商品，让测试数据、依赖替身与断言保持集中。"""
    with Session(engine) as db:
        product = Product(name="低糖燕麦饼干", platform=Platform.DOUYIN)
        db.add(product)
        db.commit()
        return product.id


def _seed_task(engine, product_id: int) -> int:
    """构造或执行测试所需的测试数据任务，让测试数据、依赖替身与断言保持集中。"""
    with Session(engine) as db:
        task = PublicLinkParseTask(product_id=product_id, url="https://example.com/item/1", platform=Platform.DOUYIN)
        db.add(task)
        db.commit()
        return task.id


def _engine():
    """构造或执行测试所需的engine，让测试数据、依赖替身与断言保持集中。"""
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _override_db(engine):
    """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
    def _dependency():
        """构造或执行测试所需的依赖覆盖，让测试数据、依赖替身与断言保持集中。"""
        with Session(engine) as db:
            yield db

    return _dependency


def _user(role: UserRole) -> User:
    """构造或执行测试所需的用户，让测试数据、依赖替身与断言保持集中。"""
    return User(id=1, email=f"{role.value}@example.com", display_name=f"{role.value}-user", role=role)
