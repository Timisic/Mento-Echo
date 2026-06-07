from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import ChatMessage, ExperimentSession, Participant, QuestionnaireResponse, QuestionnaireScore


DEFAULT_CUTOFF_UTC = datetime(2026, 6, 3, 15, 0, 0, tzinfo=UTC)

TOPIC_KEYWORDS = {
    "专业",
    "方向",
    "未来",
    "就业",
    "升学",
    "读研",
    "考研",
    "保研",
    "工作",
    "职业",
    "行业",
    "毕业",
    "实习",
    "课程",
    "本科",
    "转专业",
    "选择",
    "适合",
    "兴趣",
    "喜欢",
    "迷茫",
    "困惑",
    "焦虑",
    "价值观",
    "人生",
    "规划",
}

OFF_TOPIC_KEYWORDS = {
    "天气",
    "游戏",
    "写代码",
    "代码",
    "小说",
    "电影",
    "八卦",
    "股票",
    "彩票",
    "翻译",
}

NON_SUBSTANTIVE_REPLIES = {
    "嗯",
    "嗯嗯",
    "好",
    "好的",
    "行",
    "可以",
    "不知道",
    "没有",
    "谢谢",
    "谢谢你",
    "ok",
    "OK",
    "hi",
    "hello",
    "你好",
    "是",
    "不是",
    "对",
    "不对",
}

CORE_SCORE_ORDER = (
    ("pre", "identity_distress", "total"),
    ("post", "identity_distress", "total"),
    ("pre", "umics", "commitment"),
    ("post", "umics", "commitment"),
    ("pre", "umics", "in_depth_exploration"),
    ("post", "umics", "in_depth_exploration"),
    ("pre", "umics", "reconsideration_of_commitment"),
    ("post", "umics", "reconsideration_of_commitment"),
    ("post", "perceived_ai_competence", "total"),
    ("post", "ai_anthropomorphism", "tool_vs_communication"),
    ("post", "ai_anthropomorphism", "stiff_vs_natural"),
    ("post", "ai_anthropomorphism", "answering_vs_responding"),
    ("post", "ai_anthropomorphism", "program_vs_conversational"),
    ("post", "ai_anthropomorphism", "low_interaction_vs_interactive"),
    ("post", "ai_warmth", "mean"),
    ("post", "ai_warmth", "sum"),
    ("post", "bpnsfs_adapted_dialogue_experience", "autonomy_satisfaction"),
    ("post", "bpnsfs_adapted_dialogue_experience", "competence_satisfaction"),
    ("post", "bpnsfs_adapted_dialogue_experience", "relatedness_satisfaction"),
    ("post", "bpnsfs_adapted_dialogue_experience", "need_satisfaction_total"),
)


@dataclass
class DialogueFeatures:
    participant_message_count: int
    assistant_message_count: int
    participant_char_count: int
    participant_non_initial_char_count: int
    substantive_turn_count: int
    non_substantive_turn_count: int
    topic_keyword_hits: int
    topic_turn_count: int
    off_topic_keyword_hits: int
    assistant_error_count: int
    fallback_count: int
    last_role: str
    providers: str
    models: str
    prompt_modes: str
    auto_dialogue_validity: str
    auto_dialogue_reason: str
    manual_review_recommended: bool


