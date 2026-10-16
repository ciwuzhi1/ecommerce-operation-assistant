from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Base,
    CreativePlan,
    CreativePlanType,
    GenerationJobEvent,
    GenerationJobKind,
    GenerationJobStatus,
    Product,
)
from app.services import generation_jobs
from app.services.generation_jobs import (
    cancel_generation_job_record,
    enqueue_generation_job,
    mark_stale_running_generation_jobs,
    retry_generation_job_record,
)


def test_enqueue_generation_job_sets_queue_fields() -> None:
    """验证“enqueue生成任务任务sets队列fields”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        product = Product(name="oil control cushion")
        plan = CreativePlan(
            product=product,
            type=CreativePlanType.MAIN_IMAGE,
            title="main image",
            content={},
        )
        db.add_all([product, plan])
        db.flush()

        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        )
        db.commit()
        db.refresh(job)

        assert job.status == GenerationJobStatus.PENDING
        assert job.attempts == 0
        assert job.max_attempts == 3
        assert job.next_run_at is not None
        event = db.query(GenerationJobEvent).one()
        assert event.event_type == "queued"
        assert event.status == GenerationJobStatus.PENDING
        assert event.payload["kind"] == "main_image_asset"


def test_retry_generation_job_record_clears_lock_and_error() -> None:
    """验证“重试生成任务任务记录clears锁定and错误”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        product = Product(name="oil control cushion")
        plan = CreativePlan(
            product=product,
            type=CreativePlanType.VIDEO_SCRIPT,
            title="video",
            content={},
        )
        db.add_all([product, plan])
        db.flush()
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.VIDEO_ASSET,
        )
        job.status = GenerationJobStatus.FAILED
        job.error = "temporary"
        job.locked_by = "worker-1"

        retry_generation_job_record(job)

        assert job.status == GenerationJobStatus.PENDING
        assert job.error is None
        assert job.locked_by is None
        assert job.next_run_at is not None
        db.flush()
        event = db.query(GenerationJobEvent).filter_by(job_id=job.id, event_type="retry_requested").one()
        assert event.event_type == "retry_requested"


def test_cancel_generation_job_record_marks_pending_job_cancelled() -> None:
    """验证“取消生成任务任务记录markspending任务cancelled”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        product, plan = _seed_product_and_plan(db)
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        )

        cancelled = cancel_generation_job_record(job, reason="manual stop")
        db.flush()

        assert cancelled is True
        assert job.status == GenerationJobStatus.CANCELLED
        assert job.next_run_at is None
        event = db.query(GenerationJobEvent).filter_by(job_id=job.id, event_type="cancelled").one()
        assert event.message == "manual stop"


def test_mark_stale_running_generation_jobs_requeues_before_max_attempts() -> None:
    """验证“标记超时running生成任务jobsrequeuesbeforemaxattempts”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        product, plan = _seed_product_and_plan(db)
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        )
        job.status = GenerationJobStatus.RUNNING
        job.attempts = 1
        job.started_at = datetime.now(UTC) - timedelta(minutes=45)
        job.locked_by = "worker-timeout"
        db.flush()

        count = mark_stale_running_generation_jobs(db, timeout_minutes=30, now=datetime.now(UTC))

        assert count == 1
        assert job.status == GenerationJobStatus.PENDING
        assert job.locked_by is None
        assert job.next_run_at is not None
        assert db.query(GenerationJobEvent).filter_by(job_id=job.id, event_type="timeout_checked").count() == 1


def test_mark_stale_running_generation_jobs_fails_after_max_attempts() -> None:
    """验证“标记超时running生成任务jobsfailsaftermaxattempts”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        product, plan = _seed_product_and_plan(db)
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        )
        job.status = GenerationJobStatus.RUNNING
        job.attempts = job.max_attempts
        job.started_at = datetime.now(UTC) - timedelta(minutes=45)
        db.flush()

        count = mark_stale_running_generation_jobs(db, timeout_minutes=30, now=datetime.now(UTC))

        assert count == 1
        assert job.status == GenerationJobStatus.FAILED
        assert job.next_run_at is None
        assert "超时处理" in (job.error or "")


def test_dispatch_generation_job_uses_inline_background_task(monkeypatch) -> None:
    """验证“调度生成任务任务usesinlinebackground任务”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    class Settings:
        task_queue_backend = "inline"

    class BackgroundTasks:
        def __init__(self) -> None:
            """初始化 BackgroundTasks 的依赖与运行状态，避免执行阶段临时拼装共享资源。"""
            self.calls = []

        def add_task(self, func, *args) -> None:
            """构造或执行测试所需的add任务，让测试数据、依赖替身与断言保持集中。"""
            self.calls.append((func, args))

    background_tasks = BackgroundTasks()
    monkeypatch.setattr(generation_jobs, "get_settings", lambda: Settings())

    generation_jobs.dispatch_generation_job(12, background_tasks)

    assert len(background_tasks.calls) == 1
    assert background_tasks.calls[0][1] == (12,)


def test_dispatch_generation_job_uses_celery_when_configured(monkeypatch) -> None:
    """验证“调度生成任务任务usescelerywhenconfigured”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    class Settings:
        task_queue_backend = "celery"

    class FakeCeleryTask:
        calls: list[int] = []

        @classmethod
        def delay(cls, job_id: int) -> None:
            """构造或执行测试所需的delay，让测试数据、依赖替身与断言保持集中。"""
            cls.calls.append(job_id)

    monkeypatch.setattr(generation_jobs, "get_settings", lambda: Settings())
    monkeypatch.setattr("app.worker.tasks.run_generation_job_task", FakeCeleryTask)

    generation_jobs.dispatch_generation_job(42)

    assert FakeCeleryTask.calls == [42]


def _session() -> Session:
    """构造或执行测试所需的会话，让测试数据、依赖替身与断言保持集中。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_product_and_plan(db: Session) -> tuple[Product, CreativePlan]:
    """创建素材生成任务测试所需的商品与主图方案，并保留同一会话关系。"""
    # 使用 ORM 关系绑定方案和商品，确保队列测试覆盖真实外键与 flush 行为。
    product = Product(name="oil control cushion")
    plan = CreativePlan(
        product=product,
        type=CreativePlanType.MAIN_IMAGE,
        title="main image",
        content={},
    )
    db.add_all([product, plan])
    db.flush()
    return product, plan
