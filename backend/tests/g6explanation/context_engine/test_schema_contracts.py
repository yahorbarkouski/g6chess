from __future__ import annotations

import pytest
from pydantic import ValidationError

from g6explanation.context_engine.contracts import (
    CandidateMove,
    ContextContract,
    EvidencePacket,
    KeyMoveContext,
    LLMContext,
    MoveQuality,
    PlayerLevel,
    Score,
    VerificationResult,
)


def test_context_models_export_json_schema() -> None:
    models: list[type[ContextContract]] = [
        EvidencePacket,
        LLMContext,
        MoveQuality,
        CandidateMove,
        VerificationResult,
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
