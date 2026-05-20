from __future__ import annotations

from datetime import timedelta

import pytest

from app.ai_provider import PROMPTLESS_DIALOGUE_MODE, AIProviderError, CodexAppServerProvider, OpenAICompatibleProvider, prompt_for_group
from app.config import Settings, get_settings
from app.models import ChatMessage, ExperimentSession
from app.services import DialogueService, now_utc
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
    pilot_prompt = prompt_for_group("pilot")
    assert pilot_prompt.version == PROMPTLESS_DIALOGUE_MODE
    assert pilot_prompt.system_prompt == ""
    experiment_prompt = prompt_for_group("experiment")
    assert experiment_prompt.version == PROMPTLESS_DIALOGUE_MODE
    assert experiment_prompt.system_prompt == ""

    mock = OpenAICompatibleProvider(Settings(AI_PROVIDER_NAME="mock", AI_MODEL_NAME="mock-model"))
    result = mock.generate(system_prompt="", messages=[{"role": "user", "content": "hello"}])
    assert result.provider_name == "mock"
    assert result.model_name == "mock-model"
    assert "hello" in result.content
    assert result.generation_params["temperature"] == 0.3

    real_without_key = OpenAICompatibleProvider(
        Settings(AI_PROVIDER_NAME="openai-compatible", AI_MODEL_NAME="model", AI_API_KEY=None)
    )
    with pytest.raises(AIProviderError) as exc:
        real_without_key.generate(system_prompt="", messages=[])
    assert exc.value.code == "missing_api_key"
    assert "key" in exc.value.message.lower()


def test_openai_compatible_payload_omits_system_message_when_promptless(monkeypatch):
    import json
    import urllib.request

    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"ok"}}]}'

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider(
        Settings(
            AI_PROVIDER_NAME="deepseek",
            AI_BASE_URL="https://api.deepseek.com/v1",
            AI_MODEL_NAME="deepseek-chat",
            AI_API_KEY="test-key",
            AI_TIMEOUT_SECONDS=10,
        )
    )

    result = provider.generate(system_prompt="", messages=[{"role": "user", "content": "hello"}])

    assert result.content == "ok"
    assert captured["timeout"] == 10
    assert captured["payload"] == {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "hello"}],
        "temperature": 0.3,
        "max_tokens": 600,
    }


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


def test_promptless_message_persistence_and_metadata(client, admin_headers, db_session):
    session_id = prepared_session(client, admin_headers, group="experiment")

    state = client.get(f"/api/participant/sessions/{session_id}/dialogue")
    assert state.status_code == 200
    assert state.json()["system_prompt_version"] is None
    send = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "我在考虑是否继续这个专业。"},
    )

    assert send.status_code == 200, send.text
    body = send.json()
    assert body["participant_message"]["role"] == "participant"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["provider_name"] is None
    assert body["assistant_message"]["model_name"] is None
    assert body["assistant_message"]["system_prompt_version"] is None
    assert body["assistant_message"]["generation_params"] is None
    assert body["progress"]["participant_turn_count"] == 1
    assert "api_key" not in str(body).lower()

    messages = db_session.query(ChatMessage).filter_by(experiment_session_id=session_id).order_by(ChatMessage.message_index).all()
    assert [message.role for message in messages] == ["participant", "assistant"]
    assert messages[1].provider_name == "mock"
    assert messages[1].model_name == "mock-mentor-echo"
    assert messages[1].system_prompt_version is None
    assert messages[1].generation_params["prompt_mode"] == PROMPTLESS_DIALOGUE_MODE
    assert messages[1].generation_params["temperature"] == 0.3


def test_dialogue_provider_thread_id_is_reused_for_session(client, admin_headers, db_session, monkeypatch):
    calls: list[str | None] = []

    class FakeProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            assert system_prompt == ""
            from app.ai_provider import AIProviderResult
            from app.services import now_utc

            calls.append(provider_thread_id)
            timestamp = now_utc()
            return AIProviderResult(
                content="fake response",
                provider_name="codex",
                model_name="fake-codex",
                generation_params={},
                request_started_at=timestamp,
                response_completed_at=timestamp,
                duration_ms=1,
                provider_thread_id=provider_thread_id or "thread-1",
                provider_turn_id=f"turn-{len(calls)}",
            )

    monkeypatch.setattr("app.services.create_ai_provider", lambda settings: FakeProvider())
    session_id = prepared_session(client, admin_headers, code="THREADMEM", group="experiment")

    first = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "第一条消息"},
    )
    second = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "第二条消息"},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert calls == [None, "thread-1"]
    session = db_session.get(ExperimentSession, session_id)
    assert session is not None
    assert session.dialogue_model_thread_id == "thread-1"
    assert session.dialogue_model_turn_id == "turn-2"


