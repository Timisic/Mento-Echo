from __future__ import annotations

from datetime import timedelta

import pytest

from app.ai_provider import (
    PROMPTLESS_DIALOGUE_MODE,
    AIProviderError,
    AIProviderResult,
    CodexAppServerProvider,
    OpenAICompatibleProvider,
    prompt_for_group,
)
from app.config import Settings, get_settings
from app.models import ChatMessage, ExperimentSession, Participant
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


def test_dialogue_uses_200_char_system_prompt_for_deepseek_only():
    deepseek_prompt = DialogueService._dialogue_prompt_config(
        Settings(AI_PROVIDER_NAME="deepseek", AI_MODEL_NAME="deepseek-v4-pro")
    )
    assert deepseek_prompt.version == "deepseek_200_char_limit_v1"
    assert "严格不超过200字" in deepseek_prompt.system_prompt

    mock_prompt = DialogueService._dialogue_prompt_config(Settings(AI_PROVIDER_NAME="mock"))
    assert mock_prompt.version == PROMPTLESS_DIALOGUE_MODE
    assert mock_prompt.system_prompt == ""


def test_dialogue_injects_deepseek_prompt_and_records_version(client, admin_headers, db_session, monkeypatch):
    captured: dict[str, object] = {}

    class FakeProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            captured["system_prompt"] = system_prompt
            captured["messages"] = messages
            timestamp = now_utc()
            return AIProviderResult(
                content="建议先补编程基础，再结合心理学背景选择人机交互或AI产品方向。",
                provider_name="deepseek",
                model_name="deepseek-v4-pro",
                generation_params={},
                request_started_at=timestamp,
                response_completed_at=timestamp,
                duration_ms=1,
            )

    monkeypatch.setattr("app.services.create_ai_provider", lambda settings: FakeProvider())
    monkeypatch.setattr(
        "app.services.get_settings",
        lambda: Settings(
            AI_PROVIDER_NAME="deepseek",
            AI_MODEL_NAME="deepseek-v4-pro",
            AI_API_KEY="test-key",
            AI_FALLBACK_ENABLED=False,
        ),
    )
    session_id = prepared_session(client, admin_headers, code="DDEEPSEEK", group="experiment")

    response = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "我是心理学专业，想转人工智能。"},
    )

    assert response.status_code == 200, response.text
    assert "严格不超过200字" in str(captured["system_prompt"])
    assert captured["messages"][-1]["content"] == "我是心理学专业，想转人工智能。"
    db_session.expire_all()
    messages = db_session.query(ChatMessage).filter_by(experiment_session_id=session_id).order_by(ChatMessage.message_index).all()
    assert messages[1].system_prompt_version == "deepseek_200_char_limit_v1"
    assert messages[1].generation_params["prompt_mode"] == "deepseek_200_char_limit_v1"


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
            AI_MAX_TOKENS=600,
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



def test_openai_gpt5_payload_uses_supported_token_and_temperature_params(monkeypatch):
    import json
    import urllib.request

    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices":[{"finish_reason":"stop","message":{"content":"ok"}}]}'

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider(
        Settings(
            AI_PROVIDER_NAME="openai",
            AI_BASE_URL="https://api.openai.com/v1",
            AI_MODEL_NAME="gpt-5.5",
            AI_API_KEY="test-key",
            AI_TEMPERATURE=0.3,
            AI_MAX_TOKENS=800,
        )
    )

    result = provider.generate(system_prompt="", messages=[{"role": "user", "content": "hello"}])

    assert result.content == "ok"
    assert captured["payload"] == {
        "model": "gpt-5.5",
        "messages": [{"role": "user", "content": "hello"}],
        "max_completion_tokens": 800,
    }
    assert result.generation_params["max_completion_tokens"] == 800
    assert "temperature" not in result.generation_params

