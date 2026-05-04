"""Background orchestration for full-game analysis jobs."""

from __future__ import annotations

import io
import logging
import os
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import chess
import chess.pgn

from g6explanation.context_engine import MoveContextBuilder, MoveContextRequest
from g6explanation.context_engine.contracts import ContextResult
from g6explanation.context_engine.position_reconstruction import color_name
from g6explanation.explanation_generation import ExplanationService
from g6explanation.explanation_generation.coach_model import CoachModelProvider
from g6explanation.explanation_generation.contracts import (
    ExplanationLineCard,
    ExplanationSegment,
    GenerationAttempt,
)
from g6explanation.explanation_generation.exceptions import ExplanationVerificationError
from g6explanation.explanation_generation.openrouter_chat import OpenRouterCoachModelProvider
from g6explanation.game_analysis.contracts import (
    GameAnalysisSnapshot,
    GameAnalysisStartRequest,
    GameMoveAnalysis,
)
from g6explanation.game_analysis.provider_setup import real_game_analysis_context_builder
from g6explanation.game_analysis.state_store import GameAnalysisStore

DEFAULT_GAME_ANALYSIS_CONTEXT_WORKERS = min(os.cpu_count() or 1, 16)
DEFAULT_GAME_ANALYSIS_OPENROUTER_CONCURRENCY = 30
LOGGER = logging.getLogger(__name__)

ContextBuilderFactory = Callable[[], MoveContextBuilder]
CoachProviderFactory = Callable[[], CoachModelProvider]
Clock = Callable[[], float]
TimestampFactory = Callable[[], str]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class _PlyRequest:
    ply: int
    request: MoveContextRequest


@dataclass(frozen=True)
class _ContextBuildResult:
    ply: int
    context: ContextResult
    latency_seconds: float


@dataclass(frozen=True)
class _ExplanationBuildResult:
    ply: int
    explanation: str
    segments: list[ExplanationSegment]
    line_cards: list[ExplanationLineCard]
    latency_seconds: float
    attempts: int
    model: str


