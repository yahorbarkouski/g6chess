"""Move-quality policy."""

from __future__ import annotations

from g6explanation.context_engine.contracts import (
    EngineAnalysis,
    EngineLine,
    MoveQuality,
    MoveQualityLabel,
    PlayedMoveFacts,
    Score,
)
from g6explanation.context_engine.signals.score_comparison import (
    is_opponent_mate,
    is_player_mate,
    opponent_mate_is_worse,
    score_as_cp,
    score_loss_cp,
    wdl_delta,
    wdl_expected_score_loss,
)

BAD_QUALITY_LABELS: frozenset[MoveQualityLabel] = frozenset(
    {"inaccuracy", "mistake", "blunder", "missed_win"}
)
HIGH_WIN_PROBABILITY_FLOOR = 800
QUALITY_ORDER: dict[MoveQualityLabel, int] = {
    "best": 0,
    "forced": 1,
    "excellent": 2,
    "good": 3,
    "neutral": 4,
    "inaccuracy": 5,
    "mistake": 6,
    "blunder": 7,
    "missed_win": 7,
}


def classify_quality(
    analysis: EngineAnalysis, played: PlayedMoveFacts, legal_move_count: int | None = None
) -> MoveQuality:
    best = analysis.top_lines[0]
    played_line = analysis.played_line
    cp_loss = score_loss_cp(best.score, played_line.score)
    wdl_loss = wdl_expected_score_loss(best.wdl, played_line.wdl)

    if played.is_checkmate:
        label: MoveQualityLabel = "best"
    elif legal_move_count == 1:
        label = "forced"
    elif played.uci == best.move_uci:
        label = "best"
    elif (
        best.score.kind == "mate"
        and best.score.mate_for == "player"
        and not is_player_mate(played_line.score)
    ):
        label = "missed_win"
    elif is_opponent_mate(played_line.score):
        if is_opponent_mate(best.score) and not opponent_mate_is_worse(
            best.score, played_line.score
        ):
            label = "neutral"
        else:
            label = "blunder"
    else:
        cp_label = _label_from_cp_loss(cp_loss)
        wdl_label = _label_from_wdl_loss(wdl_loss)
        label = _merge_non_mating_loss_labels(cp_label, wdl_label)
        label = _apply_high_win_probability_floor(label, played_line)

    return MoveQuality(
        label=label,
        score_delta_cp_player_pov=None if cp_loss is None else -cp_loss,
        score_loss_vs_best_cp=cp_loss,
        wdl_delta_player_pov=wdl_delta(best.wdl, played_line.wdl),
        wdl_expected_score_loss=wdl_loss,
        severity_text=_severity_text(best.score, played_line.score, cp_loss, wdl_loss, label),
    )


def _label_from_cp_loss(loss: int | None) -> MoveQualityLabel:
    if loss is None:
        return "neutral"
    if loss <= 20:
        return "excellent"
    if loss <= 50:
        return "good"
    if loss <= 75:
        return "neutral"
    if loss <= 150:
        return "inaccuracy"
    if loss <= 300:
        return "mistake"
    return "blunder"


def _label_from_wdl_loss(loss: int | None) -> MoveQualityLabel:
    if loss is None:
        return "neutral"
    if loss <= 10:
        return "excellent"
    if loss <= 25:
        return "good"
    if loss <= 45:
        return "neutral"
    if loss <= 80:
        return "inaccuracy"
    if loss <= 150:
        return "mistake"
    return "blunder"


def _worse_label(left: MoveQualityLabel, right: MoveQualityLabel) -> MoveQualityLabel:
    return left if QUALITY_ORDER[left] >= QUALITY_ORDER[right] else right


def _merge_non_mating_loss_labels(
    cp_label: MoveQualityLabel, wdl_label: MoveQualityLabel
) -> MoveQualityLabel:
    label = _worse_label(cp_label, wdl_label)
    if label == "blunder" and cp_label != "blunder":
        return "mistake"
    return label


def _apply_high_win_probability_floor(
    label: MoveQualityLabel, played_line: EngineLine
) -> MoveQualityLabel:
    if label not in {"inaccuracy", "mistake", "blunder"}:
        return label
    if played_line.score.kind == "mate":
        return label
    if played_line.wdl is None:
        return label
    if played_line.wdl.win >= HIGH_WIN_PROBABILITY_FLOOR:
        return "good"
    return label


def _severity_text(
    best: Score,
    played: Score,
    cp_loss: int | None,
    wdl_loss: int | None,
    label: MoveQualityLabel,
) -> str:
    if label == "forced":
        if played.kind == "mate" and played.mate_for == "opponent":
            return "the player had only one legal move; the position still allowed forced mate"
        return "the player had only one legal move"
    if label == "best" and played.kind == "mate" and played.mate_for == "player":
        return "the played move checkmated the opponent"
    if is_opponent_mate(best) and is_opponent_mate(played):
        if label == "best":
            return "the move was the best defense in a position already losing by forced mate"
        if opponent_mate_is_worse(best, played):
            return "the move shortened the forced mate against the player"
        return "the position remained losing by forced mate"
    if best.kind == "mate" or played.kind == "mate":
        if played.kind == "mate" and played.mate_for == "opponent":
            return "the move allowed a forced mate against the player"
        if best.kind == "mate" and best.mate_for == "player":
            return "the best line had a forced mate for the player"
        return "the move changed a forced-mate evaluation"
    text = f"from {_score_band(score_as_cp(best))} to {_score_band(score_as_cp(played))}"
    if wdl_loss is not None and wdl_loss > 45:
        return f"{text}, with expected score dropping by {wdl_loss}/1000"
    if cp_loss is not None:
        return f"{text}, losing {cp_loss} centipawns versus the best move"
    return text


def _score_band(cp: int) -> str:
    if cp >= 300:
        return "winning"
    if cp >= 150:
        return "clearly better"
    if cp >= 50:
        return "slightly better"
    if cp > -50:
        return "roughly equal"
    if cp > -150:
        return "slightly worse"
    if cp > -300:
        return "clearly worse"
    return "losing"
