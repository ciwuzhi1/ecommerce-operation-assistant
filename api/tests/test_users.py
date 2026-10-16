from app.models import User, UserRole
from app.services.users import hash_password, user_permissions, verify_password


def test_user_role_permissions_keep_ad_confirmation_manual() -> None:
    """验证“用户角色permissionskeep投放confirmationmanual”场景，确保重构后仍满足预期业务与安全边界。"""
    owner = User(email="owner@example.com", display_name="Owner", role=UserRole.OWNER)
    operator = User(email="ops@example.com", display_name="Ops", role=UserRole.OPERATOR)
    viewer = User(email="viewer@example.com", display_name="Viewer", role=UserRole.VIEWER)

    assert user_permissions(owner)["can_manage_users"]
    assert user_permissions(operator)["can_confirm_ad_actions"]
    assert not user_permissions(viewer)["can_confirm_ad_actions"]
    assert not user_permissions(viewer)["can_edit"]


def test_password_hash_verification() -> None:
    """验证“password哈希verification”场景，确保重构后仍满足预期业务与安全边界。"""
    password_hash = hash_password("secret-password")

    assert verify_password("secret-password", password_hash)
    assert not verify_password("wrong-password", password_hash)
