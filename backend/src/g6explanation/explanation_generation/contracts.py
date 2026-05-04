"""Schema contracts for verified explanation generation."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import Field, field_validator, model_validator

from g6explanation.context_engine.contracts import ContextContract

EXPLANATION_SCHEMA_VERSION = "explanation_output.v3"
PROMPT_ID = "single_move_coach"
PROMPT_VERSION = "single_move_coach.v10"

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
    "internal_language",
    "best_move_inconsistent",
    "recommendation_policy_violation",
    "hard_move_uncaveated",
    "side_attribution_unsupported",
    "line_card_unsupported",
    "line_card_move_mismatch",
    "line_card_unreferenced",
]
GenerationFinishReason: TypeAlias = Literal["model", "fallback", "controlled_failure"]
LineEvidenceRole: TypeAlias = Literal["played_line", "better_line"]


class ExplanationSegment(ContextContract):
    """Visible explanation text with optional hover-line attachment."""

    text: str = Field(min_length=1, max_length=320)
    line_card_id: str | None
    line_card_anchor: str | None = Field(default=None, max_length=60)

    @field_validator("text", "line_card_anchor")
    @classmethod
    def _strip_text_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = " ".join(value.split())
        if not stripped:
            raise ValueError("Segment text cannot be empty.")
        return stripped

    @model_validator(mode="after")
    def _validate_line_card_anchor(self) -> ExplanationSegment:
        if self.line_card_id is None:
            if self.line_card_anchor is not None:
                raise ValueError("line_card_anchor requires line_card_id.")
            return self

        if self.line_card_anchor is None:
            raise ValueError("line_card_anchor is required when line_card_id is present.")
        if self.line_card_anchor not in self.text:
            raise ValueError("line_card_anchor must be an exact substring of text.")
        anchor_words = self.line_card_anchor.split()
        if len(anchor_words) > 8:
            raise ValueError("line_card_anchor must be no more than 8 words.")
        text_words = self.text.split()
        if (
            _normalized_text(self.line_card_anchor) == _normalized_text(self.text)
            and len(text_words) > 8
        ):
            raise ValueError("line_card_anchor must not be a whole long segment.")
        return self


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


class ExplanationLineCard(ContextContract):
    """Hover data for one verified tactical or strategic line."""

    id: str = Field(min_length=1, max_length=80)
    moves: list[str] = Field(min_length=2, max_length=8)
    title: str = Field(min_length=1, max_length=100)
    why: str = Field(min_length=1, max_length=320)

    @field_validator("id", "title", "why")
    @classmethod
    def _strip_text_field(cls, value: str) -> str:
        stripped = " ".join(value.split())
        if not stripped:
            raise ValueError("Line-card text fields cannot be empty.")
        return stripped

    @field_validator("moves")
    @classmethod
    def _strip_moves(cls, value: list[str]) -> list[str]:
        stripped = [" ".join(move.split()) for move in value]
        if any(not move for move in stripped):
            raise ValueError("Line-card moves cannot be empty.")
        return stripped


class ExplanationLineEvidence(ContextContract):
    """Verified line evidence supplied to the model for optional hover cards."""

    id: str
    role: LineEvidenceRole
    moves: list[str]
    title: str
    why: str


class ExplanationOutput(ContextContract):
    """Strict raw model response shape."""

    segments: list[ExplanationSegment] = Field(min_length=1, max_length=6)
    line_cards: list[ExplanationLineCard] = Field(max_length=3)

    @property
    def explanation(self) -> str:
        return " ".join(segment.text.strip() for segment in self.segments).strip()

    @model_validator(mode="after")
    def _validate_segment_line_card_refs(self) -> ExplanationOutput:
        card_ids = [card.id for card in self.line_cards]
        if len(card_ids) != len(set(card_ids)):
            raise ValueError("Line-card ids must be unique.")
        card_id_set = set(card_ids)
        referenced_ids = {
            segment.line_card_id for segment in self.segments if segment.line_card_id is not None
        }
        missing_ids = referenced_ids - card_id_set
        if missing_ids:
            raise ValueError(f"Segments reference missing line-card ids: {sorted(missing_ids)}.")
        unreferenced_ids = card_id_set - referenced_ids
        if unreferenced_ids:
            raise ValueError(
                f"Line cards are not referenced by any segment: {sorted(unreferenced_ids)}."
            )
        if not self.explanation:
            raise ValueError("Explanation cannot be empty.")
        return self


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
    explanation: str | None = None
    error: str | None = None


class ExplanationResult(ContextContract):
    explanation: str
    segments: list[ExplanationSegment] = Field(default_factory=list[ExplanationSegment])
    line_cards: list[ExplanationLineCard] = Field(default_factory=list[ExplanationLineCard])
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
