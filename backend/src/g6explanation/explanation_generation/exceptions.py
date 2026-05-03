"""Exceptions for explanation generation."""

from collections.abc import Sequence

from g6explanation.explanation_generation.contracts import GenerationAttempt


class ExplanationGenerationError(Exception):
    """Base exception for explanation-generation failures."""


class CoachModelError(ExplanationGenerationError):
    """Raised when a coach model provider cannot return usable output."""


class ExplanationInputError(ExplanationGenerationError):
    """Raised when public explanation input is ambiguous or incomplete."""


class ExplanationVerificationError(ExplanationGenerationError):
    """Raised when no generated or fallback explanation passes verification."""

    def __init__(
        self,
        message: str,
        attempts: Sequence[GenerationAttempt] | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = list(attempts or [])
