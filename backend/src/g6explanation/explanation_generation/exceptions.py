"""Exceptions for explanation generation."""


class ExplanationGenerationError(Exception):
    """Base exception for explanation-generation failures."""


class CoachModelError(ExplanationGenerationError):
    """Raised when a coach model provider cannot return usable output."""


class ExplanationVerificationError(ExplanationGenerationError):
    """Raised when no generated or fallback explanation passes verification."""
