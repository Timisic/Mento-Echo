from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

QUESTIONNAIRE_VERSION = "mentor_echo_questionnaire_v2026_05_14_hitl_map"

Phase = Literal["pre", "post"]


@dataclass(frozen=True)
class ScaleProfile:
    key: str
    value_type: Literal["integer", "categorical"]
    min_value: int | None = None
    max_value: int | None = None
    labels: dict[str, str] | None = None
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuestionnaireItem:
    phase: Phase
    order: int
    item_key: str
    item_text: str
    item_type: str
    scale: str
    instrument: str
    dimension: str
    reverse_scored: bool = False
    required: bool = True
    attention_check: bool = False
    attention_check_expected_value: int | None = None
    score_dimension: str | None = None


@dataclass(frozen=True)
class ScoreRule:
    phase: Phase
    instrument: str
    dimension: str
    item_keys: tuple[str, ...]


SCALE_PROFILES: dict[str, ScaleProfile] = {
    "gender_options": ScaleProfile(
        key="gender_options", value_type="categorical", options=("男", "女")
    ),
    "grade_options": ScaleProfile(
        key="grade_options",
        value_type="categorical",
        options=("大一", "大二", "大三", "大四", "硕士研究生", "博士研究生"),
    ),
    "identity_distress_1_5": ScaleProfile(
        key="identity_distress_1_5",
        value_type="integer",
        min_value=1,
        max_value=5,
        labels={"1": "完全没有", "2": "比较轻", "3": "中等", "4": "比较严重", "5": "非常严重"},
    ),
    "agreement_1_5": ScaleProfile(
        key="agreement_1_5",
        value_type="integer",
        min_value=1,
        max_value=5,
        labels={"1": "完全不符合", "5": "完全符合"},
    ),
    "bpnsfs_agreement_1_5": ScaleProfile(
        key="bpnsfs_agreement_1_5",
        value_type="integer",
        min_value=1,
        max_value=5,
        labels={"1": "完全不符合", "2": "比较不符合", "3": "不确定", "4": "比较符合", "5": "完全符合"},
    ),
    "agreement_1_7": ScaleProfile(
        key="agreement_1_7",
        value_type="integer",
        min_value=1,
        max_value=7,
        labels={"1": "非常不同意", "7": "非常同意"},
    ),
    "semantic_differential_1_5": ScaleProfile(
        key="semantic_differential_1_5",
        value_type="integer",
        min_value=1,
        max_value=5,
        labels={
            "1": "非常接近左侧",
            "2": "比较接近左侧",
            "3": "两者差不多",
            "4": "比较接近右侧",
            "5": "非常接近右侧",
        },
    ),
}

identity_distress_texts = [
    "我会因为未来发展方向不清楚而感到困扰。",
    "我会因为专业、升学或职业选择拿不准而感到困扰。",
    "我会因为还没有想清楚自己真正认同的价值观或信念而感到困扰。",
    "我会因为还没有想清楚自己属于什么样的人或群体而感到困扰。",
    "总体来说，这些与自我认同和未来方向有关的问题让我感到困扰。",
    "这些与身份有关的不确定感已经影响了我的日常生活和情绪状态。",
]

umics = [
    ("commitment", "01", "我的[专业选择/职业方向/价值观/人生目标]让我对生活有确定感。"),
    ("commitment", "02", "我的[专业选择/职业方向/价值观/人生目标]很适合我。"),
    ("commitment", "03", "我觉得我的[专业选择/职业方向/价值观/人生目标]很有吸引力。"),
    ("commitment", "04", "我认同我的[专业选择/职业方向/价值观/人生目标]。"),
    ("commitment", "05", "我对我的[专业选择/职业方向/价值观/人生目标]感到有承诺。"),
    ("in_depth_exploration", "01", "我经常思考我的[专业选择/职业方向/价值观/人生目标]。"),
    ("in_depth_exploration", "02", "我试图去发现关于我的[专业选择/职业方向/价值观/人生目标]的新事物。"),
    ("in_depth_exploration", "03", "我经常反思我的[专业选择/职业方向/价值观/人生目标]。"),
    ("in_depth_exploration", "04", "我经常和其他人谈论我的[专业选择/职业方向/价值观/人生目标]。"),
    ("in_depth_exploration", "05", "我试图尽可能多地了解我的[专业选择/职业方向/价值观/人生目标]。"),
    ("reconsideration_of_commitment", "01", "我经常想，试着去寻找一个不同的[专业选择/职业方向/价值观/人生目标]可能会更好。"),
    ("reconsideration_of_commitment", "02", "我经常想，一个新的[专业选择/职业方向/价值观/人生目标]会让我的生活变得更有趣。"),
    ("reconsideration_of_commitment", "03", "事实上，我正在寻找一个不同的[专业选择/职业方向/价值观/人生目标]。"),
]

