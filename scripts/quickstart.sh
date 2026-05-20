#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已从 .env.example 创建 .env。生产/真实实验前请修改默认密码和密钥。"
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -e 'backend[dev]'

set -a
# shellcheck disable=SC1091
source .env
set +a

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

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi

cleanup() {
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

source .venv/bin/activate
uvicorn app.main:app --app-dir backend --reload &
BACKEND_PID=$!
(cd frontend && npm run dev) &
FRONTEND_PID=$!

cat <<INFO

Mentor Echo 已启动：
- 前端：http://localhost:5173
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

默认本地演示账号（若 .env 未改动）：
- 研究者账号：${ADMIN_USERNAME:-researcher}
- 研究者密码：${ADMIN_PASSWORD:-echo2026}
- 被试编号：PILOT001
- 被试密码：无需密码，输入编号即可进入

按 Ctrl+C 同时停止前端和后端；数据库容器会继续运行，可用 docker compose down 停止。
INFO

wait "$BACKEND_PID" "$FRONTEND_PID"