def test_deepseek_v4_payload_disables_thinking_for_sla_fallback(monkeypatch):
    import json
    import urllib.request

    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices":[{"finish_reason":"stop","message":{"content":"ok","reasoning_content":null}}]}'

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider(
        Settings(
            AI_PROVIDER_NAME="deepseek",
            AI_BASE_URL="https://api.deepseek.com",
            AI_MODEL_NAME="deepseek-v4-pro",
            AI_API_KEY="test-key",
        )
    )

    result = provider.generate(system_prompt="", messages=[{"role": "user", "content": "hello"}])

    assert result.content == "ok"
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert result.generation_params["thinking"] == {"type": "disabled"}
    assert result.generation_params["finish_reason"] == "stop"


def test_openai_compatible_empty_content_is_provider_error(monkeypatch):
    import urllib.request

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices":[{"finish_reason":"length","message":{"content":"","reasoning_content":"thinking"}}]}'

    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: FakeResponse())
    provider = OpenAICompatibleProvider(
        Settings(
            AI_PROVIDER_NAME="deepseek",
            AI_BASE_URL="https://api.deepseek.com",
            AI_MODEL_NAME="deepseek-v4-pro",
            AI_API_KEY="test-key",
        )
    )

    with pytest.raises(AIProviderError) as exc:
        provider.generate(system_prompt="", messages=[{"role": "user", "content": "hello"}])

    assert exc.value.code == "provider_error"
    assert "empty content" in exc.value.message
    assert "finish_reason=length" in exc.value.message


def test_openai_compatible_read_timeout_is_ai_provider_error(monkeypatch):
    import urllib.request

    class TimeoutResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: TimeoutResponse())
    provider = OpenAICompatibleProvider(
        Settings(
            AI_PROVIDER_NAME="deepseek",
            AI_BASE_URL="https://api.deepseek.com/v1",
            AI_MODEL_NAME="deepseek-chat",
            AI_API_KEY="test-key",
            AI_TIMEOUT_SECONDS=10,
        )
    )

    with pytest.raises(AIProviderError) as exc:
        provider.generate(system_prompt="", messages=[{"role": "user", "content": "hello"}])

    assert exc.value.code == "provider_timeout"
    assert "timed out" in exc.value.message


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
    assert body["assistant_message"] is None
    assert body["progress"]["participant_turn_count"] == 1
    assert "api_key" not in str(body).lower()

    db_session.expire_all()
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
            assert "严格不超过200字" in system_prompt
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
            AI_FALLBACK_MODEL_NAME="deepseek-v4-pro",
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
    assert body["assistant_message"] is None

    db_session.expire_all()
    messages = db_session.query(ChatMessage).filter_by(experiment_session_id=session_id).order_by(ChatMessage.message_index).all()
    assert messages[1].content == "fallback response"
    assert messages[1].provider_name == "deepseek"
    assert messages[1].model_name == "deepseek-v4-pro"
    assert messages[1].system_prompt_version == "deepseek_200_char_limit_v1"
    assert messages[1].generation_params["prompt_mode"] == "deepseek_200_char_limit_v1"
    assert messages[1].generation_params["fallback_triggered"] is True
    assert messages[1].generation_params["primary_error_code"] == "codex_timeout"
    assert messages[1].generation_params["fallback_from_provider"] == "codex"
    assert messages[1].generation_params["fallback_reason"] == "codex_timeout"


