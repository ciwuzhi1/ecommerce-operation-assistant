from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, User, UserRole
from app.services.bootstrap import ensure_bootstrap_user
from app.services.users import verify_password


def test_ensure_bootstrap_user_creates_owner() -> None:
    """验证“确保初始化账号用户createsowner”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user, created = ensure_bootstrap_user(
            db,
            email=" Owner@Example.com ",
            display_name="Owner",
            password="secret-password",
            role=UserRole.OWNER,
        )

        assert created
        assert user.email == "owner@example.com"
        assert user.role == UserRole.OWNER
        assert user.password_hash is not None
        assert verify_password("secret-password", user.password_hash)


def test_ensure_bootstrap_user_keeps_existing_user() -> None:
    """验证“确保初始化账号用户keepsexisting用户”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add(User(email="owner@example.com", display_name="Old Owner", role=UserRole.OPERATOR))
        db.commit()

        user, created = ensure_bootstrap_user(
            db,
            email="owner@example.com",
            display_name="New Owner",
            password="secret-password",
            role=UserRole.OWNER,
        )

        assert not created
        assert user.display_name == "Old Owner"
        assert user.role == UserRole.OPERATOR


def _engine():
    """构造或执行测试所需的engine，让测试数据、依赖替身与断言保持集中。"""
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
