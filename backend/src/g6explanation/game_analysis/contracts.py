"""Contracts for asynchronous full-game analysis jobs."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from g6explanation.context_engine.contracts import (
    ColorName,
    ContextContract,
    ContextResult,
    MoveBeauty,
    MoveQualityLabel,
    MoveSignificance,
    PlayerLevel,
    SignificanceLabel,
)
from g6explanation.explanation_generation.contracts import (
    ExplanationLineCard,
    ExplanationSegment,
)

GAME_ANALYSIS_SNAPSHOT_VERSION = "game_analysis_snapshot.v1"

GameAnalysisStatus: TypeAlias = Literal["pending", "running", "succeeded", "failed"]
GameMoveAnalysisState: TypeAlias = Literal[
    "context_ready",
    "explained",
    "explanation_failed",
]


def _default_critical_significance() -> list[SignificanceLabel]:
    return ["critical"]


class GameAnalysisStartRequest(ContextContract):
    """Public request for starting a full-game analysis job."""

    pgn: str = Field(min_length=1)
    player_level: PlayerLevel | None = None
    white_player_level: PlayerLevel | None = None
    black_player_level: PlayerLevel | None = None
    time_control: str = "unknown"
    explain_significance: list[SignificanceLabel] = Field(
        default_factory=_default_critical_significance
    )
    include_context: bool = False
    use_baseline_fallback: bool = False

    @model_validator(mode="after")
    def _validate_player_levels(self) -> GameAnalysisStartRequest:
        if not self.explain_significance:
            raise ValueError("explain_significance must include at least one label.")
        if self.player_level is not None:
            return self
        if self.white_player_level is None or self.black_player_level is None:
            raise ValueError(
                "Provide player_level for both sides or explicit white_player_level "
                "and black_player_level."
            )
        return self

    def level_for(self, player_color: ColorName) -> PlayerLevel:
        if self.player_level is not None:
            return self.player_level
        if player_color == "white" and self.white_player_level is not None:
            return self.white_player_level
        if player_color == "black" and self.black_player_level is not None:
            return self.black_player_level
        raise ValueError(f"Missing player level for {player_color}.")


class GameMoveAnalysis(ContextContract):
    """Current analysis state for one ply."""

    ply: int = Field(ge=1)
    san: str
    uci: str
    player_color: ColorName
    state: GameMoveAnalysisState
    requires_explanation: bool
    quality: MoveQualityLabel
    significance: MoveSignificance
    beauty: MoveBeauty
    context_latency_seconds: float
    clock_before_seconds: float | None = None
    remaining_clock_seconds: float | None = None
    think_time_seconds: float | None = None
    explanation: str | None = None
    explanation_segments: list[ExplanationSegment] = Field(default_factory=list[ExplanationSegment])
    explanation_line_cards: list[ExplanationLineCard] = Field(
        default_factory=list[ExplanationLineCard]
    )
    explanation_latency_seconds: float | None = None
    explanation_attempts: int = 0
    explanation_model: str | None = None
    explanation_error: str | None = None
    context: ContextResult | None = None


class GameAnalysisSnapshot(ContextContract):
    """Redis-persisted snapshot returned by the polling endpoint."""

    snapshot_version: str = GAME_ANALYSIS_SNAPSHOT_VERSION
    analysis_id: str
    status: GameAnalysisStatus
    total_plies: int = Field(ge=0)
    context_completed: int = Field(ge=0)
    explanation_required: int = Field(ge=0)
    explanation_completed: int = Field(ge=0)
    explanation_failed: int = Field(ge=0)
    explain_significance: list[SignificanceLabel] = Field(default_factory=list[SignificanceLabel])
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    moves: list[GameMoveAnalysis] = Field(default_factory=list[GameMoveAnalysis])


class GameAnalysisStartResponse(ContextContract):
    """Response for a submitted full-game analysis job."""

    analysis_id: str
    status: GameAnalysisStatus
    status_url: str
