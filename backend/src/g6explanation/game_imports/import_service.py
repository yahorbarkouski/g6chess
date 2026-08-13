"""Import orchestration that starts the existing game-analysis job."""

from __future__ import annotations

import hashlib
import io
import json
import os
from collections.abc import Callable
from typing import Any, Protocol, cast

import chess.pgn

from g6explanation.context_engine.contracts import ColorName, PlayerLevel
from g6explanation.game_analysis import GameAnalysisService, GameAnalysisStartRequest
from g6explanation.game_imports.chess_com_live_games import (
    ChessComLiveGameResolver,
    extract_chess_com_live_game_id,
)
from g6explanation.game_imports.contracts import (
    GameAnalysisImportRequest,
    GameAnalysisImportResponse,
    ImportedGame,
    ImportedGameMetadata,
    metadata_title,
)
from g6explanation.game_imports.lichess_games import (
    LichessGameResolver,
    extract_lichess_game_id,
)
from g6explanation.game_imports.lichess_study_chapters import (
    LichessStudyChapterResolver,
    extract_lichess_study_chapter_identity,
)

DEFAULT_IMPORTED_GAME_ANALYSIS_CACHE_TTL_SECONDS = 24 * 60 * 60


class GameAnalysisImportIndex(Protocol):
    """Best-effort source index for already-started imported analyses."""

    def get(self, key: str) -> GameAnalysisImportResponse | None:
        """Return an import response pointer if present."""
        ...

    def set(
        self,
        key: str,
        response: GameAnalysisImportResponse,
        ttl_seconds: int,
    ) -> None:
        """Persist an import response pointer."""
        ...


class InMemoryGameAnalysisImportIndex:
    """Small deterministic import-analysis index for tests."""

    def __init__(self) -> None:
        self._items: dict[str, GameAnalysisImportResponse] = {}

    def get(self, key: str) -> GameAnalysisImportResponse | None:
        return self._items.get(key)

    def set(
        self,
        key: str,
        response: GameAnalysisImportResponse,
        ttl_seconds: int,
    ) -> None:
        del ttl_seconds
        self._items[key] = response


class RedisGameAnalysisImportIndex:
    """Redis-backed source index for imported analysis jobs."""

    def __init__(
        self,
        redis_client: Any,
        *,
        key_prefix: str = "g6:game_import_analysis",
    ) -> None:
        self._redis: Any = redis_client
        self._key_prefix = key_prefix

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        *,
        key_prefix: str = "g6:game_import_analysis",
    ) -> RedisGameAnalysisImportIndex:
        from redis import Redis

        return cls(
            cast(
                Callable[[str], Any],
                Redis.from_url,  # pyright: ignore[reportUnknownMemberType]
            )(redis_url),
            key_prefix=key_prefix,
        )

    def get(self, key: str) -> GameAnalysisImportResponse | None:
        try:
            raw = self._redis.get(self._key(key))
        except Exception:
            return None
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                return GameAnalysisImportResponse.model_validate_json(raw.decode("utf-8"))
            return GameAnalysisImportResponse.model_validate_json(cast(str, raw))
        except ValueError:
            return None

    def set(
        self,
        key: str,
        response: GameAnalysisImportResponse,
        ttl_seconds: int,
    ) -> None:
        try:
            self._redis.set(self._key(key), response.model_dump_json(), ex=ttl_seconds)
        except Exception:
            return

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"


class GameImportError(ValueError):
    """Raised when an imported game cannot be normalized for analysis."""


class ImportPlayerLevelRequiredError(GameImportError):
    """Raised when source metadata cannot establish a side's player level."""


