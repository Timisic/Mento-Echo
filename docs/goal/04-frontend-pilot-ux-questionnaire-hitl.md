# Goal 04: Frontend Pilot UX and Questionnaire HITL Sign-off

## GitHub issues

Implement and satisfy:

- https://github.com/Timisic/Mento-Echo/issues/10

Reopened prerequisite / gate:

- https://github.com/Timisic/Mento-Echo/issues/6

## Target result

Turn the current functional tracer frontend into a pilot-usable Chinese experiment UI, and do not treat the questionnaire as final until the researcher explicitly signs off the HITL questionnaire implementation map or records requested changes.

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
4. Split or clearly structure frontend into participant and researcher flows instead of a single tracer page.
5. Participant UI should provide clear Chinese stage guidance:
   - code entry;
   - pre-survey instructions and progress;
   - assignment/dialogue instructions;
   - dialogue progress and finish rule;
   - post-survey;
   - completion.
6. Questionnaire UI should be pilot-readable:
   - grouped or paginated items;
   - progress visible;
   - required responses clear;
   - locked/completed states clear;
   - Chinese labels and messages.
7. Dialogue UI should clearly explain and show the 10 participant turns + 15 minutes rule.
8. Researcher UI should be usable for pilot operations:
   - login;
   - import participants;
   - progress dashboard;
   - reset with reason;
   - exclusion with reason;
   - export ZIP;
   - sensitive raw chat warning.
9. Error/loading/success/blocked messages should be Chinese and user-facing.
10. Add or update frontend tests for key participant and researcher paths.
11. Keep backend regression coverage green after any questionnaire or API changes.

## Constraints

- Do not collect participant names.
- Do not add participant passwords unless the researcher explicitly changes the privacy model; current entry is participant-code-only.
- Do not expose AI API keys, admin token, or provider secrets to the frontend.
- Do not put raw chat in `analysis_dataset.csv`.
- Keep PostgreSQL as the source of truth.
- If questionnaire wording/scoring changes, create a new questionnaire version instead of silently mutating the existing version.

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
