from __future__ import annotations

from g6explanation.explanation_generation.baseline_renderer import render_baseline_explanation
from g6explanation.explanation_generation.explanation_verification import ExplanationVerifier
from tests.g6explanation.context_engine.helpers import (
    century_be6_queen_sacrifice_context,
    hung_rook_time_scramble_context,
    na4_tactical_objection_context,
)
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


def test_baseline_renderer_normalizes_legacy_findability_note_text() -> None:
    context = hard_engine_best_context()
    context = context.model_copy(
        update={
            "llm_context": context.llm_context.model_copy(
                update={"human_note": "e4 was engine_like to find in blitz."}
            )
        }
    )

    output = render_baseline_explanation(context)
    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed
    assert "engine-like" in output.explanation
    assert "engine_like" not in output.explanation


def test_baseline_renderer_uses_practical_alternative_without_judging_model_output() -> None:
    context = mistake_context_with_practical_alternative()

    output = render_baseline_explanation(context)
    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed
    assert "mistake" in output.explanation.lower()
    assert "Nf3" in output.explanation


def test_baseline_renderer_uses_tactical_objection_proof_when_supplied() -> None:
    context = na4_tactical_objection_context()

    output = render_baseline_explanation(context)
    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed
    assert "Nxa4 is met by Nxe4" in output.explanation
    assert "not simply free" in output.explanation


def test_baseline_renderer_keeps_simple_hung_piece_blunder_concise() -> None:
    context = hung_rook_time_scramble_context()

    output = render_baseline_explanation(context)
    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed
    assert output.explanation == "Rf4+ was a blunder because it hung the rook to gxf4."
    assert "follow-up" not in output.explanation
    assert "Kh7" not in output.explanation


def test_baseline_renderer_foregrounds_verified_queen_sacrifice() -> None:
    context = century_be6_queen_sacrifice_context()

    output = render_baseline_explanation(context)
    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed
    assert output.explanation == "Be6 set up a brilliant queen sacrifice on c5."
    assert "attacked the bishop" not in output.explanation
