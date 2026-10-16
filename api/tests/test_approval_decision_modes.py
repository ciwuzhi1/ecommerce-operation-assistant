"""审批三决策与错误码字段（DesignSpec §6 API-07、§6 错误码体系 / ADR-07）。

覆盖：
- 决策契约校验：「修改后通过」必须带完整结果，其余决策不得携带
- 服务层：三种决策分别落到正确的审批状态，且恢复载荷符合编排图合同
- 响应体：错误响应确实带机器可读的 code 字段
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.agents.contracts import ReviewResumePayload
from app.api.routes.auth import get_current_user
from app.core.errors import MODEL_NOT_CONFIGURED
from app.db.session import get_db
from app.main import app
from app.models import (
    AgentApproval,
    AgentApprovalStatus,
    AgentRiskLevel,
    AgentRun,
    AgentRunStatus,
    AgentTask,
    AgentTaskStatus,
    Base,
    OutboxEvent,
    User,
    UserRole,
    Workspace,
)
from app.schemas import AgentApprovalDecisionCreate
from app.services import llm as llm_service
from app.services.agent_tasks import decide_agent_approval

def _creative_plan(index: int) -> dict[str, object]:
    """构造符合草稿契约的创意方案（契约要求 3～6 条）。"""
    return {
        "title": f"人工修改方案 {index}",
        "angle": "通勤场景",
        "layout": "左文右图",
        "headline": "三秒上妆",
        "sub_headline": "通勤不脱妆",
        "visual_focus": "产品特写",
        "proof_points": ["持妆 12 小时"],
        "suitable_audience": "通勤人群",
        "image_prompt": "product close-up, clean background",
        "source": "rules",
        "provenance": {},
    }


EDITED_OUTPUT: dict[str, object] = {
    "diagnosis": {
        "source": "rules",
        "positioning": "人工修改后的定位",
        "price_band": "中位价格带",
        "audience_insights": ["通勤人群"],
        "pain_points": ["易出油"],
        "selling_point_analysis": ["控油"],
        "risks": [],
        "recommendations": ["先测首屏"],
    },
    "creative_plans": [_creative_plan(i) for i in range(1, 4)],
}


# ---------------------------------------------------------------- 契约校验


def test_edit_and_approve_requires_complete_output() -> None:
    """「修改后通过」缺少完整结果时必须被拒绝（FR-49）。"""
    with pytest.raises(ValidationError, match="edited_output"):
        AgentApprovalDecisionCreate(decision="edit_and_approve")


def test_edit_and_approve_rejects_empty_output() -> None:
    """空对象不算完整结果。"""
    with pytest.raises(ValidationError, match="edited_output"):
        AgentApprovalDecisionCreate(decision="edit_and_approve", edited_output={})


def test_approve_must_not_carry_edited_output() -> None:
    """只有「修改后通过」允许携带结果，避免语义混淆。"""
    with pytest.raises(ValidationError, match="only allowed"):
        AgentApprovalDecisionCreate(decision="approve", edited_output=EDITED_OUTPUT)


def test_three_decisions_are_accepted() -> None:
    """三种决策各自成立。"""
    assert AgentApprovalDecisionCreate(decision="approve").decision == "approve"
    assert AgentApprovalDecisionCreate(decision="reject").decision == "reject"
    edited = AgentApprovalDecisionCreate(decision="edit_and_approve", edited_output=EDITED_OUTPUT)
    assert edited.edited_output == EDITED_OUTPUT


# ---------------------------------------------------------------- 服务层


def _engine():
    return create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )


def _seed_pending_approval(engine, *, risk: AgentRiskLevel = AgentRiskLevel.R2) -> tuple[int, int]:
    """建立一条待审批的 任务 / 运行 / 审批 链路，返回（审批 id, 复核人 id）。"""
    with Session(engine) as db:
        workspace = Workspace(slug="approval-test", name="审批测试工作区")
        db.add(workspace)
        db.flush()

        requester = User(
            email="requester@example.com", display_name="申请人", role=UserRole.OPERATOR
        )
        reviewer = User(email="owner@example.com", display_name="所有者", role=UserRole.OWNER)
        db.add_all([requester, reviewer])
        db.flush()

        task = AgentTask(
            workspace_id=workspace.id,
            requested_by_user_id=requester.id,
            workflow_key="product_operation",
            workflow_version="1.0.0",
            title="审批测试任务",
            status=AgentTaskStatus.AWAITING_APPROVAL,
            risk_level=risk,
        )
        db.add(task)
        db.flush()

        run = AgentRun(
            thread_id="11111111-1111-1111-1111-111111111111",
            workspace_id=workspace.id,
            task_id=task.id,
            requested_by_user_id=requester.id,
            workflow_key="product_operation",
            workflow_version="1.0.0",
            status=AgentRunStatus.AWAITING_REVIEW,
            revision_count=0,
            max_revisions=1,
            budget={},
            usage={},
            version_manifest={},
            context_snapshot={},
            draft_output={},
            quality_report={},
            final_output={},
        )
        db.add(run)
        db.flush()

        approval = AgentApproval(
            workspace_id=workspace.id,
            task_id=task.id,
            run_id=run.id,
            requested_by_user_id=requester.id,
            action_key="workflow.accept_result",
            risk_level=risk,
            status=AgentApprovalStatus.PENDING,
            request_payload={},
            decision_payload={},
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        db.add(approval)
        db.commit()
        return approval.id, reviewer.id


def _decide(engine, approval_id: int, reviewer_id: int, **kwargs):
    """在独立事务里执行一次审批决策，返回（审批状态, 恢复载荷）。"""
    with Session(engine) as db:
        approval = db.get(AgentApproval, approval_id)
        reviewer = db.get(User, reviewer_id)
        decide_agent_approval(
            db,
            approval=approval,
            reviewer=reviewer,
            reviewer_role=reviewer.role,
            decision=kwargs["decision"],
            note=kwargs.get("note"),
            decision_payload=kwargs.get("decision_payload") or {},
            edited_output=kwargs.get("edited_output"),
        )
        db.commit()
        status = approval.status
        # 驳回不进恢复队列，因此不产生投递事件。
        event = db.query(OutboxEvent).order_by(OutboxEvent.id.desc()).first()
        if event is None:
            return status, None
        payload = json.loads(event.payload) if isinstance(event.payload, str) else event.payload
        return status, payload["resume_payload"]


@pytest.mark.parametrize(
    ("decision", "expected_status"),
    [
        ("approve", AgentApprovalStatus.APPROVED),
        ("edit_and_approve", AgentApprovalStatus.APPROVED),
        ("reject", AgentApprovalStatus.REJECTED),
    ],
)
def test_decision_lands_on_expected_approval_status(decision, expected_status) -> None:
    """三种决策分别落到正确状态；通过类决策进入恢复队列，驳回不进恢复。"""
    engine = _engine()
    Base.metadata.create_all(engine)
    approval_id, reviewer_id = _seed_pending_approval(engine)

    kwargs = {"decision": decision}
    if decision == "edit_and_approve":
        kwargs["edited_output"] = EDITED_OUTPUT

    status, resume_payload = _decide(engine, approval_id, reviewer_id, **kwargs)
    assert status == expected_status

    if decision == "reject":
        assert resume_payload is None
    else:
        # 恢复载荷必须能被编排图的审批合同严格解析（禁止额外字段）。
        parsed = ReviewResumePayload.model_validate(resume_payload)
        assert parsed.decision == decision
        if decision == "edit_and_approve":
            assert parsed.edited_output is not None


def test_edited_output_is_preserved_on_approval_record() -> None:
    """人工修改后的结果必须留痕，便于审计「批的是什么」。"""
    engine = _engine()
    Base.metadata.create_all(engine)
    approval_id, reviewer_id = _seed_pending_approval(engine)
    _decide(
        engine,
        approval_id,
        reviewer_id,
        decision="edit_and_approve",
        edited_output=EDITED_OUTPUT,
    )
    with Session(engine) as db:
        approval = db.get(AgentApproval, approval_id)
        assert approval.decision_payload["edited_output"] == EDITED_OUTPUT


def test_reject_is_allowed_for_r2_without_owner() -> None:
    """R2 审批不要求所有者，运营人员即可驳回。"""
    engine = _engine()
    Base.metadata.create_all(engine)
    approval_id, _owner_id = _seed_pending_approval(engine)
    with Session(engine) as db:
        operator = User(email="op@example.com", display_name="运营", role=UserRole.OPERATOR)
        db.add(operator)
        db.commit()
        operator_id = operator.id
    status, _ = _decide(engine, approval_id, operator_id, decision="reject")
    assert status == AgentApprovalStatus.REJECTED


# ---------------------------------------------------------------- 错误码字段


def test_error_response_carries_machine_readable_code(monkeypatch) -> None:
    """未配置模型时，响应体必须带 code 字段而不仅是自然语言 detail（ADR-07）。"""
    monkeypatch.setattr(llm_service, "is_llm_configured", lambda *a, **k: False)

    engine = _engine()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="owner2@example.com", display_name="所有者", role=UserRole.OWNER)
        db.add(user)
        db.commit()
        user_id = user.id

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=user_id, email="owner2@example.com", display_name="所有者", role=UserRole.OWNER
    )
    try:
        response = TestClient(app).post("/api/v1/model-settings/test", json={"target": "text"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == MODEL_NOT_CONFIGURED
    # detail 文本保留，保证向后兼容。
    assert body["detail"]
