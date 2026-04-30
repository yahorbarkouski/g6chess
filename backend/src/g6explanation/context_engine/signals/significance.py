"""Move-significance policy."""

from __future__ import annotations

from g6explanation.context_engine.contracts import (
    EngineAnalysis,
    EngineLine,
    MoveSignificance,
    PlayedMoveFacts,
    SignificanceLabel,
)
from g6explanation.context_engine.signals.score_comparison import (
    absolute_cp_gap,
    absolute_wdl_expected_gap,
    has_mate_transition,
)


def calculate_significance(analysis: EngineAnalysis, played: PlayedMoveFacts) -> MoveSignificance:
    """Measure how much this move deserves emphasis relative to alternatives."""

    if has_mate_transition(analysis):
        return MoveSignificance(label="critical", score=1.0)

    reference = _significance_reference_line(analysis, played)
    if reference is None:
        return MoveSignificance(label="low", score=0.0)

    played_line = analysis.played_line
    cp_gap = absolute_cp_gap(played_line.score, reference.score)
    wdl_gap = absolute_wdl_expected_gap(played_line.wdl, reference.wdl)

    cp_score = 0.0 if cp_gap is None else _clamp(cp_gap / 300)
    wdl_score = 0.0 if wdl_gap is None else _clamp(wdl_gap / 180)
    score = round(max(cp_score, wdl_score), 2)
    return MoveSignificance(label=_significance_label(score), score=score)


def _significance_reference_line(
    analysis: EngineAnalysis, played: PlayedMoveFacts
) -> EngineLine | None:
    if played.uci != analysis.top_lines[0].move_uci:
        return analysis.top_lines[0]
    return next(
        (line for line in analysis.top_lines[1:] if line.move_uci != played.uci),
        None,
    )


def _significance_label(score: float) -> SignificanceLabel:
    if score >= 0.65:
        return "critical"
    if score >= 0.35:
        return "high"
    if score >= 0.15:
        return "moderate"
    return "low"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
