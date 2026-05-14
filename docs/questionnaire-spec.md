# Questionnaire Implementation Specification

## Source documents

- Raw Word source: `docs/source/汇总问卷.docx`
- Markdown conversion: [`docs/汇总问卷.md`](./汇总问卷.md)
- Research protocol: [`docs/研究1-AI对话平台.md`](./研究1-AI对话平台.md)

## MVP interpretation

The MVP treats questionnaires as versioned structured configuration. The admin UI does not edit questions or options.

The final AFK-ready item/scoring map for the current source snapshot is
[`docs/questionnaire-implementation-map.md`](./questionnaire-implementation-map.md).
Use that map as the implementation authority for item keys, normalized anchors,
dimension names, attention-check pass criteria, and the participant-code-only
privacy rule.

Each rendered questionnaire item should be defined with at least:

| Field | Meaning |
|---|---|
| `questionnaire_version` | Immutable version of the full pre/post questionnaire set. |
| `phase` | `pre` or `post`. |
| `item_key` | Stable machine-readable item identifier. |
| `item_text` | Participant-visible question text. |
| `item_type` | Example: `single_choice`, `matrix_single_choice`, `text`. |
| `scale_min` / `scale_max` | Numeric response range where applicable. |
| `scale_labels` | Anchor labels such as `完全不符合` and `完全符合`. |
| `instrument` | Example: identity distress, U-MICS, DIDS, perceived AI competence, AI anthropomorphism, BPNSFS. |
| `dimension` | Subscale/dimension when known. |
| `reverse_scored` | Boolean where scoring requires reverse coding. |
| `attention_check` | Boolean for attention check items. |
| `required` | Whether the item must be answered. |

## Pre-survey source content

The Word source currently describes the pre-survey as including:

1. Demographic/identifier information: participant code, name, gender, age, grade.
2. Baseline identity distress.
3. U-MICS items adapted to educational identity domains: major choice, career direction, values, life goals.
4. One attention check embedded in U-MICS.
5. DIDS items adapted to educational identity domains.

## Post-survey source content

The Word source currently describes the post-survey as including:

1. Identifier information: participant code and name.
2. Baseline/identity distress items.
3. Perceived AI competence.
4. AI anthropomorphism perception using a 5-point semantic differential scale.
5. BPNSFS items for the dialogue experience.
6. U-MICS adapted identity items.
7. DIDS adapted identity items.
8. One attention check embedded in DIDS.

## MVP privacy adjustment

The Word source includes “姓名”. The MVP platform must not store participant names. Implementation should render/store participant code only.

If researchers require names for recruitment or compensation, keep the name-to-code mapping outside the platform.

## Submission and locking

- A participant can submit each phase once.
- After submission, responses are locked from participant edits.
- Administrator reset can reopen a phase only with an audit log reason.
- Resetting a stage must not silently delete historical data; preserve enough audit information to explain what changed.

## Scoring and export

The MVP should store raw item responses and derived scores separately.

Recommended derived score records:

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
| `attention_check_passed` | Attention check status where relevant. |

`analysis_dataset.csv` should include one row per participant with pre scores, post scores, and change scores for each exported dimension.

## Source issues resolved by the final map

The source-document observations below are resolved or explicitly accepted in
[`docs/questionnaire-implementation-map.md`](./questionnaire-implementation-map.md):

- The adjacent repeated post-survey identity-distress text is treated as a
  source typo. `post_identity_distress_02` uses the missing parallel
  professional/study/career-choice wording from the pre-survey.
- Identity-distress anchors are normalized to `1=完全没有` through
  `5=非常严重`.
- U-MICS, DIDS, BPNSFS adapted dialogue experience, perceived AI competence,
  AI anthropomorphism, reverse-scoring flags, attention checks, required flags,
  and participant-name omission are explicitly mapped for implementation.
