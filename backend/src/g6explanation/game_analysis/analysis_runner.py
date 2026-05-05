"""Background orchestration for full-game analysis jobs."""

from __future__ import annotations

import io
import logging
import os
import re
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
from g6explanation.context_engine.contracts import ColorName, ContextResult
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
    GameAnalysisGame,
    GameAnalysisSnapshot,
    GameAnalysisStartRequest,
    GameMainlineMove,
    GameMoveAnalysis,
    OpeningBookMetadata,
)
from g6explanation.game_analysis.opening_book import OpeningBookPly, run_opening_book_pass
from g6explanation.game_analysis.provider_setup import real_game_analysis_context_builder
from g6explanation.game_analysis.state_store import GameAnalysisStore

DEFAULT_GAME_ANALYSIS_CONTEXT_WORKERS = min(os.cpu_count() or 1, 16)
DEFAULT_GAME_ANALYSIS_OPENROUTER_CONCURRENCY = 30
PGN_CLOCK_RE = re.compile(r"\[%clk\s+(?P<clock>[^\]]+)\]")
LOGGER = logging.getLogger(__name__)

ContextBuilderFactory = Callable[[], MoveContextBuilder]
CoachProviderFactory = Callable[[], CoachModelProvider]
OpeningBookPass = Callable[[Sequence[OpeningBookPly]], dict[int, OpeningBookMetadata]]
Clock = Callable[[], float]
TimestampFactory = Callable[[], str]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class _PlyRequest:
    ply: int
    request: MoveContextRequest
    opening_book_ply: OpeningBookPly
    clock_after_seconds: float | None = None
    think_time_seconds: float | None = None


@dataclass(frozen=True)
class _PlyFrame:
    ply: int
    move_number: int
    player_color: ColorName
    opponent_color: ColorName
    fen_before: str
    san: str
    uci: str
    fen_after: str
    clock_before_seconds: float | None = None
    increment_seconds: float | None = None
    clock_after_seconds: float | None = None
    think_time_seconds: float | None = None


