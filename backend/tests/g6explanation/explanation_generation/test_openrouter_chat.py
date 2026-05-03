from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from g6explanation.explanation_generation.exceptions import CoachModelError
from g6explanation.explanation_generation.openrouter_chat import (
    DEFAULT_OPENROUTER_MODEL,
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
                        "content": '{"explanation":"e4 was the best move."}',
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
    assert payload["reasoning"] == {"effort": "high", "exclude": True}
    assert response.content == '{"explanation":"e4 was the best move."}'


def test_openrouter_provider_loads_api_key_from_dotenv(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENROUTER_API_KEY='dotenv-key'\n", encoding="utf-8")

    assert openrouter_api_key(dotenv) == "dotenv-key"


def test_openrouter_provider_raises_for_missing_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(CoachModelError):
        openrouter_api_key(tmp_path / ".env")