class GameAnalysisRunner:
    """Run a full-game job and persist partial snapshots as work completes."""

    def __init__(
        self,
        *,
        context_builder_factory: ContextBuilderFactory = real_game_analysis_context_builder,
        coach_provider_factory: CoachProviderFactory = OpenRouterCoachModelProvider.from_env,
        context_workers: int = DEFAULT_GAME_ANALYSIS_CONTEXT_WORKERS,
        openrouter_concurrency: int = DEFAULT_GAME_ANALYSIS_OPENROUTER_CONCURRENCY,
        clock: Clock = time.perf_counter,
        timestamp_factory: TimestampFactory = _utc_now,
    ) -> None:
        if context_workers < 1:
            raise ValueError("context_workers must be at least 1.")
        if openrouter_concurrency < 1:
            raise ValueError("openrouter_concurrency must be at least 1.")
        self._context_builder_factory = context_builder_factory
        self._coach_provider_factory = coach_provider_factory
        self._context_workers = context_workers
        self._openrouter_concurrency = openrouter_concurrency
        self._clock = clock
        self._timestamp_factory = timestamp_factory

    def run(
        self,
        *,
        analysis_id: str,
        request: GameAnalysisStartRequest,
        store: GameAnalysisStore,
    ) -> None:
        """Run one submitted analysis job."""

        started_at = self._timestamp_factory()
        snapshot = store.get(analysis_id)
        if snapshot is None:
            return
        snapshot = snapshot.model_copy(
            update={"status": "running", "started_at": started_at, "updated_at": started_at}
        )
        store.save(snapshot)
        LOGGER.info(
            "Game analysis started: analysis_id=%s total_plies=%s explain_significance=%s "
            "include_context=%s baseline_fallback=%s context_workers=%s openrouter_concurrency=%s",
            analysis_id,
            snapshot.total_plies,
            request.explain_significance,
            request.include_context,
            request.use_baseline_fallback,
            self._context_workers,
            self._openrouter_concurrency,
        )

        try:
            ply_requests = game_ply_requests(request)
            if not ply_requests:
                raise ValueError("PGN contains no mainline moves.")
            snapshot = self._run_context_phase(
                snapshot=snapshot,
                ply_requests=ply_requests,
                request=request,
                store=store,
            )
            completed_at = self._timestamp_factory()
            final_status = "failed" if snapshot.explanation_failed else "succeeded"
            final_error = (
                f"{snapshot.explanation_failed} requested explanation(s) failed. "
                "See per-move explanation_error fields and server logs."
                if snapshot.explanation_failed
                else None
            )
            snapshot = snapshot.model_copy(
                update={
                    "status": final_status,
                    "error": final_error,
                    "completed_at": completed_at,
                    "updated_at": completed_at,
                }
            )
            store.save(snapshot)
            if final_status == "failed":
                LOGGER.error(
                    "Game analysis completed with explanation failures: analysis_id=%s "
                    "total_plies=%s context_completed=%s explanation_required=%s "
                    "explanation_completed=%s explanation_failed=%s error=%s",
                    analysis_id,
                    snapshot.total_plies,
                    snapshot.context_completed,
                    snapshot.explanation_required,
                    snapshot.explanation_completed,
                    snapshot.explanation_failed,
                    final_error,
                )
            else:
                LOGGER.info(
                    "Game analysis succeeded: analysis_id=%s total_plies=%s "
                    "context_completed=%s explanation_required=%s explanation_completed=%s",
                    analysis_id,
                    snapshot.total_plies,
                    snapshot.context_completed,
                    snapshot.explanation_required,
                    snapshot.explanation_completed,
                )
        except Exception as exc:
            failed_at = self._timestamp_factory()
            snapshot = snapshot.model_copy(
                update={
                    "status": "failed",
                    "error": str(exc),
                    "completed_at": failed_at,
                    "updated_at": failed_at,
                }
            )
            store.save(snapshot)
            LOGGER.exception("Game analysis failed: analysis_id=%s error=%s", analysis_id, exc)

    def _run_context_phase(
        self,
        *,
        snapshot: GameAnalysisSnapshot,
        ply_requests: Sequence[_PlyRequest],
        request: GameAnalysisStartRequest,
        store: GameAnalysisStore,
    ) -> GameAnalysisSnapshot:
        worker_state = threading.local()

        def builder() -> MoveContextBuilder:
            builder_value = getattr(worker_state, "builder", None)
            if builder_value is None:
                builder_value = self._context_builder_factory()
                worker_state.builder = builder_value
            return cast(MoveContextBuilder, builder_value)

        max_workers = min(self._context_workers, len(ply_requests))
        explanation_futures: dict[Future[_ExplanationBuildResult], int] = {}
        with (
            ThreadPoolExecutor(max_workers=max_workers) as context_executor,
            ThreadPoolExecutor(
                max_workers=min(self._openrouter_concurrency, len(ply_requests))
            ) as explanation_executor,
        ):
            context_futures = {
                context_executor.submit(
                    _build_context,
                    builder,
                    ply_request,
                    self._clock,
                ): ply_request.ply
                for ply_request in ply_requests
            }
            for context_future in as_completed(context_futures):
                ply = context_futures[context_future]
                try:
                    context_result = context_future.result()
                except Exception:
                    LOGGER.exception(
                        "Context build failed: analysis_id=%s ply=%s",
                        snapshot.analysis_id,
                        ply,
                    )
                    raise
                requires_explanation = (
                    context_result.context.evidence.significance.label
                    in request.explain_significance
                )
                move = _move_from_context_result(
                    context_result,
                    requires_explanation=requires_explanation,
                    include_context=request.include_context,
                )
                snapshot = _snapshot_with_move(
                    snapshot,
                    move,
                    updated_at=self._timestamp_factory(),
                )
                store.save(snapshot)
                if requires_explanation:
                    LOGGER.info(
                        "Explanation queued: analysis_id=%s ply=%s san=%s quality=%s "
                        "significance=%s",
                        snapshot.analysis_id,
                        context_result.ply,
                        move.san,
                        move.quality,
                        move.significance.label,
                    )
                    explanation_futures[
                        explanation_executor.submit(
                            self._explain_context,
                            snapshot.analysis_id,
                            context_result.ply,
                            context_result.context,
                            request.use_baseline_fallback,
                        )
                    ] = context_result.ply

            for explanation_future in as_completed(explanation_futures):
                ply = explanation_futures[explanation_future]
                try:
                    explanation = explanation_future.result()
                    snapshot = _snapshot_with_explanation(
                        snapshot,
                        explanation,
                        updated_at=self._timestamp_factory(),
                    )
                except Exception as exc:
                    failed_move = _move_by_ply(snapshot, ply)
                    _log_explanation_failure(snapshot.analysis_id, ply, failed_move, exc)
                    snapshot = _snapshot_with_explanation_error(
                        snapshot,
                        ply=ply,
                        error=str(exc),
                        updated_at=self._timestamp_factory(),
                    )
                store.save(snapshot)
        return snapshot

    def _explain_context(
        self,
        analysis_id: str,
        ply: int,
        context: ContextResult,
        use_baseline_fallback: bool,
    ) -> _ExplanationBuildResult:
        start = self._clock()
        LOGGER.info(
            "Explanation generation started: analysis_id=%s ply=%s san=%s quality=%s "
            "significance=%s",
            analysis_id,
            ply,
            context.evidence.played.san,
            context.evidence.quality.label,
            context.evidence.significance.label,
        )
        service = ExplanationService(
            context_builder=self._context_builder_factory(),
            coach_provider=self._coach_provider_factory(),
            use_baseline_fallback=use_baseline_fallback,
        )
        result = service.explain_context(context)
        latency_seconds = round(self._clock() - start, 3)
        LOGGER.info(
            "Explanation generation completed: analysis_id=%s ply=%s san=%s model=%s "
            "finish_reason=%s attempts=%s latency_seconds=%.3f fallback=%s",
            analysis_id,
            ply,
            context.evidence.played.san,
            result.model,
            result.finish_reason,
            len(result.attempts),
            latency_seconds,
            result.used_fallback,
        )
        return _ExplanationBuildResult(
            ply=ply,
            explanation=result.explanation,
            segments=result.segments,
            line_cards=result.line_cards,
            latency_seconds=latency_seconds,
            attempts=len(result.attempts),
            model=result.model,
        )


