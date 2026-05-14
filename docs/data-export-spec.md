# Data Export Specification

## Export principle

PostgreSQL is the system of record. Exports are generated snapshots for analysis, audit, and coding. The canonical export format is a ZIP archive containing CSV/JSONL files plus a README.

## ZIP contents

Recommended export package layout:

```text
mentor-echo-export-{timestamp}/
├── README.md
├── participants.csv
├── experiment_sessions.csv
├── questionnaire_responses.csv
├── questionnaire_scores.csv
├── analysis_dataset.csv
├── chat_messages.jsonl
├── behavior_events.jsonl
├── audit_logs.csv
├── ai_call_records.csv
└── export_manifest.json
```

## Required files

### README.md

Human-readable export description:

- export timestamp;
- questionnaire version;
- AI provider/model configuration snapshot;
- system prompt versions;
- completion rule: 10 participant turns + 15 minutes;
- group assignment rules;
- privacy warning for raw chat;
- field descriptions or links to schema docs.

### participants.csv

One row per participant code.

Suggested fields:

- `participant_code`
- `imported_at`
- `import_batch_id`
- `assigned_group_imported`
- `created_at`
- `excluded`
- `exclusion_reason`

### experiment_sessions.csv

One row per experiment session.

Suggested fields:

- `experiment_session_id`
- `participant_code`
- `group`
- `assignment_source`
- `status`
- `started_at`
- `pre_survey_submitted_at`
- `chat_started_at`
- `chat_completed_at`
- `post_survey_submitted_at`
- `completed_at`
- `participant_turn_count`
- `dialogue_elapsed_seconds`
- `met_min_turns`
- `met_min_duration`
- `resume_count`
- `last_seen_at`

### questionnaire_responses.csv

Long-form raw response table.

Suggested fields:

- `participant_code`
- `experiment_session_id`
- `phase`
- `questionnaire_version`
- `item_key`
- `instrument`
- `dimension`
- `response_value`
- `response_text`
- `submitted_at`

### questionnaire_scores.csv

Long-form derived scores.

Suggested fields:

- `participant_code`
- `experiment_session_id`
- `phase`
- `questionnaire_version`
- `instrument`
- `dimension`
- `score`
- `valid_items`
- `missing_items`
- `attention_check_passed`

### analysis_dataset.csv

Wide analysis-ready dataset. One row per participant code.

Required identity/status fields:

- `participant_code`
- `group`
- `assignment_source`
- `status`
- `excluded`
- `exclusion_reason`
- `completed`
- `pre_survey_submitted_at`
- `chat_started_at`
- `chat_completed_at`
- `post_survey_submitted_at`
- `completed_at`
- `participant_turn_count`
- `dialogue_elapsed_seconds`
- `met_min_turns`
- `met_min_duration`
- `resume_count`

Score fields should follow a stable pattern:

```text
{instrument}_{dimension}_pre
{instrument}_{dimension}_post
{instrument}_{dimension}_change
```

Examples:

```text
identity_distress_total_pre
identity_distress_total_post
identity_distress_total_change
umics_commitment_pre
umics_commitment_post
umics_commitment_change
```

Final instrument/dimension names must match the implemented questionnaire scoring config.

### chat_messages.jsonl

Sensitive raw dialogue export. One JSON object per message.

Suggested fields:

- `experiment_session_id`
- `participant_code`
- `group`
- `message_index`
- `role` (`participant` or `assistant`)
- `content`
- `created_at`
- `provider_name` for assistant messages
- `model_name` for assistant messages
- `system_prompt_version` for assistant messages
- `generation_params` for assistant messages

### behavior_events.jsonl

One JSON object per key experiment event or technical diagnostic event.

Suggested fields:

- `event_id`
- `experiment_session_id`
- `participant_code`
- `event_type`
- `stage`
- `created_at`
- `metadata`

### audit_logs.csv

Administrator action history.

Suggested fields:

- `audit_log_id`
- `admin_id`
- `action`
- `target_type`
- `target_id`
- `reason`
- `created_at`
- `metadata`

### ai_call_records.csv

Technical AI provider diagnostics.

Suggested fields:

- `ai_call_id`
- `experiment_session_id`
- `participant_code`
- `provider_name`
- `model_name`
- `system_prompt_version`
- `request_started_at`
- `response_completed_at`
- `duration_ms`
- `retry_count`
- `status`
- `error_code`
- `error_message_sanitized`

### export_manifest.json

Machine-readable manifest:

- export ID;
- generated timestamp;
- administrator ID;
- filters applied;
- included files;
- row counts;
- hash/checksum per file if implemented;
- `contains_raw_chat: true | false`.

## Privacy boundary

- `analysis_dataset.csv` should not include raw chat text.
- `chat_messages.jsonl` contains sensitive raw content and should be labelled clearly.
- The platform does not store participant names.
- Full IP addresses should not be exported by default.