def main() -> None:
    parser = argparse.ArgumentParser(description="Export cleaned analysis screening datasets.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--cutoff-utc", default=DEFAULT_CUTOFF_UTC.isoformat())
    parser.add_argument("--min-participant-code", default=None)
    args = parser.parse_args()

    cutoff = datetime.fromisoformat(args.cutoff_utc)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=UTC)
    output_dir = args.output_dir or Path("analysis_exports") / f"cleaning_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    with Session(get_engine()) as db:
        rows = build_screening_rows(db, cutoff=cutoff)
    if args.min_participant_code:
        min_key = participant_code_sort_key(args.min_participant_code)
        rows = [row for row in rows if participant_code_sort_key(str(row["participant_code"])) >= min_key]

    all_path = output_dir / "participant_screening_all.csv"
    valid_path = output_dir / "analysis_ready_scores.csv"
    excluded_path = output_dir / "excluded_participants.csv"
    attention_path = output_dir / "attention_check_failures.csv"
    review_path = output_dir / "conversation_review_recommended.csv"
    long_scores_path = output_dir / "analysis_ready_scores_long.csv"
    completed_excluded_path = output_dir / "completed_excluded_participants.csv"
    valid_completed_scores_path = output_dir / "valid_completed_analysis_scores.csv"
    transcript_path = output_dir / "conversation_review_notes.md"
    readme_path = output_dir / "README.md"

    valid_rows = [row for row in rows if row["analysis_decision"] == "include_main"]
    excluded_rows = [row for row in rows if row["analysis_decision"] != "include_main"]
    attention_rows = [row for row in rows if row["attention_flag"] == "fail"]
    review_rows = [row for row in rows if row["manual_review_recommended"] == "true"]
    write_csv(all_path, strip_private_digest(rows))
    write_csv(valid_path, strip_private_digest(valid_rows))
    write_csv(excluded_path, strip_private_digest(excluded_rows))
    write_csv(attention_path, strip_private_digest(attention_rows))
    write_csv(review_path, strip_private_digest(review_rows))
    write_long_scores(long_scores_path, valid_rows)
    write_csv(completed_excluded_path, completed_excluded_rows(rows))
    write_csv(valid_completed_scores_path, strip_private_digest(valid_rows))
    write_review_notes(transcript_path, rows)
    write_readme(
        readme_path,
        cutoff=cutoff,
        rows=rows,
        valid_rows=valid_rows,
        excluded_rows=excluded_rows,
        attention_rows=attention_rows,
        review_rows=review_rows,
    )

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "cutoff_utc": cutoff.isoformat(),
        "files": {
            path.name: {"rows": count_csv_rows(path) if path.suffix == ".csv" else None}
            for path in [
                all_path,
                valid_path,
                excluded_path,
                attention_path,
                review_path,
                long_scores_path,
                completed_excluded_path,
                valid_completed_scores_path,
                transcript_path,
                readme_path,
            ]
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_dir)


