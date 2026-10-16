from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """返回服务健康状态，供容器编排和部署探针判断 API 是否可用。"""
    return {"status": "ok"}
