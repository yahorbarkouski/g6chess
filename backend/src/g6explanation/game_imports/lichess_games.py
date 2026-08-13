"""Resolve public Lichess game URLs to canonical PGN."""

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
from typing import Any, Protocol, cast

import chess.pgn

from g6explanation.game_imports.chess_com_live_games import RedisGameImportCache
from g6explanation.game_imports.contracts import (
    ImportedGame,
    ImportedGameMetadata,
    metadata_title,
)

LICHESS_EXPORT_URL = "https://lichess.org/game/export/{external_game_id}"
LICHESS_HOSTS = frozenset({"lichess.org", "www.lichess.org"})
LICHESS_GAME_ID_RE = re.compile(r"^[A-Za-z0-9]{8}$")
DEFAULT_LICHESS_USER_AGENT = "g6explanation/0.1 (+https://github.com/yahorbarkouski/g6explanation)"
DEFAULT_LICHESS_TIMEOUT_SECONDS = 20.0
DEFAULT_LICHESS_MAX_RETRIES = 2
DEFAULT_LICHESS_RETRY_BACKOFF_SECONDS = 0.5
DEFAULT_LICHESS_CACHE_TTL_SECONDS = 24 * 60 * 60
RETRYABLE_LICHESS_STATUSES = frozenset({429, 500, 502, 503, 504})
FINISHED_LICHESS_STATUSES = frozenset(
    {
        "aborted",
        "mate",
        "resign",
        "stalemate",
        "timeout",
        "draw",
        "outoftime",
        "cheat",
        "noStart",
        "unknownFinish",
        "insufficientMaterialClaim",
        "variantEnd",
    }
)
STANDARD_VARIANTS = frozenset({"standard"})

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


class LichessGameError(ValueError):
    """Base error for Lichess game import failures."""


class LichessGameNotFoundError(LichessGameError):
    """Raised when a public Lichess game URL cannot be resolved."""


class LichessGameNotFinishedError(LichessGameError):
    """Raised when a Lichess game exists but has not finished."""


class LichessGameUnavailableError(LichessGameError):
    """Raised when Lichess data is temporarily unavailable or malformed."""


class LichessGameInvalidPgnError(LichessGameError):
    """Raised when a resolved game does not contain parseable standard-chess PGN."""


def extract_lichess_game_id(url: str) -> str:
    """Extract a Lichess game id from a supported public URL."""

    parsed = _parse_url_like(url.strip())
    if parsed is None or parsed.hostname is None:
        raise LichessGameNotFoundError("Invalid Lichess game URL.")
    if parsed.hostname.lower() not in LICHESS_HOSTS:
        raise LichessGameNotFoundError("Invalid Lichess game URL.")

    parts = _path_parts(parsed.path)
    candidate: str | None = None
    if len(parts) >= 3 and parts[0] == "game" and parts[1] == "export":
        candidate = parts[2]
    elif parts:
        candidate = parts[0]

    if candidate is None or LICHESS_GAME_ID_RE.fullmatch(candidate) is None:
        raise LichessGameNotFoundError("Invalid Lichess game URL.")
    return candidate


class LichessGameResolver:
    """Resolve a finished public Lichess game through the one-game export API."""

    def __init__(
        self,
        *,
        cache: GameImportCache | None = None,
        user_agent: str = DEFAULT_LICHESS_USER_AGENT,
        timeout_seconds: float = DEFAULT_LICHESS_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_LICHESS_MAX_RETRIES,
        retry_backoff_seconds: float = DEFAULT_LICHESS_RETRY_BACKOFF_SECONDS,
        cache_ttl_seconds: int = DEFAULT_LICHESS_CACHE_TTL_SECONDS,
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
    def from_env(cls) -> LichessGameResolver:
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
                "G6EXPLANATION_LICHESS_USER_AGENT",
                DEFAULT_LICHESS_USER_AGENT,
            ),
            timeout_seconds=_float_env(
                "G6EXPLANATION_LICHESS_TIMEOUT_SECONDS",
                DEFAULT_LICHESS_TIMEOUT_SECONDS,
            ),
            max_retries=_int_env(
                "G6EXPLANATION_LICHESS_MAX_RETRIES",
                DEFAULT_LICHESS_MAX_RETRIES,
            ),
            retry_backoff_seconds=_float_env(
                "G6EXPLANATION_LICHESS_RETRY_BACKOFF_SECONDS",
                DEFAULT_LICHESS_RETRY_BACKOFF_SECONDS,
            ),
            cache_ttl_seconds=_int_env(
                "G6EXPLANATION_GAME_IMPORT_CACHE_TTL_SECONDS",
                DEFAULT_LICHESS_CACHE_TTL_SECONDS,
            ),
        )

    def resolve(self, url: str) -> ImportedGame:
        external_game_id = extract_lichess_game_id(url)
        cache_key = f"lichess_game:{external_game_id}"
        cached = self._cache.get(cache_key) if self._cache is not None else None
        if cached is not None:
            return cached

        payload = self._export_game(external_game_id)
        imported_game = _imported_game_from_payload(payload, external_game_id=external_game_id)
        if self._cache is not None:
            self._cache.set(cache_key, imported_game, self._cache_ttl_seconds)
        return imported_game

    def _export_game(self, external_game_id: str) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {
                "moves": "true",
                "pgnInJson": "true",
                "tags": "true",
                "clocks": "true",
                "evals": "false",
                "opening": "true",
                "literate": "false",
                "accuracy": "false",
            }
        )
        url = f"{LICHESS_EXPORT_URL.format(external_game_id=external_game_id)}?{query}"
        status, body = self._get(url)
        if status == 404:
            raise LichessGameNotFoundError("Lichess game not found.")
        if status >= 400:
            raise LichessGameUnavailableError(
                f"Lichess game is temporarily unavailable: HTTP {status}."
            )
        return _json_object(body, "Lichess export payload was invalid.")

    def _get(self, url: str) -> tuple[int, bytes]:
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/json",
        }
        attempts = self._max_retries + 1
        last_status: int | None = None
        last_body = b""
        for attempt_index in range(1, attempts + 1):
            status, body = self._transport(url, headers, self._timeout_seconds)
            last_status = status
            last_body = body
            if status not in RETRYABLE_LICHESS_STATUSES or attempt_index == attempts:
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
        raise LichessGameUnavailableError("Lichess game is temporarily unavailable.") from exc


