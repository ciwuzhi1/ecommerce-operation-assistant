from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    MembershipStatus,
    User,
    UserRole,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)


DEFAULT_WORKSPACE_SLUG = "default"


class WorkspaceAccessError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkspaceAccess:
    workspace: Workspace
    membership: WorkspaceMembership
    user: User

    @property
    def role(self) -> UserRole:
        """角色；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
        return self.membership.role


def ensure_default_workspace(db: Session) -> Workspace:
    """确保默认Workspace；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    workspace = db.scalar(select(Workspace).where(Workspace.slug == DEFAULT_WORKSPACE_SLUG))
    if workspace is None:
        workspace = Workspace(
            slug=DEFAULT_WORKSPACE_SLUG,
            name="默认工作区",
            status=WorkspaceStatus.ACTIVE,
            settings={"agent_platform_enabled": True},
        )
        db.add(workspace)
        db.flush()
    return workspace


def ensure_workspace_membership(
    db: Session,
    *,
    workspace: Workspace,
    user: User,
    role: UserRole | None = None,
) -> WorkspaceMembership:
    """确保Workspacemembership；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == user.id,
        )
    )
    if membership is None:
        membership = WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=role or user.role,
            status=MembershipStatus.ACTIVE,
        )
        db.add(membership)
        db.flush()
    return membership


def resolve_workspace_access(
    db: Session,
    *,
    user: User,
    workspace_id: int | None,
) -> WorkspaceAccess:
    """解析Workspace访问；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    statement = (
        select(WorkspaceMembership, Workspace)
        .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
        .where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.status == MembershipStatus.ACTIVE,
            Workspace.status == WorkspaceStatus.ACTIVE,
        )
        .order_by(WorkspaceMembership.id.asc())
    )
    if workspace_id is not None:
        statement = statement.where(WorkspaceMembership.workspace_id == workspace_id)
    row = db.execute(statement).first()
    if row is None:
        raise WorkspaceAccessError("Workspace membership not found or inactive")
    membership, workspace = row
    return WorkspaceAccess(workspace=workspace, membership=membership, user=user)


def list_user_workspaces(db: Session, *, user: User) -> list[tuple[Workspace, WorkspaceMembership]]:
    """查询用户workspaces；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    statement = (
        select(Workspace, WorkspaceMembership)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.status == MembershipStatus.ACTIVE,
            Workspace.status == WorkspaceStatus.ACTIVE,
        )
        .order_by(Workspace.id.asc())
    )
    return list(db.execute(statement).all())