def build_screening_rows(db: Session, *, cutoff: datetime) -> list[dict[str, Any]]:
    participants = db.scalars(select(Participant).order_by(Participant.participant_code)).all()
    sessions = {session.participant_id: session for session in db.scalars(select(ExperimentSession)).all()}
    responses_by_session = group_by(
        db.scalars(select(QuestionnaireResponse).where(QuestionnaireResponse.superseded_at.is_(None))).all(),
        "experiment_session_id",
    )
    scores_by_session = group_by(
        db.scalars(select(QuestionnaireScore).where(QuestionnaireScore.superseded_at.is_(None))).all(),
        "experiment_session_id",
    )
    messages_by_session = group_by(
        db.scalars(select(ChatMessage).order_by(ChatMessage.experiment_session_id, ChatMessage.message_index)).all(),
        "experiment_session_id",
    )

    rows: list[dict[str, Any]] = []
    for participant in participants:
        session = sessions.get(participant.id)
        created_at = participant.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        if created_at < cutoff:
            continue
        session_responses = responses_by_session.get(session.id, []) if session else []
        session_scores = scores_by_session.get(session.id, []) if session else []
        session_messages = messages_by_session.get(session.id, []) if session else []

        demographics = demographic_values(session_responses)
        score_values = score_values_by_key(session_scores)
        attention_flag, attention_value = attention_status(session_scores)
        features = dialogue_features(session_messages)

        exclusion_reasons: list[str] = []
        warnings: list[str] = []
        pre_complete = bool(session and session.pre_survey_submitted_at)
        post_complete = bool(session and session.post_survey_submitted_at)
        completed = bool(session and session.completed_at and session.status == "completed")
        if not session:
            exclusion_reasons.append("no_experiment_session")
        if not pre_complete:
            exclusion_reasons.append("pre_survey_not_completed")
        if not post_complete:
            exclusion_reasons.append("post_survey_not_completed")
        if not completed:
            exclusion_reasons.append("session_not_completed")
        if attention_flag == "fail":
            exclusion_reasons.append("attention_check_failed")
        elif attention_flag == "missing":
            exclusion_reasons.append("attention_check_missing")
        if features.auto_dialogue_validity == "invalid":
            exclusion_reasons.append(f"dialogue_invalid:{features.auto_dialogue_reason}")
        if features.last_role == "participant":
            exclusion_reasons.append("last_participant_message_has_no_assistant_reply")

        age = parse_int(demographics.get("age"))
        if age is not None and (age < 16 or age > 30):
            warnings.append("age_outside_typical_undergraduate_range")
        grade = demographics.get("grade") or ""
        if grade and not grade.startswith("本科"):
            exclusion_reasons.append("grade_not_undergraduate")
        if features.auto_dialogue_validity == "review":
            warnings.append(f"dialogue_needs_review:{features.auto_dialogue_reason}")
        if features.fallback_count:
            warnings.append("ai_fallback_used")
        if features.assistant_error_count:
            warnings.append("assistant_error_message_present")

        decision = "include_main" if not exclusion_reasons else "exclude_hard"
        if decision == "include_main" and warnings:
            decision = "include_with_flags"

        row: dict[str, Any] = {
            "participant_code": participant.participant_code,
            "experiment_session_id": session.id if session else "",
            "participant_created_at_utc": fmt_dt(participant.created_at),
            "session_started_at_utc": fmt_dt(session.started_at) if session else "",
            "group": session.group if session else "",
            "status": session.status if session else "",
            "analysis_decision": decision if decision != "include_with_flags" else "include_main",
            "analysis_flags": ";".join(warnings),
            "exclusion_reasons": ";".join(exclusion_reasons),
            "pre_complete": str(pre_complete).lower(),
            "post_complete": str(post_complete).lower(),
            "completed": str(completed).lower(),
            "attention_flag": attention_flag,
            "pre_attention_check_passed": attention_value,
            "gender": demographics.get("gender", ""),
            "grade": grade,
            "major": demographics.get("major", ""),
            "age": demographics.get("age", ""),
            "participant_turn_count_recorded": session.participant_turn_count if session else "",
            "dialogue_elapsed_seconds_recorded": session.dialogue_elapsed_seconds if session else "",
            "dialogue_elapsed_minutes_recorded": round((session.dialogue_elapsed_seconds if session else 0) / 60, 3),
            "dialogue_finish_decision": session.dialogue_finish_decision if session else "",
            "dialogue_finish_decision_turn_count": session.dialogue_finish_decision_turn_count if session else "",
            "topic_validity_status_db": session.topic_validity_status if session else "",
            "topic_off_track_ratio_db": session.topic_off_track_ratio if session else "",
            "participant_message_count": features.participant_message_count,
            "assistant_message_count": features.assistant_message_count,
            "participant_char_count": features.participant_char_count,
            "participant_non_initial_char_count": features.participant_non_initial_char_count,
            "substantive_turn_count": features.substantive_turn_count,
            "non_substantive_turn_count": features.non_substantive_turn_count,
            "topic_keyword_hits": features.topic_keyword_hits,
            "topic_turn_count": features.topic_turn_count,
            "off_topic_keyword_hits": features.off_topic_keyword_hits,
            "assistant_error_count": features.assistant_error_count,
            "fallback_count": features.fallback_count,
            "last_role": features.last_role,
            "providers": features.providers,
            "models": features.models,
            "prompt_modes": features.prompt_modes,
            "auto_dialogue_validity": features.auto_dialogue_validity,
            "auto_dialogue_reason": features.auto_dialogue_reason,
            "manual_review_recommended": str(features.manual_review_recommended).lower(),
            "participant_message_digest": compact_participant_digest(session_messages),
        }
        row.update(flatten_scores(score_values))
        rows.append(row)
    return rows


