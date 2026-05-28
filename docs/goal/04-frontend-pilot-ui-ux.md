# Goal 04: Frontend Pilot UI/UX

Chinese reading version: `docs/goal/04-frontend-pilot-ui-ux.zh-CN.md`.

## GitHub issue

Implement and satisfy:

- https://github.com/Timisic/Mento-Echo/issues/10

Resolved prerequisite:

- https://github.com/Timisic/Mento-Echo/issues/6 — questionnaire HITL is closed. Use `mentor_echo_questionnaire_v2026_05_15_major_umics_only` as the fixed questionnaire content/scoring contract.

## Target result

Turn the current functional tracer frontend into a pilot-usable Chinese experiment UI. This goal is now **UI/UX only**: information architecture, participant flow, researcher dashboard interaction, questionnaire presentation, dialogue presentation, copy, error/loading states, and frontend tests.

Questionnaire wording, item count, item mapping, scoring rules, and version are **out of scope for this goal** except that the UI must render the backend-provided questionnaire definition correctly.

## Scope boundary

### In scope

- Role split between participant and researcher administrator.
- Participant-facing staged flow.
- Chinese guidance copy before major stages.
- Questionnaire UI controls, grouping, progress, validation, and locked-submission feedback.
- AI dialogue UI and completion-progress display. Markdown rendering.
- Researcher dashboard layout and operation confirmations.
- Sensitive export warnings.
- User-facing loading/error/success states.
- Frontend tests for key participant and admin paths.

### Out of scope

- Changing questionnaire item wording.
- Changing questionnaire item count.
- Changing U-MICS dimensions or scoring.
- Reintroducing DIDS.
- Changing questionnaire version.
- Backend autosave per item.
- Final high-fidelity visual design/polish.

## Confirmed product / UX decisions

1. **Participant-facing screens hide group/admin internals.** Participants must not see experiment/control labels, assignment source, experiment session ID, prompt mode, backend status fields, provider metadata, export controls, reset/exclusion controls, or researcher/admin internals.
2. **Participant flow is system-controlled and one-way.** Participants may refresh and resume the current stage, but they must not manually skip stages, enter post-survey early, or resubmit locked questionnaires.
3. **Questionnaire UI is grouped and readable.** Do not show one long raw list. Use neutral Chinese section titles and progress. Do not expose English instrument names to participants.
4. **Questionnaire filling does not require backend autosave per item.** Preserve answers while navigating within the frontend session; warn before refresh/navigation when there are unsaved answers; validate missing responses before submit; keep answers after submit failure; show submitted-and-locked state after success.
5. **Researcher dashboard does not show full raw chat by default.** Raw chat remains available through the sensitive export package with explicit confirmation, not inline dashboard browsing.
6. **Visual tone is trustworthy, quiet, and low-interference.** The UI should feel like a research experiment platform, not therapy, counseling, or a strongly companion-like AI product.

## Read first

- `CONTEXT.md`
- `README.md`
- `docs/prd/mvp-experiment-platform.md`
- `docs/mvp-spec.md`
- `docs/questionnaire-spec.md`
- `docs/questionnaire-implementation-map.md`
- `docs/data-export-spec.md`
- `docs/adr/0005-sensitive-raw-chat-export-boundary.md`
- GitHub Issue #10

## Available frontend skill

This repository has a project-local Codex install of the Impeccable frontend skill:

- Skill entry: `.agents/skills/impeccable/SKILL.md`
- Skill context: `.agents/context/PRODUCT.md` and `.agents/context/DESIGN.md`
- Codex asset subagent: `.codex/agents/impeccable_asset_producer.toml`

Use the skill as a UI/UX execution aid after reading this goal. Recommended Codex invocations for this goal:

```text
$impeccable layout frontend
$impeccable clarify frontend participant and researcher flows
$impeccable harden frontend UI states
$impeccable polish frontend pilot UI
$impeccable audit frontend
```

