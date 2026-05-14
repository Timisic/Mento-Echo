# Mentor Echo MVP 实验平台

Mentor Echo 是一个用于大学生身份发展相关 AI 对话研究的 MVP 实验平台。系统采用 **React + FastAPI + PostgreSQL**，重点保障实验流程、分组锁定、问卷数据、AI 对话记录、管理员审计和研究数据导出的完整性。

## 核心功能

### 被试流程

- 使用研究者发放的匿名 **Participant Code（被试编号）** 进入实验。
- 自动恢复同一被试的未完成实验会话，避免重复提交。
- 完成版本化前测问卷后进入分组与 AI 对话。
- 支持实验组 / 控制组对话提示词。
- AI 对话完成条件由平台判定：至少 10 条被试消息 + 至少 15 分钟。
- 对话达标后进入后测问卷，提交后实验完成。

### 管理员功能

- 管理员登录。
- 导入被试编号，可选择预设分组或留空后随机分组。
- 仪表盘查看：被试编号、分组、分组来源、状态、问卷完成情况、对话轮次、对话时长、完成资格、完成状态、排除状态、恢复次数、最后访问时间。
- 重置前测问卷，必须填写审计原因。
- 标记实验会话为排除，必须填写排除原因。
- 生成研究导出 ZIP 包。

### 数据与导出

导出包由 PostgreSQL 当前数据生成，包含：

- `README.md`
- `participants.csv`
- `experiment_sessions.csv`
- `questionnaire_responses.csv`
- `questionnaire_scores.csv`
- `analysis_dataset.csv`
- `chat_messages.jsonl`
- `behavior_events.jsonl`
- `audit_logs.csv`
- `ai_call_records.csv`
- `export_manifest.json`

隐私边界：

- 平台只保存被试编号，不保存被试姓名。
- `analysis_dataset.csv` 是常规分析数据，不包含原始聊天文本。
- 原始聊天文本仅在 `chat_messages.jsonl` 中导出，并在 README / manifest 中标记为敏感数据。
- 默认不导出完整 IP 地址。
- API Key、管理员密码、管理员 Token 等敏感配置不得提交到仓库，也不会进入前端响应或导出包。

## 技术栈

- 前端：React、TypeScript、Vite、Vitest
- 后端：FastAPI、SQLAlchemy、Alembic、Pydantic Settings
- 数据库：PostgreSQL
- AI 接口：后端 OpenAI-compatible Chat Completions 边界，可通过 `.env` 配置 provider、base URL、model 和 API key

## 目录结构

```text
backend/    FastAPI 后端、数据库模型、迁移、测试
frontend/   React 前端、前端测试
docs/       PRD、规格、ADR、目标文档、pilot 检查文档
```

## 本地启动

### 1. 准备配置

复制示例配置并按本地环境填写：

```bash
cp .env.example .env
```

注意：不要把真实 API Key、管理员密码、管理员 Token 或任何被试隐私信息提交到 Git。

### 2. 启动 PostgreSQL

```bash
docker compose up -d db
```

确认数据库容器健康：

```bash
docker compose ps
```

### 3. 安装后端依赖并执行迁移

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e 'backend[dev]'

cd backend
alembic upgrade head
cd ..
```

### 4. 启动后端

```bash
source .venv/bin/activate
uvicorn app.main:app --app-dir backend --reload
```

后端默认地址：`http://localhost:8000`

### 5. 启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

前端默认地址：`http://localhost:5173`

## 常用验证命令

确保 PostgreSQL 已启动后运行：

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

## AI 模型配置说明

默认测试环境可以使用 mock provider，不会调用外部模型。需要测试真实模型时，在 `.env` 中配置：

- `AI_PROVIDER_NAME`
- `AI_BASE_URL`
- `AI_MODEL_NAME`
- `AI_API_KEY`
- `AI_TEMPERATURE`
- `AI_MAX_TOKENS`
- `AI_TIMEOUT_SECONDS`

真实模型调用可能产生外部 API 费用。请只在确认配置和成本后运行。

## 研究数据注意事项

- 被试姓名与编号映射表应由研究者在线下单独保存，不进入平台。
- 导出 ZIP 中的原始聊天文件属于敏感研究材料，应限制访问范围。
- 常规统计分析优先使用 `analysis_dataset.csv`。
- 若修改问卷、提示词、评分规则或导出字段，应同步更新对应文档、测试和版本标识。
