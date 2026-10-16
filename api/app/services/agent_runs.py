from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agents.contracts import (
    AgentDraftOutput,
    HarnessEvent,
    ProductContext,
    ReviewResumePayload,
)
from app.agents.definitions import (
    HUMAN_REVIEW_GATE,
    VERSION_MANIFEST,
    WORKFLOW_KEY,
    WORKFLOW_VERSION,
)
from app.agents.graph import AgentWorkflowDependencies, build_product_operation_graph
from app.agents.harness import redact_snapshot
from app.agents.persistence import open_postgres_checkpointer
from app.agents.registry import get_workflow, is_workflow_enabled
from app.agents.specialists import default_completion_client
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    AgentReviewDecision,
    AgentApproval,
    AgentApprovalStatus,
    AgentRiskLevel,
    AgentRun,
    AgentRunEvent,
    AgentRunOperation,
    AgentRunReview,
    AgentRunStatus,
    AgentTask,
    AgentTaskStatus,
    CreativePlan,
    CreativePlanType,
    MembershipStatus,
    Product,
    ProductDiagnosis,
    OutboxEvent,
    User,
    UserStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)
from app.services.agent_leases import (
    AgentLeaseLostError,
    agent_lease_heartbeat,
    create_lease_owner,
    renew_active_lease,
    require_active_lease,
)


ACTIVE_AGENT_RUN_STATUSES = {
    AgentRunStatus.QUEUED,
    AgentRunStatus.RUNNING,
    AgentRunStatus.AWAITING_REVIEW,
    AgentRunStatus.RESUME_QUEUED,
}
CheckpointerFactory = Callable[[], AbstractContextManager[Any]]


class AgentRunConflictError(RuntimeError):
    pass


class AgentRunStateError(RuntimeError):
    pass


def create_agent_run_record(db: Session, *, product: Product, requested_by: User) -> AgentRun:
    """创建Agent执行记录；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    active_run = db.scalar(
        select(AgentRun)
        .where(
            AgentRun.product_id == product.id,
            AgentRun.status.in_(ACTIVE_AGENT_RUN_STATUSES),
        )
        .order_by(AgentRun.id.desc())
        .with_for_update()
    )
    if active_run is not None:
        raise AgentRunConflictError(f"Product already has active agent run {active_run.id}")

    settings = get_settings()
    task = None
    workspace = db.get(Workspace, product.workspace_id) if product.workspace_id is not None else None
    if workspace is not None and is_workflow_enabled(
        workspace.settings,
        "product_diagnosis_optimization",
    ):
        workflow = get_workflow("product_diagnosis_optimization")
        task = AgentTask(
            workspace_id=product.workspace_id,
            requested_by_user_id=requested_by.id,
            workflow_key=workflow.key,
            workflow_version=workflow.version,
            title=workflow.title,
            intent="从商品工作台发起诊断与优化",
            status=AgentTaskStatus.QUEUED,
            risk_level=AgentRiskLevel.R2,
            context_scope={"product_id": product.id, "store_id": product.store_id},
            input_payload={},
            result_summary={},
            version_manifest=workflow.version_manifest,
        )
        db.add(task)
        db.flush()
    run = AgentRun(
        thread_id=str(uuid4()),
        workspace_id=product.workspace_id,
        task_id=task.id if task is not None else None,
        product_id=product.id,
        requested_by_user_id=requested_by.id,
        workflow_key=task.workflow_key if task is not None else WORKFLOW_KEY,
        workflow_version=task.workflow_version if task is not None else WORKFLOW_VERSION,
        attempt=1,
        queue_name=settings.celery_agent_queue,
        status=AgentRunStatus.QUEUED,
        revision_count=0,
        max_revisions=settings.agent_max_revisions,
        budget={"max_total_tokens": settings.agent_max_total_tokens},
        usage={},
        version_manifest=task.version_manifest if task is not None else VERSION_MANIFEST,
        context_snapshot={},
        draft_output={},
        quality_report={},
        final_output={},
        timeout_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    db.add(run)
    db.flush()
    db.add(
        AgentRunEvent(
            run_id=run.id,
            event_type="queued",
            status=AgentRunStatus.QUEUED.value,
            message="商品运营 Agent 已进入 Celery 队列。",
            output_snapshot={"workflow": WORKFLOW_KEY, "version": WORKFLOW_VERSION},
        )
    )
    if task is not None:
        db.add(
            OutboxEvent(
                workspace_id=product.workspace_id,
                aggregate_type="agent_run",
                aggregate_id=str(run.id),
                event_type="workflow.run.requested",
                payload={"run_id": run.id, "resume_payload": None},
                idempotency_key=f"agent-run:{run.id}:start",
                status="pending",
                attempts=0,
                available_at=datetime.now(UTC),
            )
        )
    return run


def dispatch_agent_run(run_id: int, resume_payload: dict[str, Any] | None = None) -> None:
    """调度Agent执行；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    with SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        if run is not None and run.task_id is not None:
            if resume_payload is not None:
                event = OutboxEvent(
                    workspace_id=run.workspace_id,
                    aggregate_type="agent_run",
                    aggregate_id=str(run.id),
                    event_type="workflow.run.requested",
                    payload={"run_id": run.id, "resume_payload": resume_payload},
                    idempotency_key=f"agent-run:{run.id}:legacy-review",
                    status="pending",
                    attempts=0,
                    available_at=datetime.now(UTC),
                )
                db.add(event)
                db.commit()
            from app.services.outbox import kick_outbox_dispatcher

            try:
                kick_outbox_dispatcher()
            except Exception:
                # Outbox 已持久化，瞬时 Redis 故障不能把可恢复运行误标记为失败。
                pass
            return
    from app.worker.tasks import run_agent_workflow_task

    settings = get_settings()
    run_agent_workflow_task.apply_async(
        args=[run_id, resume_payload],
        queue=settings.celery_agent_queue,
    )


