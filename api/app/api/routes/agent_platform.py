from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.agents.registry import (
    AGENT_REGISTRY,
    COORDINATOR_AGENT,
    TOOL_REGISTRY,
    WORKFLOW_REGISTRY,
    is_workflow_enabled,
)
from app.agents.tool_gateway import EXECUTABLE_TOOL_KEYS
from app.api.routes.auth import (
    get_current_user,
    get_current_workspace,
    require_workspace_edit_permission,
)
from app.core.errors import APPR_ALREADY_DECIDED, APPR_EXPIRED, CodedHTTPException
from app.db.session import get_db
from app.models import (
    AgentApproval,
    AgentApprovalStatus,
    AgentConversation,
    AgentConversationMessage,
    AgentMemory,
    AgentMemoryStatus,
    AgentRun,
    AgentTask,
    AgentTaskStatus,
    User,
)
from app.schemas import (
    AgentApprovalDecisionCreate,
    AgentApprovalRead,
    AgentCatalogRead,
    AgentConversationCreate,
    AgentConversationMessageCreate,
    AgentConversationMessageRead,
    AgentConversationRead,
    AgentDefinitionRead,
    AgentMemoryCreate,
    AgentMemoryRead,
    AgentRunRead,
    AgentTaskCreate,
    AgentTaskRead,
    ToolDefinitionRead,
    WorkflowDefinitionRead,
    WorkspaceAccessRead,
)
from app.services.agent_tasks import (
    AgentApprovalExpiredError,
    AgentTaskConflictError,
    AgentTaskStateError,
    cancel_agent_task,
    create_agent_memory,
    create_agent_task,
    decide_agent_approval,
    revoke_agent_memory,
)
from app.services.outbox import kick_outbox_dispatcher
from app.services.workspaces import WorkspaceAccess, list_user_workspaces


router = APIRouter(tags=["agent-platform"])
SessionDep = Annotated[Session, Depends(get_db)]
WorkspaceDep = Annotated[WorkspaceAccess, Depends(get_current_workspace)]
WorkspaceEditDep = Annotated[WorkspaceAccess, Depends(require_workspace_edit_permission)]


