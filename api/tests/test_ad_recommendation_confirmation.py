from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import AdRecommendation, Base, Platform, Product, User, UserRole


def test_operator_can_confirm_ad_recommendation_manually() -> None:
    """验证“operatorcanconfirm投放建议manually”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, recommendation_id = _seed_recommendation(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).patch(
            f"/api/v1/products/{product_id}/ad-recommendations/{recommendation_id}/confirmation",
            headers={"Authorization": "Bearer test"},
            json={"confirmation_status": "confirmed", "confirmation_note": "确认用于小预算测试。"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["confirmation_status"] == "confirmed"
    assert payload["confirmed_by_user_id"] == 1
    assert payload["confirmed_at"] is not None
    assert payload["confirmation_note"] == "确认用于小预算测试。"


def test_viewer_cannot_confirm_ad_recommendation() -> None:
    """验证“viewercannotconfirm投放建议”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, recommendation_id = _seed_recommendation(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = TestClient(app).patch(
            f"/api/v1/products/{product_id}/ad-recommendations/{recommendation_id}/confirmation",
            headers={"Authorization": "Bearer test"},
            json={"confirmation_status": "confirmed"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def _seed_recommendation(engine) -> tuple[int, int]:
    """构造或执行测试所需的测试数据建议，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with Session(engine) as db:
        product = Product(name="控油气垫", platform=Platform.DOUYIN)
        db.add(product)
        db.flush()
        recommendation = AdRecommendation(
            product_id=product.id,
            source="rules",
            summary="建议小预算验证素材。",
            content={"objective": "验证点击和 ROI"},
        )
        db.add(recommendation)
        db.commit()
        return product.id, recommendation.id


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
