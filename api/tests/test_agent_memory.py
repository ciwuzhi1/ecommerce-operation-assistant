"""T-21 记忆冲突消解验收：新覆盖旧、作用域隔离、审计痕迹保留与事务边界。"""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import (
    AgentMemory,
    AgentMemoryStatus,
    Base,
    Platform,
    Product,
    Store,
    User,
    UserRole,
    Workspace,
)
from app.schemas import AgentMemoryCreate
from app.services.agent_tasks import (
    AgentTaskStateError,
    create_agent_memory,
    revoke_agent_memory,
)


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(slug="memory-a", name="记忆甲")
        other_workspace = Workspace(slug="memory-b", name="记忆乙")
        user = User(email="memory@example.com", display_name="运营", role=UserRole.OWNER)
        db.add_all([workspace, other_workspace, user])
        db.flush()
        product = Product(workspace_id=workspace.id, name="低糖燕麦饼干", platform=Platform.DOUYIN)
        other_product = Product(workspace_id=workspace.id, name="高纤谷物棒", platform=Platform.DOUYIN)
        store = Store(workspace_id=workspace.id, name="旗舰店", platform=Platform.DOUYIN)
        db.add_all([product, other_product, store])
        db.commit()
        ids = {
            "workspace": workspace.id,
            "other_workspace": other_workspace.id,
            "user": user.id,
            "product": product.id,
            "other_product": other_product.id,
            "store": store.id,
        }
    yield engine, ids
    engine.dispose()


def _create(db, ids, *, workspace_key="workspace", scope_type="workspace", scope_id=None,
            memory_key="tone", content=None, source_type="user_confirmed", source_reference=None):
    return create_agent_memory(
        db,
        workspace_id=ids[workspace_key],
        created_by=db.get(User, ids["user"]),
        payload=AgentMemoryCreate(
            scope_type=scope_type,
            scope_id=scope_id,
            memory_key=memory_key,
            content=content if content is not None else {"value": "口语化"},
            source_type=source_type,
            source_reference=source_reference or {},
        ),
    )


def _active_count(db, **filters):
    statement = select(func.count()).select_from(AgentMemory).where(
        AgentMemory.status == AgentMemoryStatus.ACTIVE, *[getattr(AgentMemory, k) == v for k, v in filters.items()]
    )
    return db.scalar(statement)


def test_new_memory_supersedes_previous_and_keeps_audit_trace(database):
    engine, ids = database
    with Session(engine) as db:
        first = _create(db, ids, content={"value": "口语化"})
        first_id = first.id
        db.commit()

        second = _create(db, ids, content={"value": "专业书面"})
        db.commit()

        # 只有新记忆处于 ACTIVE，旧的被撤销但仍保留在库中作为审计痕迹。
        assert _active_count(db, workspace_id=ids["workspace"], memory_key="tone") == 1
        old = db.get(AgentMemory, first_id)
        assert old is not None
        assert old.status == AgentMemoryStatus.REVOKED
        assert old.revoked_at is not None
        assert old.content == {"value": "口语化"}
        assert second.status == AgentMemoryStatus.ACTIVE
        assert second.revoked_at is None


def test_supersede_only_touches_active_memories_and_reuses_revoke_semantics(database):
    engine, ids = database
    with Session(engine) as db:
        # 模拟历史遗留：同作用域已存在两条 ACTIVE 记忆（旧实现无冲突消解留下的数据）。
        for value in ("旧值一", "旧值二"):
            db.add(
                AgentMemory(
                    workspace_id=ids["workspace"],
                    created_by_user_id=ids["user"],
                    scope_type="workspace",
                    scope_id=None,
                    memory_key="tone",
                    schema_version="1.0",
                    content={"value": value},
                    source_type="user_confirmed",
                    source_reference={},
                    status=AgentMemoryStatus.ACTIVE,
                )
            )
        db.commit()
        legacy_ids = list(
            db.scalars(
                select(AgentMemory.id).where(AgentMemory.status == AgentMemoryStatus.ACTIVE)
            ).all()
        )

        _create(db, ids, content={"value": "新值"})
        db.commit()

        # 两条历史 ACTIVE 都被撤销，且撤销语义与 revoke_agent_memory 一致。
        assert _active_count(db, workspace_id=ids["workspace"], memory_key="tone") == 1
        for legacy_id in legacy_ids:
            legacy = db.get(AgentMemory, legacy_id)
            assert legacy.status == AgentMemoryStatus.REVOKED
            assert legacy.revoked_at is not None
        # 已撤销记录不参与冲突消解：再次撤销应沿用既有报错语义，不另起状态机。
        with pytest.raises(AgentTaskStateError, match="not active"):
            revoke_agent_memory(db.get(AgentMemory, legacy_ids[0]))


def test_supersede_is_scoped_by_memory_key(database):
    engine, ids = database
    with Session(engine) as db:
        _create(db, ids, memory_key="tone")
        _create(db, ids, memory_key="banned_words")
        db.commit()
        assert _active_count(db, workspace_id=ids["workspace"], memory_key="tone") == 1
        assert _active_count(db, workspace_id=ids["workspace"], memory_key="banned_words") == 1


def test_supersede_is_scoped_by_scope_type(database):
    engine, ids = database
    with Session(engine) as db:
        _create(db, ids, scope_type="product", scope_id=str(ids["product"]))
        _create(db, ids, scope_type="store", scope_id=str(ids["store"]))
        db.commit()
        assert _active_count(db, workspace_id=ids["workspace"], scope_type="product") == 1
        assert _active_count(db, workspace_id=ids["workspace"], scope_type="store") == 1


def test_supersede_is_scoped_by_scope_id(database):
    engine, ids = database
    with Session(engine) as db:
        _create(db, ids, scope_type="product", scope_id=str(ids["product"]))
        _create(db, ids, scope_type="product", scope_id=str(ids["other_product"]))
        db.commit()
        # 两个不同商品的记忆互不影响。
        assert _active_count(db, workspace_id=ids["workspace"], scope_type="product") == 2


def test_supersede_is_scoped_by_workspace(database):
    engine, ids = database
    with Session(engine) as db:
        _create(db, ids, workspace_key="workspace")
        _create(db, ids, workspace_key="other_workspace")
        db.commit()
        # 不同 Workspace 的同名记忆互不影响。
        assert _active_count(db, workspace_id=ids["workspace"], memory_key="tone") == 1
        assert _active_count(db, workspace_id=ids["other_workspace"], memory_key="tone") == 1


def test_rollback_leaves_previous_memory_active_without_partial_insert(database):
    engine, ids = database
    with Session(engine) as db:
        first = _create(db, ids)
        db.commit()
        first_id = first.id

    with Session(engine) as db:
        _create(db, ids, content={"value": "未提交的新值"})
        # 未提交即回滚：撤销动作与插入同处一个事务，不能出现旧的已失效、新的没写入的中间态。
        db.rollback()

    with Session(engine) as db:
        assert db.get(AgentMemory, first_id).status == AgentMemoryStatus.ACTIVE
        assert db.scalar(select(func.count()).select_from(AgentMemory)) == 1


def test_memory_content_is_redacted_before_persist(database):
    engine, ids = database
    with Session(engine) as db:
        memory = _create(
            db,
            ids,
            content={"value": "口语化", "api_key": "sk-live-should-not-leak"},
        )
        db.commit()
        assert memory.content["value"] == "口语化"
        assert memory.content["api_key"] == "[redacted]"
