# =============================================================================
# 电商运营助手 · 后端镜像（API 与 Worker 共用同一份构建产物）
# 依据：DesignSpec §2「技术栈与依赖」、§4「部署拓扑」；实现任务 T-39。
#
# 构建约定
#   1. 基础镜像与 uv 二进制默认走国内可拉取的镜像源，可用 --build-arg 覆盖；
#   2. 依赖用 uv.lock 锁定安装（--locked），镜像可复现；
#   3. 密钥一律运行时经环境变量注入（由 docker-compose 从根目录 .env 映射），
#      本文件不写入任何密钥，也不 COPY 任何 .env（见 .dockerignore）；
#   4. API 与 Worker 使用同一镜像，靠 compose 覆盖 command 区分角色，
#      避免两份依赖树产生漂移。
# =============================================================================

# 全局构建参数：仅在 FROM 指令中生效；要进入构建阶段需在阶段内再次 ARG 声明。
ARG PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.12-slim
ARG UV_IMAGE=docker.m.daocloud.io/astral-sh/uv:0.12.8

# 取 uv / uvx 可执行文件的中转层：最终镜像不含该基础镜像的任何内容。
FROM ${UV_IMAGE} AS uv-bin

FROM ${PYTHON_IMAGE}

# 中国大陆网络环境默认使用清华 PyPI 镜像；海外或私有源用 --build-arg 覆盖。
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_DEFAULT_INDEX=${PIP_INDEX_URL} \
    UV_HTTP_TIMEOUT=120 \
    PATH=/opt/venv/bin:$PATH

COPY --from=uv-bin /uv /uvx /bin/

WORKDIR /app

# 先装依赖再拷代码：只要 pyproject.toml / uv.lock 不变，依赖层就一直命中缓存。
# --no-dev 不装 pytest / ruff；--no-install-project 只装第三方依赖，不装本仓库自身。
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --python /usr/local/bin/python --no-cache

# 再拷贝应用代码。alembic/、alembic.ini、scripts/ 都在这里，供 API 启动迁移使用。
COPY . .

# 以非 root 身份运行。uploads 目录会被命名卷 api-uploads 挂载，
# 必须先把目录属主交给运行用户，否则空卷初始化时会继承 root 属主导致素材写不进去
# （app/main.py 启动时会往该目录 mkdir，图片/视频生成服务也会写入）。
RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app/uploads

USER appuser

EXPOSE 8000

# 默认以 API 身份启动；Worker 由 docker-compose 覆盖 command 启动 Celery。
# 生产环境的迁移入口在 compose 的 api.command：alembic upgrade head && uvicorn ...
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
