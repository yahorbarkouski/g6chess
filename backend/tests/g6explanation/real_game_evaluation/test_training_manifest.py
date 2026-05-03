from __future__ import annotations

from typing import cast

from g6explanation.real_game_evaluation import (
    ManualReviewCategory,
    RealExplanationEvalRecord,
    build_training_data_manifest,
)


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
    assert manifest.entries[0].explanation == "e4 was the best move."
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


def _record(
    *,
    case_id: str,
    manual_review_category: str = "not_reviewed",
    passed: bool = True,
    used_fallback: bool = False,
    stockfish_depth: int | None = 16,
    model: str | None = "openai/gpt-5.5-20260423",
    explanation: str | None = "e4 was the best move.",
) -> RealExplanationEvalRecord:
    return RealExplanationEvalRecord(
        case_id=case_id,
        description=f"{case_id} description",
        tags=["synthetic"],
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
        finish_reason="model",
        used_fallback=used_fallback,
        attempts=1,
        latency_seconds=1.0,
        explanation=explanation,
        manual_review_category=cast(ManualReviewCategory, manual_review_category),
    )
