from __future__ import annotations

from pathlib import Path
from typing import cast

from g6explanation.real_game_evaluation import (
    ManualReviewCategory,
    RealExplanationEvalRecord,
    build_real_explanation_eval_report,
    build_real_explanation_eval_report_from_jsonl,
    render_real_explanation_eval_report_markdown,
    summarize_real_explanation_eval_records,
    write_real_explanation_eval_report,
)


def test_build_real_explanation_eval_report_summarizes_records() -> None:
    summary = summarize_real_explanation_eval_records(
        [
            _record(
                case_id="passed",
                passed=True,
                attempts=1,
                latency_seconds=2.0,
                failure_codes=[],
            ),
            _record(
                case_id="retried",
                passed=True,
                attempts=2,
                latency_seconds=4.0,
                failure_codes=["unsupported_concept_claim"],
            ),
            _record(
                case_id="failed",
                passed=False,
                attempts=0,
                latency_seconds=6.0,
                failure_codes=["provider_error"],
                used_fallback=True,
                manual_review_category="provider_or_runtime_issue",
            ),
        ]
    )

    report = build_real_explanation_eval_report(summary)

    assert report.total_cases == 3
    assert report.passed_cases == 2
    assert report.failed_cases == 1
    assert report.fallback_cases == 1
    assert report.retry_cases == 1
    assert report.pass_rate == 0.6667
    assert report.fallback_rate == 0.3333
    assert report.retry_rate == 0.3333
    assert report.failure_code_counts == {
        "provider_error": 1,
        "unsupported_concept_claim": 1,
    }
    assert report.model_counts == {"openai/gpt-5.5-20260423": 3}
    assert report.stockfish_min_depth == 16
    assert report.maia_sources == ["maia2_rapid"]
    assert report.latency_avg_seconds == 4.0
    assert report.latency_p50_seconds == 4.0
    assert report.latency_max_seconds == 6.0
    assert report.review_required_case_ids == ["retried", "failed"]
    assert report.manual_review_counts == {
        "not_reviewed": 2,
        "provider_or_runtime_issue": 1,
    }


def test_real_explanation_eval_report_can_be_written_and_reloaded(tmp_path: Path) -> None:
    records = [
        _record(
            case_id="case-a",
            passed=True,
            attempts=1,
            latency_seconds=3.25,
            failure_codes=[],
        )
    ]
    summary = summarize_real_explanation_eval_records(records)
    jsonl_path = tmp_path / "eval.jsonl"
    report_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"

    jsonl_path.write_text(
        "\n".join(record.model_dump_json() for record in records) + "\n",
        encoding="utf-8",
    )

    markdown_report = write_real_explanation_eval_report(summary, report_path)
    json_report = write_real_explanation_eval_report(summary, json_path)
    loaded_report = build_real_explanation_eval_report_from_jsonl(jsonl_path)

    assert markdown_report == loaded_report
    assert json_report == loaded_report
    assert "# Real Explanation Evaluation Report" in report_path.read_text(encoding="utf-8")
    assert '"total_cases": 1' in json_path.read_text(encoding="utf-8")


def test_render_real_explanation_eval_report_markdown_lists_review_required_cases() -> None:
    summary = summarize_real_explanation_eval_records(
        [
            _record(
                case_id="needs-review",
                passed=True,
                attempts=2,
                latency_seconds=1.0,
                failure_codes=["unsupported_tactic_claim"],
            )
        ]
    )

    report = build_real_explanation_eval_report(summary)
    markdown = render_real_explanation_eval_report_markdown(report)

    assert "Review required cases: `needs-review`" in markdown
    assert "`unsupported_tactic_claim`: 1" in markdown


def _record(
    *,
    case_id: str,
    passed: bool,
    attempts: int,
    latency_seconds: float,
    failure_codes: list[str],
    used_fallback: bool = False,
    manual_review_category: str = "not_reviewed",
) -> RealExplanationEvalRecord:
    return RealExplanationEvalRecord(
        case_id=case_id,
        description=f"{case_id} description",
        tags=["synthetic"],
        passed=passed,
        played_san="e4",
        played_uci="e2e4",
        player_color="white",
        quality="best",
        significance="low",
        beauty="low",
        stockfish_version="Stockfish 18",
        stockfish_depth=16,
        maia_candidate_count=2,
        maia_sources=["maia2_rapid"],
        provider_name="openrouter",
        model="openai/gpt-5.5-20260423",
        finish_reason="model" if passed else None,
        used_fallback=used_fallback,
        attempts=attempts,
        failure_codes=failure_codes,
        latency_seconds=latency_seconds,
        explanation="e4 was the best move." if passed else None,
        manual_review_category=cast(ManualReviewCategory, manual_review_category),
    )
