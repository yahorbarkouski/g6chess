"""Import orchestration that starts the existing game-analysis job."""

from __future__ import annotations

import io

import chess.pgn

from g6explanation.game_analysis import GameAnalysisService, GameAnalysisStartRequest
from g6explanation.game_imports.chess_com_live_games import ChessComLiveGameResolver
from g6explanation.game_imports.contracts import (
    GameAnalysisImportRequest,
    GameAnalysisImportResponse,
    ImportedGame,
    ImportedGameMetadata,
    level_from_rating,
    metadata_title,
)


class GameImportError(ValueError):
    """Raised when an imported game cannot be normalized for analysis."""


class GameImportService:
    """Resolve user-provided game sources and start game analysis."""

    def __init__(
        self,
        *,
        analysis_service: GameAnalysisService,
        chess_com_resolver: ChessComLiveGameResolver | None = None,
    ) -> None:
        self._analysis_service = analysis_service
        self._chess_com_resolver = chess_com_resolver or ChessComLiveGameResolver.from_env()

    def start(self, request: GameAnalysisImportRequest) -> GameAnalysisImportResponse:
        imported_game = self._imported_game(request)
        start_request = _analysis_request_from_import(imported_game, request)
        start_response = self._analysis_service.start(start_request)
        return GameAnalysisImportResponse(
            analysis_id=start_response.analysis_id,
            status=start_response.status,
            status_url=start_response.status_url,
            source=imported_game.metadata,
        )

    def _imported_game(self, request: GameAnalysisImportRequest) -> ImportedGame:
        if request.source == "chess_com_live_url":
            assert request.url is not None
            return self._chess_com_resolver.resolve(request.url)
        assert request.pgn is not None
        return imported_game_from_pgn(request.pgn)


def game_import_service_from_env(analysis_service: GameAnalysisService) -> GameImportService:
    """Build the default import service for the HTTP API."""

    return GameImportService(analysis_service=analysis_service)


def imported_game_from_pgn(pgn: str) -> ImportedGame:
    """Normalize a pasted PGN into an imported-game contract."""

    headers = _pgn_headers(pgn)
    white_username = _blank_to_none(headers.get("White"))
    black_username = _blank_to_none(headers.get("Black"))
    metadata = ImportedGameMetadata(
        source="pgn",
        source_url=None,
        external_game_id=None,
        title=metadata_title(
            white_username=white_username,
            black_username=black_username,
            fallback=_blank_to_none(headers.get("Event")) or "Pasted PGN",
        ),
        white_username=white_username,
        black_username=black_username,
        white_rating=_rating_from_header(headers.get("WhiteElo")),
        black_rating=_rating_from_header(headers.get("BlackElo")),
        time_control=_blank_to_none(headers.get("TimeControl")),
        result=_blank_to_none(headers.get("Result")),
    )
    return ImportedGame(pgn=pgn, metadata=metadata)


def _analysis_request_from_import(
    imported_game: ImportedGame,
    import_request: GameAnalysisImportRequest,
) -> GameAnalysisStartRequest:
    time_control = (
        _blank_to_none(import_request.time_control)
        or imported_game.metadata.time_control
        or "unknown"
    )
    if import_request.player_level is not None:
        return GameAnalysisStartRequest(
            pgn=imported_game.pgn,
            player_level=import_request.player_level,
            time_control=time_control,
            explain_significance=import_request.explain_significance,
            include_context=import_request.include_context,
            use_baseline_fallback=import_request.use_baseline_fallback,
        )
    return GameAnalysisStartRequest(
        pgn=imported_game.pgn,
        white_player_level=import_request.white_player_level
        or level_from_rating(imported_game.metadata.white_rating),
        black_player_level=import_request.black_player_level
        or level_from_rating(imported_game.metadata.black_rating),
        time_control=time_control,
        explain_significance=import_request.explain_significance,
        include_context=import_request.include_context,
        use_baseline_fallback=import_request.use_baseline_fallback,
    )


def _pgn_headers(pgn: str) -> dict[str, str]:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise GameImportError("PGN could not be parsed.")
    if not list(game.mainline_moves()):
        raise GameImportError("PGN contains no mainline moves.")
    return dict(game.headers)


def _rating_from_header(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    return int(stripped) if stripped.isdigit() else None


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
