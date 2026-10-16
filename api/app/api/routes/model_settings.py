"""模型配置路由（DesignSpec §6 API-01、API-02 / PRD FR-01～FR-03）。

实现任务：T-08、T-10、T-11。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.routes.auth import require_edit_permission
from app.core.errors import (
    MEDIA_SUBMIT_FAILED,
    MODEL_NOT_CONFIGURED,
    MODEL_UPSTREAM_ERROR,
    CodedHTTPException,
)
from app.db.session import get_db
from app.models import User
from app.schemas import (
    ModelSettingsRead,
    ModelSettingsTestRequest,
    ModelSettingsTestResult,
    ModelSettingsUpdate,
)
from app.services.image_generation import (
    ImageGenerationError,
    ImageGenerationNotConfiguredError,
    check_image_generation_connectivity,
)
from app.services.llm import (
    LLMNotConfiguredError,
    LLMResponseError,
    create_json_chat_completion,
)
from app.services.model_settings import (
    get_runtime_settings,
    read_model_settings,
    update_model_settings,
)
from app.services.video_generation import (
    VideoGenerationError,
    VideoGenerationNotConfiguredError,
    check_video_generation_connectivity,
)

router = APIRouter(prefix="/model-settings", tags=["model-settings"])
SessionDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=ModelSettingsRead)
def get_model_settings(
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> dict:
    """读取模型配置，密钥脱敏返回（API-01 / PRD FR-01、FR-02）。"""
    return read_model_settings(db)


@router.patch("", response_model=ModelSettingsRead)
def patch_model_settings(
    payload: ModelSettingsUpdate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> dict:
    """保存模型配置，未提交的目标保持原值（API-01 / PRD FR-01）。"""
    return update_model_settings(payload.model_dump(exclude_unset=True), db)


@router.post("/test", response_model=ModelSettingsTestResult)
def test_model_settings(
    payload: ModelSettingsTestRequest,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> dict:
    """连通性测试：只验证供应商可达，不生成业务素材、不写库（API-02 / PRD FR-03）。"""
    if payload.target == "text":
        return _test_text_model()
    if payload.target == "image":
        return _test_media_model("image", check_image_generation_connectivity)
    return _test_media_model("video", check_video_generation_connectivity)


def _test_text_model() -> dict:
    """文本模型连通性测试（PRD FR-03）。"""
    settings = get_runtime_settings()
    try:
        response, raw = create_json_chat_completion(
            [
                {
                    "role": "system",
                    "content": "你是一个接口连通性测试助手，只返回 JSON。",
                },
                {
                    "role": "user",
                    "content": '返回 {"ok": true, "message": "ready"}',
                },
            ],
            max_tokens=80,
            temperature=0,
            settings=settings,
        )
    except LLMNotConfiguredError as exc:
        raise CodedHTTPException(
            status.HTTP_400_BAD_REQUEST, str(exc), code=MODEL_NOT_CONFIGURED
        ) from exc
    except LLMResponseError as exc:
        # 只返回通用文案，不回显上游响应正文（DesignSpec §8 安全）。
        raise CodedHTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "模型服务不可达或返回异常，请检查配置。",
            code=MODEL_UPSTREAM_ERROR,
        ) from exc

    model = raw.get("model") or settings.llm_model or ""
    return {
        "target": "text",
        "ok": bool(response.get("ok", True)),
        "message": f"Text model is reachable. model={model}",
    }


def _test_media_model(target: str, probe: Callable[[], str]) -> dict:
    """图片 / 视频供应商连通性测试（PRD FR-16、FR-17 的配置前置校验）。"""
    try:
        message = probe()
    except (ImageGenerationNotConfiguredError, VideoGenerationNotConfiguredError) as exc:
        raise CodedHTTPException(
            status.HTTP_400_BAD_REQUEST, str(exc), code=MEDIA_SUBMIT_FAILED
        ) from exc
    except (ImageGenerationError, VideoGenerationError) as exc:
        # 只返回通用文案，不回显供应商响应正文（DesignSpec §8 安全）。
        raise CodedHTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "媒体服务不可达或返回异常，请检查配置。",
            code=MEDIA_SUBMIT_FAILED,
        ) from exc

    return {"target": target, "ok": True, "message": message}
