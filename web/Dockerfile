# =============================================================================
# 电商运营助手 · 前端工作台镜像（Next.js 生产构建）
# 依据：DesignSpec §2「技术栈与依赖」、§4「部署拓扑」；实现任务 T-39。
#
# 构建约定
#   1. 基础镜像默认走国内可拉取的镜像源，npm 走 npmmirror，均可用 --build-arg 覆盖；
#   2. 四阶段构建：deps → builder → prod-deps → runner，
#      运行层只保留「构建产物 + 生产依赖」，不含源码与开发依赖；
#   3. NEXT_PUBLIC_* 会被内联进浏览器包，必须在构建期确定，不能用运行时环境变量改；
#      BFF（服务端）访问后端则用运行时的 API_INTERNAL_BASE_URL，指向 http://api:8000；
#   4. .env / .env.local 一律不进镜像（见 .dockerignore），工作台不持有长期密钥。
# =============================================================================

ARG NODE_IMAGE=docker.m.daocloud.io/library/node:22-slim
ARG NPM_REGISTRY=https://registry.npmmirror.com

# ---------------------------------------------------------------------------
# 1) 依赖层：只复制清单文件，源码变更不会让 npm ci 缓存失效
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS deps

ARG NPM_REGISTRY
# replace-registry-host=always：把 package-lock.json 里的 registry.npmjs.org
# 地址整体改写到国内镜像，否则 npm ci 仍会回源到官方仓库。
RUN npm config set registry ${NPM_REGISTRY} \
    && npm config set replace-registry-host always

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---------------------------------------------------------------------------
# 2) 构建层：产出 .next 生产构建产物
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS builder

# 浏览器侧要访问的后端地址，构建期烘焙进客户端包。
ARG NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
# 3) 生产依赖层：只装 dependencies，剔除 devDependencies
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS prod-deps

ARG NPM_REGISTRY
RUN npm config set registry ${NPM_REGISTRY} \
    && npm config set replace-registry-host always

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# ---------------------------------------------------------------------------
# 4) 运行层：最小化产物，以非 root 的 node 用户运行
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

WORKDIR /app

# .next 需要可写：Next.js 的图片优化等运行期缓存落在 .next/cache 下。
COPY --from=builder --chown=node:node /app/.next ./.next
COPY --from=builder --chown=node:node /app/public ./public
COPY --from=prod-deps --chown=node:node /app/node_modules ./node_modules
COPY --chown=node:node package.json ./

USER node

EXPOSE 3000

# next start 默认监听 0.0.0.0:3000，容器内可直接被 compose 网络访问。
CMD ["npm", "run", "start"]