def group_by(rows: list[Any], attr: str) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[getattr(row, attr)].append(row)
    return grouped


def participant_code_sort_key(code: str) -> tuple[str, int, str]:
    match = re.match(r"^([A-Za-z]+)(\d+)(?:-(.*))?$", code.strip())
    if not match:
        return (code.strip(), -1, "")
    prefix, number, suffix = match.groups()
    return (prefix.upper(), int(number), suffix or "")


def demographic_values(responses: list[QuestionnaireResponse]) -> dict[str, str]:
    values: dict[str, str] = {}
    mapping = {
        "pre_demo_gender": "gender",
        "pre_demo_grade": "grade",
        "pre_demo_major": "major",
        "pre_demo_age": "age",
    }
    for response in responses:
        key = mapping.get(response.item_key)
        if key:
            values[key] = response.response_text or (str(response.response_value) if response.response_value is not None else "")
    return values


def score_values_by_key(scores: list[QuestionnaireScore]) -> dict[tuple[str, str, str], QuestionnaireScore]:
    return {(score.phase, score.instrument, score.dimension): score for score in scores}


def attention_status(scores: list[QuestionnaireScore]) -> tuple[str, str]:
    for score in scores:
        if score.instrument == "attention_check" and score.phase == "pre":
            passed = score.attention_check_passed
            return ("pass" if passed else "fail", str(passed).lower())
    return "missing", ""


def dialogue_features(messages: list[ChatMessage]) -> DialogueFeatures:
    participant_messages = [m for m in messages if m.role == "participant"]
    assistant_messages = [m for m in messages if m.role == "assistant"]
    user_texts = [m.content.strip() for m in participant_messages]
    non_initial_texts = [
        m.content.strip()
        for m in participant_messages
        if m.effective_turn_excluded_reason != "initial_profile_injection"
    ]
    topic_hits = sum(count_terms(text, TOPIC_KEYWORDS) for text in user_texts)
    topic_turns = sum(1 for text in user_texts if count_terms(text, TOPIC_KEYWORDS) > 0)
    off_topic_hits = sum(count_terms(text, OFF_TOPIC_KEYWORDS) for text in user_texts)
    non_substantive = sum(1 for text in non_initial_texts if is_non_substantive(text))
    substantive = len(non_initial_texts) - non_substantive
    assistant_errors = sum(1 for m in assistant_messages if m.error_code)
    fallback_count = sum(1 for m in assistant_messages if (m.generation_params or {}).get("fallback_triggered"))
    providers = sorted({m.provider_name for m in assistant_messages if m.provider_name})
    models = sorted({m.model_name for m in assistant_messages if m.model_name})
    prompt_modes = sorted({str((m.generation_params or {}).get("prompt_mode", "")) for m in assistant_messages if m.generation_params})
    participant_chars = sum(len(text) for text in user_texts)
    non_initial_chars = sum(len(text) for text in non_initial_texts)
    last_role = messages[-1].role if messages else ""

    validity = "valid"
    reason = "topic_covered_with_substantive_dialogue"
    review = False
    if not participant_messages:
        validity = "invalid"
        reason = "no_participant_messages"
    elif last_role == "participant":
        validity = "invalid"
        reason = "last_message_pending_assistant_reply"
    elif substantive <= 1 and non_initial_chars < 40:
        validity = "invalid"
        reason = "too_little_substantive_participant_content"
    elif topic_turns == 0 and topic_hits == 0:
        validity = "invalid" if off_topic_hits else "review"
        reason = "no_topic_keyword_coverage"
        review = True
    elif non_substantive >= max(4, len(non_initial_texts) // 2 + 1):
        validity = "review"
        reason = "many_non_substantive_turns"
        review = True
    elif non_initial_chars < 100 or topic_turns < 2:
        validity = "review"
        reason = "thin_but_potentially_valid_dialogue"
        review = True
    elif off_topic_hits >= 3 and off_topic_hits >= topic_hits:
        validity = "review"
        reason = "possible_off_topic_dialogue"
        review = True

    return DialogueFeatures(
        participant_message_count=len(participant_messages),
        assistant_message_count=len(assistant_messages),
        participant_char_count=participant_chars,
        participant_non_initial_char_count=non_initial_chars,
        substantive_turn_count=substantive,
        non_substantive_turn_count=non_substantive,
        topic_keyword_hits=topic_hits,
        topic_turn_count=topic_turns,
        off_topic_keyword_hits=off_topic_hits,
        assistant_error_count=assistant_errors,
        fallback_count=fallback_count,
        last_role=last_role,
        providers="|".join(providers),
        models="|".join(models),
        prompt_modes="|".join(prompt_modes),
        auto_dialogue_validity=validity,
        auto_dialogue_reason=reason,
        manual_review_recommended=review,
    )


def count_terms(text: str, terms: set[str]) -> int:
    return sum(text.count(term) for term in terms)


def is_non_substantive(text: str) -> bool:
    clean = re.sub(r"\\s+", "", text)
    clean = clean.strip("。！？!?~～，,；;")
    return clean in NON_SUBSTANTIVE_REPLIES or len(clean) <= 2


def compact_participant_digest(messages: list[ChatMessage]) -> str:
    snippets: list[str] = []
    for message in messages:
        if message.role != "participant":
            continue
        text = re.sub(r"\\s+", " ", message.content.strip())
        if len(text) > 80:
            text = text[:77] + "..."
        snippets.append(f"{message.message_index}:{text}")
    return " || ".join(snippets)


def flatten_scores(scores: dict[tuple[str, str, str], QuestionnaireScore]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for phase, instrument, dimension in CORE_SCORE_ORDER:
        key = f"{phase}_{field_token(instrument)}_{field_token(dimension)}"
        score = scores.get((phase, instrument, dimension))
        flat[key] = score.score if score else ""
        flat[f"{key}_valid_items"] = score.valid_items if score else ""
    change_pairs = [
        ("identity_distress_total", "post_identity_distress_total", "pre_identity_distress_total"),
        ("umics_commitment", "post_umics_commitment", "pre_umics_commitment"),
        ("umics_in_depth_exploration", "post_umics_in_depth_exploration", "pre_umics_in_depth_exploration"),
        ("umics_reconsideration_of_commitment", "post_umics_reconsideration_of_commitment", "pre_umics_reconsideration_of_commitment"),
    ]
    for label, post_key, pre_key in change_pairs:
        post = flat.get(post_key)
        pre = flat.get(pre_key)
        flat[f"change_{label}"] = round(float(post) - float(pre), 6) if post != "" and pre != "" else ""
    return flat


def field_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: scalar(value) for key, value in row.items()})


