from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Competitor, Product, PublicLinkParseTask
from app.schemas import CompetitorUrlImport
from app.services.link_extraction import LinkExtractionError, fetch_competitor_profile


def enqueue_competitor_import_task(
    db: Session,
    product: Product,
    payload: CompetitorUrlImport,
) -> PublicLinkParseTask:
    # 链接解析先落任务记录，便于前端展示状态、重试次数和失败原因，而不是同步卡住表单。
    """enqueue竞品导入任务；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    task = PublicLinkParseTask(
        product_id=product.id,
        task_type="competitor_import",
        url=str(payload.url),
        platform=payload.platform,
        status="pending",
        result={},
        next_run_at=datetime.now(timezone.utc),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def run_public_link_parse_task(db: Session, task: PublicLinkParseTask) -> PublicLinkParseTask:
    """执行公开链接链接解析任务；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if task.status not in {"pending", "failed"}:
        # 已成功或正在运行的任务保持幂等返回，避免重复创建同一竞品档案。
        return task

    now = datetime.now(timezone.utc)
    task.status = "running"
    task.error = None
    task.attempts += 1
    task.started_at = now
    # 公开链接解析只处理用户提交的 http/https 商品页，并依赖 link_extraction 的内网地址拦截。
    # 这里不保存登录态、不接收 Cookie，也不绕过验证码或平台风控。
    try:
        profile = fetch_competitor_profile(task.url)
        competitor = Competitor(
            product_id=task.product_id,
            platform=task.platform,
            url=task.url,
            review_keywords=[],
            **profile.model_payload(),
        )
        db.add(competitor)
        db.flush()
        task.status = "succeeded"
        task.result = {
            "competitor_id": competitor.id,
            "name": competitor.name,
            "title": competitor.title,
            "price": str(competitor.price) if competitor.price is not None else None,
        }
        task.finished_at = datetime.now(timezone.utc)
    except LinkExtractionError as exc:
        _mark_failed(task, str(exc))
    except Exception as exc:
        _mark_failed(task, f"公开链接解析失败：{exc}")

    db.commit()
    db.refresh(task)
    return task


def _mark_failed(task: PublicLinkParseTask, error: str) -> None:
    """标记失败，统一主流程中的格式、默认值和异常边界。"""
    task.error = error
    task.finished_at = datetime.now(timezone.utc)
    if task.attempts < task.max_attempts:
        # 公开页面偶发超时可短延迟重试；达到上限后停止，交给运营检查链接或平台限制。
        task.status = "pending"
        task.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=5 * task.attempts)
    else:
        task.status = "failed"
        task.next_run_at = None
