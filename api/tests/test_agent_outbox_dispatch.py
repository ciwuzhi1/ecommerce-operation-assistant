"""第21章Outbox投递验收：使用内存数据库与消息发布替身。"""
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.policy import AgentPolicyError, authorize_tool
from app.agents.registry import (
    AGENT_REGISTRY, TOOL_REGISTRY, WORKFLOW_REGISTRY, INVENTORY_OPERATIONS_AGENT,
)
from app.models import (
    AgentRun, AgentRunStatus, AgentTask, Base, OutboxEvent, OutboxEventStatus,
    Platform, Product, User, UserRole, Workspace,
)
from app.schemas import AgentTaskCreate
from app.services import outbox
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


def test_outbox_success_publishes_once_without_loading_worker(database, monkeypatch):
    engine, ids = database
    with Session(engine) as db:
        _, _, event = _create(db, ids)
        db.commit()
        event_id = event.id
    published = []
    monkeypatch.setattr(outbox, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(outbox, "_publish_event", lambda event: published.append(event.id))
    assert outbox.dispatch_pending_outbox_events() == 1
    assert outbox.dispatch_pending_outbox_events() == 0
    assert published == [event_id]
    with Session(engine) as db:
        event = db.get(OutboxEvent, event_id)
        assert event.status == OutboxEventStatus.PUBLISHED
        assert event.attempts == 1
        assert event.published_at is not None


def test_outbox_failure_keeps_record_for_later_retry(database, monkeypatch):
    engine, ids = database
    with Session(engine) as db:
        _, _, event = _create(db, ids)
        db.commit()
        event_id = event.id
    def fail_publish(event):
        raise RuntimeError("模拟消息队列暂时不可用")
    monkeypatch.setattr(outbox, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(outbox, "_publish_event", fail_publish)
    assert outbox.dispatch_pending_outbox_events() == 0
    with Session(engine) as db:
        event = db.get(OutboxEvent, event_id)
        assert event.status == OutboxEventStatus.PENDING
        assert event.attempts == 1
        assert "暂时不可用" in event.error
        assert event.available_at.replace(tzinfo=UTC) > datetime.now(UTC)
