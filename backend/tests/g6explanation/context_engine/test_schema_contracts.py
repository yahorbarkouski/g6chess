from __future__ import annotations

import pytest
from pydantic import ValidationError

from g6explanation.context_engine.contracts import (
    CandidateMove,
    ContextContract,
    EvidencePacket,
    KeyMoveContext,
    LLMContext,
    MoveBeauty,
    MoveQuality,
    PlayerLevel,
    Score,
    VerificationIssue,
    VerificationResult,
    Wdl,
    WdlDelta,
)


def test_context_models_export_json_schema() -> None:
    models: list[type[ContextContract]] = [
        EvidencePacket,
        LLMContext,
        MoveQuality,
        MoveBeauty,
        CandidateMove,
        VerificationIssue,
        VerificationResult,
        Wdl,
        WdlDelta,
    ]
    for model in models:
        schema = model.json_schema()

        assert schema["type"] == "object"
        assert "properties" in schema


def test_score_contract_rejects_mixed_centipawn_and_mate_fields() -> None:
    with pytest.raises(ValidationError):
        Score(kind="cp", value=10, mate_in=2, mate_for="player")

    with pytest.raises(ValidationError):
        Score(kind="mate", value=10, mate_in=2, mate_for="player")


def test_wdl_contract_rejects_non_absolute_values() -> None:
    with pytest.raises(ValidationError):
        Wdl(win=1500, draw=-500, loss=0)

    with pytest.raises(ValidationError):
        Wdl(win=500, draw=400, loss=50)


def test_wdl_delta_contract_accepts_signed_zero_sum_values() -> None:
    delta = WdlDelta(win=-300, draw=100, loss=200)

    assert delta.to_dict() == {"win": -300, "draw": 100, "loss": 200}

    with pytest.raises(ValidationError):
        WdlDelta(win=-300, draw=0, loss=200)


def test_player_level_contract_rejects_rating_without_integer_value() -> None:
    with pytest.raises(ValidationError):
        PlayerLevel.model_validate({"kind": "rating", "value": "1200"})


def test_candidate_contract_rejects_unknown_role() -> None:
    candidate = {
        "san": "e4",
        "uci": "e2e4",
        "roles": ["vague_role"],
        "engine_rank": 1,
        "score": {"kind": "cp", "value": 10},
        "score_loss_vs_best_cp": 0,
        "player_level_probability": None,
        "plus_400_probability": None,
        "time_adjusted_findability": "unknown",
        "forcing_tier": "quiet",
        "findability_source": "unknown",
        "findability_confidence": "none",
        "teachable_skill_gap": False,
        "practicality": "clear_recommendation",
        "recommendation_policy": "recommend_directly",
    }

    with pytest.raises(ValidationError):
        CandidateMove.model_validate(candidate)


def test_key_move_context_contract_is_strict() -> None:
    context = KeyMoveContext(
        move="e4",
        practicality="clear_recommendation",
        findability="findable",
        reason="it is the engine's best move",
        recommendation_policy="recommend_directly",
    )

    assert context.to_dict()["move"] == "e4"

    with pytest.raises(ValidationError):
        KeyMoveContext.model_validate(
            {
                "move": "e4",
                "practicality": "clear_recommendation",
                "findability": "findable",
                "reason": "it is the engine's best move",
                "recommendation_policy": "recommend_directly",
                "unsupported": True,
            }
        )