def submit_agent_review(
    db: Session,
    *,
    run: AgentRun,
    reviewer: User,
    payload: ReviewResumePayload,
) -> AgentRunReview:
    """提交Agent审核；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == run.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise AgentRunStateError("Agent run does not exist")
    if run.status != AgentRunStatus.AWAITING_REVIEW:
        raise AgentRunStateError("Agent run is not awaiting review")
    if run.cancel_requested_at is not None:
        raise AgentRunStateError("Agent run cancellation was requested")
    existing_review = db.scalar(select(AgentRunReview.id).where(AgentRunReview.run_id == run.id))
    if existing_review is not None:
        raise AgentRunStateError("Agent run already has a review decision")

    review = AgentRunReview(
        run_id=run.id,
        reviewed_by_user_id=reviewer.id,
        decision=AgentReviewDecision(payload.decision),
        edited_output=(
            payload.edited_output.model_dump(mode="json")
            if payload.edited_output is not None
            else {}
        ),
        note=payload.note,
    )
    run.status = AgentRunStatus.RESUME_QUEUED
    run.current_agent = HUMAN_REVIEW_GATE
    if run.task_id is not None:
        task = db.get(AgentTask, run.task_id)
        if task is not None:
            task.status = AgentTaskStatus.QUEUED
        approval = db.scalar(
            select(AgentApproval)
            .where(
                AgentApproval.run_id == run.id,
                AgentApproval.action_key == "workflow.accept_result",
            )
            .with_for_update()
        )
        if approval is not None and approval.status == AgentApprovalStatus.PENDING:
            now = datetime.now(UTC)
            if approval.expires_at is not None and _is_due(approval.expires_at, now):
                raise AgentRunStateError("Agent approval has expired")
            approval.status = (
                AgentApprovalStatus.REJECTED
                if payload.decision == "reject"
                else AgentApprovalStatus.APPROVED
            )
            approval.decided_by_user_id = reviewer.id
            approval.decision_payload = payload.model_dump(mode="json")
            approval.note = payload.note
            approval.decided_at = datetime.now(UTC)
    db.add(review)
    db.add(
        AgentRunEvent(
            run_id=run.id,
            event_type="resume_queued",
            agent_name=HUMAN_REVIEW_GATE,
            operation_name="interrupt.resume",
            status=AgentRunStatus.RESUME_QUEUED.value,
            message="人工审核决定已提交，等待 Celery 恢复工作流。",
            input_snapshot=redact_snapshot(payload.model_dump(mode="json")),
        )
    )
    db.flush()
    return review


def _is_due(value: datetime, now: datetime) -> bool:
    """判断到期；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    if value.tzinfo is None:
        return value <= now.replace(tzinfo=None)
    return value <= now


