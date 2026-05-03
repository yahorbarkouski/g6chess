from __future__ import annotations

from typing import cast

from g6explanation.context_engine.contracts import LLMContext
from g6explanation.real_game_evaluation import (
    CHESS_COM_REQUIRES_AUTHORIZATION_SOURCE,
    PROJECT_SYNTHETIC_SOURCE,
    ExplanationDataSource,
    ManualReviewCategory,
    RealExplanationEvalRecord,
    build_training_data_manifest,
)
from tests.g6explanation.explanation_generation.helpers import best_context

_DEFAULT_LLM_CONTEXT = object()


def test_training_manifest_includes_only_manually_accepted_verified_records() -> None:
    accepted = _record(case_id="accepted", manual_review_category="accepted")
    not_reviewed = _record(case_id="not-reviewed")
    fallback = _record(
        case_id="fallback",
        manual_review_category="accepted",
        used_fallback=True,
    )
    low_depth = _record(
        case_id="low-depth",
        manual_review_category="accepted",
        stockfish_depth=12,
    )

    manifest = build_training_data_manifest([accepted, not_reviewed, fallback, low_depth])

    assert manifest.entry_count == 1
    assert manifest.entries[0].case_id == "accepted"
    assert manifest.entries[0].source == PROJECT_SYNTHETIC_SOURCE
    assert manifest.entries[0].llm_context == accepted.llm_context
    assert manifest.entries[0].prompt_version == "single_move_coach.v8"
    assert manifest.entries[0].explanation == "e4 claims the center and opens lines for White."
    assert manifest.excluded_counts == {
        "fallback_or_unknown_finish": 1,
        "insufficient_stockfish_depth": 1,
        "not_manually_accepted": 1,
    }


def test_training_manifest_rejects_missing_model_or_explanation() -> None:
    missing_model = _record(
        case_id="missing-model",
        manual_review_category="accepted",
        model=None,
    )
    missing_explanation = _record(
        case_id="missing-explanation",
        manual_review_category="accepted",
        explanation=None,
    )

    manifest = build_training_data_manifest([missing_model, missing_explanation])

    assert manifest.entries == []
    assert manifest.excluded_counts == {
        "missing_explanation": 1,
        "missing_model_metadata": 1,
    }


def test_training_manifest_rejects_missing_source_context_or_generation_metadata() -> None:
    missing_source = _record(
        case_id="missing-source",
        manual_review_category="accepted",
        source=None,
    )
    blocked_source = _record(
        case_id="blocked-source",
        manual_review_category="accepted",
        source=CHESS_COM_REQUIRES_AUTHORIZATION_SOURCE,
    )
    missing_context = _record(
        case_id="missing-context",
        manual_review_category="accepted",
        llm_context=None,
    )
    missing_prompt = _record(
        case_id="missing-prompt",
        manual_review_category="accepted",
        prompt_version=None,
    )

    manifest = build_training_data_manifest(
        [missing_source, blocked_source, missing_context, missing_prompt]
    )

    assert manifest.entries == []
    assert manifest.excluded_counts == {
        "missing_generation_metadata": 1,
        "missing_llm_context": 1,
        "missing_source_rights": 1,
        "source_rights_do_not_allow_training": 1,
    }


def _record(
    *,
    case_id: str,
    manual_review_category: str = "not_reviewed",
    passed: bool = True,
    used_fallback: bool = False,
    stockfish_depth: int | None = 16,
    model: str | None = "openai/gpt-5.5-20260423",
    explanation: str | None = "e4 claims the center and opens lines for White.",
    source: ExplanationDataSource | None = PROJECT_SYNTHETIC_SOURCE,
    llm_context: LLMContext | None | object = _DEFAULT_LLM_CONTEXT,
    prompt_version: str | None = "single_move_coach.v8",
) -> RealExplanationEvalRecord:
    resolved_llm_context = (
        best_context().llm_context if llm_context is _DEFAULT_LLM_CONTEXT else llm_context
    )
    assert resolved_llm_context is None or isinstance(resolved_llm_context, LLMContext)
    return RealExplanationEvalRecord(
        case_id=case_id,
        description=f"{case_id} description",
        tags=["synthetic"],
        source=source,
        passed=passed,
        played_san="e4",
        played_uci="e2e4",
        player_color="white",
        quality="best",
        significance="low",
        beauty="low",
        stockfish_version="Stockfish 18",
        stockfish_depth=stockfish_depth,
        maia_candidate_count=2,
        maia_sources=["maia2_rapid"],
        provider_name="openrouter",
        model=model,
        schema_version="explanation_output.v1",
        context_version="move_context.v1",
        prompt_id="single_move_coach",
        prompt_version=prompt_version,
        verifier_version="explanation_verifier.v1",
        finish_reason="model",
        used_fallback=used_fallback,
        attempts=1,
        latency_seconds=1.0,
        llm_context=resolved_llm_context,
        explanation=explanation,
        manual_review_category=cast(ManualReviewCategory, manual_review_category),
    )