dids = [
    ("commitment_making", "01", "我已经决定了我将要遵循的[职业/专业/价值观/人生目标]方向。"),
    ("commitment_making", "02", "我对未来要做什么有计划。"),
    ("commitment_making", "03", "我知道我的人生将要遵循哪个方向。"),
    ("commitment_making", "04", "我对未来要做什么有清晰的构想。"),
    ("commitment_making", "05", "我已经对我的人生要做什么做出了选择。"),
    ("exploration_in_breadth", "01", "我主动思考我可能采取的不同[职业/专业/价值观/人生目标]方向。"),
    ("exploration_in_breadth", "02", "我思考未来可能做的不同事情。"),
    ("exploration_in_breadth", "03", "我正在考虑多种不同的[职业/专业/价值观/人生目标]生活方式。"),
    ("exploration_in_breadth", "04", "我思考我可能追求的不同目标。"),
    ("exploration_in_breadth", "05", "我正在思考可能适合我的不同[职业/专业/价值观/人生目标]生活方式。"),
    ("ruminative_exploration", "01", "我对我人生中真正想实现的目标感到怀疑。"),
    ("ruminative_exploration", "02", "我担心我的未来到底想做什么。"),
    ("ruminative_exploration", "03", "我一直在寻找我人生想要走的方向。"),
    ("ruminative_exploration", "04", "我一直琢磨我的人生必须走哪个方向。"),
    ("ruminative_exploration", "05", "我很难停止思考我人生的方向。"),
    ("identification_with_commitment", "01", "我未来的计划与我真正的[职业/专业/价值观/人生目标]兴趣相匹配"),
    ("identification_with_commitment", "02", "我未来的计划让我感到自信。"),
    ("identification_with_commitment", "03", "因为有未来的计划，我对自己感到确定。"),
    ("identification_with_commitment", "04", "我感觉到我人生想要走的[职业/专业/价值观/人生目标]方向。"),
    ("identification_with_commitment", "05", "我确信我未来的[职业/专业/价值观/人生目标]计划是正确的。"),
    ("exploration_in_depth", "01", "我会思考我已经制定的未来计划。"),
    ("exploration_in_depth", "02", "我会和其他人谈论我未来的计划。"),
    ("exploration_in_depth", "03", "我会思考我已有的生活目标是否与我的[职业/专业/价值观/人生目标]相匹配。"),
    ("exploration_in_depth", "04", "我试图了解其他人对我具体的[职业/专业/价值观/人生目标]的看法。"),
    ("exploration_in_depth", "05", "我会思考我未来的计划是否与我的[职业/专业/价值观/人生目标]相匹配。"),
]


