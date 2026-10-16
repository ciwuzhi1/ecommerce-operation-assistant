"""T-01 模型配置读写的单元测试（使用临时内存库）。"""
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, ModelProviderSetting, ModelTarget
from app.services.model_settings import read_model_settings, update_model_settings


def _session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _env_settings() -> SimpleNamespace:
    return SimpleNamespace(
        app_name="test",
        database_url="sqlite://",
        api_cors_origins="",
        llm_base_url="https://env.example.com",
        llm_api_key="env-secret",
        llm_model="env-text-model",
        image_provider=None,
        image_base_url=None,
        image_api_key=None,
        image_model=None,
        image_size="1024*1024",
        image_workspace_id=None,
        image_poll_interval_seconds=5,
        image_poll_max_attempts=24,
        video_provider=None,
        video_base_url=None,
        video_api_key=None,
        video_model=None,
        video_size="1280*720",
        video_duration=2,
        video_workspace_id=None,
        video_poll_interval_seconds=10,
        video_poll_max_attempts=36,
    )


def test_read_model_settings_uses_database_before_env() -> None:
    """给定库中已有图片配置，读取时应优先于环境变量，且文本回退环境变量。"""
    with _session() as db:
        db.add(
            ModelProviderSetting(
                target=ModelTarget.IMAGE,
                provider="jimeng",
                base_url="https://visual.volcengineapi.com",
                api_key="volc-ak:volc-sk",
                model="jimeng_t2i_v31",
                size="1328*1328",
                poll_interval_seconds=3,
                poll_max_attempts=10,
            )
        )
        db.commit()
        settings = read_model_settings(db, _env_settings())

    assert settings["image"]["provider"] == "jimeng"
    assert settings["image"]["model"] == "jimeng_t2i_v31"
    assert settings["image"]["size"] == "1328*1328"
    assert settings["image"]["has_api_key"] is True
    assert settings["text"]["model"] == "env-text-model"


def test_read_model_settings_never_returns_plaintext_key() -> None:
    """给定已配置密钥，读取结果不得包含明文（PRD FR-02）。"""
    secret = "sk-plaintext-secret-value-1234567890"
    with _session() as db:
        db.add(
            ModelProviderSetting(
                target=ModelTarget.TEXT,
                base_url="https://api.example.com",
                api_key=secret,
                model="m1",
            )
        )
        db.commit()
        settings = read_model_settings(db, _env_settings())

    assert settings["text"]["has_api_key"] is True
    assert secret not in settings["text"]["api_key_masked"]
    assert "..." in settings["text"]["api_key_masked"]


def test_short_secret_is_fully_masked() -> None:
    """给定短密钥，应整体遮蔽而不保留首尾字符。"""
    with _session() as db:
        db.add(
            ModelProviderSetting(
                target=ModelTarget.TEXT,
                base_url="https://api.example.com",
                api_key="short123",
                model="m1",
            )
        )
        db.commit()
        settings = read_model_settings(db, _env_settings())

    masked = settings["text"]["api_key_masked"]
    assert masked == "*" * 8
    assert "short" not in masked


def test_update_model_settings_keeps_existing_secret_when_blank() -> None:
    """给定空密钥提交，不应清空已保存的密钥。"""
    with _session() as db:
        db.add(
            ModelProviderSetting(
                target=ModelTarget.TEXT,
                base_url="https://old.example.com",
                api_key="old-secret",
                model="old-model",
            )
        )
        db.commit()

        update_model_settings(
            {"text": {"base_url": "https://new.example.com", "api_key": ""}},
            db,
        )
        row = db.query(ModelProviderSetting).filter_by(target=ModelTarget.TEXT).one()

    assert row.base_url == "https://new.example.com"
    assert row.api_key == "old-secret"


def test_update_model_settings_only_touches_submitted_target() -> None:
    """给定只提交文本目标，图片配置应保持不变。"""
    with _session() as db:
        db.add(
            ModelProviderSetting(
                target=ModelTarget.IMAGE, provider="jimeng", model="img-old"
            )
        )
        db.commit()

        update_model_settings({"text": {"model": "text-new"}}, db)
        image_row = db.query(ModelProviderSetting).filter_by(target=ModelTarget.IMAGE).one()

    assert image_row.model == "img-old"