For this MVP, prefer `layout`, `clarify`, `harden`, `polish`, and `audit`. Avoid `craft`, `live`, or visual direction workflows unless the researcher explicitly wants a human-in-the-loop visual exploration step. The goal is a quiet, trustworthy research product UI, not a new brand/marketing direction.

## UI/UX requirements

### 1. Top-level role split

The first screen should present two clear roles instead of exposing all operations at once:

```text
Mentor Echo AI 对话实验平台

[我是被试，进入实验]
[我是研究者，进入管理后台]
```

Participant-facing screens must not show admin operations, assignment internals, group labels, assignment source, session ID, prompt mode, backend status fields, export controls, reset/exclusion buttons, or provider metadata.

Researcher-facing screens must require login before showing import, dashboard, reset, exclusion, export, audit/behavior summaries, or sensitive-data actions.

### 2. Participant flow

Participant UI should be a staged Chinese flow controlled by backend session state:

1. 被试编号进入；
2. 实验说明 / 欢迎指导语；
3. 前测问卷；
4. AI 对话说明；
5. AI 对话；
6. 后测问卷；
7. 完成页。

Use neutral wording such as “AI 对话”. Do not tell participants whether they are in experiment/control unless the researcher later explicitly requests that.

### 3. Stage guides

Initial experiment guide:

```text
欢迎参加本实验

本实验包含：
1. 前测问卷
2. AI 对话
3. 后测问卷

你需要使用研究者提供的被试编号进入。
平台不会收集你的姓名。

[我已了解，开始]
```

Before AI dialogue:

```text
AI 对话说明

请根据页面中的 AI 回应进行自然对话。
有效完成对话需要同时满足：

- 至少发送 6 条消息
- 对话时间至少 10 分钟

达到条件后，系统会开放“结束对话并进入后测”按钮。

[开始 AI 对话]
```

Before post-survey:

```text
你已完成 AI 对话，下面将进入后测问卷。
请根据刚才的对话体验作答。
```

### 4. Questionnaire presentation

Render the backend-provided questionnaire definition. Do not hard-code or reinterpret questionnaire content in the frontend.

Numeric scale items should use clickable scale controls, not dropdowns.

5-point example:

```text
完全没有    ○   ○   ○   ○   ○    非常严重
            1   2   3   4   5
```

7-point example:

```text
非常不同意  ○ ○ ○ ○ ○ ○ ○  非常同意
             1 2 3 4 5 6 7
```

Semantic differential example:

```text
这个 AI 更像一个工具     ○ ○ ○ ○ ○     这个 AI 更像是在和我交流
```

Categorical items should use visible option buttons/cards instead of dropdowns:

```text
您的性别

[男] [女]
```

```text
您目前在读：

[大一] [大二] [大三] [大四] [硕士研究生] [博士研究生]
```

### 5. Questionnaire grouping / pagination

Use neutral Chinese grouping based on item metadata and scale/theme. Suggested grouping:

Pre-survey:

1. 基本信息；
2. 身份困扰；
3. 专业选择相关题项；
4. 检查并提交。

Post-survey:

1. 身份困扰；
2. AI 感知能力；
3. AI 拟人感；
4. 对话体验；
5. 专业选择相关题项；
6. 检查并提交。

Show progress:

```text
前测问卷  第 2 / 4 部分
进度：██████░░░░ 40%

[上一页] [下一页]
```

Submit screen should warn:

```text
请确认所有题目已完成。提交后将锁定，不能自行修改。
[提交前测]
```

### 6. Dialogue UI

Replace tracer-style message lists with a phone-first, single-screen chat layout and visible completion progress. Participant-facing topic copy such as “talk about your major/future direction” is allowed because it is part of the study task; the promptless rule applies to model-side prompts/instructions, not to visible participant guidance. The page must prevent horizontal scrolling on mobile and desktop: no sideways drag, no clipped message bubbles, no table-like overflow in the chat surface, and long content wraps inside the viewport. The input stays reachable at the bottom of the single-screen mobile chat experience.

Visible progress copy:

```text
完成要求：
消息数：3 / 6
对话时长：04:21 / 10:00
当前状态：尚未达到完成条件
```

