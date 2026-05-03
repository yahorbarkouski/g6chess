"""No-mock real-game explanation evaluation runner."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import time
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias, cast

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

REAL_EXPLANATION_EVAL_REPORT_VERSION = "real_explanation_eval_report.v1"
DEFAULT_REAL_EXPLANATION_MANUAL_REVIEWS_PATH = Path(
    "docs/development/real-explanation-manual-reviews.json"
)
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
    records = apply_real_explanation_manual_reviews(
        [_evaluate_case(case, context_builder, service) for case in cases],
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
    return "\n".join(lines)


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