def game_ply_requests(request: GameAnalysisStartRequest) -> list[_PlyRequest]:
    """Build one context-engine request per PGN mainline ply."""

    game = chess.pgn.read_game(io.StringIO(request.pgn))
    if game is None:
        raise ValueError("PGN could not be parsed.")
    moves = list(game.mainline_moves())
    board = game.board()
    ply_requests: list[_PlyRequest] = []
    for ply, move in enumerate(moves, start=1):
        player_color = color_name(board.turn)
        ply_requests.append(
            _PlyRequest(
                ply=ply,
                request=MoveContextRequest(
                    pgn=request.pgn,
                    ply=ply,
                    player_color=player_color,
                    player_level=request.level_for(player_color),
                    time_control=request.time_control,
                ),
            )
        )
        board.push(move)
    return ply_requests


def count_game_plies(pgn: str) -> int:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("PGN could not be parsed.")
    return len(list(game.mainline_moves()))


def game_analysis_context_workers_from_env() -> int:
    return _int_env(
        "G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS",
        DEFAULT_GAME_ANALYSIS_CONTEXT_WORKERS,
    )


def game_analysis_openrouter_concurrency_from_env() -> int:
    return _int_env(
        "G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY",
        DEFAULT_GAME_ANALYSIS_OPENROUTER_CONCURRENCY,
    )


def _build_context(
    builder: Callable[[], MoveContextBuilder],
    ply_request: _PlyRequest,
    clock: Clock,
) -> _ContextBuildResult:
    start = clock()
    context = builder().build(ply_request.request)
    return _ContextBuildResult(
        ply=ply_request.ply,
        context=context,
        latency_seconds=round(clock() - start, 3),
    )


def _move_from_context_result(
    context_result: _ContextBuildResult,
    *,
    requires_explanation: bool,
    include_context: bool,
) -> GameMoveAnalysis:
    context = context_result.context
    return GameMoveAnalysis(
        ply=context_result.ply,
        san=context.evidence.played.san,
        uci=context.evidence.played.uci,
        player_color=context.evidence.request.player_color,
        state="context_ready",
        requires_explanation=requires_explanation,
        quality=context.evidence.quality.label,
        significance=context.evidence.significance,
        beauty=context.evidence.beauty,
        context_latency_seconds=context_result.latency_seconds,
        context=context if include_context else None,
    )


