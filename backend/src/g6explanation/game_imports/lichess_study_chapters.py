"""Resolve one public Lichess study chapter to canonical PGN."""

from __future__ import annotations

import io
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass

import chess.pgn

from g6explanation.game_imports.chess_com_live_games import RedisGameImportCache
from g6explanation.game_imports.contracts import (
    ImportedGame,
    ImportedGameMetadata,
    metadata_title,
)
from g6explanation.game_imports.lichess_games import (
    DEFAULT_LICHESS_CACHE_TTL_SECONDS,
    DEFAULT_LICHESS_MAX_RETRIES,
    DEFAULT_LICHESS_RETRY_BACKOFF_SECONDS,
    DEFAULT_LICHESS_TIMEOUT_SECONDS,
    DEFAULT_LICHESS_USER_AGENT,
    LICHESS_HOSTS,
    RETRYABLE_LICHESS_STATUSES,
    GameImportCache,
    HttpGetTransport,
    Sleep,
)

LICHESS_STUDY_EXPORT_URL = "https://lichess.org/api/study/{study_id}/{chapter_id}.pgn"
LICHESS_STUDY_ID_RE = re.compile(r"^[A-Za-z0-9]{8}$")
DEFAULT_LICHESS_STUDY_MAX_RESPONSE_BYTES = 1024 * 1024


class LichessStudyChapterError(ValueError):
    """Base error for Lichess study-chapter import failures."""


class LichessStudyChapterNotFoundError(LichessStudyChapterError):
    """Raised when a public study chapter cannot be resolved."""


class LichessStudyChapterUnavailableError(LichessStudyChapterError):
    """Raised when Lichess study data is temporarily unavailable."""


class LichessStudyChapterInvalidPgnError(LichessStudyChapterError):
    """Raised when a study export is not parseable standard-chess PGN."""


@dataclass(frozen=True, slots=True)
class LichessStudyChapterIdentity:
    """Canonical identifiers for one Lichess study chapter."""

    study_id: str
    chapter_id: str

    @property
    def external_game_id(self) -> str:
        return f"{self.study_id}/{self.chapter_id}"

    @property
    def source_url(self) -> str:
        return f"https://lichess.org/study/{self.study_id}/{self.chapter_id}"


def extract_lichess_study_chapter_identity(
    url: str,
) -> LichessStudyChapterIdentity:
    """Extract study and chapter ids from one canonical public URL."""

    parsed = _parse_url_like(url.strip())
    if parsed is None or parsed.hostname is None:
        raise LichessStudyChapterNotFoundError("Invalid Lichess study chapter URL.")
    if parsed.hostname.lower() not in LICHESS_HOSTS:
        raise LichessStudyChapterNotFoundError("Invalid Lichess study chapter URL.")

    parts = _path_parts(parsed.path)
    if len(parts) < 3 or parts[0] != "study":
        raise LichessStudyChapterNotFoundError("Invalid Lichess study chapter URL.")
    study_id, chapter_id = parts[1], parts[2]
    if (
        LICHESS_STUDY_ID_RE.fullmatch(study_id) is None
        or LICHESS_STUDY_ID_RE.fullmatch(chapter_id) is None
    ):
        raise LichessStudyChapterNotFoundError("Invalid Lichess study chapter URL.")
    return LichessStudyChapterIdentity(study_id=study_id, chapter_id=chapter_id)