def test_fallback_timeout_uses_remaining_sla_budget(monkeypatch):
    seen_timeouts: list[float] = []

    class PrimaryProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            raise AIProviderError("codex_timeout", "primary timed out")

    class FallbackProvider:
        def __init__(self, settings):
            seen_timeouts.append(settings.ai_timeout_seconds)

        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            from app.ai_provider import AIProviderResult

            timestamp = now_utc()
            return AIProviderResult(
                content="fallback response",
                provider_name="deepseek",
                model_name="deepseek-v4-pro",
                generation_params={},
                request_started_at=timestamp,
                response_completed_at=timestamp,
                duration_ms=1,
            )

    def provider_factory(settings):
        if settings.ai_provider_name == "codex":
            return PrimaryProvider()
        return FallbackProvider(settings)

    ticks = iter([100.0, 124.0, 124.0])
    monkeypatch.setattr("app.services.time.perf_counter", lambda: next(ticks))
    monkeypatch.setattr("app.services.create_ai_provider", provider_factory)

    result, primary_error = DialogueService._generate_with_fallback(
        settings=Settings(
            AI_PROVIDER_NAME="codex",
            AI_MODEL_NAME="gpt-5.5",
            AI_RESPONSE_SLA_SECONDS=30,
            AI_FALLBACK_ENABLED=True,
            AI_FALLBACK_PROVIDER_NAME="deepseek",
            AI_FALLBACK_API_KEY="test-key",
            AI_FALLBACK_TIMEOUT_SECONDS=30,
        ),
        system_prompt="",
        history=[{"role": "user", "content": "hello"}],
        provider_thread_id=None,
    )

    assert result.provider_name == "deepseek"
    assert primary_error is not None
    assert seen_timeouts == [6.0]



def test_default_fallback_model_uses_current_deepseek_v4_pro():
    assert Settings.model_fields["ai_fallback_model_name"].default == "deepseek-v4-pro"


def test_default_fallback_limits_fit_deepseek_v4_pro_sla():
    assert Settings.model_fields["ai_fallback_max_tokens"].default == 500
    assert Settings.model_fields["codex_read_timeout_seconds"].default == 5.0


def test_fallback_retries_transient_provider_error_before_success(monkeypatch):
    fallback_attempts: list[int] = []

    class PrimaryProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            raise AIProviderError("codex_timeout", "primary timed out")

    class FallbackProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            from app.ai_provider import AIProviderResult

            fallback_attempts.append(len(fallback_attempts) + 1)
            if len(fallback_attempts) == 1:
                raise AIProviderError("provider_timeout", "temporary fallback timeout")
            timestamp = now_utc()
            return AIProviderResult(
                content="fallback response after retry",
                provider_name="deepseek",
                model_name="deepseek-v4-pro",
                generation_params={"temperature": 0.3},
                request_started_at=timestamp,
                response_completed_at=timestamp,
                duration_ms=1,
            )

    def provider_factory(settings):
        if settings.ai_provider_name == "codex":
            return PrimaryProvider()
        return FallbackProvider()

    monkeypatch.setattr("app.services.create_ai_provider", provider_factory)

    result, primary_error = DialogueService._generate_with_fallback(
        settings=Settings(
            AI_PROVIDER_NAME="codex",
            AI_MODEL_NAME="gpt-5.5",
            AI_RESPONSE_SLA_SECONDS=30,
            AI_FALLBACK_ENABLED=True,
            AI_FALLBACK_PROVIDER_NAME="deepseek",
            AI_FALLBACK_MODEL_NAME="deepseek-v4-pro",
            AI_FALLBACK_API_KEY="test-key",
            AI_FALLBACK_MAX_ATTEMPTS=2,
        ),
        system_prompt="",
        history=[{"role": "user", "content": "hello"}],
        provider_thread_id=None,
    )

    assert primary_error is not None
    assert primary_error.code == "codex_timeout"
    assert result.content == "fallback response after retry"
    assert result.provider_name == "deepseek"
    assert result.retry_count == 1
    assert result.generation_params["retry_errors"][0]["code"] == "provider_timeout"
    assert fallback_attempts == [1, 2]



