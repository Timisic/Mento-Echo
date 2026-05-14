# Goal 03: Admin Operations, Export Package, and Pilot Readiness

## GitHub issue

Implement and satisfy:

- https://github.com/Timisic/Mento-Echo/issues/9

Prerequisite:

- https://github.com/Timisic/Mento-Echo/issues/8 complete

## Target result

Make the MVP pilot-ready for researchers: admin dashboard, reset/exclusion controls, behavior events, audit logs, export ZIP, analysis dataset, sensitive raw chat boundary, and end-to-end regression evidence.

## Read first

- `CONTEXT.md`
- `docs/prd/mvp-experiment-platform.md`
- `docs/mvp-spec.md`
- `docs/data-export-spec.md`
- `docs/adr/0005-sensitive-raw-chat-export-boundary.md`
- GitHub Issue #9

## Scope

1. Admin dashboard shows Participant Code, group, assignment source, status, survey completion, turn count, elapsed dialogue minutes, eligibility, completion, exclusion, resume/last-seen metadata.
2. Admin can reset stages with required audit reason.
3. Admin can mark sessions excluded with exclusion reason.
4. Behavior Events cover required participant/technical lifecycle events.
5. Audit Logs cover required admin actions.
6. Export Package ZIP is generated from PostgreSQL.
7. Export ZIP includes README, participants, sessions, raw questionnaire responses, questionnaire scores, `analysis_dataset.csv`, raw chat JSONL, behavior events, audit logs, AI call records, and manifest.
8. `analysis_dataset.csv` has one row per participant and excludes raw chat text.
9. Raw chat export is clearly marked as sensitive.
10. End-to-end pilot regression covers full study flow and export.

## Constraints

- PostgreSQL remains the source of truth; exports are generated snapshots.
- Routine analysis data must not contain raw chat text.
- No participant names.
- No full IP address export by default.

## Validation evidence

Run and report:

- Admin dashboard/API tests.
- Reset/exclusion audit tests.
- Behavior Event tests.
- Export package structure/content tests.
- Privacy boundary tests: no names, no frontend API keys, no full IP export, raw chat absent from `analysis_dataset.csv`.
- End-to-end test: import → entry → pre-survey → assignment → chat → eligibility → post-survey → dashboard → export.

## Stop condition

Stop when Issue #9 acceptance criteria are satisfied and the repository has a documented command sequence for a local pilot-readiness check.
