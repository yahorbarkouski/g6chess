"""Orchestration for verified explanation generation."""

from __future__ import annotations

from pydantic import ValidationError

from g6explanation.context_engine import (
    MoveContextBuilder,
    MoveContextRequest,
    PlayerLevel,
    StockfishAnalysisProvider,
)
from g6explanation.context_engine.contracts import ColorName, ContextResult
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
    ExplanationInputError,
    ExplanationVerificationError,
)
from g6explanation.explanation_generation.explanation_verification import (
    ExplanationVerifier,
)
from g6explanation.explanation_generation.openrouter_chat import OpenRouterCoachModelProvider
from g6explanation.explanation_generation.prompt_builder import build_coach_prompt

DEFAULT_MAX_MODEL_ATTEMPTS = 3


class ExplanationService:
    """Generate and verify one explanation from verified context evidence."""

    def __init__(
        self,
        context_builder: MoveContextBuilder,
        coach_provider: CoachModelProvider,
        explanation_verifier: ExplanationVerifier | None = None,
        max_model_attempts: int = DEFAULT_MAX_MODEL_ATTEMPTS,
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
                    explanation=output.explanation,
                )
            )
            if verification.passed:
                return ExplanationResult(
                    explanation=output.explanation,
                    segments=output.segments,
                    line_cards=output.line_cards,
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
                segments=baseline.segments,
                line_cards=baseline.line_cards,
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
            f"{_attempt_failure_summary(attempts)}",
            attempts=attempts,
        )


def explain_move(
    game_context: MoveContextRequest | str,
    played_move: str | None = None,
    player_level: PlayerLevel | int | None = None,
    *,
    player_color: ColorName | None = None,
    pgn_ply: int | None = None,
    time_control: str = "unknown",
    clock_before_seconds: float | None = None,
    increment_seconds: float | None = None,
    think_time_seconds: float | None = None,
    context_builder: MoveContextBuilder | None = None,
    coach_provider: CoachModelProvider | None = None,
) -> str:
    """Public one-move explanation API."""

    request = _public_move_context_request(
        game_context=game_context,
        played_move=played_move,
        player_level=player_level,
        player_color=player_color,
        pgn_ply=pgn_ply,
        time_control=time_control,
        clock_before_seconds=clock_before_seconds,
        increment_seconds=increment_seconds,
        think_time_seconds=think_time_seconds,
    )
    service = ExplanationService(
        context_builder=context_builder or MoveContextBuilder(StockfishAnalysisProvider()),
        coach_provider=coach_provider or OpenRouterCoachModelProvider.from_env(),
    )
    return service.explain(request).explanation


def _public_move_context_request(
    *,
    game_context: MoveContextRequest | str,
    played_move: str | None,
    player_level: PlayerLevel | int | None,
    player_color: ColorName | None,
    pgn_ply: int | None,
    time_control: str,
    clock_before_seconds: float | None,
    increment_seconds: float | None,
    think_time_seconds: float | None,
) -> MoveContextRequest:
    if isinstance(game_context, MoveContextRequest):
        if (
            any(
                value is not None
                for value in (
                    played_move,
                    player_level,
                    player_color,
                    pgn_ply,
                    clock_before_seconds,
                    increment_seconds,
                    think_time_seconds,
                )
            )
            or time_control != "unknown"
        ):
            raise ExplanationInputError(
                "Pass either a MoveContextRequest or public API fields, not both."
            )
        return game_context

    if player_color is None:
        raise ExplanationInputError("player_color is required for public explain_move input.")
    if player_level is None:
        raise ExplanationInputError("player_level is required for public explain_move input.")

    level = _public_player_level(player_level)
    if pgn_ply is not None:
        return MoveContextRequest(
            pgn=game_context,
            ply=pgn_ply,
            player_color=player_color,
            player_level=level,
            time_control=time_control,
            clock_before_seconds=clock_before_seconds,
            increment_seconds=increment_seconds,
            think_time_seconds=think_time_seconds,
        )
    if played_move is None:
        raise ExplanationInputError(
            "played_move is required when game_context is a FEN string. "
            "For PGN input, pass pgn_ply."
        )
    return MoveContextRequest(
        fen_before=game_context,
        played_move=played_move,
        player_color=player_color,
        player_level=level,
        time_control=time_control,
        clock_before_seconds=clock_before_seconds,
        increment_seconds=increment_seconds,
        think_time_seconds=think_time_seconds,
    )


def _public_player_level(player_level: PlayerLevel | int) -> PlayerLevel:
    if isinstance(player_level, PlayerLevel):
        return player_level
    if player_level <= 0:
        raise ExplanationInputError("player_level rating must be positive.")
    return PlayerLevel.rating(player_level)


def _attempt_from_response(
    attempt_index: int,
    response: CoachModelResponse,
    verification_passed: bool,
    failure_codes: list[str],
    explanation: str,
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
        explanation=explanation,
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
        f"attempt {attempt.attempt_index}: {_attempt_failure_detail(attempt)}"
        for attempt in attempts
    )


def _attempt_failure_detail(attempt: GenerationAttempt) -> str:
    details: list[str] = []
    if attempt.failure_codes:
        details.append(f"codes={attempt.failure_codes}")
    if attempt.error:
        details.append(f"error={_compact_error(attempt.error)}")
    return ", ".join(details) if details else "unknown failure"


def _compact_error(error: str, max_length: int = 700) -> str:
    compacted = " ".join(error.split())
    if len(compacted) <= max_length:
        return compacted
    return f"{compacted[: max_length - 3]}..."
