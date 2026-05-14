# Questionnaire Implementation Map

Status: ready for AFK implementation  
Questionnaire version: `mentor_echo_questionnaire_v2026_05_14_hitl_map`  
Source snapshot: `docs/source/汇总问卷.docx` and `docs/汇总问卷.md`, verified on 2026-05-14.  
Related issue: <https://github.com/Timisic/Mento-Echo/issues/6>

## Purpose

This is the durable implementation map for the MVP pre-survey and post-survey. It resolves the questionnaire HITL blockers before questionnaire rendering, locked submission, scoring, and export are implemented.

Implementation must treat questionnaire definitions as versioned structured configuration. Store raw item responses and derived scores separately, and attach `questionnaire_version = mentor_echo_questionnaire_v2026_05_14_hitl_map` to every response and score record.

## Source and privacy decisions

| Source field / note | Platform item key | Decision |
|---|---|---|
| source pre Q1 / post Q1 编号 | participant_code | Do not collect as an editable questionnaire response. Attach the already-validated participant code from the Experiment Session to every submission/response/score/export row; UI may show it read-only. |
| source pre Q2 / post Q2 姓名 | none | Omit from rendering and storage. The platform stores no participant names; any name-to-code roster stays outside the platform. |
| source pre summary says 年龄 | none | No actual age question appears in the Word form or Markdown conversion, so v2026-05-14 does not add an age item. Adding age later requires a new questionnaire version. |

All implemented items below are required unless explicitly marked otherwise. Participant-facing labels should remain in Chinese as listed here.

## Scale profiles

| scale | value type | anchors/options | implementation note |
|---|---|---|---|
| gender_options | categorical | 男, 女 | Store normalized option code such as `male` / `female`; display source Chinese labels. |
| grade_options | categorical | 大一, 大二, 大三, 大四, 硕士研究生, 博士研究生 | Store normalized option codes such as `undergrad_year_1` ... `doctoral`. |
| identity_distress_1_5 | integer | 1=完全没有; 2=比较轻; 3=中等; 4=比较严重; 5=非常严重 | Normalizes source typo `4比较严重·` and `5完全符合`; use instruction/post anchors as authority. |
| agreement_1_5 | integer | 1=完全不符合; 2; 3; 4; 5=完全符合 | Used by U-MICS, DIDS, and attention checks. |
| bpnsfs_agreement_1_5 | integer | 1=完全不符合; 2=比较不符合; 3=不确定; 4=比较符合; 5=完全符合 | BPNSFS source instruction provides intermediate labels. |
| agreement_1_7 | integer | 1=非常不同意; 2; 3; 4; 5; 6; 7=非常同意 | Used by perceived AI competence. |
| semantic_differential_1_5 | integer | 1=非常接近左侧; 2=比较接近左侧; 3=两者差不多; 4=比较接近右侧; 5=非常接近右侧 | For every anthropomorphism row, higher value means closer to the right-side, more anthropomorphic/interpersonal anchor. |

## Scoring profiles

Use numeric mean scores for multi-item scales. Keep `valid_items` and `missing_items` for every derived score. Because MVP forms require every implemented item, missing values should be exceptional and should still be represented explicitly in exports.

Change scores are `post - pre` for dimensions measured in both phases: `identity_distress.total`, all U-MICS dimensions, and all DIDS dimensions. Post-only instruments do not have change scores.

