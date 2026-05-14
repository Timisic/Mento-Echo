# Mentor Echo MVP Specification

## Purpose

Build a stable backend-first MVP for an AI dialogue experiment on university students' identity formation. UI may be simple, but the experimental lifecycle, data integrity, AI provider boundary, logging, and export must be reliable enough for pilot use.

## MVP scope

The MVP implements the complete experimental loop:

```text
Unified entry
→ participant code verification
→ pre-survey
→ group assignment
→ AI dialogue
→ post-survey
→ completion
→ researcher export
```

## Non-goals for MVP

- Polished visual design or advanced UI animations.
- Researcher-side questionnaire editing UI.
- Multi-role researcher permission system.
- Multiple AI providers selectable from the admin UI.
- Fine-grained frontend analytics such as keystroke tracking or focus tracking.
- Automatic semantic de-identification of raw chat text.

## Users

### Participant

A participant enters the platform with a researcher-issued participant code, completes the pre-survey, talks with the assigned AI condition, and completes the post-survey.

### Researcher administrator

A single administrator account can:

- import participant codes and optional pre-assigned groups;
- view participant progress and key completion metrics;
- reset locked stages when necessary;
- mark sessions as excluded or requiring review;
- export research data;
- trigger actions that are recorded in audit logs.

## Participant identity

- The platform stores `participant_code` but does not store participant names.
- The platform may generate internal IDs such as `participant_id` and `experiment_session_id`.
- If the researcher needs a name-to-code mapping, it must be kept outside the platform.
- The participant code is the cross-stage research identifier in exports.

## Participant import

Minimum import fields:

| Field | Required | Notes |
|---|---:|---|
| `participant_code` | yes | Unique researcher-issued code. |
| `assigned_group` | no | `experiment` or `control`; blank means randomize on first entry. |

Recommended import handling:

- Reject duplicate participant codes in the same import.
- Normalize whitespace and casing according to a documented rule.
- Record import time and administrator in the audit log.
- Preserve the original imported assignment source for exports.

## Group assignment

Group assignment supports both pre-assigned and randomized flows:

1. If an imported participant row includes `assigned_group`, the platform uses that group.
2. If `assigned_group` is blank, the platform randomizes when the participant first reaches the assignment point.
3. Once assigned, the group is locked and must not change on refresh, logout, or resume.
4. Exports must include `assignment_source = imported | randomized`.

Default groups:

| Group | Meaning |
|---|---|
| `experiment` | Identity development topic: current major, future study/work direction, self-understanding, values, goals. |
| `control` | Identity-unrelated light topic: movies, music, food, travel, sports, campus daily life, hobbies, general knowledge chat. |

## Experimental flow

### Entry

- Participant enters `participant_code`.
- If the code does not exist, show a neutral error and do not create a session.
- If an incomplete experiment session exists for the code, resume it.
- If a completed session exists, show completion status and do not allow duplicate submission unless the administrator resets it.

### Pre-survey

- Participant completes the configured pre-survey.
- On submission, responses are saved and locked.
- Group assignment occurs after pre-survey submission if not already imported.
- The platform does not need to show a persistent “pre-survey in progress” admin state for MVP.

### AI dialogue

- Dialogue starts after pre-survey submission and group assignment.
- Participant instructions must state that valid completion requires at least 10 participant messages and at least 15 minutes.
- The system tracks participant turn count and elapsed time from dialogue start.
- The “finish dialogue / enter post-survey” action is disabled until both thresholds are met.
- The AI may provide a summary or closing guidance near the end, but completion eligibility is determined by the platform, not by the AI.

### Post-survey

- Participant reaches post-survey only after dialogue completion.
- On submission, responses are saved and locked.
- The experiment session becomes `completed`.
- The platform does not need to show a persistent “post-survey in progress” admin state for MVP.

## Status machine

Canonical session statuses:

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

Admin dashboard should show the status plus key metrics:

- participant code;
- group and assignment source;
- pre-survey submitted yes/no;
- dialogue started time;
- participant turn count;
- dialogue elapsed minutes;
- completion eligibility yes/no;
- dialogue completed yes/no;
- post-survey submitted yes/no;
- final completion/exclusion status;
- resume count or last seen time when useful.

## Resume behavior

- A participant re-entering the same code resumes the same experiment session.
- Refreshing or re-entering must not create a new assignment or duplicate responses.
- Previously saved survey and message data remain preserved.
- Resume events are recorded as behavior events.

## Questionnaire rules

- Questionnaire definitions are structured configuration, not admin-editable in MVP.
- Each questionnaire definition has a `questionnaire_version`.
- Submitted responses are immutable for participants.
- Administrator reset is the only path for correction and must write an audit log with actor, time, stage, and reason.
- The source Word questionnaire contains name fields; MVP implementation omits participant name storage and uses participant code only.