class GameImportService:
    """Resolve user-provided game sources and start game analysis."""

    def __init__(
        self,
        *,
        analysis_service: GameAnalysisService,
        analysis_index: GameAnalysisImportIndex | None = None,
        analysis_index_ttl_seconds: int = DEFAULT_IMPORTED_GAME_ANALYSIS_CACHE_TTL_SECONDS,
        chess_com_resolver: ChessComLiveGameResolver | None = None,
        lichess_resolver: LichessGameResolver | None = None,
        lichess_study_resolver: LichessStudyChapterResolver | None = None,
    ) -> None:
        if analysis_index_ttl_seconds <= 0:
            raise ValueError("analysis_index_ttl_seconds must be positive.")
        self._analysis_service = analysis_service
        self._analysis_index = analysis_index
        self._analysis_index_ttl_seconds = analysis_index_ttl_seconds
        self._chess_com_resolver = chess_com_resolver or ChessComLiveGameResolver.from_env()
        self._lichess_resolver = lichess_resolver or LichessGameResolver.from_env()
        self._lichess_study_resolver = (
            lichess_study_resolver or LichessStudyChapterResolver.from_env()
        )

    def start(self, request: GameAnalysisImportRequest) -> GameAnalysisImportResponse:
        cached_response = self._cached_response_for_request(request)
        if cached_response is not None:
            return cached_response

        imported_game = self._imported_game(request)
        start_request = _analysis_request_from_import(imported_game, request)
        start_response = self._analysis_service.start(start_request)
        response = GameAnalysisImportResponse(
            analysis_id=start_response.analysis_id,
            status=start_response.status,
            status_url=start_response.status_url,
            source=imported_game.metadata,
            game=start_response.game,
        )
        self._write_response_for_request(request, response)
        return response

    def cached_chess_com_live_game_analysis(
        self,
        external_game_id: str,
    ) -> GameAnalysisImportResponse | None:
        """Return an existing non-failed analysis pointer for a Chess.com live game."""

        normalized = external_game_id.strip()
        if not normalized.isdigit():
            return None
        return self._cached_index_response(_chess_com_live_analysis_key(normalized))

    def cached_lichess_game_analysis(
        self,
        external_game_id: str,
    ) -> GameAnalysisImportResponse | None:
        """Return an existing non-failed analysis pointer for a Lichess game."""

        normalized = external_game_id.strip()
        try:
            normalized = extract_lichess_game_id(f"https://lichess.org/{normalized}")
        except ValueError:
            return None
        return self._cached_index_response(_lichess_analysis_key(normalized))

    def cached_lichess_study_chapter_analysis(
        self,
        study_id: str,
        chapter_id: str,
    ) -> GameAnalysisImportResponse | None:
        """Return an existing non-failed analysis pointer for one study chapter."""

        try:
            identity = extract_lichess_study_chapter_identity(
                f"https://lichess.org/study/{study_id}/{chapter_id}"
            )
        except ValueError:
            return None
        return self._cached_index_response(
            _lichess_study_chapter_analysis_key(identity.external_game_id)
        )

    def _imported_game(self, request: GameAnalysisImportRequest) -> ImportedGame:
        if request.source == "chess_com_live_url":
            return self._chess_com_resolver.resolve(request.url)
        if request.source == "lichess_game_url":
            return self._lichess_resolver.resolve(request.url)
        if request.source == "lichess_study_chapter_url":
            return self._lichess_study_resolver.resolve(request.url)
        return imported_game_from_pgn(request.pgn)

    def _cached_response_for_request(
        self,
        request: GameAnalysisImportRequest,
    ) -> GameAnalysisImportResponse | None:
        key = _analysis_key_for_request(request)
        if key is None:
            return None
        return self._cached_index_response(key)

    def _cached_index_response(self, key: str) -> GameAnalysisImportResponse | None:
        if self._analysis_index is None:
            return None
        cached = self._analysis_index.get(key)
        if cached is None:
            return None
        snapshot = self._analysis_service.get(cached.analysis_id)
        if snapshot is None or snapshot.status == "failed":
            return None
        return GameAnalysisImportResponse(
            analysis_id=cached.analysis_id,
            status=snapshot.status,
            status_url=cached.status_url,
            source=cached.source,
            game=snapshot.game or cached.game,
        )

    def _write_response_for_request(
        self,
        request: GameAnalysisImportRequest,
        response: GameAnalysisImportResponse,
    ) -> None:
        if self._analysis_index is None:
            return
        key = _analysis_key_for_request(request)
        if key is None:
            return
        self._analysis_index.set(
            key,
            response,
            self._analysis_index_ttl_seconds,
        )


def game_import_service_from_env(analysis_service: GameAnalysisService) -> GameImportService:
    """Build the default import service for the HTTP API."""

    analysis_index = RedisGameAnalysisImportIndex.from_url(
        os.getenv("G6EXPLANATION_REDIS_URL", "redis://localhost:6379/0"),
        key_prefix=os.getenv(
            "G6EXPLANATION_GAME_IMPORT_ANALYSIS_REDIS_PREFIX",
            "g6:game_import_analysis",
        ),
    )
    return GameImportService(
        analysis_index=analysis_index,
        analysis_index_ttl_seconds=_int_env(
            "G6EXPLANATION_GAME_IMPORT_ANALYSIS_CACHE_TTL_SECONDS",
            DEFAULT_IMPORTED_GAME_ANALYSIS_CACHE_TTL_SECONDS,
        ),
        analysis_service=analysis_service,
    )


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
    return GameAnalysisStartRequest(
        pgn=imported_game.pgn,
        white_player_level=_level_for_imported_side(imported_game, import_request, "white"),
        black_player_level=_level_for_imported_side(imported_game, import_request, "black"),
        time_control=time_control,
        explain_significance=import_request.explain_significance,
        include_context=import_request.include_context,
        use_baseline_fallback=import_request.use_baseline_fallback,
    )


