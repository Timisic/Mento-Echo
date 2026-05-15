# Questionnaire Implementation Map

Status: researcher-confirmed for current MVP implementation
Questionnaire version: `mentor_echo_questionnaire_v2026_05_15_major_umics_only`
Source snapshot: `docs/source/汇总问卷.docx` and `docs/汇总问卷.md`.
Related issue: <https://github.com/Timisic/Mento-Echo/issues/6>

## Researcher confirmation on 2026-05-15

- Render every source bracket placeholder `[专业选择/职业方向/价值观/人生目标]` as **专业选择**.
- Remove the **DIDS** scale from both pre-survey and post-survey.
- Keep the **U-MICS** scale in both pre-survey and post-survey.
- Because the original post-survey attention check lived inside DIDS, the current MVP has no post-survey attention-check item.
- The platform continues to store participant code only and does not store participant names.

## Purpose

This is the durable implementation map for the MVP pre-survey and post-survey. Implementation must treat questionnaire definitions as versioned structured configuration, store raw item responses and derived scores separately, and attach the questionnaire version above to every response and score record.

## Source and privacy decisions

| Source field / note | Platform item key | Decision |
|---|---|---|
| source pre Q1 / post Q1 编号 | participant_code | Do not collect as an editable questionnaire response. Attach the already-validated participant code from the Experiment Session to every submission/response/score/export row; UI may show it read-only. |
| source pre Q2 / post Q2 姓名 | none | Omit from rendering and storage. The platform stores no participant names; any name-to-code roster stays outside the platform. |
| source pre summary says 年龄 | none | No actual age question appears in the Word form or Markdown conversion, so this version does not add an age item. Adding age later requires a new questionnaire version. |
| source bracket placeholder | 专业选择 | Replace `[专业选择/职业方向/价值观/人生目标]` with `专业选择` in all retained U-MICS items. |
| source DIDS sections | none | Remove DIDS from both phases for this questionnaire version. |

All implemented items below are required unless explicitly marked otherwise. Participant-facing labels should remain in Chinese as listed here.

## Scale profiles

| scale | value type | anchors/options |
|---|---|---|
| gender_options | categorical | 男, 女 |
| grade_options | categorical | 大一, 大二, 大三, 大四, 硕士研究生, 博士研究生 |
| identity_distress_1_5 | integer | 1=完全没有; 2=比较轻; 3=中等; 4=比较严重; 5=非常严重 |
| agreement_1_5 | integer | 1=完全不符合; 5=完全符合; numeric range 1-5 |
| bpnsfs_agreement_1_5 | integer | 1=完全不符合; 2=比较不符合; 3=不确定; 4=比较符合; 5=完全符合 |
| agreement_1_7 | integer | 1=非常不同意; 7=非常同意; numeric range 1-7 |
| semantic_differential_1_5 | integer | 1=非常接近左侧; 2=比较接近左侧; 3=两者差不多; 4=比较接近右侧; 5=非常接近右侧 |

## Scoring profiles

- Use numeric mean scores for multi-item scales.
- Keep `valid_items` and `missing_items` for every derived score.
- Change scores are `post - pre` for dimensions measured in both phases: `identity_distress.total` and all U-MICS dimensions.
- Post-only instruments do not have change scores.
- No item in this map is reverse-scored.
- `pre_ac_umics_select_5` passes iff the stored numeric response is `5`; it is excluded from U-MICS scores.
- There is no post-survey attention check in this questionnaire version.

