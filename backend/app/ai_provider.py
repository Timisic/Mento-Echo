from __future__ import annotations

import json
import os
import selectors
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.config import Settings

PROMPTLESS_DIALOGUE_MODE = "promptless"
LENGTH_GUARDED_PROMPTLESS_MODE = "length_guarded_promptless_v1"
LENGTH_GUARD_SYSTEM_PROMPT = (
    "请用简体中文回复。回复控制在约300-500个中文字符内，保持完整收束，不要在句中中断。"
)


@dataclass(frozen=True)
class PromptConfig:
    version: str
    system_prompt: str


@dataclass(frozen=True)
class AIProviderResult:
    content: str
    provider_name: str
    model_name: str
    generation_params: dict[str, Any]
    request_started_at: datetime
    response_completed_at: datetime
    duration_ms: int
    retry_count: int = 0
    error_code: str | None = None
    error_message_sanitized: str | None = None
    provider_thread_id: str | None = None
    provider_turn_id: str | None = None


class AIProviderError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def prompt_for_group(group: str) -> PromptConfig:
    if group in {"pilot", "experiment", "control"}:
        return PromptConfig(LENGTH_GUARDED_PROMPTLESS_MODE, LENGTH_GUARD_SYSTEM_PROMPT)
    raise ValueError(f"Unknown group: {group}")


class OpenAICompatibleProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        provider_thread_id: str | None = None,
    ) -> AIProviderResult:
        started = datetime.now(UTC)
        monotonic_started = time.perf_counter()
        provider_name = self.settings.ai_provider_name.strip().lower()
        model_name = self.settings.ai_model_name.strip().lower()
        params = self._completion_params(provider_name=provider_name, model_name=model_name)
        if self.settings.ai_provider_name == "mock":
            latest_user = next((message["content"] for message in reversed(messages) if message["role"] == "user"), "")
            if "有效用户回合" in system_prompt:
                content = "1"
            else:
                content = f"[mock:{self.settings.ai_model_name}] 我会继续陪你讨论：{latest_user[:120]}"
            completed = datetime.now(UTC)
            return AIProviderResult(
                content=content,
                provider_name="mock",
                model_name=self.settings.ai_model_name,
                generation_params=params,
                request_started_at=started,
                response_completed_at=completed,
                duration_ms=int((time.perf_counter() - monotonic_started) * 1000),
            )

        if not self.settings.ai_api_key:
            raise AIProviderError("missing_api_key", "AI provider API key is not configured")
        payload_messages = list(messages)
        if system_prompt.strip():
            payload_messages = [{"role": "system", "content": system_prompt}, *payload_messages]
        payload = {
            "model": self.settings.ai_model_name,
            "messages": payload_messages,
            **params,
        }
        if provider_name == "deepseek" and model_name.startswith("deepseek-v4"):
            payload["thinking"] = {"type": "disabled"}
        request = urllib.request.Request(
            self.settings.ai_base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.ai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.ai_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason")
        except TimeoutError as exc:
            raise AIProviderError("provider_timeout", sanitize_error_message(str(exc))) from exc
        except (urllib.error.URLError, OSError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise AIProviderError("provider_error", sanitize_error_message(str(exc))) from exc
        if not str(content or "").strip():
            raise AIProviderError(
                "provider_error",
                sanitize_error_message(
                    f"AI provider returned empty content; finish_reason={finish_reason}"
                ),
            )
        if finish_reason == "length":
            raise AIProviderError(
                "provider_error",
                "AI provider response hit the configured length budget before finishing",
            )
        completed = datetime.now(UTC)
        generation_params = dict(params)
        if "thinking" in payload:
            generation_params["thinking"] = payload["thinking"]
        if finish_reason:
            generation_params["finish_reason"] = finish_reason
        return AIProviderResult(
            content=content,
            provider_name=self.settings.ai_provider_name,
            model_name=self.settings.ai_model_name,
            generation_params=generation_params,
            request_started_at=started,
            response_completed_at=completed,
            duration_ms=int((time.perf_counter() - monotonic_started) * 1000),
        )

    def _completion_params(self, *, provider_name: str, model_name: str) -> dict[str, str | float | int]:
        params: dict[str, str | float | int] = {}
        if self._uses_max_completion_tokens(provider_name=provider_name, model_name=model_name):
            params["max_completion_tokens"] = self.settings.ai_max_tokens
        else:
            params["max_tokens"] = self.settings.ai_max_tokens
        if self._supports_temperature(provider_name=provider_name, model_name=model_name):
            params["temperature"] = self.settings.ai_temperature
        if provider_name == "openai" and self.settings.ai_reasoning_effort:
            params["reasoning_effort"] = self.settings.ai_reasoning_effort
        return params

    @staticmethod
    def _uses_max_completion_tokens(*, provider_name: str, model_name: str) -> bool:
        return provider_name == "openai" and (
            model_name.startswith("gpt-5")
            or model_name.startswith("o1")
            or model_name.startswith("o3")
            or model_name.startswith("o4")
        )

    @staticmethod
    def _supports_temperature(*, provider_name: str, model_name: str) -> bool:
        if provider_name == "openai" and model_name.startswith("gpt-5"):
            return False
        return True


class CodexAppServerProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._request_id = 0

    def generate(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        provider_thread_id: str | None = None,
    ) -> AIProviderResult:
        latest_user = next((message["content"] for message in reversed(messages) if message["role"] == "user"), "")
        if not latest_user:
            raise AIProviderError("missing_user_message", "Codex provider requires a user message")

        started = datetime.now(UTC)
        monotonic_started = time.perf_counter()
        command = self.settings.codex_command.strip()
        if not command:
            raise AIProviderError("missing_codex_command", "CODEX_COMMAND is not configured")

        cwd = self.settings.codex_cwd or os.getcwd()
        process = subprocess.Popen(
            ["bash", "-lc", command],
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        selector = selectors.DefaultSelector()
        assert process.stdout is not None
        assert process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        try:
            self._send(process, "initialize", {
                "clientInfo": {"name": "mentor-echo", "version": "0.1"},
                "capabilities": {"experimentalApi": True},
            })
            self._read_response(process, selector, 1, timeout=self.settings.codex_read_timeout_seconds)

            if provider_thread_id:
                thread_response = self._send(
                    process,
                    "thread/resume",
                    self._thread_params(system_prompt=system_prompt, cwd=cwd, thread_id=provider_thread_id),
                )
            else:
                thread_response = self._send(
                    process,
                    "thread/start",
                    self._thread_params(system_prompt=system_prompt, cwd=cwd),
                )
            thread_result = self._read_response(
                process, selector, thread_response, timeout=self.settings.codex_read_timeout_seconds
            )
            thread_id = thread_result["thread"]["id"]

            turn_response = self._send(
                process,
                "turn/start",
                {
                    "threadId": thread_id,
                    "cwd": cwd,
                    "input": [{"type": "text", "text": latest_user}],
                    "model": self.settings.ai_model_name,
                    "effort": self.settings.codex_reasoning_effort,
                    "approvalPolicy": self.settings.codex_approval_policy,
                },
            )
            turn_result = self._read_response(
                process, selector, turn_response, timeout=self.settings.codex_read_timeout_seconds
            )
            turn_id = turn_result["turn"]["id"]
            content = self._read_turn_content(
                process,
                selector,
                thread_id=thread_id,
                turn_id=turn_id,
                timeout=min(self.settings.codex_turn_timeout_seconds, self.settings.ai_response_sla_seconds),
            )
        except AIProviderError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise AIProviderError("codex_protocol_error", sanitize_error_message(str(exc))) from exc
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
            selector.close()

        completed = datetime.now(UTC)
        return AIProviderResult(
            content=content.strip(),
            provider_name="codex",
            model_name=self.settings.ai_model_name,
            generation_params={
                "codex_command": command,
                "approval_policy": self.settings.codex_approval_policy,
                "sandbox": self.settings.codex_sandbox,
                "reasoning_effort": self.settings.codex_reasoning_effort,
            },
            request_started_at=started,
            response_completed_at=completed,
            duration_ms=int((time.perf_counter() - monotonic_started) * 1000),
            provider_thread_id=thread_id,
            provider_turn_id=turn_id,
        )

    def _thread_params(self, *, system_prompt: str, cwd: str, thread_id: str | None = None) -> dict[str, object]:
        params: dict[str, object] = {
            "cwd": cwd,
            "model": self.settings.ai_model_name,
            "approvalPolicy": self.settings.codex_approval_policy,
            "sandbox": self.settings.codex_sandbox,
        }
        if system_prompt.strip():
            params["baseInstructions"] = system_prompt
        if thread_id:
            params["threadId"] = thread_id
        return params

    def _send(self, process: subprocess.Popen[str], method: str, params: dict[str, object]) -> int:
        self._request_id += 1
        payload = {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params}
        assert process.stdin is not None
        process.stdin.write(json.dumps(payload) + "\n")
        process.stdin.flush()
        return self._request_id

    def _read_response(
        self,
        process: subprocess.Popen[str],
        selector: selectors.BaseSelector,
        request_id: int,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        stderr_tail: list[str] = []
        while time.monotonic() < deadline:
            for key, _ in selector.select(max(0.1, min(0.5, deadline - time.monotonic()))):
                line = key.fileobj.readline()
                if not line:
                    continue
                if key.data == "stderr":
                    stderr_tail.append(line.strip())
                    stderr_tail = stderr_tail[-5:]
                    continue
                message = json.loads(line)
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    raise AIProviderError("codex_protocol_error", sanitize_error_message(str(message["error"])))
                return message["result"]
            if process.poll() is not None:
                break
        raise AIProviderError("codex_timeout", sanitize_error_message("; ".join(stderr_tail) or "Codex app-server timed out"))

    def _read_turn_content(
        self,
        process: subprocess.Popen[str],
        selector: selectors.BaseSelector,
        *,
        thread_id: str,
        turn_id: str,
        timeout: float,
    ) -> str:
        deadline = time.monotonic() + timeout
        content_parts: list[str] = []
        stderr_tail: list[str] = []
        while time.monotonic() < deadline:
            for key, _ in selector.select(max(0.1, min(0.5, deadline - time.monotonic()))):
                line = key.fileobj.readline()
                if not line:
                    continue
                if key.data == "stderr":
                    stderr_tail.append(line.strip())
                    stderr_tail = stderr_tail[-5:]
                    continue
                message = json.loads(line)
                method = message.get("method")
                params = message.get("params") or {}
                if method == "item/agentMessage/delta" and params.get("threadId") == thread_id and params.get("turnId") == turn_id:
                    content_parts.append(str(params.get("delta") or ""))
                if method == "item/completed" and params.get("threadId") == thread_id and params.get("turnId") == turn_id:
                    item = params.get("item") or {}
                    if item.get("type") == "agentMessage":
                        completed_content = str(item.get("text") or "").strip()
                        if completed_content:
                            return completed_content
                if method == "turn/completed" and params.get("threadId") == thread_id:
                    turn = params.get("turn") or {}
                    if turn.get("id") == turn_id:
                        if turn.get("status") != "completed":
                            raise AIProviderError("codex_turn_failed", sanitize_error_message(str(turn.get("error") or turn)))
                        return "".join(content_parts)
                if method == "error":
                    if params.get("willRetry") is True:
                        stderr_tail.append(sanitize_error_message(str(params)))
                        stderr_tail = stderr_tail[-5:]
                        continue
                    raise AIProviderError("codex_protocol_error", sanitize_error_message(str(params)))
            if process.poll() is not None:
                break
        raise AIProviderError("codex_timeout", sanitize_error_message("; ".join(stderr_tail) or "Codex turn timed out"))


def create_ai_provider(settings: Settings) -> OpenAICompatibleProvider | CodexAppServerProvider:
    if settings.ai_provider_name.strip().lower() == "codex":
        return CodexAppServerProvider(settings)
    return OpenAICompatibleProvider(settings)


def sanitize_error_message(message: str) -> str:
    redacted = message
    # Avoid leaking bearer tokens or other long secrets through persisted diagnostics.
    for marker in ("Bearer ", "api_key", "apikey"):
        if marker in redacted:
            redacted = redacted.split(marker)[0] + marker + "[redacted]"
    return redacted[:500]
