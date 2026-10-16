from contextlib import contextmanager
from types import SimpleNamespace

from app.agents import persistence
from app.agents.platform_graph import build_platform_workflow_graph
from app.agents.tool_gateway import ToolGateway


def test_component_imports():
    assert callable(build_platform_workflow_graph)
    assert callable(ToolGateway)


def test_checkpointer_uses_existing_config_property(monkeypatch):
    calls = []
    class Saver:
        def setup(self):
            calls.append("setup")
    @contextmanager
    def connect(url):
        calls.append(url)
        yield Saver()
    monkeypatch.setattr(persistence, "get_settings", lambda: SimpleNamespace(
        checkpoint_database_url="postgresql://test:test@localhost/test"))
    monkeypatch.setattr(persistence.PostgresSaver, "from_conn_string", connect)
    with persistence.open_postgres_checkpointer() as saver:
        assert isinstance(saver, Saver)
    assert calls == ["postgresql://test:test@localhost/test", "setup"]
