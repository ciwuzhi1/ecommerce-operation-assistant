from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import get_settings


@contextmanager
def open_postgres_checkpointer() -> Generator[Any, None, None]:
    """打开postgrescheckpointer，集中管理 PostgreSQL checkpoint 的连接、释放和失败边界。"""
    settings = get_settings()
    # 每个 Celery 任务独立持有连接上下文，避免 worker fork 后复用父进程数据库连接。
    with PostgresSaver.from_conn_string(settings.checkpoint_database_url) as checkpointer:
        checkpointer.setup()
        yield checkpointer
