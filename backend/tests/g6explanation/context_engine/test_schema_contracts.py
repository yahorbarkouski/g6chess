from __future__ import annotations

import pytest
from pydantic import ValidationError

from g6explanation.context_engine.models import (
    CandidateMove,
    EvidencePacket,
    LLMContext,
    MoveQuality,
    Score,
    VerificationResult,
)


def test_context_models_export_json_schema() -> None:
    for model in [EvidencePacket, LLMContext, MoveQuality, CandidateMove, VerificationResult]:
        schema = model.json_schema()

        assert schema["type"] == "object"
        assert "properties" in schema


def test_score_contract_rejects_mixed_centipawn_and_mate_fields() -> None:
    with pytest.raises(ValidationError):
        Score(kind="cp", value=10, mate_in=2, mate_for="player")

    with pytest.raises(ValidationError):
        Score(kind="mate", value=10, mate_in=2, mate_for="player")