| phase | instrument | dimension | item count | score rule |
|---|---|---|---:|---|
| pre | identity_distress | total | 6 | mean(pre_identity_distress_01, pre_identity_distress_02, pre_identity_distress_03, pre_identity_distress_04, pre_identity_distress_05, pre_identity_distress_06) |
| pre | umics | commitment | 5 | mean(pre_umics_commitment_01, pre_umics_commitment_02, pre_umics_commitment_03, pre_umics_commitment_04, pre_umics_commitment_05) |
| pre | umics | in_depth_exploration | 5 | mean(pre_umics_in_depth_exploration_01, pre_umics_in_depth_exploration_02, pre_umics_in_depth_exploration_03, pre_umics_in_depth_exploration_04, pre_umics_in_depth_exploration_05) |
| pre | umics | reconsideration_of_commitment | 3 | mean(pre_umics_reconsideration_of_commitment_01, pre_umics_reconsideration_of_commitment_02, pre_umics_reconsideration_of_commitment_03) |
| post | identity_distress | total | 6 | mean(post_identity_distress_01, post_identity_distress_02, post_identity_distress_03, post_identity_distress_04, post_identity_distress_05, post_identity_distress_06) |
| post | perceived_ai_competence | total | 4 | mean(post_perceived_ai_competence_01, post_perceived_ai_competence_02, post_perceived_ai_competence_03, post_perceived_ai_competence_04) |
| post | ai_anthropomorphism | tool_vs_communication | 1 | mean(post_ai_anthropomorphism_01) |
| post | ai_anthropomorphism | stiff_vs_natural | 1 | mean(post_ai_anthropomorphism_02) |
| post | ai_anthropomorphism | answering_vs_responding | 1 | mean(post_ai_anthropomorphism_03) |
| post | ai_anthropomorphism | program_vs_conversational | 1 | mean(post_ai_anthropomorphism_04) |
| post | ai_anthropomorphism | low_interaction_vs_interactive | 1 | mean(post_ai_anthropomorphism_05) |
| post | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | 5 | mean(post_bpnsfs_autonomy_satisfaction_01, post_bpnsfs_autonomy_satisfaction_02, post_bpnsfs_autonomy_satisfaction_03, post_bpnsfs_autonomy_satisfaction_04, post_bpnsfs_autonomy_satisfaction_05) |
| post | bpnsfs_adapted_dialogue_experience | relatedness_satisfaction | 4 | mean(post_bpnsfs_relatedness_satisfaction_01, post_bpnsfs_relatedness_satisfaction_02, post_bpnsfs_relatedness_satisfaction_03, post_bpnsfs_relatedness_satisfaction_04) |
| post | umics | commitment | 5 | mean(post_umics_commitment_01, post_umics_commitment_02, post_umics_commitment_03, post_umics_commitment_04, post_umics_commitment_05) |
| post | umics | in_depth_exploration | 5 | mean(post_umics_in_depth_exploration_01, post_umics_in_depth_exploration_02, post_umics_in_depth_exploration_03, post_umics_in_depth_exploration_04, post_umics_in_depth_exploration_05) |
| post | umics | reconsideration_of_commitment | 3 | mean(post_umics_reconsideration_of_commitment_01, post_umics_reconsideration_of_commitment_02, post_umics_reconsideration_of_commitment_03) |
| post | bpnsfs_adapted_dialogue_experience | need_satisfaction_total | 9 | mean(post_bpnsfs_autonomy_satisfaction_01, post_bpnsfs_autonomy_satisfaction_02, post_bpnsfs_autonomy_satisfaction_03, post_bpnsfs_autonomy_satisfaction_04, post_bpnsfs_autonomy_satisfaction_05, post_bpnsfs_relatedness_satisfaction_01, post_bpnsfs_relatedness_satisfaction_02, post_bpnsfs_relatedness_satisfaction_03, post_bpnsfs_relatedness_satisfaction_04) |

## Resolved source issues

| Issue | Status | Implementation decision |
|---|---|---|
| post identity-distress Q4 repeats Q3 | Resolved | Map post item 2 to the missing pre-survey parallel text `我会因为专业、升学或职业选择拿不准而感到困扰。` under `post_identity_distress_02`. |
| identity-distress scale header conflict | Resolved | Use `identity_distress_1_5`: 1=完全没有 through 5=非常严重. Treat pre table `5完全符合` as a source typo. |
| BPNSFS post Q15/Q16 duplicate text | Accepted | Retain both as separate required items with distinct keys (`post_bpnsfs_autonomy_satisfaction_02` and `_03`) and score both. |
| pre summary mentions age but form has no age question | Resolved | Do not implement age in this questionnaire version. |
| U-MICS bracket placeholder | Resolved | Render as `专业选择` rather than slash-separated placeholder text. |
| DIDS in source questionnaire | Resolved | Remove DIDS from both pre-survey and post-survey. |
| post attention check was inside DIDS | Resolved | Remove the post attention check with DIDS; only the pre U-MICS attention check remains. |

## Pre-survey item map

