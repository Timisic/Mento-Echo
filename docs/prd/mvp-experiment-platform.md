# PRD: Mentor Echo MVP Experiment Platform

## Problem Statement

The research team needs a stable MVP platform to run Study One Pilot, a single-group AI dialogue pre-experiment about university students' identity formation. The current requirements exist across research notes, Word questionnaires, converted Markdown, and planning decisions, but there is not yet a working system that can reliably connect participant codes, pre-survey responses, locked study mode or future group assignment, AI dialogue, post-survey responses, behavior logs, audit logs, and analysis-ready exports.

From the researcher's perspective, the main risk is not UI polish; it is losing experimental control or data integrity. The platform must prevent duplicate or inconsistent participant sessions, keep group assignment stable after refresh or re-entry, enforce dialogue completion rules, preserve enough AI provider metadata for reproducibility, and export both raw and derived data in a form suitable for statistical analysis and later text coding.

## Solution

Build a backend-stable, UI-simple MVP with a React frontend, FastAPI backend, and PostgreSQL system of record. Participants enter with researcher-issued or platform-generated participant codes, complete a versioned pre-survey, complete a single-group Study One Pilot AI dialogue through a configurable provider boundary, complete a versioned post-survey, and are then marked as completed. Future grouped studies can re-enable imported or first-entry randomized group assignment.

A single researcher administrator account can import participant codes, monitor per-participant status and key metrics, reset locked stages with an audit reason, exclude sessions, and export a ZIP package containing structured raw and derived research data. The export package includes an analysis-ready wide CSV with one row per participant and clearly separates sensitive raw chat text from routine statistical data.

## User Stories