def run_agent_workflow(
    run_id: int,
    resume_payload: dict[str, Any] | None = None,
    *,
    checkpointer_factory: CheckpointerFactory = open_postgres_checkpointer,
    workflow_dependencies: AgentWorkflowDependencies | None = None,
    lease_owner: str | None = None,
) -> None:
    """执行Agent工作流；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    lease_owner = lease_owner or create_lease_owner("product-workflow", run_id)
    run_snapshot = _claim_agent_run(
        run_id,
        is_resume=resume_payload is not None,
        lease_owner=lease_owner,
    )
    if run_snapshot is None:
        return

    dependencies = workflow_dependencies or AgentWorkflowDependencies(
        load_product_context=_load_product_context,
        completion_client=default_completion_client,
        record_event=lambda target_run_id, event: _record_harness_event(
            target_run_id,
            event,
            lease_owner=lease_owner,
        ),
        finalize_run=lambda target_run_id, review, output: _finalize_agent_run(
            target_run_id,
            review,
            output,
            lease_owner=lease_owner,
        ),
    )
    config = {
        "configurable": {"thread_id": run_snapshot["thread_id"]},
        "recursion_limit": 24,
    }
    with agent_lease_heartbeat(run_id, lease_owner), checkpointer_factory() as checkpointer:
        graph = build_product_operation_graph(checkpointer=checkpointer, deps=dependencies)
        if resume_payload is None:
            graph.invoke(
                {
                    "run_id": run_id,
                    "product_id": run_snapshot["product_id"],
                    "revision_count": run_snapshot["revision_count"],
                    "max_revisions": run_snapshot["max_revisions"],
                    "budget": run_snapshot["budget"],
                    "usage": run_snapshot["usage"],
                },
                config=config,
            )
        else:
            graph.invoke(Command(resume=resume_payload), config=config)
        graph_state = graph.get_state(config)
        _sync_agent_run_state(
            run_id,
            graph_state.values,
            interrupted=bool(graph_state.next),
            lease_owner=lease_owner,
        )


def mark_agent_run_task_error(
    run_id: int,
    error: Exception,
    *,
    will_retry: bool,
    is_resume: bool,
    lease_owner: str | None = None,
) -> bool:
    """标记Agent执行任务错误；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    with SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        if run is None or run.status in {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.REJECTED,
            AgentRunStatus.CANCELLED,
        }:
            return False
        if lease_owner is not None and run.lease_owner != lease_owner:
            return False
        task = db.get(AgentTask, run.task_id) if run.task_id else None
        if run.cancel_requested_at is not None:
            now = datetime.now(UTC)
            run.status = AgentRunStatus.CANCELLED
            run.finished_at = now
            run.lease_owner = None
            run.lease_expires_at = None
            if task is not None:
                task.status = AgentTaskStatus.CANCELLED
                task.finished_at = now
            db.commit()
            return False
        run.status = (
            AgentRunStatus.RESUME_QUEUED
            if will_retry and is_resume
            else AgentRunStatus.QUEUED
            if will_retry
            else AgentRunStatus.FAILED
        )
        run.error = str(error)[:2000]
        run.lease_owner = None
        run.lease_expires_at = None
        if task is not None:
            task.status = AgentTaskStatus.QUEUED if will_retry else AgentTaskStatus.FAILED
            task.error = run.error
        if not will_retry:
            run.finished_at = datetime.now(UTC)
            if task is not None:
                task.finished_at = run.finished_at
        db.add(
            AgentRunEvent(
                run_id=run.id,
                event_type="task_retry" if will_retry else "task_failed",
                status=run.status.value,
                message=str(error)[:1000],
            )
        )
        db.commit()
        return will_retry


