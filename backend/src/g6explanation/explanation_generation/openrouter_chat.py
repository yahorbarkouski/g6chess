"""OpenRouter chat-completions adapter for coach explanations."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from g6explanation.explanation_generation.contracts import (
    CoachModelResponse,
    CoachPrompt,
)
from g6explanation.explanation_generation.exceptions import CoachModelError

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-5.5"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_TIMEOUT_SECONDS = 90.0
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_BACKOFF_SECONDS = 0.5
DEFAULT_MAX_COMPLETION_TOKENS = 4096
RETRYABLE_HTTP_STATUSES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

HttpTransport = Callable[[str, Mapping[str, str], bytes, float], tuple[int, bytes]]
Sleep = Callable[[float], None]


def _urllib_transport(
    url: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout_seconds: float,
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(response.status)
            return status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


@dataclass(frozen=True)
class OpenRouterCoachModelProvider:
    """OpenRouter adapter using the OpenAI-compatible chat completions shape."""

    api_key: str
    model: str = DEFAULT_OPENROUTER_MODEL
    endpoint: str = OPENROUTER_CHAT_COMPLETIONS_URL
    reasoning_effort: str | None = DEFAULT_REASONING_EFFORT
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS
    max_completion_tokens: int | None = DEFAULT_MAX_COMPLETION_TOKENS
    transport: HttpTransport = _urllib_transport
    sleep: Sleep = time.sleep

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative.")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be non-negative.")
        if self.max_completion_tokens is not None and self.max_completion_tokens <= 0:
            raise ValueError("max_completion_tokens must be positive when set.")

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @classmethod
    def from_env(
        cls,
        dotenv_path: str | Path | None = None,
        model: str | None = None,
    ) -> OpenRouterCoachModelProvider:
        api_key = openrouter_api_key(dotenv_path)
        return cls(
            api_key=api_key,
            model=model
            or os.environ.get("G6EXPLANATION_OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
            reasoning_effort=os.environ.get(
                "G6EXPLANATION_OPENROUTER_REASONING_EFFORT",
                DEFAULT_REASONING_EFFORT,
            ),
            timeout_seconds=_float_env(
                "G6EXPLANATION_OPENROUTER_TIMEOUT_SECONDS",
                DEFAULT_TIMEOUT_SECONDS,
            ),
            max_retries=_int_env("G6EXPLANATION_OPENROUTER_MAX_RETRIES", DEFAULT_MAX_RETRIES),
            retry_backoff_seconds=_float_env(
                "G6EXPLANATION_OPENROUTER_RETRY_BACKOFF_SECONDS",
                DEFAULT_RETRY_BACKOFF_SECONDS,
            ),
            max_completion_tokens=_int_env(
                "G6EXPLANATION_OPENROUTER_MAX_TOKENS",
                DEFAULT_MAX_COMPLETION_TOKENS,
            ),
        )

    def generate(self, prompt: CoachPrompt) -> CoachModelResponse:
        payload = self._payload(prompt)
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": "g6explanation",
        }
        last_error: str | None = None
        attempts = self.max_retries + 1
        for attempt_index in range(1, attempts + 1):
            try:
                status, response_body = self.transport(
                    self.endpoint,
                    headers,
                    body,
                    self.timeout_seconds,
                )
            except (OSError, urllib.error.URLError) as exc:
                last_error = f"request failed: {exc}"
                if attempt_index < attempts:
                    self._sleep_before_retry(attempt_index)
                    continue
                raise CoachModelError(
                    f"OpenRouter request failed after {attempts} attempts: {exc}"
                ) from exc
            if status >= 400:
                body_text = _safe_body(response_body)
                last_error = f"HTTP {status}: {body_text}"
                if status in RETRYABLE_HTTP_STATUSES and attempt_index < attempts:
                    self._sleep_before_retry(attempt_index)
                    continue
                raise CoachModelError(
                    f"OpenRouter returned HTTP {status} after {attempt_index} attempts: {body_text}"
                )
            return _response_from_body(response_body, requested_model=self.model)
        raise CoachModelError(f"OpenRouter request failed: {last_error or 'unknown error'}")

    def _payload(self, prompt: CoachPrompt) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": prompt.messages,
            "response_format": prompt.response_format,
        }
        if self.max_completion_tokens is not None:
            payload["max_completion_tokens"] = self.max_completion_tokens
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort, "exclude": True}
        return payload

    def _sleep_before_retry(self, attempt_index: int) -> None:
        if self.retry_backoff_seconds == 0:
            return
        self.sleep(self.retry_backoff_seconds * attempt_index)


def openrouter_api_key(dotenv_path: str | Path | None = None) -> str:
    value = os.environ.get("OPENROUTER_API_KEY") or _dotenv_value(
        Path(dotenv_path) if dotenv_path is not None else Path.cwd() / ".env",
        "OPENROUTER_API_KEY",
    )
    if not value:
        raise CoachModelError("OPENROUTER_API_KEY is not set in the environment or .env.")
    return value


def _dotenv_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        if name.strip() != key:
            continue
        return raw_value.strip().strip("'\"")
    return None


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value is None else int(value)


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    return default if value is None else float(value)


def _response_from_body(body: bytes, requested_model: str) -> CoachModelResponse:
    try:
        data_object: object = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoachModelError("OpenRouter returned non-JSON response.") from exc
    if not isinstance(data_object, dict):
        raise CoachModelError("OpenRouter response was not an object.")
    data = cast(dict[str, object], data_object)
    choices_object = data.get("choices")
    if not isinstance(choices_object, list) or not choices_object:
        raise CoachModelError("OpenRouter response did not include choices.")
    choices = cast(list[object], choices_object)
    first_choice_object = choices[0]
    if not isinstance(first_choice_object, dict):
        raise CoachModelError("OpenRouter first choice was not an object.")
    first_choice = cast(dict[str, object], first_choice_object)
    message_object = first_choice.get("message")
    if not isinstance(message_object, dict):
        raise CoachModelError("OpenRouter first choice did not include a message.")
    message = cast(dict[str, object], message_object)
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise CoachModelError("OpenRouter message content was empty.")

    response_id_object = data.get("id")
    response_id = response_id_object if isinstance(response_id_object, str) else None
    model_object = data.get("model")
    returned_model = model_object if isinstance(model_object, str) else requested_model
    finish_reason_object = first_choice.get("finish_reason")
    finish_reason = finish_reason_object if isinstance(finish_reason_object, str) else None
    usage_object = data.get("usage")
    usage = cast(dict[str, Any], usage_object) if isinstance(usage_object, dict) else None
    return CoachModelResponse(
        provider_name="openrouter",
        model=returned_model,
        content=content,
        response_id=response_id,
        finish_reason=finish_reason,
        usage=usage,
    )


def _safe_body(body: bytes) -> str:
    text = body.decode("utf-8", errors="replace").strip()
    return text[:500]