def build_items() -> tuple[QuestionnaireItem, ...]:
    items: list[QuestionnaireItem] = []

    def add(
        phase: Phase,
        key: str,
        text: str,
        item_type: str,
        scale: str,
        instrument: str,
        dimension: str,
        *,
        attention_check: bool = False,
        expected: int | None = None,
    ) -> None:
        phase_items = [item for item in items if item.phase == phase]
        items.append(
            QuestionnaireItem(
                phase=phase,
                order=len(phase_items) + 1,
                item_key=key,
                item_text=text,
                item_type=item_type,
                scale=scale,
                instrument=instrument,
                dimension=dimension,
                attention_check=attention_check,
                attention_check_expected_value=expected,
            )
        )

    add("pre", "pre_demo_gender", "您的性别", "single_choice", "gender_options", "demographics", "gender")
    add("pre", "pre_demo_grade", "您目前在读：", "single_choice", "grade_options", "demographics", "grade")
    for i, text in enumerate(identity_distress_texts, 1):
        add("pre", f"pre_identity_distress_{i:02d}", text, "matrix_single_choice", "identity_distress_1_5", "identity_distress", "total")
    for idx, (dimension, n, text) in enumerate(umics, 1):
        if idx == 13:
            add("pre", "pre_ac_umics_select_5", "这道题请选择5", "matrix_single_choice", "agreement_1_5", "attention_check", "umics_attention", attention_check=True, expected=5)
        add("pre", f"pre_umics_{dimension}_{n}", text, "matrix_single_choice", "agreement_1_5", "umics", dimension)
    for dimension, n, text in dids:
        add("pre", f"pre_dids_{dimension}_{n}", text, "matrix_single_choice", "agreement_1_5", "dids", dimension)

    for i, text in enumerate(identity_distress_texts, 1):
        add("post", f"post_identity_distress_{i:02d}", text, "single_choice", "identity_distress_1_5", "identity_distress", "total")
    for i, text in enumerate(
        [
            "这个 AI 给出的建议对我是有帮助的。",
            "这个 AI 提供的信息是可信的。",
            "这个 AI 给出的内容基本准确。",
            "这个 AI 对这些问题是比较了解的。",
        ],
        1,
    ):
        add("post", f"post_perceived_ai_competence_{i:02d}", text, "single_choice", "agreement_1_7", "perceived_ai_competence", "total")
    for i, (dimension, text) in enumerate(
        [
            ("tool_vs_communication", "左：这个 AI 更像一个工具 / 右：这个 AI 更像是在和我交流"),
            ("stiff_vs_natural", "左：这个 AI 的表达比较生硬 / 右：这个 AI 的表达比较自然"),
            ("answering_vs_responding", "左：这个 AI 更像是在输出答案 / 右：这个 AI 更像是在回应我"),
            ("program_vs_conversational", "左：这个 AI 更像一个程序 / 右：这个 AI 更像可以和我交流"),
            ("low_interaction_vs_interactive", "左：这个 AI 几乎没有互动感 / 右：这个 AI 有明显的互动感"),
        ],
        1,
    ):
        add("post", f"post_ai_anthropomorphism_{i:02d}", text, "matrix_semantic_differential", "semantic_differential_1_5", "ai_anthropomorphism", dimension)
    for dimension, n, text in [
        ("autonomy_satisfaction", "01", "在刚才这次对话中，我觉得自己可以按照自己的想法去思考和自己未来有关的内容。"),
        ("autonomy_satisfaction", "02", "在这次对话中，我觉得自己是在从自己的立场出发看待这些问题。"),
        ("autonomy_satisfaction", "03", "在这次对话中，我觉得自己是在从自己的立场出发看待这些问题。"),
        ("autonomy_satisfaction", "04", "这次对话让我觉得，关于自己未来方向的思考是由我自己主导的。"),
        ("autonomy_satisfaction", "05", "在这次对话中，我觉得自己可以比较自由地表达对这些问题的真实想法。"),
        ("relatedness_satisfaction", "01", "在这次对话中，我觉得自己的想法被认真对待了。"),
        ("relatedness_satisfaction", "02", "在这次对话中，我感到自己是被理解的。"),
        ("relatedness_satisfaction", "03", "这次对话让我觉得自己可以把这些困惑说出来，而不是被评判。"),
        ("relatedness_satisfaction", "04", "与通用大模型对话时，我感受到一种支持性的、较为温和的交流氛围。"),
    ]:
        add("post", f"post_bpnsfs_{dimension}_{n}", text, "single_choice", "bpnsfs_agreement_1_5", "bpnsfs_adapted_dialogue_experience", dimension)
    for dimension, n, text in umics:
        add("post", f"post_umics_{dimension}_{n}", text, "matrix_single_choice", "agreement_1_5", "umics", dimension)
    for idx, (dimension, n, text) in enumerate(dids, 1):
        if idx == 24:
            add("post", "post_ac_dids_select_1", "这道题请选择1", "matrix_single_choice", "agreement_1_5", "attention_check", "dids_attention", attention_check=True, expected=1)
        add("post", f"post_dids_{dimension}_{n}", text, "matrix_single_choice", "agreement_1_5", "dids", dimension)
    return tuple(items)


QUESTIONNAIRE_ITEMS = build_items()
ITEMS_BY_KEY = {item.item_key: item for item in QUESTIONNAIRE_ITEMS}
ITEMS_BY_PHASE: dict[Phase, tuple[QuestionnaireItem, ...]] = {
    "pre": tuple(item for item in QUESTIONNAIRE_ITEMS if item.phase == "pre"),
    "post": tuple(item for item in QUESTIONNAIRE_ITEMS if item.phase == "post"),
}


def get_items(phase: Phase) -> tuple[QuestionnaireItem, ...]:
    return ITEMS_BY_PHASE[phase]


def score_rules_for_phase(phase: Phase) -> tuple[ScoreRule, ...]:
    items = get_items(phase)
    rules: list[ScoreRule] = []
    grouped: dict[tuple[str, str], list[str]] = {}
    for item in items:
        if item.instrument in {"demographics", "attention_check"} or item.attention_check:
            continue
        grouped.setdefault((item.instrument, item.dimension), []).append(item.item_key)
    for (instrument, dimension), keys in grouped.items():
        rules.append(ScoreRule(phase=phase, instrument=instrument, dimension=dimension, item_keys=tuple(keys)))
    if phase == "post":
        bpnsfs_keys = tuple(
            item.item_key
            for item in items
            if item.instrument == "bpnsfs_adapted_dialogue_experience"
        )
        rules.append(
            ScoreRule(
                phase="post",
                instrument="bpnsfs_adapted_dialogue_experience",
                dimension="need_satisfaction_total",
                item_keys=bpnsfs_keys,
            )
        )
    return tuple(rules)
