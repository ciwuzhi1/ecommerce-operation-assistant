from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import make_url

API_DIR = Path(__file__).resolve().parents[2]



def _is_placeholder_or_weak(value: str,*,min_length: int) -> bool:
    normalized = value.strip().lower()
    return len(value) < min_length or normalized.startswith("replace_with_") or normalized in {"agent","password"}


class Settings(BaseSettings):

    app_name: str = "Ecommerce Operation Assistant API"
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(..., alias="DATABASE_URL")
    api_cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000", alias="API_CORS_ORIGINS")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", alias="REDIS_URL")
    task_queue_backend: str = Field(default="inline", alias="TASK_QUEUE_BACKEND")
    celery_task_default_queue: str = Field(default="generation", alias="CELERY_TASK_DEFAULT_QUEUE")
    celery_agent_queue: str = Field(default="agent", alias="CELERY_AGENT_QUEUE")
    celery_agent_workflow_queue: str = Field(default="agent.workflow", alias="CELERY_AGENT_WORKFLOW_QUEUE")
    celery_maintenance_queue: str = Field(default="maintenance", alias="CELERY_MAINTENANCE_QUEUE")
    agent_checkpoint_database_url: str | None = Field(default=None, alias="AGENT_CHECKPOINT_DATABASE_URL")
    agent_checkpoint_host: str = Field(default="127.0.0.1", alias="AGENT_CHECKPOINT_HOST")
    agent_checkpoint_port: int = Field(default=5433, alias="AGENT_CHECKPOINT_PORT")
    agent_checkpoint_user: str = Field(default="agent", alias="AGENT_CHECKPOINT_USER")
    agent_checkpoint_password: str = Field(default="agent", alias="AGENT_CHECKPOINT_PASSWORD")
    agent_checkpoint_database: str = Field(default="agent_checkpoints", alias="AGENT_CHECKPOINT_DATABASE")
    agent_max_total_tokens: int = Field(default=12000, alias="AGENT_MAX_TOTAL_TOKENS")
    agent_max_revisions: int = Field(default=1, alias="AGENT_MAX_REVISIONS")
    otel_service_name: str = Field(default="ecommerce-operation-agent", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    auth_secret_key: str = Field(default="dev-auth-secret-change-me", alias="AUTH_SECRET_KEY")
    auth_token_expire_minutes: int = Field(default=60 * 24 * 7, alias="AUTH_TOKEN_EXPIRE_MINUTES")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    image_provider: str | None = Field(default=None, alias="IMAGE_PROVIDER")
    image_base_url: str | None = Field(default=None, alias="IMAGE_BASE_URL")
    image_api_key: str | None = Field(default=None, alias="IMAGE_API_KEY")
    image_model: str | None = Field(default=None, alias="IMAGE_MODEL")
    image_size: str = Field(default="1024*1024", alias="IMAGE_SIZE")
    image_workspace_id: str | None = Field(default=None, alias="IMAGE_WORKSPACE_ID")
    image_poll_interval_seconds: int = Field(default=5, alias="IMAGE_POLL_INTERVAL_SECONDS")
    image_poll_max_attempts: int = Field(default=24, alias="IMAGE_POLL_MAX_ATTEMPTS")
    video_provider: str | None = Field(default=None, alias="VIDEO_PROVIDER")
    video_base_url: str | None = Field(default=None, alias="VIDEO_BASE_URL")
    video_api_key: str | None = Field(default=None, alias="VIDEO_API_KEY")
    video_model: str | None = Field(default=None, alias="VIDEO_MODEL")
    video_size: str = Field(default="1280*720", alias="VIDEO_SIZE")
    video_duration: int = Field(default=2, alias="VIDEO_DURATION")
    video_workspace_id: str | None = Field(default=None, alias="VIDEO_WORKSPACE_ID")
    video_poll_interval_seconds: int = Field(default=10, alias="VIDEO_POLL_INTERVAL_SECONDS")
    video_poll_max_attempts: int = Field(default=36, alias="VIDEO_POLL_MAX_ATTEMPTS")

    #核心方法是读取本地的.env文件覆盖当前对象中的变量值 
    # 推荐写成绝对路径的形式 指定固定的.env文件
    model_config = SettingsConfigDict(env_file=API_DIR / ".env",env_file_encoding="utf-8",extra="ignore")

    #特殊参数处理
    #1. 处理跨域来源 => 把一个长字符串拆分为多个来源
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.api_cors_origins.split(",") if origin.strip()]

    #2. 检查点数据库地址
    @property
    def checkpoint_database_url(self) -> str:
        if self.agent_checkpoint_database_url:
            return self.agent_checkpoint_database_url
        return f"postgresql://{self.agent_checkpoint_user}:{self.agent_checkpoint_password}@{self.agent_checkpoint_host}:{self.agent_checkpoint_port}/{self.agent_checkpoint_database}"

    #后置参数校验
    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        #1. 循环复查次数
        if self.agent_max_revisions < 0 or self.agent_max_revisions > 3:
            raise ValueError("AGENT_MAX_REVISIONS must be between 0 and 3")

        #2. agent的最大token数
        if self.agent_max_total_tokens < 1000:
            raise ValueError("AGENT_MAX_TOTAL_TOKENS must be at least 1000")

        #3. 生产环境下必须设置安全等级够高的密钥
        if self.app_env.lower() in {"production", "prod"}:
            # 保证令牌密码的安全等级
            if _is_placeholder_or_weak(self.auth_secret_key, min_length=32):
                raise ValueError("AUTH_SECRET_KEY must be set to a strong value in production")
            # 获取配置文件的检查点账号密码
            checkpoint_password = self.agent_checkpoint_password
            if self.checkpoint_database_url:
                try:
                    checkpoint_password = make_url(self.checkpoint_database_url).password or ""
                except Exception as exc:
                    raise ValueError(f"Invalid AGENT_CHECKPOINT_DATABASE_URL: {exc}") from exc
            if _is_placeholder_or_weak(checkpoint_password, min_length=16):
                raise ValueError("AGENT_CHECKPOINT_PASSWORD must be set to a strong value in production")
        return self


# 单例创建Settings  只有在第一次调用的时候会执行 后续的调用会直接使用第一次执行的结果
@lru_cache
def get_settings() -> Settings:
    # print("hello")
    return Settings()


