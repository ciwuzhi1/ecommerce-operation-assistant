"""第19章验收：只测试注册、记录与事务边界，不导入第20、21章执行器。"""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.agents.policy import AgentPolicyError, authorize_tool
from app.agents.registry import (
    AGENT_REGISTRY,
    INVENTORY_OPERATIONS_AGENT,
    TOOL_REGISTRY,
    WORKFLOW_REGISTRY,
)
from app.models import (
    AgentRun,
    AgentRunStatus,
    AgentTask,
    Base,
    OutboxEvent,
    OutboxEventStatus,
    Platform,
    Product,
    User,
    UserRole,
    Workspace,
)
from app.schemas import AgentTaskCreate
from app.services.agent_tasks import AgentTaskStateError, create_agent_task


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(slug="lesson19", name="课堂食品店")
        other = Workspace(slug="other", name="其他团队")
        user = User(email="lesson19@example.com", display_name="讲师", role=UserRole.OWNER)
        db.add_all([workspace, other, user])
        db.flush()
        product = Product(workspace_id=workspace.id, name="低糖燕麦饼干", platform=Platform.DOUYIN)
        other_product = Product(workspace_id=other.id, name="其他团队商品", platform=Platform.DOUYIN)
        db.add_all([product, other_product])
        db.commit()
        ids = workspace.id, user.id, product.id, other_product.id
    yield engine, ids
    engine.dispose()


def _create(db, ids, *, product_id=None):
    workspace_id, user_id, own_product_id, _ = ids
    return create_agent_task(
        db, workspace_id=workspace_id, requested_by=db.get(User, user_id),
        payload=AgentTaskCreate(
            workflow_key="inventory_operations",
            context_scope={"product_id": own_product_id if product_id is None else product_id},
        ),
    )


def test_registry_has_nine_agents_sixteen_tools_and_seven_workflows():
    assert len(AGENT_REGISTRY) == 9
    assert len(TOOL_REGISTRY) == 16
    assert len(WORKFLOW_REGISTRY) == 7


def test_policy_denies_unlisted_tool_and_requires_owner_approval():
    with pytest.raises(AgentPolicyError, match="not allowed"):
        authorize_tool(agent_key=INVENTORY_OPERATIONS_AGENT,
                       tool_key="content.image.generate", workspace_role=UserRole.OWNER)
    operator = authorize_tool(agent_key=INVENTORY_OPERATIONS_AGENT,
                              tool_key="inventory.adjust", workspace_role=UserRole.OPERATOR)
    owner = authorize_tool(agent_key=INVENTORY_OPERATIONS_AGENT,
                           tool_key="inventory.adjust", workspace_role=UserRole.OWNER)
    assert not operator.allowed
    assert owner.allowed and owner.requires_approval


def test_create_persists_task_run_and_outbox_in_one_transaction(database):
    engine, ids = database
    with Session(engine) as db:
        task, run, event = _create(db, ids)
        db.commit()
        assert task.workspace_id == run.workspace_id == ids[0]
        assert run.task_id == task.id
        assert run.status == AgentRunStatus.QUEUED
        assert event.aggregate_id == str(run.id)
        assert event.payload["run_id"] == run.id
        assert event.status == OutboxEventStatus.PENDING


def test_rollback_leaves_no_partial_task_run_or_outbox(database):
    engine, ids = database
    with Session(engine) as db:
        _create(db, ids)
        db.rollback()
    with Session(engine) as db:
        for model in (AgentTask, AgentRun, OutboxEvent):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_cross_workspace_product_is_rejected_before_writing(database):
    engine, ids = database
    with Session(engine) as db:
        with pytest.raises(AgentTaskStateError, match=r"Product \d+ does not exist in workspace \d+"):
            _create(db, ids, product_id=ids[3])
        assert db.scalar(select(func.count()).select_from(AgentTask)) == 0
