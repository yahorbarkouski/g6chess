"""Contracts for user-requested game imports before analysis."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from g6explanation.context_engine.contracts import (
    ContextContract,
    PlayerLevel,
    SignificanceLabel,
)

GameImportSource: TypeAlias = Literal["chess_com_live_url", "pgn"]


def _default_critical_significance() -> list[SignificanceLabel]:
    return ["critical"]


class ImportedGameMetadata(ContextContract):
    """Source metadata for one user-requested imported game."""

    source: GameImportSource
    source_url: str | None = None
    external_game_id: str | None = None
    title: str
    white_username: str | None = None
    black_username: str | None = None
    white_rating: int | None = None
    black_rating: int | None = None
    time_control: str | None = None
    result: str | None = None
    allows_global_training: bool = False
    rights_basis: str = (
        "User-requested analysis input only; not eligible for global model training "
        "without explicit source rights."
    )


class ImportedGame(ContextContract):
    """Canonical PGN plus source metadata ready for game analysis."""

    pgn: str
    metadata: ImportedGameMetadata


class GameAnalysisImportRequest(ContextContract):
    """Request for resolving/importing a game and starting analysis."""

    source: GameImportSource
    url: str | None = Field(default=None, max_length=8192)
    pgn: str | None = Field(default=None, max_length=131072)
    player_level: PlayerLevel | None = None
    white_player_level: PlayerLevel | None = None
    black_player_level: PlayerLevel | None = None
    time_control: str | None = None
    explain_significance: list[SignificanceLabel] = Field(
        default_factory=_default_critical_significance
    )
    include_context: bool = False
    use_baseline_fallback: bool = False
    turnstile_token: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def _validate_source_payload(self) -> GameAnalysisImportRequest:
        if not self.explain_significance:
            raise ValueError("explain_significance must include at least one label.")
        if self.source == "chess_com_live_url":
            if self.url is None or not self.url.strip():
                raise ValueError("url is required for chess_com_live_url imports.")
            return self
        if self.pgn is None or not self.pgn.strip():
            raise ValueError("pgn is required for pgn imports.")
        return self


class GameAnalysisImportResponse(ContextContract):
    """Response for an imported game-analysis job."""

    analysis_id: str
    status: Literal["pending", "running", "succeeded", "failed"]
    status_url: str
    source: ImportedGameMetadata


def metadata_title(
    *,
    white_username: str | None,
    black_username: str | None,
    fallback: str,
) -> str:
    """Build a compact title from player names when available."""

    if white_username and black_username:
        return f"{white_username} vs {black_username}"
    return fallback
