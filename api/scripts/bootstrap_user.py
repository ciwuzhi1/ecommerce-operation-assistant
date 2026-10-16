import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models import UserRole
from app.services.bootstrap import ensure_bootstrap_user


def main() -> int:
    """读取环境配置并执行命令行主流程，失败时向调用方返回明确状态。"""
    # 先处理输入与边界条件，再执行核心逻辑，最后返回稳定且可验证的结果。
    email = os.getenv("BOOTSTRAP_EMAIL", "").strip()
    display_name = os.getenv("BOOTSTRAP_DISPLAY_NAME", "Owner").strip()
    password = os.getenv("BOOTSTRAP_PASSWORD", "")
    role_value = os.getenv("BOOTSTRAP_ROLE", UserRole.OWNER.value).strip()

    if not email or not password:
        print("请设置 BOOTSTRAP_EMAIL 和 BOOTSTRAP_PASSWORD 后再初始化首个账号。")
        return 1

    try:
        role = UserRole(role_value)
    except ValueError:
        print(f"BOOTSTRAP_ROLE 只能是：{', '.join(role.value for role in UserRole)}")
        return 1

    with SessionLocal() as db:
        user, created = ensure_bootstrap_user(
            db,
            email=email,
            display_name=display_name or email,
            password=password,
            role=role,
        )

    action = "已创建" if created else "已存在"
    print(f"{action}初始化账号：{user.email}（角色：{user.role.value}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