## AI provider

MVP provider requirements:

- Use a single configured SOTA model through an API key.
- Use an OpenAI-compatible chat completion interface where possible.
- Keep a backend `AIProvider` boundary so the model/provider can be replaced later.
- Do not hard-code the selected model name in business logic.

Every AI response record should preserve enough metadata for reproducibility:

| Field | Purpose |
|---|---|
| `provider_name` | Provider used for the call. |
| `base_url` or provider config key | Identifies the OpenAI-compatible endpoint without exposing secrets. |
| `model_name` | Configured model. |
| `model_version` or config snapshot | Version if available. |
| `system_prompt_version` | Prompt condition used for the group. |
| `generation_params` | Temperature, max tokens, top_p, etc. |
| `request_started_at` / `response_completed_at` | Timing diagnostics. |
| `retry_count` | Stability diagnostics. |
| `error_code` / `error_message` | Stored only for failed calls. |

## AI condition behavior

### Experiment group

Theme: whether the participant wants to continue their current major and whether future study or work should continue in this direction.

The AI should:

- guide the participant to describe current major experience;
- ask about key experiences and sources of uncertainty;
- help clarify reasons to continue and reasons for hesitation;
- encourage reflection on study, work, future lifestyle, values, and self-understanding;
- summarize core confusion, clarified points, missing information, and next verification actions near the end.

The AI should not present the final summary as a separate formal report; it remains part of the dialogue.

### Control group

Theme: identity-unrelated casual conversation.

Allowed topics include movies, music, food, travel, sports, campus daily life, hobbies, and general knowledge chat.

The AI should avoid actively discussing:

- major choice;
- career planning;
- life goals;
- values;
- self-understanding;
- future development.

If the participant raises identity-related content, the AI may answer briefly and redirect to a light topic. Such events should remain visible in raw chat for later manipulation checks or coding.

## Behavior logging

Record key experiment events plus technical diagnostics. Do not record every keystroke or focus event.

Required event families:

- participant entry and code validation;
- pre-survey submission;
- group assignment creation;
- dialogue start;
- participant message saved;
- AI response saved;
- AI call failure/retry;
- completion eligibility reached;
- dialogue completed;
- post-survey submission;
- session resumed;
- administrator reset/exclusion;
- data export requested and completed.

Recommended technical fields:

- event time;
- participant code or session ID;
- event type;
- stage;
- request duration;
- provider/model for AI events;
- retry count;
- sanitized error code/message;
- coarse browser/device information if useful;
- no full IP address by default.

## Audit logging

Audit logs are for researcher administrator actions, especially:

- login/logout if implemented;
- participant import;
- stage reset;
- participant exclusion or inclusion change;
- export request;
- configuration change.

Each audit log should include actor, action, target, timestamp, and reason when applicable.

## Data export

The canonical export is a ZIP archive generated from PostgreSQL. See [data-export-spec.md](./data-export-spec.md) for concrete files.

MVP must include a wide `analysis_dataset.csv` with one row per participant code and questionnaire scores/change scores for convenient statistical analysis.

Raw chat export is sensitive and should be clearly separated and labelled inside the export package.

## Data storage

- PostgreSQL is the single source of truth.
- CSV, JSONL, Excel, and ZIP files are generated export views, not primary storage.
- Raw dialogue, survey responses, questionnaire versions, behavior events, and audit logs are stored in PostgreSQL.

## Technology stack

- Frontend: React.
- Backend: FastAPI.
- Database: PostgreSQL.
- AI integration: backend server-side API key; OpenAI-compatible request shape.

## Suggested backend domain tables

This is not a final schema, but implementation should cover these domain records:

- `participants`
- `experiment_sessions`
- `group_assignments`
- `questionnaire_definitions`
- `questionnaire_items`
- `questionnaire_responses`
- `questionnaire_scores`
- `chat_messages`
- `ai_call_records`
- `behavior_events`
- `audit_logs`
- `exports`

## Acceptance criteria

The MVP is complete when all are true:

1. Researcher administrator can import participant codes with optional pre-assigned groups.
2. Participant can complete the full entry → pre-survey → assignment → dialogue → post-survey flow.
3. Random assignment happens only once for participants without imported assignment.
4. Refresh/re-entry resumes the same experiment session.
5. Dialogue cannot be completed before 10 participant turns and 15 minutes.
6. Submitted questionnaires are locked from participant edits.
7. Administrator can view per-participant status and key metrics.
8. Administrator can reset stages with audited reason.
9. AI calls go through a configurable OpenAI-compatible provider boundary.
10. Behavior events and AI technical diagnostics are recorded.
11. Export ZIP includes raw and derived files, including `analysis_dataset.csv`.
12. Platform stores participant codes only and does not store participant names.
