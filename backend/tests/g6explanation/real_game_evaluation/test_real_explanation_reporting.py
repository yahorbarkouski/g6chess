from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

import g6explanation.real_game_evaluation.explanation_evaluation as evaluation_module
from g6explanation.explanation_generation.contracts import GenerationAttempt
from g6explanation.real_game_evaluation import (
    ManualReviewCategory,
    RealExplanationEvalRecord,
    RealExplanationManualReview,
    apply_real_explanation_manual_reviews,
    build_real_explanation_eval_report,
    build_real_explanation_eval_report_from_jsonl,
    evaluate_real_explanation_promotion_gate,
    load_real_explanation_manual_reviews,
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
    assert report.review_required_case_ids == ["retried"]
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


def test_markdown_report_includes_failed_attempt_explanations() -> None:
    summary = summarize_real_explanation_eval_records(
        [
            _record(
                case_id="needs-review",
                passed=True,
                attempts=2,
                latency_seconds=1.0,
                failure_codes=["unsupported_tactic_claim"],
                generation_attempts=[
                    GenerationAttempt(
                        attempt_index=1,
                        provider_name="openrouter",
                        model="openai/gpt-5.5-20260423",
                        prompt_id="single_move_coach",
                        prompt_version="single_move_coach.v4",
                        verification_passed=False,
                        failure_codes=["unsupported_tactic_claim"],
                        explanation="Nf6 missed a back-rank tactic.",
                    ),
                    GenerationAttempt(
                        attempt_index=2,
                        provider_name="openrouter",
                        model="openai/gpt-5.5-20260423",
                        prompt_id="single_move_coach",
                        prompt_version="single_move_coach.v4",
                        verification_passed=True,
                        explanation="Nf6 missed Qh4#.",
                    ),
                ],
            )
        ]
    )

    report = build_real_explanation_eval_report(summary)
    markdown = render_real_explanation_eval_report_markdown(report)

    assert report.case_reports[0].failed_attempt_explanations == ["Nf6 missed a back-rank tactic."]
    assert "## Failed Attempt Explanations" in markdown
    assert "- Attempt 1: Nf6 missed a back-rank tactic." in markdown


def test_reviewed_retry_is_not_reported_as_needing_manual_review() -> None:
    summary = summarize_real_explanation_eval_records(
        [
            _record(
                case_id="reviewed-retry",
                passed=True,
                attempts=2,
                latency_seconds=1.0,
                failure_codes=["recommendation_policy_violation"],
                manual_review_category="model_wording_issue",
            )
        ]
    )

    report = build_real_explanation_eval_report(summary)

    assert report.review_required_case_ids == []
    assert report.manual_review_counts == {"model_wording_issue": 1}


def test_manual_review_file_can_be_loaded(tmp_path: Path) -> None:
    review_path = tmp_path / "manual_reviews.json"
    review_path.write_text(
        """
        {
          "reviews": [
            {
              "case_id": "capablanca-g4",
              "category": "model_wording_issue",
              "notes": "Verifier correctly blocked the first attempt; retry passed.",
              "model": "openai/gpt-5.5-20260423",
              "attempts": 2,
              "failure_codes": ["recommendation_policy_violation"]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    reviews = load_real_explanation_manual_reviews(review_path)

    assert reviews == {
        "capablanca-g4": RealExplanationManualReview(
            case_id="capablanca-g4",
            category="model_wording_issue",
            notes="Verifier correctly blocked the first attempt; retry passed.",
            model="openai/gpt-5.5-20260423",
            attempts=2,
            failure_codes=["recommendation_policy_violation"],
        )
    }


def test_manual_review_annotations_apply_only_to_matching_records() -> None:
    review = RealExplanationManualReview(
        case_id="capablanca-g4",
        category="model_wording_issue",
        notes="Verifier correctly blocked the first attempt; retry passed.",
        model="openai/gpt-5.5-20260423",
        attempts=2,
        failure_codes=["recommendation_policy_violation"],
    )
    matching = _record(
        case_id="capablanca-g4",
        passed=True,
        attempts=2,
        latency_seconds=1.0,
        failure_codes=["recommendation_policy_violation"],
    )
    changed_failure = _record(
        case_id="capablanca-g4",
        passed=True,
        attempts=2,
        latency_seconds=1.0,
        failure_codes=["unsupported_concept_claim"],
    )

    reviewed_records = apply_real_explanation_manual_reviews(
        [matching, changed_failure],
        {"capablanca-g4": review},
    )

    assert reviewed_records[0].manual_review_category == "model_wording_issue"
    assert reviewed_records[0].manual_review_notes == review.notes
    assert reviewed_records[1].manual_review_category == "not_reviewed"


def test_openrouter_generation_concurrency_defaults_to_bounded_parallelism(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("G6EXPLANATION_REAL_LLM_EVAL_OPENROUTER_CONCURRENCY", raising=False)

    assert evaluation_module.real_explanation_openrouter_generation_concurrency(0) == 0
    assert evaluation_module.real_explanation_openrouter_generation_concurrency(12) == 12
    assert evaluation_module.real_explanation_openrouter_generation_concurrency(40) == 30


def test_openrouter_generation_concurrency_respects_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("G6EXPLANATION_REAL_LLM_EVAL_OPENROUTER_CONCURRENCY", "7")

    assert evaluation_module.real_explanation_openrouter_generation_concurrency(20) == 7


def test_jsonl_report_builder_applies_manual_reviews(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "eval.jsonl"
    review_path = tmp_path / "manual_reviews.json"
    record = _record(
        case_id="capablanca-g4",
        passed=True,
        attempts=2,
        latency_seconds=1.0,
        failure_codes=["recommendation_policy_violation"],
    )
    jsonl_path.write_text(record.model_dump_json() + "\n", encoding="utf-8")
    review_path.write_text(
        """
        {
          "reviews": [
            {
              "case_id": "capablanca-g4",
              "category": "model_wording_issue",
              "notes": "Verifier correctly blocked the first attempt; retry passed.",
              "model": "openai/gpt-5.5-20260423",
              "attempts": 2,
              "failure_codes": ["recommendation_policy_violation"]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    report = build_real_explanation_eval_report_from_jsonl(
        jsonl_path,
        manual_review_path=review_path,
    )

    assert report.review_required_case_ids == []
    assert report.manual_review_counts == {"model_wording_issue": 1}


def test_promotion_gate_passes_when_current_report_matches_or_improves() -> None:
    baseline = build_real_explanation_eval_report(
        summarize_real_explanation_eval_records(
            [
                _record(
                    case_id="case-a",
                    passed=True,
                    attempts=2,
                    latency_seconds=1.0,
                    failure_codes=["unsupported_concept_claim"],
                    manual_review_category="model_wording_issue",
                )
            ]
        )
    )
    current = build_real_explanation_eval_report(
        summarize_real_explanation_eval_records(
            [
                _record(
                    case_id="case-a",
                    passed=True,
                    attempts=1,
                    latency_seconds=1.0,
                    failure_codes=[],
                )
            ]
        )
    )

    result = evaluate_real_explanation_promotion_gate(baseline, current)

    assert result.passed
    assert result.issues == []


def test_promotion_gate_blocks_regressions_and_unreviewed_records() -> None:
    baseline = build_real_explanation_eval_report(
        summarize_real_explanation_eval_records(
            [
                _record(
                    case_id="case-a",
                    passed=True,
                    attempts=1,
                    latency_seconds=1.0,
                    failure_codes=[],
                ),
                _record(
                    case_id="case-b",
                    passed=True,
                    attempts=1,
                    latency_seconds=1.0,
                    failure_codes=[],
                ),
            ]
        )
    )
    current = build_real_explanation_eval_report(
        summarize_real_explanation_eval_records(
            [
                _record(
                    case_id="case-a",
                    passed=True,
                    attempts=2,
                    latency_seconds=1.0,
                    failure_codes=["unsupported_tactic_claim"],
                )
            ]
        )
    )

    result = evaluate_real_explanation_promotion_gate(baseline, current)

    assert not result.passed
    assert {issue.code for issue in result.issues} == {
        "case_count_regressed",
        "retry_cases_regressed",
        "failure_code_regressed",
        "manual_review_required",
    }


def _record(
    *,
    case_id: str,
    passed: bool,
    attempts: int,
    latency_seconds: float,
    failure_codes: list[str],
    used_fallback: bool = False,
    manual_review_category: str = "not_reviewed",
    generation_attempts: list[GenerationAttempt] | None = None,
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
        generation_attempts=generation_attempts or [],
        latency_seconds=latency_seconds,
        explanation="e4 was the best move." if passed else None,
        manual_review_category=cast(ManualReviewCategory, manual_review_category),
    )