def test_fallback_retry_recomputes_timeout_against_cumulative_sla(monkeypatch):
    seen_timeouts: list[float] = []
    fallback_attempts: list[int] = []

    class PrimaryProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            raise AIProviderError("codex_timeout", "primary timed out")

    class FallbackProvider:
        def __init__(self, settings):
            seen_timeouts.append(settings.ai_timeout_seconds)

        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            from app.ai_provider import AIProviderResult

            fallback_attempts.append(len(fallback_attempts) + 1)
            if len(fallback_attempts) == 1:
                raise AIProviderError("provider_timeout", "temporary fallback timeout")
            timestamp = now_utc()
            return AIProviderResult(
                content="fallback response",
                provider_name="deepseek",
                model_name="deepseek-v4-pro",
                generation_params={},
                request_started_at=timestamp,
                response_completed_at=timestamp,
                duration_ms=1,
            )

    def provider_factory(settings):
        if settings.ai_provider_name == "codex":
            return PrimaryProvider()
        return FallbackProvider(settings)

    ticks = iter([100.0, 124.0, 124.0, 129.5])
    monkeypatch.setattr("app.services.time.perf_counter", lambda: next(ticks))
    monkeypatch.setattr("app.services.create_ai_provider", provider_factory)

    result, primary_error = DialogueService._generate_with_fallback(
        settings=Settings(
            AI_PROVIDER_NAME="codex",
            AI_MODEL_NAME="gpt-5.5",
            AI_RESPONSE_SLA_SECONDS=30,
            AI_FALLBACK_ENABLED=True,
            AI_FALLBACK_PROVIDER_NAME="deepseek",
            AI_FALLBACK_API_KEY="test-key",
            AI_FALLBACK_TIMEOUT_SECONDS=30,
            AI_FALLBACK_MAX_ATTEMPTS=2,
        ),
        system_prompt="",
        history=[{"role": "user", "content": "hello"}],
        provider_thread_id=None,
    )

    assert result.provider_name == "deepseek"
    assert primary_error is not None
    assert seen_timeouts == [6.0, 0.5]
    assert fallback_attempts == [1, 2]


def test_fallback_retry_stops_when_cumulative_sla_budget_is_exhausted(monkeypatch):
    fallback_attempts: list[int] = []

    class PrimaryProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            raise AIProviderError("codex_timeout", "primary timed out")

    class FallbackProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            fallback_attempts.append(len(fallback_attempts) + 1)
            raise AIProviderError("provider_timeout", "temporary fallback timeout")

    def provider_factory(settings):
        if settings.ai_provider_name == "codex":
            return PrimaryProvider()
        return FallbackProvider()

    ticks = iter([100.0, 124.0, 124.0, 130.1])
    monkeypatch.setattr("app.services.time.perf_counter", lambda: next(ticks))
    monkeypatch.setattr("app.services.create_ai_provider", provider_factory)

    with pytest.raises(AIProviderError) as exc:
        DialogueService._generate_with_fallback(
            settings=Settings(
                AI_PROVIDER_NAME="codex",
                AI_MODEL_NAME="gpt-5.5",
                AI_RESPONSE_SLA_SECONDS=30,
                AI_FALLBACK_ENABLED=True,
                AI_FALLBACK_PROVIDER_NAME="deepseek",
                AI_FALLBACK_API_KEY="test-key",
                AI_FALLBACK_TIMEOUT_SECONDS=30,
                AI_FALLBACK_MAX_ATTEMPTS=2,
            ),
            system_prompt="",
            history=[{"role": "user", "content": "hello"}],
            provider_thread_id=None,
        )

    assert exc.value.code == "ai_fallback_failed"
    assert "Fallback retry budget exhausted" in exc.value.message
    assert fallback_attempts == [1]