def mark_agent_run_dispatch_failed(run_id: int, error: Exception) -> None:
    """标记Agent执行调度失败；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    with SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        if run is None:
            return
        run.status = AgentRunStatus.FAILED
        run.error = str(error)[:2000]
        run.finished_at = datetime.now(UTC)
        db.add(
            AgentRunEvent(
                run_id=run_id,
                event_type="dispatch_failed",
                status=AgentRunStatus.FAILED.value,
                message=str(error)[:1000],
            )
        )
        db.commit()


def _claim_agent_run(
    run_id: int,
    *,
    is_resume: bool,
    lease_owner: str,
) -> dict[str, Any] | None:
    """认领Agent执行；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    allowed_statuses = (
        {AgentRunStatus.RESUME_QUEUED}
        if is_resume
        else {AgentRunStatus.QUEUED}
    )
    with SessionLocal() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if (
            run is None
            or run.status not in allowed_statuses
            or run.cancel_requested_at is not None
        ):
            return None
        run.status = AgentRunStatus.RUNNING
        run.error = None
        run.started_at = run.started_at or datetime.now(UTC)
        run.lease_owner = lease_owner
        run.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
        if run.task_id is not None:
            task = db.get(AgentTask, run.task_id)
            if task is not None:
                if not _task_requester_has_active_access(db, task):
                    now = datetime.now(UTC)
                    run.status = AgentRunStatus.CANCELLED
                    run.error = "Task requester no longer has active Workspace access"
                    run.finished_at = now
                    run.lease_owner = None
                    run.lease_expires_at = None
                    task.status = AgentTaskStatus.CANCELLED
                    task.error = run.error
                    task.finished_at = now
                    db.commit()
                    return None
                task.status = AgentTaskStatus.RUNNING
                task.error = None
        db.add(
            AgentRunEvent(
                run_id=run.id,
                event_type="workflow_resumed" if is_resume else "workflow_started",
                status=AgentRunStatus.RUNNING.value,
                message="Celery worker 开始执行商品运营 Agent。",
            )
        )
        snapshot = {
            "thread_id": run.thread_id,
            "product_id": run.product_id,
            "revision_count": run.revision_count,
            "max_revisions": run.max_revisions,
            "budget": run.budget,
            "usage": run.usage,
        }
        db.commit()
        return snapshot


def _load_product_context(product_id: int) -> ProductContext:
    """加载商品上下文；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    with SessionLocal() as db:
        product = db.scalar(
            select(Product)
            .where(Product.id == product_id)
            .options(selectinload(Product.competitors))
        )
        if product is None:
            raise AgentRunStateError("Product not found while building agent context")
        return ProductContext(
            product_id=product.id,
            name=product.name,
            platform=product.platform.value,
            category=product.category,
            price=str(product.price) if product.price is not None else None,
            cost=str(product.cost) if product.cost is not None else None,
            target_audience=product.target_audience,
            selling_points=product.selling_points,
            product_url=product.product_url,
            images=product.images,
            competitors=[
                {
                    "name": competitor.name,
                    "platform": competitor.platform.value if competitor.platform else None,
                    "price": str(competitor.price) if competitor.price is not None else None,
                    "sales_hint": competitor.sales_hint,
                    "title": competitor.title,
                    "selling_points": competitor.selling_points,
                    "review_keywords": competitor.review_keywords,
                }
                for competitor in product.competitors
            ],
        )


def _record_harness_event(
    run_id: int,
    event: HarnessEvent,
    *,
    lease_owner: str | None = None,
) -> None:
    """记录harness事件；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    with SessionLocal() as db:
        run = require_active_lease(db, run_id=run_id, lease_owner=lease_owner, for_update=True)
        renew_active_lease(db, run=run)
        if event.agent_name:
            run.current_agent = event.agent_name
        db.add(
            AgentRunEvent(
                run_id=run_id,
                event_type=event.event_type,
                agent_name=event.agent_name,
                operation_name=event.operation_name,
                status=event.status,
                message=event.message,
                input_snapshot=redact_snapshot(event.input_snapshot),
                output_snapshot=redact_snapshot(event.output_snapshot),
                metrics=redact_snapshot(event.metrics),
                trace_id=event.trace_id,
                span_id=event.span_id,
            )
        )
        db.commit()


