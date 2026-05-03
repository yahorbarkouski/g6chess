"""Schema contracts for verified explanation generation."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import Field, field_validator

from g6explanation.context_engine.contracts import ContextContract

EXPLANATION_SCHEMA_VERSION = "explanation_output.v1"
PROMPT_ID = "single_move_coach"
PROMPT_VERSION = "single_move_coach.v3"

ExplanationVerificationIssueCode: TypeAlias = Literal[
    "empty_explanation",
    "played_move_missing",
    "quality_label_missing",
    "quality_label_conflict",
    "mentioned_move_unsupported",
    "uci_move_mentioned",
    "unsupported_pv",
    "unsupported_mate_claim",
    "unsupported_material_claim",
    "unsupported_tactic_claim",
    "unsupported_concept_claim",
    "raw_engine_dump",
    "best_move_inconsistent",
    "recommendation_policy_violation",
    "hard_move_uncaveated",
    "side_attribution_unsupported",
]
GenerationFinishReason: TypeAlias = Literal["model", "fallback", "controlled_failure"]


class ExplanationOutput(ContextContract):
    """Strict raw model response shape."""

    explanation: str = Field(min_length=1)

    @field_validator("explanation")
    @classmethod
    def _strip_and_reject_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Explanation cannot be empty.")
        return stripped


class ExplanationVerificationIssue(ContextContract):
    code: ExplanationVerificationIssueCode
    message: str
    path: str


class ExplanationVerificationResult(ContextContract):
    verifier_version: str
    passed: bool
    failures: list[ExplanationVerificationIssue] = Field(
        default_factory=list[ExplanationVerificationIssue]
    )
    warnings: list[ExplanationVerificationIssue] = Field(
        default_factory=list[ExplanationVerificationIssue]
    )


class CoachPrompt(ContextContract):
    prompt_id: str
    prompt_version: str
    context_version: str
    messages: list[dict[str, str]]
    response_format: dict[str, Any]


class CoachModelResponse(ContextContract):
    provider_name: str
    model: str
    content: str
    response_id: str | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None


class GenerationAttempt(ContextContract):
    attempt_index: int
    provider_name: str
    model: str
    prompt_id: str
    prompt_version: str
    response_id: str | None = None
    finish_reason: str | None = None
    verification_passed: bool = False
    failure_codes: list[str] = Field(default_factory=list[str])
    error: str | None = None


class ExplanationResult(ContextContract):
    explanation: str
    finish_reason: GenerationFinishReason
    schema_version: str
    context_version: str
    prompt_id: str
    prompt_version: str
    provider_name: str
    model: str
    verifier_version: str
    used_fallback: bool
    attempts: list[GenerationAttempt] = Field(default_factory=list[GenerationAttempt])
    verification: ExplanationVerificationResult
