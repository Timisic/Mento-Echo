# Questionnaire Implementation Specification

## Source documents

- Raw Word source: `docs/source/汇总问卷.docx`
- Markdown conversion: [`docs/汇总问卷.md`](./汇总问卷.md)
- Current implementation map: [`docs/questionnaire-implementation-map.md`](./questionnaire-implementation-map.md)
- Research protocol: [`docs/研究1-AI对话平台.md`](./研究1-AI对话平台.md)

## Current researcher-confirmed version

Current questionnaire version: `mentor_echo_questionnaire_v2026_05_15_major_umics_only`

Researcher confirmation on 2026-05-15:

1. All source placeholders like `[专业选择/职业方向/价值观/人生目标]` are rendered as **专业选择**.
2. DIDS is removed from both pre-survey and post-survey.
3. U-MICS is retained in both pre-survey and post-survey.
4. The source post-survey attention check was inside DIDS, so it is removed with DIDS. The current version has only one attention check: pre-survey U-MICS item `这道题请选择5`.
5. The platform stores participant code only and does not store participant names.

## MVP interpretation

The MVP treats questionnaires as versioned structured configuration. The admin UI does not edit questions or options.

Each rendered questionnaire item should be defined with at least:

| Field | Meaning |
|---|---|
| `questionnaire_version` | Immutable version of the full pre/post questionnaire set. |
| `phase` | `pre` or `post`. |
| `item_key` | Stable machine-readable item identifier. |
| `item_text` | Participant-visible question text. |
| `item_type` | Example: `single_choice`, `matrix_single_choice`, `matrix_semantic_differential`, `text`. |
| `scale_min` / `scale_max` | Numeric response range where applicable. |
| `scale_labels` | Anchor labels such as `完全不符合` and `完全符合`. |
| `instrument` | Example: identity distress, U-MICS, perceived AI competence, AI anthropomorphism, BPNSFS. |
| `dimension` | Subscale/dimension when known. |
| `reverse_scored` | Boolean where scoring requires reverse coding. |
| `attention_check` | Boolean for attention check items. |
| `required` | Whether the item must be answered. |

## Pre-survey content

Implemented pre-survey content:

1. Demographic/identifier-related items rendered by the platform:
   - participant code is attached from the Experiment Session, not collected as editable questionnaire response;
   - gender;
   - grade.
2. Baseline identity distress: 6 items, scale 1=完全没有 to 5=非常严重.
3. U-MICS adapted to **专业选择**:
   - commitment: 5 items;
   - in-depth exploration: 5 items;
   - reconsideration of commitment: 3 items.
4. One U-MICS attention check: `这道题请选择5`.

DIDS is not implemented in the pre-survey.

## Post-survey content

Implemented post-survey content:

1. Participant code is attached from the Experiment Session, not collected as editable questionnaire response.
2. Identity distress: 6 items, scale 1=完全没有 to 5=非常严重.
3. Perceived AI competence: 4 items, scale 1=非常不同意 to 7=非常同意.
4. AI anthropomorphism: 5 semantic differential items, scale 1=非常接近左侧 to 5=非常接近右侧.
5. BPNSFS adapted dialogue experience: 9 items.
6. U-MICS adapted to **专业选择**:
   - commitment: 5 items;
   - in-depth exploration: 5 items;
   - reconsideration of commitment: 3 items.

DIDS is not implemented in the post-survey. There is no post-survey attention check in this questionnaire version.

## MVP privacy adjustment

The Word source includes “姓名”. The MVP platform must not store participant names. Implementation should render/store participant code only.

If researchers require names for recruitment or compensation, keep the name-to-code mapping outside the platform.

## Submission and locking

- A participant can submit each phase once.
- After submission, responses are locked from participant edits.
- Administrator reset can reopen a phase only with an audit log reason.
- Resetting a stage must not silently delete historical data; preserve enough audit information to explain what changed.

## Scoring and export

The MVP stores raw item responses and derived scores separately.

Derived score records include:

| Field | Meaning |
|---|---|
| `participant_code` | Research identifier. |
| `phase` | `pre` or `post`. |
| `questionnaire_version` | Version used for scoring. |
| `instrument` | Scale or instrument name. |
| `dimension` | Subscale/dimension. |
| `score` | Computed score. |
| `valid_items` | Count of valid answered items. |
| `missing_items` | Count/list of missing items. |
| `attention_check_passed` | Attention check status where relevant; `null` for phases without attention checks. |

`analysis_dataset.csv` should include one row per participant with pre scores, post scores, and change scores for dimensions measured in both phases.

## Current known source issues and resolutions

- The post-survey identity distress source has a duplicated item. Current implementation maps `post_identity_distress_02` to the pre-survey parallel item: `我会因为专业、升学或职业选择拿不准而感到困扰。`
- Identity distress source anchors contained a typo/conflict. Current implementation uses 1=完全没有 to 5=非常严重.
- BPNSFS contains two identical items about thinking from one's own standpoint. Current implementation keeps both as separate required items with distinct item keys.
- The source summary mentions age, but the source questionnaire body has no actual age item. Current implementation does not collect age.
- DIDS source sections remain in the raw converted document for provenance, but they are intentionally not part of the current implemented questionnaire version.
