import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import Settings, get_settings
from app.models import User, UserStatus


class AuthTokenError(ValueError):
    pass


def create_access_token(user: User, settings: Settings | None = None) -> str:
    """创建访问Token；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    settings = settings or get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.auth_token_expire_minutes)
    # Token 只放用户身份、角色和过期时间，避免把可变权限明细或敏感配置写进客户端可见载荷。
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "exp": int(expires_at.timestamp()),
    }
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(encoded_payload, settings.auth_secret_key)
    return f"{encoded_payload}.{signature}"


def parse_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """解析访问Token；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    settings = settings or get_settings()
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthTokenError("Token format is invalid") from exc

    # 先校验签名再解析载荷，避免未受信任的客户端内容影响后续鉴权分支。
    expected_signature = _sign(encoded_payload, settings.auth_secret_key)
    if not hmac.compare_digest(signature, expected_signature):
        raise AuthTokenError("Token signature is invalid")

    try:
        payload = json.loads(_base64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthTokenError("Token payload is invalid") from exc

    expires_at = int(payload.get("exp", 0))
    if expires_at < int(datetime.now(UTC).timestamp()):
        raise AuthTokenError("Token has expired")
    return payload


def ensure_user_can_login(user: User | None) -> User:
    # 登录态每次都回表校验用户状态，便于后台停用账号后立即阻断继续操作。
    """确保用户can登录；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if user is None:
        raise AuthTokenError("User not found")
    if user.status != UserStatus.ACTIVE:
        raise AuthTokenError("User is disabled")
    return user


def _sign(encoded_payload: str, secret_key: str) -> str:
    # 这里不用第三方 JWT 库，是为了保持原型依赖轻量；签名结构保留清晰边界，后续可平滑替换为标准 JWT。
    """签名，统一主流程中的格式、默认值和异常边界。"""
    digest = hmac.new(secret_key.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    return _base64url_encode(digest)


def _base64url_encode(value: bytes) -> str:
    """Base64URLencode，统一主流程中的格式、默认值和异常边界。"""
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    """Base64URLdecode，统一主流程中的格式、默认值和异常边界。"""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
