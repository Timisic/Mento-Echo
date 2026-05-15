# Codex Goal Execution Plan

Use these files as ready-to-run prompts for future Codex sessions. Each goal points to GitHub Issues and the source docs it must respect.

Recommended order:

1. `00-questionnaire-hitl.md` — human/research confirmation, can run in parallel with Goal 1.
2. `01-foundation-registry-session-assignment.md` — platform scaffold, admin import, participant entry, session state, assignment.
3. `02-questionnaire-and-ai-dialogue.md` — versioned questionnaire flow plus AI dialogue/completion, after Goal 0 and Goal 1.
4. `03-admin-export-pilot-readiness.md` — dashboard, logs, exports, E2E pilot readiness, after Goal 2.
5. `04-frontend-pilot-ui-ux.md` — pilot-ready Chinese frontend UI/UX after Goal 3. Chinese reading version: `04-frontend-pilot-ui-ux.zh-CN.md`.

Optional:

- `99-full-mvp-mega-goal.md` — one-shot full MVP prompt. This reduces human orchestration but has higher risk of oversized diffs, weaker review boundaries, and harder recovery.

## Shared source docs

Every goal should begin by reading:

- `CONTEXT.md`
- `docs/prd/mvp-experiment-platform.md`
- `docs/mvp-spec.md`
- `docs/questionnaire-spec.md`
- `docs/data-export-spec.md`
- `docs/adr/`

## GitHub issue map

- Parent PRD: https://github.com/Timisic/Mento-Echo/issues/1
- Scaffold: https://github.com/Timisic/Mento-Echo/issues/2
- Participant registry/import/code entry: https://github.com/Timisic/Mento-Echo/issues/3
- Experiment Session state machine: https://github.com/Timisic/Mento-Echo/issues/4
- Group assignment: https://github.com/Timisic/Mento-Echo/issues/5
- Questionnaire HITL map: https://github.com/Timisic/Mento-Echo/issues/6
- Questionnaire flow/scoring: https://github.com/Timisic/Mento-Echo/issues/7
- AI Dialogue/completion: https://github.com/Timisic/Mento-Echo/issues/8
- Admin/logging/export/pilot: https://github.com/Timisic/Mento-Echo/issues/9
- Frontend pilot UI/UX: https://github.com/Timisic/Mento-Echo/issues/10
