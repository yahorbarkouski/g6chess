"""Submission service for asynchronous game-analysis jobs."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Protocol

from g6explanation.game_analysis.analysis_runner import (
    GameAnalysisRunner,
    count_game_plies,
    game_analysis_context_workers_from_env,
    game_analysis_openrouter_concurrency_from_env,
)
from g6explanation.game_analysis.contracts import (
    GameAnalysisSnapshot,
    GameAnalysisStartRequest,
    GameAnalysisStartResponse,
)
from g6explanation.game_analysis.state_store import (
    GameAnalysisStore,
    RedisGameAnalysisStore,
)

DEFAULT_GAME_ANALYSIS_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_GAME_ANALYSIS_JOB_WORKERS = 1


class GameAnalysisExecutor(Protocol):
    def submit(
        self,
        fn: Callable[..., object],
        /,
        *args: object,
        **kwargs: object,
    ) -> Future[object]:
        """Submit one background job."""
        ...


class GameAnalysisService:
    """Start jobs, persist initial state, and expose latest snapshots."""

    def __init__(
        self,
        *,
        store: GameAnalysisStore,
        runner: GameAnalysisRunner,
        executor: GameAnalysisExecutor | None = None,
    ) -> None:
        self._store = store
        self._runner = runner
        self._executor = executor or ThreadPoolExecutor(
            max_workers=_int_env(
                "G6EXPLANATION_GAME_ANALYSIS_JOB_WORKERS",
                DEFAULT_GAME_ANALYSIS_JOB_WORKERS,
            )
        )

    def start(self, request: GameAnalysisStartRequest) -> GameAnalysisStartResponse:
        total_plies = count_game_plies(request.pgn)
        if total_plies == 0:
            raise ValueError("PGN contains no mainline moves.")
        analysis_id = uuid.uuid4().hex
        created_at = _utc_now()
        snapshot = GameAnalysisSnapshot(
            analysis_id=analysis_id,
            status="pending",
            total_plies=total_plies,
            context_completed=0,
            explanation_required=0,
            explanation_completed=0,
            explanation_failed=0,
            explain_significance=request.explain_significance,
            created_at=created_at,
            updated_at=created_at,
        )
        self._store.save(snapshot)
        self._executor.submit(
            self._runner.run,
            analysis_id=analysis_id,
            request=request,
            store=self._store,
        )
        return GameAnalysisStartResponse(
            analysis_id=analysis_id,
            status=snapshot.status,
            status_url=f"/api/game-analysis/{analysis_id}",
        )

    def get(self, analysis_id: str) -> GameAnalysisSnapshot | None:
        return self._store.get(analysis_id)


def game_analysis_service_from_env() -> GameAnalysisService:
    store = RedisGameAnalysisStore.from_url(
        os.getenv("G6EXPLANATION_REDIS_URL", DEFAULT_GAME_ANALYSIS_REDIS_URL),
        key_prefix=os.getenv("G6EXPLANATION_GAME_ANALYSIS_REDIS_PREFIX", "g6:game_analysis"),
        ttl_seconds=_int_env("G6EXPLANATION_GAME_ANALYSIS_TTL_SECONDS", 24 * 60 * 60),
    )
    runner = GameAnalysisRunner(
        context_workers=game_analysis_context_workers_from_env(),
        openrouter_concurrency=game_analysis_openrouter_concurrency_from_env(),
    )
    return GameAnalysisService(store=store, runner=runner)


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
