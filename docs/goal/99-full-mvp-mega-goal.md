# Optional Goal 99: Full MVP One-Shot Mega Goal

## When to use

Use this only if you intentionally want one long Codex run to attempt the entire MVP. It reduces manual orchestration, but it is riskier than Goals 00-03 because the diff will be large, review boundaries will be weaker, and failures late in the run may be harder to recover from.

## GitHub issues

Implement all MVP issues:

- https://github.com/Timisic/Mento-Echo/issues/2
- https://github.com/Timisic/Mento-Echo/issues/3
- https://github.com/Timisic/Mento-Echo/issues/4
- https://github.com/Timisic/Mento-Echo/issues/5
- https://github.com/Timisic/Mento-Echo/issues/7
- https://github.com/Timisic/Mento-Echo/issues/8
- https://github.com/Timisic/Mento-Echo/issues/9

Do not implement questionnaire scoring until https://github.com/Timisic/Mento-Echo/issues/6 is resolved or an explicit approved questionnaire map exists.

## Target result

Deliver the complete Mentor Echo MVP: React frontend, FastAPI backend, PostgreSQL system of record, participant import/code entry/session/assignment, versioned questionnaires, AI Dialogue, completion eligibility, admin dashboard, logs/audit, export package, and pilot-readiness regression suite.

## Required reading

- `CONTEXT.md`
- `docs/prd/mvp-experiment-platform.md`
- `docs/mvp-spec.md`
- `docs/questionnaire-spec.md`
- `docs/data-export-spec.md`
- `docs/adr/`
- all GitHub issues listed above

## Execution guidance

Proceed in this order inside the single goal:

1. Scaffold and health path.
2. Participant registry/admin import/code entry.
3. Experiment Session state machine and resume.
4. Group Assignment locking.
5. Questionnaire flow and scoring only if the HITL map is resolved.
6. AI Dialogue and completion eligibility.
7. Admin dashboard/logging/audit.
8. Export package and E2E pilot regression.

## Stop condition

Stop only when the full MVP passes local verification, or when a hard blocker prevents meaningful progress. If blocked by the questionnaire HITL map, implement all non-questionnaire-dependent infrastructure and leave explicit failing/skipped tests for the blocked scoring pieces.
