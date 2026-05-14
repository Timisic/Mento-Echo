# Mentor Echo MVP 实验平台

Mentor Echo 是一个用于研究“AI 对话是否能促进大学生身份发展”的实验平台。它把被试编号、前测问卷、实验/控制组分配、AI 对话、后测问卷、行为事件、管理员审计和研究数据导出串成一条可恢复、可审计的实验流程。

这个项目不是通用聊天产品，也不是心理咨询系统。它的目标是帮助研究者稳定地运行一个 MVP 级别的对照实验，并生成后续统计分析和文本分析所需的数据包。

## 实验流程

```text
被试输入编号
→ 前测问卷
→ 锁定实验组 / 控制组分配
→ AI 对话干预
→ 达成 10 条被试消息 + 15 分钟
→ 后测问卷
→ 实验完成
→ 研究者导出数据
```

### 被试端

- 被试只使用匿名 **被试编号（Participant Code）** 进入实验。
- 被试不需要账号密码；编号就是入口凭证。
- 同一编号再次进入时会恢复同一个实验会话，避免重复提交。
- 前测提交后锁定，不允许被试自行修改。
- 分组一旦确定就锁定：
  - 导入时指定 `experiment` / `control` 的，直接使用导入分组；
  - 未指定分组的，在首次到达分组点时随机分组。
- AI 对话分为：
  - 实验组：围绕专业、未来学习/工作方向、价值、目标、自我理解与身份发展展开；
  - 控制组：围绕电影、音乐、饮食、旅行、校园生活等非身份主题轻松聊天。
- 完成 AI 对话必须同时满足：
  - 至少 10 条被试消息；
  - 至少 15 分钟对话时长。
- 后测只在对话完成后开放。

### 研究者管理端

- 单一研究者管理员登录。
- 导入被试编号，可选预设分组。
- 查看实验进度仪表盘，包括：
  - 被试编号；
  - 分组与分组来源；
  - 当前状态；
  - 前测/后测完成情况；
  - 对话轮次与对话时长；
  - 是否达到完成资格；
  - 是否完成实验；
  - 是否被排除；
  - 恢复次数与最后访问时间。
- 可重置前测，必须填写审计原因。
- 可将实验会话标记为排除，必须填写排除原因。
- 可导出研究数据 ZIP 包。

## 数据导出

导出包由 PostgreSQL 当前数据生成，是分析快照，不是数据库备份。ZIP 内包含：

```text
README.md
participants.csv
experiment_sessions.csv
questionnaire_responses.csv
questionnaire_scores.csv
analysis_dataset.csv
chat_messages.jsonl
behavior_events.jsonl
audit_logs.csv
ai_call_records.csv
export_manifest.json
```

### 隐私边界

- 平台只保存被试编号，不保存被试姓名。
- 姓名与编号映射表应由研究者在线下单独保存，不进入平台。
- `analysis_dataset.csv` 用于常规统计分析，不包含原始聊天文本。
- 原始聊天文本只在 `chat_messages.jsonl` 中导出，并在导出 README 和 manifest 中标记为敏感数据。
- 默认不导出完整 IP 地址。
- 前端不会拿到 AI API Key、管理员密码或管理员 Token。
- 不要把真实 API Key、管理员密码、Token、被试隐私材料提交到 Git。

## 技术栈

- 前端：React + TypeScript + Vite
- 后端：FastAPI + SQLAlchemy + Alembic + Pydantic Settings
- 数据库：PostgreSQL
- AI 调用：后端 OpenAI-compatible Chat Completions 边界，可替换 provider/model

## 快速启动

最简单方式：

```bash
./scripts/quickstart.sh
```

脚本会自动完成：

1. 如果没有 `.env`，从 `.env.example` 创建；
2. 创建/使用 `.venv` 并安装后端依赖；
3. 启动 Docker PostgreSQL；
4. 执行 Alembic 数据库迁移；
5. 初始化一个演示被试；
6. 安装前端依赖；
7. 同时启动后端和前端。

启动后访问：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`

### 默认本地演示账号

如果没有修改 `.env`，默认是：

- 研究者账号：`researcher`
- 研究者密码：`change-me-admin-password`
- 演示被试编号：`PILOT001`
- 被试密码：无；输入被试编号即可进入

> 真实实验前请务必修改默认研究者密码和 Token。

## 手动启动

### 1. 准备配置

```bash
cp .env.example .env
```

按需修改 `.env`。真实模型调用至少需要配置 provider、base URL、model 和 API key。

### 2. 启动数据库

```bash
docker compose up -d db
docker compose ps
```

### 3. 安装后端并迁移数据库

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e 'backend[dev]'

cd backend
alembic upgrade head
cd ..
```

### 4. 初始化演示被试

```bash
source .venv/bin/activate
PYTHONPATH=backend python -m app.seed
```

可通过环境变量改默认被试：

```bash
SEED_PARTICIPANT_CODE=PILOT002 SEED_ASSIGNED_GROUP=control PYTHONPATH=backend python -m app.seed
```

### 5. 启动后端

```bash
source .venv/bin/activate
uvicorn app.main:app --app-dir backend --reload
```

### 6. 启动前端

另开终端：

```bash
cd frontend
npm install
npm run dev
```

## 验证命令

PostgreSQL 启动后运行：

```bash
source .venv/bin/activate
pytest backend

cd frontend
npm test -- --run
npm run build
```

完整 pilot-readiness 检查流程见：

```text
docs/pilot-readiness-check.md
```

## AI 模型配置

默认 `.env.example` 使用 mock provider，不会调用外部模型。接入真实模型时配置：

```text
AI_PROVIDER_NAME=
AI_BASE_URL=
AI_MODEL_NAME=
AI_API_KEY=
AI_TEMPERATURE=
AI_MAX_TOKENS=
AI_TIMEOUT_SECONDS=
```

真实模型调用可能产生外部 API 费用。API Key 只应保存在本地 `.env` 或部署环境变量中。

## 目录结构

```text
backend/    FastAPI 后端、数据库模型、迁移、导出、测试
frontend/   React 前端、前端测试
docs/       PRD、规格、ADR、目标文档、pilot 检查文档
scripts/    本地开发脚本
```

## 当前 MVP 状态

已实现：

- PostgreSQL 系统事实源；
- React/FastAPI 前后端分离；
- 管理员登录与被试导入；
- 被试编号入口与恢复；
- 实验会话状态机；
- 导入/随机混合分组与分组锁定；
- 版本化前测/后测问卷；
- 问卷锁定、重置与评分；
- 实验组/控制组 AI 对话；
- 后端 AI provider 边界；
- 对话完成资格判定；
- 行为事件与审计日志；
- 管理员仪表盘；
- 会话排除；
- 研究数据 ZIP 导出；
- pilot-readiness 回归测试。