def _level_for_imported_side(
    imported_game: ImportedGame,
    import_request: GameAnalysisImportRequest,
    side: ColorName,
) -> PlayerLevel:
    rating = (
        imported_game.metadata.white_rating
        if side == "white"
        else imported_game.metadata.black_rating
    )
    if rating is not None:
        return _level_from_source_rating(rating, imported_game.metadata.source)
    if imported_game.metadata.source in {"chess_com_live_url", "lichess_game_url"}:
        source_name = (
            "Chess.com" if imported_game.metadata.source == "chess_com_live_url" else "Lichess"
        )
        raise GameImportError(
            f"{source_name} import did not include a {side} rating; cannot analyze without "
            "source-derived ratings."
        )

    explicit_side_level = (
        import_request.white_player_level if side == "white" else import_request.black_player_level
    )
    if explicit_side_level is not None:
        return _validated_explicit_import_level(explicit_side_level, side)
    if import_request.player_level is not None:
        return _validated_explicit_import_level(import_request.player_level, side)
    source_name = (
        "Lichess study chapter"
        if imported_game.metadata.source == "lichess_study_chapter_url"
        else "PGN"
    )
    raise ImportPlayerLevelRequiredError(
        f"{source_name} import did not include a {side} rating. Add WhiteElo and BlackElo "
        "headers or provide explicit player levels."
    )


def _level_from_source_rating(value: int, source: str) -> PlayerLevel:
    if value <= 0:
        raise GameImportError("Imported ratings must be positive integers.")
    if source == "chess_com_live_url":
        system = "chess.com"
    elif source == "lichess_game_url" or source == "lichess_study_chapter_url":
        system = "lichess"
    else:
        system = "pgn"
    return PlayerLevel.rating(value, system)


def _validated_explicit_import_level(level: PlayerLevel, side: ColorName) -> PlayerLevel:
    if level.system == "frontend-default":
        raise GameImportError(
            "Import requests may not use frontend-default player levels; use source ratings "
            "or explicit side ratings."
        )
    rating = level.rating_value()
    if rating is None:
        raise GameImportError(f"Explicit {side} player level for imports must be a rating.")
    if rating <= 0:
        raise GameImportError(f"Explicit {side} player rating must be positive.")
    return level


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
    if not stripped.isdigit():
        return None
    rating = int(stripped)
    return rating if rating > 0 else None


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _chess_com_live_analysis_key(external_game_id: str) -> str:
    return f"chess_com_live:{external_game_id}"


def _lichess_analysis_key(external_game_id: str) -> str:
    return f"lichess_game:{external_game_id}"


def _lichess_study_chapter_analysis_key(external_game_id: str) -> str:
    return f"lichess_study_chapter:{external_game_id}"


def _analysis_key_for_request(request: GameAnalysisImportRequest) -> str | None:
    if request.source == "chess_com_live_url":
        return _chess_com_live_analysis_key(extract_chess_com_live_game_id(request.url))
    if request.source == "lichess_game_url":
        return _lichess_analysis_key(extract_lichess_game_id(request.url))
    if request.source == "lichess_study_chapter_url":
        identity = extract_lichess_study_chapter_identity(request.url)
        return _lichess_study_chapter_analysis_key(identity.external_game_id)
    payload = {
        "pgn": _normalized_pgn(request.pgn),
        "player_level": _contract_key(request.player_level),
        "white_player_level": _contract_key(request.white_player_level),
        "black_player_level": _contract_key(request.black_player_level),
        "time_control": _blank_to_none(request.time_control),
        "explain_significance": request.explain_significance,
        "include_context": request.include_context,
        "use_baseline_fallback": request.use_baseline_fallback,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"pgn:{digest}"


def _contract_key(value: PlayerLevel | None) -> dict[str, object] | None:
    if value is None:
        return None
    return value.model_dump(mode="json")


def _normalized_pgn(pgn: str) -> str:
    return "\n".join(line.rstrip() for line in pgn.strip().splitlines())


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)