def _snapshot_with_move(
    snapshot: GameAnalysisSnapshot,
    move: GameMoveAnalysis,
    *,
    updated_at: str,
) -> GameAnalysisSnapshot:
    moves = [existing for existing in snapshot.moves if existing.ply != move.ply]
    moves.append(move)
    moves.sort(key=lambda item: item.ply)
    return _snapshot_with_recomputed_counts(snapshot, moves, updated_at=updated_at)


def _snapshot_with_explanation(
    snapshot: GameAnalysisSnapshot,
    explanation: _ExplanationBuildResult,
    *,
    updated_at: str,
) -> GameAnalysisSnapshot:
    moves = [
        move.model_copy(
            update={
                "state": "explained",
                "explanation": explanation.explanation,
                "explanation_segments": explanation.segments,
                "explanation_line_cards": explanation.line_cards,
                "explanation_latency_seconds": explanation.latency_seconds,
                "explanation_attempts": explanation.attempts,
                "explanation_model": explanation.model,
                "explanation_error": None,
            }
        )
        if move.ply == explanation.ply
        else move
        for move in snapshot.moves
    ]
    return _snapshot_with_recomputed_counts(snapshot, moves, updated_at=updated_at)


def _snapshot_with_explanation_error(
    snapshot: GameAnalysisSnapshot,
    *,
    ply: int,
    error: str,
    updated_at: str,
) -> GameAnalysisSnapshot:
    moves = [
        move.model_copy(
            update={
                "state": "explanation_failed",
                "explanation_error": error,
            }
        )
        if move.ply == ply
        else move
        for move in snapshot.moves
    ]
    return _snapshot_with_recomputed_counts(snapshot, moves, updated_at=updated_at)


def _snapshot_with_recomputed_counts(
    snapshot: GameAnalysisSnapshot,
    moves: list[GameMoveAnalysis],
    *,
    updated_at: str,
) -> GameAnalysisSnapshot:
    return snapshot.model_copy(
        update={
            "moves": moves,
            "context_completed": len(moves),
            "explanation_required": sum(move.requires_explanation for move in moves),
            "explanation_completed": sum(move.explanation is not None for move in moves),
            "explanation_failed": sum(move.explanation_error is not None for move in moves),
            "updated_at": updated_at,
        }
    )


def _move_by_ply(snapshot: GameAnalysisSnapshot, ply: int) -> GameMoveAnalysis | None:
    return next((move for move in snapshot.moves if move.ply == ply), None)


def _log_explanation_failure(
    analysis_id: str,
    ply: int,
    move: GameMoveAnalysis | None,
    exc: Exception,
) -> None:
    move_details = (
        f"san={move.san} quality={move.quality} significance={move.significance.label}"
        if move is not None
        else "san=<unknown> quality=<unknown> significance=<unknown>"
    )
    if isinstance(exc, ExplanationVerificationError):
        LOGGER.error(
            "Explanation generation failed: analysis_id=%s ply=%s %s error=%s attempts=%s",
            analysis_id,
            ply,
            move_details,
            _compact_error(str(exc)),
            [_attempt_log_summary(attempt) for attempt in exc.attempts],
        )
        return
    LOGGER.exception(
        "Explanation generation crashed: analysis_id=%s ply=%s %s error=%s",
        analysis_id,
        ply,
        move_details,
        exc,
    )


def _attempt_log_summary(attempt: GenerationAttempt) -> dict[str, object]:
    return {
        "attempt": attempt.attempt_index,
        "provider": attempt.provider_name,
        "model": attempt.model,
        "response_id": attempt.response_id,
        "finish_reason": attempt.finish_reason,
        "verification_passed": attempt.verification_passed,
        "failure_codes": attempt.failure_codes,
        "error": _compact_error(attempt.error) if attempt.error else None,
    }


def _compact_error(error: str, max_length: int = 900) -> str:
    compacted = " ".join(error.split())
    if len(compacted) <= max_length:
        return compacted
    return f"{compacted[: max_length - 3]}..."


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)
