"""OpenRouter chat-completions adapter for coach explanations."""

from __future__ import annotations

import json
import os
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

HttpTransport = Callable[[str, Mapping[str, str], bytes, float], tuple[int, bytes]]


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
    timeout_seconds: float = 90.0
    max_completion_tokens: int = 700
    transport: HttpTransport = _urllib_transport

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
        )

    def generate(self, prompt: CoachPrompt) -> CoachModelResponse:
        payload = self._payload(prompt)
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": "g6explanation",
        }
        try:
            status, response_body = self.transport(
                self.endpoint,
                headers,
                body,
                self.timeout_seconds,
            )
        except (OSError, urllib.error.URLError) as exc:
            raise CoachModelError(f"OpenRouter request failed: {exc}") from exc
        if status >= 400:
            raise CoachModelError(f"OpenRouter returned HTTP {status}: {_safe_body(response_body)}")
        return _response_from_body(response_body, requested_model=self.model)

    def _payload(self, prompt: CoachPrompt) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": prompt.messages,
            "response_format": prompt.response_format,
            "max_completion_tokens": self.max_completion_tokens,
        }
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort, "exclude": True}
        return payload


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