| instrument | dimension | score rule | interpretation / note |
|---|---|---|---|
| demographics | gender, grade | none | Raw categorical only; no score. |
| identity_distress | total | mean(pre/post_identity_distress_01..06) | Higher = more identity/future-direction distress. Compute pre, post, and post-pre change. |
| umics | commitment | mean items 01..05 | Higher = stronger commitment. |
| umics | in_depth_exploration | mean items 01..05 | Higher = more in-depth exploration. |
| umics | reconsideration_of_commitment | mean items 01..03 | Higher = more reconsideration of current commitment. |
| dids | commitment_making | mean items 01..05 | Higher = more commitment making. |
| dids | exploration_in_breadth | mean items 01..05 | Higher = more exploration in breadth. |
| dids | ruminative_exploration | mean items 01..05 | Higher = more ruminative exploration. |
| dids | identification_with_commitment | mean items 01..05 | Higher = more identification with commitment. |
| dids | exploration_in_depth | mean items 01..05 | Higher = more exploration in depth. |
| perceived_ai_competence | total | mean post_perceived_ai_competence_01..04 | Post-only. Higher = stronger perceived competence/helpfulness/credibility/accuracy/knowledge. |
| ai_anthropomorphism | total | mean post_ai_anthropomorphism_01..05 | Post-only. Higher = closer to right-side anthropomorphic/interpersonal anchors. |
| bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | mean post_bpnsfs_autonomy_satisfaction_01..05 | Post-only. Source-authored duplicate items 02 and 03 are both retained with separate keys. |
| bpnsfs_adapted_dialogue_experience | relatedness_satisfaction | mean post_bpnsfs_relatedness_satisfaction_01..04 | Post-only. Do not infer absent BPNSFS competence/frustration dimensions. |
| bpnsfs_adapted_dialogue_experience | need_satisfaction_total | mean all 9 BPNSFS adapted items | Optional convenience derived score; keep dimension scores as primary. |

### Reverse scoring

No item in this map is reverse-scored. Set `reverse_scored=false` for every item. If a future validated scoring decision requires reverse coding, create a new questionnaire version and document the affected item keys.

### Attention checks and validity flags

- `pre_ac_umics_select_5`: pass iff the stored numeric response is `5`.
- `post_ac_dids_select_1`: pass iff the stored numeric response is `1`.
- `pre_attention_check_passed` is true only when all pre-survey attention checks pass.
- `post_attention_check_passed` is true only when all post-survey attention checks pass.
- Export both phase-level attention flags and the raw attention-check item responses.
- Attention-check items are not included in U-MICS or DIDS dimension scores.

## Resolved and accepted source issues

| Issue | Status | Implementation decision |
|---|---|---|
| post identity-distress Q4 repeats Q3 | Resolved | Word and Markdown both show duplicate `我会因为未来发展方向不清楚而感到困扰。`; pre-survey identity-distress has six parallel rows, so implementation maps post item 2 to the missing parallel text `我会因为专业、升学或职业选择拿不准而感到困扰。` under `post_identity_distress_02`. |
| identity-distress scale header conflict | Resolved | Use `identity_distress_1_5` anchors from the instruction and post single-choice endpoints: 1=完全没有 through 5=非常严重. Treat pre table `5完全符合` as a source typo. |
| BPNSFS post Q15/Q16 duplicate text | Accepted | The Word source contains identical text twice. Retain both as separate required items with distinct keys (`post_bpnsfs_autonomy_satisfaction_02` and `_03`) and score both; this preserves source intent without inventing a replacement item. |
| pre summary mentions age but form has no age question | Resolved | Do not implement age in this questionnaire version because there is no source item wording/control. A future researcher change should create a new version. |
| U-MICS/DIDS bracketed domain phrase | Resolved | Do not multiply items by four domains. Render the bracketed slash phrase as source text, preserving the 13 U-MICS and 25 DIDS scored-item counts per phase. |

## Pre-survey item map

