from __future__ import annotations

import pytest
from pydantic import ValidationError

from g6explanation.explanation_generation.contracts import ExplanationOutput


def test_explanation_output_accepts_single_explanation_field() -> None:
    output = ExplanationOutput(explanation="e4 was the best move.")

    assert output.explanation == "e4 was the best move."


def test_explanation_output_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ExplanationOutput.model_validate(
            {
                "explanation": "e4 was the best move.",
                "line": "e4 e5",
            }
        )


def test_explanation_output_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        ExplanationOutput(explanation="   ")
