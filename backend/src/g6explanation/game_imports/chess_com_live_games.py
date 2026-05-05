"""Resolve public Chess.com game URLs to canonical PGN."""

from __future__ import annotations

import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Protocol, cast

import chess.pgn

from g6explanation.game_imports.contracts import (
    ImportedGame,
    ImportedGameMetadata,
    metadata_title,
)

CHESS_COM_CALLBACK_URL = "https://www.chess.com/callback/live/game/{external_game_id}"
CHESS_COM_MONTH_ARCHIVE_URL = (
    "https://api.chess.com/pub/player/{username}/games/{year:04d}/{month:02d}"
)
CHESS_COM_GAME_URL_RE = re.compile(
    r"chess\.com/(?:analysis/)?game/(?:live/)?(?P<external_game_id>\d+)(?:[/?#]|$)"
)
DEFAULT_CHESS_COM_USER_AGENT = (
    "g6explanation/0.1 (+https://github.com/yahorbarkouski/g6explanation)"
)
DEFAULT_CHESS_COM_TIMEOUT_SECONDS = 20.0
DEFAULT_CHESS_COM_MAX_RETRIES = 2
DEFAULT_CHESS_COM_RETRY_BACKOFF_SECONDS = 0.5
DEFAULT_CHESS_COM_CACHE_TTL_SECONDS = 24 * 60 * 60
RETRYABLE_CHESS_COM_STATUSES = frozenset({429, 500, 502, 503, 504})

HttpGetTransport = Callable[[str, Mapping[str, str], float], tuple[int, bytes]]
Sleep = Callable[[float], None]


class GameImportCache(Protocol):
    """Best-effort cache for imported games."""

    def get(self, key: str) -> ImportedGame | None:
        """Return a cached import if present."""
        ...

    def set(self, key: str, imported_game: ImportedGame, ttl_seconds: int) -> None:
        """Persist a cached import."""
        ...


class ChessComLiveGameError(ValueError):
    """Base error for Chess.com live-game import failures."""


class ChessComLiveGameNotFoundError(ChessComLiveGameError):
    """Raised when a public live-game URL cannot be resolved."""


class ChessComLiveGameNotFinishedError(ChessComLiveGameError):
    """Raised when the live game exists but has not finished."""


class ChessComLiveGameUnavailableError(ChessComLiveGameError):
    """Raised when Chess.com data is temporarily unavailable or malformed."""


class ChessComLiveGameInvalidPgnError(ChessComLiveGameError):
    """Raised when a resolved game does not contain parseable PGN."""


def extract_chess_com_live_game_id(url: str) -> str:
    """Extract a Chess.com game id from a supported public URL."""

    match = CHESS_COM_GAME_URL_RE.search(url.strip())
    if match is None:
        raise ChessComLiveGameNotFoundError("Invalid Chess.com game URL.")
    return match.group("external_game_id")


class InMemoryGameImportCache:
    """Small deterministic cache for tests."""

    def __init__(self) -> None:
        self._items: dict[str, ImportedGame] = {}

    def get(self, key: str) -> ImportedGame | None:
        return self._items.get(key)

    def set(self, key: str, imported_game: ImportedGame, ttl_seconds: int) -> None:
        del ttl_seconds
        self._items[key] = imported_game


class RedisGameImportCache:
    """Redis-backed cache for resolved imported games."""

    def __init__(
        self,
        redis_client: Any,
        *,
        key_prefix: str = "g6:game_import",
    ) -> None:
        self._redis: Any = redis_client
        self._key_prefix = key_prefix

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        *,
        key_prefix: str = "g6:game_import",
    ) -> RedisGameImportCache:
        from redis import Redis

        return cls(
            cast(
                Callable[[str], Any],
                Redis.from_url,  # pyright: ignore[reportUnknownMemberType]
            )(redis_url),
            key_prefix=key_prefix,
        )

    def get(self, key: str) -> ImportedGame | None:
        try:
            raw = self._redis.get(self._key(key))
        except Exception:
            return None
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                return ImportedGame.model_validate_json(raw.decode("utf-8"))
            return ImportedGame.model_validate_json(cast(str, raw))
        except ValueError:
            return None

    def set(self, key: str, imported_game: ImportedGame, ttl_seconds: int) -> None:
        try:
            self._redis.set(self._key(key), imported_game.model_dump_json(), ex=ttl_seconds)
        except Exception:
            return

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"