1. As a participant, I want the platform to generate a simple anonymous participant code for me, so that I can enter the pre-experiment without a researcher manually issuing a code.
2. As a researcher administrator, I want imports to reject duplicate participant codes, so that one code cannot accidentally create conflicting experiment sessions.
3. As a researcher administrator, I want to optionally include a pre-assigned group during import, so that pilot or controlled assignment workflows are supported.
4. As a researcher administrator, I want participants without imported groups to be randomized by the platform, so that formal experiments can use system assignment.
5. As a researcher administrator, I want the assignment source recorded as imported or randomized, so that later analysis can account for how each participant was assigned.
6. As a researcher administrator, I want group assignment to lock after it is determined, so that refresh or re-entry does not change the participant's condition.
7. As a researcher administrator, I want the platform to store participant codes but not names, so that identity exposure is minimized.
8. As a researcher administrator, I want to keep any name-to-code mapping outside the platform, so that experimental data remains pseudonymous inside the system.
9. As a participant, I want to enter or resume the experiment using my participant code, so that the platform can connect my pre-survey, dialogue, and post-survey.
10. As a participant, I want an understandable error if my code is not recognized, so that I know I need to contact the researcher without exposing internal details.
11. As a participant, I want to resume the same experiment session after refresh or network interruption, so that I do not lose progress.
12. As a participant, I want the platform to remember my assigned condition after re-entry, so that I do not get reassigned.
13. As a participant, I want to complete the pre-survey before the dialogue, so that my baseline measures are captured before intervention.
14. As a researcher administrator, I want pre-survey submissions to be locked, so that baseline data cannot be edited after the experiment stage changes.
15. As a researcher administrator, I want questionnaire definitions to be versioned, so that responses and scores can always be interpreted against the correct instrument version.
16. As a researcher administrator, I want the MVP questionnaire to be configuration-driven rather than admin-editable, so that wording and scoring changes are deliberate and traceable.
17. As a researcher administrator, I want the source questionnaire's name fields omitted from platform storage, so that the platform follows the participant-code-only privacy rule.
18. As a participant in the experiment group, I want the AI dialogue to focus on my current major, future study or work direction, values, goals, and self-understanding, so that the conversation matches the identity formation intervention.
19. As a participant in the control group, I want the AI dialogue to stay on light identity-unrelated topics, so that the control condition controls for AI interaction without intentionally triggering identity reflection.
20. As a researcher administrator, I want the experiment group and control group prompts to be versioned, so that future analysis can identify which prompt condition was used.
21. As a participant, I want the instructions to clearly state that the dialogue requires at least 10 participant messages and at least 15 minutes, so that I understand the completion requirement.
22. As a participant, I want the finish-dialogue action disabled until both completion thresholds are met, so that I cannot accidentally submit an invalid dialogue.
23. As a researcher administrator, I want the completion rule enforced by the platform rather than by the AI, so that eligibility is deterministic and auditable.
24. As a researcher administrator, I want the AI to be allowed to summarize near the end without deciding completion, so that the research intervention stays controlled.
25. As a participant, I want to proceed to the post-survey only after the dialogue is complete, so that the post-survey reflects the dialogue experience.
26. As a researcher administrator, I want post-survey submissions to be locked, so that final responses remain stable after completion.
27. As a researcher administrator, I want a dashboard showing each participant's group, assignment source, current status, turn count, elapsed dialogue time, and survey completion, so that I can monitor the study while it runs.
28. As a researcher administrator, I want statuses that distinguish not started, pre-survey submitted, chat in progress, chat eligible to finish, chat completed, completed, reset required, and excluded, so that operational decisions are clear.
29. As a researcher administrator, I do not need separate persistent pre-survey-in-progress or post-survey-in-progress states, so that the status machine remains simple.
30. As a researcher administrator, I want to reset a participant's locked stage only with an audit reason, so that corrections are traceable.
31. As a researcher administrator, I want to mark a participant as excluded, so that invalid sessions can be separated from analysis without deleting raw records.
32. As a researcher administrator, I want participant resume events recorded, so that unusual interruptions can be considered during data review.
33. As a researcher administrator, I want key behavior events recorded, so that I can reconstruct what happened in each experiment session.
34. As a researcher administrator, I want AI call failures, retries, latency, provider name, model name, prompt mode, and fallback source recorded, so that technical issues can be diagnosed.
35. As a researcher administrator, I do not want high-granularity keystroke or focus analytics in the MVP, so that logging remains privacy-conscious and implementation stays focused.
36. As a researcher administrator, I want Codex GPT-5.5 preferred for AI dialogue when it can respond within 10 seconds, with DeepSeek/OpenAI-compatible fallback when it cannot, so that participant experience stays responsive without giving up Codex when it is viable.
37. As a developer, I want model name, provider endpoint configuration, generation parameters, provider thread id when applicable, prompt mode, latency, and fallback metadata stored with AI messages or the experiment session, so that model behavior is reproducible without storing hidden prompt versions.
38. As a developer, I want API keys to remain server-side, so that participants and browsers never receive provider secrets.
39. As a researcher administrator, I want a ZIP export generated from PostgreSQL, so that the export is a reproducible snapshot of the system of record.
40. As a researcher administrator, I want `participants.csv`, `experiment_sessions.csv`, `questionnaire_responses.csv`, `questionnaire_scores.csv`, `chat_messages.jsonl`, `behavior_events.jsonl`, `audit_logs.csv`, `ai_call_records.csv`, and an export manifest, so that raw and operational data are available for review.
41. As a researcher administrator, I want an `analysis_dataset.csv` with one row per participant, so that statistical analysis can start without manually joining many raw files.
42. As a researcher administrator, I want the analysis dataset to include participant code, group, status, completion timestamps, validity flags, questionnaire scores, and change scores, so that primary analyses are convenient.
43. As a researcher administrator, I want raw chat exported separately and clearly marked as sensitive, so that routine statistical workflows do not unnecessarily spread dialogue text.
44. As a researcher administrator, I want raw item responses and derived questionnaire scores stored separately, so that scoring rules can be audited and recomputed if necessary.
45. As a researcher administrator, I want attention-check results exported, so that invalid responses can be screened.
46. As a researcher administrator, I want the export README to include questionnaire version, prompt mode, AI model configuration, fallback behavior, completion rules, and privacy warnings, so that analysis files remain interpretable later.
47. As a developer, I want PostgreSQL to be the only system of record, so that generated exports do not become competing primary data stores.
48. As a developer, I want the experiment lifecycle to be represented as a clear state machine, so that invalid transitions are rejected consistently.
49. As a developer, I want group assignment, questionnaire scoring, dialogue eligibility, AI provider calls, and export building to be deep modules with stable interfaces, so that they can be tested in isolation.
50. As a developer, I want external behavior tests around the full participant flow, so that implementation refactors do not break the research protocol.
51. As a developer, I want admin actions recorded separately from participant behavior events, so that operational accountability is clear.
52. As a researcher administrator, I want the UI to be simple but usable, so that the MVP can run the experiment before visual design is upgraded.
53. As a participant, I want clear stage transitions and instructions, so that I know what to do without researcher intervention.
54. As a researcher administrator, I want completed participants prevented from submitting duplicates, so that the analysis dataset remains one row per participant code.
55. As a researcher administrator, I want source questionnaire inconsistencies flagged before implementation, so that duplicated or mislabeled items do not silently become production data.
56. As a researcher administrator, I want control-group identity-topic drift preserved in raw chat, so that later manipulation checks and sensitivity analyses can identify it.
57. As a researcher administrator, I want exported exclusion status and exclusion reasons, so that statistical analyses can reproduce inclusion decisions.
58. As a researcher administrator, I want export actions audited, so that sensitive raw chat access is traceable.