def test_dialogue_falls_back_without_exposing_provider_to_participant(client, admin_headers, db_session, monkeypatch):
    class PrimaryProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            assert system_prompt == ""
            raise AIProviderError("codex_timeout", "primary timed out")

    class FallbackProvider:
        def __init__(self, settings):
            self.settings = settings

        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            assert system_prompt == ""
            from app.ai_provider import AIProviderResult
            from app.services import now_utc

            timestamp = now_utc()
            return AIProviderResult(
                content="fallback response",
                provider_name=self.settings.ai_provider_name,
                model_name=self.settings.ai_model_name,
                generation_params={"temperature": self.settings.ai_temperature},
                request_started_at=timestamp,
                response_completed_at=timestamp,
                duration_ms=3,
            )

    def provider_factory(settings):
        if settings.ai_provider_name == "codex":
            return PrimaryProvider()
        return FallbackProvider(settings)

    monkeypatch.setattr("app.services.create_ai_provider", provider_factory)
    monkeypatch.setattr(
        "app.services.get_settings",
        lambda: Settings(
            AI_PROVIDER_NAME="codex",
            AI_MODEL_NAME="gpt-5.5",
            AI_FALLBACK_ENABLED=True,
            AI_FALLBACK_PROVIDER_NAME="deepseek",
            AI_FALLBACK_MODEL_NAME="deepseek-chat",
            AI_FALLBACK_API_KEY="test-key",
        ),
    )
    session_id = prepared_session(client, admin_headers, code="DFALLBACK", group="experiment")

    response = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "我想继续聊专业方向。"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assistant_message"]["content"] == "fallback response"
    assert body["assistant_message"]["provider_name"] is None
    assert body["assistant_message"]["model_name"] is None
    assert body["assistant_message"]["generation_params"] is None

    messages = db_session.query(ChatMessage).filter_by(experiment_session_id=session_id).order_by(ChatMessage.message_index).all()
    assert messages[1].provider_name == "deepseek"
    assert messages[1].model_name == "deepseek-chat"
    assert messages[1].system_prompt_version is None
    assert messages[1].generation_params["prompt_mode"] == PROMPTLESS_DIALOGUE_MODE
    assert messages[1].generation_params["fallback_triggered"] is True
    assert messages[1].generation_params["primary_error_code"] == "codex_timeout"
    assert messages[1].generation_params["fallback_from_provider"] == "codex"
    assert messages[1].generation_params["fallback_reason"] == "codex_timeout"


def test_codex_thread_params_are_promptless_by_default():
    provider = CodexAppServerProvider(Settings(AI_PROVIDER_NAME="codex", AI_MODEL_NAME="gpt-5.5"))

    params = provider._thread_params(system_prompt="", cwd="/tmp/mentor-echo")

    assert params["model"] == "gpt-5.5"
    assert "baseInstructions" not in params
    assert "developerInstructions" not in params


def test_codex_retryable_error_notification_does_not_fail_turn():
    class FakeStream:
        def __init__(self, lines: list[str]):
            self.lines = lines

        def readline(self) -> str:
            return self.lines.pop(0) if self.lines else ""

    class FakeKey:
        def __init__(self, stream: FakeStream):
            self.fileobj = stream
            self.data = "stdout"

    class FakeSelector:
        def __init__(self, stream: FakeStream):
            self.key = FakeKey(stream)

        def select(self, timeout: float):
            return [(self.key, None)] if self.key.fileobj.lines else []

    class FakeProcess:
        def poll(self):
            return None

    stream = FakeStream(
        [
            '{"method":"error","params":{"willRetry":true,"threadId":"thread-1","turnId":"turn-1","error":{"message":"Reconnecting..."}}}\n',
            '{"method":"item/agentMessage/delta","params":{"threadId":"thread-1","turnId":"turn-1","delta":"ok"}}\n',
            '{"method":"turn/completed","params":{"threadId":"thread-1","turn":{"id":"turn-1","status":"completed"}}}\n',
        ]
    )
    provider = CodexAppServerProvider(Settings(AI_PROVIDER_NAME="codex"))

    assert provider._read_turn_content(  # type: ignore[arg-type]
        FakeProcess(),
        FakeSelector(stream),
        thread_id="thread-1",
        turn_id="turn-1",
        timeout=1,
    ) == "ok"