@router.get("/workspaces", response_model=list[WorkspaceAccessRead])
def list_workspaces(
    db: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    """处理查询workspaces接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    return [
        {"workspace": workspace, "membership": membership}
        for workspace, membership in list_user_workspaces(db, user=current_user)
    ]


@router.get("/workspaces/{workspace_id}/agent/catalog", response_model=AgentCatalogRead)
def get_agent_catalog(workspace_id: int, access: WorkspaceDep) -> AgentCatalogRead:
    """处理获取Agentcatalog接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    coordinator = AGENT_REGISTRY[COORDINATOR_AGENT]
    return AgentCatalogRead(
        coordinator=_agent_read(coordinator),
        agents=[
            _agent_read(definition)
            for key, definition in AGENT_REGISTRY.items()
            if key != COORDINATOR_AGENT
        ],
        # PRD FR-59 要求目录同时返回工具及其风险等级，前端据此判断哪些能力已可用。
        tools=[
            ToolDefinitionRead(
                key=definition.key,
                risk_level=definition.risk_level,
                description=definition.description,
                executable=definition.key in EXECUTABLE_TOOL_KEYS,
            )
            for definition in TOOL_REGISTRY.values()
        ],
        workflows=[
            WorkflowDefinitionRead(
                key=workflow.key,
                version=workflow.version,
                title=workflow.title,
                description=workflow.description,
                agents=list(workflow.agents),
                required_context_any=list(workflow.required_context_any),
                default_risk_level=workflow.default_risk_level,
            )
            for workflow in WORKFLOW_REGISTRY.values()
            if is_workflow_enabled(access.workspace.settings, workflow.key)
        ],
    )


@router.post(
    "/workspaces/{workspace_id}/agent/conversations",
    response_model=AgentConversationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    workspace_id: int,
    payload: AgentConversationCreate,
    db: SessionDep,
    access: WorkspaceEditDep,
) -> AgentConversation:
    """处理创建会话接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    conversation = AgentConversation(
        workspace_id=workspace_id,
        created_by_user_id=access.user.id,
        title=payload.title,
        context_scope=payload.context_scope,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get(
    "/workspaces/{workspace_id}/agent/conversations",
    response_model=list[AgentConversationRead],
)
def list_conversations(
    workspace_id: int,
    db: SessionDep,
    access: WorkspaceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AgentConversation]:
    """处理查询conversations接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    return list(
        db.scalars(
            select(AgentConversation)
            .where(AgentConversation.workspace_id == workspace_id)
            .order_by(AgentConversation.id.desc())
            .limit(limit)
        ).all()
    )


@router.post(
    "/workspaces/{workspace_id}/agent/conversations/{conversation_id}/messages",
    response_model=AgentConversationMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_message(
    workspace_id: int,
    conversation_id: int,
    payload: AgentConversationMessageCreate,
    db: SessionDep,
    access: WorkspaceEditDep,
) -> AgentConversationMessage:
    """处理创建会话消息接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    conversation = db.get(AgentConversation, conversation_id)
    if conversation is None or conversation.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    message = AgentConversationMessage(
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        author_user_id=access.user.id,
        role="user",
        content=payload.content,
        structured_content=payload.structured_content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.post(
    "/workspaces/{workspace_id}/agent/tasks",
    response_model=AgentTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_task(
    workspace_id: int,
    payload: AgentTaskCreate,
    db: SessionDep,
    access: WorkspaceEditDep,
) -> AgentTask:
    """处理创建任务接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    try:
        task, _run, _event = create_agent_task(
            db,
            workspace_id=workspace_id,
            requested_by=access.user,
            payload=payload,
        )
        db.commit()
    except AgentTaskConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AgentTaskStateError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    try:
        kick_outbox_dispatcher()
    except Exception:
        # Outbox 已与 Task 同事务提交，瞬时队列故障由 maintenance worker 后续重投。
        pass
    db.refresh(task)
    return task


@router.get("/workspaces/{workspace_id}/agent/tasks", response_model=list[AgentTaskRead])
def list_tasks(
    workspace_id: int,
    db: SessionDep,
    access: WorkspaceDep,
    task_status: AgentTaskStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AgentTask]:
    """处理查询tasks接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    statement = select(AgentTask).where(AgentTask.workspace_id == workspace_id)
    if task_status is not None:
        statement = statement.where(AgentTask.status == task_status)
    return list(db.scalars(statement.order_by(AgentTask.id.desc()).limit(limit)).all())


@router.get("/workspaces/{workspace_id}/agent/tasks/{task_id}", response_model=AgentTaskRead)
def get_task(workspace_id: int, task_id: int, db: SessionDep, access: WorkspaceDep) -> AgentTask:
    """处理获取任务接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    _require_path_workspace(workspace_id, access)
    return _task_or_404(db, workspace_id=workspace_id, task_id=task_id)


@router.get(
    "/workspaces/{workspace_id}/agent/tasks/{task_id}/runs",
    response_model=list[AgentRunRead],
)
def list_task_runs(
    workspace_id: int,
    task_id: int,
    db: SessionDep,
    access: WorkspaceDep,
) -> list[AgentRun]:
    """处理查询任务runs接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    _task_or_404(db, workspace_id=workspace_id, task_id=task_id)
    return list(
        db.scalars(
            select(AgentRun)
            .where(AgentRun.workspace_id == workspace_id, AgentRun.task_id == task_id)
            .order_by(AgentRun.id.desc())
        ).all()
    )


@router.post(
    "/workspaces/{workspace_id}/agent/tasks/{task_id}/cancel",
    response_model=AgentTaskRead,
)
def cancel_task(
    workspace_id: int,
    task_id: int,
    db: SessionDep,
    access: WorkspaceEditDep,
) -> AgentTask:
    """处理取消任务接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    task = _task_or_404(db, workspace_id=workspace_id, task_id=task_id, for_update=True)
    try:
        cancel_agent_task(db, task=task)
        db.commit()
    except AgentTaskStateError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.refresh(task)
    return task


@router.get("/workspaces/{workspace_id}/agent/approvals", response_model=list[AgentApprovalRead])
def list_approvals(
    workspace_id: int,
    db: SessionDep,
    access: WorkspaceDep,
    approval_status: AgentApprovalStatus | None = AgentApprovalStatus.PENDING,
) -> list[AgentApproval]:
    """查询当前 Workspace 的审批列表，并可按审批状态过滤。"""
    # 路径 Workspace 必须与认证依赖解析结果一致，避免通过修改 URL 查看其他租户审批。
    _require_path_workspace(workspace_id, access)
    statement = select(AgentApproval).where(AgentApproval.workspace_id == workspace_id)
    if approval_status is not None:
        statement = statement.where(AgentApproval.status == approval_status)
    return list(db.scalars(statement.order_by(AgentApproval.id.desc())).all())


@router.post(
    "/workspaces/{workspace_id}/agent/approvals/{approval_id}/decision",
    response_model=AgentApprovalRead,
)
def decide_approval(
    workspace_id: int,
    approval_id: int,
    payload: AgentApprovalDecisionCreate,
    db: SessionDep,
    access: WorkspaceEditDep,
) -> AgentApproval:
    """处理处理决策审批接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    approval = db.scalar(
        select(AgentApproval)
        .where(AgentApproval.id == approval_id, AgentApproval.workspace_id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    try:
        event = decide_agent_approval(
            db,
            approval=approval,
            reviewer=access.user,
            reviewer_role=access.role,
            decision=payload.decision,
            note=payload.note,
            decision_payload=payload.decision_payload,
            edited_output=payload.edited_output,
        )
        db.commit()
    except AgentApprovalExpiredError as exc:
        # 过期本身是需要持久化的终态，不能随 409 响应一起回滚。
        db.commit()
        raise CodedHTTPException(
            status.HTTP_409_CONFLICT, str(exc), code=APPR_EXPIRED
        ) from exc
    except AgentTaskStateError as exc:
        db.rollback()
        raise CodedHTTPException(
            status.HTTP_409_CONFLICT, str(exc), code=APPR_ALREADY_DECIDED
        ) from exc
    if event is not None:
        try:
            kick_outbox_dispatcher()
        except Exception:
            pass
    db.refresh(approval)
    return approval


@router.get("/workspaces/{workspace_id}/agent/memories", response_model=list[AgentMemoryRead])
def list_memories(
    workspace_id: int,
    db: SessionDep,
    access: WorkspaceDep,
    include_inactive: bool = False,
) -> list[AgentMemory]:
    """处理查询memories接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    statement = select(AgentMemory).where(AgentMemory.workspace_id == workspace_id)
    if access.role != "owner":
        statement = statement.where(
            or_(
                AgentMemory.scope_type != "user",
                AgentMemory.scope_id == str(access.user.id),
            )
        )
    if not include_inactive:
        statement = statement.where(AgentMemory.status == AgentMemoryStatus.ACTIVE)
    return list(db.scalars(statement.order_by(AgentMemory.id.desc())).all())


@router.post(
    "/workspaces/{workspace_id}/agent/memories",
    response_model=AgentMemoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_memory(
    workspace_id: int,
    payload: AgentMemoryCreate,
    db: SessionDep,
    access: WorkspaceEditDep,
) -> AgentMemory:
    """处理创建记忆接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    try:
        memory = create_agent_memory(
            db,
            workspace_id=workspace_id,
            created_by=access.user,
            payload=payload,
        )
        db.commit()
    except (AgentTaskStateError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    db.refresh(memory)
    return memory


@router.post(
    "/workspaces/{workspace_id}/agent/memories/{memory_id}/revoke",
    response_model=AgentMemoryRead,
)
def revoke_memory(
    workspace_id: int,
    memory_id: int,
    db: SessionDep,
    access: WorkspaceEditDep,
) -> AgentMemory:
    """处理撤销记忆接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    _require_path_workspace(workspace_id, access)
    memory = db.get(AgentMemory, memory_id)
    if memory is None or memory.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    if (
        memory.scope_type == "user"
        and access.role != "owner"
        and memory.scope_id != str(access.user.id)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot revoke another user's memory")
    try:
        revoke_agent_memory(memory)
        db.commit()
    except AgentTaskStateError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.refresh(memory)
    return memory


def _require_path_workspace(workspace_id: int, access: WorkspaceAccess) -> None:
    """处理校验并获取pathWorkspace接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    if access.workspace.id != workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace path does not match membership")


def _task_or_404(
    db: Session,
    *,
    workspace_id: int,
    task_id: int,
    for_update: bool = False,
) -> AgentTask:
    """处理任务or404接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    statement = select(AgentTask).where(
        AgentTask.id == task_id,
        AgentTask.workspace_id == workspace_id,
    )
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    task = db.scalar(statement)
    if task is None or task.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent task not found")
    return task


def _agent_read(definition) -> AgentDefinitionRead:
    """处理Agent读取接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    return AgentDefinitionRead(
        key=definition.key,
        version=definition.version,
        description=definition.description,
        tools=sorted(definition.tool_allowlist),
    )
