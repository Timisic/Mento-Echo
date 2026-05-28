# Mentor Echo MVP 实验平台

Mentor Echo 是一个用于研究“AI 对话是否能促进大学生身份发展”的实验平台。当前默认面向研究一预实验：被试可自助生成匿名编号，完成前测、单组 AI 对话、后测、行为事件记录、管理员审计和研究数据导出。分组能力保留给后续研究二或正式分组实验。

这个项目不是通用聊天产品，也不是心理咨询系统。它的目标是帮助研究者稳定地运行一个 MVP 级别的对照实验，并生成后续统计分析和文本分析所需的数据包。

## 实验流程

```text
被试输入或自助生成编号
→ 前测问卷
→ 研究一预实验单组 AI 对话
→ 达成 6 条被试消息 + 10 分钟
→ 后测问卷
→ 实验完成
→ 研究者导出数据
```

### 被试端

- 被试只使用匿名 **被试编号（Participant Code）** 进入实验。
- 被试可以输入研究者提供的编号，也可以让平台自动生成 `P001-7K` 这类“顺序号 + 防猜后缀”的编号。
- 被试不需要账号密码；编号就是入口凭证，必须由被试截图或记下。
- 同一编号再次进入时会恢复同一个实验会话，避免重复提交。
- 前测提交后锁定，不允许被试自行修改。
- 当前默认 `STUDY_MODE=pilot_single`：研究一预实验暂不展示、不执行实验组/控制组分配，所有被试进入同一套 AI 对话。
- 后续研究二可切换到 `STUDY_MODE=grouped`，恢复导入/随机分组；如需提示词条件，应作为新的研究协议决策重新确认。
- 当前 AI 对话为 `length_guarded_promptless_v1`：后端只发送中性的长度/完整性守卫，
  不发送话题引导、研究条件提示、角色人设或咨询风格指令。
- 完成 AI 对话必须同时满足：
  - 至少 6 条被试消息；
  - 至少 10 分钟活跃对话时长。
- 后测只在对话完成后开放。

### 研究者管理端

- 单一研究者管理员登录。
- 查看自助生成的被试编号，也可手动导入被试编号；预设分组仅在后续分组模式使用。
- 查看实验进度仪表盘，包括：
  - 被试编号；
  - 当前研究模式、分组与分组来源；
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
- AI 调用：后端 provider 边界，优先支持带长度守卫的 Codex GPT-5.5；若 30 秒内不能返回，则降级到 DeepSeek/OpenAI-compatible Chat Completions；开发/测试可用 mock

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
- 研究者密码：`echo2026`
- 演示被试编号：`PILOT001`
- 被试密码：无；输入被试编号即可进入

> 真实实验前请务必修改默认研究者密码和 Token。

## 手动启动

### 1. 准备配置

```bash
cp .env.example .env
```

按需修改 `.env`。DeepSeek 需要配置 provider、base URL、model 和 API key；Codex 需要服务器已安装并登录 Codex CLI。

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
SEED_PARTICIPANT_CODE=PILOT002 PYTHONPATH=backend python -m app.seed
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

## 云服务器最小部署

服务器已安装并登录 Codex CLI 时，可使用：

```bash
./scripts/deploy_minimal.sh
```

脚本会检查 `.env`、PostgreSQL、后端迁移、前端构建和 Codex 命令，并在启动时打印研究者后台地址、账号和当前 `.env` 中的密码。脚本不会自动安装或登录 Codex CLI。

> 如果服务器对公网开放，请在正式收数前把 `.env` 中的 `ADMIN_PASSWORD` 和 `ADMIN_TOKEN` 改成更强的值。

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

默认 `.env.example` 使用 mock provider，不会调用外部模型。真实模型可配置为 OpenAI/DeepSeek/OpenAI-compatible provider；当前公网实验部署使用 OpenAI：

```text
# 当前默认研究一预实验单组；后续研究二可改为 grouped
STUDY_MODE=pilot_single
SELF_REGISTRATION_ENABLED=true
PARTICIPANT_CODE_PREFIX=P

# mock | openai | deepseek | openai-compatible | codex
AI_PROVIDER_NAME=openai
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL_NAME=gpt-5.5
AI_API_KEY=
AI_TEMPERATURE=1
AI_MAX_TOKENS=900
AI_REASONING_EFFORT=none
AI_TIMEOUT_SECONDS=45

# AI_PROVIDER_NAME=codex 时使用；Codex CLI 需在服务器上预先安装并登录
CODEX_COMMAND=codex app-server --disable hooks
CODEX_APPROVAL_POLICY=never
CODEX_SANDBOX=read-only
CODEX_REASONING_EFFORT=low
CODEX_READ_TIMEOUT_SECONDS=5
CODEX_TURN_TIMEOUT_SECONDS=25

# Optional fallback provider. Keep disabled unless a second provider/key is intentionally configured.
AI_FALLBACK_ENABLED=false
AI_FALLBACK_PROVIDER_NAME=deepseek
AI_FALLBACK_BASE_URL=https://api.deepseek.com
AI_FALLBACK_MODEL_NAME=deepseek-v4-pro
AI_FALLBACK_API_KEY=
AI_FALLBACK_MAX_TOKENS=500
AI_FALLBACK_TIMEOUT_SECONDS=30
AI_FALLBACK_MAX_ATTEMPTS=2
```

