from __future__ import annotations

from dataclasses import dataclass, field

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.explanation_generation.contracts import CoachModelResponse, CoachPrompt
from g6explanation.explanation_generation.generation_service import ExplanationService
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


def test_service_returns_verified_model_output_without_baseline_comparison() -> None:
    context = mistake_context_with_practical_alternative()
    provider = StaticCoachProvider(
        [
            (
                '{"explanation":"g4 was a mistake because it let the opponent improve with e5. '
                'Nf3 was a practical alternative close to the engine best move."}'
            )
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


def test_service_retries_with_verifier_failures() -> None:
    context = mistake_context_with_practical_alternative()
    provider = StaticCoachProvider(
        [
            '{"explanation":"g4 was a mistake, and a3 was the better move."}',
            (
                '{"explanation":"g4 was a mistake because it let the opponent improve with e5. '
                'Nf3 was a practical alternative close to the engine best move."}'
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
    assert len(provider.prompts) == 2
    assert "previous_verifier_failures" in provider.prompts[1].messages[1]["content"]


def test_service_uses_verified_fallback_after_unverified_model_attempts() -> None:
    context = mistake_context_with_practical_alternative()
    provider = StaticCoachProvider(
        [
            '{"explanation":"g4 was a mistake, and a3 was the better move."}',
            '{"explanation":"g4 was a mistake because it loses a queen."}',
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


def _unused_builder() -> MoveContextBuilder:
    context = mistake_context_with_practical_alternative()
    return MoveContextBuilder(StaticAnalysisProvider(context.evidence.engine))