| order | phase | source | item_key | item_text | type | scale | instrument | dimension | reverse | required | attention | scoring/pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pre | pre Q3 | pre_demo_gender | 您的性别 | single_choice | gender_options | demographics | gender | false | true | false | not_scored |
| 2 | pre | pre Q4 | pre_demo_grade | 您目前在读： | single_choice | grade_options | demographics | grade | false | true | false | not_scored |
| 3 | pre | pre Q5 row 1 | pre_identity_distress_01 | 我会因为未来发展方向不清楚而感到困扰。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 4 | pre | pre Q5 row 2 | pre_identity_distress_02 | 我会因为专业、升学或职业选择拿不准而感到困扰。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 5 | pre | pre Q5 row 3 | pre_identity_distress_03 | 我会因为还没有想清楚自己真正认同的价值观或信念而感到困扰。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 6 | pre | pre Q5 row 4 | pre_identity_distress_04 | 我会因为还没有想清楚自己属于什么样的人或群体而感到困扰。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 7 | pre | pre Q5 row 5 | pre_identity_distress_05 | 总体来说，这些与自我认同和未来方向有关的问题让我感到困扰。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 8 | pre | pre Q5 row 6 | pre_identity_distress_06 | 这些与身份有关的不确定感已经影响了我的日常生活和情绪状态。 | matrix_single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 9 | pre | pre Q6 row 1 | pre_umics_commitment_01 | 我的[专业选择/职业方向/价值观/人生目标]让我对生活有确定感。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 10 | pre | pre Q6 row 2 | pre_umics_commitment_02 | 我的[专业选择/职业方向/价值观/人生目标]很适合我。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 11 | pre | pre Q6 row 3 | pre_umics_commitment_03 | 我觉得我的[专业选择/职业方向/价值观/人生目标]很有吸引力。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 12 | pre | pre Q6 row 4 | pre_umics_commitment_04 | 我认同我的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 13 | pre | pre Q6 row 5 | pre_umics_commitment_05 | 我对我的[专业选择/职业方向/价值观/人生目标]感到有承诺。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 14 | pre | pre Q6 row 6 | pre_umics_in_depth_exploration_01 | 我经常思考我的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 15 | pre | pre Q6 row 7 | pre_umics_in_depth_exploration_02 | 我试图去发现关于我的[专业选择/职业方向/价值观/人生目标]的新事物。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 16 | pre | pre Q6 row 8 | pre_umics_in_depth_exploration_03 | 我经常反思我的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 17 | pre | pre Q6 row 9 | pre_umics_in_depth_exploration_04 | 我经常和其他人谈论我的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 18 | pre | pre Q6 row 10 | pre_umics_in_depth_exploration_05 | 我试图尽可能多地了解我的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 19 | pre | pre Q6 row 11 | pre_umics_reconsideration_of_commitment_01 | 我经常想，试着去寻找一个不同的[专业选择/职业方向/价值观/人生目标]可能会更好。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |
| 20 | pre | pre Q6 row 12 | pre_umics_reconsideration_of_commitment_02 | 我经常想，一个新的[专业选择/职业方向/价值观/人生目标]会让我的生活变得更有趣。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |
| 21 | pre | pre Q6 row 13 | pre_ac_umics_select_5 | 这道题请选择5 | matrix_single_choice | agreement_1_5 | attention_check | umics_attention | false | true | true | pass_if_response_eq_5 |
| 22 | pre | pre Q6 row 14 | pre_umics_reconsideration_of_commitment_03 | 事实上，我正在寻找一个不同的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |
| 23 | pre | pre Q7 row 1 | pre_dids_commitment_making_01 | 我已经决定了我将要遵循的[职业/专业/价值观/人生目标]方向。 | matrix_single_choice | agreement_1_5 | dids | commitment_making | false | true | false | scored |
| 24 | pre | pre Q7 row 2 | pre_dids_commitment_making_02 | 我对未来要做什么有计划。 | matrix_single_choice | agreement_1_5 | dids | commitment_making | false | true | false | scored |
| 25 | pre | pre Q7 row 3 | pre_dids_commitment_making_03 | 我知道我的人生将要遵循哪个方向。 | matrix_single_choice | agreement_1_5 | dids | commitment_making | false | true | false | scored |
| 26 | pre | pre Q7 row 4 | pre_dids_commitment_making_04 | 我对未来要做什么有清晰的构想。 | matrix_single_choice | agreement_1_5 | dids | commitment_making | false | true | false | scored |
| 27 | pre | pre Q7 row 5 | pre_dids_commitment_making_05 | 我已经对我的人生要做什么做出了选择。 | matrix_single_choice | agreement_1_5 | dids | commitment_making | false | true | false | scored |
| 28 | pre | pre Q7 row 6 | pre_dids_exploration_in_breadth_01 | 我主动思考我可能采取的不同[职业/专业/价值观/人生目标]方向。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_breadth | false | true | false | scored |
| 29 | pre | pre Q7 row 7 | pre_dids_exploration_in_breadth_02 | 我思考未来可能做的不同事情。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_breadth | false | true | false | scored |
| 30 | pre | pre Q7 row 8 | pre_dids_exploration_in_breadth_03 | 我正在考虑多种不同的[职业/专业/价值观/人生目标]生活方式。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_breadth | false | true | false | scored |
| 31 | pre | pre Q7 row 9 | pre_dids_exploration_in_breadth_04 | 我思考我可能追求的不同目标。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_breadth | false | true | false | scored |
| 32 | pre | pre Q7 row 10 | pre_dids_exploration_in_breadth_05 | 我正在思考可能适合我的不同[职业/专业/价值观/人生目标]生活方式。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_breadth | false | true | false | scored |
| 33 | pre | pre Q7 row 11 | pre_dids_ruminative_exploration_01 | 我对我人生中真正想实现的目标感到怀疑。 | matrix_single_choice | agreement_1_5 | dids | ruminative_exploration | false | true | false | scored |
| 34 | pre | pre Q7 row 12 | pre_dids_ruminative_exploration_02 | 我担心我的未来到底想做什么。 | matrix_single_choice | agreement_1_5 | dids | ruminative_exploration | false | true | false | scored |
| 35 | pre | pre Q7 row 13 | pre_dids_ruminative_exploration_03 | 我一直在寻找我人生想要走的方向。 | matrix_single_choice | agreement_1_5 | dids | ruminative_exploration | false | true | false | scored |
| 36 | pre | pre Q7 row 14 | pre_dids_ruminative_exploration_04 | 我一直琢磨我的人生必须走哪个方向。 | matrix_single_choice | agreement_1_5 | dids | ruminative_exploration | false | true | false | scored |
| 37 | pre | pre Q7 row 15 | pre_dids_ruminative_exploration_05 | 我很难停止思考我人生的方向。 | matrix_single_choice | agreement_1_5 | dids | ruminative_exploration | false | true | false | scored |
| 38 | pre | pre Q7 row 16 | pre_dids_identification_with_commitment_01 | 我未来的计划与我真正的[职业/专业/价值观/人生目标]兴趣相匹配 | matrix_single_choice | agreement_1_5 | dids | identification_with_commitment | false | true | false | scored |
| 39 | pre | pre Q7 row 17 | pre_dids_identification_with_commitment_02 | 我未来的计划让我感到自信。 | matrix_single_choice | agreement_1_5 | dids | identification_with_commitment | false | true | false | scored |
| 40 | pre | pre Q7 row 18 | pre_dids_identification_with_commitment_03 | 因为有未来的计划，我对自己感到确定。 | matrix_single_choice | agreement_1_5 | dids | identification_with_commitment | false | true | false | scored |
| 41 | pre | pre Q7 row 19 | pre_dids_identification_with_commitment_04 | 我感觉到我人生想要走的[职业/专业/价值观/人生目标]方向。 | matrix_single_choice | agreement_1_5 | dids | identification_with_commitment | false | true | false | scored |
| 42 | pre | pre Q7 row 20 | pre_dids_identification_with_commitment_05 | 我确信我未来的[职业/专业/价值观/人生目标]计划是正确的。 | matrix_single_choice | agreement_1_5 | dids | identification_with_commitment | false | true | false | scored |
| 43 | pre | pre Q7 row 21 | pre_dids_exploration_in_depth_01 | 我会思考我已经制定的未来计划。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_depth | false | true | false | scored |
| 44 | pre | pre Q7 row 22 | pre_dids_exploration_in_depth_02 | 我会和其他人谈论我未来的计划。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_depth | false | true | false | scored |
| 45 | pre | pre Q7 row 23 | pre_dids_exploration_in_depth_03 | 我会思考我已有的生活目标是否与我的[职业/专业/价值观/人生目标]相匹配。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_depth | false | true | false | scored |
| 46 | pre | pre Q7 row 24 | pre_dids_exploration_in_depth_04 | 我试图了解其他人对我具体的[职业/专业/价值观/人生目标]的看法。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_depth | false | true | false | scored |
| 47 | pre | pre Q7 row 25 | pre_dids_exploration_in_depth_05 | 我会思考我未来的计划是否与我的[职业/专业/价值观/人生目标]相匹配。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_depth | false | true | false | scored |

