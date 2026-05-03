"""No-mock real-game explanation evaluation runner."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from pydantic import Field

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    CandidateMove,
    ColorName,
    ContextContract,
    EngineLine,
    MoveContextRequest,
    PlayerLevel,
)
from g6explanation.context_engine.maia_likelihood import Maia2MoveLikelihoodProvider, MaiaModelType
from g6explanation.context_engine.stockfish_analysis import (
    MIN_STOCKFISH_DEPTH,
    StockfishAnalysisProvider,
)
from g6explanation.explanation_generation import ExplanationService
from g6explanation.explanation_generation.openrouter_chat import OpenRouterCoachModelProvider
from g6explanation.real_game_evaluation.real_games import (
    BYRNE_FISCHER,
    CAPABLANCA_TARTAKOWER,
    KASPAROV_TOPALOV,
    OPERA_GAME,
)


class RealEvaluationSetupError(RuntimeError):
    """Raised when a required real provider is unavailable."""


@dataclass(frozen=True)
class RealExplanationEvalCase:
    case_id: str
    description: str
    player_color: ColorName
    player_level: PlayerLevel
    time_control: str
    expected_san: str
    tags: tuple[str, ...]
    pgn: str | None = None
    ply: int | None = None
    fen_before: str | None = None
    played_move: str | None = None

    def request(self) -> MoveContextRequest:
        if self.pgn is not None and self.ply is not None:
            return MoveContextRequest(
                pgn=self.pgn,
                ply=self.ply,
                player_color=self.player_color,
                player_level=self.player_level,
                time_control=self.time_control,
            )
        if self.fen_before is not None and self.played_move is not None:
            return MoveContextRequest(
                fen_before=self.fen_before,
                played_move=self.played_move,
                player_color=self.player_color,
                player_level=self.player_level,
                time_control=self.time_control,
            )
        raise ValueError("A real explanation eval case needs either PGN+ply or FEN+played_move.")


class RealExplanationEvalRecord(ContextContract):
    case_id: str
    description: str
    tags: list[str]
    passed: bool
    error: str | None = None
    played_san: str | None = None
    played_uci: str | None = None
    player_color: ColorName | None = None
    quality: str | None = None
    score_loss_vs_best_cp: int | None = None
    wdl_expected_score_loss: int | None = None
    significance: str | None = None
    beauty: str | None = None
    stockfish_version: str | None = None
    stockfish_depth: int | None = None
    maia_candidate_count: int = 0
    maia_sources: list[str] = Field(default_factory=list[str])
    played_findability_source: str | None = None
    played_findability: str | None = None
    provider_name: str | None = None
    model: str | None = None
    finish_reason: str | None = None
    used_fallback: bool | None = None
    attempts: int = 0
    failure_codes: list[str] = Field(default_factory=list[str])
    latency_seconds: float | None = None
    explanation: str | None = None


class RealExplanationEvalSummary(ContextContract):
    total_cases: int
    passed_cases: int
    failed_cases: int
    fallback_cases: int
    records: list[RealExplanationEvalRecord]


REAL_EXPLANATION_EVAL_CASES: tuple[RealExplanationEvalCase, ...] = (
    RealExplanationEvalCase(
        case_id="opera-final-mate",
        description="Opera Game final mate",
        pgn=OPERA_GAME,
        ply=33,
        player_color="white",
        player_level=PlayerLevel.rating(2400, "historical-demo"),
        time_control="classical",
        expected_san="Rd8#",
        tags=("opera", "mate", "famous", "best"),
    ),
    RealExplanationEvalCase(
        case_id="opera-black-b5-inaccuracy",
        description="Opera Game defensive inaccuracy before the sacrifice",
        pgn=OPERA_GAME,
        ply=18,
        player_color="black",
        player_level=PlayerLevel.rating(1600, "historical-demo"),
        time_control="classical",
        expected_san="b5",
        tags=("opera", "inaccuracy", "defense"),
    ),
    RealExplanationEvalCase(
        case_id="century-be6",
        description="Game of the Century queen-sacrifice sequence",
        pgn=BYRNE_FISCHER,
        ply=34,
        player_color="black",
        player_level=PlayerLevel.rating(2400, "historical-demo"),
        time_control="classical",
        expected_san="Be6",
        tags=("game-of-the-century", "hard-resource", "famous", "best"),
    ),
    RealExplanationEvalCase(
        case_id="kasparov-rxd4",
        description="Kasparov-Topalov rook sacrifice",
        pgn=KASPAROV_TOPALOV,
        ply=47,
        player_color="white",
        player_level=PlayerLevel.rating(2700, "historical-demo"),
        time_control="classical",
        expected_san="Rxd4",
        tags=("kasparov-topalov", "sacrifice", "hard-resource", "best"),
    ),
    RealExplanationEvalCase(
        case_id="capablanca-g4",
        description="Capablanca-Tartakower quiet rook-endgame expansion",
        pgn=CAPABLANCA_TARTAKOWER,
        ply=61,
        player_color="white",
        player_level=PlayerLevel.rating(2400, "historical-demo"),
        time_control="classical",
        expected_san="g4",
        tags=("capablanca-tartakower", "quiet-positional", "endgame"),
    ),
    RealExplanationEvalCase(
        case_id="forced-only-legal-defense",
        description="Exactly-one-legal-move forced defense",
        fen_before="1Q2kb1r/p2n1ppp/4q3/4p1B1/4P3/8/PPP2PPP/2KR4 b k - 1 16",
        played_move="d7b8",
        player_color="black",
        player_level=PlayerLevel.rating(1800, "synthetic-edge"),
        time_control="rapid",
        expected_san="Nxb8",
        tags=("synthetic", "forced", "only-legal-move"),
    ),
    RealExplanationEvalCase(
        case_id="fools-mate-g4-blunder",
        description="Fool's Mate pattern ordinary blunder",
        fen_before="rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2",
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(900, "synthetic-edge"),
        time_control="blitz",
        expected_san="g4",
        tags=("synthetic", "ordinary-blunder", "mate-threat"),
    ),
    RealExplanationEvalCase(
        case_id="high-wdl-qxa7-good",
        description="High-WDL non-best winning move",
        fen_before="rnb1kbnr/pppppppp/8/8/8/8/QPPPPPPP/RNB1KBNR w KQkq - 0 1",
        played_move="a2a7",
        player_color="white",
        player_level=PlayerLevel.rating(1400, "synthetic-edge"),
        time_control="rapid",
        expected_san="Qxa7",
        tags=("synthetic", "high-wdl-non-best", "winning"),
    ),
)


def select_real_explanation_eval_cases(
    case_ids: Iterable[str] | None,
) -> list[RealExplanationEvalCase]:
    if case_ids is None:
        return list(REAL_EXPLANATION_EVAL_CASES)
    requested = list(case_ids)
    by_id = {case.case_id: case for case in REAL_EXPLANATION_EVAL_CASES}
    unknown = [case_id for case_id in requested if case_id not in by_id]
    if unknown:
        raise ValueError(f"Unknown real explanation eval case ids: {unknown}.")
    return [by_id[case_id] for case_id in requested]


def run_real_explanation_evaluation(
    cases: Sequence[RealExplanationEvalCase],
    output_path: str | Path | None = None,
    use_baseline_fallback: bool = False,
) -> RealExplanationEvalSummary:
    """Run real Stockfish, Maia, and OpenRouter explanation evaluation."""

    context_builder = _real_context_builder()
    service = ExplanationService(
        context_builder=context_builder,
        coach_provider=OpenRouterCoachModelProvider.from_env(),
        use_baseline_fallback=use_baseline_fallback,
    )
    records = [_evaluate_case(case, context_builder, service) for case in cases]
    if output_path is not None:
        _write_jsonl(Path(output_path), records)
    return RealExplanationEvalSummary(
        total_cases=len(records),
        passed_cases=sum(record.passed for record in records),
        failed_cases=sum(not record.passed for record in records),
        fallback_cases=sum(record.used_fallback is True for record in records),
        records=records,
    )


def _evaluate_case(
    case: RealExplanationEvalCase,
    context_builder: MoveContextBuilder,
    service: ExplanationService,
) -> RealExplanationEvalRecord:
    start = time.perf_counter()
    try:
        context = context_builder.build(case.request())
        if context.evidence.played.san != case.expected_san:
            raise AssertionError(
                f"Expected {case.expected_san}, got {context.evidence.played.san}."
            )
        result = service.explain_context(context)
        if result.used_fallback:
            raise AssertionError("Real explanation eval used deterministic fallback.")
        played = _played_candidate(context.evidence.candidates)
        failure_codes = [
            code for attempt in result.attempts for code in attempt.failure_codes if code
        ]
        return RealExplanationEvalRecord(
            case_id=case.case_id,
            description=case.description,
            tags=list(case.tags),
            passed=result.verification.passed and not result.used_fallback,
            played_san=context.evidence.played.san,
            played_uci=context.evidence.played.uci,
            player_color=context.evidence.request.player_color,
            quality=context.evidence.quality.label,
            score_loss_vs_best_cp=context.evidence.quality.score_loss_vs_best_cp,
            wdl_expected_score_loss=context.evidence.quality.wdl_expected_score_loss,
            significance=context.evidence.significance.label,
            beauty=context.evidence.beauty.label,
            stockfish_version=context.evidence.engine.engine_version,
            stockfish_depth=_stockfish_depth(context.evidence.engine.top_lines),
            maia_candidate_count=_maia_candidate_count(context.evidence.candidates),
            maia_sources=_maia_sources(context.evidence.candidates),
            played_findability_source=played.findability_source if played else None,
            played_findability=played.time_adjusted_findability if played else None,
            provider_name=result.provider_name,
            model=result.model,
            finish_reason=result.finish_reason,
            used_fallback=result.used_fallback,
            attempts=len(result.attempts),
            failure_codes=failure_codes,
            latency_seconds=round(time.perf_counter() - start, 3),
            explanation=result.explanation,
        )
    except Exception as exc:
        return RealExplanationEvalRecord(
            case_id=case.case_id,
            description=case.description,
            tags=list(case.tags),
            passed=False,
            error=f"{type(exc).__name__}: {exc}",
            latency_seconds=round(time.perf_counter() - start, 3),
        )


def _real_context_builder() -> MoveContextBuilder:
    stockfish_binary = (
        os.getenv("G6_REAL_LLM_EVAL_STOCKFISH_BINARY")
        or os.getenv("G6EXPLANATION_STOCKFISH_BINARY")
        or shutil.which("stockfish")
    )
    if stockfish_binary is None:
        raise RealEvaluationSetupError(
            "Real explanation evaluation requires Stockfish on PATH or "
            "G6_REAL_LLM_EVAL_STOCKFISH_BINARY."
        )
    if importlib.util.find_spec("maia2") is None:
        raise RealEvaluationSetupError(
            "Real explanation evaluation requires maia2. Install with `uv sync --extra maia`."
        )
    return MoveContextBuilder(
        StockfishAnalysisProvider(
            binary_path=stockfish_binary,
            depth=_int_env("G6_REAL_LLM_EVAL_STOCKFISH_DEPTH", MIN_STOCKFISH_DEPTH),
            multipv=_int_env("G6_REAL_LLM_EVAL_STOCKFISH_MULTIPV", 5),
            threads=_optional_int_env("G6_REAL_LLM_EVAL_STOCKFISH_THREADS"),
            hash_mb=_optional_int_env("G6_REAL_LLM_EVAL_STOCKFISH_HASH_MB"),
            show_wdl=True,
        ),
        Maia2MoveLikelihoodProvider(
            model_type=_maia_model_type(),
            device=_maia_device(),
            save_root=os.getenv("MAIA2_MODEL_ROOT", "./maia2_models"),
            top_move_limit=_int_env("G6_REAL_LLM_EVAL_MAIA2_TOP_MOVES", 5),
        ),
    )


def _played_candidate(candidates: list[CandidateMove]) -> CandidateMove | None:
    return next((candidate for candidate in candidates if "played_move" in candidate.roles), None)


def _stockfish_depth(lines: Sequence[EngineLine]) -> int | None:
    depths = [line.depth for line in lines if line.depth is not None]
    return min(depths) if depths else None


def _maia_candidate_count(candidates: list[CandidateMove]) -> int:
    return sum(candidate.findability_source.startswith("maia2_") for candidate in candidates)


def _maia_sources(candidates: list[CandidateMove]) -> list[str]:
    return sorted(
        {
            candidate.findability_source
            for candidate in candidates
            if candidate.findability_source.startswith("maia2_")
        }
    )


def _write_jsonl(path: Path, records: list[RealExplanationEvalRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(record.to_dict(), sort_keys=True) for record in records)
    path.write_text(f"{payload}\n", encoding="utf-8")


def _maia_model_type() -> MaiaModelType:
    model_type = os.getenv("G6_REAL_LLM_EVAL_MAIA2_MODEL", "auto")
    if model_type not in {"auto", "rapid", "blitz"}:
        raise RealEvaluationSetupError(
            "G6_REAL_LLM_EVAL_MAIA2_MODEL must be one of: auto, rapid, blitz."
        )
    return cast(MaiaModelType, model_type)


def _maia_device() -> Literal["cpu", "gpu"]:
    device = os.getenv("G6_REAL_LLM_EVAL_MAIA2_DEVICE", "cpu")
    if device not in {"cpu", "gpu"}:
        raise RealEvaluationSetupError("G6_REAL_LLM_EVAL_MAIA2_DEVICE must be cpu or gpu.")
    return cast("Literal['cpu', 'gpu']", device)


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _optional_int_env(name: str) -> int | None:
    value = os.getenv(name)
    return None if value is None else int(value)
