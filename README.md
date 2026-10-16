# Ecommerce Operation Assistant

面向电商运营场景的智能工作台。围绕一件商品从资料建档、竞品监控、库存管理，到创意素材生产、投放实验与经营复盘，提供结构化的数据底座，并在其上叠加**受控的模型能力与多智能体编排**。

业务链路上，商品诊断、创意方案、库存建议、投放建议、经营复盘均可由模型生成，模型不可用时自动降级为确定性规则结果并标注来源；智能体域提供 9 个平台角色、16 项注册工具与 7 条工作流，写入类操作（改成正式对象、调整库存）必须先经人工审批。

---

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.12+ · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · uvicorn |
| 包管理 | uv |
| 业务数据库 | MySQL 8.4（驱动 `pymysql`），37 张表 |
| 队列 / 缓存 | Redis 7 · Celery（4 队列 + Beat） |
| 智能体编排 | LangGraph · PostgreSQL checkpoint（断点状态持久化） |
| 文本模型 | OpenAI 兼容协议，httpx 直连，结构化 JSON 输出 |
| 图片 / 视频生成 | 火山引擎即梦，自研 HMAC-SHA256 签名 |
| 前端 | Next.js 16.3.1 · React 19.2.4 · TypeScript 5 · Tailwind CSS 4 |
| 部署 | Docker Compose |

---

## 架构

**模块化单体 + 独立 Worker 进程 + 前后端分离**。三个业务域共享同一份领域模型，靠模块边界而非服务拆分隔离；耗时操作（模型调用、媒体生成、智能体运行）交给独立 Worker，用队列隔离换伸缩能力。

```
┌─────────────────────────────────────────────────────────────┐
│  web/  Next.js 工作台 + BFF 代理路由                          │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP
┌───────────────────────────▼─────────────────────────────────┐
│  api/  FastAPI 单进程多模块                                   │
│  ├ 业务域      店铺 / 商品 / SKU / 库存 / 竞品 / 推广 / 经营   │
│  ├ 模型能力域  配置读取 · 统一调用 · 结构化生成 · 媒体生成      │
│  └ 智能体域    合同 · 注册表 · 工具网关 · 编排图 · 审批 · 运行  │
└──────┬────────────────────┬──────────────────┬──────────────┘
       │                    │                  │
   MySQL(业务)        Redis(队列)      PostgreSQL(断点状态)
       ▲                    │                  ▲
       └────────────────────┴──────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  worker/  Celery                                             │
│  generation · agent · agent.workflow · maintenance + Beat    │
└─────────────────────────────────────────────────────────────┘
```

**四条设计约束**

1. 页面不直连数据库，前端只经后端 HTTP 接口；
2. 路由不堆积业务，业务规则集中在 `services/`；
3. **模型输出是不可信输入**：模型不得直接调用业务服务，必须经工具网关，网关按「角色白名单 → 风险等级 → 工作区归属」三段校验，并按风险决定放行或挂起审批；
4. 密钥只从环境变量读取，不写入代码，也不落进镜像。

**数据一致性要点**

- 库存不允许直接覆盖，所有变化必须写入 `inventory_movements` 流水（记录变更前后数量），超量出库被拒绝且不改变库存；
- 智能体的幂等由数据库唯一约束保证（同一运行内同一操作只落一次），不用分布式锁；
- 任务与投递事件同事务写入（Outbox），保证「有任务必有投递」。

---

## 智能体平台

| 维度 | 规模 |
|---|---|
| 平台角色 | 9 个（1 个协调者 + 8 个专业角色） |
| 注册工具 | 16 项，**全部具备执行适配** |
| 工作流 | 7 条 |
| 风险分级 | R0 只读 · R1 生成草稿 · R2 写入正式对象 · R3 库存调整（仅所有者） |

