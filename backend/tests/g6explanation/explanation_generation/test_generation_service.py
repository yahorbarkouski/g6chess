from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import cast

import pytest

from g6explanation.context_engine import ContextResult, MoveContextBuilder, MoveContextRequest
from g6explanation.explanation_generation.contracts import CoachModelResponse, CoachPrompt
from g6explanation.explanation_generation.exceptions import (
    ExplanationInputError,
    ExplanationVerificationError,
)
from g6explanation.explanation_generation.generation_service import ExplanationService, explain_move
from tests.g6explanation.context_engine.helpers import StaticAnalysisProvider
from tests.g6explanation.explanation_generation.helpers import (
    mistake_context_with_practical_alternative,
)


@dataclass
class StaticCoachProvider:
    responses: list[str]
    provider_name: str = "static-coach"
    model: str = "static-model"
    prompts: list[CoachPrompt] = field(default_factory=list[CoachPrompt])

    def generate(self, prompt: CoachPrompt) -> CoachModelResponse:
        self.prompts.append(prompt)
        content = self.responses.pop(0)
        return CoachModelResponse(
            provider_name=self.provider_name,
            model=self.model,
            content=content,
            response_id=f"response-{len(self.prompts)}",
            finish_reason="stop",
        )


@dataclass
class RecordingContextBuilder:
    context: ContextResult
    requests: list[MoveContextRequest] = field(default_factory=list[MoveContextRequest])

    def build(self, request: MoveContextRequest) -> ContextResult:
        self.requests.append(request)
        return self.context


def test_service_returns_verified_model_output_without_baseline_comparison() -> None:
    context = mistake_context_with_practical_alternative()
    provider = StaticCoachProvider(
        [
            _response(
                "g4 was a mistake because it let the opponent improve with e5. "
                "Nf3 was a practical alternative that stayed close to best play."
            ),
            _response(
                "g4 was a mistake because it let the opponent improve with e5. "
                "Nf3 was a practical alternative that stayed close to best play."
            ),
        ]
    )
    service = ExplanationService(
        context_builder=_unused_builder(),
        coach_provider=provider,
    )

    result = service.explain_context(context)

    assert result.finish_reason == "model"
    assert not result.used_fallback
    assert result.verification.passed
    assert len(provider.prompts) == 1


def test_prompt_spells_out_style_and_recommendation_policy_contract() -> None:
    context = mistake_context_with_practical_alternative()
    provider = StaticCoachProvider(
        [
            _response(
                "g4 was a mistake because it let the opponent improve with e5. "
                "Nf3 was a practical alternative that stayed close to best play."
            ),
            _response(
                "g4 was a mistake because it let the opponent improve with e5. "
                "Nf3 was a practical alternative that stayed close to best play."
            ),
        ]
    )
    service = ExplanationService(
        context_builder=_unused_builder(),
        coach_provider=provider,
    )

    result = service.explain_context(context)
    prompt_payload = provider.prompts[0].messages[1]["content"]

    assert result.prompt_version == "single_move_coach.v10"
    assert "segments and line_cards" in prompt_payload
    assert "line_card_anchor" in prompt_payload
    assert "exact short phrase the UI should highlight" in prompt_payload
    assert "Do not split sentences into tiny text fragments" in prompt_payload
    assert "line_evidence" in prompt_payload
    assert "roughly 35 to 90 visible words" in prompt_payload
    assert "why that reply is good for" in prompt_payload
    assert "Use a neutral explanatory voice" in prompt_payload
    assert "Write like a compact game-review note" in prompt_payload
    assert "Avoid rigid templates" in prompt_payload
    assert "avoid repeated 'MOVE was QUALITY because'" in prompt_payload
    assert "usually lead with the concrete chess function" in prompt_payload
    assert "For routine best moves" in prompt_payload
    assert "avoid the phrase 'critical best move'" in prompt_payload
    assert "Do not use generic value-preservation filler" in prompt_payload
    assert "Do not lean on 'no sharper alternative needed'" in prompt_payload
    assert "Choose the smallest sufficient teaching point" in prompt_payload
    assert "For low-significance best" in prompt_payload
    assert "Do not call a practical_alternative a better move" in prompt_payload
    assert "Do not expose internal wording" in prompt_payload
    assert "engine best move" in prompt_payload
    assert "recommend_directly allows direct advice" in prompt_payload
    assert "do_not_recommend must not be called" in prompt_payload
    assert "Do not use named tactic labels" in prompt_payload


def test_service_retries_with_verifier_failures() -> None:
    context = mistake_context_with_practical_alternative()
    provider = StaticCoachProvider(
        [
            _response("g4 was a mistake, and a3 was the better move."),
            _response(
                "g4 was a mistake because it let the opponent improve with e5. "
                "Nf3 was a practical alternative that stayed close to best play."
            ),
        ]
    )
    service = ExplanationService(
        context_builder=_unused_builder(),
        coach_provider=provider,
    )

    result = service.explain_context(context)

    assert result.finish_reason == "model"
    assert [attempt.verification_passed for attempt in result.attempts] == [False, True]
    assert result.attempts[0].explanation == "g4 was a mistake, and a3 was the better move."
    assert len(provider.prompts) == 2
    assert "previous_verifier_failures" in provider.prompts[1].messages[1]["content"]
    assert "retry_repair_instructions" in provider.prompts[1].messages[1]["content"]


