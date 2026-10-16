"""扫描已到期的媒体任务；API、Worker 与调度进程使用同一份 api/.env。"""
import logging
import time
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import GenerationJob, GenerationJobStatus
from app.services.generation_jobs import dispatch_generation_job

logger = logging.getLogger(__name__)
SCAN_INTERVAL_SECONDS = 5
BATCH_SIZE = 20


def dispatch_due_generation_jobs() -> int:
    """重新投递到期的 pending 任务，包括失败后等待重试和漏投递任务。"""
    now = datetime.now(UTC)
    with SessionLocal() as db:
        job_ids = list(db.scalars(
            select(GenerationJob.id)
            .where(
                GenerationJob.status == GenerationJobStatus.PENDING,
                (GenerationJob.next_run_at.is_(None)) | (GenerationJob.next_run_at <= now),
            )
            .order_by(GenerationJob.created_at.asc(), GenerationJob.id.asc())
            .limit(BATCH_SIZE)
        ))

    dispatched = 0
    for job_id in job_ids:
        try:
            # celery 模式投递消息；inline 模式在当前调度进程内执行。
            # 执行服务仍会在行锁内检查状态和到期时间，重复消息不会重复启动。
            dispatch_generation_job(job_id)
            dispatched += 1
        except Exception as exc:
            # 不打印可能包含连接密码的完整异常；保留 pending，下一轮再投递。
            logger.warning("任务 %s 调度失败，异常类型：%s", job_id, type(exc).__name__)
    return dispatched


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("媒体任务调度器启动：每 %s 秒扫描一次到期任务。", SCAN_INTERVAL_SECONDS)
    try:
        while True:
            try:
                count = dispatch_due_generation_jobs()
                if count:
                    logger.info("本轮处理 %s 条到期任务。", count)
            except Exception as exc:
                logger.warning("扫描失败，异常类型：%s；下一轮继续。", type(exc).__name__)
            time.sleep(SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("媒体任务调度器已停止。")


if __name__ == "__main__":
    main()
