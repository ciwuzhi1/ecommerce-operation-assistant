from fastapi.testclient import TestClient

from app.main import app


def test_health_check() -> None:
    """验证“健康检查检查”场景，确保重构后仍满足预期业务与安全边界。"""
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
