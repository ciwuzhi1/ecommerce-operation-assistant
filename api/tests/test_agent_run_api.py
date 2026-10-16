from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import agent_runs
from app.agents.contracts import AgentDraftOutput, ReviewResumePayload
from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import AgentRun, AgentRunStatus, Base, Platform, Product, User, UserRole
from app.models import AgentRunOperation, CreativePlan, ProductDiagnosis
from app.services import agent_runs as agent_run_service


def test_operator_can_queue_agent_run(monkeypatch) -> None:
    """验证“operatorcan队列Agent执行”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, user_id = _seed_product_and_user(engine)
    dispatched: list[tuple[int, dict[str, Any] | None]] = []
    monkeypatch.setattr(
        agent_runs,
        "dispatch_agent_run",
        lambda run_id, payload=None: dispatched.append((run_id, payload)),
    )

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(user_id, UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            f"/api/v1/products/{product_id}/agent-runs",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["events"][0]["event_type"] == "queued"
    assert dispatched == [(response.json()["id"], None)]


def test_product_rejects_second_active_agent_run(monkeypatch) -> None:
    """验证“商品rejectssecond有效Agent执行”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, user_id = _seed_product_and_user(engine)
    monkeypatch.setattr(agent_runs, "dispatch_agent_run", lambda *args, **kwargs: None)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(user_id, UserRole.OPERATOR)
    try:
        client = TestClient(app)
        first = client.post(
            f"/api/v1/products/{product_id}/agent-runs",
            headers={"Authorization": "Bearer test"},
        )
        second = client.post(
            f"/api/v1/products/{product_id}/agent-runs",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 202
    assert second.status_code == 409


def test_operator_can_resume_awaiting_review(monkeypatch) -> None:
    """验证“operatorcanresumeawaiting审核”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, user_id = _seed_product_and_user(engine)
    run_id = _seed_awaiting_review_run(engine, product_id, user_id)
    dispatched: list[tuple[int, dict[str, Any] | None]] = []
    monkeypatch.setattr(
        agent_runs,
        "dispatch_agent_run",
        lambda current_run_id, payload=None: dispatched.append((current_run_id, payload)),
    )

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(user_id, UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            f"/api/v1/agent-runs/{run_id}/review",
            json={"decision": "approve", "note": "确认采用"},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["status"] == "resume_queued"
    assert response.json()["reviews"][0]["decision"] == "approve"
    assert dispatched[0][0] == run_id
    assert dispatched[0][1]["decision"] == "approve"


def test_viewer_cannot_start_or_review_agent_run(monkeypatch) -> None:
    """验证“viewercannot启动or审核Agent执行”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, user_id = _seed_product_and_user(engine)
    run_id = _seed_awaiting_review_run(engine, product_id, user_id)
    monkeypatch.setattr(agent_runs, "dispatch_agent_run", lambda *args, **kwargs: None)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(user_id, UserRole.VIEWER)
    try:
        client = TestClient(app)
        create_response = client.post(
            f"/api/v1/products/{product_id}/agent-runs",
            headers={"Authorization": "Bearer test"},
        )
        review_response = client.post(
            f"/api/v1/agent-runs/{run_id}/review",
            json={"decision": "reject"},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert create_response.status_code == 403
    assert review_response.status_code == 403


def test_finalize_operation_is_idempotent(monkeypatch) -> None:
    """验证“完成落库操作判断idempotent”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    product_id, user_id = _seed_product_and_user(engine)
    run_id = _seed_awaiting_review_run(engine, product_id, user_id)
    lease_owner = "test-finalizer-lease"
    with Session(engine) as db:
        run = db.get(AgentRun, run_id)
        run.status = AgentRunStatus.RUNNING
        run.lease_owner = lease_owner
        db.commit()
    monkeypatch.setattr(agent_run_service, "SessionLocal", sessionmaker(bind=engine))
    approved_output = AgentDraftOutput.model_validate(_approved_output())
    review = ReviewResumePayload(decision="approve")

    first = agent_run_service._finalize_agent_run(
        run_id,
        review,
        approved_output,
        lease_owner=lease_owner,
    )
    second = agent_run_service._finalize_agent_run(
        run_id,
        review,
        approved_output,
        lease_owner=lease_owner,
    )

    assert first == second
    with Session(engine) as db:
        assert db.query(ProductDiagnosis).filter_by(agent_run_id=run_id).count() == 1
        assert db.query(CreativePlan).filter_by(agent_run_id=run_id).count() == 3
        assert db.query(AgentRunOperation).filter_by(run_id=run_id).count() == 1


def _seed_product_and_user(engine) -> tuple[int, int]:
    """创建 Agent Run 接口测试所需的商品和运营用户，并返回稳定主键。"""
    # 商品与用户在同一事务提交，确保后续接口测试使用真实数据库关系而不是伪造 ID。
    with Session(engine) as db:
        product = Product(name="控油气垫", platform=Platform.DOUYIN)
        user = User(
            email="operator@example.com",
            display_name="Operator",
            role=UserRole.OPERATOR,
        )
        db.add_all([product, user])
        db.commit()
        return product.id, user.id


def _seed_awaiting_review_run(engine, product_id: int, user_id: int) -> int:
    """构造或执行测试所需的测试数据awaiting审核执行，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with Session(engine) as db:
        run = AgentRun(
            thread_id=f"00000000-0000-0000-0000-{product_id:012d}",
            product_id=product_id,
            requested_by_user_id=user_id,
            workflow_key="product_operation",
            workflow_version="1.0.0",
            status=AgentRunStatus.AWAITING_REVIEW,
            revision_count=0,
            max_revisions=1,
            budget={"max_total_tokens": 5000},
            usage={},
            version_manifest={},
            context_snapshot={},
            draft_output={},
            quality_report={},
            final_output={},
        )
        db.add(run)
        db.commit()
        return run.id


def _override_db(engine):
    """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
    def override_db():
        """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
        with Session(engine) as db:
            yield db

    return override_db


def _user(user_id: int, role: UserRole) -> User:
    """构造或执行测试所需的用户，让测试数据、依赖替身与断言保持集中。"""
    return User(
        id=user_id,
        email=f"{role.value}@example.com",
        display_name=role.value,
        role=role,
    )


def _engine():
    """构造或执行测试所需的engine，让测试数据、依赖替身与断言保持集中。"""
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _approved_output() -> dict[str, Any]:
    """构造或执行测试所需的approved输出，让测试数据、依赖替身与断言保持集中。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    return {
        "diagnosis": {
            "source": "rules",
            "positioning": "通勤控油底妆",
            "price_band": "中位价格带",
            "audience_insights": ["通勤时间长", "关注持妆"],
            "pain_points": ["易出油", "补妆麻烦"],
            "selling_point_analysis": ["控油对应核心痛点"],
            "risks": ["需要真实素材证明"],
            "recommendations": ["测试场景主图", "测试对比主图"],
            "provenance": {},
        },
        "creative_plans": [
            {
                "title": f"方案 {index}",
                "angle": f"角度 {index}",
                "layout": "商品居中，文案置顶",
                "headline": f"通勤控油 {index}",
                "sub_headline": "实际效果以使用为准",
                "visual_focus": "商品与通勤场景",
                "proof_points": ["产品参数"],
                "suitable_audience": "通勤人群",
                "image_prompt": "电商主图，干净背景",
                "source": "rules",
                "provenance": {},
            }
            for index in range(1, 4)
        ],
    }