## Post-survey item map

| order | phase | source | item_key | item_text | type | scale | instrument | dimension | reverse | required | attention | scoring/pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | post | post Q3 | post_identity_distress_01 | 我会因为未来发展方向不清楚而感到困扰。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 2 | post | post Q4 (corrected from source duplicate) | post_identity_distress_02 | 我会因为专业、升学或职业选择拿不准而感到困扰。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 3 | post | post Q5 | post_identity_distress_03 | 我会因为还没有想清楚自己真正认同的价值观或信念而感到困扰。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 4 | post | post Q6 | post_identity_distress_04 | 我会因为还没有想清楚自己属于什么样的人或群体而感到困扰。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 5 | post | post Q7 | post_identity_distress_05 | 总体来说，这些与自我认同和未来方向有关的问题让我感到困扰。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 6 | post | post Q8 | post_identity_distress_06 | 这些与身份有关的不确定感已经影响了我的日常生活和情绪状态。 | single_choice | identity_distress_1_5 | identity_distress | total | false | true | false | scored |
| 7 | post | post Q9 | post_perceived_ai_competence_01 | 这个 AI 给出的建议对我是有帮助的。 | single_choice | agreement_1_7 | perceived_ai_competence | total | false | true | false | scored |
| 8 | post | post Q10 | post_perceived_ai_competence_02 | 这个 AI 提供的信息是可信的。 | single_choice | agreement_1_7 | perceived_ai_competence | total | false | true | false | scored |
| 9 | post | post Q11 | post_perceived_ai_competence_03 | 这个 AI 给出的内容基本准确。 | single_choice | agreement_1_7 | perceived_ai_competence | total | false | true | false | scored |
| 10 | post | post Q12 | post_perceived_ai_competence_04 | 这个 AI 对这些问题是比较了解的。 | single_choice | agreement_1_7 | perceived_ai_competence | total | false | true | false | scored |
| 11 | post | post Q13 row 1 | post_ai_anthropomorphism_01 | 左：这个 AI 更像一个工具 / 右：这个 AI 更像是在和我交流 | matrix_semantic_differential | semantic_differential_1_5 | ai_anthropomorphism | tool_vs_communication | false | true | false | scored |
| 12 | post | post Q13 row 2 | post_ai_anthropomorphism_02 | 左：这个 AI 的表达比较生硬 / 右：这个 AI 的表达比较自然 | matrix_semantic_differential | semantic_differential_1_5 | ai_anthropomorphism | stiff_vs_natural | false | true | false | scored |
| 13 | post | post Q13 row 3 | post_ai_anthropomorphism_03 | 左：这个 AI 更像是在输出答案 / 右：这个 AI 更像是在回应我 | matrix_semantic_differential | semantic_differential_1_5 | ai_anthropomorphism | answering_vs_responding | false | true | false | scored |
| 14 | post | post Q13 row 4 | post_ai_anthropomorphism_04 | 左：这个 AI 更像一个程序 / 右：这个 AI 更像可以和我交流 | matrix_semantic_differential | semantic_differential_1_5 | ai_anthropomorphism | program_vs_conversational | false | true | false | scored |
| 15 | post | post Q13 row 5 | post_ai_anthropomorphism_05 | 左：这个 AI 几乎没有互动感 / 右：这个 AI 有明显的互动感 | matrix_semantic_differential | semantic_differential_1_5 | ai_anthropomorphism | low_interaction_vs_interactive | false | true | false | scored |
| 16 | post | post Q14 | post_bpnsfs_autonomy_satisfaction_01 | 在刚才这次对话中，我觉得自己可以按照自己的想法去思考和自己未来有关的内容。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | false | true | false | scored |
| 17 | post | post Q15 | post_bpnsfs_autonomy_satisfaction_02 | 在这次对话中，我觉得自己是在从自己的立场出发看待这些问题。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | false | true | false | scored |
| 18 | post | post Q16 (accepted source duplicate) | post_bpnsfs_autonomy_satisfaction_03 | 在这次对话中，我觉得自己是在从自己的立场出发看待这些问题。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | false | true | false | scored |
| 19 | post | post Q17 | post_bpnsfs_autonomy_satisfaction_04 | 这次对话让我觉得，关于自己未来方向的思考是由我自己主导的。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | false | true | false | scored |
| 20 | post | post Q18 | post_bpnsfs_autonomy_satisfaction_05 | 在这次对话中，我觉得自己可以比较自由地表达对这些问题的真实想法。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | autonomy_satisfaction | false | true | false | scored |
| 21 | post | post Q19 | post_bpnsfs_relatedness_satisfaction_01 | 在这次对话中，我觉得自己的想法被认真对待了。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | relatedness_satisfaction | false | true | false | scored |
| 22 | post | post Q20 | post_bpnsfs_relatedness_satisfaction_02 | 在这次对话中，我感到自己是被理解的。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | relatedness_satisfaction | false | true | false | scored |
| 23 | post | post Q21 | post_bpnsfs_relatedness_satisfaction_03 | 这次对话让我觉得自己可以把这些困惑说出来，而不是被评判。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | relatedness_satisfaction | false | true | false | scored |
| 24 | post | post Q22 | post_bpnsfs_relatedness_satisfaction_04 | 与通用大模型对话时，我感受到一种支持性的、较为温和的交流氛围。 | single_choice | bpnsfs_agreement_1_5 | bpnsfs_adapted_dialogue_experience | relatedness_satisfaction | false | true | false | scored |
| 25 | post | post Q23 row 1 | post_umics_commitment_01 | 我的[专业选择/职业方向/价值观/人生目标]让我对生活有确定感。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 26 | post | post Q23 row 2 | post_umics_commitment_02 | 我的[专业选择/职业方向/价值观/人生目标]很适合我。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 27 | post | post Q23 row 3 | post_umics_commitment_03 | 我觉得我的[专业选择/职业方向/价值观/人生目标]很有吸引力。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 28 | post | post Q23 row 4 | post_umics_commitment_04 | 我认同我的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 29 | post | post Q23 row 5 | post_umics_commitment_05 | 我对我的[专业选择/职业方向/价值观/人生目标]感到有承诺。 | matrix_single_choice | agreement_1_5 | umics | commitment | false | true | false | scored |
| 30 | post | post Q23 row 6 | post_umics_in_depth_exploration_01 | 我经常思考我的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 31 | post | post Q23 row 7 | post_umics_in_depth_exploration_02 | 我试图去发现关于我的[专业选择/职业方向/价值观/人生目标]的新事物。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 32 | post | post Q23 row 8 | post_umics_in_depth_exploration_03 | 我经常反思我的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 33 | post | post Q23 row 9 | post_umics_in_depth_exploration_04 | 我经常和其他人谈论我的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 34 | post | post Q23 row 10 | post_umics_in_depth_exploration_05 | 我试图尽可能多地了解我的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | in_depth_exploration | false | true | false | scored |
| 35 | post | post Q23 row 11 | post_umics_reconsideration_of_commitment_01 | 我经常想，试着去寻找一个不同的[专业选择/职业方向/价值观/人生目标]可能会更好。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |
| 36 | post | post Q23 row 12 | post_umics_reconsideration_of_commitment_02 | 我经常想，一个新的[专业选择/职业方向/价值观/人生目标]会让我的生活变得更有趣。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |
| 37 | post | post Q23 row 13 | post_umics_reconsideration_of_commitment_03 | 事实上，我正在寻找一个不同的[专业选择/职业方向/价值观/人生目标]。 | matrix_single_choice | agreement_1_5 | umics | reconsideration_of_commitment | false | true | false | scored |
| 38 | post | post Q24 row 1 | post_dids_commitment_making_01 | 我已经决定了我将要遵循的[职业/专业/价值观/人生目标]方向。 | matrix_single_choice | agreement_1_5 | dids | commitment_making | false | true | false | scored |
| 39 | post | post Q24 row 2 | post_dids_commitment_making_02 | 我对未来要做什么有计划。 | matrix_single_choice | agreement_1_5 | dids | commitment_making | false | true | false | scored |
| 40 | post | post Q24 row 3 | post_dids_commitment_making_03 | 我知道我的人生将要遵循哪个方向。 | matrix_single_choice | agreement_1_5 | dids | commitment_making | false | true | false | scored |
| 41 | post | post Q24 row 4 | post_dids_commitment_making_04 | 我对未来要做什么有清晰的构想。 | matrix_single_choice | agreement_1_5 | dids | commitment_making | false | true | false | scored |
| 42 | post | post Q24 row 5 | post_dids_commitment_making_05 | 我已经对我的人生要做什么做出了选择。 | matrix_single_choice | agreement_1_5 | dids | commitment_making | false | true | false | scored |
| 43 | post | post Q24 row 6 | post_dids_exploration_in_breadth_01 | 我主动思考我可能采取的不同[职业/专业/价值观/人生目标]方向。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_breadth | false | true | false | scored |
| 44 | post | post Q24 row 7 | post_dids_exploration_in_breadth_02 | 我思考未来可能做的不同事情。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_breadth | false | true | false | scored |
| 45 | post | post Q24 row 8 | post_dids_exploration_in_breadth_03 | 我正在考虑多种不同的[职业/专业/价值观/人生目标]生活方式。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_breadth | false | true | false | scored |
| 46 | post | post Q24 row 9 | post_dids_exploration_in_breadth_04 | 我思考我可能追求的不同目标。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_breadth | false | true | false | scored |
| 47 | post | post Q24 row 10 | post_dids_exploration_in_breadth_05 | 我正在思考可能适合我的不同[职业/专业/价值观/人生目标]生活方式。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_breadth | false | true | false | scored |
| 48 | post | post Q24 row 11 | post_dids_ruminative_exploration_01 | 我对我人生中真正想实现的目标感到怀疑。 | matrix_single_choice | agreement_1_5 | dids | ruminative_exploration | false | true | false | scored |
| 49 | post | post Q24 row 12 | post_dids_ruminative_exploration_02 | 我担心我的未来到底想做什么。 | matrix_single_choice | agreement_1_5 | dids | ruminative_exploration | false | true | false | scored |
| 50 | post | post Q24 row 13 | post_dids_ruminative_exploration_03 | 我一直在寻找我人生想要走的方向。 | matrix_single_choice | agreement_1_5 | dids | ruminative_exploration | false | true | false | scored |
| 51 | post | post Q24 row 14 | post_dids_ruminative_exploration_04 | 我一直琢磨我的人生必须走哪个方向。 | matrix_single_choice | agreement_1_5 | dids | ruminative_exploration | false | true | false | scored |
| 52 | post | post Q24 row 15 | post_dids_ruminative_exploration_05 | 我很难停止思考我人生的方向。 | matrix_single_choice | agreement_1_5 | dids | ruminative_exploration | false | true | false | scored |
| 53 | post | post Q24 row 16 | post_dids_identification_with_commitment_01 | 我未来的计划与我真正的[职业/专业/价值观/人生目标]兴趣相匹配 | matrix_single_choice | agreement_1_5 | dids | identification_with_commitment | false | true | false | scored |
| 54 | post | post Q24 row 17 | post_dids_identification_with_commitment_02 | 我未来的计划让我感到自信。 | matrix_single_choice | agreement_1_5 | dids | identification_with_commitment | false | true | false | scored |
| 55 | post | post Q24 row 18 | post_dids_identification_with_commitment_03 | 因为有未来的计划，我对自己感到确定。 | matrix_single_choice | agreement_1_5 | dids | identification_with_commitment | false | true | false | scored |
| 56 | post | post Q24 row 19 | post_dids_identification_with_commitment_04 | 我感觉到我人生想要走的[职业/专业/价值观/人生目标]方向。 | matrix_single_choice | agreement_1_5 | dids | identification_with_commitment | false | true | false | scored |
| 57 | post | post Q24 row 20 | post_dids_identification_with_commitment_05 | 我确信我未来的[职业/专业/价值观/人生目标]计划是正确的。 | matrix_single_choice | agreement_1_5 | dids | identification_with_commitment | false | true | false | scored |
| 58 | post | post Q24 row 21 | post_dids_exploration_in_depth_01 | 我会思考我已经制定的未来计划。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_depth | false | true | false | scored |
| 59 | post | post Q24 row 22 | post_dids_exploration_in_depth_02 | 我会和其他人谈论我未来的计划。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_depth | false | true | false | scored |
| 60 | post | post Q24 row 23 | post_dids_exploration_in_depth_03 | 我会思考我已有的生活目标是否与我的[职业/专业/价值观/人生目标]相匹配。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_depth | false | true | false | scored |
| 61 | post | post Q24 row 24 | post_ac_dids_select_1 | 这道题请选择1 | matrix_single_choice | agreement_1_5 | attention_check | dids_attention | false | true | true | pass_if_response_eq_1 |
| 62 | post | post Q24 row 25 | post_dids_exploration_in_depth_04 | 我试图了解其他人对我具体的[职业/专业/价值观/人生目标]的看法。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_depth | false | true | false | scored |
| 63 | post | post Q24 row 26 | post_dids_exploration_in_depth_05 | 我会思考我未来的计划是否与我的[职业/专业/价值观/人生目标]相匹配。 | matrix_single_choice | agreement_1_5 | dids | exploration_in_depth | false | true | false | scored |

