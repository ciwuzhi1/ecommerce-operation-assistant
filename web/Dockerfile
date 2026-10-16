FROM node:22-slim AS deps

WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:22-slim AS builder

WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-slim AS prod-deps

WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev

FROM node:22-slim AS runner

ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
WORKDIR /app

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./
COPY --from=prod-deps /app/node_modules ./node_modules

EXPOSE 3000

CMD ["npm", "run", "start"]