def test_completion_eligibility_requires_10_effective_turns_and_15_minutes(client, admin_headers, db_session):
    session_id = prepared_session(client, admin_headers, code="DELIG", group="control")
    assert client.get(f"/api/participant/sessions/{session_id}/dialogue").status_code == 200
    session = db_session.get(ExperimentSession, session_id)
    assert session is not None
    session.dialogue_elapsed_seconds = DialogueService.MIN_ELAPSED_SECONDS + 5
    session.last_seen_at = now_utc()
    db_session.commit()

    filler = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "嗯"},
    )
    assert filler.status_code == 200, filler.text
    assert filler.json()["progress"]["participant_turn_count"] == 0

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
    assert tenth.json()["progress"]["finish_prompt_visible"] is True
    assert tenth.json()["status"] == "chat_eligible_to_finish"

    finish = client.post(f"/api/participant/sessions/{session_id}/dialogue/finish", json={"decision": "can_end"})
    assert finish.status_code == 200
    assert finish.json()["status"] == "chat_completed"


def test_dialogue_elapsed_time_does_not_count_offline_gap_or_force_time_limit(client, admin_headers, db_session):
    session_id = prepared_session(client, admin_headers, code="DOFFLINE", group="experiment")
    assert client.get(f"/api/participant/sessions/{session_id}/dialogue").status_code == 200
    session = db_session.get(ExperimentSession, session_id)
    assert session is not None
    session.dialogue_elapsed_seconds = 420
    session.chat_started_at = now_utc() - timedelta(hours=2)
    session.last_seen_at = now_utc() - timedelta(hours=2)
    db_session.commit()

    state = client.get(f"/api/participant/sessions/{session_id}/dialogue")

    assert state.status_code == 200
    progress = state.json()["progress"]
    assert 420 <= progress["dialogue_elapsed_seconds"] < 500
    assert progress["forced_to_finish"] is False
    assert progress["forced_finish_reason"] is None


def test_ai_provider_failure_response_keeps_cors_header(client, admin_headers, monkeypatch):
    session_id = prepared_session(client, admin_headers, code="DCORS", group="experiment")
    assert client.get(f"/api/participant/sessions/{session_id}/dialogue").status_code == 200

    class FailingProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            raise AIProviderError("provider_down", "simulated provider failure")

    monkeypatch.setattr("app.services.create_ai_provider", lambda settings: FailingProvider())

    origin = get_settings().cors_origin_list[0]
    response = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "我想聊聊当前专业和未来方向。"},
        headers={"Origin": origin},
    )

    assert response.status_code == 502
    assert response.headers["access-control-allow-origin"] == origin