def test_fallback_does_not_retry_non_retryable_provider_error(monkeypatch):
    fallback_attempts: list[int] = []

    class PrimaryProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            raise AIProviderError("codex_timeout", "primary timed out")

    class FallbackProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            fallback_attempts.append(len(fallback_attempts) + 1)
            raise AIProviderError("missing_api_key", "fallback key missing")

    def provider_factory(settings):
        if settings.ai_provider_name == "codex":
            return PrimaryProvider()
        return FallbackProvider()

    monkeypatch.setattr("app.services.create_ai_provider", provider_factory)

    with pytest.raises(AIProviderError) as exc:
        DialogueService._generate_with_fallback(
            settings=Settings(
                AI_PROVIDER_NAME="codex",
                AI_MODEL_NAME="gpt-5.5",
                AI_RESPONSE_SLA_SECONDS=30,
                AI_FALLBACK_ENABLED=True,
                AI_FALLBACK_PROVIDER_NAME="deepseek",
                AI_FALLBACK_API_KEY="test-key",
                AI_FALLBACK_MAX_ATTEMPTS=3,
            ),
            system_prompt="",
            history=[{"role": "user", "content": "hello"}],
            provider_thread_id=None,
        )

    assert exc.value.code == "ai_fallback_failed"
    assert "fallback missing_api_key" in exc.value.message
    assert "attempts=1" in exc.value.message
    assert "retryable=False" in exc.value.message
    assert fallback_attempts == [1]


def test_fallback_retry_exhaustion_reports_sanitized_failure(monkeypatch):
    fallback_attempts: list[int] = []

    class PrimaryProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            raise AIProviderError("codex_timeout", "primary timed out")

    class FallbackProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            fallback_attempts.append(len(fallback_attempts) + 1)
            raise AIProviderError("provider_timeout", "temporary fallback timeout")

    def provider_factory(settings):
        if settings.ai_provider_name == "codex":
            return PrimaryProvider()
        return FallbackProvider()

    monkeypatch.setattr("app.services.create_ai_provider", provider_factory)

    with pytest.raises(AIProviderError) as exc:
        DialogueService._generate_with_fallback(
            settings=Settings(
                AI_PROVIDER_NAME="codex",
                AI_MODEL_NAME="gpt-5.5",
                AI_RESPONSE_SLA_SECONDS=30,
                AI_FALLBACK_ENABLED=True,
                AI_FALLBACK_PROVIDER_NAME="deepseek",
                AI_FALLBACK_MODEL_NAME="deepseek-v4-pro",
                AI_FALLBACK_API_KEY="test-key",
                AI_FALLBACK_MAX_ATTEMPTS=2,
            ),
            system_prompt="",
            history=[{"role": "user", "content": "hello"}],
            provider_thread_id=None,
        )

    assert exc.value.code == "ai_fallback_failed"
    assert "primary codex_timeout" in exc.value.message
    assert "fallback provider_timeout" in exc.value.message
    assert "attempts=2" in exc.value.message
    assert fallback_attempts == [1, 2]

def test_dialogue_unexpected_provider_error_completes_pending_turn(client, admin_headers, db_session, monkeypatch):
    class BrokenProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            raise ValueError("unexpected provider failure")

    monkeypatch.setattr("app.services.create_ai_provider", lambda settings: BrokenProvider())
    session_id = prepared_session(client, admin_headers, code="DUNEXPECTED", group="experiment")

    response = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "我想聊聊专业方向和未来选择。"},
    )

    assert response.status_code == 200, response.text
    db_session.expire_all()
    messages = db_session.query(ChatMessage).filter_by(experiment_session_id=session_id).order_by(ChatMessage.message_index).all()
    assert [message.role for message in messages] == ["participant", "assistant"]
    assert messages[1].content == "AI 回复暂时生成失败，请稍后重试或联系研究者。"
    assert messages[1].error_code == "ai_generation_failed"
    assert "unexpected provider failure" in messages[1].error_message_sanitized