- **编排图**：基础图为 7 节点固定图（上下文 → 诊断 → 创意策略 → 质量复核 → 条件路由 → 返修或人工 → 终结，返修上限 1 次）；平台图按工作流动态串联角色，并按风险等级动态插入审批闸门。
- **审批**：决策三态 `approve` / `edit_and_approve` / `reject`，「修改后通过」必须提交完整结果并会重跑质量复核；审批记录有效期 24 小时，超期自动失效并联动取消运行。
- **记忆**：同作用域同键的新记忆覆盖旧记忆（旧记录置为已撤销、保留审计痕迹），不让两条互相矛盾的事实并存。
- **可靠性**：运行认领需持有权属凭证并定期心跳续期（防止脑裂写入）；`acks_late` + 执行者丢失重投；软超时 1700s / 硬超时 1800s 双阈值，另有维护任务兜底回收。

---

## 目录结构

```
.
├── api/
│   ├── app/
│   │   ├── api/routes/     # auth · products · stores · workspace · promotion_links · users · health
│   │   │                   # model_settings · agent_platform · agent_runs
│   │   ├── agents/         # 智能体域：合同 · 注册表 · 策略 · 工具网关 · 两张编排图 · 断点持久化
│   │   ├── core/           # 配置中心 · 统一错误码
│   │   ├── db/             # Base 与会话
│   │   ├── services/       # 业务服务 + 模型能力域 + 智能体运行/投递/维护
│   │   ├── worker/         # Celery 应用 · 薄任务 · 生成任务调度
│   │   ├── evals/          # 评测用例
│   │   ├── main.py         # 应用入口（含统一异常处理）
│   │   ├── models.py       # ORM 模型（37 张表）
│   │   └── schemas.py      # 请求/响应模型
│   ├── alembic/            # 数据库迁移
│   ├── scripts/            # 初始化脚本
│   ├── tests/              # Pytest 测试（154 项）
│   ├── pyproject.toml
│   └── .env.example
├── web/                    # Next.js 工作台
├── infra/compose.yaml      # 开发环境基础服务（Redis · PostgreSQL）
├── docker-compose.yml      # 一体化交付编排（application + 中间件）
├── docs/                   # 交付与故障排查
└── .env.example
```

---

## 快速开始

### 1. 环境要求