def strip_private_digest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if key != "participant_message_digest"} for row in rows]


def completed_excluded_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        if row["completed"] != "true" or row["analysis_decision"] == "include_main":
            continue
        raw_reasons = str(row["exclusion_reasons"])
        failed_attention = "attention_check_failed" in raw_reasons
        output.append(
            {
                "participant_code": str(row["participant_code"]),
                "excluded_reason": readable_exclusion_reason(raw_reasons),
                "failed_attention_check_item_key": "pre_ac_umics_select_5" if failed_attention else "",
                "failed_attention_check_item_text": "这道题请选择5" if failed_attention else "",
                "failed_attention_expected_response": "5" if failed_attention else "",
                "raw_exclusion_reasons": raw_reasons,
            }
        )
    return output


def readable_exclusion_reason(raw_reasons: str) -> str:
    reasons: list[str] = []
    if "attention_check_failed" in raw_reasons:
        reasons.append("注意力检测未通过")
    if "dialogue_invalid:too_little_substantive_participant_content" in raw_reasons:
        reasons.append("对话内容过少/明显不认真")
    if "dialogue_invalid:no_topic_keyword_coverage" in raw_reasons:
        reasons.append("对话未覆盖专业选择/未来方向主题")
    if "last_participant_message_has_no_assistant_reply" in raw_reasons:
        reasons.append("最后一条用户消息无 AI 回复")
    return "；".join(reasons) if reasons else raw_reasons