## Implementation Decisions

- Build the MVP as a separated React frontend, FastAPI backend, and PostgreSQL database. The UI can remain simple initially while the backend domain logic stays stable for later UI upgrades.
- Treat PostgreSQL as the single source of truth. CSV, JSONL, Excel, and ZIP artifacts are generated exports, not primary storage.
- Use the project glossary terms consistently: Participant, Participant Code, Experiment Session, Group Assignment, AI Dialogue, Behavior Event, Audit Log, Export Package, Analysis Dataset, and Raw Chat Export.
- Use one researcher administrator account for MVP. Do not build multi-role permissions yet.
- Use participant-code-only identity inside the platform. Do not store participant names, even if source questionnaires include name fields.
- Model the participant lifecycle as an Experiment Session with a deterministic status machine:

  | Status | Meaning |
  |---|---|
  | `not_started` | Participant code exists but no experiment activity has started. |
  | `pre_survey_submitted` | Pre-survey is locked; group assignment should be present before chat starts. |
  | `chat_in_progress` | AI dialogue has started but completion thresholds are not yet met. |
  | `chat_eligible_to_finish` | Dialogue has at least 10 participant turns and at least 15 elapsed minutes. |
  | `chat_completed` | Participant ended the eligible dialogue and can proceed to post-survey. |
  | `completed` | Post-survey submitted; full experimental loop complete. |
  | `reset_required` | Administrator or system flagged the session for intervention. |
  | `excluded` | Session is excluded from analysis by administrator decision. |

- Build a Participant Registry module that handles participant import, code normalization, duplicate detection, imported group assignment, and import audit records.
- Build an Experiment Session module that owns entry, resume, current stage, status transitions, completion checks, duplicate prevention, and reset/exclusion handling.
- Build a Study Mode / Group Assignment module that defaults to `pilot_single` for Study One Pilot, records `assignment_source = pilot_single`, and can later support imported assignment and first-entry randomized assignment for grouped studies.
- Build a Questionnaire Definition module that renders versioned pre-survey and post-survey definitions from structured configuration. The MVP admin UI must not edit questionnaire text, options, or scoring rules.
- Build a Questionnaire Response module that stores locked raw responses by participant, phase, item, questionnaire version, instrument, and dimension.
- Build a Questionnaire Scoring module that computes derived pre scores, post scores, attention-check status, and change scores for export. It should be usable without rendering UI.
- Build an AI Provider module with a configurable provider boundary. Codex GPT-5.5 is preferred for participant dialogue when it can satisfy the 10-second response SLA; DeepSeek-style OpenAI-compatible providers are fallback options with server-side API key handling. Codex uses local `codex app-server` and persists a thread id per Experiment Session. Business logic should depend on a provider interface rather than a hard-coded vendor call.
- Build an AI Dialogue module that stores participant messages, assistant messages, prompt mode (`promptless`), provider metadata, model name, generation parameters, timing, retry count, fallback metadata, and sanitized errors.
- Do not send system prompts, developer instructions, base instructions, or model-side topic guidance to dialogue model providers in the current Study One Pilot.
- Enforce dialogue completion eligibility in backend logic using both thresholds: at least 10 participant turns and at least 15 minutes since dialogue start. The AI must not determine eligibility.
- Build a Behavior Event module for key experiment events and technical diagnostics, not high-granularity frontend analytics.
- Build an Audit Log module for administrator actions such as import, reset, exclusion, configuration change, and export.
- Build an Export Package module that creates a ZIP archive from PostgreSQL and includes raw tables, derived scoring files, an analysis dataset, raw chat JSONL, behavior events, audit logs, AI call diagnostics, README, and manifest.
- Clearly separate routine statistical data from sensitive raw chat. `analysis_dataset.csv` must not include raw dialogue text.
- Provide frontend participant screens for self-generating or entering a participant code, pre-survey, Study One Pilot dialogue, dialogue completion progress, post-survey, and final completion.
- Provide frontend admin screens for login, participant import, progress dashboard, participant detail/review, reset/exclusion actions, and export trigger/download.
- Use a backend API boundary that supports participant flow endpoints, admin flow endpoints, AI dialogue endpoints, questionnaire endpoints, and export endpoints. Keep API details stable enough for future UI redesign.
- Store enough AI provider metadata for reproducibility: provider name, endpoint configuration key or base URL identity without secrets, model name, available model version/config snapshot, prompt mode, generation parameters, request/response timestamps, retry count, fallback metadata, and sanitized error data.
- Questionnaire HITL was resolved on 2026-05-15: bracket placeholders render as 专业选择; DIDS is removed from both phases; U-MICS is retained; the current implementation map is `mentor_echo_questionnaire_v2026_05_15_major_umics_only`.

