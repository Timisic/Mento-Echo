#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已从 .env.example 创建 .env。公网部署前请修改 ADMIN_PASSWORD、ADMIN_TOKEN 和真实模型配置。"
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [ "${AI_PROVIDER_NAME:-mock}" = "codex" ]; then
  CODEX_BIN="${CODEX_COMMAND:-codex app-server}"
  if ! bash -lc "command -v ${CODEX_BIN%% *}" >/dev/null 2>&1; then
    echo "未找到 Codex CLI：${CODEX_COMMAND:-codex app-server}。请先在服务器安装并登录 Codex CLI。" >&2
    exit 1
  fi
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -e 'backend[dev]'

docker compose up -d db
for i in $(seq 1 40); do
  db_status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' mentor-echo-postgres 2>/dev/null || true)"
  [ "$db_status" = "healthy" ] && break
  echo "等待 PostgreSQL 启动... (${db_status:-unknown})"
  sleep 2
  if [ "$i" = "40" ]; then
    echo "PostgreSQL 未在预期时间内变为 healthy" >&2
    exit 1
  fi
done

(cd backend && alembic upgrade head)
PYTHONPATH=backend python -m app.seed

(cd frontend && npm install && npm run build)

cleanup() {
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "${BACKEND_PORT:-8000}" &
BACKEND_PID=$!
(cd frontend && npm run preview -- --host 0.0.0.0 --port "${FRONTEND_PORT:-4173}") &
FRONTEND_PID=$!

cat <<INFO

Mentor Echo 最小部署已启动：
- 前端：http://0.0.0.0:${FRONTEND_PORT:-4173}
- 后端：http://0.0.0.0:${BACKEND_PORT:-8000}
- API 文档：http://0.0.0.0:${BACKEND_PORT:-8000}/docs

研究者登录信息（来自 .env）：
- 研究者账号：${ADMIN_USERNAME:-researcher}
- 研究者密码：${ADMIN_PASSWORD:-echo2026}

当前 AI Provider：${AI_PROVIDER_NAME:-mock}
当前研究模式：${STUDY_MODE:-pilot_single}

公网开放前请确认 ADMIN_PASSWORD、ADMIN_TOKEN、CORS_ORIGINS 和服务器防火墙设置。
按 Ctrl+C 停止前端和后端；数据库容器会继续运行，可用 docker compose down 停止。
INFO

wait "$BACKEND_PID" "$FRONTEND_PID"