def write_long_scores(path: Path, rows: list[dict[str, Any]]) -> None:
    long_rows: list[dict[str, Any]] = []
    for row in rows:
        for phase, instrument, dimension in CORE_SCORE_ORDER:
            key = f"{phase}_{field_token(instrument)}_{field_token(dimension)}"
            score = row.get(key, "")
            if score == "":
                continue
            long_rows.append(
                {
                    "participant_code": row["participant_code"],
                    "group": row["group"],
                    "phase": phase,
                    "instrument": instrument,
                    "dimension": dimension,
                    "score": score,
                    "valid_items": row.get(f"{key}_valid_items", ""),
                }
            )
    write_csv(path, long_rows)


def write_review_notes(path: Path, rows: list[dict[str, Any]]) -> None:
    review_rows = [row for row in rows if row["manual_review_recommended"] == "true" or row["analysis_decision"] != "include_main"]
    lines = [
        "# Conversation Review Notes",
        "",
        "This file contains compact participant-message digests only, for screening. It is not a full raw-chat export.",
        "",
    ]
    for row in review_rows:
        lines.append(f"## {row['participant_code']}")
        lines.append(f"- decision: {row['analysis_decision']}")
        lines.append(f"- exclusion_reasons: {row['exclusion_reasons']}")
        lines.append(f"- flags: {row['analysis_flags']}")
        lines.append(f"- auto_dialogue: {row['auto_dialogue_validity']} / {row['auto_dialogue_reason']}")
        lines.append(f"- digest: {row['participant_message_digest']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_readme(
    path: Path,
    *,
    cutoff: datetime,
    rows: list[dict[str, Any]],
    valid_rows: list[dict[str, Any]],
    excluded_rows: list[dict[str, Any]],
    attention_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> None:
    text = f"""# Mentor Echo Analysis Cleaning Export

Generated from the local PostgreSQL database with read-only queries.

## Primary Rules

- Formal experiment window: participant creation time >= `{cutoff.isoformat()}` UTC (`2026-06-03 23:00:00+08:00`).
- Main analysis inclusion: pre-survey completed, post-survey completed, session completed, pre attention check passed, no hard dialogue invalidity.
- Current questionnaire has only one attention check: pre-survey U-MICS `这道题请选择5`, expected value `5`.
- Dialogue validity is intentionally broad: exclude only no substantive dialogue, no topic coverage, or pending assistant reply. Thin but plausible conversations and visible assistant-generation error messages are flagged, not removed.
- Undergraduate eligibility is based on current stored grade options. Age outside 16-30 is flagged, not automatically removed.

## Files

- `analysis_ready_scores.csv`: participant-level wide file for analysis. Includes IDs, group, demographics, flags, dialogue metrics, and core score columns.
- `analysis_ready_scores_long.csv`: retained participants' core scores in long format.
- `valid_completed_analysis_scores.csv`: retained completed participants in the same wide score format.
- `participant_screening_all.csv`: all formal-window participants with inclusion/exclusion flags.
- `excluded_participants.csv`: participants not in the main analysis set with reasons.
- `completed_excluded_participants.csv`: completed participants excluded from the main analysis, with concise Chinese reasons and the failed attention-check item when applicable.
- `attention_check_failures.csv`: participants who failed the attention check.
- `conversation_review_recommended.csv`: participants whose dialogue was thin/off-topic enough to inspect manually.
- `conversation_review_notes.md`: compact participant-message digests for review; not a full raw-chat export.

## Counts

- Formal-window participants scanned: {len(rows)}
- Main analysis rows retained: {len(valid_rows)}
- Excluded rows: {len(excluded_rows)}
- Attention-check failures: {len(attention_rows)}
- Dialogue manual-review recommended: {len(review_rows)}
"""
    path.write_text(text, encoding="utf-8")


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def fmt_dt(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(sum(1 for _ in csv.reader(handle)) - 1, 0)


if __name__ == "__main__":
    main()