def test_finish_waits_for_pending_assistant_response(client, admin_headers, db_session):
    session_id = prepared_session(client, admin_headers, code="DPENDING", group="experiment")
    assert client.get(f"/api/participant/sessions/{session_id}/dialogue").status_code == 200
    session = db_session.get(ExperimentSession, session_id)
    assert session is not None
    participant = db_session.get(Participant, session.participant_id)
    assert participant is not None
    session.dialogue_elapsed_seconds = DialogueService.MIN_ELAPSED_SECONDS + 5
    session.last_seen_at = now_utc()
    db_session.commit()

    for i in range(DialogueService.MIN_PARTICIPANT_TURNS):
        participant_message = DialogueService.send_message(
            db_session,
            session=session,
            participant=participant,
            content=f"我对当前专业和未来方向的想法 {i}",
        )
        if i < DialogueService.MIN_PARTICIPANT_TURNS - 1:
            assistant = ChatMessage(
                experiment_session_id=session.id,
                participant_code=participant.participant_code,
                message_index=participant_message.message_index + 1,
                role="assistant",
                content="继续聊聊。",
                provider_name="mock",
                model_name="mock-mentor-echo",
            )
            db_session.add(assistant)
            db_session.commit()

    finish = client.post(f"/api/participant/sessions/{session_id}/dialogue/finish", json={"decision": "can_end"})

    assert finish.status_code == 409
    assert finish.json()["detail"] == "AI response is still pending"

    early_stop = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/finish",
        json={"decision": "early_stop"},
    )

    assert early_stop.status_code == 409
    assert early_stop.json()["detail"] == "AI response is still pending"


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


def test_codex_item_completed_returns_content_without_turn_completed():
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
            '{"method":"item/agentMessage/delta","params":{"threadId":"thread-1","turnId":"turn-1","delta":"o"}}\n',
            '{"method":"item/agentMessage/delta","params":{"threadId":"thread-1","turnId":"turn-1","delta":"k"}}\n',
            '{"method":"item/completed","params":{"threadId":"thread-1","turnId":"turn-1","item":{"type":"agentMessage","text":"ok"}}}\n',
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


def test_completion_eligibility_requires_6_effective_turns_and_10_active_minutes(client, admin_headers, db_session):
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

    for i in range(DialogueService.MIN_PARTICIPANT_TURNS - 1):
        response = client.post(
            f"/api/participant/sessions/{session_id}/dialogue/messages",
            json={"content": f"light topic message {i}"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["progress"]["eligible_to_finish"] is False

    finish_early = client.post(f"/api/participant/sessions/{session_id}/dialogue/finish")
    assert finish_early.status_code == 409

    sixth = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "light topic message final"},
    )
    assert sixth.status_code == 200
    assert sixth.json()["progress"]["eligible_to_finish"] is True
    assert sixth.json()["progress"]["finish_prompt_visible"] is True
    assert sixth.json()["status"] == "chat_eligible_to_finish"

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


def test_ai_provider_failure_response_keeps_cors_header(client, admin_headers, db_session, monkeypatch):
    session_id = prepared_session(client, admin_headers, code="DCORS", group="experiment")
    assert client.get(f"/api/participant/sessions/{session_id}/dialogue").status_code == 200

    class FailingProvider:
        def generate(self, *, system_prompt, messages, provider_thread_id=None):
            raise AIProviderError("provider_down", "simulated provider failure")

    monkeypatch.setattr("app.services.create_ai_provider", lambda settings: FailingProvider())
    monkeypatch.setattr("app.services.get_settings", lambda: Settings(AI_FALLBACK_ENABLED=False))

    origin = get_settings().cors_origin_list[0]
    response = client.post(
        f"/api/participant/sessions/{session_id}/dialogue/messages",
        json={"content": "我想聊聊当前专业和未来方向。"},
        headers={"Origin": origin},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    db_session.expire_all()
    messages = db_session.query(ChatMessage).filter_by(experiment_session_id=session_id).order_by(ChatMessage.message_index).all()
    assert [message.role for message in messages] == ["participant", "assistant"]
    assert messages[1].content == "AI 回复暂时生成失败，请稍后重试或联系研究者。"
    assert messages[1].error_code == "provider_down"


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
