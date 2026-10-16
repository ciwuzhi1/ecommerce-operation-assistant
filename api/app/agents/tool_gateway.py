from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Final

from sqlalchemy import select

from app.agents.harness import redact_snapshot
from app.agents.policy import AgentPolicyError, authorize_tool
from app.db.session import SessionLocal
from app.models import (
    AdExperiment,
    AgentApproval,
    AgentApprovalStatus,
    AgentRunOperation,
    Competitor,
    CompetitorMonitor,
    CompetitorMonitorSnapshot,
    CreativePlan,
    CreativePlanType,
    InventoryItem,
    InventoryMovementType,
    MembershipStatus,
    Product,
    ProductDiagnosis,
    ProductSku,
    Store,
    User,
    UserRole,
    UserStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)
from app.schemas import StoreInventoryRow
from app.services.ad_experiments import build_ad_experiment_payload
from app.services.ad_recommendations import generate_ad_recommendation
from app.services.creative_plans import generate_main_image_plans, generate_video_script_plans
from app.services.competitor_monitoring import run_competitor_monitor
from app.services.diagnosis import generate_product_diagnosis
from app.services.image_generation import generate_main_image_asset
from app.services.inventory import adjust_inventory
from app.services.inventory_advice import generate_inventory_advice
from app.services.promotion_links import build_promotion_link_payloads
from app.services.review import generate_review
from app.services.agent_leases import require_active_lease
from app.services.video_generation import generate_video_asset


# 运行级审批动作键，与 agent_runs/agent_workflows 写入的审批记录保持一致。
RUN_APPROVAL_ACTION_KEY: Final = "workflow.accept_result"

# 草稿采用为正式诊断时允许落库的字段，显式白名单避免草稿夹带未知列。
DIAGNOSIS_ARTIFACT_FIELDS: Final = (
    "source",
    "positioning",
    "price_band",
    "audience_insights",
    "pain_points",
    "selling_point_analysis",
    "risks",
    "recommendations",
    "raw_output",
)


