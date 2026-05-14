# Goal 04: Frontend Pilot UX and Questionnaire HITL Sign-off

## GitHub issues

Implement and satisfy:

- https://github.com/Timisic/Mento-Echo/issues/10

Reopened prerequisite / gate:

- https://github.com/Timisic/Mento-Echo/issues/6

## Target result

Turn the current functional tracer frontend into a pilot-usable Chinese experiment UI, while keeping questionnaire content/scoring finalization gated by researcher HITL sign-off.

Frontend style and interaction improvements may proceed before questionnaire sign-off. Questionnaire wording, item count, item mapping, scoring rules, and questionnaire version must not be silently changed until Issue #6 is explicitly confirmed or corrected.

## Why this goal exists

The backend MVP now has the core experimental lifecycle, data model, audit/event logging, export package, and local startup path. The frontend, however, is still mostly a single-page operational tracer that exposes backend fields and buttons. That is useful for development but not enough for real participants or a researcher-facing pilot.

Also, Issue #6 was explicitly a human-in-the-loop questionnaire confirmation task. Automated checks and an implementation map exist, but if the researcher has not actually completed review, #6 must remain open and block final questionnaire confidence.

## Read first

- `CONTEXT.md`
- `README.md`
- `docs/prd/mvp-experiment-platform.md`
- `docs/mvp-spec.md`
- `docs/questionnaire-spec.md`
- `docs/questionnaire-implementation-map.md`
- `docs/data-export-spec.md`
- `docs/adr/0005-sensitive-raw-chat-export-boundary.md`
- GitHub Issue #6
- GitHub Issue #10

## UX direction to confirm and implement

### 1. Top-level role split

The first screen should not expose all operations at once. It should present two clear roles:

```text
Mentor Echo AI 对话实验平台

[我是被试，进入实验]
[我是研究者，进入管理后台]
```

Participant-facing screens must not show admin operations, assignment internals, export controls, reset/exclusion buttons, or technical provider metadata.

Researcher-facing screens must require login before showing import, dashboard, reset, exclusion, export, audit/behavior summaries, or sensitive-data actions.

### 2. Participant flow

Participant UI should be a staged Chinese flow:

1. 被试编号进入；
2. 实验说明 / 欢迎指导语；
3. 前测问卷；
4. AI 对话说明；
5. AI 对话；
6. 后测问卷；
7. 完成页。

The participant should not need to know whether they are in `experiment` or `control` unless the researcher explicitly wants that displayed. Use neutral wording such as “AI 对话”.

### 3. Instruction modals / stage guides

Add lightweight guidance before major stages.

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

- 至少发送 10 条消息
- 对话时间至少 15 分钟

达到条件后，系统会开放“结束对话并进入后测”按钮。

[开始 AI 对话]
```

Before post-survey:

```text
你已完成 AI 对话，下面将进入后测问卷。
请根据刚才的对话体验作答。
```

### 4. Questionnaire UI

Do not use dropdowns for numeric scale items. Use clickable scale controls.

5-point Likert / severity item example:

```text
我会因为未来发展方向不清楚而感到困扰。

完全没有    ○   ○   ○   ○   ○    非常严重
            1   2   3   4   5
```

Selected state should be visually obvious:

```text
完全没有    ○   ○   ●   ○   ○    非常严重
            1   2   3   4   5
```

7-point agreement item example:

```text
非常不同意  ○ ○ ○ ○ ○ ○ ○  非常同意
             1 2 3 4 5 6 7
```

Semantic differential item example:

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

Avoid rendering dozens of items as one long plain list. Use grouped or paginated sections with progress.

Suggested pre-survey sections:

1. 基本信息；
2. 身份困扰；
3. U-MICS；
4. DIDS；
5. 检查并提交。

Suggested post-survey sections:

1. 身份困扰；
2. AI 感知能力；
3. AI 拟人感；
4. 对话体验 / BPNSFS；
5. U-MICS；
6. DIDS；
7. 检查并提交。

Section UI should show progress:

```text
前测问卷  第 2 / 5 部分
进度：██████░░░░ 40%

