from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import CreativePlan, GenerationJob, GenerationJobEvent, GenerationJobKind, GenerationJobStatus
from app.services.generated_assets import create_generated_asset
from app.services.image_generation import generate_main_image_asset
from app.services.video_generation import generate_video_asset


DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RUNNING_TIMEOUT_MINUTES = 30


def enqueue_generation_job(
    db: Session,
    product_id: int,
    creative_plan_id: int,
    kind: GenerationJobKind,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> GenerationJob:
    # 生成图片/视频可能耗时较长，API 只负责落任务记录，实际执行交给后台队列并保留可追踪状态。
    """enqueue生成任务任务；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    job = GenerationJob(
        product_id=product_id,
        creative_plan_id=creative_plan_id,
        kind=kind,
        status=GenerationJobStatus.PENDING,
        result={},
        attempts=0,
        max_attempts=max_attempts,
        next_run_at=datetime.now(UTC),
    )
    db.add(job)
    record_generation_job_event(
        job,
        "queued",
        message="生成任务已入队。",
        payload={"kind": kind.value, "max_attempts": max_attempts},
    )
    return job


def retry_generation_job_record(job: GenerationJob) -> None:
    # 重试时清空上一次执行痕迹，但保留同一任务 ID，前端和审计日志可以串起完整生命周期。
    """重试生成任务任务记录；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    job.status = GenerationJobStatus.PENDING
    job.result = {}
    job.error = None
    job.locked_at = None
    job.locked_by = None
    job.started_at = None
    job.finished_at = None
    job.next_run_at = datetime.now(UTC)
    record_generation_job_event(
        job,
        "retry_requested",
        message="用户请求重试生成任务。",
        payload={"next_run_at": job.next_run_at.isoformat()},
    )


def cancel_generation_job_record(job: GenerationJob, *, reason: str | None = None) -> bool:
    # 只允许取消尚未结束的任务；已成功或失败的记录是历史事实，不在这里做状态回滚。
    """取消生成任务任务记录；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if job.status not in {GenerationJobStatus.PENDING, GenerationJobStatus.RUNNING}:
        return False
    job.status = GenerationJobStatus.CANCELLED
    job.error = reason or "任务已取消。"
    job.locked_at = None
    job.locked_by = None
    job.next_run_at = None
    job.finished_at = datetime.now(UTC)
    record_generation_job_event(
        job,
        "cancelled",
        message=job.error,
        payload={"reason": reason or "user_cancelled"},
    )
    return True


def mark_stale_running_generation_jobs(
    db: Session,
    *,
    timeout_minutes: int = DEFAULT_RUNNING_TIMEOUT_MINUTES,
    now: datetime | None = None,
) -> int:
    """标记超时running生成任务jobs；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    current_time = now or datetime.now(UTC)
    deadline = current_time - timedelta(minutes=timeout_minutes)
    jobs = db.scalars(
        select(GenerationJob).where(
            GenerationJob.status == GenerationJobStatus.RUNNING,
            GenerationJob.started_at.is_not(None),
            GenerationJob.started_at <= deadline,
        )
    ).all()
    for job in jobs:
        # 超时任务视为 worker 执行链路中断：释放锁并按重试策略重新排队，避免长期卡在 running。
        _mark_failed_or_retry(job, RuntimeError(f"生成任务运行超过 {timeout_minutes} 分钟，已按超时处理。"))
        job.locked_at = None
        job.locked_by = None
        job.finished_at = current_time
        record_generation_job_event(
            job,
            "timeout_checked",
            message="调度器已处理运行超时任务。",
            payload={"timeout_minutes": timeout_minutes},
        )
    db.commit()
    return len(jobs)


def dispatch_generation_job(job_id: int, background_tasks: object | None = None) -> None:
    """调度生成任务任务；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    settings = get_settings()
    if settings.task_queue_backend == "celery":
        # 生产环境优先走 Celery，避免长耗时生成阻塞 Web 进程，也便于后续横向扩 worker。
        from app.worker.tasks import run_generation_job_task

        run_generation_job_task.delay(job_id)
        return

    if background_tasks is not None and hasattr(background_tasks, "add_task"):
        # 本地和轻量部署可使用 FastAPI background task，保持原型部署简单。
        background_tasks.add_task(run_generation_job, job_id)
        return

    run_generation_job(job_id)


def process_next_generation_job(worker_id: str = "fastapi-background") -> int | None:
    """处理下次生成任务任务；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    now = datetime.now(UTC)
    with SessionLocal() as db:
        # 单次只取最早可执行任务，便于用定时器或单 worker 轮询时控制并发和重试节奏。
        statement = (
            select(GenerationJob)
            .where(
                GenerationJob.status == GenerationJobStatus.PENDING,
                (GenerationJob.next_run_at.is_(None)) | (GenerationJob.next_run_at <= now),
            )
            .order_by(GenerationJob.created_at.asc())
            .limit(1)
        )
        job = db.scalars(statement).first()
        if job is None:
            return None
        job_id = job.id

    run_generation_job(job_id, worker_id=worker_id)
    return job_id


def run_generation_job(job_id: int, worker_id: str = "fastapi-background") -> None:
    """执行生成任务任务；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    with SessionLocal() as db:
        # MySQL 行锁让 API 后台、调度器和 Worker 的重复消息只能有一个开始执行。
        job = db.get(GenerationJob, job_id, with_for_update=True)
        # 任务可能被用户取消、重试或其他 worker 抢先处理；非 pending 时直接退出，避免重复生成素材。
        if job is None or job.status != GenerationJobStatus.PENDING:
            return

        # SQLite/MySQL 驱动可能返回无时区值，数据库时间按 UTC 解释。
        due_at = job.next_run_at
        if due_at is not None and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        if due_at is not None and due_at > datetime.now(UTC):
            return

        _mark_running(job, worker_id)
        db.commit()

        try:
            creative_plan = db.scalars(
                select(CreativePlan).where(CreativePlan.id == job.creative_plan_id)
            ).first()
            if creative_plan is None:
                raise RuntimeError("Creative plan not found.")

            asset = _generate_asset(db, job, creative_plan)
            job.result = asset
            job.status = GenerationJobStatus.SUCCEEDED
            job.error = None
            job.next_run_at = None
            record_generation_job_event(
                job,
                "succeeded",
                message="生成任务执行成功。",
                payload={"result_url": asset.get("url"), "attempts": job.attempts},
                worker_id=worker_id,
            )
        except Exception as exc:
            _mark_failed_or_retry(job, exc)
        finally:
            job.locked_at = None
            job.locked_by = None
            job.finished_at = datetime.now(UTC)
            db.commit()


def _mark_running(job: GenerationJob, worker_id: str) -> None:
    """标记running，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    job.status = GenerationJobStatus.RUNNING
    job.attempts += 1
    job.started_at = datetime.now(UTC)
    job.finished_at = None
    job.locked_at = job.started_at
    job.locked_by = worker_id
    record_generation_job_event(
        job,
        "started",
        message="worker 已开始执行生成任务。",
        payload={"attempts": job.attempts},
        worker_id=worker_id,
    )


def _generate_asset(db: Session, job: GenerationJob, creative_plan: CreativePlan) -> dict:
    """生成素材，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if job.kind == GenerationJobKind.MAIN_IMAGE_ASSET:
        asset = generate_main_image_asset(creative_plan)
        _append_generated_asset(creative_plan, "generated_images", asset)
        create_generated_asset(db, creative_plan, "image", asset, job.id)
        return asset
    if job.kind == GenerationJobKind.VIDEO_ASSET:
        asset = generate_video_asset(creative_plan)
        _append_generated_asset(creative_plan, "generated_videos", asset)
        create_generated_asset(db, creative_plan, "video", asset, job.id)
        return asset
    raise RuntimeError(f"Unsupported generation job kind: {job.kind}")


def _mark_failed_or_retry(job: GenerationJob, exc: Exception) -> None:
    """标记失败or重试，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    job.error = str(exc)[:2000]
    if job.attempts < job.max_attempts:
        # 外部生成供应商偶发超时较常见，采用短退避重试；超过上限后保留失败状态等待人工处理。
        job.status = GenerationJobStatus.PENDING
        job.next_run_at = datetime.now(UTC) + timedelta(minutes=min(job.attempts * 2, 10))
        record_generation_job_event(
            job,
            "retry_scheduled",
            message=job.error,
            payload={"attempts": job.attempts, "next_run_at": job.next_run_at.isoformat()},
        )
        return
    job.status = GenerationJobStatus.FAILED
    job.next_run_at = None
    record_generation_job_event(
        job,
        "failed",
        message=job.error,
        payload={"attempts": job.attempts},
    )


def _append_generated_asset(creative_plan: CreativePlan, key: str, asset: dict) -> None:
    """追加生成素材，统一主流程中的格式、默认值和异常边界。"""
    content = dict(creative_plan.content or {})
    existing = content.get(key, [])
    if not isinstance(existing, list):
        existing = []
    # 最新素材放在最前面，详情页展示和运营复核时优先看到最近一次生成结果。
    content[key] = [asset, *existing]
    creative_plan.content = content


def record_generation_job_event(
    job: GenerationJob,
    event_type: str,
    *,
    message: str | None = None,
    payload: dict | None = None,
    worker_id: str | None = None,
) -> GenerationJobEvent:
    # 事件日志用于排查任务生命周期，只记录状态和安全摘要，不保存模型 API key 或完整外部响应。
    """记录生成任务任务事件；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    event = GenerationJobEvent(
        event_type=event_type,
        status=job.status,
        message=message,
        payload=payload or {},
        worker_id=worker_id,
    )
    job.events.append(event)
    return event
