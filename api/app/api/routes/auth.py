from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User, UserRole, Workspace
from app.schemas import AuthTokenRead, LoginRequest, UserRead
from app.services.auth import AuthTokenError, create_access_token, ensure_user_can_login, parse_access_token
from app.services.users import user_to_read, verify_password
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.workspaces import WorkspaceAccess, WorkspaceAccessError, resolve_workspace_access


router = APIRouter(prefix="/auth", tags=["auth"])
SessionDep = Annotated[Session, Depends(get_db)]
# Swagger 的 Authorize 按钮依赖安全方案声明；auto_error=False 让缺失令牌由本模块统一返回 401。
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/login", response_model=AuthTokenRead)
def login(payload: LoginRequest, db: SessionDep) -> dict:
    # 邮箱统一归一化后查询，避免大小写差异导致同一运营账号出现多套登录态。
    """处理登录接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    user = db.scalars(select(User).where(User.email == payload.email.strip().lower())).first()
    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    try:
        ensure_user_can_login(user)
    except AuthTokenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": user_to_read(user),
    }


def get_current_user(
    db: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    # 依赖层只接受 Bearer token，并在每次请求里重新校验账号可用性，保证权限收口在后端。
    # 通过 HTTPBearer 读取令牌，接口文档才会声明 bearer 安全方案。
    """处理获取当前用户接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    token = _bearer_token(credentials)
    try:
        payload = parse_access_token(token)
        user_id = int(payload.get("sub", 0))
        user = ensure_user_can_login(db.get(User, user_id))
    except (AuthTokenError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token") from exc
    return user


def require_edit_permission(
    db: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
    x_workspace_id: Annotated[int | None, Header(alias="X-Workspace-ID")] = None,
) -> User:
    """处理校验并获取edit权限接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    access = _bind_workspace_to_session(db, current_user=current_user, workspace_id=x_workspace_id)
    # Workspace 已启用后以成员角色为准，避免全局 operator 绕过目标 Workspace 的 viewer 限制。
    effective_role = access.role if access is not None else current_user.role
    if effective_role not in {UserRole.OWNER, UserRole.OPERATOR}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Edit permission required")
    return current_user


def require_view_permission(
    db: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
    x_workspace_id: Annotated[int | None, Header(alias="X-Workspace-ID")] = None,
) -> User:
    """处理校验并获取查看权限接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    _bind_workspace_to_session(db, current_user=current_user, workspace_id=x_workspace_id)
    return current_user


def get_current_workspace(
    db: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
    x_workspace_id: Annotated[int | None, Header(alias="X-Workspace-ID")] = None,
) -> WorkspaceAccess:
    # Workspace 必须从认证用户的成员关系解析，不能信任模型或普通请求体自由填写租户 ID。
    """处理获取当前Workspace接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    try:
        return resolve_workspace_access(db, user=current_user, workspace_id=x_workspace_id)
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


def require_workspace_edit_permission(
    access: Annotated[WorkspaceAccess, Depends(get_current_workspace)],
) -> WorkspaceAccess:
    """处理校验并获取Workspaceedit权限接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    if access.role not in {UserRole.OWNER, UserRole.OPERATOR}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace edit permission required")
    return access


def require_workspace_owner_permission(
    access: Annotated[WorkspaceAccess, Depends(get_current_workspace)],
) -> WorkspaceAccess:
    """处理校验并获取Workspaceowner权限接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    if access.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace owner permission required")
    return access


def require_manage_users_permission(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    # 用户管理会影响全局权限边界，当前只开放给 owner，后续如做店铺级权限再拆细。
    """处理校验并获取manageusers权限接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    if current_user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User management permission required")
    return current_user


def require_ad_confirmation_permission(
    db: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
    x_workspace_id: Annotated[int | None, Header(alias="X-Workspace-ID")] = None,
) -> User:
    # 投放确认虽不直接扣费，但会形成运营决策记录，因此只允许 owner/operator 操作。
    """处理校验并获取投放confirmation权限接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    access = _bind_workspace_to_session(db, current_user=current_user, workspace_id=x_workspace_id)
    effective_role = access.role if access is not None else current_user.role
    if effective_role not in {UserRole.OWNER, UserRole.OPERATOR}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ad confirmation permission required")
    return current_user


def _bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    """处理bearerToken接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")
    if (credentials.scheme or "").lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth header")
    return credentials.credentials


def _bind_workspace_to_session(
    db: Session,
    *,
    current_user: User,
    workspace_id: int | None,
) -> WorkspaceAccess | None:
    # 只有尚未创建 Workspace 数据的旧测试库允许兼容路径；真实环境缺少 Membership 必须拒绝。
    """处理绑定Workspaceto会话接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    from app.services.workspaces import list_user_workspaces

    memberships = list_user_workspaces(db, user=current_user)
    if not memberships:
        workspace_count = db.scalar(select(func.count(Workspace.id)))
        if int(workspace_count or 0) > 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace membership not found or inactive",
            )
        db.info["workspace_id"] = None
        return None
    try:
        access = resolve_workspace_access(db, user=current_user, workspace_id=workspace_id)
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    db.info["workspace_id"] = access.workspace.id
    return access


@router.get("/me", response_model=UserRead)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """处理获取me接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    return user_to_read(current_user)