def _sync_agent_run_state(
    run_id: int,
    values: dict[str, Any],
    *,
    interrupted: bool,
    lease_owner: str | None = None,
) -> None:
    """同步Agent执行状态；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    with SessionLocal() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None:
            raise AgentRunStateError("Agent run not found while syncing state")
        if interrupted:
            run = require_active_lease(
                db,
                run_id=run_id,
                lease_owner=lease_owner,
                for_update=True,
            )
            run.status = AgentRunStatus.AWAITING_REVIEW
            run.lease_owner = None
            run.lease_expires_at = None
            run.current_agent = HUMAN_REVIEW_GATE
            if run.task_id is not None and run.workspace_id is not None:
                task = db.get(AgentTask, run.task_id)
                if task is not None:
                    task.status = AgentTaskStatus.AWAITING_APPROVAL
                approval = db.scalar(
                    select(AgentApproval).where(
                        AgentApproval.run_id == run.id,
                        AgentApproval.action_key == "workflow.accept_result",
                    )
                )
                if approval is None:
                    db.add(
                        AgentApproval(
                            workspace_id=run.workspace_id,
                            task_id=run.task_id,
                            run_id=run.id,
                            requested_by_user_id=run.requested_by_user_id,
                            action_key="workflow.accept_result",
                            risk_level=AgentRiskLevel.R2,
                            status=AgentApprovalStatus.PENDING,
                            request_payload={
                                "draft_output": run.draft_output,
                                "quality_report": run.quality_report,
                            },
                            decision_payload={},
                            expires_at=datetime.now(UTC) + timedelta(hours=24),
                        )
                    )
            db.add(
                AgentRunEvent(
                    run_id=run.id,
                    event_type="human_review_requested",
                    agent_name=HUMAN_REVIEW_GATE,
                    operation_name="interrupt.wait",
                    status=AgentRunStatus.AWAITING_REVIEW.value,
                    message="草稿已生成，等待人工确认、编辑或驳回。",
                    output_snapshot={
                        "quality_report": run.quality_report,
                        "revision_count": run.revision_count,
                    },
                )
            )
        elif values.get("final_status") == "rejected":
            if run.status != AgentRunStatus.REJECTED:
                raise AgentLeaseLostError("Workflow rejection was not committed by fenced finalize")
            run.current_agent = None
            if run.task_id is not None:
                task = db.get(AgentTask, run.task_id)
                if task is not None:
                    task.status = AgentTaskStatus.CANCELLED
                    task.finished_at = run.finished_at
        elif values.get("final_status") == "completed":
            if run.status != AgentRunStatus.COMPLETED:
                raise AgentLeaseLostError("Workflow completion was not committed by fenced finalize")
            run.current_agent = None
            run.final_output = redact_snapshot(values.get("final_output", run.final_output))
            if run.task_id is not None:
                task = db.get(AgentTask, run.task_id)
                if task is not None:
                    task.status = AgentTaskStatus.COMPLETED
                    task.result_summary = run.final_output
                    task.finished_at = run.finished_at
        else:
            require_active_lease(
                db,
                run_id=run_id,
                lease_owner=lease_owner,
                for_update=True,
            )
        run.revision_count = values.get("revision_count", run.revision_count)
        run.usage = redact_snapshot(values.get("usage", {}))
        run.context_snapshot = redact_snapshot(values.get("context", {}))
        if values.get("diagnosis") and values.get("creative_plans"):
            run.draft_output = redact_snapshot(
                {
                    "diagnosis": values["diagnosis"],
                    "creative_plans": values["creative_plans"],
                }
            )
        run.quality_report = redact_snapshot(values.get("quality_report", {}))
        db.commit()


def _finalize_agent_run(
    run_id: int,
    review: ReviewResumePayload,
    approved_output: AgentDraftOutput | None,
    *,
    lease_owner: str | None = None,
) -> dict[str, Any]:
    """完成落库Agent执行；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    operation_key = "finalize-v1"
    with SessionLocal() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None:
            raise AgentRunStateError("Agent run not found while finalizing")
        operation = db.scalar(
            select(AgentRunOperation).where(
                AgentRunOperation.run_id == run_id,
                AgentRunOperation.operation_key == operation_key,
            )
        )
        if operation is not None and operation.status == "completed":
            return operation.result
        run = require_active_lease(
            db,
            run_id=run_id,
            lease_owner=lease_owner,
            for_update=True,
        )
        if run.task_id is not None:
            task = db.get(AgentTask, run.task_id)
            if task is None or not _task_requester_has_active_access(db, task):
                raise AgentRunStateError("Task requester no longer has active Workspace access")
        if operation is None:
            operation = AgentRunOperation(
                run_id=run_id,
                operation_key=operation_key,
                status="running",
                result={},
            )
            db.add(operation)
            db.flush()

        if review.decision == "reject":
            result = {"decision": "reject", "note": review.note}
            run.status = AgentRunStatus.REJECTED
        else:
            if approved_output is None:
                raise AgentRunStateError("Approved output is required for finalization")
            diagnosis_payload = approved_output.diagnosis
            diagnosis = ProductDiagnosis(
                product_id=run.product_id,
                agent_run_id=run.id,
                source=diagnosis_payload.source,
                positioning=diagnosis_payload.positioning,
                price_band=diagnosis_payload.price_band,
                audience_insights=diagnosis_payload.audience_insights,
                pain_points=diagnosis_payload.pain_points,
                selling_point_analysis=diagnosis_payload.selling_point_analysis,
                risks=diagnosis_payload.risks,
                recommendations=diagnosis_payload.recommendations,
                raw_output={
                    "agent_run_id": run.id,
                    "workflow_version": run.workflow_version,
                    "provenance": redact_snapshot(diagnosis_payload.provenance),
                },
            )
            db.add(diagnosis)
            creative_rows = []
            for plan in approved_output.creative_plans:
                content = plan.model_dump(mode="json", exclude={"title", "source", "provenance"})
                creative_row = CreativePlan(
                    product_id=run.product_id,
                    agent_run_id=run.id,
                    type=CreativePlanType.MAIN_IMAGE,
                    title=plan.title,
                    content=content,
                    rationale=plan.angle,
                )
                db.add(creative_row)
                creative_rows.append(creative_row)
            db.flush()
            result = {
                **approved_output.model_dump(mode="json"),
                "artifacts": {
                    "diagnosis_id": diagnosis.id,
                    "creative_plan_ids": [row.id for row in creative_rows],
                },
            }
            run.status = AgentRunStatus.COMPLETED

        if run.task_id is not None:
            task = db.get(AgentTask, run.task_id)
            if task is not None:
                task.status = (
                    AgentTaskStatus.CANCELLED
                    if review.decision == "reject"
                    else AgentTaskStatus.COMPLETED
                )
                task.result_summary = redact_snapshot(result)
                task.finished_at = datetime.now(UTC)

        run.final_output = redact_snapshot(result)
        run.current_agent = None
        run.finished_at = datetime.now(UTC)
        run.lease_owner = None
        run.lease_expires_at = None
        operation.status = "completed"
        operation.result = run.final_output
        operation.completed_at = datetime.now(UTC)
        db.commit()
        return result


def _task_requester_has_active_access(db: Session, task: AgentTask) -> bool:
    """任务requesterhas有效访问；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    membership_id = db.scalar(
        select(WorkspaceMembership.id)
        .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
        .join(User, User.id == WorkspaceMembership.user_id)
        .where(
            WorkspaceMembership.workspace_id == task.workspace_id,
            WorkspaceMembership.user_id == task.requested_by_user_id,
            WorkspaceMembership.status == MembershipStatus.ACTIVE,
            Workspace.status == WorkspaceStatus.ACTIVE,
            User.status == UserStatus.ACTIVE,
        )
    )
    return membership_id is not None
