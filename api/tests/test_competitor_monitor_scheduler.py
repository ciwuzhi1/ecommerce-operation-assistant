from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import Base, Competitor, CompetitorMonitor, CompetitorMonitorSnapshot, Platform, Product, User, UserRole
from app.services.link_extraction import LinkProfile


def test_run_due_competitor_monitors_requires_edit_permission() -> None:
    """验证“执行到期竞品monitorsrequiresedit权限”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed_due_monitor(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = TestClient(app).post(
            "/api/v1/workspace/competitor-monitors/run-due",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_run_due_competitor_monitors_consumes_due_monitors(monkeypatch) -> None:
    """验证“执行到期竞品monitorsconsumes到期monitors”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    due_monitor_id = _seed_due_monitor(engine)
    future_monitor_id = _seed_future_monitor(engine)

    def fake_fetch_profile(url: str) -> LinkProfile:
        """构造或执行测试所需的fake获取资料，让测试数据、依赖替身与断言保持集中。"""
        return LinkProfile(
            name="竞品新标题",
            title="竞品新标题",
            price=Decimal("21.90"),
            sales_hint="月销 2 万+",
            main_image="https://example.com/new.png",
            selling_points=["低糖"],
        )

    monkeypatch.setattr("app.services.competitor_monitoring.fetch_competitor_profile", fake_fetch_profile)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            "/api/v1/workspace/competitor-monitors/run-due",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["checked_count"] == 1
    assert payload["succeeded_count"] == 1
    assert payload["monitor_ids"] == [due_monitor_id]

    with Session(engine) as db:
        assert db.query(CompetitorMonitorSnapshot).count() == 1
        due_monitor = db.get(CompetitorMonitor, due_monitor_id)
        future_monitor = db.get(CompetitorMonitor, future_monitor_id)
        assert due_monitor is not None
        assert future_monitor is not None
        assert due_monitor.last_checked_at is not None
        assert due_monitor.next_check_at is not None
        assert due_monitor.next_check_at > due_monitor.last_checked_at
        assert future_monitor.last_checked_at is None


def _seed_due_monitor(engine) -> int:
    """构造或执行测试所需的测试数据到期监控，让测试数据、依赖替身与断言保持集中。"""
    return _seed_monitor(engine, next_check_at=datetime.now(UTC) - timedelta(minutes=5))


def _seed_future_monitor(engine) -> int:
    """构造或执行测试所需的测试数据future监控，让测试数据、依赖替身与断言保持集中。"""
    return _seed_monitor(engine, next_check_at=datetime.now(UTC) + timedelta(days=1))


def _seed_monitor(engine, next_check_at: datetime) -> int:
    """构造或执行测试所需的测试数据监控，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with Session(engine) as db:
        product = Product(name="低糖燕麦饼干", platform=Platform.DOUYIN)
        competitor = Competitor(
            product=product,
            name="竞品饼干",
            platform=Platform.DOUYIN,
            url="https://example.com/item/1",
        )
        db.add_all([product, competitor])
        db.flush()
        monitor = CompetitorMonitor(
            product_id=product.id,
            competitor_id=competitor.id,
            interval_days=1,
            status="active",
            next_check_at=next_check_at,
        )
        db.add(monitor)
        db.commit()
        return monitor.id


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
