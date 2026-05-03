"""Verified explanation generation API."""

from g6explanation.explanation_generation.baseline_renderer import render_baseline_explanation
from g6explanation.explanation_generation.coach_model import CoachModelProvider
from g6explanation.explanation_generation.contracts import (
    CoachModelResponse,
    CoachPrompt,
    ExplanationOutput,
    ExplanationResult,
    ExplanationVerificationIssue,
    ExplanationVerificationResult,
    GenerationAttempt,
)
from g6explanation.explanation_generation.exceptions import (
    CoachModelError,
    ExplanationGenerationError,
    ExplanationVerificationError,
)
from g6explanation.explanation_generation.explanation_verification import ExplanationVerifier
from g6explanation.explanation_generation.generation_service import ExplanationService, explain_move
from g6explanation.explanation_generation.openrouter_chat import OpenRouterCoachModelProvider

__all__ = [
    "CoachModelError",
    "CoachModelProvider",
    "CoachModelResponse",
    "CoachPrompt",
    "ExplanationGenerationError",
    "ExplanationOutput",
    "ExplanationResult",
    "ExplanationService",
    "ExplanationVerificationError",
    "ExplanationVerificationIssue",
    "ExplanationVerificationResult",
    "ExplanationVerifier",
    "GenerationAttempt",
    "OpenRouterCoachModelProvider",
    "explain_move",
    "render_baseline_explanation",
]