def test_service_uses_verified_fallback_after_unverified_model_attempts() -> None:
    context = mistake_context_with_practical_alternative()
    provider = StaticCoachProvider(
        [
            _response("g4 was a mistake, and a3 was the better move."),
            _response("g4 was a mistake because it loses a queen."),
        ]
    )
    service = ExplanationService(
        context_builder=_unused_builder(),
        coach_provider=provider,
    )

    result = service.explain_context(context)

    assert result.finish_reason == "fallback"
    assert result.used_fallback
    assert result.verification.passed
    assert [attempt.verification_passed for attempt in result.attempts] == [False, False]


def test_service_exposes_attempts_on_controlled_verification_failure() -> None:
    context = mistake_context_with_practical_alternative()
    provider = StaticCoachProvider(
        [
            _response("g4 was a mistake, and a3 was the better move."),
        ]
    )
    service = ExplanationService(
        context_builder=_unused_builder(),
        coach_provider=provider,
        max_model_attempts=1,
        use_baseline_fallback=False,
    )

    with pytest.raises(ExplanationVerificationError) as exc_info:
        service.explain_context(context)

    assert "mentioned_move_unsupported" in exc_info.value.attempts[0].failure_codes
    assert exc_info.value.attempts[0].explanation == (
        "g4 was a mistake, and a3 was the better move."
    )


def test_public_explain_move_accepts_fen_played_move_and_rating() -> None:
    context = mistake_context_with_practical_alternative()
    context_builder = RecordingContextBuilder(context)
    provider = StaticCoachProvider(
        [
            _response(
                "g4 was a mistake because it let the opponent improve with e5. "
                "Nf3 was a practical alternative that stayed close to best play."
            )
        ]
    )

    explanation = explain_move(
        context.evidence.position.fen_before,
        "g2g4",
        1250,
        player_color="white",
        time_control="blitz",
        context_builder=cast(MoveContextBuilder, context_builder),
        coach_provider=provider,
    )

    assert explanation.startswith("g4 was a mistake")
    assert context_builder.requests[0].fen_before == context.evidence.position.fen_before
    assert context_builder.requests[0].played_move == "g2g4"
    assert context_builder.requests[0].player_level.value == 1250


def test_public_explain_move_accepts_existing_request() -> None:
    context = mistake_context_with_practical_alternative()
    context_builder = RecordingContextBuilder(context)
    provider = StaticCoachProvider(
        [
            _response(
                "g4 was a mistake because it let the opponent improve with e5. "
                "Nf3 was a practical alternative that stayed close to best play."
            )
        ]
    )

    explanation = explain_move(
        context.evidence.request,
        context_builder=cast(MoveContextBuilder, context_builder),
        coach_provider=provider,
    )

    assert explanation.startswith("g4 was a mistake")
    assert context_builder.requests == [context.evidence.request]


def test_public_explain_move_accepts_explicit_pgn_ply() -> None:
    context = mistake_context_with_practical_alternative()
    context_builder = RecordingContextBuilder(context)
    provider = StaticCoachProvider(
        [
            _response(
                "g4 was a mistake because it let the opponent improve with e5. "
                "Nf3 was a practical alternative that stayed close to best play."
            )
        ]
    )

    explanation = explain_move(
        "1. f3 e5 2. g4",
        player_level=900,
        player_color="white",
        pgn_ply=3,
        time_control="blitz",
        context_builder=cast(MoveContextBuilder, context_builder),
        coach_provider=provider,
    )

    assert explanation.startswith("g4 was a mistake")
    assert context_builder.requests[0].pgn == "1. f3 e5 2. g4"
    assert context_builder.requests[0].ply == 3
    assert context_builder.requests[0].played_move is None


def test_public_explain_move_rejects_ambiguous_input() -> None:
    context = mistake_context_with_practical_alternative()

    with pytest.raises(ExplanationInputError):
        explain_move(
            context.evidence.request,
            "g2g4",
            1250,
            player_color="white",
            context_builder=_unused_builder(),
            coach_provider=StaticCoachProvider([]),
        )


def test_public_explain_move_requires_player_fields_for_fen_input() -> None:
    context = mistake_context_with_practical_alternative()

    with pytest.raises(ExplanationInputError):
        explain_move(
            context.evidence.position.fen_before,
            "g2g4",
            context_builder=_unused_builder(),
            coach_provider=StaticCoachProvider([]),
        )


def _unused_builder() -> MoveContextBuilder:
    context = mistake_context_with_practical_alternative()
    return MoveContextBuilder(StaticAnalysisProvider(context.evidence.engine))


def _response(text: str) -> str:
    return json.dumps(
        {
            "segments": [{"text": text, "line_card_id": None}],
            "line_cards": [],
        }
    )
