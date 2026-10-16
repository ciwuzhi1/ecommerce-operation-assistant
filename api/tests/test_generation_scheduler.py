"""第17章调度闭环；内存数据库和媒体替身，不使用真实供应商。"""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import products
from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import Base, CreativePlan, CreativePlanType, GenerationJob, GenerationJobKind, GenerationJobStatus, Product, User, UserRole
from app.services import generation_jobs
from app.worker import generation_scheduler


@pytest.fixture
def runtime(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(generation_jobs, "SessionLocal", factory)
    monkeypatch.setattr(generation_scheduler, "SessionLocal", factory)
    with factory() as db:
        product = Product(name="低糖燕麦饼干")
        plan = CreativePlan(product=product, type=CreativePlanType.MAIN_IMAGE, title="课堂主图", content={})
        db.add_all([product, plan])
        db.flush()
        job = generation_jobs.enqueue_generation_job(
            db, product.id, plan.id, GenerationJobKind.MAIN_IMAGE_ASSET
        )
        db.commit()
        ids = (product.id, plan.id, job.id)
    try:
        yield factory, ids
    finally:
        engine.dispose()


def test_scheduler_skips_future_and_cancelled_and_recovers_dispatch_error(runtime, monkeypatch):
    factory, (_, _, job_id) = runtime
    calls = []
    def fail(job_id):
        calls.append(job_id)
        raise ConnectionError("simulated broker outage")
    monkeypatch.setattr(generation_scheduler, "dispatch_generation_job", fail)
    assert generation_scheduler.dispatch_due_generation_jobs() == 0
    with factory() as db:
        assert db.get(GenerationJob, job_id).status == GenerationJobStatus.PENDING
    monkeypatch.setattr(generation_scheduler, "dispatch_generation_job", calls.append)
    assert generation_scheduler.dispatch_due_generation_jobs() == 1
    with factory() as db:
        job = db.get(GenerationJob, job_id)
        job.next_run_at = datetime.now(UTC) + timedelta(minutes=5)
        db.commit()
    assert generation_scheduler.dispatch_due_generation_jobs() == 0
    with factory() as db:
        job = db.get(GenerationJob, job_id)
        job.next_run_at = datetime.now(UTC) - timedelta(seconds=1)
        generation_jobs.cancel_generation_job_record(job)
        db.commit()
    assert generation_scheduler.dispatch_due_generation_jobs() == 0


def test_failed_attempt_is_scanned_and_succeeds_without_new_job(runtime, monkeypatch):
    factory, (_, _, job_id) = runtime
    calls = []
    def media(db, job, plan):
        calls.append(job.id)
        if len(calls) == 1:
            raise RuntimeError("temporary media failure")
        return {"url": "/uploads/test.png"}
    monkeypatch.setattr(generation_jobs, "_generate_asset", media)
    monkeypatch.setattr(generation_scheduler, "dispatch_generation_job", generation_jobs.run_generation_job)
    assert generation_scheduler.dispatch_due_generation_jobs() == 1
    with factory() as db:
        job = db.get(GenerationJob, job_id)
        assert job.status == GenerationJobStatus.PENDING
        assert job.attempts == 1
        assert any(e.event_type == "retry_scheduled" for e in job.events)
    # 模拟重复消息早到，不能跳过退避时间。
    generation_jobs.run_generation_job(job_id)
    assert len(calls) == 1
    with factory() as db:
        db.get(GenerationJob, job_id).next_run_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert generation_scheduler.dispatch_due_generation_jobs() == 1
    with factory() as db:
        job = db.get(GenerationJob, job_id)
        assert job.status == GenerationJobStatus.SUCCEEDED
        assert job.attempts == 2
        assert job.result["url"] == "/uploads/test.png"
        assert db.query(GenerationJob).count() == 1
    generation_jobs.run_generation_job(job_id)
    assert len(calls) == 2


def test_scheduler_stops_after_max_attempts(runtime, monkeypatch):
    factory, (_, _, job_id) = runtime
    def fail(db, job, plan):
        raise RuntimeError("persistent failure")
    monkeypatch.setattr(generation_jobs, "_generate_asset", fail)
    monkeypatch.setattr(generation_scheduler, "dispatch_generation_job", generation_jobs.run_generation_job)
    for attempt in range(1, 4):
        with factory() as db:
            db.get(GenerationJob, job_id).next_run_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
        assert generation_scheduler.dispatch_due_generation_jobs() == 1
        with factory() as db:
            job = db.get(GenerationJob, job_id)
            assert job.attempts == attempt
            expected = GenerationJobStatus.FAILED if attempt == 3 else GenerationJobStatus.PENDING
            assert job.status == expected
    assert generation_scheduler.dispatch_due_generation_jobs() == 0


def test_routes_submit_cancel_retry_and_reject_wrong_plan(runtime, monkeypatch):
    factory, (product_id, plan_id, job_id) = runtime
    dispatched = []
    monkeypatch.setattr(products, "dispatch_generation_job", lambda id, background: dispatched.append(id))
    def db_override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, email="class@example.com", display_name="课堂运营", role=UserRole.OPERATOR
    )
    try:
        with TestClient(app) as client:
            path = f"/api/v1/products/{product_id}"
            response = client.post(path + f"/creative-plans/{plan_id}/images/generate")
            assert response.status_code == 202, response.text
            new_id = response.json()["id"]
            assert response.json()["kind"] == "main_image_asset"
            assert new_id in dispatched
            assert client.post(path + f"/creative-plans/{plan_id}/videos/generate").status_code == 400
            response = client.post(path + f"/generation-jobs/{new_id}/cancel")
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "cancelled"
            assert client.post(path + f"/generation-jobs/{new_id}/retry").status_code == 400
            with factory() as db:
                job = db.get(GenerationJob, job_id)
                job.status = GenerationJobStatus.FAILED
                job.error = "test failure"
                db.commit()
            response = client.post(path + f"/generation-jobs/{job_id}/retry")
            assert response.status_code == 202, response.text
            assert response.json()["id"] == job_id
            assert response.json()["error"] is None
            assert client.post(path + "/generation-jobs/999999/cancel").status_code == 404
    finally:
        app.dependency_overrides.clear()
