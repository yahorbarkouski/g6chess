from __future__ import annotations

import json
import urllib.error
from collections.abc import Mapping
from pathlib import Path

import pytest

from g6explanation.explanation_generation.exceptions import CoachModelError
from g6explanation.explanation_generation.openrouter_chat import (
    DEFAULT_MAX_COMPLETION_TOKENS,
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_TIMEOUT_SECONDS,
    OpenRouterCoachModelProvider,
    openrouter_api_key,
)
from g6explanation.explanation_generation.prompt_builder import build_coach_prompt
from tests.g6explanation.explanation_generation.helpers import best_context


def test_openrouter_provider_sends_structured_output_request() -> None:
    captured: dict[str, object] = {}

    def transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        captured["url"] = url
        captured["headers"] = dict(headers)
        captured["payload"] = json.loads(body.decode("utf-8"))
        captured["timeout_seconds"] = timeout_seconds
        response = {
            "id": "gen-test",
            "model": DEFAULT_OPENROUTER_MODEL,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": _coach_response("e4 claimed the center."),
                    },
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        }
        return 200, json.dumps(response).encode("utf-8")

    provider = OpenRouterCoachModelProvider(api_key="test-key", transport=transport)
    prompt = build_coach_prompt(best_context())

    response = provider.generate(prompt)

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == DEFAULT_OPENROUTER_MODEL
    assert payload["response_format"] == prompt.response_format
    assert payload["reasoning"] == {
        "effort": DEFAULT_REASONING_EFFORT,
        "exclude": True,
    }
    assert payload["max_completion_tokens"] == DEFAULT_MAX_COMPLETION_TOKENS
    assert response.content == _coach_response("e4 claimed the center.")


def test_openrouter_provider_loads_api_key_from_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENROUTER_API_KEY='dotenv-key'\n", encoding="utf-8")

    assert openrouter_api_key(dotenv) == "dotenv-key"


def test_openrouter_provider_loads_resilience_settings_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENROUTER_API_KEY=dotenv-key\n", encoding="utf-8")
    monkeypatch.setenv("G6EXPLANATION_OPENROUTER_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("G6EXPLANATION_OPENROUTER_MAX_RETRIES", "3")
    monkeypatch.setenv("G6EXPLANATION_OPENROUTER_RETRY_BACKOFF_SECONDS", "0.25")
    monkeypatch.setenv("G6EXPLANATION_OPENROUTER_MAX_TOKENS", "900")

    provider = OpenRouterCoachModelProvider.from_env(dotenv)

    assert provider.timeout_seconds == 12.5
    assert provider.max_retries == 3
    assert provider.retry_backoff_seconds == 0.25
    assert provider.max_completion_tokens == 900


def test_openrouter_provider_raises_for_missing_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(CoachModelError):
        openrouter_api_key(tmp_path / ".env")


def test_openrouter_provider_retries_retryable_http_status() -> None:
    calls = 0

    def transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return 503, b"temporarily unavailable"
        return 200, _openrouter_response()

    provider = OpenRouterCoachModelProvider(
        api_key="test-key",
        max_retries=1,
        retry_backoff_seconds=0,
        transport=transport,
    )

    response = provider.generate(build_coach_prompt(best_context()))

    assert calls == 2
    assert response.response_id == "gen-test"


def test_openrouter_provider_does_not_retry_non_retryable_http_status() -> None:
    calls = 0

    def transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        nonlocal calls
        calls += 1
        return 400, b"bad request"

    provider = OpenRouterCoachModelProvider(
        api_key="test-key",
        max_retries=3,
        retry_backoff_seconds=0,
        transport=transport,
    )

    with pytest.raises(CoachModelError, match="HTTP 400 after 1 attempts"):
        provider.generate(build_coach_prompt(best_context()))

    assert calls == 1


def test_openrouter_provider_retries_transport_errors() -> None:
    calls = 0

    def transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("timeout")

    provider = OpenRouterCoachModelProvider(
        api_key="test-key",
        max_retries=2,
        retry_backoff_seconds=0,
        transport=transport,
    )

    with pytest.raises(CoachModelError, match="after 3 attempts"):
        provider.generate(build_coach_prompt(best_context()))

    assert calls == 3


def test_openrouter_provider_validates_resilience_settings() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        OpenRouterCoachModelProvider(api_key="test-key", timeout_seconds=0)
    with pytest.raises(ValueError, match="max_retries"):
        OpenRouterCoachModelProvider(api_key="test-key", max_retries=-1)
    with pytest.raises(ValueError, match="retry_backoff_seconds"):
        OpenRouterCoachModelProvider(api_key="test-key", retry_backoff_seconds=-1)
    with pytest.raises(ValueError, match="max_completion_tokens"):
        OpenRouterCoachModelProvider(api_key="test-key", max_completion_tokens=0)


def test_openrouter_provider_defaults_timeout_policy() -> None:
    provider = OpenRouterCoachModelProvider(api_key="test-key")

    assert provider.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert provider.max_retries == 1
    assert provider.max_completion_tokens == DEFAULT_MAX_COMPLETION_TOKENS
    assert provider.reasoning_effort == DEFAULT_REASONING_EFFORT == "high"


def _openrouter_response() -> bytes:
    response = {
        "id": "gen-test",
        "model": DEFAULT_OPENROUTER_MODEL,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": _coach_response("e4 claimed the center."),
                },
            }
        ],
    }
    return json.dumps(response).encode("utf-8")


def _coach_response(text: str) -> str:
    return json.dumps(
        {
            "segments": [{"text": text, "line_card_id": None}],
            "line_cards": [],
        }
    )
