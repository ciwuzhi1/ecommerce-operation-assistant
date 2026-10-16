from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import Base, CreativePlan, CreativePlanType, GeneratedAsset, Platform, Product, User, UserRole


def test_update_generated_asset_review_fields_updates_plan_and_asset() -> None:
    """验证“更新生成素材审核fieldsupdates方案and素材”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, plan_id = _seed_asset(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).patch(
            f"/api/v1/products/{product_id}/creative-plans/{plan_id}/assets",
            headers={"Authorization": "Bearer test"},
            json={
                "url": "/uploads/a.png",
                "asset_type": "image",
                "status": "复测",
                "asset_version": 2,
                "usage_contexts": ["冷启动", "人群测试"],
                "rating": 4,
                "tags": ["高点击"],
                "note": "首轮反馈好，建议复测。",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    with Session(engine) as db:
        plan = db.get(CreativePlan, plan_id)
        asset = db.query(GeneratedAsset).filter_by(product_id=product_id, url="/uploads/a.png").one()

        plan_asset = plan.content["generated_images"][0]
        assert plan_asset["status"] == "复测"
        assert plan_asset["asset_version"] == 2
        assert plan_asset["usage_contexts"] == ["冷启动", "人群测试"]
        assert asset.status == "复测"
        assert asset.asset_version == 2
        assert asset.usage_contexts == ["冷启动", "人群测试"]


def test_update_generated_asset_rejects_unknown_review_status() -> None:
    """验证“更新生成素材rejectsunknown审核状态”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, plan_id = _seed_asset(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).patch(
            f"/api/v1/products/{product_id}/creative-plans/{plan_id}/assets",
            headers={"Authorization": "Bearer test"},
            json={"url": "/uploads/a.png", "asset_type": "image", "status": "可投放"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def _seed_asset(engine) -> tuple[int, int]:
    """构造或执行测试所需的测试数据素材，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with Session(engine) as db:
        product = Product(name="控油气垫", platform=Platform.DOUYIN)
        db.add(product)
        db.flush()

        plan = CreativePlan(
            product_id=product.id,
            type=CreativePlanType.MAIN_IMAGE,
            title="控油主图",
            content={
                "generated_images": [
                    {
                        "url": "/uploads/a.png",
                        "model": "mock",
                        "status": "待评估",
                    }
                ]
            },
        )
        db.add(plan)
        db.flush()

        db.add(
            GeneratedAsset(
                product_id=product.id,
                creative_plan_id=plan.id,
                asset_type="image",
                title="控油主图",
                url="/uploads/a.png",
                status="待评估",
            )
        )
        db.commit()
        return product.id, plan.id


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
