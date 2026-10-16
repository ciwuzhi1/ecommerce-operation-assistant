from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from langgraph.types import Command
from sqlalchemy import and_, or_, select

from app.agents.harness import redact_snapshot
from app.agents.persistence import open_postgres_checkpointer
from app.agents.platform_graph import PlatformWorkflowDependencies, build_platform_workflow_graph
from app.agents.registry import (
    CONTENT_PRODUCTION_AGENT,
    CREATIVE_STRATEGY_AGENT,
    GROWTH_EXPERIMENT_AGENT,
    INVENTORY_OPERATIONS_AGENT,
    MARKET_INTELLIGENCE_AGENT,
    PERFORMANCE_REVIEW_AGENT,
    PRODUCT_STRATEGY_AGENT,
    get_workflow,
)
from app.agents.tool_gateway import ToolExecutionContext, ToolGateway
from app.db.session import SessionLocal
from app.models import (
    AdExperiment,
    AdRecommendation,
    AgentApproval,
    AgentApprovalStatus,
    AgentMemory,
    AgentMemoryStatus,
    AgentRiskLevel,
    AgentRun,
    AgentRunEvent,
    AgentRunOperation,
    AgentRunStatus,
    AgentTask,
    AgentTaskStatus,
    Competitor,
    CreativePlan,
    CreativePlanType,
    InventoryItem,
    MembershipStatus,
    PerformanceRecord,
    Product,
    ProductSku,
    ReviewReport,
    Store,
    User,
    UserRole,
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


class RegisteredWorkflowStateError(RuntimeError):
    pass


def run_registered_agent_workflow(
    run_id: int,
    resume_payload: dict[str, Any] | None = None,
    *,
    lease_owner: str | None = None,
) -> None:
    """执行已注册Agent工作流；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    lease_owner = lease_owner or create_lease_owner("registered-workflow", run_id)
    with SessionLocal() as db:
        workflow_key = db.scalar(select(AgentRun.workflow_key).where(AgentRun.id == run_id))
    if workflow_key == "product_diagnosis_optimization":
        from app.services.agent_runs import run_agent_workflow

        run_agent_workflow(run_id, resume_payload, lease_owner=lease_owner)
        return

    run_snapshot = _claim_run(
        run_id,
        is_resume=resume_payload is not None,
        lease_owner=lease_owner,
    )
    if run_snapshot is None:
        return

    workflow = get_workflow(run_snapshot["workflow_key"])
    deps = PlatformWorkflowDependencies(
        load_context=_load_task_context,
        run_specialist=lambda agent_key, context, outputs: _run_specialist(
            agent_key,
            context,
            outputs,
            lease_owner=lease_owner,
        ),
        evaluate_quality=_evaluate_quality,
        finalize=lambda target_run_id, outputs, usage: _finalize_generic_run(
            target_run_id,
            outputs,
            usage,
            lease_owner=lease_owner,
        ),
        record_event=lambda target_run_id, event_type, agent_key, payload, operation_name=None: _record_event(
            target_run_id,
            event_type,
            agent_key,
            payload,
            operation_name=operation_name,
            lease_owner=lease_owner,
        ),
    )
    config = {
        "configurable": {"thread_id": run_snapshot["thread_id"]},
        "recursion_limit": 32,
    }
    with agent_lease_heartbeat(run_id, lease_owner), open_postgres_checkpointer() as checkpointer:
        graph = build_platform_workflow_graph(workflow=workflow, checkpointer=checkpointer, deps=deps)
        if resume_payload is None:
            graph.invoke(
                {
                    "run_id": run_id,
                    "task_id": run_snapshot["task_id"],
                    "workspace_id": run_snapshot["workspace_id"],
                    "context_scope": run_snapshot["context_scope"],
                },
                config=config,
            )
        else:
            graph.invoke(Command(resume=resume_payload), config=config)
        state = graph.get_state(config)
        _sync_generic_state(
            run_id,
            state.values,
            interrupted=bool(state.next),
            lease_owner=lease_owner,
        )


def mark_registered_workflow_error(
    run_id: int,
    error: Exception,
    *,
    will_retry: bool,
    lease_owner: str | None = None,
) -> bool:
    """标记已注册工作流错误；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
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
        if task is not None and not _task_requester_has_active_access(db, task):
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
            return False
        run.status = AgentRunStatus.QUEUED if will_retry else AgentRunStatus.FAILED
        run.lease_owner = None
        run.lease_expires_at = None
        run.error = str(error)[:2000]
        if task is not None:
            task.status = AgentTaskStatus.QUEUED if will_retry else AgentTaskStatus.FAILED
            task.error = run.error
            if not will_retry:
                task.finished_at = datetime.now(UTC)
        if not will_retry:
            run.finished_at = datetime.now(UTC)
        db.add(
            AgentRunEvent(
                run_id=run.id,
                event_type="task_retry" if will_retry else "task_failed",
                status=run.status.value,
                message=run.error,
            )
        )
        db.commit()
        return will_retry


def _claim_run(
    run_id: int,
    *,
    is_resume: bool,
    lease_owner: str,
) -> dict[str, Any] | None:
    """认领执行；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    allowed = (
        {AgentRunStatus.RESUME_QUEUED}
        if is_resume
        else {AgentRunStatus.QUEUED}
    )
    with SessionLocal() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None or run.status not in allowed or run.cancel_requested_at is not None:
            return None
        if run.task_id is None or run.workspace_id is None:
            raise RegisteredWorkflowStateError("Registered workflow requires Task and Workspace")
        task = db.get(AgentTask, run.task_id)
        if task is None or task.workspace_id != run.workspace_id:
            raise RegisteredWorkflowStateError("Run Task does not match Workspace")
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
        run.status = AgentRunStatus.RUNNING
        run.started_at = run.started_at or datetime.now(UTC)
        run.lease_owner = lease_owner
        run.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
        run.error = None
        task.status = AgentTaskStatus.RUNNING
        task.error = None
        db.add(
            AgentRunEvent(
                run_id=run.id,
                event_type="workflow_resumed" if is_resume else "workflow_started",
                status=AgentRunStatus.RUNNING.value,
                message="Celery worker 开始执行版本化 Agent 工作流。",
            )
        )
        snapshot = {
            "thread_id": run.thread_id,
            "task_id": task.id,
            "workspace_id": run.workspace_id,
            "workflow_key": run.workflow_key,
            "context_scope": task.context_scope,
            "lease_owner": lease_owner,
        }
        db.commit()
        return snapshot


def _load_task_context(task_id: int) -> dict[str, Any]:
    """加载任务上下文；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    with SessionLocal() as db:
        task = db.get(AgentTask, task_id)
        if task is None:
            raise RegisteredWorkflowStateError("Agent Task not found")
        context: dict[str, Any] = {
            "workspace_id": task.workspace_id,
            "run_id": db.scalar(
                select(AgentRun.id)
                .where(AgentRun.task_id == task.id)
                .order_by(AgentRun.id.desc())
                .limit(1)
            ),
            "requested_by_user_id": task.requested_by_user_id,
            "workflow_key": task.workflow_key,
            "scope": task.context_scope,
            "input": task.input_payload,
        }
        membership = db.scalar(
            select(WorkspaceMembership)
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
        if membership is None:
            raise RegisteredWorkflowStateError("Task requester no longer has active Workspace access")
        context["workspace_role"] = membership.role.value
        product_id = _optional_int(task.context_scope.get("product_id"))
        store_id = _optional_int(task.context_scope.get("store_id"))
        if product_id is not None:
            product = db.get(Product, product_id)
            if product is None or product.workspace_id != task.workspace_id:
                raise RegisteredWorkflowStateError("Product context is outside Workspace")
            context["product"] = _product_context(db, product)
        if store_id is not None:
            store = db.get(Store, store_id)
            if store is None or store.workspace_id != task.workspace_id:
                raise RegisteredWorkflowStateError("Store context is outside Workspace")
            context["store"] = _store_context(db, store)
        context["memories"] = _memory_context(db, task)
        return redact_snapshot(context)


def _task_requester_has_active_access(db, task: AgentTask) -> bool:
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


def _product_context(db, product: Product) -> dict[str, Any]:
    """商品上下文；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    competitors = db.scalars(select(Competitor).where(Competitor.product_id == product.id)).all()
    records = db.scalars(
        select(PerformanceRecord)
        .where(PerformanceRecord.product_id == product.id)
        .order_by(PerformanceRecord.period_end.desc())
        .limit(12)
    ).all()
    skus = db.scalars(select(ProductSku).where(ProductSku.product_id == product.id)).all()
    inventory_rows = []
    for sku in skus:
        item = db.scalar(select(InventoryItem).where(InventoryItem.sku_id == sku.id))
        inventory_rows.append(
            {
                "sku_id": sku.id,
                "sku_code": sku.sku_code,
                "name": sku.name,
                "quantity": item.quantity if item else 0,
                "locked_quantity": item.locked_quantity if item else 0,
                "warning_threshold": item.warning_threshold if item else 0,
            }
        )
    return {
        "id": product.id,
        "store_id": product.store_id,
        "name": product.name,
        "platform": product.platform.value,
        "category": product.category,
        "price": _decimal_text(product.price),
        "cost": _decimal_text(product.cost),
        "target_audience": product.target_audience,
        "selling_points": product.selling_points,
        "images": product.images,
        "competitors": [
            {
                "id": row.id,
                "name": row.name,
                "platform": row.platform.value,
                "price": _decimal_text(row.price),
                "selling_points": row.selling_points,
                "review_keywords": row.review_keywords,
            }
            for row in competitors
        ],
        "performance": [
            {
                "period_start": row.period_start.isoformat(),
                "period_end": row.period_end.isoformat(),
                "impressions": row.impressions,
                "clicks": row.clicks,
                "ctr": _decimal_text(row.ctr),
                "conversions": row.conversions,
                "conversion_rate": _decimal_text(row.conversion_rate),
                "spend": _decimal_text(row.spend),
                "revenue": _decimal_text(row.revenue),
                "roi": _decimal_text(row.roi),
            }
            for row in records
        ],
        "inventory": inventory_rows,
        "creative_plan_count": db.scalar(
            select(CreativePlan.id).where(CreativePlan.product_id == product.id).limit(1)
        )
        is not None,
        "ad_recommendation_count": len(
            db.scalars(select(AdRecommendation).where(AdRecommendation.product_id == product.id)).all()
        ),
        "ad_experiment_count": len(
            db.scalars(select(AdExperiment).where(AdExperiment.product_id == product.id)).all()
        ),
    }


def _store_context(db, store: Store) -> dict[str, Any]:
    """装配店铺级工作流上下文，限定商品查询只能落在当前 Workspace 和店铺。"""
    # 显式叠加 Workspace 条件，防止只凭 store_id 查询时把其他租户商品带入 Agent 上下文。
    products = db.scalars(
        select(Product).where(Product.store_id == store.id, Product.workspace_id == store.workspace_id)
    ).all()
    return {
        "id": store.id,
        "name": store.name,
        "platform": store.platform.value,
        "status": store.status.value,
        "products": [_product_context(db, product) for product in products],
    }


def _memory_context(db, task: AgentTask) -> list[dict[str, Any]]:
    """记忆上下文；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    now = datetime.now(UTC)
    product_id = _optional_int(task.context_scope.get("product_id"))
    store_id = _optional_int(task.context_scope.get("store_id"))
    if store_id is None and product_id is not None:
        store_id = db.scalar(select(Product.store_id).where(Product.id == product_id))
    scope_filters = [
        and_(
            AgentMemory.scope_type == "workspace",
            or_(AgentMemory.scope_id.is_(None), AgentMemory.scope_id == str(task.workspace_id)),
        ),
        and_(
            AgentMemory.scope_type == "user",
            AgentMemory.scope_id == str(task.requested_by_user_id),
        ),
    ]
    if product_id is not None:
        scope_filters.append(
            and_(AgentMemory.scope_type == "product", AgentMemory.scope_id == str(product_id))
        )
    if store_id is not None:
        scope_filters.append(
            and_(AgentMemory.scope_type == "store", AgentMemory.scope_id == str(store_id))
        )
    rows = db.scalars(
        select(AgentMemory)
        .where(
            AgentMemory.workspace_id == task.workspace_id,
            AgentMemory.status == AgentMemoryStatus.ACTIVE,
            or_(AgentMemory.effective_at.is_(None), AgentMemory.effective_at <= now),
            or_(AgentMemory.expires_at.is_(None), AgentMemory.expires_at > now),
            or_(*scope_filters),
        )
        .order_by(AgentMemory.id.desc())
        .limit(50)
    ).all()
    return [
        {
            "scope_type": row.scope_type,
            "scope_id": row.scope_id,
            "memory_key": row.memory_key,
            "schema_version": row.schema_version,
            "content": row.content,
        }
        for row in rows
    ]


def _run_specialist(
    agent_key: str,
    context: dict[str, Any],
    previous_outputs: dict[str, Any],
    *,
    lease_owner: str | None = None,
) -> tuple[dict[str, Any], str]:
    """执行领域 Agent，返回（输出, 本次实际执行的操作名）。

    操作名取自网关真实执行过的工具，供运行事件记录「操作名」字段（DesignSpec §8）；
    未走网关的纯汇总分支没有对应工具，标注为 `{agent}.summarize`。
    """
    gateway = ToolGateway(
        ToolExecutionContext(
            workspace_id=int(context["workspace_id"]),
            user_id=int(context["requested_by_user_id"]),
            workspace_role=UserRole(context["workspace_role"]),
            run_id=int(context["run_id"]),
            lease_owner=lease_owner,
        )
    )
    result = _dispatch_specialist(gateway, agent_key, context, previous_outputs)
    return result, gateway.last_tool_key or f"{agent_key}.summarize"


def _dispatch_specialist(
    gateway: ToolGateway,
    agent_key: str,
    context: dict[str, Any],
    previous_outputs: dict[str, Any],
) -> dict[str, Any]:
    """按角色分派到对应工具；只交换结构化 Agent 状态或受控工具结果。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    product = context.get("product") or {}
    store = context.get("store") or {}
    if agent_key == MARKET_INTELLIGENCE_AGENT:
        competitors = product.get("competitors", [])
        if not competitors and store:
            competitors = [
                competitor
                for store_product in store.get("products", [])
                for competitor in store_product.get("competitors", [])
            ]
        result = {
            "summary": f"当前纳入 {len(competitors)} 个竞品样本。",
            "signals": [
                f"{row['name']}：价格 {row.get('price') or '未录入'}，卖点 {', '.join(row.get('selling_points') or ['未录入'])}"
                for row in competitors[:8]
            ],
            "actions": ["补充竞品最新价格和主图快照", "按卖点与价格带建立可验证对照"],
            "evidence": {"competitor_ids": [row["id"] for row in competitors]},
        }
        if context.get("workflow_key") == "competitor_continuous_monitoring":
            result["monitor_snapshots"] = gateway.execute(
                agent_key=agent_key,
                tool_key="competitor.monitor.run",
                input_payload={
                    "product_id": product.get("id"),
                    "store_id": store.get("id"),
                },
            )
        return result
    if agent_key == PRODUCT_STRATEGY_AGENT:
        if not product:
            store_products = store.get("products", [])
            return {
                "summary": f"本次巡检 {len(store_products)} 个商品。",
                "priorities": [
                    {
                        "product_id": item.get("id"),
                        "product_name": item.get("name"),
                        "risks": _product_risks(item),
                    }
                    for item in store_products[:20]
                ],
                "actions": ["优先处理资料、库存或经营数据缺口最大的商品"],
            }
        return gateway.execute(
            agent_key=agent_key,
            tool_key="diagnosis.draft",
            input_payload={"product_id": product["id"]},
        )
    if agent_key == CREATIVE_STRATEGY_AGENT:
        return gateway.execute(
            agent_key=agent_key,
            tool_key="creative.plan.draft",
            input_payload={"product_id": product["id"]},
        )
    if agent_key == CONTENT_PRODUCTION_AGENT:
        creative = previous_outputs.get(CREATIVE_STRATEGY_AGENT, {})
        plans = [
            *[("main_image", plan) for plan in creative.get("main_image_plans", [])],
            *[("video_script", plan) for plan in creative.get("video_script_plans", [])],
        ]
        return {
            "asset_requests": [
                {
                    "kind": kind,
                    "status": "draft",
                    "prompt": (
                        f"{product.get('name', '商品')}，"
                        f"{plan.get('rationale') or plan.get('title') or '创意方向'}，移动端电商内容"
                    ),
                }
                for kind, plan in plans
            ],
            "requires_human_selection": True,
        }
    if agent_key == GROWTH_EXPERIMENT_AGENT:
        recommendation = gateway.execute(
            agent_key=agent_key,
            tool_key="ad.recommendation.draft",
            input_payload={"product_id": product["id"]},
        )
        links = gateway.execute(
            agent_key=agent_key,
            tool_key="promotion.link.draft",
            input_payload={"product_id": product["id"]},
        )
        return {
            "recommendation": recommendation,
            "promotion_link_drafts": links,
            "guardrails": ["只生成实验草稿", "不调用广告平台", "不执行资金操作"],
        }
    if agent_key == PERFORMANCE_REVIEW_AGENT:
        if product.get("id"):
            return gateway.execute(
                agent_key=agent_key,
                tool_key="performance.review.draft",
                input_payload={"product_id": product["id"]},
            )
        records = product.get("performance", [])
        if not records and store:
            records = [item for row in store.get("products", []) for item in row.get("performance", [])]
        return {
            "summary": f"本次纳入 {len(records)} 条经营记录。",
            "insights": _performance_insights(records),
            "next_actions": ["补齐缺失归因字段", "对高低表现素材做结构化对照"],
            "evidence_count": len(records),
        }
    if agent_key == INVENTORY_OPERATIONS_AGENT:
        target_store_id = store.get("id") or product.get("store_id")
        if target_store_id:
            return gateway.execute(
                agent_key=agent_key,
                tool_key="inventory.advice.draft",
                input_payload={"store_id": target_store_id},
            )
        inventory = product.get("inventory", [])
        if not inventory and store:
            inventory = [item for row in store.get("products", []) for item in row.get("inventory", [])]
        return {
            "risks": _inventory_risks(inventory),
            "actions": ["先核对库存快照与在途数据", "任何真实调整必须单独走 R3 审批"],
            "inventory_rows": inventory,
            "writes_inventory": False,
        }
    raise RegisteredWorkflowStateError(f"No specialist implementation for {agent_key}")


def _evaluate_quality(context: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
    """评估质量；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    issues = []
    if not outputs:
        issues.append({"code": "output.empty", "severity": "error", "message": "没有专业 Agent 输出"})
    serialized = str(outputs)
    for phrase in ("百分百", "保证治愈", "自动扣费", "绕过登录"):
        if phrase in serialized:
            issues.append(
                {"code": "claim.prohibited", "severity": "error", "message": f"包含禁止表达：{phrase}"}
            )
    if not context.get("product") and not context.get("store"):
        issues.append({"code": "context.missing", "severity": "error", "message": "缺少业务上下文"})
    error_count = sum(issue["severity"] == "error" for issue in issues)
    return {
        "passed": error_count == 0,
        "score": max(0, 100 - error_count * 25),
        "issues": issues,
        "checked_rules": ["non_empty", "prohibited_claims", "business_context", "human_boundary"],
    }


def _finalize_generic_run(
    run_id: int,
    outputs: dict[str, Any],
    usage: dict[str, Any] | None = None,
    *,
    lease_owner: str | None = None,
) -> dict[str, Any]:
    """完成落库generic执行；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    with SessionLocal() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None or run.task_id is None:
            raise RegisteredWorkflowStateError("Run not found while finalizing")
        task = db.get(AgentTask, run.task_id)
        if task is None:
            raise RegisteredWorkflowStateError("Task not found while finalizing")
        operation = db.scalar(
            select(AgentRunOperation).where(
                AgentRunOperation.run_id == run.id,
                AgentRunOperation.operation_key == "platform-finalize-v1",
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
        if operation is None:
            operation = AgentRunOperation(
                run_id=run.id,
                operation_key="platform-finalize-v1",
                status="running",
                result={},
            )
            db.add(operation)
            db.flush()
        artifacts = _persist_generic_artifacts(db, run=run, task=task, outputs=outputs)
        result = {
            "workflow_key": run.workflow_key,
            "outputs": redact_snapshot(outputs),
            "artifacts": artifacts,
        }
        run.final_output = result
        # 运行级用量：各环节调用的用量汇总，供前端「用量 / 预算」与 FR-33 校验读取。
        if usage:
            run.usage = redact_snapshot(usage)
        run.status = AgentRunStatus.COMPLETED
        run.current_agent = None
        run.finished_at = datetime.now(UTC)
        run.lease_owner = None
        run.lease_expires_at = None
        task.result_summary = result
        task.status = AgentTaskStatus.COMPLETED
        task.finished_at = run.finished_at
        operation.status = "completed"
        operation.result = result
        operation.completed_at = run.finished_at
        db.commit()
        return result


def _persist_generic_artifacts(
    db,
    *,
    run: AgentRun,
    task: AgentTask,
    outputs: dict[str, Any],
) -> dict[str, list[int]]:
    """持久化genericartifacts；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    product_id = _optional_int(task.context_scope.get("product_id"))
    artifacts: dict[str, list[int]] = {}
    if product_id is None:
        return artifacts
    if run.workflow_key == "creative_content_production":
        creative = outputs.get(CREATIVE_STRATEGY_AGENT, {})
        rows = []
        for plan_type, key in (
            (CreativePlanType.MAIN_IMAGE, "main_image_plans"),
            (CreativePlanType.VIDEO_SCRIPT, "video_script_plans"),
        ):
            for payload in creative.get(key, []):
                row = CreativePlan(
                    product_id=product_id,
                    agent_run_id=run.id,
                    type=plan_type,
                    title=payload["title"],
                    content=payload,
                    rationale=payload.get("angle"),
                )
                db.add(row)
                rows.append(row)
        db.flush()
        artifacts["creative_plan_ids"] = [row.id for row in rows]
    elif run.workflow_key == "growth_ad_experiment_loop":
        growth = outputs.get(GROWTH_EXPERIMENT_AGENT, {})
        payload = growth.get("recommendation")
        if payload:
            row = AdRecommendation(product_id=product_id, **payload)
            db.add(row)
            db.flush()
            artifacts["ad_recommendation_ids"] = [row.id]
    elif run.workflow_key == "periodic_performance_review":
        payload = outputs.get(PERFORMANCE_REVIEW_AGENT)
        if payload and payload.get("period_start") and payload.get("period_end"):
            row = ReviewReport(product_id=product_id, **payload)
            db.add(row)
            db.flush()
            artifacts["review_report_ids"] = [row.id]
    return artifacts


def _sync_generic_state(
    run_id: int,
    values: dict[str, Any],
    *,
    interrupted: bool,
    lease_owner: str | None = None,
) -> None:
    """同步generic状态；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    with SessionLocal() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None or run.task_id is None or run.workspace_id is None:
            raise RegisteredWorkflowStateError("Run not found while syncing")
        task = db.get(AgentTask, run.task_id)
        if task is None:
            raise RegisteredWorkflowStateError("Task not found while syncing")
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
            task.status = AgentTaskStatus.AWAITING_APPROVAL
            approval = db.scalar(
                select(AgentApproval).where(
                    AgentApproval.run_id == run.id,
                    AgentApproval.action_key == "workflow.accept_result",
                )
            )
            if approval is None:
                approval = AgentApproval(
                    workspace_id=run.workspace_id,
                    task_id=task.id,
                    run_id=run.id,
                    requested_by_user_id=run.requested_by_user_id,
                    action_key="workflow.accept_result",
                    risk_level=AgentRiskLevel(task.risk_level),
                    status=AgentApprovalStatus.PENDING,
                    request_payload={
                        "draft_output": run.draft_output,
                        "quality_report": run.quality_report,
                    },
                    decision_payload={},
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
                db.add(approval)
            db.add(
                AgentRunEvent(
                    run_id=run.id,
                    event_type="approval_requested",
                    status=AgentRunStatus.AWAITING_REVIEW.value,
                    message="工作流结果需要人工审批后才能采用。",
                )
            )
        elif values.get("final_status") == "quality_failed":
            run = require_active_lease(
                db,
                run_id=run_id,
                lease_owner=lease_owner,
                for_update=True,
            )
            run.status = AgentRunStatus.FAILED
            run.error = "QualityCompliance gate rejected workflow output"
            run.finished_at = datetime.now(UTC)
            run.lease_owner = None
            run.lease_expires_at = None
            task.status = AgentTaskStatus.FAILED
            task.error = run.error
            task.finished_at = run.finished_at
            db.add(
                AgentRunEvent(
                    run_id=run.id,
                    event_type="quality_gate_rejected",
                    agent_name="quality_compliance_agent",
                    status=AgentRunStatus.FAILED.value,
                    message="质量与合规门禁未通过，未持久化业务成果。",
                    output_snapshot=redact_snapshot(values.get("quality_report", {})),
                )
            )
        elif values.get("final_status") == "completed":
            if run.status != AgentRunStatus.COMPLETED:
                raise AgentLeaseLostError("Workflow reported completion without a fenced finalize")
        else:
            require_active_lease(
                db,
                run_id=run_id,
                lease_owner=lease_owner,
                for_update=True,
            )
        run.context_snapshot = redact_snapshot(values.get("context", {}))
        run.draft_output = redact_snapshot(values.get("agent_outputs", {}))
        run.quality_report = redact_snapshot(values.get("quality_report", {}))
        db.commit()


def _record_event(
    run_id: int,
    event_type: str,
    agent_key: str | None,
    payload: dict[str, Any],
    *,
    operation_name: str | None = None,
    lease_owner: str | None = None,
) -> None:
    """记录事件；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    with SessionLocal() as db:
        run = require_active_lease(db, run_id=run_id, lease_owner=lease_owner, for_update=True)
        renew_active_lease(db, run=run)
        run.current_agent = agent_key
        db.add(
            AgentRunEvent(
                run_id=run_id,
                event_type=event_type,
                agent_name=agent_key,
                operation_name=operation_name,
                status="completed",
                output_snapshot=redact_snapshot(payload),
            )
        )
        db.commit()


def _price_band(product: dict[str, Any]) -> str:
    """价格band；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    price = _decimal(product.get("price"))
    competitor_prices = [_decimal(row.get("price")) for row in product.get("competitors", [])]
    competitor_prices = [item for item in competitor_prices if item is not None]
    if price is None:
        return "商品售价未录入"
    if not competitor_prices:
        return f"当前售价 {price}，暂无可比较竞品价格"
    return f"当前售价 {price}，竞品区间 {min(competitor_prices)}-{max(competitor_prices)}"


def _product_risks(product: dict[str, Any]) -> list[str]:
    """商品risks；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    risks = []
    if not product.get("images"):
        risks.append("缺少商品图片，创意建议需要人工补充素材")
    if not product.get("competitors"):
        risks.append("缺少竞品样本，价格带和差异结论证据有限")
    if not product.get("performance"):
        risks.append("缺少经营表现数据，无法验证历史策略效果")
    return risks or ["当前基础资料较完整，仍需人工核对平台实时数据"]


def _performance_insights(records: list[dict[str, Any]]) -> list[str]:
    """经营数据洞察；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    if not records:
        return ["暂无可复盘经营数据，应先导入曝光、点击、转化和收入记录"]
    latest = records[0]
    return [
        f"最近周期曝光 {latest.get('impressions') or 0}、点击 {latest.get('clicks') or 0}",
        f"最近周期转化 {latest.get('conversions') or 0}、ROI {latest.get('roi') or '未录入'}",
    ]


def _inventory_risks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """库存risks；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    risks = []
    for row in rows:
        available = row.get("quantity", 0) - row.get("locked_quantity", 0)
        threshold = row.get("warning_threshold", 0)
        if available <= threshold:
            risks.append(
                {
                    "sku_id": row.get("sku_id"),
                    "sku_code": row.get("sku_code"),
                    "available": available,
                    "warning_threshold": threshold,
                    "level": "high" if available <= 0 else "warning",
                }
            )
    return risks


def _decimal_text(value: Decimal | None) -> str | None:
    """小数文本；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    return str(value) if value is not None else None


def _decimal(value: Any) -> Decimal | None:
    """小数；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    try:
        return Decimal(str(value)) if value is not None else None
    except Exception:
        return None


def _optional_int(value: Any) -> int | None:
    """可选int；只交换结构化 Agent 状态或受控工具结果，支持 checkpoint、审计与恢复。"""
    return int(value) if value not in {None, ""} else None