| order | phase | item_key | item_text | type | scale | instrument | dimension | reverse | required | attention | scoring/pass |
|---:|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pre | pre_demo_gender | 您的性别 | single_choice | gender_options | demographics | gender | false | true | false | not_scored |
| 2 | pre | pre_demo_grade | 您目前在读： | single_choice | grade_options | demographics | grade | false | true | false | not_scored |
| 3 | pre | pre_identity_distress_01 | 我会因为未来发展方向不清楚而感到困扰。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 4 | pre | pre_identity_distress_02 | 我会因为专业、升学或职业选择拿不准而感到困扰。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 5 | pre | pre_identity_distress_03 | 我会因为还没有想清楚自己真正认同的价值观或信念而感到困扰。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 6 | pre | pre_identity_distress_04 | 我会因为还没有想清楚自己属于什么样的人或群体而感到困扰。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 7 | pre | pre_identity_distress_05 | 总体来说，这些与自我认同和未来方向有关的问题让我感到困扰。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 8 | pre | pre_identity_distress_06 | 这些与身份有关的不确定感已经影响了我的日常生活和情绪状态。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 9 | pre | pre_umics_commitment_01 | 我的专业选择让我对生活有确定感。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 10 | pre | pre_umics_commitment_02 | 我的专业选择很适合我。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 11 | pre | pre_umics_commitment_03 | 我觉得我的专业选择很有吸引力。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 12 | pre | pre_umics_commitment_04 | 我认同我的专业选择。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 13 | pre | pre_umics_commitment_05 | 我对我的专业选择感到有承诺。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 14 | pre | pre_umics_in_depth_exploration_01 | 我经常思考我的专业选择。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 15 | pre | pre_umics_in_depth_exploration_02 | 我试图去发现关于我的专业选择的新事物。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 16 | pre | pre_umics_in_depth_exploration_03 | 我经常反思我的专业选择。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 17 | pre | pre_umics_in_depth_exploration_04 | 我经常和其他人谈论我的专业选择。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 18 | pre | pre_umics_in_depth_exploration_05 | 我试图尽可能多地了解我的专业选择。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 19 | pre | pre_umics_reconsideration_of_commitment_01 | 我经常想，试着去寻找一个不同的专业选择可能会更好。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |
| 20 | pre | pre_umics_reconsideration_of_commitment_02 | 我经常想，一个新的专业选择会让我的生活变得更有趣。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |
| 21 | pre | pre_ac_umics_select_5 | 这道题请选择5 | matrix_single_choice | agreement_1_5 | attention_check | umics_attention | false | true | true | pass_if_response_eq_5 |
| 22 | pre | pre_umics_reconsideration_of_commitment_03 | 事实上，我正在寻找一个不同的专业选择。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |

## Post-survey item map

