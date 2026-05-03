"""Redis persistence for asynchronous game-analysis snapshots."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any, Protocol, cast

from redis import Redis
from redis.exceptions import RedisError

from g6explanation.game_analysis.contracts import GameAnalysisSnapshot


class GameAnalysisStoreError(RuntimeError):
    """Raised when analysis job state cannot be persisted or loaded."""


class GameAnalysisStore(Protocol):
    """Storage boundary for game-analysis job snapshots."""

    def save(self, snapshot: GameAnalysisSnapshot) -> None:
        """Persist the latest snapshot."""
        ...

    def get(self, analysis_id: str) -> GameAnalysisSnapshot | None:
        """Return the latest snapshot for a job, if present."""
        ...


class RedisGameAnalysisStore:
    """Redis-backed snapshot store for local asynchronous analysis jobs."""

    def __init__(
        self,
        redis_client: Any,
        *,
        key_prefix: str = "g6:game_analysis",
        ttl_seconds: int = 24 * 60 * 60,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive.")
        self._redis: Any = redis_client
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        *,
        key_prefix: str = "g6:game_analysis",
        ttl_seconds: int = 24 * 60 * 60,
    ) -> RedisGameAnalysisStore:
        return cls(
            cast(
                Callable[[str], Any],
                Redis.from_url,  # pyright: ignore[reportUnknownMemberType]
            )(redis_url),
            key_prefix=key_prefix,
            ttl_seconds=ttl_seconds,
        )

    def ping(self) -> None:
        try:
            self._redis.ping()
        except RedisError as exc:
            raise GameAnalysisStoreError(f"Redis is unavailable: {exc}") from exc

    def save(self, snapshot: GameAnalysisSnapshot) -> None:
        try:
            self._redis.set(
                self._key(snapshot.analysis_id),
                snapshot.model_dump_json(),
                ex=self._ttl_seconds,
            )
        except RedisError as exc:
            raise GameAnalysisStoreError(f"Could not save game analysis state: {exc}") from exc

    def get(self, analysis_id: str) -> GameAnalysisSnapshot | None:
        try:
            raw = self._redis.get(self._key(analysis_id))
        except RedisError as exc:
            raise GameAnalysisStoreError(f"Could not load game analysis state: {exc}") from exc
        if raw is None:
            return None
        if isinstance(raw, bytes):
            return GameAnalysisSnapshot.model_validate_json(raw.decode("utf-8"))
        return GameAnalysisSnapshot.model_validate_json(cast(str, raw))

    def _key(self, analysis_id: str) -> str:
        return f"{self._key_prefix}:{analysis_id}"


class InMemoryGameAnalysisStore:
    """Small deterministic store for unit tests and local dry runs."""

    def __init__(self) -> None:
        self._snapshots: MutableMapping[str, GameAnalysisSnapshot] = {}

    def save(self, snapshot: GameAnalysisSnapshot) -> None:
        self._snapshots[snapshot.analysis_id] = snapshot

    def get(self, analysis_id: str) -> GameAnalysisSnapshot | None:
        return self._snapshots.get(analysis_id)
