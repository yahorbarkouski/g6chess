"""Contracts for user-requested game imports before analysis."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from g6explanation.context_engine.contracts import (
    ContextContract,
    PlayerLevel,
    SignificanceLabel,
)
from g6explanation.game_analysis.contracts import GameAnalysisGame

GameImportSource: TypeAlias = Literal[
    "chess_com_live_url",
    "lichess_game_url",
    "lichess_study_chapter_url",
    "pgn",
]


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


class GameAnalysisImportOptions(ContextContract):
    """Options shared by every imported-analysis request variant."""

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


class ChessComLiveImportRequest(GameAnalysisImportOptions):
    """Import one finished Chess.com live-game URL."""

    source: Literal["chess_com_live_url"]
    url: str = Field(min_length=1, max_length=8192)


class LichessGameImportRequest(GameAnalysisImportOptions):
    """Import one finished public Lichess game URL."""

    source: Literal["lichess_game_url"]
    url: str = Field(min_length=1, max_length=8192)


class LichessStudyChapterImportRequest(GameAnalysisImportOptions):
    """Import one public Lichess study chapter URL."""

    source: Literal["lichess_study_chapter_url"]
    url: str = Field(min_length=1, max_length=8192)


class PgnImportRequest(GameAnalysisImportOptions):
    """Import one caller-supplied PGN."""

    source: Literal["pgn"]
    pgn: str = Field(min_length=1, max_length=131072)


GameAnalysisImportRequest: TypeAlias = Annotated[
    ChessComLiveImportRequest
    | LichessGameImportRequest
    | LichessStudyChapterImportRequest
    | PgnImportRequest,
    Field(discriminator="source"),
]


class GameAnalysisImportResponse(ContextContract):
    """Response for an imported game-analysis job."""

    analysis_id: str
    status: Literal["pending", "running", "succeeded", "failed"]
    status_url: str
    source: ImportedGameMetadata
    game: GameAnalysisGame


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
