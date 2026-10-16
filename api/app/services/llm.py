"""统一文本调用出口（DesignSpec §3、§7.1 / PRD FR-04、FR-05）。

所有文本类能力共用本出口：统一做结构化输出校验、错误分类与用量提取。
错误分类：未配置 -> LLMNotConfiguredError（路由映射 400），
上游异常或响应不合规 -> LLMResponseError（路由映射 502）。

实现任务：T-02。
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.errors import MODEL_NOT_CONFIGURED, MODEL_UPSTREAM_ERROR, ModelError
from app.core.config import Settings
from app.services.model_settings import get_runtime_settings

# 这些模型的推理内容会挤占 completion 额度：长提示词下 content 可能被推理吃空而返回空串，
# 导致结构化解析失败并误触发规则回退。本出口一律只取结构化结果，故统一关闭 thinking。
THINKING_DISABLED_PREFIXES = ("deepseek-v4", "deepseek-flash")

REQUEST_TIMEOUT_SECONDS = 60
ERROR_DETAIL_MAX_LENGTH = 500


class LLMNotConfiguredError(ModelError):
    """模型未配置（映射 HTTP 400）。"""

    def __init__(self, detail: str = "LLM provider is not configured.") -> None:
        super().__init__(MODEL_NOT_CONFIGURED, detail)


class LLMResponseError(ModelError):
    """上游响应异常或结构化校验失败（映射 HTTP 502）。"""

    def __init__(self, detail: str) -> None:
        super().__init__(MODEL_UPSTREAM_ERROR, detail)


def is_llm_configured(settings: Settings | None = None) -> bool:
    """判断文本模型三要素是否齐备（PRD FR-03）。"""
    settings = settings or get_runtime_settings()
    return bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model)


def create_json_chat_completion(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 1800,
    temperature: float = 0.3,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """发起一次结构化文本调用，返回（解析后的 JSON, 原始响应）。

    实现任务：T-02。
    """
    settings = settings or get_runtime_settings()
    if not is_llm_configured(settings):
        raise LLMNotConfiguredError()

    response_json = _post_chat_completion(
        settings=settings,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = _extract_message_content(response_json)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMResponseError("LLM response was not valid JSON.") from exc

    return parsed, response_json


def _post_chat_completion(
    *,
    settings: Settings,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    """发送请求并按 HTTP 错误类型分类上抛，不回显上游正文到响应体。"""
    url = _chat_completion_url(settings.llm_base_url or "")
    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    if (settings.llm_model or "").startswith(THINKING_DISABLED_PREFIXES):
        payload["thinking"] = {"type": "disabled"}

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # 上游正文只截取摘要进入异常链（日志），路由层统一返回通用文案，不回显给调用方。
        raise LLMResponseError(
            f"LLM provider returned an error: {_safe_error_detail(exc.response)}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LLMResponseError("LLM provider request failed.") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise LLMResponseError("LLM response was not valid JSON payload.") from exc


def _chat_completion_url(base_url: str) -> str:
    """拼接补全地址；已含 /chat/completions 时不再重复追加（DesignSpec §7.1）。"""
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _extract_message_content(response_json: dict[str, Any]) -> str:
    """取出首条消息内容，并校验类型与空值。"""
    try:
        message = response_json["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMResponseError("LLM response did not contain message content.") from exc

    content = (message or {}).get("content")
    if isinstance(content, str) and content.strip():
        return content

    # 区分「推理内容吃空额度」与「真的没返回内容」，便于定位是额度问题还是供应商问题。
    if isinstance((message or {}).get("reasoning_content"), str) and message["reasoning_content"].strip():
        raise LLMResponseError(
            "LLM response returned only reasoning content; increase max_tokens or disable thinking."
        )
    raise LLMResponseError("LLM response content was empty.")


def _safe_error_detail(response: httpx.Response) -> str:
    """截取上游错误摘要，限制长度，避免过长响应写入异常链。"""
    try:
        data = response.json()
        return json.dumps(data, ensure_ascii=False)[:ERROR_DETAIL_MAX_LENGTH]
    except ValueError:
        return response.text[:ERROR_DETAIL_MAX_LENGTH]