真实模型调用可能产生外部 API 或 Codex 账号费用。API Key 只应保存在本地 `.env` 或部署环境变量中。当前 AI 对话决策是 `length_guarded_promptless_v1`：后端只允许一条中性的长度/完整性守卫，不应向模型发送话题引导、研究条件提示、角色人设或咨询风格指令。Codex 模式会把每个 Experiment Session 的 Codex thread id 存入数据库，以便浏览器刷新或后端重启后继续同一段对话。

Codex 原生提速优先路径：当前机器 `codex-cli 0.132.0` 已可用，`~/.codex/config.toml` 默认模型为 `gpt-5.5`，因此 provider 配置应优先使用 `AI_MODEL_NAME=gpt-5.5`。当前每轮直接启动 `codex app-server --disable hooks` 会有冷启动成本；更快的原生路径是使用 Codex app-server daemon + `codex app-server proxy` 复用常驻服务。实测本机 `codex app-server daemon start` 提示缺少 standalone Codex install（需要 Codex installer 管理的 `~/.codex/packages/standalone/current/codex`），所以要启用 daemon/proxy 提速，需要先安装 standalone Codex；在此之前仍应保留 30 秒 SLA 和 DeepSeek 降级。


## 公网 IPv4 安全控制

当实验平台直接用公网 IPv4 发布时，模型 provider key 只应保存在后端 `.env` / 部署环境变量中，并配置以下应用级防护：

```text
CORS_ORIGINS=http://YOUR_IPV4:5173
ALLOWED_HOSTS=YOUR_IPV4,localhost,127.0.0.1
MAX_REQUEST_BODY_BYTES=262144
RATE_LIMIT_ENABLED=true
RATE_LIMIT_GENERAL_PER_MINUTE=300
RATE_LIMIT_PARTICIPANT_PER_MINUTE=120
RATE_LIMIT_CHAT_PER_MINUTE=20
RATE_LIMIT_ADMIN_PER_MINUTE=120
RATE_LIMIT_ADMIN_LOGIN_PER_MINUTE=10
ADMIN_LOGIN_LOCKOUT_ATTEMPTS=5
ADMIN_LOGIN_LOCKOUT_SECONDS=300
TRUST_PROXY_HEADERS=false
```

这些控制会拒绝异常 `Host` 头、过大的请求体、请求突增、AI 对话额度滥用以及重复管理员登录失败，同时默认限额保留正常被试问卷/对话使用空间。若要更接近生产环境，还应在服务器防火墙/安全组中只开放确实需要的前后端端口，避免暴露 PostgreSQL 或其他后台服务；任何曾经粘贴到聊天或日志里的 key 都要轮换；有域名后尽快启用 HTTPS。

OpenAI GPT-5 系列 chat-completions 模型会拒绝旧的 `max_tokens` 参数和非默认 `temperature`。后端会自动把 `AI_MAX_TOKENS` 映射为 `max_completion_tokens`，并对 GPT-5 系列省略非默认 temperature。若使用支持该值的 GPT-5.1+ / 当前 `gpt-5.5` 类模型，建议设置 `AI_REASONING_EFFORT=none`，避免普通聊天把输出额度耗尽在不可见 reasoning tokens 上。若 provider 返回 `finish_reason=length`，后端会把该轮视为 provider error，避免把截断回复直接展示给被试。

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
- 管理员登录、被试导入与被试自助生成编号；
- 被试编号入口与恢复；
- 实验会话状态机；
- 研究一预实验单组流程，并保留导入/随机混合分组扩展位；
- 版本化前测/后测问卷；
- 问卷锁定、重置与评分；
- 研究一预实验单组 AI 对话；
- 后端 AI provider 边界；
- 对话完成资格判定；
- 行为事件与审计日志；
- 管理员仪表盘；
- 会话排除；
- 研究数据 ZIP 导出；
- pilot-readiness 回归测试。
