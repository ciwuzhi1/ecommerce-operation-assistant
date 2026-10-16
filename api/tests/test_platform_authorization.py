from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import Base, Platform, PlatformAccount, PlatformAccountStatus, Store, User, UserRole


def test_platform_authorization_start_requires_edit_permission() -> None:
    """验证“平台授权启动requiresedit权限”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    store_id, account_id = _seed_account(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = TestClient(app).post(
            f"/api/v1/stores/{store_id}/platform-accounts/{account_id}/authorization/start",
            headers={"Authorization": "Bearer test"},
            json={"auth_type": "official_api", "scopes": ["orders:read"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_platform_authorization_start_records_safe_metadata() -> None:
    """验证“平台授权启动records安全metadata”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    store_id, account_id = _seed_account(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            f"/api/v1/stores/{store_id}/platform-accounts/{account_id}/authorization/start",
            headers={"Authorization": "Bearer test"},
            json={
                "auth_type": "oauth2",
                "redirect_uri": "https://example.com/callback",
                "scopes": ["products:read", "reports:read"],
                "note": "抖音官方授权预留",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["state"]
    assert payload["authorization_url"].startswith("https://example.com/callback")
    assert "绕过登录" in payload["safety_note"]

    with Session(engine) as db:
        account = db.get(PlatformAccount, account_id)
        assert account is not None
        authorization = account.auth_metadata["authorization"]
        assert authorization["scopes"] == ["products:read", "reports:read"]
        assert "access_token" not in authorization
        assert "cookie" not in authorization


def test_platform_authorization_callback_updates_account_status() -> None:
    """验证“平台授权callbackupdates账号状态”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    store_id, account_id = _seed_account(engine)
    state = _start_authorization(engine, store_id, account_id)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            f"/api/v1/stores/{store_id}/platform-accounts/{account_id}/authorization/callback-placeholder",
            headers={"Authorization": "Bearer test"},
            json={"state": state, "status": "authorized", "external_account_id": "dy-account-001"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "authorized"
    with Session(engine) as db:
        account = db.get(PlatformAccount, account_id)
        assert account is not None
        assert account.status == PlatformAccountStatus.ACTIVE
        assert account.external_account_id == "dy-account-001"


def test_platform_authorization_callback_rejects_state_mismatch() -> None:
    """验证“平台授权callbackrejects状态mismatch”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    store_id, account_id = _seed_account(engine)
    _start_authorization(engine, store_id, account_id)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            f"/api/v1/stores/{store_id}/platform-accounts/{account_id}/authorization/callback-placeholder",
            headers={"Authorization": "Bearer test"},
            json={"state": "wrong-state", "status": "authorized"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def _start_authorization(engine, store_id: int, account_id: int) -> str:
    """构造或执行测试所需的启动授权，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            f"/api/v1/stores/{store_id}/platform-accounts/{account_id}/authorization/start",
            headers={"Authorization": "Bearer test"},
            json={"auth_type": "official_api", "scopes": ["reports:read"]},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    return response.json()["state"]


def _seed_account(engine) -> tuple[int, int]:
    """创建平台授权测试所需的店铺和平台账号，并返回二者主键。"""
    # 先 flush 店铺取得真实主键，再创建平台账号，确保授权接口的归属校验有效。
    with Session(engine) as db:
        store = Store(name="抖音旗舰店", platform=Platform.DOUYIN)
        db.add(store)
        db.flush()
        account = PlatformAccount(store_id=store.id, platform=Platform.DOUYIN, account_name="官方账号")
        db.add(account)
        db.commit()
        return store.id, account.id


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
