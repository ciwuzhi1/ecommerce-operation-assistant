"""T-23 剩余部分：16 项工具执行适配（只读、生成、写入类）的行为与安全边界。"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.policy import AgentPolicyError
from app.agents.registry import (
    AGENT_REGISTRY,
    CONTENT_PRODUCTION_AGENT,
    GROWTH_EXPERIMENT_AGENT,
    INVENTORY_OPERATIONS_AGENT,
    MARKET_INTELLIGENCE_AGENT,
    QUALITY_COMPLIANCE_AGENT,
    TOOL_REGISTRY,
    AgentDefinition,
    ToolDefinition,
)
from app.agents.tool_gateway import (
    ToolApprovalRequired,
    ToolExecutionContext,
    ToolGateway,
)
from app.models import (
    AdExperiment,
    AgentApproval,
    AgentApprovalStatus,
    AgentRiskLevel,
    AgentRun,
    AgentRunStatus,
    AgentTask,
    Base,
    Competitor,
    CompetitorMonitor,
    CompetitorMonitorSnapshot,
    CreativePlan,
    CreativePlanType,
    InventoryItem,
    InventoryMovement,
    MembershipStatus,
    Platform,
    Product,
    ProductDiagnosis,
    ProductSku,
    Store,
    User,
    UserRole,
    Workspace,
    WorkspaceMembership,
)


@pytest.fixture
def context(monkeypatch):
    """构造共享内存库、租户数据和运行记录，并把网关的 SessionLocal 指向测试库。"""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr("app.agents.tool_gateway.SessionLocal", test_session_local)

    with Session(engine) as db:
        workspace = Workspace(slug="agent-adapters", name="智能体适配测试")
        other_workspace = Workspace(slug="agent-adapters-other", name="其他团队")
        owner = User(email="owner@adapters.test", display_name="所有者", role=UserRole.OWNER)
        operator = User(email="operator@adapters.test", display_name="运营", role=UserRole.OPERATOR)
        db.add_all([workspace, other_workspace, owner, operator])
        db.flush()
        db.add_all(
            [
                WorkspaceMembership(
                    workspace_id=workspace.id,
                    user_id=owner.id,
                    role=UserRole.OWNER,
                    status=MembershipStatus.ACTIVE,
                ),
                WorkspaceMembership(
                    workspace_id=workspace.id,
                    user_id=operator.id,
                    role=UserRole.OPERATOR,
                    status=MembershipStatus.ACTIVE,
                ),
            ]
        )
        store = Store(workspace_id=workspace.id, name="旗舰店", platform=Platform.DOUYIN)
        other_store = Store(workspace_id=other_workspace.id, name="其他店", platform=Platform.TMALL)
        db.add_all([store, other_store])
        db.flush()
        product = Product(
            workspace_id=workspace.id,
            store_id=store.id,
            name="控油气垫",
            platform=Platform.DOUYIN,
            category="美妆",
            price=Decimal("129.00"),
            selling_points=["轻薄", "控油"],
        )
        other_product = Product(
            workspace_id=other_workspace.id,
            store_id=other_store.id,
            name="其他团队商品",
            platform=Platform.TMALL,
        )
        db.add_all([product, other_product])
        db.flush()
        sku = ProductSku(product_id=product.id, sku_code="SKU-1", name="自然色")
        db.add(sku)
        db.flush()
        inventory_item = InventoryItem(
            sku_id=sku.id, quantity=10, locked_quantity=0, warning_threshold=2
        )
        db.add(inventory_item)
        main_plan = CreativePlan(
            product_id=product.id,
            type=CreativePlanType.MAIN_IMAGE,
            title="通勤场景首屏",
            content={"headline": "控油持妆", "image_prompt": "干净背景的商品主图"},
            rationale="通勤场景",
        )
        video_plan = CreativePlan(
            product_id=product.id,
            type=CreativePlanType.VIDEO_SCRIPT,
            title="痛点钩子脚本",
            content={"hook": "出门最怕脱妆", "video_prompt": "通勤短视频"},
            rationale="痛点钩子",
        )
        db.add_all([main_plan, video_plan])
        competitor = Competitor(
            product_id=product.id,
            name="竞品A",
            platform=Platform.TMALL,
            price=Decimal("119.00"),
            selling_points=["持妆"],
        )
        db.add(competitor)
        db.flush()
        monitor = CompetitorMonitor(
            product_id=product.id, competitor_id=competitor.id, status="active"
        )
        db.add(monitor)
        db.flush()
        db.add(
            CompetitorMonitorSnapshot(
                monitor_id=monitor.id,
                product_id=product.id,
                competitor_id=competitor.id,
                status="succeeded",
                price=Decimal("115.00"),
                changes=["价格下降 4 元"],
            )
        )
        task = AgentTask(
            workspace_id=workspace.id,
            requested_by_user_id=owner.id,
            workflow_key="inventory_operations",
            workflow_version="1.0.0",
            title="适配测试任务",
        )
        db.add(task)
        db.flush()
        run = AgentRun(
            thread_id="agent-adapters-run",
            workspace_id=workspace.id,
            task_id=task.id,
            product_id=product.id,
            requested_by_user_id=owner.id,
            workflow_key="inventory_operations",
            workflow_version="1.0.0",
            status=AgentRunStatus.RUNNING,
        )
        db.add(run)
        db.commit()
        ids = {
            "workspace_id": workspace.id,
            "task_id": task.id,
            "run_id": run.id,
            "owner_id": owner.id,
            "operator_id": operator.id,
            "store_id": store.id,
            "product_id": product.id,
            "other_product_id": other_product.id,
            "sku_id": sku.id,
            "inventory_item_id": inventory_item.id,
            "main_plan_id": main_plan.id,
            "video_plan_id": video_plan.id,
        }
    try:
        yield engine, ids
    finally:
        engine.dispose()


def _gateway(ids: dict, *, user_id: int) -> ToolGateway:
    """构造指向测试租户与运行的工具网关，供各用例复用。"""
    return ToolGateway(
        ToolExecutionContext(
            workspace_id=ids["workspace_id"],
            user_id=user_id,
            workspace_role=UserRole.OWNER,
            run_id=ids["run_id"],
            lease_owner=None,
        )
    )


def _approve_run(engine, ids: dict) -> None:
    """为当前运行写入一条已通过审批记录，模拟人工审批后的恢复执行。"""
    with Session(engine) as db:
        db.add(
            AgentApproval(
                workspace_id=ids["workspace_id"],
                task_id=ids["task_id"],
                run_id=ids["run_id"],
                requested_by_user_id=ids["owner_id"],
                action_key="workflow.accept_result",
                risk_level=AgentRiskLevel.R3,
                status=AgentApprovalStatus.APPROVED,
            )
        )
        db.commit()


def test_product_read_returns_workspace_scoped_context(context):
    """只读商品返回结构化上下文，并带出当前 Workspace 的 SKU 数量。"""
    _, ids = context
    gateway = _gateway(ids, user_id=ids["owner_id"])

    result = gateway.execute(
        agent_key=MARKET_INTELLIGENCE_AGENT,
        tool_key="product.read",
        input_payload={"product_id": ids["product_id"]},
    )

    assert result["id"] == ids["product_id"]
    assert result["store_id"] == ids["store_id"]
    assert result["platform"] == "douyin"
    assert result["price"] == "129.00"
    assert result["sku_count"] == 1


def test_product_read_rejects_cross_workspace_scope(context):
    """跨租户商品必须被权属校验拦截，不能读到其他 Workspace 数据。"""
    _, ids = context
    gateway = _gateway(ids, user_id=ids["owner_id"])

    with pytest.raises(AgentPolicyError, match="outside current Workspace"):
        gateway.execute(
            agent_key=MARKET_INTELLIGENCE_AGENT,
            tool_key="product.read",
            input_payload={"product_id": ids["other_product_id"]},
        )


def test_store_read_lists_workspace_products(context):
    """只读店铺返回店铺摘要与当前 Workspace 内的商品列表。"""
    _, ids = context
    gateway = _gateway(ids, user_id=ids["owner_id"])

    result = gateway.execute(
        agent_key=MARKET_INTELLIGENCE_AGENT,
        tool_key="store.read",
        input_payload={"store_id": ids["store_id"]},
    )

    assert result["id"] == ids["store_id"]
    assert result["product_count"] == 1
    assert result["products"][0]["id"] == ids["product_id"]


def test_competitor_read_returns_latest_snapshot(context):
    """只读竞品返回竞品资料与最新监控快照。"""
    _, ids = context
    gateway = _gateway(ids, user_id=ids["owner_id"])

    result = gateway.execute(
        agent_key=MARKET_INTELLIGENCE_AGENT,
        tool_key="competitor.read",
        input_payload={"product_id": ids["product_id"]},
    )

    assert result[0]["name"] == "竞品A"
    assert result[0]["price"] == "119.00"
    assert result[0]["latest_snapshot"]["changes"] == ["价格下降 4 元"]


def test_inventory_read_returns_sku_rows(context):
    """只读库存返回店铺 SKU 库存行，含可用量与预警判断。"""
    _, ids = context
    gateway = _gateway(ids, user_id=ids["owner_id"])

    result = gateway.execute(
        agent_key=INVENTORY_OPERATIONS_AGENT,
        tool_key="inventory.read",
        input_payload={"store_id": ids["store_id"]},
    )

    assert len(result) == 1
    assert result[0]["sku_code"] == "SKU-1"
    assert result[0]["quantity"] == 10
    assert result[0]["available_quantity"] == 10
    assert result[0]["is_low_stock"] is False


def test_content_image_generate_delegates_to_service(context, monkeypatch):
    """图片生成委托图片供应商服务，只返回候选素材元数据。"""
    _, ids = context
    captured: dict = {}

    def fake_generate(plan):
        captured["plan_id"] = plan.id
        return {"provider": "jimeng", "url": "/uploads/generated/x.png", "size": "1328x1328"}

    monkeypatch.setattr("app.agents.tool_gateway.generate_main_image_asset", fake_generate)
    gateway = _gateway(ids, user_id=ids["owner_id"])

    result = gateway.execute(
        agent_key=CONTENT_PRODUCTION_AGENT,
        tool_key="content.image.generate",
        input_payload={"creative_plan_id": ids["main_plan_id"]},
    )

    assert captured["plan_id"] == ids["main_plan_id"]
    assert result["creative_plan_id"] == ids["main_plan_id"]
    assert result["url"] == "/uploads/generated/x.png"


def test_content_image_generate_rejects_non_main_image_plan(context):
    """图片生成只接受主图方案，视频方案被拒绝。"""
    _, ids = context
    gateway = _gateway(ids, user_id=ids["owner_id"])

    with pytest.raises(AgentPolicyError, match="main image creative plan"):
        gateway.execute(
            agent_key=CONTENT_PRODUCTION_AGENT,
            tool_key="content.image.generate",
            input_payload={"creative_plan_id": ids["video_plan_id"]},
        )


def test_content_video_generate_delegates_to_service(context, monkeypatch):
    """视频生成委托视频供应商服务，只返回候选素材元数据。"""
    _, ids = context
    captured: dict = {}

    def fake_generate(plan):
        captured["plan_id"] = plan.id
        return {"provider": "jimeng", "url": "/uploads/generated-videos/y.mp4", "duration": 5}

    monkeypatch.setattr("app.agents.tool_gateway.generate_video_asset", fake_generate)
    gateway = _gateway(ids, user_id=ids["owner_id"])

    result = gateway.execute(
        agent_key=CONTENT_PRODUCTION_AGENT,
        tool_key="content.video.generate",
        input_payload={"creative_plan_id": ids["video_plan_id"]},
    )

    assert captured["plan_id"] == ids["video_plan_id"]
    assert result["url"] == "/uploads/generated-videos/y.mp4"


def test_ad_experiment_create_requires_approval_before_any_write(context):
    """R2 工具在审批前挂起，且不产生任何实验记录（业务数据零变更）。"""
    engine, ids = context
    gateway = _gateway(ids, user_id=ids["owner_id"])

    with pytest.raises(ToolApprovalRequired):
        gateway.execute(
            agent_key=GROWTH_EXPERIMENT_AGENT,
            tool_key="ad.experiment.create",
            input_payload={"product_id": ids["product_id"]},
        )

    with Session(engine) as db:
        assert db.scalar(select(AdExperiment)) is None


def test_ad_experiment_create_persists_after_approval(context):
    """审批通过后创建正式投放实验，且保持 draft 状态。"""
    engine, ids = context
    _approve_run(engine, ids)
    gateway = _gateway(ids, user_id=ids["owner_id"])

    result = gateway.execute(
        agent_key=GROWTH_EXPERIMENT_AGENT,
        tool_key="ad.experiment.create",
        input_payload={"product_id": ids["product_id"]},
    )

    assert result["status"] == "draft"
    with Session(engine) as db:
        experiment = db.scalar(select(AdExperiment))
        assert experiment is not None
        assert experiment.id == result["ad_experiment_id"]
        assert experiment.product_id == ids["product_id"]


def test_inventory_adjust_rejects_non_owner_before_any_write(context):
    """R3 owner_only：运营人员被拒绝，库存与流水保持零变更。"""
    engine, ids = context
    gateway = _gateway(ids, user_id=ids["operator_id"])

    with pytest.raises(AgentPolicyError, match="Owner"):
        gateway.execute(
            agent_key=INVENTORY_OPERATIONS_AGENT,
            tool_key="inventory.adjust",
            input_payload=_adjust_payload(ids),
        )

    with Session(engine) as db:
        assert db.scalar(select(InventoryMovement)) is None
        assert db.get(InventoryItem, ids["inventory_item_id"]).quantity == 10


def test_inventory_adjust_requires_approval_for_owner(context):
    """R3：所有者未审批时仍挂起，库存与流水保持零变更。"""
    engine, ids = context
    gateway = _gateway(ids, user_id=ids["owner_id"])

    with pytest.raises(ToolApprovalRequired):
        gateway.execute(
            agent_key=INVENTORY_OPERATIONS_AGENT,
            tool_key="inventory.adjust",
            input_payload=_adjust_payload(ids),
        )

    with Session(engine) as db:
        assert db.scalar(select(InventoryMovement)) is None
        assert db.get(InventoryItem, ids["inventory_item_id"]).quantity == 10


def test_inventory_adjust_writes_movement_after_owner_approval(context):
    """所有者审批后写入库存流水，数量按流水变化并保留前后值。"""
    engine, ids = context
    _approve_run(engine, ids)
    gateway = _gateway(ids, user_id=ids["owner_id"])

    result = gateway.execute(
        agent_key=INVENTORY_OPERATIONS_AGENT,
        tool_key="inventory.adjust",
        input_payload=_adjust_payload(ids, quantity_delta=-4),
    )

    assert result["before_quantity"] == 10
    assert result["after_quantity"] == 6
    with Session(engine) as db:
        movement = db.scalar(select(InventoryMovement))
        assert movement is not None
        assert movement.movement_type.value == "outbound"
        assert movement.before_quantity == 10
        assert movement.after_quantity == 6
        assert db.get(InventoryItem, ids["inventory_item_id"]).quantity == 6


def test_artifact_persist_requires_approval_and_is_idempotent(context, monkeypatch):
    """R2 采用草稿：审批前零变更，审批后落库且重复采用不产生第二条记录。"""
    engine, ids = context
    monkeypatch.setitem(
        AGENT_REGISTRY,
        QUALITY_COMPLIANCE_AGENT,
        AgentDefinition(
            QUALITY_COMPLIANCE_AGENT, "1.0.0", "测试用质量合规 Agent", frozenset({"artifact.persist"})
        ),
    )
    payload = {
        "artifact_type": "diagnosis",
        "product_id": ids["product_id"],
        "draft": {
            "source": "llm",
            "positioning": "适合通勤人群的控油底妆",
            "price_band": "处于竞品中位价格带",
            "risks": ["需要真实持妆素材证明"],
        },
    }
    gateway = _gateway(ids, user_id=ids["owner_id"])

    with pytest.raises(ToolApprovalRequired):
        gateway.execute(
            agent_key=QUALITY_COMPLIANCE_AGENT, tool_key="artifact.persist", input_payload=payload
        )
    with Session(engine) as db:
        assert db.scalar(select(ProductDiagnosis)) is None

    _approve_run(engine, ids)
    first = gateway.execute(
        agent_key=QUALITY_COMPLIANCE_AGENT, tool_key="artifact.persist", input_payload=payload
    )
    second = gateway.execute(
        agent_key=QUALITY_COMPLIANCE_AGENT, tool_key="artifact.persist", input_payload=payload
    )

    assert first["diagnosis_id"] == second["diagnosis_id"]
    with Session(engine) as db:
        diagnoses = db.scalars(select(ProductDiagnosis)).all()
        assert len(diagnoses) == 1
        assert diagnoses[0].positioning == "适合通勤人群的控油底妆"
        assert diagnoses[0].agent_run_id == ids["run_id"]


def test_artifact_persist_creates_creative_plans(context):
    """采用创意方案草稿时批量写入正式创意方案并标注来源运行。"""
    engine, ids = context
    gateway = _gateway(ids, user_id=ids["owner_id"])
    payload = {
        "artifact_type": "creative_plan",
        "product_id": ids["product_id"],
        "draft": [
            {
                "type": "main_image",
                "title": "主图方案A",
                "content": {"headline": "控油持妆"},
                "rationale": "通勤场景",
            }
        ],
    }

    with Session(engine) as db:
        result = gateway._execute_tool(db, tool_key="artifact.persist", input_payload=payload)
        db.commit()
        assert result["artifact_type"] == "creative_plan"
        plan = db.get(CreativePlan, result["creative_plan_ids"][0])
        assert plan.title == "主图方案A"
        assert plan.agent_run_id == ids["run_id"]


def test_registered_tool_without_adapter_raises_policy_error(context, monkeypatch):
    """已登记但暂无执行适配的工具仍必须抛 AgentPolicyError，保护既有兜底语义。"""
    _, ids = context
    monkeypatch.setitem(
        TOOL_REGISTRY, "future.tool", ToolDefinition("future.tool", AgentRiskLevel.R0, "未来工具")
    )
    monkeypatch.setitem(
        AGENT_REGISTRY,
        MARKET_INTELLIGENCE_AGENT,
        AgentDefinition(
            MARKET_INTELLIGENCE_AGENT, "1.0.0", "测试用市场情报 Agent", frozenset({"future.tool"})
        ),
    )
    gateway = _gateway(ids, user_id=ids["owner_id"])

    with pytest.raises(AgentPolicyError, match="has no executable adapter: future.tool"):
        gateway.execute(
            agent_key=MARKET_INTELLIGENCE_AGENT, tool_key="future.tool", input_payload={}
        )


def _adjust_payload(ids: dict, *, quantity_delta: int = -4) -> dict:
    """构造库存调整入参，默认执行一次出库调整。"""
    return {
        "sku_id": ids["sku_id"],
        "movement_type": "outbound",
        "quantity_delta": quantity_delta,
        "reason": "盘点出库",
    }
