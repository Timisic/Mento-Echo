from __future__ import annotations

from datetime import timedelta

import pytest

from app.ai_provider import AIProviderError, OpenAICompatibleProvider, prompt_for_group
from app.config import Settings
from app.models import ChatMessage, ExperimentSession
from app.services import DialogueService
from tests.conftest import import_participants
from tests.test_questionnaire_flow import responses_for_phase


def prepared_session(client, admin_headers, code="DIALOGUE", group="experiment") -> str:
    assert import_participants(
        client, admin_headers, [{"participant_code": code, "assigned_group": group}]
    ).status_code == 200
    session_id = client.post("/api/participant/entry", json={"participant_code": code}).json()["session"][
        "experiment_session_id"
    ]
    assert client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/pre/submit",
        json={"responses": responses_for_phase("pre")},
    ).status_code == 200
    return session_id


def test_ai_provider_boundary_mock_and_missing_key_behavior():
    mock = OpenAICompatibleProvider(Settings(AI_PROVIDER_NAME="mock", AI_MODEL_NAME="mock-model"))
    result = mock.generate(system_prompt="system", messages=[{"role": "user", "content": "hello"}])
    assert result.provider_name == "mock"
    assert result.model_name == "mock-model"
    assert "hello" in result.content
    assert result.generation_params["temperature"] == 0.3

    real_without_key = OpenAICompatibleProvider(
        Settings(AI_PROVIDER_NAME="openai-compatible", AI_MODEL_NAME="model", AI_API_KEY=None)
    )
    with pytest.raises(AIProviderError) as exc:
        real_without_key.generate(system_prompt="system", messages=[])
    assert exc.value.code == "missing_api_key"
    assert "key" in exc.value.message.lower()


def test_dialogue_blocked_before_pre_survey(client, admin_headers):
    assert import_participants(
        client, admin_headers, [{"participant_code": "DBLOCK", "assigned_group": "experiment"}]
    ).status_code == 200
    session_id = client.post("/api/participant/entry", json={"participant_code": "DBLOCK"}).json()["session"][
        "experiment_session_id"
    ]

    response = client.get(f"/api/participant/sessions/{session_id}/dialogue")

    assert response.status_code == 409
    assert response.json()["detail"] in {
        "AI Dialogue is available only after pre-survey submission",
        "Group Assignment is required before dialogue",
    }


def test_prompt_selection_message_persistence_and_metadata(client, admin_headers, db_session):
    session_id = prepared_session(client, admin_headers, group="experiment")

    state = client.get(f"/api/participant/sessions/{session_id}/dialogue")
    assert state.status_code == 200
    assert state.json()["system_prompt_version"] == prompt_for_group("experiment").version
    send = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "我在考虑是否继续这个专业。"},
    )

    assert send.status_code == 200, send.text
    body = send.json()
    assert body["participant_message"]["role"] == "participant"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["provider_name"] == "mock"
    assert body["assistant_message"]["model_name"] == "mock-mentor-echo"
    assert body["assistant_message"]["system_prompt_version"] == "experiment_identity_dialogue_v1"
    assert body["progress"]["participant_turn_count"] == 1
    assert "api_key" not in str(body).lower()

    messages = db_session.query(ChatMessage).filter_by(experiment_session_id=session_id).order_by(ChatMessage.message_index).all()
    assert [message.role for message in messages] == ["participant", "assistant"]
    assert messages[1].generation_params["temperature"] == 0.3


def test_completion_eligibility_requires_10_participant_turns_and_15_minutes(client, admin_headers, db_session):
    session_id = prepared_session(client, admin_headers, code="DELIG", group="control")
    assert client.get(f"/api/participant/sessions/{session_id}/dialogue").status_code == 200
    session = db_session.get(ExperimentSession, session_id)
    assert session is not None
    session.chat_started_at = session.chat_started_at - timedelta(seconds=DialogueService.MIN_ELAPSED_SECONDS + 5)
    db_session.commit()

    for i in range(9):
        response = client.post(
            f"/api/participant/sessions/{session_id}/dialogue/messages",
            json={"content": f"light topic message {i}"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["progress"]["eligible_to_finish"] is False

    finish_early = client.post(f"/api/participant/sessions/{session_id}/dialogue/finish")
    assert finish_early.status_code == 409

    tenth = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "light topic message 10"},
    )
    assert tenth.status_code == 200
    assert tenth.json()["progress"]["eligible_to_finish"] is True
    assert tenth.json()["status"] == "chat_eligible_to_finish"

    finish = client.post(f"/api/participant/sessions/{session_id}/dialogue/finish")
    assert finish.status_code == 200
    assert finish.json()["status"] == "chat_completed"


def test_full_participant_path_pre_dialogue_post_completed(client, admin_headers, db_session):
    session_id = prepared_session(client, admin_headers, code="DFULL", group="experiment")
    assert client.get(f"/api/participant/sessions/{session_id}/dialogue").status_code == 200
    session = db_session.get(ExperimentSession, session_id)
    assert session is not None
    session.chat_started_at = session.chat_started_at - timedelta(seconds=DialogueService.MIN_ELAPSED_SECONDS + 5)
    db_session.commit()
    for i in range(10):
        assert client.post(
            f"/api/participant/sessions/{session_id}/dialogue/messages",
            json={"content": f"identity reflection {i}"},
        ).status_code == 200
    assert client.post(f"/api/participant/sessions/{session_id}/dialogue/finish").status_code == 200

    post_definition = client.get(f"/api/participant/sessions/{session_id}/questionnaires/post")
    assert post_definition.status_code == 200
    assert len(post_definition.json()["items"]) == 36
    post_submit = client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/post/submit",
        json={"responses": responses_for_phase("post")},
    )
    assert post_submit.status_code == 200, post_submit.text
    assert post_submit.json()["session"]["status"] == "completed"
    duplicate_post = client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/post/submit",
        json={"responses": responses_for_phase("post")},
    )
    assert duplicate_post.status_code == 409