class LichessStudyChapterResolver:
    """Resolve a public standard-chess chapter through Lichess's PGN API."""

    def __init__(
        self,
        *,
        cache: GameImportCache | None = None,
        user_agent: str = DEFAULT_LICHESS_USER_AGENT,
        timeout_seconds: float = DEFAULT_LICHESS_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_LICHESS_MAX_RETRIES,
        retry_backoff_seconds: float = DEFAULT_LICHESS_RETRY_BACKOFF_SECONDS,
        cache_ttl_seconds: int = DEFAULT_LICHESS_CACHE_TTL_SECONDS,
        max_response_bytes: int = DEFAULT_LICHESS_STUDY_MAX_RESPONSE_BYTES,
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
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive.")
        self._cache = cache
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._cache_ttl_seconds = cache_ttl_seconds
        self._max_response_bytes = max_response_bytes
        self._transport = transport or _urllib_get
        self._sleep = sleep

    @classmethod
    def from_env(cls) -> LichessStudyChapterResolver:
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
            max_response_bytes=_int_env(
                "G6EXPLANATION_LICHESS_STUDY_MAX_RESPONSE_BYTES",
                DEFAULT_LICHESS_STUDY_MAX_RESPONSE_BYTES,
            ),
        )

    def resolve(self, url: str) -> ImportedGame:
        identity = extract_lichess_study_chapter_identity(url)
        cache_key = f"lichess_study_chapter:{identity.external_game_id}"
        cached = self._cache.get(cache_key) if self._cache is not None else None
        if cached is not None:
            return cached

        pgn = self._export_chapter(identity)
        imported = _imported_game_from_pgn(pgn, identity=identity)
        if self._cache is not None:
            self._cache.set(cache_key, imported, self._cache_ttl_seconds)
        return imported

    def _export_chapter(self, identity: LichessStudyChapterIdentity) -> str:
        query = urllib.parse.urlencode(
            {
                "clocks": "true",
                "comments": "false",
                "variations": "false",
                "orientation": "false",
            }
        )
        url = (
            LICHESS_STUDY_EXPORT_URL.format(
                study_id=identity.study_id,
                chapter_id=identity.chapter_id,
            )
            + f"?{query}"
        )
        status, body = self._get(url)
        if status == 404:
            raise LichessStudyChapterNotFoundError("Lichess study chapter not found.")
        if status >= 400:
            raise LichessStudyChapterUnavailableError(
                f"Lichess study chapter is temporarily unavailable: HTTP {status}."
            )
        if len(body) > self._max_response_bytes:
            raise LichessStudyChapterInvalidPgnError(
                "Lichess study chapter PGN exceeded the import size limit."
            )
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LichessStudyChapterInvalidPgnError(
                "Lichess study chapter PGN was not valid UTF-8."
            ) from exc

    def _get(self, url: str) -> tuple[int, bytes]:
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/x-chess-pgn",
        }
        attempts = self._max_retries + 1
        for attempt_index in range(1, attempts + 1):
            status, body = self._transport(url, headers, self._timeout_seconds)
            if status not in RETRYABLE_LICHESS_STATUSES or attempt_index == attempts:
                return status, body
            if self._retry_backoff_seconds > 0:
                self._sleep(self._retry_backoff_seconds * attempt_index)
        raise AssertionError("Lichess study retry loop did not return.")


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
        raise LichessStudyChapterUnavailableError(
            "Lichess study chapter is temporarily unavailable."
        ) from exc


def _imported_game_from_pgn(
    pgn: str,
    *,
    identity: LichessStudyChapterIdentity,
) -> ImportedGame:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or not list(game.mainline_moves()):
        raise LichessStudyChapterInvalidPgnError(
            "Resolved Lichess study chapter PGN could not be parsed."
        )
    headers = dict(game.headers)
    variant = _optional_str(headers.get("Variant"))
    if variant is not None and variant.lower() != "standard":
        raise LichessStudyChapterInvalidPgnError(
            "Resolved Lichess study chapter is not standard chess."
        )

    white_username = _optional_str(headers.get("White"))
    black_username = _optional_str(headers.get("Black"))
    return ImportedGame(
        pgn=pgn,
        metadata=ImportedGameMetadata(
            source="lichess_study_chapter_url",
            source_url=identity.source_url,
            external_game_id=identity.external_game_id,
            title=metadata_title(
                white_username=white_username,
                black_username=black_username,
                fallback=_optional_str(headers.get("Event")) or "Lichess study chapter",
            ),
            white_username=white_username,
            black_username=black_username,
            white_rating=_positive_int(headers.get("WhiteElo")),
            black_rating=_positive_int(headers.get("BlackElo")),
            time_control=_optional_str(headers.get("TimeControl")),
            result=_optional_str(headers.get("Result")),
            rights_basis=(
                "User-requested Lichess study chapter import only; not eligible for global "
                "model training without explicit source-rights review."
            ),
        ),
    )


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


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _positive_int(value: object) -> int | None:
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return value if isinstance(value, int) and value > 0 else None


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)
