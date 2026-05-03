from __future__ import annotations

from g6explanation.explanation_generation.baseline_renderer import render_baseline_explanation
from g6explanation.explanation_generation.explanation_verification import ExplanationVerifier
from tests.g6explanation.explanation_generation.helpers import (
    best_context,
    hard_engine_best_context,
    mistake_context_with_practical_alternative,
)


def test_baseline_renderer_outputs_verified_best_move_explanation() -> None:
    context = best_context()

    output = render_baseline_explanation(context)
    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed
    assert "e4" in output.explanation


def test_baseline_renderer_caveats_hard_engine_move() -> None:
    context = hard_engine_best_context()

    output = render_baseline_explanation(context)
    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed
    assert "hard" in output.explanation.lower()


def test_baseline_renderer_uses_practical_alternative_without_judging_model_output() -> None:
    context = mistake_context_with_practical_alternative()

    output = render_baseline_explanation(context)
    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed
    assert "mistake" in output.explanation.lower()
    assert "Nf3" in output.explanation
