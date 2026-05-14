# Goal 02: Versioned Questionnaire Flow and AI Dialogue

## GitHub issues

Implement and satisfy:

- https://github.com/Timisic/Mento-Echo/issues/7
- https://github.com/Timisic/Mento-Echo/issues/8

Prerequisites:

- https://github.com/Timisic/Mento-Echo/issues/5 complete
- https://github.com/Timisic/Mento-Echo/issues/6 resolved or explicitly approved for implementation

## Target result

Complete the participant-facing experimental path from pre-survey through AI Dialogue completion and post-survey completion. This goal should produce the first full participant loop, even if the admin/export surface remains minimal.

## Read first

- `CONTEXT.md`
- `docs/prd/mvp-experiment-platform.md`
- `docs/mvp-spec.md`
- `docs/questionnaire-spec.md`
- the finalized questionnaire map from Goal 00
- `docs/adr/0004-versioned-questionnaire-configuration.md`
- GitHub Issues #7 and #8

## Scope

1. Render versioned pre-survey from structured configuration.
2. Lock pre-survey on submit.
3. Store raw responses with questionnaire version, phase, item, instrument, and dimension metadata.
4. Compute derived questionnaire scores and attention-check status from the approved scoring map.
5. After pre-survey and assignment, route participant to the correct AI Dialogue condition.
6. Implement OpenAI-compatible server-side provider boundary with configurable model/provider settings.
7. Store participant and assistant messages with provider/model/prompt/generation metadata.
8. Enforce Dialogue Completion Eligibility in backend: at least 10 participant turns and at least 15 elapsed minutes.
9. Show participant completion progress in the simple UI and disable finish until eligible.
10. Render versioned post-survey after eligible dialogue completion.
11. Lock post-survey on submit and mark Experiment Session completed.

## Constraints

- Do not expose provider API keys to the frontend.
- AI can summarize near the end but must not decide completion eligibility.
- Do not store participant names.
- Keep provider/model selection configurable, not hard-coded in business logic.

## Validation evidence

Run and report:

- Questionnaire rendering/submission/locking tests.
- Questionnaire scoring tests.
- AI provider adapter tests using mocked OpenAI-compatible responses.
- Message persistence and metadata tests.
- Dialogue eligibility tests for turn count and elapsed time.
- Integration path: participant code → pre-survey → assignment → AI Dialogue → eligibility → post-survey → completed.

## Stop condition

Stop when Issues #7-#8 acceptance criteria are satisfied and a participant can complete the full experimental flow locally with mocked or configured AI provider behavior.
