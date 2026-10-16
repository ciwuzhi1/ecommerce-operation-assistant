"""统一错误码体系（DesignSpec §6 错误码体系 / ADR-07）。

采用「段位划分 + HTTP 状态码共存」：HTTP 状态码保持既有语义不变，
响应体新增机器可读的 code 字段供前端与测试判定，detail 文本保留以兼容既有契约。

本模块只定义错误码常量与异常类型，不改变既有路由的返回结构。
"""
from __future__ import annotations

from typing import Final

from fastapi import HTTPException

AUTH_PREFIX: Final = "AUTH_"
BIZ_PREFIX: Final = "BIZ_"
MODEL_PREFIX: Final = "MODEL_"
MEDIA_PREFIX: Final = "MEDIA_"
JOB_PREFIX: Final = "JOB_"
AGENT_PREFIX: Final = "AGENT_"
APPR_PREFIX: Final = "APPR_"
SYS_PREFIX: Final = "SYS_"

AUTH_TOKEN_INVALID: Final = "AUTH_TOKEN_INVALID"
AUTH_PERMISSION_DENIED: Final = "AUTH_PERMISSION_DENIED"
AUTH_WORKSPACE_MISMATCH: Final = "AUTH_WORKSPACE_MISMATCH"

BIZ_INVENTORY_INSUFFICIENT: Final = "BIZ_INVENTORY_INSUFFICIENT"
BIZ_PLAN_TYPE_MISMATCH: Final = "BIZ_PLAN_TYPE_MISMATCH"
BIZ_STATE_TRANSITION_INVALID: Final = "BIZ_STATE_TRANSITION_INVALID"

MODEL_NOT_CONFIGURED: Final = "MODEL_NOT_CONFIGURED"
MODEL_RESPONSE_INVALID: Final = "MODEL_RESPONSE_INVALID"
MODEL_UPSTREAM_ERROR: Final = "MODEL_UPSTREAM_ERROR"

MEDIA_SUBMIT_FAILED: Final = "MEDIA_SUBMIT_FAILED"
MEDIA_POLL_TIMEOUT: Final = "MEDIA_POLL_TIMEOUT"
MEDIA_DOWNLOAD_FAILED: Final = "MEDIA_DOWNLOAD_FAILED"

JOB_NOT_RETRYABLE: Final = "JOB_NOT_RETRYABLE"
JOB_NOT_CANCELLABLE: Final = "JOB_NOT_CANCELLABLE"
JOB_ALREADY_RUNNING: Final = "JOB_ALREADY_RUNNING"

AGENT_TOOL_NOT_ALLOWED: Final = "AGENT_TOOL_NOT_ALLOWED"
AGENT_TOOL_NO_ADAPTER: Final = "AGENT_TOOL_NO_ADAPTER"
AGENT_LEASE_LOST: Final = "AGENT_LEASE_LOST"
AGENT_BUDGET_EXCEEDED: Final = "AGENT_BUDGET_EXCEEDED"

APPR_EXPIRED: Final = "APPR_EXPIRED"
APPR_ALREADY_DECIDED: Final = "APPR_ALREADY_DECIDED"
APPR_EDIT_OUTPUT_REQUIRED: Final = "APPR_EDIT_OUTPUT_REQUIRED"

SYS_DEPENDENCY_UNAVAILABLE: Final = "SYS_DEPENDENCY_UNAVAILABLE"

CODE_TO_HTTP_STATUS: Final[dict[str, int]] = {
    AUTH_TOKEN_INVALID: 401,
    AUTH_PERMISSION_DENIED: 403,
    AUTH_WORKSPACE_MISMATCH: 403,
    BIZ_INVENTORY_INSUFFICIENT: 400,
    BIZ_PLAN_TYPE_MISMATCH: 400,
    BIZ_STATE_TRANSITION_INVALID: 400,
    MODEL_NOT_CONFIGURED: 400,
    MODEL_RESPONSE_INVALID: 502,
    MODEL_UPSTREAM_ERROR: 502,
    MEDIA_SUBMIT_FAILED: 502,
    MEDIA_POLL_TIMEOUT: 502,
    MEDIA_DOWNLOAD_FAILED: 502,
    JOB_NOT_RETRYABLE: 400,
    JOB_NOT_CANCELLABLE: 400,
    JOB_ALREADY_RUNNING: 409,
    AGENT_TOOL_NOT_ALLOWED: 403,
    AGENT_TOOL_NO_ADAPTER: 400,
    AGENT_LEASE_LOST: 409,
    AGENT_BUDGET_EXCEEDED: 400,
    APPR_EXPIRED: 409,
    APPR_ALREADY_DECIDED: 409,
    APPR_EDIT_OUTPUT_REQUIRED: 400,
    SYS_DEPENDENCY_UNAVAILABLE: 502,
}


class ApiError(Exception):
    """带错误码的业务异常基类；路由层负责转换为 HTTP 响应并附带 code 字段。"""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

    @property
    def http_status(self) -> int:
        return CODE_TO_HTTP_STATUS.get(self.code, 400)


class AuthError(ApiError):
    """认证与鉴权类错误（AUTH_ 段位）。"""


class BizError(ApiError):
    """业务规则类错误（BIZ_ 段位）。"""


class ModelError(ApiError):
    """模型能力类错误（MODEL_ 段位）。"""


class MediaError(ApiError):
    """媒体生成类错误（MEDIA_ 段位）。"""


class JobError(ApiError):
    """任务状态机类错误（JOB_ 段位）。"""


class AgentError(ApiError):
    """智能体执行类错误（AGENT_ 段位）。"""


class ApprovalError(ApiError):
    """审批类错误（APPR_ 段位）。"""


class CodedHTTPException(HTTPException):
    """携带错误码的 HTTP 异常。

    路由层大多直接抛 HTTPException；用它承载已知错误码，
    由 main.py 的处理器统一把 code 写进响应体，HTTP 状态码语义保持不变。
    """

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code
