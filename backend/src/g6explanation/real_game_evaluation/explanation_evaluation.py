"""No-mock real-game explanation evaluation runner."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import time
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias, cast

from pydantic import Field

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    CandidateMove,
    ColorName,
    ContextContract,
    ContextResult,
    EngineLine,
    LLMContext,
    MoveContextRequest,
    PlayerLevel,
)
from g6explanation.context_engine.maia_likelihood import Maia2MoveLikelihoodProvider, MaiaModelType
from g6explanation.context_engine.stockfish_analysis import (
    MIN_STOCKFISH_DEPTH,
    StockfishAnalysisProvider,
)
from g6explanation.explanation_generation import ExplanationService
from g6explanation.explanation_generation.contracts import (
    EXPLANATION_SCHEMA_VERSION,
    PROMPT_ID,
    GenerationAttempt,
)
from g6explanation.explanation_generation.exceptions import ExplanationVerificationError
from g6explanation.explanation_generation.openrouter_chat import OpenRouterCoachModelProvider
from g6explanation.real_game_evaluation.real_games import (
    BYRNE_FISCHER,
    CAPABLANCA_TARTAKOWER,
    KASPAROV_TOPALOV,
    OPERA_GAME,
)
from g6explanation.real_game_evaluation.source_rights import (
    CHESS_COM_REQUIRES_AUTHORIZATION_SOURCE,
    LICHESS_DATABASE_CC0_SOURCE,
    PROJECT_HISTORICAL_GAME_SOURCE,
    PROJECT_SYNTHETIC_SOURCE,
    ExplanationDataSource,
)

REAL_EXPLANATION_EVAL_REPORT_VERSION = "real_explanation_eval_report.v1"
DEFAULT_REAL_LLM_EVAL_OPENROUTER_CONCURRENCY = 30
DEFAULT_REAL_EXPLANATION_MANUAL_REVIEWS_PATH = Path(
    "docs/development/real-explanation-manual-reviews.json"
)
SYNTHETIC_RECAPTURE_PGN = """
[Event "Synthetic Recapture Regression"]
[Site "?"]
[Date "2026.05.04"]
[Round "?"]
[White "Synthetic White"]
[Black "Synthetic Black"]
[Result "*"]