@dataclass(frozen=True)
class _ContextBuildResult:
    ply: int
    context: ContextResult
    latency_seconds: float
    clock_after_seconds: float | None = None
    think_time_seconds: float | None = None


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
        opening_book_pass: OpeningBookPass = run_opening_book_pass,
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
        self._opening_book_pass = opening_book_pass
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
            opening_book_by_ply = _opening_book_metadata_for(
                ply_requests,
                opening_book_pass=self._opening_book_pass,
            )
            snapshot = self._run_context_phase(
                snapshot=snapshot,
                ply_requests=ply_requests,
                opening_book_by_ply=opening_book_by_ply,
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
        opening_book_by_ply: dict[int, OpeningBookMetadata],
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
                    opening_book=opening_book_by_ply.get(context_result.ply),
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

    return [
        _PlyRequest(
            ply=frame.ply,
            request=MoveContextRequest(
                pgn=request.pgn,
                ply=frame.ply,
                player_color=frame.player_color,
                player_level=request.level_for(frame.player_color),
                opponent_level=request.level_for(frame.opponent_color),
                time_control=request.time_control,
                clock_before_seconds=frame.clock_before_seconds,
                increment_seconds=frame.increment_seconds,
            ),
            opening_book_ply=OpeningBookPly(
                ply=frame.ply,
                san=frame.san,
                uci=frame.uci,
                side=frame.player_color,
                fen_before=frame.fen_before,
                fen_after=frame.fen_after,
            ),
            clock_after_seconds=frame.clock_after_seconds,
            think_time_seconds=frame.think_time_seconds,
        )
        for frame in _game_ply_frames(request.pgn, request.time_control)
    ]


def game_analysis_game(pgn: str, time_control: str = "unknown") -> GameAnalysisGame:
    """Build the board-renderable game skeleton without engine or model analysis."""

    moves = [
        GameMainlineMove(
            ply=frame.ply,
            move_number=frame.move_number,
            player_color=frame.player_color,
            san=frame.san,
            uci=frame.uci,
            fen_before=frame.fen_before,
            fen_after=frame.fen_after,
            clock_before_seconds=frame.clock_before_seconds,
            remaining_clock_seconds=frame.clock_after_seconds,
            think_time_seconds=frame.think_time_seconds,
        )
        for frame in _game_ply_frames(pgn, time_control)
    ]
    return GameAnalysisGame(total_plies=len(moves), moves=moves)


def _game_ply_frames(pgn: str, time_control: str) -> list[_PlyFrame]:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("PGN could not be parsed.")
    nodes = list(game.mainline())
    board = game.board()
    base_seconds, increment_seconds = _parse_time_control(time_control)
    remaining_by_side: dict[ColorName, float | None] = {
        "white": base_seconds,
        "black": base_seconds,
    }
    frames: list[_PlyFrame] = []
    for ply, node in enumerate(nodes, start=1):
        move = node.move
        player_color = color_name(board.turn)
        opponent_color: ColorName = "black" if player_color == "white" else "white"
        move_number = board.fullmove_number
        fen_before = board.fen()
        san = board.san(move)
        uci = move.uci()
        board_after = board.copy(stack=False)
        board_after.push(move)
        fen_after = board_after.fen()
        clock_before_seconds = remaining_by_side[player_color]
        clock_after_seconds = _clock_seconds_from_comment(node.comment)
        think_time_seconds = _think_time_seconds(
            clock_before_seconds=clock_before_seconds,
            clock_after_seconds=clock_after_seconds,
            increment_seconds=increment_seconds,
        )
        frames.append(
            _PlyFrame(
                ply=ply,
                move_number=move_number,
                player_color=player_color,
                opponent_color=opponent_color,
                fen_before=fen_before,
                san=san,
                uci=uci,
                fen_after=fen_after,
                clock_before_seconds=clock_before_seconds,
                increment_seconds=increment_seconds,
                clock_after_seconds=clock_after_seconds,
                think_time_seconds=think_time_seconds,
            )
        )
        remaining_by_side[player_color] = clock_after_seconds
        board.push(move)
    return frames


def count_game_plies(pgn: str) -> int:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("PGN could not be parsed.")
    return len(list(game.mainline_moves()))


def _parse_time_control(time_control: str) -> tuple[float | None, float | None]:
    stripped = time_control.strip()
    if not stripped or stripped in {"-", "unknown"}:
        return None, None
    base_text, separator, increment_text = stripped.partition("+")
    if not base_text.isdigit():
        return None, None
    base_seconds = float(int(base_text))
    if not separator:
        return base_seconds, 0.0
    try:
        increment_seconds = float(increment_text)
    except ValueError:
        return base_seconds, None
    return base_seconds, increment_seconds if increment_seconds >= 0 else None


def _clock_seconds_from_comment(comment: str) -> float | None:
    match = PGN_CLOCK_RE.search(comment)
    if match is None:
        return None
    return _parse_clock_token(match.group("clock").strip())


def _parse_clock_token(value: str) -> float | None:
    parts = value.split(":")
    try:
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        if len(parts) == 1:
            return float(parts[0])
    except ValueError:
        return None
    return None


def _think_time_seconds(
    *,
    clock_before_seconds: float | None,
    clock_after_seconds: float | None,
    increment_seconds: float | None,
) -> float | None:
    if clock_before_seconds is None or clock_after_seconds is None:
        return None
    increment = increment_seconds or 0.0
    return round(max(0.0, clock_before_seconds + increment - clock_after_seconds), 3)


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
        clock_after_seconds=ply_request.clock_after_seconds,
        think_time_seconds=ply_request.think_time_seconds,
    )


def _move_from_context_result(
    context_result: _ContextBuildResult,
    *,
    requires_explanation: bool,
    include_context: bool,
    opening_book: OpeningBookMetadata | None,
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
        clock_before_seconds=context.evidence.request.clock_before_seconds,
        remaining_clock_seconds=context_result.clock_after_seconds,
        think_time_seconds=context_result.think_time_seconds,
        opening_book=opening_book,
        context=context if include_context else None,
    )


def _opening_book_metadata_for(
    ply_requests: Sequence[_PlyRequest],
    *,
    opening_book_pass: OpeningBookPass,
) -> dict[int, OpeningBookMetadata]:
    try:
        return opening_book_pass([item.opening_book_ply for item in ply_requests])
    except Exception as exc:
        LOGGER.warning("Opening-book pass failed; continuing without book metadata: %s", exc)
        return {}


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
