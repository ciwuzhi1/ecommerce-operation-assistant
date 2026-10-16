from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import Base, User, UserRole
from app.services.auth import create_access_token, parse_access_token
from app.services.users import hash_password


def test_create_and_parse_access_token() -> None:
    """验证“创建and解析访问Token”场景，确保重构后仍满足预期业务与安全边界。"""
    user = User(id=7, email="owner@example.com", display_name="Owner", role=UserRole.OWNER)
    settings = SimpleNamespace(auth_secret_key="test-secret", auth_token_expire_minutes=10)

    token = create_access_token(user, settings)
    payload = parse_access_token(token, settings)

    assert payload["sub"] == "7"
    assert payload["email"] == "owner@example.com"
    assert payload["role"] == "owner"


def test_login_and_me_api() -> None:
    """验证“登录andmeapi”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            User(
                email="owner@example.com",
                display_name="Owner",
                role=UserRole.OWNER,
                password_hash=hash_password("secret-password"),
            )
        )
        db.commit()

    def override_db():
        """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "secret-password"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]

        me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "owner@example.com"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_login_rejects_wrong_password() -> None:
    """验证“登录rejectswrongpassword”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            User(
                email="owner@example.com",
                display_name="Owner",
                password_hash=hash_password("secret-password"),
            )
        )
        db.commit()

    def override_db():
        """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "wrong"},
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


def _engine():
    """构造或执行测试所需的engine，让测试数据、依赖替身与断言保持集中。"""
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
