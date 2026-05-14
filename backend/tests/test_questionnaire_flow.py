from __future__ import annotations

from app.models import AuditLog, QuestionnaireResponse, QuestionnaireScore
from app.questionnaire_config import ITEMS_BY_KEY, get_items
from tests.conftest import import_participants


def responses_for_phase(phase: str, *, numeric_value: int = 4, pass_attention: bool = True) -> dict[str, int | str]:
    responses: dict[str, int | str] = {}
    for item in get_items(phase):
        if item.scale == "gender_options":
            responses[item.item_key] = "女"
        elif item.scale == "grade_options":
            responses[item.item_key] = "大三"
        elif item.attention_check and pass_attention:
            assert item.attention_check_expected_value is not None
            responses[item.item_key] = item.attention_check_expected_value
        else:
            responses[item.item_key] = numeric_value
    return responses


def create_session(client, admin_headers, code="QFLOW", group="experiment") -> str:
    assert import_participants(
        client, admin_headers, [{"participant_code": code, "assigned_group": group}]
    ).status_code == 200
    return client.post("/api/participant/entry", json={"participant_code": code}).json()["session"][
        "experiment_session_id"
    ]


def test_pre_questionnaire_renders_from_versioned_config_without_name_fields(client, admin_headers):
    session_id = create_session(client, admin_headers)

    response = client.get(f"/api/participant/sessions/{session_id}/questionnaires/pre")

    assert response.status_code == 200
    body = response.json()
    assert body["questionnaire_version"] == "mentor_echo_questionnaire_v2026_05_14_hitl_map"
    assert body["phase"] == "pre"
    assert len(body["items"]) == 47
    assert all("姓名" not in item["item_text"] for item in body["items"])
    assert {item["item_key"] for item in body["items"]} == {item.item_key for item in get_items("pre")}


def test_pre_submission_locks_raw_responses_scores_and_assignment(client, admin_headers, db_session):
    session_id = create_session(client, admin_headers, group="control")

    submit = client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/pre/submit",
        json={"responses": responses_for_phase("pre", numeric_value=5)},
    )

    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["locked"] is True
    assert body["response_count"] == 47
    assert body["session"]["status"] == "pre_survey_submitted"
    assert body["session"]["group"] == "control"
    assert body["session"]["assignment_source"] == "imported"
    duplicate = client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/pre/submit",
        json={"responses": responses_for_phase("pre")},
    )
    assert duplicate.status_code == 409

    rows = db_session.query(QuestionnaireResponse).filter_by(experiment_session_id=session_id, phase="pre").all()
    assert len(rows) == 47
    sample = next(row for row in rows if row.item_key == "pre_identity_distress_01")
    assert sample.questionnaire_version == "mentor_echo_questionnaire_v2026_05_14_hitl_map"
    assert sample.instrument == "identity_distress"
    assert sample.dimension == "total"
    assert sample.response_value == 5
    assert sample.locked is True

    scores = db_session.query(QuestionnaireScore).filter_by(experiment_session_id=session_id, phase="pre").all()
    score_by_key = {(score.instrument, score.dimension): score for score in scores}
    assert score_by_key[("identity_distress", "total")].score == 5
    assert score_by_key[("attention_check", "pre_attention")].attention_check_passed is True


def test_attention_check_failure_is_scored(client, admin_headers):
    session_id = create_session(client, admin_headers, code="QATTN")
    payload = responses_for_phase("pre", numeric_value=4, pass_attention=False)
    payload["pre_ac_umics_select_5"] = 4

    response = client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/pre/submit",
        json={"responses": payload},
    )

    assert response.status_code == 200
    attention_score = next(
        score for score in response.json()["scores"] if score["instrument"] == "attention_check"
    )
    assert attention_score["score"] == 0
    assert attention_score["attention_check_passed"] is False


def test_admin_reset_reopens_questionnaire_with_audited_reason(client, admin_headers, db_session):
    session_id = create_session(client, admin_headers, code="QRESET")
    assert client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/pre/submit",
        json={"responses": responses_for_phase("pre")},
    ).status_code == 200

    reset = client.post(
        f"/api/admin/sessions/{session_id}/questionnaires/pre/reset",
        headers=admin_headers,
        json={"reason": "participant reported accidental submission"},
    )

    assert reset.status_code == 200
    resubmit = client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/pre/submit",
        json={"responses": responses_for_phase("pre", numeric_value=3)},
    )
    assert resubmit.status_code == 200

    audit = db_session.query(AuditLog).filter_by(action="pre_survey_reset").one()
    assert audit.reason == "participant reported accidental submission"
    active_rows = db_session.query(QuestionnaireResponse).filter_by(
        experiment_session_id=session_id, phase="pre", superseded_at=None
    ).all()
    assert len(active_rows) == 47


def test_post_questionnaire_is_available_only_after_dialogue_completion(client, admin_headers):
    session_id = create_session(client, admin_headers, code="QPOST")

    blocked = client.get(f"/api/participant/sessions/{session_id}/questionnaires/post")
    assert blocked.status_code == 409