def _imported_game_from_payload(
    payload: dict[str, Any],
    *,
    external_game_id: str,
) -> ImportedGame:
    status = _optional_str(payload.get("status"))
    if status is not None and status not in FINISHED_LICHESS_STATUSES:
        raise LichessGameNotFinishedError("Lichess game has not finished yet.")

    variant = _optional_str(payload.get("variant"))
    if variant not in STANDARD_VARIANTS:
        raise LichessGameInvalidPgnError("Resolved Lichess game is not standard chess.")

    pgn = payload.get("pgn")
    if not isinstance(pgn, str) or not pgn.strip():
        raise LichessGameInvalidPgnError("Lichess export did not include PGN.")

    headers = _pgn_headers(pgn)
    pgn_variant = _optional_str(headers.get("Variant"))
    if pgn_variant is not None and pgn_variant.lower() != "standard":
        raise LichessGameInvalidPgnError("Resolved Lichess PGN is not standard chess.")

    white_username = _optional_str(headers.get("White")) or _username_from_player(payload, "white")
    black_username = _optional_str(headers.get("Black")) or _username_from_player(payload, "black")
    source_url = _optional_str(headers.get("Site")) or f"https://lichess.org/{external_game_id}"
    metadata = ImportedGameMetadata(
        source="lichess_game_url",
        source_url=source_url,
        external_game_id=external_game_id,
        title=metadata_title(
            white_username=white_username,
            black_username=black_username,
            fallback="Lichess game",
        ),
        white_username=white_username,
        black_username=black_username,
        white_rating=_positive_int(headers.get("WhiteElo"))
        or _rating_from_player(payload, "white"),
        black_rating=_positive_int(headers.get("BlackElo"))
        or _rating_from_player(payload, "black"),
        time_control=_optional_str(headers.get("TimeControl")) or _time_control_from_clock(payload),
        result=_optional_str(headers.get("Result")) or _result_from_winner(payload),
        rights_basis=(
            "User-requested Lichess game import only; not eligible for global model "
            "training without explicit source-rights review."
        ),
    )
    return ImportedGame(pgn=pgn, metadata=metadata)


def _parse_url_like(value: str) -> urllib.parse.ParseResult | None:
    if not value:
        return None
    candidate = value if re.match(r"^[a-z][a-z0-9+.-]*:", value, re.I) else f"https://{value}"
    try:
        return urllib.parse.urlparse(candidate)
    except ValueError:
        return None


def _path_parts(path: str) -> list[str]:
    return [urllib.parse.unquote(part) for part in path.split("/") if part]


def _pgn_headers(pgn: str) -> dict[str, str]:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or not list(game.mainline_moves()):
        raise LichessGameInvalidPgnError("Resolved Lichess PGN could not be parsed.")
    return dict(game.headers)


def _json_object(body: bytes, error_message: str) -> dict[str, Any]:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LichessGameUnavailableError(error_message) from exc
    if not isinstance(value, dict):
        raise LichessGameUnavailableError(error_message)
    return cast(dict[str, Any], value)


def _username_from_player(payload: dict[str, Any], side: str) -> str | None:
    player = _player_payload(payload, side)
    if player is None:
        return None
    user = player.get("user")
    if not isinstance(user, dict):
        return None
    user_payload = cast(dict[str, object], user)
    return _optional_str(user_payload.get("name")) or _optional_str(user_payload.get("id"))


def _rating_from_player(payload: dict[str, Any], side: str) -> int | None:
    player = _player_payload(payload, side)
    if player is None:
        return None
    return _positive_int(player.get("rating"))


def _player_payload(payload: dict[str, Any], side: str) -> dict[str, object] | None:
    players = payload.get("players")
    if not isinstance(players, dict):
        return None
    players_payload = cast(dict[str, object], players)
    player = players_payload.get(side)
    if not isinstance(player, dict):
        return None
    return cast(dict[str, object], player)


def _time_control_from_clock(payload: dict[str, Any]) -> str | None:
    clock = payload.get("clock")
    if not isinstance(clock, dict):
        return None
    clock_payload = cast(dict[str, object], clock)
    initial = _positive_int_or_zero(clock_payload.get("initial"))
    increment = _positive_int_or_zero(clock_payload.get("increment"))
    if initial is None or increment is None:
        return None
    return f"{initial}+{increment}"


def _result_from_winner(payload: dict[str, Any]) -> str | None:
    winner = _optional_str(payload.get("winner"))
    if winner == "white":
        return "1-0"
    if winner == "black":
        return "0-1"
    status = _optional_str(payload.get("status"))
    return "1/2-1/2" if status in {"draw", "stalemate", "insufficientMaterialClaim"} else None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _positive_int_or_zero(value: Any) -> int | None:
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed >= 0 else None
    return None


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)