[上一页] [下一页]
```

Submit screen should warn:

```text
请确认所有题目已完成。提交后将锁定，不能自行修改。
[提交前测]
```

### 6. Dialogue UI

Replace the tracer-style message list with a chat-like layout.

Required visible progress:

```text
完成要求：
消息数：3 / 10
对话时长：04:21 / 15:00
当前状态：尚未达到完成条件
```

Message area:

```text
AI：你好，我们可以从你最近在思考的问题开始。
你：我最近在想要不要继续现在的专业。
AI：……

[输入你的回复……                         ][发送]
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

The AI may summarize, but UI copy must make clear that completion is determined by the platform rule, not AI approval.

### 7. Researcher dashboard UI

Researcher dashboard should be more than a raw table.

Top summary cards:

```text
总被试数：20
未开始：5
前测完成：8
对话中：4
已完成：3
已排除：0
```

Operational table:

```text
被试编号 | 分组 | 来源 | 状态 | 前测 | 对话轮次 | 对话时长 | 后测 | 排除 | 最后访问 | 操作
```

Operations should use dialogs, not inline blind actions.

Reset dialog:

```text
请输入重置原因
[文本框]
[确认重置]
```

Exclusion dialog:

```text
请输入排除原因
[文本框]
[确认排除]
```

Export dialog:

```text
导出包包含敏感原始聊天记录 chat_messages.jsonl。
请确认仅用于研究分析并妥善保存。

[取消] [确认导出]
```

### 8. Suggested component structure

Avoid adding a router dependency unless it materially helps. State-driven views or hash routing are acceptable for MVP.

Suggested structure:

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

Keep reusable UI small and local unless a clear abstraction emerges.

## Scope

1. Run a questionnaire HITL checklist for `docs/questionnaire-implementation-map.md`.
2. Capture researcher sign-off or requested corrections for all known questionnaire source issues:
   - repeated post-survey identity-distress item;
   - identity-distress scale anchor conflict;
   - BPNSFS duplicate item text;
   - age mention without source item;
   - U-MICS/DIDS bracketed domain phrase;
   - scoring dimensions and attention-check rules;
   - participant-code-only privacy rule.
3. If the researcher requests questionnaire changes, implement them as a new questionnaire version and update tests/export expectations.
4. Split frontend into participant and researcher flows instead of a single tracer page.
5. Implement participant stage guidance and modals as described above.
6. Replace numeric questionnaire dropdowns with clickable scale controls.
7. Replace categorical questionnaire dropdowns with visible option buttons/cards.
8. Group or paginate questionnaires with progress and submit confirmation.
9. Implement chat-like dialogue UI with visible 10-turn + 15-minute progress.
10. Implement researcher dashboard summary cards, operational table, action dialogs, and export sensitive-data warning.
11. Ensure all error/loading/success/blocked messages are Chinese and user-facing.
12. Add or update frontend tests for key participant and researcher paths.
13. Keep backend regression coverage green after any questionnaire or API changes.

## Constraints

- Do not collect participant names.
- Do not add participant passwords unless the researcher explicitly changes the privacy model; current entry is participant-code-only.
- Do not expose AI API keys, admin token, or provider secrets to the frontend.
- Do not put raw chat in `analysis_dataset.csv`.
- Keep PostgreSQL as the source of truth.
- If questionnaire wording/scoring changes, create a new questionnaire version instead of silently mutating the existing version.
- Frontend UI/UX implementation can proceed before #6 sign-off, but questionnaire content/scoring/version changes cannot.

## Validation evidence

Run and report:

- Questionnaire HITL checklist and sign-off/correction record for Issue #6.
- Backend regression: `pytest backend -q`.
- Frontend tests: `cd frontend && npm test -- --run`.
- Frontend build: `cd frontend && npm run build`.
- Smoke path using the UI: researcher login/import → participant entry → pre-survey → dialogue → eligibility → post-survey → dashboard → export.
- Privacy checks: no participant names, no frontend API keys/secrets, no full IP export by default, raw chat absent from `analysis_dataset.csv`.

## Stop condition

Stop only when Issue #10 acceptance criteria are satisfied and Issue #6 is either explicitly signed off by the researcher or has documented requested changes implemented in a new questionnaire version.