class ToolApprovalRequired(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolExecutionContext:
    workspace_id: int
    user_id: int
    workspace_role: UserRole
    run_id: int
    lease_owner: str | None = None


class ToolGateway:
    def __init__(self, context: ToolExecutionContext) -> None:
        """初始化 ToolGateway 的依赖与运行状态，避免执行阶段临时拼装共享资源。"""
        self.context = context
        # 最近一次实际执行的工具名；编排层据此给运行事件填上操作名。
        self.last_tool_key: str | None = None

    def execute(
        self,
        *,
        agent_key: str,
        tool_key: str,
        input_payload: dict[str, Any],
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """执行，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        # 供编排层记录「本次环节实际执行了哪个操作」（DesignSpec §8 事件需含操作名）。
        self.last_tool_key = tool_key
        operation_key = f"tool:{agent_key}:{tool_key}"
        with SessionLocal() as db:
            run = require_active_lease(
                db,
                run_id=self.context.run_id,
                lease_owner=self.context.lease_owner,
                for_update=True,
            )
            if run.workspace_id != self.context.workspace_id:
                raise AgentPolicyError("Agent run is outside current Workspace")
            current_role = self._current_workspace_role(db)
            decision = authorize_tool(
                agent_key=agent_key,
                tool_key=tool_key,
                workspace_role=current_role,
            )
            if not decision.allowed:
                raise AgentPolicyError(decision.reason)
            # 写入正式对象与库存调整类工具必须已有人工审批记录，审批前保持业务数据零变更。
            if decision.requires_approval and not self._has_approved_action(db):
                raise ToolApprovalRequired(
                    f"Tool {tool_key} requires {decision.risk_level.value} approval"
                )
            operation = db.scalar(
                select(AgentRunOperation).where(
                    AgentRunOperation.run_id == self.context.run_id,
                    AgentRunOperation.operation_key == operation_key,
                )
            )
            if operation is not None and operation.status == "completed":
                return operation.result.get("value", operation.result)
            if operation is None:
                operation = AgentRunOperation(
                    run_id=self.context.run_id,
                    operation_key=operation_key,
                    status="running",
                    result={},
                )
                db.add(operation)
                db.flush()
            try:
                result = self._execute_tool(db, tool_key=tool_key, input_payload=input_payload)
            except Exception as exc:
                db.rollback()
                self._record_operation_failure(operation_key, exc)
                raise
            operation.status = "completed"
            operation.result = {"value": redact_snapshot(result)}
            operation.error = None
            operation.completed_at = datetime.now(UTC)
            db.commit()
            return result

    def _record_operation_failure(self, operation_key: str, error: Exception) -> None:
        """记录操作failure，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        with SessionLocal() as db:
            operation = db.scalar(
                select(AgentRunOperation).where(
                    AgentRunOperation.run_id == self.context.run_id,
                    AgentRunOperation.operation_key == operation_key,
                )
            )
            if operation is None:
                operation = AgentRunOperation(
                    run_id=self.context.run_id,
                    operation_key=operation_key,
                    status="failed",
                    result={},
                )
                db.add(operation)
            operation.status = "failed"
            operation.error = str(error)[:2000]
            db.commit()

    def _current_workspace_role(self, db) -> UserRole:
        """当前Workspace角色，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        membership = db.scalar(
            select(WorkspaceMembership)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .join(User, User.id == WorkspaceMembership.user_id)
            .where(
                WorkspaceMembership.workspace_id == self.context.workspace_id,
                WorkspaceMembership.user_id == self.context.user_id,
                WorkspaceMembership.status == MembershipStatus.ACTIVE,
                Workspace.status == WorkspaceStatus.ACTIVE,
                User.status == UserStatus.ACTIVE,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if membership is None:
            raise AgentPolicyError("Agent requester no longer has active Workspace access")
        return membership.role

    def _execute_tool(self, db, *, tool_key: str, input_payload: dict[str, Any]):
        """执行工具，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        handlers: dict[str, Callable[[], Any]] = {
            "diagnosis.draft": lambda: generate_product_diagnosis(
                self._product(db, input_payload["product_id"])
            ),
            "competitor.monitor.run": lambda: self._run_competitor_monitors(
                db,
                product_id=input_payload.get("product_id"),
                store_id=input_payload.get("store_id"),
            ),
            "creative.plan.draft": lambda: self._creative_plans(
                db,
                product_id=input_payload["product_id"],
            ),
            "ad.recommendation.draft": lambda: generate_ad_recommendation(
                self._product(db, input_payload["product_id"])
            ),
            "promotion.link.draft": lambda: build_promotion_link_payloads(
                self._product(db, input_payload["product_id"])
            ),
            "performance.review.draft": lambda: generate_review(
                self._product(db, input_payload["product_id"])
            ),
            "inventory.advice.draft": lambda: self._inventory_advice(
                db,
                store_id=input_payload["store_id"],
            ),
            "product.read": lambda: self._read_product(
                db,
                product_id=input_payload["product_id"],
            ),
            "store.read": lambda: self._read_store(
                db,
                store_id=input_payload["store_id"],
            ),
            "competitor.read": lambda: self._read_competitors(
                db,
                product_id=input_payload["product_id"],
            ),
            "inventory.read": lambda: self._read_inventory(
                db,
                store_id=input_payload.get("store_id"),
                product_id=input_payload.get("product_id"),
            ),
            "content.image.generate": lambda: self._generate_image_asset(
                db,
                creative_plan_id=input_payload["creative_plan_id"],
            ),
            "content.video.generate": lambda: self._generate_video_asset(
                db,
                creative_plan_id=input_payload["creative_plan_id"],
            ),
            "ad.experiment.create": lambda: self._create_ad_experiment(
                db,
                product_id=input_payload["product_id"],
            ),
            "inventory.adjust": lambda: self._adjust_inventory(
                db,
                input_payload=input_payload,
            ),
            "artifact.persist": lambda: self._persist_artifact(
                db,
                input_payload=input_payload,
            ),
        }
        handler = handlers.get(tool_key)
        if handler is None:
            raise AgentPolicyError(f"Tool has no executable adapter: {tool_key}")
        return redact_snapshot(handler())

    def _product(self, db, product_id: int) -> Product:
        """商品，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        product = db.get(Product, int(product_id))
        if product is None or product.workspace_id != self.context.workspace_id:
            raise AgentPolicyError("Product tool scope is outside current Workspace")
        return product

    def _store(self, db, store_id: int) -> Store:
        """店铺，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        store = db.get(Store, int(store_id))
        if store is None or store.workspace_id != self.context.workspace_id:
            raise AgentPolicyError("Store tool scope is outside current Workspace")
        return store

    def _creative_plans(self, db, *, product_id: int) -> dict[str, Any]:
        """创意plans，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        product = self._product(db, product_id)
        diagnosis = db.scalar(
            select(ProductDiagnosis)
            .where(ProductDiagnosis.product_id == product.id)
            .order_by(ProductDiagnosis.id.desc())
            .limit(1)
        )
        return {
            "main_image_plans": generate_main_image_plans(product, diagnosis),
            "video_script_plans": generate_video_script_plans(product, diagnosis),
        }

    def _run_competitor_monitors(
        self,
        db,
        *,
        product_id: int | None,
        store_id: int | None,
    ) -> list[dict[str, Any]]:
        """执行竞品monitors，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        statement = select(CompetitorMonitor).join(
            Product,
            Product.id == CompetitorMonitor.product_id,
        )
        statement = statement.where(
            Product.workspace_id == self.context.workspace_id,
            CompetitorMonitor.status == "active",
        )
        if product_id is not None:
            self._product(db, product_id)
            statement = statement.where(CompetitorMonitor.product_id == int(product_id))
        elif store_id is not None:
            self._store(db, store_id)
            statement = statement.where(Product.store_id == int(store_id))
        else:
            raise AgentPolicyError("Competitor monitor tool requires product_id or store_id")
        snapshots = [run_competitor_monitor(db, monitor) for monitor in db.scalars(statement).all()]
        return [
            {
                "snapshot_id": snapshot.id,
                "monitor_id": snapshot.monitor_id,
                "status": snapshot.status,
                "changes": snapshot.changes,
                "error": snapshot.error,
            }
            for snapshot in snapshots
        ]

    def _inventory_advice(self, db, *, store_id: int) -> dict[str, Any]:
        """库存建议，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        store = self._store(db, store_id)
        rows = self._inventory_rows(db, store_id=store.id)
        return generate_inventory_advice(store, rows)

    def _inventory_rows(self, db, *, store_id: int) -> list[StoreInventoryRow]:
        """库存行，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        statement = (
            select(ProductSku, Product, InventoryItem)
            .join(Product, ProductSku.product_id == Product.id)
            .outerjoin(InventoryItem, InventoryItem.sku_id == ProductSku.id)
            .where(
                Product.store_id == store_id,
                Product.workspace_id == self.context.workspace_id,
            )
            .order_by(Product.id.asc(), ProductSku.id.asc())
        )
        rows = []
        for sku, product, item in db.execute(statement).all():
            quantity = item.quantity if item else 0
            locked = item.locked_quantity if item else 0
            warning = item.warning_threshold if item else 0
            available = quantity - locked
            rows.append(
                StoreInventoryRow(
                    product_id=product.id,
                    product_name=product.name,
                    sku_id=sku.id,
                    sku_code=sku.sku_code,
                    sku_name=sku.name,
                    quantity=quantity,
                    locked_quantity=locked,
                    available_quantity=available,
                    warning_threshold=warning,
                    is_low_stock=available <= warning,
                    location=item.location if item else None,
                )
            )
        return rows

    def _has_approved_action(self, db) -> bool:
        """确认高风险工具在写入前已获得人工审批记录，审批前保持业务数据零变更。"""
        # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
        approval = db.scalar(
            select(AgentApproval).where(
                AgentApproval.run_id == self.context.run_id,
                AgentApproval.action_key == RUN_APPROVAL_ACTION_KEY,
                AgentApproval.status == AgentApprovalStatus.APPROVED,
            )
        )
        return approval is not None

    def _creative_plan(self, db, creative_plan_id: int) -> CreativePlan:
        """创意方案，在工具执行前复核租户、角色、租约和幂等键，并记录操作结果。"""
        plan = db.get(CreativePlan, int(creative_plan_id))
        if plan is None:
            raise AgentPolicyError("Creative plan tool scope is outside current Workspace")
        self._product(db, plan.product_id)
        return plan

    def _read_product(self, db, *, product_id: int) -> dict[str, Any]:
        """读取商品，只返回当前 Workspace 内的结构化经营上下文。"""
        product = self._product(db, product_id)
        sku_ids = db.scalars(
            select(ProductSku.id).where(ProductSku.product_id == product.id)
        ).all()
        return {
            "id": product.id,
            "store_id": product.store_id,
            "name": product.name,
            "platform": product.platform.value,
            "category": product.category,
            "price": _decimal_text(product.price),
            "cost": _decimal_text(product.cost),
            "target_audience": product.target_audience,
            "selling_points": list(product.selling_points or []),
            "product_url": product.product_url,
            "images": list(product.images or []),
            "external_product_id": product.external_product_id,
            "platform_status": product.platform_status,
            "sku_count": len(sku_ids),
        }

    def _read_store(self, db, *, store_id: int) -> dict[str, Any]:
        """读取店铺，只返回当前 Workspace 内的店铺与商品摘要。"""
        store = self._store(db, store_id)
        products = db.scalars(
            select(Product).where(
                Product.store_id == store.id,
                Product.workspace_id == self.context.workspace_id,
            )
        ).all()
        return {
            "id": store.id,
            "name": store.name,
            "platform": store.platform.value,
            "status": store.status.value,
            "external_store_id": store.external_store_id,
            "owner_name": store.owner_name,
            "product_count": len(products),
            "products": [
                {
                    "id": product.id,
                    "name": product.name,
                    "platform": product.platform.value,
                    "category": product.category,
                    "price": _decimal_text(product.price),
                }
                for product in products
            ],
        }

    def _read_competitors(self, db, *, product_id: int) -> list[dict[str, Any]]:
        """读取竞品，返回当前 Workspace 内竞品资料与最新监控快照。"""
        product = self._product(db, product_id)
        competitors = db.scalars(
            select(Competitor)
            .where(Competitor.product_id == product.id)
            .order_by(Competitor.id.asc())
        ).all()
        result: list[dict[str, Any]] = []
        for competitor in competitors:
            latest = db.scalar(
                select(CompetitorMonitorSnapshot)
                .where(CompetitorMonitorSnapshot.competitor_id == competitor.id)
                .order_by(CompetitorMonitorSnapshot.id.desc())
                .limit(1)
            )
            result.append(
                {
                    "id": competitor.id,
                    "name": competitor.name,
                    "platform": competitor.platform.value,
                    "url": competitor.url,
                    "price": _decimal_text(competitor.price),
                    "title": competitor.title,
                    "sales_hint": competitor.sales_hint,
                    "selling_points": list(competitor.selling_points or []),
                    "review_keywords": list(competitor.review_keywords or []),
                    "latest_snapshot": None
                    if latest is None
                    else {
                        "id": latest.id,
                        "status": latest.status,
                        "checked_at": latest.checked_at.isoformat() if latest.checked_at else None,
                        "price": _decimal_text(latest.price),
                        "changes": list(latest.changes or []),
                        "error": latest.error,
                    },
                }
            )
        return result

    def _read_inventory(
        self,
        db,
        *,
        store_id: int | None,
        product_id: int | None,
    ) -> list[dict[str, Any]]:
        """读取库存，返回当前 Workspace 内的 SKU 库存行。"""
        if store_id is not None:
            store = self._store(db, store_id)
            rows = self._inventory_rows(db, store_id=store.id)
        elif product_id is not None:
            product = self._product(db, product_id)
            rows = (
                [
                    row
                    for row in self._inventory_rows(db, store_id=product.store_id)
                    if row.product_id == product.id
                ]
                if product.store_id is not None
                else []
            )
        else:
            raise AgentPolicyError("Inventory read tool requires store_id or product_id")
        return [row.model_dump(mode="json") for row in rows]

    def _generate_image_asset(self, db, *, creative_plan_id: int) -> dict[str, Any]:
        """生成候选图片素材，委托图片供应商服务，只返回可审核的素材元数据。"""
        plan = self._creative_plan(db, creative_plan_id)
        if plan.type != CreativePlanType.MAIN_IMAGE:
            raise AgentPolicyError("content.image.generate requires a main image creative plan")
        asset = generate_main_image_asset(plan)
        return {"creative_plan_id": plan.id, "product_id": plan.product_id, **asset}

    def _generate_video_asset(self, db, *, creative_plan_id: int) -> dict[str, Any]:
        """生成候选视频素材，委托视频供应商服务，只返回可审核的素材元数据。"""
        plan = self._creative_plan(db, creative_plan_id)
        if plan.type != CreativePlanType.VIDEO_SCRIPT:
            raise AgentPolicyError("content.video.generate requires a video script creative plan")
        asset = generate_video_asset(plan)
        return {"creative_plan_id": plan.id, "product_id": plan.product_id, **asset}

    def _create_ad_experiment(self, db, *, product_id: int) -> dict[str, Any]:
        """创建正式投放实验，复用服务层实验计划并保持 draft 状态。"""
        product = self._product(db, product_id)
        payload = build_ad_experiment_payload(product)
        experiment = AdExperiment(product_id=product.id, **payload)
        db.add(experiment)
        db.flush()
        return {
            "ad_experiment_id": experiment.id,
            "product_id": product.id,
            "name": experiment.name,
            "status": experiment.status,
            "daily_budget": _decimal_text(experiment.daily_budget),
            "generated_asset_id": experiment.generated_asset_id,
            "promotion_link_id": experiment.promotion_link_id,
        }

    def _adjust_inventory(self, db, *, input_payload: dict[str, Any]) -> dict[str, Any]:
        """执行库存调整，必须经流水写入，禁止直接覆盖库存数量。"""
        sku = db.get(ProductSku, int(input_payload["sku_id"]))
        if sku is None:
            raise AgentPolicyError("Inventory adjust scope is outside current Workspace")
        self._product(db, sku.product_id)
        item = db.scalar(select(InventoryItem).where(InventoryItem.sku_id == sku.id))
        if item is None:
            raise AgentPolicyError("Inventory item does not exist for SKU")
        # 库存变化只经 adjust_inventory 写流水，网关不自行加减数量，避免绕过对账逻辑。
        movement = adjust_inventory(
            db,
            item,
            movement_type=InventoryMovementType(input_payload["movement_type"]),
            quantity_delta=int(input_payload.get("quantity_delta", 0)),
            locked_delta=int(input_payload.get("locked_delta", 0)),
            reason=input_payload.get("reason"),
            reference_type=input_payload.get("reference_type"),
            reference_id=input_payload.get("reference_id"),
            operator_name=input_payload.get("operator_name"),
        )
        db.flush()
        return {
            "movement_id": movement.id,
            "sku_id": sku.id,
            "product_id": sku.product_id,
            "movement_type": movement.movement_type.value,
            "quantity_delta": movement.quantity_delta,
            "locked_delta": movement.locked_delta,
            "before_quantity": movement.before_quantity,
            "after_quantity": movement.after_quantity,
            "before_locked_quantity": movement.before_locked_quantity,
            "after_locked_quantity": movement.after_locked_quantity,
            "reason": movement.reason,
        }

    def _persist_artifact(self, db, *, input_payload: dict[str, Any]) -> dict[str, Any]:
        """采用草稿为正式业务对象，写入来源运行编号并保持幂等。"""
        artifact_type = input_payload["artifact_type"]
        product = self._product(db, input_payload["product_id"])
        draft = input_payload["draft"]
        if artifact_type in {"diagnosis", "product_diagnosis"}:
            payload = {
                field: draft[field]
                for field in DIAGNOSIS_ARTIFACT_FIELDS
                if field in draft
            }
            if not payload.get("positioning") or not payload.get("price_band"):
                raise AgentPolicyError("Diagnosis artifact requires positioning and price_band")
            diagnosis = ProductDiagnosis(
                product_id=product.id,
                agent_run_id=self.context.run_id,
                **payload,
            )
            db.add(diagnosis)
            db.flush()
            return {
                "artifact_type": "diagnosis",
                "diagnosis_id": diagnosis.id,
                "product_id": product.id,
                "agent_run_id": self.context.run_id,
            }
        if artifact_type in {"creative_plan", "creative_plans"}:
            plans = draft if isinstance(draft, list) else [draft]
            rows = []
            for plan in plans:
                row = CreativePlan(
                    product_id=product.id,
                    agent_run_id=self.context.run_id,
                    type=CreativePlanType(plan.get("type", "main_image")),
                    title=plan["title"],
                    content=plan.get("content") or plan,
                    rationale=plan.get("rationale") or plan.get("angle"),
                )
                db.add(row)
                rows.append(row)
            db.flush()
            return {
                "artifact_type": "creative_plan",
                "creative_plan_ids": [row.id for row in rows],
                "product_id": product.id,
                "agent_run_id": self.context.run_id,
            }
        raise AgentPolicyError(f"Unsupported artifact type: {artifact_type}")


def _decimal_text(value: Any) -> str | None:
    """把 Decimal 归一化为字符串，避免快照序列化丢失精度。"""
    return None if value is None else str(value)


# 具备执行适配的工具清单，与注册表登记的 16 项工具一一对应（PRD Q4）。
# 能力目录用它标注每项工具是否已可用；新增工具时必须同时补进这里，否则目录会失真。
EXECUTABLE_TOOL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "product.read",
        "store.read",
        "competitor.read",
        "competitor.monitor.run",
        "diagnosis.draft",
        "creative.plan.draft",
        "content.image.generate",
        "content.video.generate",
        "promotion.link.draft",
        "ad.recommendation.draft",
        "ad.experiment.create",
        "performance.review.draft",
        "inventory.read",
        "inventory.advice.draft",
        "inventory.adjust",
        "artifact.persist",
    }
)
