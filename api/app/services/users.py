import base64
import hashlib
import hmac
import os

from app.models import User, UserRole


ROLE_PERMISSIONS = {
    UserRole.OWNER: {
        "can_read": True,
        "can_edit": True,
        "can_manage_users": True,
        "can_confirm_ad_actions": True,
    },
    UserRole.OPERATOR: {
        "can_read": True,
        "can_edit": True,
        "can_manage_users": False,
        "can_confirm_ad_actions": True,
    },
    UserRole.VIEWER: {
        "can_read": True,
        "can_edit": False,
        "can_manage_users": False,
        "can_confirm_ad_actions": False,
    },
}


def user_permissions(user: User) -> dict[str, bool]:
    # 权限从角色统一派生，避免接口之间各自维护权限布尔值导致边界漂移。
    """用户permissions；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    return ROLE_PERMISSIONS[user.role]


def user_to_read(user: User) -> dict:
    """用户to读取；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
        "permissions": user_permissions(user),
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def hash_password(password: str) -> str:
    # 使用随机盐和 PBKDF2 保存密码摘要；代码和数据库都不保存明文密码。
    """哈希password；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    """验证password；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    try:
        algorithm, salt_value, digest_value = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False

    salt = base64.b64decode(salt_value)
    expected = base64.b64decode(digest_value)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    # 常量时间比较降低摘要校验被时序侧信道观察的风险。
    return hmac.compare_digest(actual, expected)