1. e4 c6 2. Nf3 d5 3. exd5 cxd5 *
""".strip()
ManualReviewCategory: TypeAlias = Literal[
    "not_reviewed",
    "context_missing_evidence",
    "wrong_context_policy",
    "prompt_issue",
    "verifier_too_weak",
    "verifier_too_strict",
    "model_wording_issue",
    "provider_or_runtime_issue",
    "accepted",
]


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
    clock_before_seconds: float | None = None
    increment_seconds: float | None = None
    think_time_seconds: float | None = None
    source: ExplanationDataSource = PROJECT_SYNTHETIC_SOURCE

    def request(self) -> MoveContextRequest:
        if self.pgn is not None and self.ply is not None:
            return MoveContextRequest(
                pgn=self.pgn,
                ply=self.ply,
                player_color=self.player_color,
                player_level=self.player_level,
                time_control=self.time_control,
                clock_before_seconds=self.clock_before_seconds,
                increment_seconds=self.increment_seconds,
                think_time_seconds=self.think_time_seconds,
            )
        if self.fen_before is not None and self.played_move is not None:
            return MoveContextRequest(
                fen_before=self.fen_before,
                played_move=self.played_move,
                player_color=self.player_color,
                player_level=self.player_level,
                time_control=self.time_control,
                clock_before_seconds=self.clock_before_seconds,
                increment_seconds=self.increment_seconds,
                think_time_seconds=self.think_time_seconds,
            )
        raise ValueError("A real explanation eval case needs either PGN+ply or FEN+played_move.")


class RealExplanationEvalRecord(ContextContract):
    case_id: str
    description: str
    tags: list[str]
    source: ExplanationDataSource | None = None
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
    schema_version: str | None = None
    context_version: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    verifier_version: str | None = None
    finish_reason: str | None = None
    used_fallback: bool | None = None
    attempts: int = 0
    failure_codes: list[str] = Field(default_factory=list[str])
    generation_attempts: list[GenerationAttempt] = Field(default_factory=list[GenerationAttempt])
    latency_seconds: float | None = None
    llm_context: LLMContext | None = None
    explanation: str | None = None
    manual_review_category: ManualReviewCategory = "not_reviewed"
    manual_review_notes: str | None = None


class RealExplanationManualReview(ContextContract):
    case_id: str
    category: ManualReviewCategory
    notes: str
    model: str | None = None
    attempts: int | None = None
    failure_codes: list[str] | None = None


class RealExplanationEvalSummary(ContextContract):
    total_cases: int
    passed_cases: int
    failed_cases: int
    fallback_cases: int
    records: list[RealExplanationEvalRecord]


class RealExplanationEvalCaseReport(ContextContract):
    case_id: str
    passed: bool
    used_fallback: bool | None
    attempts: int
    failure_codes: list[str] = Field(default_factory=list[str])
    latency_seconds: float | None = None
    model: str | None = None
    stockfish_depth: int | None = None
    maia_sources: list[str] = Field(default_factory=list[str])
    failed_attempt_explanations: list[str] = Field(default_factory=list[str])
    manual_review_category: ManualReviewCategory
    manual_review_notes: str | None = None


class RealExplanationEvalReport(ContextContract):
    report_version: str = REAL_EXPLANATION_EVAL_REPORT_VERSION
    total_cases: int
    passed_cases: int
    failed_cases: int
    fallback_cases: int
    retry_cases: int
    pass_rate: float
    fallback_rate: float
    retry_rate: float
    failure_code_counts: dict[str, int] = Field(default_factory=dict[str, int])
    finish_reason_counts: dict[str, int] = Field(default_factory=dict[str, int])
    provider_counts: dict[str, int] = Field(default_factory=dict[str, int])
    model_counts: dict[str, int] = Field(default_factory=dict[str, int])
    source_counts: dict[str, int] = Field(default_factory=dict[str, int])
    stockfish_versions: list[str] = Field(default_factory=list[str])
    stockfish_min_depth: int | None = None
    maia_sources: list[str] = Field(default_factory=list[str])
    latency_avg_seconds: float | None = None
    latency_p50_seconds: float | None = None
    latency_max_seconds: float | None = None
    manual_review_counts: dict[str, int] = Field(default_factory=dict[str, int])
    review_required_case_ids: list[str] = Field(default_factory=list[str])
    case_reports: list[RealExplanationEvalCaseReport] = Field(
        default_factory=list[RealExplanationEvalCaseReport]
    )


class RealExplanationPromotionGateIssue(ContextContract):
    code: str
    message: str


class RealExplanationPromotionGateResult(ContextContract):
    passed: bool
    issues: list[RealExplanationPromotionGateIssue] = Field(
        default_factory=list[RealExplanationPromotionGateIssue]
    )
    baseline_total_cases: int
    current_total_cases: int
    baseline_pass_rate: float
    current_pass_rate: float
    baseline_fallback_rate: float
    current_fallback_rate: float
    baseline_retry_rate: float
    current_retry_rate: float


@dataclass(frozen=True)
class _PreparedRealExplanationEvalCase:
    case: RealExplanationEvalCase
    context: ContextResult
    context_latency_seconds: float


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
        source=PROJECT_HISTORICAL_GAME_SOURCE,
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
        source=PROJECT_HISTORICAL_GAME_SOURCE,
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
        source=PROJECT_HISTORICAL_GAME_SOURCE,
    ),
    RealExplanationEvalCase(
        case_id="century-na4-objection",
        description="Game of the Century Na4 fork whose apparent capture is tactically punished",
        pgn=BYRNE_FISCHER,
        ply=22,
        player_color="black",
        player_level=PlayerLevel.rating(2300, "historical-demo"),
        time_control="classical",
        expected_san="Na4",
        tags=("game-of-the-century", "objection-line", "fork", "best"),
        source=PROJECT_HISTORICAL_GAME_SOURCE,
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
        source=PROJECT_HISTORICAL_GAME_SOURCE,
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
        source=PROJECT_HISTORICAL_GAME_SOURCE,
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
    RealExplanationEvalCase(
        case_id="synthetic-cxd5-recapture-recovery",
        description="Opening recapture that restores material instead of winning a pawn",
        pgn=SYNTHETIC_RECAPTURE_PGN,
        ply=6,
        player_color="black",
        player_level=PlayerLevel.rating(1200, "synthetic-edge"),
        time_control="rapid",
        expected_san="cxd5",
        tags=("synthetic", "recapture", "material-recovery", "opening"),
    ),
    RealExplanationEvalCase(
        case_id="synthetic-bxf3-bishop-knight-trade",
        description="Unplayed Bxf3 alternative trades bishop for knight instead of winning one",
        fen_before="r2qkb1r/pp2pppp/2n2n2/1B1p4/3P2b1/5N1P/PPP2PP1/RNBQ1RK1 b kq - 0 7",
        played_move="g4h5",
        player_color="black",
        player_level=PlayerLevel.rating(1200, "synthetic-edge"),
        time_control="rapid",
        expected_san="Bh5",
        tags=("synthetic", "material-trade", "black-perspective", "alternative"),
    ),
    RealExplanationEvalCase(
        case_id="chesscom-168288554622-nb6-rook-fork",
        description="User-requested Chess.com position where Nb6 attacks both rooks",
        fen_before="r1b3k1/1p1r2pn/p7/5p2/2NppP2/6B1/PPP3PP/2KR3R w - - 0 22",
        played_move="c4b6",
        player_color="white",
        player_level=PlayerLevel.rating(1215, "chess.com"),
        time_control="180",
        expected_san="Nb6",
        tags=("chesscom", "user-requested", "rook-fork", "critical"),
        source=CHESS_COM_REQUIRES_AUTHORIZATION_SOURCE,
    ),
    RealExplanationEvalCase(
        case_id="synthetic-g3-bishop-route-development",
        description="Opening pawn move that opens a bishop diagonal route",
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        played_move="g2g3",
        player_color="white",
        player_level=PlayerLevel.rating(1400, "synthetic-edge"),
        time_control="rapid",
        expected_san="g3",
        tags=("synthetic", "opening", "bishop-route", "development"),
    ),
    RealExplanationEvalCase(
        case_id="castling-low-time-beginner",
        description="Beginner low-time castling notation edge case",
        fen_before="r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
        played_move="e1g1",
        player_color="white",
        player_level=PlayerLevel.rating(800, "synthetic-edge"),
        time_control="blitz",
        clock_before_seconds=8,
        increment_seconds=0,
        expected_san="O-O",
        tags=("synthetic", "castling", "low-time", "beginner"),
    ),
    RealExplanationEvalCase(
        case_id="en-passant-intermediate",
        description="Intermediate en-passant notation edge case",
        fen_before="rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3",
        played_move="e5d6",
        player_color="white",
        player_level=PlayerLevel.rating(1500, "synthetic-edge"),
        time_control="rapid",
        expected_san="exd6",
        tags=("synthetic", "en-passant", "intermediate"),
    ),
    RealExplanationEvalCase(
        case_id="promotion-advanced",
        description="Advanced promotion notation edge case",
        fen_before="8/P7/8/8/8/8/8/k6K w - - 0 1",
        played_move="a7a8q",
        player_color="white",
        player_level=PlayerLevel.rating(2200, "synthetic-edge"),
        time_control="rapid",
        expected_san="a8=Q+",
        tags=("synthetic", "promotion", "advanced"),
    ),
    RealExplanationEvalCase(
        case_id="black-missed-mate-nf6",
        description="Black-perspective missed immediate mate",
        fen_before="rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq g3 0 2",
        played_move="g8f6",
        player_color="black",
        player_level=PlayerLevel.rating(900, "synthetic-edge"),
        time_control="blitz",
        expected_san="Nf6",
        tags=("synthetic", "missed-win", "black-perspective", "beginner"),
    ),
    RealExplanationEvalCase(
        case_id="lichess-00008-source-bxg3",
        description="Lichess puzzle 00008 source-game move Bxg3",
        fen_before="r6k/pp2r2p/4Rp1Q/3p4/8/1N1P2R1/PqP2bPP/7K b - - 0 24",
        played_move="f2g3",
        player_color="black",
        player_level=PlayerLevel.rating(1800, "lichess-puzzle-rating"),
        time_control="rapid",
        expected_san="Bxg3",
        tags=("lichess", "puzzle-source-move", "hanging-piece", "middlegame"),
        source=LICHESS_DATABASE_CC0_SOURCE,
    ),
    RealExplanationEvalCase(
        case_id="lichess-00008-solution-rxe7",
        description="Lichess puzzle 00008 solution move Rxe7",
        fen_before="r6k/pp2r2p/4Rp1Q/3p4/8/1N1P2b1/PqP3PP/7K w - - 0 25",
        played_move="e6e7",
        player_color="white",
        player_level=PlayerLevel.rating(1800, "lichess-puzzle-rating"),
        time_control="rapid",
        expected_san="Rxe7",
        tags=("lichess", "puzzle-solution", "hanging-piece", "middlegame"),
        source=LICHESS_DATABASE_CC0_SOURCE,
    ),
    RealExplanationEvalCase(
        case_id="lichess-0000d-source-qd6",
        description="Lichess puzzle 0000D source-game move Qd6",
        fen_before="5rk1/1p3ppp/pq3b2/8/8/1P1Q1N2/P4PPP/3R2K1 w - - 2 27",
        played_move="d3d6",
        player_color="white",
        player_level=PlayerLevel.rating(1500, "lichess-puzzle-rating"),
        time_control="rapid",
        expected_san="Qd6",
        tags=("lichess", "puzzle-source-move", "endgame"),
        source=LICHESS_DATABASE_CC0_SOURCE,
    ),
    RealExplanationEvalCase(
        case_id="lichess-0000d-solution-rd8",
        description="Lichess puzzle 0000D solution move Rd8",
        fen_before="5rk1/1p3ppp/pq1Q1b2/8/8/1P3N2/P4PPP/3R2K1 b - - 3 27",
        played_move="f8d8",
        player_color="black",
        player_level=PlayerLevel.rating(1500, "lichess-puzzle-rating"),
        time_control="rapid",
        expected_san="Rd8",
        tags=("lichess", "puzzle-solution", "endgame"),
        source=LICHESS_DATABASE_CC0_SOURCE,
    ),
    RealExplanationEvalCase(
        case_id="lichess-000rz-source-nxe6",
        description="Lichess puzzle 000rZ source-game move Nxe6",
        fen_before="2kr1b1r/p1p2pp1/2pqb3/7p/3N2n1/2NPB3/PPP2PPP/R2Q1RK1 w - - 2 13",
        played_move="d4e6",
        player_color="white",
        player_level=PlayerLevel.rating(900, "lichess-puzzle-rating"),
        time_control="rapid",
        expected_san="Nxe6",
        tags=("lichess", "puzzle-source-move", "mate-threat", "opening"),
        source=LICHESS_DATABASE_CC0_SOURCE,
    ),
    RealExplanationEvalCase(
        case_id="lichess-000rz-solution-qxh2-mate",
        description="Lichess puzzle 000rZ solution move Qxh2#",
        fen_before="2kr1b1r/p1p2pp1/2pqN3/7p/6n1/2NPB3/PPP2PPP/R2Q1RK1 b - - 0 13",
        played_move="d6h2",
        player_color="black",
        player_level=PlayerLevel.rating(900, "lichess-puzzle-rating"),
        time_control="rapid",
        expected_san="Qxh2#",
        tags=("lichess", "puzzle-solution", "mate", "opening"),
        source=LICHESS_DATABASE_CC0_SOURCE,
    ),
    RealExplanationEvalCase(
        case_id="lichess-001oo-source-qa4",
        description="Lichess puzzle 001Oo source-game move Qa4",
        fen_before="6k1/4p1bp/6p1/1p1pP3/1PpPp3/2P1P3/Q2B1KPP/3q4 b - - 2 23",
        played_move="d1a4",
        player_color="black",
        player_level=PlayerLevel.rating(2000, "lichess-puzzle-rating"),
        time_control="rapid",
        expected_san="Qa4",
        tags=("lichess", "puzzle-source-move", "quiet-move", "endgame"),
        source=LICHESS_DATABASE_CC0_SOURCE,
    ),
    RealExplanationEvalCase(
        case_id="lichess-001kr-solution-rf8-mate",
        description="Lichess puzzle 001KR solution move Rf8#",
        fen_before="6k1/p1p3pp/4N3/1p6/2q1r1n1/2B5/PP4PP/3R1R1K w - - 0 29",
        played_move="f1f8",
        player_color="white",
        player_level=PlayerLevel.rating(650, "lichess-puzzle-rating"),
        time_control="rapid",
        expected_san="Rf8#",
        tags=("lichess", "puzzle-solution", "mate", "middlegame", "beginner"),
        source=LICHESS_DATABASE_CC0_SOURCE,
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
    report_path: str | Path | None = None,
    use_baseline_fallback: bool = False,
    manual_review_path: str | Path | None = None,
    manual_reviews: Mapping[str, RealExplanationManualReview] | None = None,
) -> RealExplanationEvalSummary:
    """Run real Stockfish, Maia, and OpenRouter explanation evaluation."""

    reviews = _load_default_manual_reviews(manual_review_path)
    if manual_reviews is not None:
        reviews.update(manual_reviews)
    context_builder = _real_context_builder()
    service = ExplanationService(
        context_builder=context_builder,
        coach_provider=OpenRouterCoachModelProvider.from_env(),
        use_baseline_fallback=use_baseline_fallback,
    )
    records_by_index: list[RealExplanationEvalRecord | None] = [None] * len(cases)
    prepared_cases: list[tuple[int, _PreparedRealExplanationEvalCase]] = []
    for index, case in enumerate(cases):
        prepared_or_record = _prepare_case(case, context_builder)
        if isinstance(prepared_or_record, RealExplanationEvalRecord):
            records_by_index[index] = prepared_or_record
        else:
            prepared_cases.append((index, prepared_or_record))

    if prepared_cases:
        max_workers = real_explanation_openrouter_generation_concurrency(len(prepared_cases))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_evaluate_prepared_case, prepared, service): index
                for index, prepared in prepared_cases
            }
            for future in as_completed(futures):
                records_by_index[futures[future]] = future.result()

    records = apply_real_explanation_manual_reviews(
        [record for record in records_by_index if record is not None],
        reviews,
    )
    if output_path is not None:
        _write_jsonl(Path(output_path), records)
    summary = summarize_real_explanation_eval_records(records)
    if report_path is not None:
        write_real_explanation_eval_report(summary, Path(report_path))
    return summary


def summarize_real_explanation_eval_records(
    records: Sequence[RealExplanationEvalRecord],
) -> RealExplanationEvalSummary:
    return RealExplanationEvalSummary(
        total_cases=len(records),
        passed_cases=sum(record.passed for record in records),
        failed_cases=sum(not record.passed for record in records),
        fallback_cases=sum(record.used_fallback is True for record in records),
        records=list(records),
    )


def load_real_explanation_eval_records(path: str | Path) -> list[RealExplanationEvalRecord]:
    records: list[RealExplanationEvalRecord] = []
    for line_number, raw_line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            records.append(RealExplanationEvalRecord.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(f"Invalid eval JSONL record at line {line_number}.") from exc
    return records


def load_real_explanation_manual_reviews(
    path: str | Path,
) -> dict[str, RealExplanationManualReview]:
    payload: object = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload_mapping = cast(dict[object, object], payload)
        if not all(isinstance(key, str) for key in payload_mapping):
            raise ValueError("Manual review file object must use string keys.")
        raw_reviews: object = cast(dict[str, object], payload_mapping).get("reviews")
    else:
        raw_reviews = payload
    if not isinstance(raw_reviews, list):
        raise ValueError("Manual review file must contain a list or a {'reviews': [...]} object.")

    reviews: dict[str, RealExplanationManualReview] = {}
    for index, raw_review in enumerate(cast(list[object], raw_reviews), 1):
        if not isinstance(raw_review, dict):
            raise ValueError(f"Manual review #{index} must be an object with string keys.")
        raw_review_mapping = cast(dict[object, object], raw_review)
        if not all(isinstance(key, str) for key in raw_review_mapping):
            raise ValueError(f"Manual review #{index} must be an object with string keys.")
        review = RealExplanationManualReview.model_validate(
            cast(dict[str, object], raw_review_mapping)
        )
        if review.case_id in reviews:
            raise ValueError(f"Duplicate manual review for case {review.case_id!r}.")
        if review.category == "not_reviewed":
            raise ValueError(f"Manual review #{index} cannot use category 'not_reviewed'.")
        reviews[review.case_id] = review
    return reviews


def apply_real_explanation_manual_reviews(
    records: Sequence[RealExplanationEvalRecord],
    reviews: Mapping[str, RealExplanationManualReview],
) -> list[RealExplanationEvalRecord]:
    return [_apply_manual_review(record, reviews) for record in records]


def build_real_explanation_eval_report(
    summary: RealExplanationEvalSummary,
) -> RealExplanationEvalReport:
    records = summary.records
    latencies = sorted(record.latency_seconds for record in records if record.latency_seconds)
    depths = [record.stockfish_depth for record in records if record.stockfish_depth is not None]
    retry_records = [record for record in records if record.attempts > 1]
    failure_codes = [code for record in records for code in record.failure_codes]
    review_required = [
        record.case_id
        for record in records
        if _needs_manual_review(record) and record.manual_review_category == "not_reviewed"
    ]
    return RealExplanationEvalReport(
        total_cases=summary.total_cases,
        passed_cases=summary.passed_cases,
        failed_cases=summary.failed_cases,
        fallback_cases=summary.fallback_cases,
        retry_cases=len(retry_records),
        pass_rate=_rate(summary.passed_cases, summary.total_cases),
        fallback_rate=_rate(summary.fallback_cases, summary.total_cases),
        retry_rate=_rate(len(retry_records), summary.total_cases),
        failure_code_counts=dict(sorted(Counter(failure_codes).items())),
        finish_reason_counts=_count_present(record.finish_reason for record in records),
        provider_counts=_count_present(record.provider_name for record in records),
        model_counts=_count_present(record.model for record in records),
        source_counts=_count_present(
            record.source.name if record.source else None for record in records
        ),
        stockfish_versions=sorted(
            {version for record in records if (version := record.stockfish_version)}
        ),
        stockfish_min_depth=min(depths) if depths else None,
        maia_sources=sorted({source for record in records for source in record.maia_sources}),
        latency_avg_seconds=_rounded(sum(latencies) / len(latencies)) if latencies else None,
        latency_p50_seconds=_percentile(latencies, 0.5),
        latency_max_seconds=max(latencies) if latencies else None,
        manual_review_counts=_count_present(record.manual_review_category for record in records),
        review_required_case_ids=review_required,
        case_reports=[
            RealExplanationEvalCaseReport(
                case_id=record.case_id,
                passed=record.passed,
                used_fallback=record.used_fallback,
                attempts=record.attempts,
                failure_codes=record.failure_codes,
                latency_seconds=record.latency_seconds,
                model=record.model,
                stockfish_depth=record.stockfish_depth,
                maia_sources=record.maia_sources,
                failed_attempt_explanations=_failed_attempt_explanations(record),
                manual_review_category=record.manual_review_category,
                manual_review_notes=record.manual_review_notes,
            )
            for record in records
        ],
    )


def build_real_explanation_eval_report_from_jsonl(
    path: str | Path,
    manual_review_path: str | Path | None = None,
    manual_reviews: Mapping[str, RealExplanationManualReview] | None = None,
) -> RealExplanationEvalReport:
    reviews = _load_default_manual_reviews(manual_review_path)
    if manual_reviews is not None:
        reviews.update(manual_reviews)
    records = apply_real_explanation_manual_reviews(
        load_real_explanation_eval_records(path), reviews
    )
    return build_real_explanation_eval_report(summarize_real_explanation_eval_records(records))


def evaluate_real_explanation_promotion_gate(
    baseline: RealExplanationEvalReport,
    current: RealExplanationEvalReport,
) -> RealExplanationPromotionGateResult:
    """Compare a candidate real-eval report against the prior promoted report."""

    issues: list[RealExplanationPromotionGateIssue] = []
    _gate_if(
        issues,
        current.total_cases < baseline.total_cases,
        "case_count_regressed",
        (
            "Current report covers fewer cases than baseline: "
            f"{current.total_cases} < {baseline.total_cases}."
        ),
    )
    _gate_if(
        issues,
        current.failed_cases > baseline.failed_cases,
        "failed_cases_regressed",
        (
            "Current report has more failed cases than baseline: "
            f"{current.failed_cases} > {baseline.failed_cases}."
        ),
    )
    _gate_if(
        issues,
        current.pass_rate < baseline.pass_rate,
        "pass_rate_regressed",
        (
            "Current pass rate is below baseline: "
            f"{_percent(current.pass_rate)} < {_percent(baseline.pass_rate)}."
        ),
    )
    _gate_if(
        issues,
        current.fallback_cases > baseline.fallback_cases,
        "fallback_cases_regressed",
        (
            "Current report has more fallback cases than baseline: "
            f"{current.fallback_cases} > {baseline.fallback_cases}."
        ),
    )
    _gate_if(
        issues,
        current.retry_cases > baseline.retry_cases,
        "retry_cases_regressed",
        (
            "Current report has more retry cases than baseline: "
            f"{current.retry_cases} > {baseline.retry_cases}."
        ),
    )
    for code, current_count in current.failure_code_counts.items():
        baseline_count = baseline.failure_code_counts.get(code, 0)
        _gate_if(
            issues,
            current_count > baseline_count,
            "failure_code_regressed",
            (f"Failure code {code!r} regressed: {current_count} > {baseline_count}."),
        )
    _gate_if(
        issues,
        bool(current.review_required_case_ids),
        "manual_review_required",
        (
            "Current report has unreviewed records requiring manual review: "
            f"{', '.join(current.review_required_case_ids)}."
        ),
    )
    return RealExplanationPromotionGateResult(
        passed=not issues,
        issues=issues,
        baseline_total_cases=baseline.total_cases,
        current_total_cases=current.total_cases,
        baseline_pass_rate=baseline.pass_rate,
        current_pass_rate=current.pass_rate,
        baseline_fallback_rate=baseline.fallback_rate,
        current_fallback_rate=current.fallback_rate,
        baseline_retry_rate=baseline.retry_rate,
        current_retry_rate=current.retry_rate,
    )


def write_real_explanation_eval_report(
    summary: RealExplanationEvalSummary,
    path: str | Path,
) -> RealExplanationEvalReport:
    report = build_real_explanation_eval_report(summary)
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.suffix.lower() == ".json":
        report_path.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        report_path.write_text(render_real_explanation_eval_report_markdown(report), "utf-8")
    return report


def render_real_explanation_eval_report_markdown(report: RealExplanationEvalReport) -> str:
    lines = [
        "# Real Explanation Evaluation Report",
        "",
        f"- Report version: `{report.report_version}`",
        f"- Cases: {report.passed_cases}/{report.total_cases} passed",
        f"- Pass rate: {_percent(report.pass_rate)}",
        f"- Fallback rate: {_percent(report.fallback_rate)}",
        f"- Retry rate: {_percent(report.retry_rate)}",
        f"- Stockfish minimum depth: {report.stockfish_min_depth or 'n/a'}",
        f"- Stockfish versions: {_join_or_none(report.stockfish_versions)}",
        f"- Maia sources: {_join_or_none(report.maia_sources)}",
        f"- Models: {_format_counts(report.model_counts)}",
        f"- Data sources: {_format_counts(report.source_counts)}",
        f"- Latency seconds: avg={_display_number(report.latency_avg_seconds)}, "
        f"p50={_display_number(report.latency_p50_seconds)}, "
        f"max={_display_number(report.latency_max_seconds)}",
        "",
        "## Failure Codes",
        "",
        _format_counts(report.failure_code_counts),
        "",
        "## Manual Review",
        "",
        f"- Review counts: {_format_counts(report.manual_review_counts)}",
        f"- Review required cases: {_join_or_none(report.review_required_case_ids)}",
        "",
        "## Cases",
        "",
        "| Case | Passed | Attempts | Fallback | Failure codes | Review |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for case in report.case_reports:
        lines.append(
            "| "
            f"{case.case_id} | "
            f"{'yes' if case.passed else 'no'} | "
            f"{case.attempts} | "
            f"{'yes' if case.used_fallback else 'no'} | "
            f"{_join_or_none(case.failure_codes)} | "
            f"{case.manual_review_category} |"
        )
    lines.append("")
    failed_attempt_cases = [
        case for case in report.case_reports if case.failed_attempt_explanations
    ]
    if failed_attempt_cases:
        lines.extend(["## Failed Attempt Explanations", ""])
        for case in failed_attempt_cases:
            lines.extend([f"### {case.case_id}", ""])
            for index, explanation in enumerate(case.failed_attempt_explanations, 1):
                lines.append(f"- Attempt {index}: {explanation}")
            lines.append("")
    return "\n".join(lines)


def _prepare_case(
    case: RealExplanationEvalCase,
    context_builder: MoveContextBuilder,
) -> _PreparedRealExplanationEvalCase | RealExplanationEvalRecord:
    start = time.perf_counter()
    context: ContextResult | None = None
    try:
        context = context_builder.build(case.request())
        if context.evidence.played.san != case.expected_san:
            raise AssertionError(
                f"Expected {case.expected_san}, got {context.evidence.played.san}."
            )
        return _PreparedRealExplanationEvalCase(
            case=case,
            context=context,
            context_latency_seconds=time.perf_counter() - start,
        )
    except Exception as exc:
        return _failure_record_from_exception(
            case=case,
            exc=exc,
            context=context,
            latency_seconds=round(time.perf_counter() - start, 3),
        )


def _evaluate_prepared_case(
    prepared: _PreparedRealExplanationEvalCase,
    service: ExplanationService,
) -> RealExplanationEvalRecord:
    start = time.perf_counter()
    case = prepared.case
    context = prepared.context
    try:
        result = service.explain_context(context)
        if result.used_fallback:
            raise AssertionError("Real explanation eval used deterministic fallback.")
        played = _played_candidate(context.evidence.candidates)
        failure_codes = [
            code for attempt in result.attempts for code in attempt.failure_codes if code
        ]
        latency_seconds = prepared.context_latency_seconds + (time.perf_counter() - start)
        return RealExplanationEvalRecord(
            case_id=case.case_id,
            description=case.description,
            tags=list(case.tags),
            source=case.source,
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
            schema_version=result.schema_version,
            context_version=result.context_version,
            prompt_id=result.prompt_id,
            prompt_version=result.prompt_version,
            verifier_version=result.verifier_version,
            finish_reason=result.finish_reason,
            used_fallback=result.used_fallback,
            attempts=len(result.attempts),
            failure_codes=failure_codes,
            generation_attempts=result.attempts,
            latency_seconds=round(latency_seconds, 3),
            llm_context=context.llm_context,
            explanation=result.explanation,
        )
    except Exception as exc:
        latency_seconds = prepared.context_latency_seconds + (time.perf_counter() - start)
        return _failure_record_from_exception(
            case=case,
            exc=exc,
            context=context,
            latency_seconds=round(latency_seconds, 3),
        )


def _failure_record_from_exception(
    *,
    case: RealExplanationEvalCase,
    exc: Exception,
    context: ContextResult | None,
    latency_seconds: float,
) -> RealExplanationEvalRecord:
    attempts: list[GenerationAttempt] = (
        exc.attempts if isinstance(exc, ExplanationVerificationError) else []
    )
    failure_codes = [code for attempt in attempts for code in attempt.failure_codes if code]
    record = RealExplanationEvalRecord(
        case_id=case.case_id,
        description=case.description,
        tags=list(case.tags),
        source=case.source,
        passed=False,
        error=f"{type(exc).__name__}: {exc}",
        attempts=len(attempts),
        failure_codes=failure_codes,
        generation_attempts=attempts,
        latency_seconds=latency_seconds,
    )
    if context is None:
        return record
    played = _played_candidate(context.evidence.candidates)
    return record.model_copy(
        update={
            "played_san": context.evidence.played.san,
            "played_uci": context.evidence.played.uci,
            "player_color": context.evidence.request.player_color,
            "quality": context.evidence.quality.label,
            "score_loss_vs_best_cp": context.evidence.quality.score_loss_vs_best_cp,
            "wdl_expected_score_loss": context.evidence.quality.wdl_expected_score_loss,
            "significance": context.evidence.significance.label,
            "beauty": context.evidence.beauty.label,
            "stockfish_version": context.evidence.engine.engine_version,
            "stockfish_depth": _stockfish_depth(context.evidence.engine.top_lines),
            "maia_candidate_count": _maia_candidate_count(context.evidence.candidates),
            "maia_sources": _maia_sources(context.evidence.candidates),
            "played_findability_source": played.findability_source if played else None,
            "played_findability": played.time_adjusted_findability if played else None,
            "schema_version": EXPLANATION_SCHEMA_VERSION if attempts else None,
            "context_version": context.evidence.context_version,
            "prompt_id": PROMPT_ID if attempts else None,
            "prompt_version": attempts[-1].prompt_version if attempts else None,
            "llm_context": context.llm_context,
        }
    )


def _load_default_manual_reviews(
    manual_review_path: str | Path | None,
) -> dict[str, RealExplanationManualReview]:
    review_path = manual_review_path
    if review_path is None:
        review_path = os.getenv("G6EXPLANATION_REAL_LLM_EVAL_MANUAL_REVIEWS")
    if review_path is None and DEFAULT_REAL_EXPLANATION_MANUAL_REVIEWS_PATH.exists():
        review_path = DEFAULT_REAL_EXPLANATION_MANUAL_REVIEWS_PATH
    if review_path is None:
        return {}
    return load_real_explanation_manual_reviews(review_path)


def _apply_manual_review(
    record: RealExplanationEvalRecord,
    reviews: Mapping[str, RealExplanationManualReview],
) -> RealExplanationEvalRecord:
    review = reviews.get(record.case_id)
    if review is None or not _manual_review_matches(record, review):
        return record
    return record.model_copy(
        update={
            "manual_review_category": review.category,
            "manual_review_notes": review.notes,
        }
    )


def _manual_review_matches(
    record: RealExplanationEvalRecord,
    review: RealExplanationManualReview,
) -> bool:
    if review.model is not None and record.model != review.model:
        return False
    if review.attempts is not None and record.attempts != review.attempts:
        return False
    return review.failure_codes is None or sorted(record.failure_codes) == sorted(
        review.failure_codes
    )


def _needs_manual_review(record: RealExplanationEvalRecord) -> bool:
    return (
        not record.passed
        or record.used_fallback is True
        or record.attempts > 1
        or bool(record.failure_codes)
        or bool(record.error)
    )


def _failed_attempt_explanations(record: RealExplanationEvalRecord) -> list[str]:
    return [
        attempt.explanation
        for attempt in record.generation_attempts
        if not attempt.verification_passed and attempt.explanation
    ]


def real_explanation_openrouter_generation_concurrency(case_count: int) -> int:
    if case_count <= 0:
        return 0
    configured = _int_env(
        "G6EXPLANATION_REAL_LLM_EVAL_OPENROUTER_CONCURRENCY",
        DEFAULT_REAL_LLM_EVAL_OPENROUTER_CONCURRENCY,
    )
    if configured < 1:
        raise RealEvaluationSetupError(
            "G6EXPLANATION_REAL_LLM_EVAL_OPENROUTER_CONCURRENCY must be at least 1."
        )
    return min(case_count, configured)


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


def _gate_if(
    issues: list[RealExplanationPromotionGateIssue],
    condition: bool,
    code: str,
    message: str,
) -> None:
    if condition:
        issues.append(RealExplanationPromotionGateIssue(code=code, message=message))


def _rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return _rounded(count / total)


def _rounded(value: float) -> float:
    return round(value, 4)


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    index = round((len(values) - 1) * fraction)
    return values[index]


def _count_present(values: Iterable[str | None]) -> dict[str, int]:
    return dict(sorted(Counter(value for value in values if value).items()))


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"`{key}`: {value}" for key, value in counts.items())


def _join_or_none(values: Sequence[str]) -> str:
    if not values:
        return "none"
    return ", ".join(f"`{value}`" for value in values)


def _display_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}".rstrip("0").rstrip(".")


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