def test_finish_branches_and_forced_limits(client, admin_headers, db_session):
    session_id = prepared_session(client, admin_headers, code="DBRANCH", group="experiment")
    assert client.get(f"/api/participant/sessions/{session_id}/dialogue").status_code == 200
    session = db_session.get(ExperimentSession, session_id)
    assert session is not None
    session.dialogue_elapsed_seconds = DialogueService.MIN_ELAPSED_SECONDS + 5
    session.last_seen_at = now_utc()
    db_session.commit()

    for i in range(DialogueService.MIN_PARTICIPANT_TURNS):
        response = client.post(
            f"/api/participant/sessions/{session_id}/dialogue/messages",
            json={"content": f"我对当前专业和未来方向的想法 {i}"},
        )
        assert response.status_code == 200, response.text
    branch = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/finish",
        json={"decision": "continue_related"},
    )
    assert branch.status_code == 200, branch.text
    assert branch.json()["status"] == "chat_in_progress"
    assert branch.json()["progress"]["finish_decision"] == "continue_related"

    one_more = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "我还想补充一个和就业方向相关的考虑。"},
    )
    assert one_more.status_code == 200
    assert one_more.json()["progress"]["finish_prompt_visible"] is False
    two_more = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "我也在比较继续读研和直接就业的风险。"},
    )
    assert two_more.status_code == 200
    assert two_more.json()["progress"]["finish_prompt_visible"] is True

    finish = client.post(f"/api/participant/sessions/{session_id}/dialogue/finish", json={"decision": "can_end"})
    assert finish.status_code == 200
    assert finish.json()["status"] == "chat_completed"

    c_session_id = prepared_session(client, admin_headers, code="DCORE", group="experiment")
    assert client.get(f"/api/participant/sessions/{c_session_id}/dialogue").status_code == 200
    c_session = db_session.get(ExperimentSession, c_session_id)
    assert c_session is not None
    c_session.dialogue_elapsed_seconds = DialogueService.MIN_ELAPSED_SECONDS + 5
    c_session.last_seen_at = now_utc()
    db_session.commit()
    for i in range(DialogueService.MIN_PARTICIPANT_TURNS):
        response = client.post(
            f"/api/participant/sessions/{c_session_id}/dialogue/messages",
            json={"content": f"我还没有谈到核心专业选择问题 {i}"},
        )
        assert response.status_code == 200, response.text
    not_core = client.post(
        f"/api/participant/sessions/{c_session_id}/dialogue/finish",
        json={"decision": "not_core"},
    )
    assert not_core.status_code == 200
    assert not_core.json()["status"] == "chat_in_progress"
    assert not_core.json()["progress"]["finish_decision"] == "not_core"
    assert not_core.json()["progress"]["finish_prompt_visible"] is False


def test_early_stop_and_max_turn_force_finish(client, admin_headers, db_session):
    early_session_id = prepared_session(client, admin_headers, code="DEARLY", group="experiment")
    assert client.get(f"/api/participant/sessions/{early_session_id}/dialogue").status_code == 200
    early = client.post(
        f"/api/participant/sessions/{early_session_id}/dialogue/finish",
        json={"decision": "early_stop"},
    )
    assert early.status_code == 200
    assert early.json()["status"] == "chat_completed"

    forced_session_id = prepared_session(client, admin_headers, code="DFORCE", group="experiment")
    assert client.get(f"/api/participant/sessions/{forced_session_id}/dialogue").status_code == 200
    for i in range(DialogueService.MAX_PARTICIPANT_TURNS):
        response = client.post(
            f"/api/participant/sessions/{forced_session_id}/dialogue/messages",
            json={"content": f"关于专业选择和未来方向的第 {i} 个具体想法。"},
        )
        assert response.status_code == 200, response.text
    state = client.get(f"/api/participant/sessions/{forced_session_id}/dialogue").json()
    assert state["progress"]["forced_to_finish"] is True
    assert state["progress"]["forced_finish_reason"] == "max_turns"
    blocked = client.post(
        f"/api/participant/sessions/{forced_session_id}/dialogue/messages",
        json={"content": "我还想继续绕过上限。"},
    )
    assert blocked.status_code == 409
    finish = client.post(f"/api/participant/sessions/{forced_session_id}/dialogue/finish", json={"decision": "can_end"})
    assert finish.status_code == 200
    assert finish.json()["status"] == "chat_completed"
    completed_send = client.post(
        f"/api/participant/sessions/{forced_session_id}/dialogue/messages",
        json={"content": "完成后不应继续发送。"},
    )
    assert completed_send.status_code == 409


def test_full_participant_path_pre_dialogue_post_completed(client, admin_headers, db_session):
    session_id = prepared_session(client, admin_headers, code="DFULL", group="experiment")
    assert client.get(f"/api/participant/sessions/{session_id}/dialogue").status_code == 200
    session = db_session.get(ExperimentSession, session_id)
    assert session is not None
    session.dialogue_elapsed_seconds = DialogueService.MIN_ELAPSED_SECONDS + 5
    session.last_seen_at = now_utc()
    db_session.commit()
    for i in range(10):
        assert client.post(
            f"/api/participant/sessions/{session_id}/dialogue/messages",
            json={"content": f"identity reflection {i}"},
        ).status_code == 200
    assert client.post(f"/api/participant/sessions/{session_id}/dialogue/finish").status_code == 200

    post_definition = client.get(f"/api/participant/sessions/{session_id}/questionnaires/post")
    assert post_definition.status_code == 200
    assert len(post_definition.json()["items"]) == 40
    assert any(
        item["item_key"] == "post_ai_warmth_01"
        for item in post_definition.json()["items"]
    )
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
