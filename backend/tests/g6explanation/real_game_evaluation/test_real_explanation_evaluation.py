from __future__ import annotations

import importlib.util
import json
import os
import shutil
from pathlib import Path

import chess
import pytest

from g6explanation.context_engine.stockfish_analysis import MIN_STOCKFISH_DEPTH
from g6explanation.real_game_evaluation import (
    REAL_EXPLANATION_EVAL_CASES,
    RealExplanationEvalRecord,
    run_real_explanation_evaluation,
    san_at_ply,
    select_real_explanation_eval_cases,
)

STOCKFISH = (
    os.getenv("G6_REAL_LLM_EVAL_STOCKFISH_BINARY")
    or os.getenv("G6EXPLANATION_STOCKFISH_BINARY")
    or shutil.which("stockfish")
)
HAS_MAIA2 = importlib.util.find_spec("maia2") is not None


def test_real_explanation_eval_catalog_targets_expected_moves() -> None:
    for case in REAL_EXPLANATION_EVAL_CASES:
        if case.pgn is not None:
            assert case.ply is not None
            assert san_at_ply(case.pgn, case.ply) == case.expected_san
        else:
            assert case.fen_before is not None
            assert case.played_move is not None
            board = chess.Board(case.fen_before)
            assert board.san(chess.Move.from_uci(case.played_move)) == case.expected_san


def test_published_eval_catalog_contains_only_redistributable_sources() -> None:
    assert all(case.source.allows_global_training for case in REAL_EXPLANATION_EVAL_CASES)


def test_select_real_explanation_eval_cases_preserves_requested_order() -> None:
    selected = select_real_explanation_eval_cases(["fools-mate-g4-blunder", "opera-final-mate"])

    assert [case.case_id for case in selected] == [
        "fools-mate-g4-blunder",
        "opera-final-mate",
    ]


@pytest.mark.skipif(
    os.getenv("G6EXPLANATION_RUN_REAL_LLM_EVAL") != "1",
    reason="Real Stockfish+Maia+OpenRouter explanation evaluation is opt-in.",
)
@pytest.mark.skipif(
    STOCKFISH is None,
    reason="Real explanation evaluation requires Stockfish.",
)
@pytest.mark.skipif(
    not HAS_MAIA2,
    reason="Real explanation evaluation requires maia2 and local Maia models.",
)
def test_real_game_explanations_pass_with_stockfish_maia_and_openrouter(
    tmp_path: Path,
) -> None:
    case_ids = _selected_case_ids()
    output_env = os.getenv("G6EXPLANATION_REAL_LLM_EVAL_OUTPUT")
    output_path = Path(output_env) if output_env else tmp_path / "real_explanation_eval.jsonl"
    report_env = os.getenv("G6EXPLANATION_REAL_LLM_EVAL_REPORT")
    report_path = Path(report_env) if report_env else tmp_path / "real_explanation_eval_report.md"

    summary = run_real_explanation_evaluation(
        select_real_explanation_eval_cases(case_ids),
        output_path=output_path,
        report_path=report_path,
        use_baseline_fallback=False,
    )
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True), flush=True)

    assert output_path.exists()
    assert report_path.exists()
    assert summary.total_cases == len(case_ids or REAL_EXPLANATION_EVAL_CASES)
    assert summary.failed_cases == 0
    assert summary.fallback_cases == 0
    assert all(record.finish_reason == "model" for record in summary.records)
    assert all(record.provider_name == "openrouter" for record in summary.records)
    assert all(record.stockfish_depth is not None for record in summary.records)
    assert all(
        record.stockfish_depth is not None and record.stockfish_depth >= MIN_STOCKFISH_DEPTH
        for record in summary.records
    )
    assert any(record.maia_candidate_count > 0 for record in summary.records)
    if case_ids is None:
        assert _all_tags(summary.records) >= {
            "opera",
            "game-of-the-century",
            "quiet-positional",
            "forced",
            "ordinary-blunder",
            "high-wdl-non-best",
            "castling",
            "en-passant",
            "promotion",
            "recapture",
            "missed-win",
            "low-time",
            "black-perspective",
            "beginner",
            "intermediate",
            "advanced",
        }
        high_wdl_record = _record(summary.records, "high-wdl-qxa7-good")
        assert high_wdl_record.quality == "good"
        assert high_wdl_record.score_loss_vs_best_cp is not None
        assert high_wdl_record.score_loss_vs_best_cp >= 150
        assert high_wdl_record.wdl_expected_score_loss == 0
        missed_win_record = _record(summary.records, "black-missed-mate-nf6")
        assert missed_win_record.quality == "missed_win"


def _selected_case_ids() -> list[str] | None:
    raw = os.getenv("G6EXPLANATION_REAL_LLM_EVAL_CASES")
    if raw is None:
        return None
    return [case_id.strip() for case_id in raw.split(",") if case_id.strip()]


def _all_tags(records: list[RealExplanationEvalRecord]) -> set[str]:
    return {tag for record in records for tag in record.tags}


def _record(
    records: list[RealExplanationEvalRecord],
    case_id: str,
) -> RealExplanationEvalRecord:
    return next(record for record in records if record.case_id == case_id)