- Python 3.12+、[uv](https://docs.astral.sh/uv/)
- Node.js 20+、npm
- Docker（用于 Redis / PostgreSQL；MySQL 可用本机实例）

### 2. 基础服务

开发环境只起中间件，应用直接跑在宿主机：

```bash
docker compose -f infra/compose.yaml up -d     # Redis :6379 · PostgreSQL :5433
```

若 MySQL 用容器，可一并启动仓库根的编排：

```bash
cp .env.example .env          # 填入随机密码
docker compose up -d mysql redis agent-checkpoints
```

### 3. 后端

```bash
cd api
cp .env.example .env          # 填写 DATABASE_URL / REDIS_URL / AGENT_CHECKPOINT_* / LLM_*
uv sync --extra dev
uv run alembic upgrade head   # 建表

# 初始化首个管理员
uv run python -c "
from app.db.session import SessionLocal
from app.services.bootstrap import ensure_bootstrap_user
with SessionLocal() as db:
    user, _ = ensure_bootstrap_user(db, email='owner@example.com',
                                    display_name='运营负责人', password='<你的密码>')
    db.commit()
"

uv run uvicorn app.main:app --reload --port 8000
```

- 接口文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>

### 4. Celery Worker

异步能力（素材生成、智能体运行、投递派发）需要一个 Worker 进程：

```bash
cd api
uv run celery -A app.worker.celery_app:celery_app worker \
  -Q generation,agent,agent.workflow,maintenance -B -l info
```

Windows 下加 `--pool=solo`。

### 5. 前端

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
| 认证 | `POST /auth/login`、`GET /auth/me` |
| 店铺 | `POST /stores`、`GET /stores/{id}/inventory-summary` |
| 商品 | `POST /products`、`GET/PATCH /products/{id}` |
| SKU 与库存 | `POST /products/{id}/skus`、`POST .../skus/{sku_id}/inventory-movements` |
| 竞品 | `POST /products/{id}/competitors`、`.../competitor-monitors/{id}/run` |
| 创意方案 | `POST /products/{id}/creative-plans` |
| 推广与投放 | `POST /products/{id}/promotion-links`、`.../ad-experiments` |
| 经营数据与复盘 | `POST /products/{id}/performance-records`、`.../review-reports` |
| **模型配置** | `GET/PATCH /model-settings`、`POST /model-settings/test`（text / image / video） |
| **模型能力** | `POST /products/{id}/diagnoses/generate`、`.../creative-plans/main-images/generate`、`.../video-scripts/generate`、`.../ad-recommendations/generate`、`.../ad-experiments/generate`、`POST /stores/{id}/inventory-advice` |
| **生成任务** | `GET /products/{id}/generation-jobs/{jobId}`、`POST .../cancel`、`.../retry` |
| **智能体** | `POST /workspaces/{wid}/agent/tasks`、`GET .../agent/tasks/{id}`、`GET .../agent/catalog` |
| **审批与记忆** | `POST .../agent/approvals/{aid}/decision`、`GET/POST .../agent/memories`、`POST .../memories/{mid}/revoke` |
| **运行** | `GET /agent-runs/{runId}`、`POST /agent-runs/{runId}/review` |

### 错误码

HTTP 状态码语义保持不变，响应体额外带一个机器可读的 `code` 字段（[ADR-07](DesignSpec-智能化迭代.md)）：

```json
{ "detail": "模型服务不可达或返回异常，请检查配置。", "code": "MODEL_UPSTREAM_ERROR" }
```

段位：`AUTH_` · `BIZ_` · `MODEL_` · `MEDIA_` · `JOB_` · `AGENT_` · `APPR_` · `SYS_`。

完整的接口签名、请求体与响应结构以 `/docs` 为准。

---

## 测试

```bash
cd api
uv run python -m pytest -q          # 154 passed
```

测试刻意使用**临时内存 SQLite + HTTP 替身**，保证用例互相隔离、不依赖外部服务，也不读取本地 `.env` 里的真实密钥。

前端：

```bash
cd web
npx tsc --noEmit                    # 类型检查
npm run build                       # 生产构建
```

**连真实库的验收**另做：遍历 OpenAPI 全量路由打真实 MySQL，再跑关键写入链路（诊断 / 库存建议 / 投放建议 / 复盘）与审批、记忆语义。内存 SQLite 掩盖不了的问题（保留字、列类型、字符集）由这一层兜住。

---

## 当前状态

| 能力 | 状态 |
|---|---|
| 店铺 / 商品 / SKU / 库存流水 | ✅ 可用 |
| 竞品档案 / 公开链接解析 / 监控快照 | ✅ 可用 |
| 创意方案 / 推广链接 / 投放实验 / 经营数据 / 复盘 | ✅ 可用 |
| 表格导入（预览 + 提交） | ✅ 可用 |
| 模型配置与连通性测试（text / image / video） | ✅ 可用 |
| 商品诊断 / 创意方案 / 库存建议 / 投放建议 / 复盘生成 | ✅ 可用（模型优先，失败降级规则并标注来源） |
| 图片 / 视频素材生成（即梦） | ✅ 可用（需配置供应商密钥） |
| 生成任务状态机（重试 / 取消 / 超时回收） | ✅ 可用 |
| 多智能体编排 · 工具网关 · 人工审批 · 断点恢复 | ✅ 可用 |
| 会话与结构化记忆 | ✅ 可用 |
| 容器化交付编排 | 📦 文件已就位，未做端到端验证 |

---

## 安全说明

- 密码使用 PBKDF2 摘要存储，登录令牌由服务端 HMAC 签名，不依赖第三方 JWT 库。
- 模型密钥只回传布尔「已配置」标记与首尾片段掩码，**从不回读原值**；上游错误只进日志，响应体只给分类码，不回显上游正文。
- 落库快照统一走脱敏函数（按键名正则遮蔽敏感字段，并对深度、条数、字符串长度设上限）。
- 智能体写入类操作（R2 / R3）在**审批通过前不触碰业务数据**；R3 库存调整只允许所有者审批，且必须走库存流水。
- `.env`、`.env.local`、上传素材与数据库数据**不进入版本控制**。
- 生产环境（`APP_ENV=production`）启动时会校验关键密钥强度，弱密钥直接拒绝启动。
