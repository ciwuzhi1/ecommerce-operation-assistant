"""模型配置读写与脱敏（DesignSpec §3 / PRD FR-01、FR-02）。

库配置（model_provider_settings 表）覆盖环境变量，支持 text/image/video 三类目标；
查询时密钥字段只返回脱敏值，绝不返回明文。

实现任务：T-01。
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models import ModelProviderSetting, ModelTarget

TARGETS: dict[str, ModelTarget] = {
    "text": ModelTarget.TEXT,
    "image": ModelTarget.IMAGE,
    "video": ModelTarget.VIDEO,
}

# 短密钥不做首尾保留，直接整体遮蔽，避免可枚举密钥泄露（DesignSpec §8 安全）。
MIN_PARTIAL_MASK_LENGTH = 13


def read_model_settings(db: Session | None = None, settings: Settings | None = None) -> dict:
    """读取生效模型配置；密钥脱敏返回（PRD FR-01、FR-02）。"""
    settings = settings or get_settings()
    rows = _read_rows(db)
    text = _effective_text(settings, rows.get(ModelTarget.TEXT))
    image = _effective_image(settings, rows.get(ModelTarget.IMAGE))
    video = _effective_video(settings, rows.get(ModelTarget.VIDEO))

    # 只返回脱敏 key 与是否已配置，避免前端或浏览器日志暴露供应商密钥。
    return {
        "text": {
            "base_url": text.llm_base_url or "",
            "api_key_masked": _mask_secret(text.llm_api_key),
            "has_api_key": bool(text.llm_api_key),
            "model": text.llm_model or "",
        },
        "image": {
            "provider": image.image_provider or "",
            "base_url": image.image_base_url or "",
            "api_key_masked": _mask_secret(image.image_api_key),
            "has_api_key": bool(image.image_api_key),
            "model": image.image_model or "",
            "size": image.image_size,
            "workspace_id": image.image_workspace_id or "",
            "poll_interval_seconds": image.image_poll_interval_seconds,
            "poll_max_attempts": image.image_poll_max_attempts,
        },
        "video": {
            "provider": video.video_provider or "",
            "base_url": video.video_base_url or "",
            "api_key_masked": _mask_secret(video.video_api_key),
            "has_api_key": bool(video.video_api_key),
            "model": video.video_model or "",
            "size": video.video_size,
            "duration": video.video_duration,
            "workspace_id": video.video_workspace_id or "",
            "poll_interval_seconds": video.video_poll_interval_seconds,
            "poll_max_attempts": video.video_poll_max_attempts,
        },
    }


def update_model_settings(payload: dict, db: Session) -> dict:
    """按目标局部更新模型配置（PRD FR-01）。"""
    for target_name, model_target in TARGETS.items():
        target_payload = payload.get(target_name) or {}
        if not target_payload:
            continue
        # 三类供应商分开保存，避免只换图片模型时影响文本生成链路。
        row = db.scalars(
            select(ModelProviderSetting).where(ModelProviderSetting.target == model_target)
        ).first()
        if row is None:
            row = ModelProviderSetting(target=model_target)
            db.add(row)
        _apply_payload(row, target_name, target_payload)

    db.commit()
    return read_model_settings(db)


def get_runtime_settings(settings: Settings | None = None) -> Any:
    """取运行期实际配置：库配置覆盖环境变量，供调用层与媒体层使用。"""
    settings = settings or get_settings()
    rows = _read_rows()
    text = _effective_text(settings, rows.get(ModelTarget.TEXT))
    image = _effective_image(settings, rows.get(ModelTarget.IMAGE))
    video = _effective_video(settings, rows.get(ModelTarget.VIDEO))

    return SimpleNamespace(
        app_name=settings.app_name,
        database_url=settings.database_url,
        api_cors_origins=settings.api_cors_origins,
        llm_base_url=text.llm_base_url,
        llm_api_key=text.llm_api_key,
        llm_model=text.llm_model,
        image_provider=image.image_provider,
        image_base_url=image.image_base_url,
        image_api_key=image.image_api_key,
        image_model=image.image_model,
        image_size=image.image_size,
        image_workspace_id=image.image_workspace_id,
        image_poll_interval_seconds=image.image_poll_interval_seconds,
        image_poll_max_attempts=image.image_poll_max_attempts,
        video_provider=video.video_provider,
        video_base_url=video.video_base_url,
        video_api_key=video.video_api_key,
        video_model=video.video_model,
        video_size=video.video_size,
        video_duration=video.video_duration,
        video_workspace_id=video.video_workspace_id,
        video_poll_interval_seconds=video.video_poll_interval_seconds,
        video_poll_max_attempts=video.video_poll_max_attempts,
    )


def _read_rows(db: Session | None = None) -> dict[ModelTarget, ModelProviderSetting]:
    """读取配置行；未迁移时回退环境变量，保证健康检查与初始化脚本可运行。"""
    if db is not None:
        return _rows_from_session(db)
    try:
        with SessionLocal() as session:
            return _rows_from_session(session)
    except SQLAlchemyError:
        return {}


def _rows_from_session(db: Session) -> dict[ModelTarget, ModelProviderSetting]:
    rows = db.scalars(select(ModelProviderSetting)).all()
    return {row.target: row for row in rows}


def _effective_text(settings: Settings, row: ModelProviderSetting | None) -> SimpleNamespace:
    return SimpleNamespace(
        llm_base_url=_row_value(row, "base_url", settings.llm_base_url),
        llm_api_key=_row_value(row, "api_key", settings.llm_api_key),
        llm_model=_row_value(row, "model", settings.llm_model),
    )


def _effective_image(settings: Settings, row: ModelProviderSetting | None) -> SimpleNamespace:
    return SimpleNamespace(
        image_provider=_row_value(row, "provider", settings.image_provider),
        image_base_url=_row_value(row, "base_url", settings.image_base_url),
        image_api_key=_row_value(row, "api_key", settings.image_api_key),
        image_model=_row_value(row, "model", settings.image_model),
        image_size=_row_value(row, "size", settings.image_size) or "1024*1024",
        image_workspace_id=_row_value(row, "workspace_id", settings.image_workspace_id),
        image_poll_interval_seconds=_row_value(
            row, "poll_interval_seconds", settings.image_poll_interval_seconds
        )
        or 5,
        image_poll_max_attempts=_row_value(
            row, "poll_max_attempts", settings.image_poll_max_attempts
        )
        or 24,
    )


def _effective_video(settings: Settings, row: ModelProviderSetting | None) -> SimpleNamespace:
    return SimpleNamespace(
        video_provider=_row_value(row, "provider", settings.video_provider),
        video_base_url=_row_value(row, "base_url", settings.video_base_url),
        video_api_key=_row_value(row, "api_key", settings.video_api_key),
        video_model=_row_value(row, "model", settings.video_model),
        video_size=_row_value(row, "size", settings.video_size) or "1280*720",
        video_duration=_row_value(row, "duration", settings.video_duration) or 2,
        video_workspace_id=_row_value(row, "workspace_id", settings.video_workspace_id),
        video_poll_interval_seconds=_row_value(
            row, "poll_interval_seconds", settings.video_poll_interval_seconds
        )
        or 10,
        video_poll_max_attempts=_row_value(
            row, "poll_max_attempts", settings.video_poll_max_attempts
        )
        or 36,
    )


def _row_value(row: ModelProviderSetting | None, field: str, fallback: Any) -> Any:
    """库值优先，空值回退环境变量。"""
    if row is None:
        return fallback
    value = getattr(row, field)
    if value is None or value == "":
        return fallback
    return value


def _apply_payload(row: ModelProviderSetting, target_name: str, payload: dict) -> None:
    if target_name == "text":
        _set_if_present(row, "base_url", payload, "base_url")
        _set_secret_if_present(row, payload)
        _set_if_present(row, "model", payload, "model")
        return

    _set_if_present(row, "provider", payload, "provider")
    _set_if_present(row, "base_url", payload, "base_url")
    _set_secret_if_present(row, payload)
    _set_if_present(row, "model", payload, "model")
    _set_if_present(row, "size", payload, "size")
    _set_if_present(row, "workspace_id", payload, "workspace_id")
    _set_if_present(row, "poll_interval_seconds", payload, "poll_interval_seconds")
    _set_if_present(row, "poll_max_attempts", payload, "poll_max_attempts")
    if target_name == "video":
        _set_if_present(row, "duration", payload, "duration")


def _set_if_present(
    row: ModelProviderSetting, field: str, payload: dict, payload_field: str
) -> None:
    if payload_field not in payload:
        return
    value = payload[payload_field]
    if isinstance(value, str):
        value = value.strip() or None
    setattr(row, field, value)


def _set_secret_if_present(row: ModelProviderSetting, payload: dict) -> None:
    if "api_key" not in payload:
        return
    value = payload["api_key"]
    if isinstance(value, str):
        value = value.strip()
    # 空字符串表示「不更新密钥」，防止保存表单时把已有供应商 key 意外清空。
    if value:
        row.api_key = value


def _mask_secret(value: str | None) -> str:
    """脱敏密钥（PRD FR-02）。

    短密钥整体遮蔽，不做首尾保留，避免可枚举的短密钥被还原。
    """
    if not value:
        return ""
    if len(value) < MIN_PARTIAL_MASK_LENGTH:
        return "*" * 8
    return f"{value[:7]}...{value[-6:]}"