## Implementation object shape

Each row above can be represented as a structured item definition with at least:

```json
{
  "questionnaire_version": "mentor_echo_questionnaire_v2026_05_14_hitl_map",
  "phase": "pre | post",
  "order": 1,
  "item_key": "pre_identity_distress_01",
  "item_text": "我会因为未来发展方向不清楚而感到困扰。",
  "item_type": "single_choice | matrix_single_choice | matrix_semantic_differential",
  "scale": "identity_distress_1_5",
  "scale_min": 1,
  "scale_max": 5,
  "scale_labels": {"1": "完全没有", "5": "非常严重"},
  "instrument": "identity_distress",
  "dimension": "total",
  "reverse_scored": false,
  "attention_check": false,
  "attention_check_expected_value": null,
  "required": true
}
```

For categorical demographics, store normalized option codes but preserve participant-facing Chinese option labels in the config. Do not represent participant name as an item definition.

## Export alignment

- `questionnaire_responses.csv` should include one row per stored response item above, plus `participant_code`, `experiment_session_id`, `phase`, `questionnaire_version`, `instrument`, `dimension`, `response_value`, `response_text`, and `submitted_at`.
- `questionnaire_scores.csv` should include every scoring profile above, `valid_items`, `missing_items`, and phase-level attention-check pass fields.
- `analysis_dataset.csv` score columns should follow `{instrument}_{dimension}_pre`, `{instrument}_{dimension}_post`, `{instrument}_{dimension}_change` for pre/post instruments, and `{instrument}_{dimension}_post` for post-only instruments.
- Routine analysis exports must not include participant names because names are not stored by the platform.

## Readiness checklist

| Check | Evidence | Notes |
|---|---|---|
| Pre stored response items | 47 | 2 demographics + 6 identity distress + 13 U-MICS scored + 1 pre attention check + 25 DIDS scored. |
| Post stored response items | 63 | 6 identity distress + 4 perceived AI competence + 5 anthropomorphism + 9 BPNSFS + 13 U-MICS + 25 DIDS scored + 1 post attention check. |
| Attention checks | 2 | `pre_ac_umics_select_5` pass iff response=5; `post_ac_dids_select_1` pass iff response=1. |
| Reverse-scored items | 0 | Every item row has `reverse_scored=false`; no source row requires reverse coding in this implementation map. |
| Name fields stored | 0 | Source name fields are omitted from rendering/storage by participant-code-only privacy rule. |
| Known ambiguities | 0 unresolved | Every known source issue above is resolved or explicitly accepted for this version; no AFK implementation guess is required. |
