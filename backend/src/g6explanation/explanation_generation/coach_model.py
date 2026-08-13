"""Coach model provider protocol."""

from __future__ import annotations

from typing import Protocol

from g6explanation.explanation_generation.contracts import CoachModelResponse, CoachPrompt


class CoachModelProvider(Protocol):
    """Provider boundary for raw explanation JSON generation."""

    @property
    def provider_name(self) -> str:
        """Stable provider label for metadata."""
        ...

    @property
    def model(self) -> str:
        """Model identifier used by the provider."""
        ...

    def generate(self, prompt: CoachPrompt) -> CoachModelResponse:
        """Return raw schema-shaped model output for a verified prompt."""
        ...
