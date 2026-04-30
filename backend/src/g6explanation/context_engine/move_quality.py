"""Compatibility exports for move-quality and significance policy."""

from g6explanation.context_engine.signals.quality import (
    BAD_QUALITY_LABELS,
    QUALITY_ORDER,
    classify_quality,
)
from g6explanation.context_engine.signals.score_comparison import (
    line_score_loss,
    score_as_cp,
    score_loss_cp,
)
from g6explanation.context_engine.signals.significance import calculate_significance

__all__ = [
    "BAD_QUALITY_LABELS",
    "QUALITY_ORDER",
    "calculate_significance",
    "classify_quality",
    "line_score_loss",
    "score_as_cp",
    "score_loss_cp",
]
