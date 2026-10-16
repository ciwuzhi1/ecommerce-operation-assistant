# Ecommerce Operation Assistant

面向电商运营场景的智能工作台后端与前端。围绕一件商品从资料建档、竞品监控、库存管理，到创意素材生产、投放实验与经营复盘，提供结构化的数据底座与可扩展的智能化扩展点。

当前版本完成**业务系统基线**：店铺 / 商品 / SKU / 库存流水 / 竞品 / 创意方案 / 推广链接 / 投放实验 / 经营数据 / 人工复盘全链路可用。商品诊断、创意生成、图片与视频生成、多 Agent 编排等智能能力已在接口层预留，返回 `501`，尚未开放。

---

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.12+ · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · uvicorn |
| 包管理 | uv |
| 业务数据库 | MySQL 8.4（驱动 `pymysql`） |
| 队列 / 缓存 | Redis 7 · Celery |
| 编排（规划中） | LangGraph · PostgreSQL checkpoint |
| 前端 | Next.js 16.3.1 · React 19.2.4 · TypeScript 5 · Tailwind CSS 4 |
| 部署 | Docker Compose |

---

## 架构

```
┌──────────────────────────────────────────────────────┐
│ web/  Next.js 工作台 + BFF 代理路由                    │
├──────────────────────────────────────────────────────┤
│ api/app/api/routes/    HTTP 入口：鉴权、租户、参数校验   │
│ api/app/services/      业务逻辑：库存、导入、统计、解析   │
│ api/app/models.py      ORM 模型（36 张业务表）          │
│ api/app/db/            会话与 Base                      │
│ api/app/core/          配置中心（Pydantic Settings）     │
├──────────────────────────────────────────────────────┤
│ MySQL（业务数据）  Redis（队列）  PostgreSQL（规划中）    │
└──────────────────────────────────────────────────────┘
```

**三条约定**

1. 页面不直连数据库，前端只经后端 HTTP 接口；
2. 路由不堆积复杂业务，业务处理集中在 `services/`；
3. 密钥只从环境变量读取，不写入代码。

**数据一致性要点**：库存不允许直接覆盖，所有变化必须写入 `inventory_movements` 流水（记录变更前后数量），超量出库被拒绝且不改变库存。

---

## 目录结构

```
.
├── api/
│   ├── app/
│   │   ├── api/routes/     # auth · products · stores · promotion_links · users · workspace · health
│   │   ├── core/config.py  # 配置中心
│   │   ├── db/             # Base 与会话
│   │   ├── services/       # 业务服务
│   │   ├── main.py         # 应用入口
│   │   ├── models.py       # ORM 模型
│   │   └── schemas.py      # 请求/响应模型
│   ├── alembic/            # 数据库迁移
│   ├── scripts/            # 初始化脚本
│   ├── tests/              # Pytest 测试
│   ├── pyproject.toml
│   └── .env.example
├── web/                    # Next.js 工作台
├── docker-compose.yml      # MySQL · Redis · PostgreSQL
└── .env.example
```

---

## 快速开始

### 1. 环境要求

- Python 3.12+、[uv](https://docs.astral.sh/uv/)
- Node.js 20+、npm
- Docker（用于 MySQL / Redis）

### 2. 启动基础服务

```bash
cp .env.example .env          # 填入随机密码
docker compose up -d mysql redis agent-checkpoints
```

### 3. 后端

```bash
cd api
cp .env.example .env          # 填写 DATABASE_URL / REDIS_URL
uv sync --extra dev
uv run alembic upgrade head   # 建表

# 初始化首个管理员（密码只经环境变量传入）
BOOTSTRAP_EMAIL=owner@example.com \
BOOTSTRAP_DISPLAY_NAME=Owner \
BOOTSTRAP_PASSWORD='<你的密码>' \
uv run python scripts/bootstrap_user.py

uv run uvicorn app.main:app --reload --port 8000
```

- 接口文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>

### 4. 前端

```bash
cd web
cp .env.example .env.local    # NEXT_PUBLIC_API_BASE_URL 指向后端
npm ci
npm run dev
```

打开 <http://127.0.0.1:3000>，使用第 3 步创建的管理员账号登录。

---

## 接口概览

所有业务接口挂在 `/api/v1` 下，认证使用 Bearer Token（Swagger 中点击 **Authorize** 填入即可）。

| 模块 | 代表接口 |
|---|---|
| 认证 | `POST /api/v1/auth/login`、`GET /api/v1/auth/me` |
| 店铺 | `POST /api/v1/stores`、`GET /api/v1/stores/{id}/inventory-summary` |
| 商品 | `POST /api/v1/products`、`GET/PATCH /api/v1/products/{id}` |
| SKU 与库存 | `POST /api/v1/products/{id}/skus`、`POST .../skus/{sku_id}/inventory-movements` |
| 竞品 | `POST /api/v1/products/{id}/competitors`、`.../competitor-monitors/{id}/run` |
| 创意方案 | `POST /api/v1/products/{id}/creative-plans` |
| 推广与投放 | `POST /api/v1/products/{id}/promotion-links`、`.../ad-experiments` |
| 经营数据 | `POST /api/v1/products/{id}/performance-records`、`.../ad-experiments/dashboard` |
| 复盘 | `POST /api/v1/products/{id}/review-reports` |
| 工作区 | 表格模板下载与产品 / SKU 库存 / 经营数据导入 |

完整的接口签名、请求体与响应结构以 `/docs` 为准。

---

## 测试

```bash
cd api
uv run python -m pytest -q
```

测试使用临时内存 SQLite 与 HTTP 替身，**不连接本地 MySQL、不调用外部服务**。

前端类型检查：

```bash
cd web
npx tsc --noEmit
```

---

## 当前状态

| 能力 | 状态 |
|---|---|
| 店铺 / 商品 / SKU / 库存流水 | ✅ 可用 |
| 竞品档案 / 公开链接解析任务 / 监控快照 | ✅ 可用 |
| 创意方案手工维护 / 素材记录同步 | ✅ 可用 |
| 推广链接与短链 / 投放实验 / 经营数据 / 复盘 | ✅ 可用 |
| 表格导入（预览 + 提交） | ✅ 可用 |
| 商品诊断 / 创意生成 / 库存建议 | 🚧 接口已预留，返回 501 |
| 图片 / 视频生成 | 🚧 接口已预留，返回 501 |
| 多 Agent 编排与人工审批 | 🚧 规划中 |

---

## 安全说明

- 密码使用 PBKDF2 摘要存储，登录令牌由服务端 HMAC 签名，不依赖第三方 JWT 库。
- `.env`、`.env.local`、上传素材与数据库数据**不进入版本控制**。
- 生产环境（`APP_ENV=production`）启动时会校验关键密钥强度，弱密钥直接拒绝启动。
