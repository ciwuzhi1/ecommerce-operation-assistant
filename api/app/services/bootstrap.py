from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserRole, UserStatus
from app.services.users import hash_password
from app.services.workspaces import ensure_default_workspace, ensure_workspace_membership


def ensure_bootstrap_user(
    db: Session,
    *,
    email: str,
    display_name: str,
    password: str,
    role: UserRole = UserRole.OWNER,
) -> tuple[User, bool]:
    """确保初始化账号用户；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    normalized_email = email.strip().lower()
    existing = db.scalars(select(User).where(User.email == normalized_email)).first()
    if existing is not None:
        workspace = ensure_default_workspace(db)
        ensure_workspace_membership(db, workspace=workspace, user=existing, role=existing.role)
        db.commit()
        return existing, False

    # 新环境没有用户时，需要一个受控的初始化入口；密码只来自环境变量或命令行，不写入代码。
    user = User(
        email=normalized_email,
        display_name=display_name.strip(),
        role=role,
        status=UserStatus.ACTIVE,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()
    workspace = ensure_default_workspace(db)
    ensure_workspace_membership(db, workspace=workspace, user=user, role=role)
    db.commit()
    db.refresh(user)
    return user, True
