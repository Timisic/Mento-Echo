# Goal 00: Finalize Questionnaire HITL Map (Resolved)

## GitHub issue

- https://github.com/Timisic/Mento-Echo/issues/6

## Target result

Resolved on 2026-05-15. The current researcher-approved map is `mentor_echo_questionnaire_v2026_05_15_major_umics_only`: placeholders render as 专业选择, DIDS is removed from both phases, and U-MICS is retained.

## Read first

- `docs/questionnaire-spec.md`
- `docs/汇总问卷.md`
- `docs/source/汇总问卷.docx` if visual/source verification is needed
- `docs/prd/mvp-experiment-platform.md`
- `CONTEXT.md`

## Work to do

1. Review the converted questionnaire and source notes.
2. Identify every pre-survey and post-survey item that must be implemented.
3. Resolve or explicitly flag the repeated post-survey item text.
4. Normalize scale anchors for implementation.
5. Define stable item keys.
6. Define instrument and dimension mapping.
7. Define reverse-scoring flags if any.
8. Define attention-check items and pass criteria.
9. Confirm that participant name fields are omitted from platform storage.
10. Write the final questionnaire map to a durable doc under `docs/`.

## Stop condition

Stop when the questionnaire map is explicit enough that a separate Codex session can implement questionnaire rendering, locked submission, scoring, and export without guessing research intent.

## Validation evidence

- Updated questionnaire implementation doc exists.
- Known ambiguity list is empty or each ambiguity is explicitly marked as unresolved/HITL.
- GitHub issue #6 can be marked ready for implementation or closed as resolved by documentation.