| order | phase | item_key | item_text | type | scale | instrument | dimension | reverse | required | attention | scoring/pass |
|---:|---|---|---|---|---|---|---|---|---|---|---|
| 1 | post | post_identity_distress_01 | 我会因为未来发展方向不清楚而感到困扰。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 2 | post | post_identity_distress_02 | 我会因为专业、升学或职业选择拿不准而感到困扰。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 3 | post | post_identity_distress_03 | 我会因为还没有想清楚自己真正认同的价值观或信念而感到困扰。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 4 | post | post_identity_distress_04 | 我会因为还没有想清楚自己属于什么样的人或群体而感到困扰。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 5 | post | post_identity_distress_05 | 总体来说，这些与自我认同和未来方向有关的问题让我感到困扰。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 6 | post | post_identity_distress_06 | 这些与身份有关的不确定感已经影响了我的日常生活和情绪状态。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 7 | post | post_perceived_ai_competence_01 | 这个 AI 给出的建议对我是有帮助的。 | single_choice | agreement_1_7 | perceived_ai_competence | total | false | true | false | scored |
| 8 | post | post_perceived_ai_competence_02 | 这个 AI 提供的信息是可信的。 | single_choice | agreement_1_7 | perceived_ai_competence | total | false | true | false | scored |
| 9 | post | post_perceived_ai_competence_03 | 这个 AI 给出的内容基本准确。 | single_choice | agreement_1_7 | perceived_ai_competence | total | false | true | false | scored |
| 10 | post | post_perceived_ai_competence_04 | 这个 AI 对这些问题是比较了解的。 | single_choice | agreement_1_7 | perceived_ai_competence | total | false | true | false | scored |
| 11 | post | post_ai_anthropomorphism_01 | 左：这个 AI 更像一个工具 / 右：这个 AI 更像是在和我交流 | matrix_semantic_differential | semantic_differential_1_5 | ai_anthropomorphism | tool_vs_communication | false | true | false | scored |
| 12 | post | post_ai_anthropomorphism_02 | 左：这个 AI 的表达比较生硬 / 右：这个 AI 的表达比较自然 | matrix_semantic_differential | semantic_differential_1_5 | ai_anthropomorphism | stiff_vs_natural | false | true | false | scored |
| 13 | post | post_ai_anthropomorphism_03 | 左：这个 AI 更像是在输出答案 / 右：这个 AI 更像是在回应我 | matrix_semantic_differential | semantic_differential_1_5 | ai_anthropomorphism | answering_vs_responding | false | true | false | scored |
| 14 | post | post_ai_anthropomorphism_04 | 左：这个 AI 更像一个程序 / 右：这个 AI 更像可以和我交流 | matrix_semantic_differential | semantic_differential_1_5 | ai_anthropomorphism | program_vs_conversational | false | true | false | scored |
| 15 | post | post_ai_anthropomorphism_05 | 左：这个 AI 几乎没有互动感 / 右：这个 AI 有明显的互动感 | matrix_semantic_differential | semantic_differential_1_5 | ai_anthropomorphism | low_interaction_vs_interactive | false | true | false | scored |
| 16 | post | post_bpnsfs_autonomy_satisfaction_01 | 在刚才这次对话中，我觉得自己可以按照自己的想法去思考和自己未来有关的内容。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | false | true | false | scored |
| 17 | post | post_bpnsfs_autonomy_satisfaction_02 | 在这次对话中，我觉得自己是在从自己的立场出发看待这些问题。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | false | true | false | scored |
| 18 | post | post_bpnsfs_autonomy_satisfaction_03 | 在这次对话中，我觉得自己是在从自己的立场出发看待这些问题。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | false | true | false | scored |
| 19 | post | post_bpnsfs_autonomy_satisfaction_04 | 这次对话让我觉得，关于自己未来方向的思考是由我自己主导的。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | false | true | false | scored |
| 20 | post | post_bpnsfs_autonomy_satisfaction_05 | 在这次对话中，我觉得自己可以比较自由地表达对这些问题的真实想法。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | false | true | false | scored |
| 21 | post | post_bpnsfs_relatedness_satisfaction_01 | 在这次对话中，我觉得自己的想法被认真对待了。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | relatedness_satisfaction | false | true | false | scored |
| 22 | post | post_bpnsfs_relatedness_satisfaction_02 | 在这次对话中，我感到自己是被理解的。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | relatedness_satisfaction | false | true | false | scored |
| 23 | post | post_bpnsfs_relatedness_satisfaction_03 | 这次对话让我觉得自己可以把这些困惑说出来，而不是被评判。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | relatedness_satisfaction | false | true | false | scored |
| 24 | post | post_bpnsfs_relatedness_satisfaction_04 | 与通用大模型对话时，我感受到一种支持性的、较为温和的交流氛围。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | relatedness_satisfaction | false | true | false | scored |
| 25 | post | post_umics_commitment_01 | 我的专业选择让我对生活有确定感。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 26 | post | post_umics_commitment_02 | 我的专业选择很适合我。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 27 | post | post_umics_commitment_03 | 我觉得我的专业选择很有吸引力。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 28 | post | post_umics_commitment_04 | 我认同我的专业选择。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 29 | post | post_umics_commitment_05 | 我对我的专业选择感到有承诺。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 30 | post | post_umics_in_depth_exploration_01 | 我经常思考我的专业选择。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 31 | post | post_umics_in_depth_exploration_02 | 我试图去发现关于我的专业选择的新事物。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 32 | post | post_umics_in_depth_exploration_03 | 我经常反思我的专业选择。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 33 | post | post_umics_in_depth_exploration_04 | 我经常和其他人谈论我的专业选择。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 34 | post | post_umics_in_depth_exploration_05 | 我试图尽可能多地了解我的专业选择。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 35 | post | post_umics_reconsideration_of_commitment_01 | 我经常想，试着去寻找一个不同的专业选择可能会更好。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |
| 36 | post | post_umics_reconsideration_of_commitment_02 | 我经常想，一个新的专业选择会让我的生活变得更有趣。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |
| 37 | post | post_umics_reconsideration_of_commitment_03 | 事实上，我正在寻找一个不同的专业选择。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |

## Implementation counts

| Count | Value | Notes |
|---|---:|---|
| Pre stored response items | 22 | 2 demographics + 6 identity distress + 13 U-MICS scored + 1 pre U-MICS attention check. |
| Post stored response items | 37 | 6 identity distress + 4 perceived AI competence + 5 anthropomorphism + 9 BPNSFS + 13 U-MICS. |
| Attention checks | 1 | `pre_ac_umics_select_5`; no post attention check in this version. |
| DIDS items | 0 | DIDS removed from both phases by researcher decision on 2026-05-15. |

