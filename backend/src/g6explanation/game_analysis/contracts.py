"""Contracts for asynchronous full-game analysis jobs."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from g6explanation.context_engine.contracts import (
    CandidateMove,
    ColorName,
    ConceptClaim,
    ContextContract,
    ContextResult,
    EngineLine,
    KeyMoveContext,
    MainPoint,
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

GAME_ANALYSIS_SNAPSHOT_VERSION = "game_analysis_snapshot.v2"

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

    pgn: str = Field(min_length=1, max_length=131072)
    player_level: PlayerLevel | None = None
    white_player_level: PlayerLevel | None = None
    black_player_level: PlayerLevel | None = None
    time_control: str = "unknown"
    explain_significance: list[SignificanceLabel] = Field(
        default_factory=_default_critical_significance
    )
    include_context: bool = False
    use_baseline_fallback: bool = False
    turnstile_token: str | None = Field(default=None, max_length=4096)

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


class BookLineMove(ContextContract):
    """One SAN/UCI move in an opening-book continuation."""

    san: str
    uci: str


class BookLine(ContextContract):
    """Opening-book continuation from the selected position."""

    moves: list[BookLineMove]
    weight: int = Field(ge=0)
    opening_name: str | None = None
    eco: str | None = None


class OpeningBookMetadata(ContextContract):
    """Opening-book status attached to a game-analysis ply."""

    is_book_move: bool
    is_novelty: bool = False
    book_lines: list[BookLine] = Field(default_factory=list[BookLine])
    opening_name: str | None = None
    eco: str | None = None


class GameMainlineMove(ContextContract):
    """PGN-derived move data that is safe to expose before analysis completes."""

    ply: int = Field(ge=1)
    move_number: int = Field(ge=1)
    player_color: ColorName
    san: str
    uci: str
    fen_before: str
    fen_after: str
    clock_before_seconds: float | None = None
    remaining_clock_seconds: float | None = None
    think_time_seconds: float | None = None


class GameAnalysisGame(ContextContract):
    """Board-renderable game skeleton for an analysis job."""

    total_plies: int = Field(ge=0)
    moves: list[GameMainlineMove] = Field(default_factory=list[GameMainlineMove])


class GameMoveAnalysis(ContextContract):
    """Current analysis state for one ply."""

    ply: int = Field(ge=1)
    move_number: int | None = Field(default=None, ge=1)
    san: str
    uci: str
    player_color: ColorName
    fen_before: str | None = None
    fen_after: str | None = None
    state: GameMoveAnalysisState
    requires_explanation: bool
    quality: MoveQualityLabel
    significance: MoveSignificance
    beauty: MoveBeauty
    quality_severity_text: str | None = None
    score_loss_vs_best_cp: int | None = None
    phase: str | None = None
    legal_move_count: int | None = Field(default=None, ge=0)
    context_version: str | None = None
    verifier_version: str | None = None
    engine_version: str | None = None
    engine_top_lines: list[EngineLine] = Field(default_factory=list[EngineLine])
    engine_played_line: EngineLine | None = None
    main_point: MainPoint | None = None
    concept_claims: list[ConceptClaim] = Field(default_factory=list[ConceptClaim])
    allowed_claims: list[str] = Field(default_factory=list[str])
    human_common_candidate: CandidateMove | None = None
    player_level: str | None = None
    time_situation: str | None = None
    best_or_key_move: KeyMoveContext | None = None
    context_latency_seconds: float
    clock_before_seconds: float | None = None
    remaining_clock_seconds: float | None = None
    think_time_seconds: float | None = None
    opening_book: OpeningBookMetadata | None = None
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
    game: GameAnalysisGame | None = None
    moves: list[GameMoveAnalysis] = Field(default_factory=list[GameMoveAnalysis])


class GameAnalysisStartResponse(ContextContract):
    """Response for a submitted full-game analysis job."""

    analysis_id: str
    status: GameAnalysisStatus
    status_url: str
    game: GameAnalysisGame
