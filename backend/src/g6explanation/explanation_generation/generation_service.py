"""Orchestration for verified explanation generation."""

from __future__ import annotations

from pydantic import ValidationError

from g6explanation.context_engine import (
    MoveContextBuilder,
    MoveContextRequest,
    StockfishAnalysisProvider,
)
from g6explanation.context_engine.contracts import ContextResult
from g6explanation.explanation_generation.baseline_renderer import render_baseline_explanation
from g6explanation.explanation_generation.coach_model import CoachModelProvider
from g6explanation.explanation_generation.contracts import (
    EXPLANATION_SCHEMA_VERSION,
    PROMPT_ID,
    PROMPT_VERSION,
    CoachModelResponse,
    ExplanationOutput,
    ExplanationResult,
    ExplanationVerificationIssue,
    GenerationAttempt,
)
from g6explanation.explanation_generation.exceptions import (
    CoachModelError,
    ExplanationVerificationError,
)
from g6explanation.explanation_generation.explanation_verification import (
    ExplanationVerifier,
)
from g6explanation.explanation_generation.openrouter_chat import OpenRouterCoachModelProvider
from g6explanation.explanation_generation.prompt_builder import build_coach_prompt


class ExplanationService:
    """Generate and verify one explanation from verified context evidence."""

    def __init__(
        self,
        context_builder: MoveContextBuilder,
        coach_provider: CoachModelProvider,
        explanation_verifier: ExplanationVerifier | None = None,
        max_model_attempts: int = 2,
        use_baseline_fallback: bool = True,
    ) -> None:
        if max_model_attempts < 1:
            raise ValueError("max_model_attempts must be at least 1.")
        self._context_builder = context_builder
        self._coach_provider = coach_provider
        self._explanation_verifier = explanation_verifier or ExplanationVerifier()
        self._max_model_attempts = max_model_attempts
        self._use_baseline_fallback = use_baseline_fallback

    def explain(self, request: MoveContextRequest) -> ExplanationResult:
        return self.explain_context(self._context_builder.build(request))

    def explain_context(self, context_result: ContextResult) -> ExplanationResult:
        baseline = render_baseline_explanation(context_result)
        baseline_verification = self._explanation_verifier.verify(context_result, baseline)
        if not baseline_verification.passed:
            raise ExplanationVerificationError(
                "Deterministic fallback failed explanation verification: "
                f"{_failure_codes(baseline_verification.failures)}"
            )

        attempts: list[GenerationAttempt] = []
        retry_issues: list[ExplanationVerificationIssue] | None = None
        for attempt_index in range(1, self._max_model_attempts + 1):
            prompt = build_coach_prompt(context_result, retry_issues=retry_issues)
            try:
                response = self._coach_provider.generate(prompt)
                output = ExplanationOutput.model_validate_json(response.content)
            except (CoachModelError, ValidationError, ValueError) as exc:
                attempts.append(
                    _failed_attempt(
                        attempt_index=attempt_index,
                        provider=self._coach_provider,
                        error=str(exc),
                    )
                )
                retry_issues = None
                continue

            verification = self._explanation_verifier.verify(context_result, output)
            attempts.append(
                _attempt_from_response(
                    attempt_index=attempt_index,
                    response=response,
                    verification_passed=verification.passed,
                    failure_codes=_failure_codes(verification.failures),
                )
            )
            if verification.passed:
                return ExplanationResult(
                    explanation=output.explanation,
                    finish_reason="model",
                    schema_version=EXPLANATION_SCHEMA_VERSION,
                    context_version=context_result.evidence.context_version,
                    prompt_id=PROMPT_ID,
                    prompt_version=PROMPT_VERSION,
                    provider_name=response.provider_name,
                    model=response.model,
                    verifier_version=verification.verifier_version,
                    used_fallback=False,
                    attempts=attempts,
                    verification=verification,
                )
            retry_issues = verification.failures

        if self._use_baseline_fallback:
            return ExplanationResult(
                explanation=baseline.explanation,
                finish_reason="fallback",
                schema_version=EXPLANATION_SCHEMA_VERSION,
                context_version=context_result.evidence.context_version,
                prompt_id=PROMPT_ID,
                prompt_version=PROMPT_VERSION,
                provider_name="deterministic_baseline",
                model="baseline_renderer.v1",
                verifier_version=baseline_verification.verifier_version,
                used_fallback=True,
                attempts=attempts,
                verification=baseline_verification,
            )

        raise ExplanationVerificationError(
            "No model explanation passed deterministic verification: "
            f"{_attempt_failure_summary(attempts)}"
        )


def explain_move(
    request: MoveContextRequest,
    context_builder: MoveContextBuilder | None = None,
    coach_provider: CoachModelProvider | None = None,
) -> str:
    """Public one-move explanation API."""

    service = ExplanationService(
        context_builder=context_builder or MoveContextBuilder(StockfishAnalysisProvider()),
        coach_provider=coach_provider or OpenRouterCoachModelProvider.from_env(),
    )
    return service.explain(request).explanation


def _attempt_from_response(
    attempt_index: int,
    response: CoachModelResponse,
    verification_passed: bool,
    failure_codes: list[str],
) -> GenerationAttempt:
    return GenerationAttempt(
        attempt_index=attempt_index,
        provider_name=response.provider_name,
        model=response.model,
        prompt_id=PROMPT_ID,
        prompt_version=PROMPT_VERSION,
        response_id=response.response_id,
        finish_reason=response.finish_reason,
        verification_passed=verification_passed,
        failure_codes=failure_codes,
    )


def _failed_attempt(
    attempt_index: int,
    provider: CoachModelProvider,
    error: str,
) -> GenerationAttempt:
    return GenerationAttempt(
        attempt_index=attempt_index,
        provider_name=provider.provider_name,
        model=provider.model,
        prompt_id=PROMPT_ID,
        prompt_version=PROMPT_VERSION,
        verification_passed=False,
        failure_codes=["schema_or_provider_error"],
        error=error,
    )


def _failure_codes(failures: list[ExplanationVerificationIssue]) -> list[str]:
    return [failure.code for failure in failures]


def _attempt_failure_summary(attempts: list[GenerationAttempt]) -> str:
    return "; ".join(
        f"attempt {attempt.attempt_index}: {attempt.failure_codes or [attempt.error]}"
        for attempt in attempts
    )