## Testing Decisions

- Tests should verify externally observable behavior and research protocol guarantees, not internal implementation details.
- Unit test the Experiment Session state machine: valid transitions, invalid transitions, completed-session duplicate prevention, reset behavior, exclusion behavior, and resume behavior.
- Unit test Group Assignment: imported assignment wins, blank imported group randomizes once, assignment source is recorded, and refresh/re-entry never re-randomizes.
- Unit test Dialogue Completion Eligibility: fewer than 10 turns fails, less than 15 minutes fails, both thresholds pass, and assistant messages do not count as participant turns.
- Unit test Questionnaire Definition and Response locking: correct version is attached, required fields are enforced, submitted phases cannot be edited by participants, and admin reset is required for correction.
- Unit test Questionnaire Scoring: raw responses map to instrument/dimension scores, attention checks are detected, missing items are handled explicitly, and change scores are computed from pre/post values.
- Unit test AI Provider adapter behavior with mocked OpenAI-compatible responses: successful response metadata, timeout/error capture, retry count, and secret-free logging.
- Unit test Behavior Event and Audit Log creation for required event families and administrator actions.
- Unit test Export Package generation: required files exist, row counts match source records, `analysis_dataset.csv` excludes raw chat, `chat_messages.jsonl` includes sensitive raw content only in the designated file, and manifest metadata is correct.
- Integration test the full participant path: code entry → pre-survey submission → assignment → chat → completion eligibility → post-survey → completed status.
- Integration test participant resume at each major stage: after pre-survey, during chat before eligibility, after chat completion, and after post-survey completion.
- Integration test administrator workflows: import participants, inspect dashboard metrics, reset a locked stage with reason, exclude a participant, and generate export.
- Integration test privacy boundaries: participant name is not stored, API keys are never exposed to frontend responses, full IP addresses are not exported by default, and raw chat is not included in the analysis dataset.
- Add lightweight frontend behavior tests for the participant path and admin dashboard once the React app exists. These should focus on user-visible behavior and API integration, not component internals.
- Because the repo currently starts from documentation rather than existing code, there is no prior test suite to mirror. The first implementation slice should establish the testing pattern before adding broad feature work.

## Out of Scope

- Polished UI, visual design system, animations, or production-grade responsive refinement.
- Researcher-side questionnaire builder or arbitrary questionnaire editing UI.
- Multi-admin, multi-role, coder-only, or read-only permission systems.
- Multiple AI providers selectable from admin UI.
- Model comparison experiments where groups bind to different providers or models.
- Automatic semantic de-identification of raw chat text.
- Fine-grained frontend analytics such as keystroke logging, focus tracking, or every input edit.
- External name-to-code roster management inside the platform.
- Longitudinal follow-up surveys beyond the immediate post-survey.
- Automated qualitative coding of chat text.
- Production deployment, institutional SSO, or enterprise compliance workflows beyond the MVP privacy boundaries.

## Further Notes

- Current implementation defaults to Study One Pilot (`pilot_single`): no participant-visible grouping, platform-generated codes are allowed, and grouping is reserved for a later study.
- Accepted architectural decisions already establish PostgreSQL as the system of record, React plus FastAPI as the stack, hybrid imported/randomized assignment with locking, versioned questionnaire configuration, and separation between routine analysis data and sensitive raw chat export.
- Before implementation, confirm the final AI model and provider parameters against current official provider documentation. The PRD intentionally keeps model selection configurable rather than hard-coded.
- Before implementing questionnaire scoring, use the resolved source-issue decisions and item/scoring map in [`docs/questionnaire-implementation-map.md`](../questionnaire-implementation-map.md): repeated post-survey item text, scale anchor inconsistencies, final dimension/scoring rules, attention checks, and participant-name omission are mapped there.
- The next recommended step after this PRD is to break it into independently implementable issues: project scaffold, database/schema foundation, participant registry, experiment session state machine, questionnaire configuration/scoring, AI dialogue/provider integration, admin dashboard, logging/audit, export package, and end-to-end verification.