class ChessComLiveGameResolver:
    """Resolve a finished public Chess.com live game through callback metadata and archives."""

    def __init__(
        self,
        *,
        cache: GameImportCache | None = None,
        user_agent: str = DEFAULT_CHESS_COM_USER_AGENT,
        timeout_seconds: float = DEFAULT_CHESS_COM_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_CHESS_COM_MAX_RETRIES,
        retry_backoff_seconds: float = DEFAULT_CHESS_COM_RETRY_BACKOFF_SECONDS,
        cache_ttl_seconds: int = DEFAULT_CHESS_COM_CACHE_TTL_SECONDS,
        transport: HttpGetTransport | None = None,
        sleep: Sleep = time.sleep,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be non-negative.")
        if cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be positive.")
        self._cache = cache
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._cache_ttl_seconds = cache_ttl_seconds
        self._transport = transport or _urllib_get
        self._sleep = sleep

    @classmethod
    def from_env(cls) -> ChessComLiveGameResolver:
        cache: GameImportCache | None = RedisGameImportCache.from_url(
            os.getenv("G6EXPLANATION_REDIS_URL", "redis://localhost:6379/0"),
            key_prefix=os.getenv(
                "G6EXPLANATION_GAME_IMPORT_REDIS_PREFIX",
                "g6:game_import",
            ),
        )
        return cls(
            cache=cache,
            user_agent=os.getenv(
                "G6EXPLANATION_CHESS_COM_USER_AGENT",
                DEFAULT_CHESS_COM_USER_AGENT,
            ),
            timeout_seconds=_float_env(
                "G6EXPLANATION_CHESS_COM_TIMEOUT_SECONDS",
                DEFAULT_CHESS_COM_TIMEOUT_SECONDS,
            ),
            max_retries=_int_env(
                "G6EXPLANATION_CHESS_COM_MAX_RETRIES",
                DEFAULT_CHESS_COM_MAX_RETRIES,
            ),
            retry_backoff_seconds=_float_env(
                "G6EXPLANATION_CHESS_COM_RETRY_BACKOFF_SECONDS",
                DEFAULT_CHESS_COM_RETRY_BACKOFF_SECONDS,
            ),
            cache_ttl_seconds=_int_env(
                "G6EXPLANATION_GAME_IMPORT_CACHE_TTL_SECONDS",
                DEFAULT_CHESS_COM_CACHE_TTL_SECONDS,
            ),
        )

    def resolve(self, url: str) -> ImportedGame:
        external_game_id = extract_chess_com_live_game_id(url)
        cache_key = f"chess_com_live:{external_game_id}"
        cached = self._cache.get(cache_key) if self._cache is not None else None
        if cached is not None:
            return cached

        callback_game = self._callback_game(external_game_id)
        headers = _callback_headers(callback_game)
        year, month = _callback_month(headers)
        matched = self._find_archive_match(
            external_game_id=external_game_id,
            year=year,
            month=month,
            candidate_usernames=[headers.get("White"), headers.get("Black")],
        )
        imported_game = _imported_game_from_archive_match(
            matched,
            callback_game=callback_game,
            external_game_id=external_game_id,
        )
        if self._cache is not None:
            self._cache.set(cache_key, imported_game, self._cache_ttl_seconds)
        return imported_game

    def _callback_game(self, external_game_id: str) -> dict[str, Any]:
        url = CHESS_COM_CALLBACK_URL.format(external_game_id=external_game_id)
        status, body = self._get(url)
        if status == 404:
            raise ChessComLiveGameNotFoundError("Chess.com live game not found.")
        if status >= 400:
            raise ChessComLiveGameUnavailableError(
                f"Chess.com live game is temporarily unavailable: HTTP {status}."
            )
        payload = _json_object(body, "Chess.com callback payload was invalid.")
        game = payload.get("game")
        if not isinstance(game, dict):
            raise ChessComLiveGameUnavailableError("Chess.com callback payload was invalid.")
        game_payload = cast(dict[str, object], game)
        if not game_payload.get("isFinished"):
            raise ChessComLiveGameNotFinishedError("Chess.com live game has not finished yet.")
        return cast(dict[str, Any], game_payload)

    def _find_archive_match(
        self,
        *,
        external_game_id: str,
        year: int,
        month: int,
        candidate_usernames: list[Any],
    ) -> dict[str, Any]:
        seen: set[str] = set()
        for raw_username in candidate_usernames:
            username = _normalized_username(raw_username)
            if username is None or username.lower() in seen:
                continue
            seen.add(username.lower())
            status, body = self._get(
                CHESS_COM_MONTH_ARCHIVE_URL.format(
                    username=urllib.parse.quote(username.lower()),
                    year=year,
                    month=month,
                )
            )
            if status == 404:
                continue
            if status >= 400:
                raise ChessComLiveGameUnavailableError(
                    f"Chess.com archive is temporarily unavailable: HTTP {status}."
                )
            payload = _json_object(body, "Chess.com archive payload was invalid.")
            games = payload.get("games")
            if not isinstance(games, list):
                raise ChessComLiveGameUnavailableError("Chess.com archive payload was invalid.")
            for raw_item in cast(list[object], games):
                if not isinstance(raw_item, dict):
                    continue
                item = cast(dict[str, object], raw_item)
                item_url = item.get("url")
                if isinstance(item_url, str) and _url_matches_game_id(item_url, external_game_id):
                    return cast(dict[str, Any], item)
        raise ChessComLiveGameNotFoundError("Chess.com archive PGN could not be resolved.")

    def _get(self, url: str) -> tuple[int, bytes]:
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        attempts = self._max_retries + 1
        last_status: int | None = None
        last_body = b""
        for attempt_index in range(1, attempts + 1):
            status, body = self._transport(url, headers, self._timeout_seconds)
            last_status = status
            last_body = body
            if status not in RETRYABLE_CHESS_COM_STATUSES or attempt_index == attempts:
                return status, body
            if self._retry_backoff_seconds > 0:
                self._sleep(self._retry_backoff_seconds * attempt_index)
        assert last_status is not None
        return last_status, last_body


def _urllib_get(
    url: str,
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise ChessComLiveGameUnavailableError(
            "Chess.com public game is temporarily unavailable."
        ) from exc


def _callback_headers(callback_game: dict[str, Any]) -> dict[str, Any]:
    headers = callback_game.get("pgnHeaders")
    if not isinstance(headers, dict):
        raise ChessComLiveGameUnavailableError("Chess.com callback headers were missing.")
    return cast(dict[str, Any], headers)


def _callback_month(headers: dict[str, Any]) -> tuple[int, int]:
    raw_date = headers.get("Date")
    if not isinstance(raw_date, str):
        raise ChessComLiveGameUnavailableError("Chess.com callback date was missing.")
    try:
        parsed = datetime.strptime(raw_date, "%Y.%m.%d")
    except ValueError as exc:
        raise ChessComLiveGameUnavailableError("Chess.com callback date was invalid.") from exc
    return parsed.year, parsed.month


def _imported_game_from_archive_match(
    archive_match: dict[str, Any],
    *,
    callback_game: dict[str, Any],
    external_game_id: str,
) -> ImportedGame:
    source_url = archive_match.get("url")
    pgn = archive_match.get("pgn")
    rules = archive_match.get("rules")
    if not isinstance(source_url, str) or not isinstance(pgn, str) or not pgn.strip():
        raise ChessComLiveGameInvalidPgnError("Chess.com archive did not include PGN.")
    if rules != "chess":
        raise ChessComLiveGameInvalidPgnError(
            "Resolved Chess.com game is not a supported chess game."
        )
    headers = _pgn_headers(pgn)
    white_username = (
        _optional_str(headers.get("White"))
        or _username_from_archive(
            archive_match,
            "white",
        )
        or _username_from_callback(callback_game, "white")
    )
    black_username = (
        _optional_str(headers.get("Black"))
        or _username_from_archive(
            archive_match,
            "black",
        )
        or _username_from_callback(callback_game, "black")
    )
    white_rating = (
        _positive_int(headers.get("WhiteElo"))
        or _rating_from_archive(archive_match, "white")
        or _rating_from_callback(callback_game, "white")
    )
    black_rating = (
        _positive_int(headers.get("BlackElo"))
        or _rating_from_archive(archive_match, "black")
        or _rating_from_callback(callback_game, "black")
    )
    metadata = ImportedGameMetadata(
        source="chess_com_live_url",
        source_url=source_url,
        external_game_id=external_game_id,
        title=metadata_title(
            white_username=white_username,
            black_username=black_username,
            fallback="Chess.com live game",
        ),
        white_username=white_username,
        black_username=black_username,
        white_rating=white_rating,
        black_rating=black_rating,
        time_control=_optional_str(headers.get("TimeControl"))
        or _optional_str(archive_match.get("time_control")),
        result=_optional_str(headers.get("Result")),
    )
    return ImportedGame(pgn=pgn, metadata=metadata)


def _pgn_headers(pgn: str) -> dict[str, str]:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or not list(game.mainline_moves()):
        raise ChessComLiveGameInvalidPgnError("Resolved Chess.com PGN could not be parsed.")
    return dict(game.headers)


def _json_object(body: bytes, error_message: str) -> dict[str, Any]:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ChessComLiveGameUnavailableError(error_message) from exc
    if not isinstance(value, dict):
        raise ChessComLiveGameUnavailableError(error_message)
    return cast(dict[str, Any], value)


def _normalized_username(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _username_from_archive(archive_match: dict[str, Any], side: str) -> str | None:
    payload = archive_match.get(side)
    if not isinstance(payload, dict):
        return None
    side_payload = cast(dict[str, object], payload)
    return _optional_str(side_payload.get("username"))


def _username_from_callback(callback_game: dict[str, Any], side: str) -> str | None:
    payload = _callback_player_for_side(callback_game, side)
    if payload is None:
        return None
    return _optional_str(payload.get("username"))


def _rating_from_archive(archive_match: dict[str, Any], side: str) -> int | None:
    payload = archive_match.get(side)
    if not isinstance(payload, dict):
        return None
    side_payload = cast(dict[str, object], payload)
    return _positive_int(side_payload.get("rating"))


def _rating_from_callback(callback_game: dict[str, Any], side: str) -> int | None:
    payload = _callback_player_for_side(callback_game, side)
    if payload is None:
        return None
    return _positive_int(payload.get("rating"))


def _callback_player_for_side(callback_game: dict[str, Any], side: str) -> dict[str, object] | None:
    players = callback_game.get("players")
    if not isinstance(players, dict):
        return None
    for raw_player in cast(dict[str, object], players).values():
        if not isinstance(raw_player, dict):
            continue
        player = cast(dict[str, object], raw_player)
        if _optional_str(player.get("color")) == side:
            return player
    return None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _url_matches_game_id(url: str, external_game_id: str) -> bool:
    try:
        return extract_chess_com_live_game_id(url) == external_game_id
    except ChessComLiveGameNotFoundError:
        return False


def _positive_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)