Before eligibility:

```text
[尚未达到完成条件，暂不能进入后测]
```

After eligibility:

```text
消息数：10 / 10
对话时长：15:02 / 15:00
当前状态：已达到完成条件

[结束对话并进入后测]
```

Copy must make clear that completion eligibility is determined by platform rules, not AI approval. Loading copy should expose only participant-friendly states such as “正在生成回复”; do not expose provider names, thread ids, prompt details, timeout internals, or fallback mechanics to participants.

### 7. Researcher dashboard UI

Researcher dashboard should include summary cards:

- 总被试数；
- 未开始；
- 前测完成；
- 对话中；
- 已完成；
- 已排除。

Operations table:

```text
被试编号 | 分组 | 来源 | 状态 | 前测 | 对话轮次 | 对话时长 | 后测 | 排除 | 最后访问 | 操作
```

Reset, exclusion, and export should use confirmation modals:

- reset requires reason;
- exclusion requires reason;
- export warns that ZIP contains sensitive raw chat `chat_messages.jsonl`.

Dashboard must not show full raw chat by default.

## Suggested component structure

No new router dependency is required; MVP can use state or hash routing.

```text
App
├── LandingPage
├── ParticipantFlow
│   ├── ParticipantEntry
│   ├── StageGuide
│   ├── QuestionnairePage
│   ├── LikertScale
│   ├── SemanticDifferentialScale
│   ├── DialoguePage
│   └── CompletionPage
└── AdminFlow
    ├── AdminLogin
    ├── AdminDashboard
    ├── ParticipantImportPanel
    ├── SessionActionModal
    └── ExportPanel
```

## Acceptance criteria

- [ ] Participant and researcher flows are visually and functionally separated.
- [ ] Participant screens hide group labels, assignment source, session ID, prompt mode, backend status fields, provider metadata, export/reset/exclusion controls, and admin internals.
- [ ] Participant flow is system-controlled: entry → guide → pre-survey → AI guide → dialogue → post-survey → completion.
- [ ] Questionnaire UI uses clickable scale controls, categorical buttons/cards, grouping/pagination, progress, required-item validation, and submit-locking feedback.
- [ ] Questionnaire UI renders backend-provided content for `mentor_echo_questionnaire_v2026_05_15_major_umics_only` without changing wording or scoring assumptions.
- [ ] AI dialogue UI shows 10-message + 15-minute completion progress and explains blocked/eligible states in Chinese.
- [ ] Dialogue provider calls are length-guarded promptless: only the neutral length/completeness guard is sent; no developer instruction, base instruction, persona, counseling style instruction, or model-side topic guidance is sent.
- [ ] Codex GPT-5.5 is preferred, but a participant-facing reply must be available within 10 seconds via Codex or fallback provider.
- [ ] Mobile chat is phone-first single-screen at 375×667 and 390×844: no horizontal scrolling, no sideways drag, message text wraps, and the input remains reachable.
- [ ] Desktop chat also has no horizontal page/chat overflow.
- [ ] Researcher dashboard supports pilot operations with summary cards, table, reset/exclusion confirmations, export confirmation, and sensitive raw-chat warning.
- [ ] Full raw chat is not displayed inline by default in the dashboard.
- [ ] Loading, error, success, blocked, and locked states use understandable Chinese copy.
- [ ] Frontend tests cover key participant and researcher UI paths.
- [ ] Existing backend regression tests still pass.

## Verification

Run and report:

- `pytest backend -q`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`
- Manual/UI smoke path for participant flow
- Manual/UI smoke path for researcher dashboard
- Privacy check that participant UI hides admin/internal fields and dashboard does not inline raw chat
- Responsive check at 375×667, 390×844, tablet, and desktop widths with no horizontal scrolling in the chat page
- Provider behavior check that model calls are promptless and Codex timeout/fallback still satisfies the 10-second participant response SLA

## Blocked by

None. Questionnaire HITL #6 is closed; this goal can focus on UI/UX execution.
