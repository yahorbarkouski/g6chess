"""LLM-facing explanation agenda construction."""

from __future__ import annotations

import chess

from g6explanation.context_engine.contracts import (
    CandidateMove,
    EngineAnalysis,
    KeyMoveContext,
    MainPoint,
    MoveQuality,
    PlayedMoveFacts,
    TimeSituation,
)
from g6explanation.context_engine.signals.quality import BAD_QUALITY_LABELS


def build_main_point(
    board: chess.Board,
    played: PlayedMoveFacts,
    quality: MoveQuality,
    key_candidate: CandidateMove | None,
    featured_candidate: CandidateMove | None,
    analysis: EngineAnalysis,
) -> MainPoint:
    quality_claim = build_quality_claim(played, quality)
    if quality.label == "forced":
        return MainPoint(
            concept="forced move",
            claim=f"{quality_claim}; the player had no legal alternative.",
        )
    if key_candidate is None:
        if quality.label == "best" and featured_candidate is not None:
            return MainPoint(
                concept=_featured_best_concept(played, analysis),
                claim=_featured_best_claim(played, quality_claim, analysis),
            )
        if quality.label == "best":
            return MainPoint(
                concept="move quality",
                claim=f"{quality_claim}; no sharper alternative is needed for this moment.",
            )
        return MainPoint(
            concept="move quality",
            claim=f"{quality_claim}; it did not lose meaningful value versus the engine choice.",
        )

    key_move = chess.Move.from_uci(key_candidate.uci)
    if key_candidate.practicality == "practical_try":
        return MainPoint(
            concept="practical alternative",
            claim=(
                f"{quality_claim}; {key_candidate.san} was a practical alternative "
                "close to the engine best move."
            ),
        )

    if key_move in board.legal_moves and board.gives_check(key_move):
        return MainPoint(
            concept="forcing moves before quiet moves",
            claim=f"{quality_claim}; {key_candidate.san} was the key forcing check.",
        )

    if analysis.after_line is not None and quality.label in BAD_QUALITY_LABELS:
        return MainPoint(
            concept="opponent resource",
            claim=(
                f"{quality_claim} because it let the opponent improve with "
                f"{analysis.after_line.move_san}."
            ),
        )

    return MainPoint(
        concept="better alternative",
        claim=f"{quality_claim}; {key_candidate.san} was the better move.",
    )


def build_allowed_claims(
    played: PlayedMoveFacts,
    quality: MoveQuality,
    key_candidate: CandidateMove | None,
    featured_candidate: CandidateMove | None,
    analysis: EngineAnalysis,
) -> list[str]:
    claims = [build_quality_claim(played, quality)]
    if key_candidate:
        claims.append(f"{key_candidate.san} was the key alternative")
        if key_candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
            claims.append(f"{key_candidate.san} was hard to find")
        if key_candidate.teachable_skill_gap:
            claims.append(f"{key_candidate.san} becomes more common at stronger levels")
        if key_candidate.practicality == "practical_try":
            claims.append(f"{key_candidate.san} was a practical alternative")
    if featured_candidate and not key_candidate:
        claims.append(f"{featured_candidate.san} was the featured move")
    if analysis.after_line and quality.label in BAD_QUALITY_LABELS:
        claims.append(
            f"the opponent's key reply after {played.san} was {analysis.after_line.move_san}"
        )
    return list(dict.fromkeys(claims))


def build_human_note(
    key_candidate: CandidateMove | None, time_situation: TimeSituation
) -> str | None:
    if key_candidate is None:
        return None
    if key_candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
        time_phrase = (
            "" if time_situation == "unknown" else f" in {time_situation.replace('_', ' ')}"
        )
        if key_candidate.teachable_skill_gap:
            return (
                f"{key_candidate.san} was {key_candidate.time_adjusted_findability} to find"
                f"{time_phrase}, but it becomes more common for stronger players; the useful "
                "lesson is the idea, not that it was obvious."
            )
        return (
            f"{key_candidate.san} was {key_candidate.time_adjusted_findability} to find"
            f"{time_phrase}; the useful lesson is the idea, not that it was obvious."
        )
    if key_candidate.teachable_skill_gap:
        return (
            f"{key_candidate.san} is a teachable upgrade: it is more common for stronger "
            "players while still realistic enough to mention."
        )
    return None


def build_key_move_context(candidate: CandidateMove | None) -> KeyMoveContext | None:
    if candidate is None:
        return None
    return KeyMoveContext(
        move=candidate.san,
        practicality=candidate.practicality,
        findability=candidate.time_adjusted_findability,
        reason=_key_move_reason(candidate),
        recommendation_policy=candidate.recommendation_policy,
    )


def build_quality_claim(played: PlayedMoveFacts, quality: MoveQuality) -> str:
    if quality.label == "best":
        return f"{played.san} was the best move"
    if quality.label == "forced":
        return f"{played.san} was forced"
    if quality.label == "missed_win":
        return f"{played.san} missed a winning move"
    if quality.label in {"excellent", "good", "neutral"}:
        return f"{played.san} was {quality.label}"
    return f"{played.san} was {article(quality.label)} {quality.label}"


def article(label: str) -> str:
    return "an" if label[0].lower() in {"a", "e", "i", "o", "u"} else "a"


def _key_move_reason(candidate: CandidateMove) -> str:
    if candidate.score.kind == "mate" and candidate.score.mate_for == "player":
        return "it checkmates the opponent"
    if candidate.practicality == "only_move":
        return "it is the only legal move"
    if candidate.practicality == "practical_try":
        return "it is close to the engine best move and more practical for the player"
    if candidate.recommendation_policy == "explain_as_hidden_resource":
        return "it is an important hidden resource that becomes more visible with stronger play"
    if candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
        return "it is objectively important but hard to find"
    if candidate.score_loss_vs_best_cp == 0:
        return "it is the engine's best move"
    return "it is a better practical move"


def _featured_best_concept(played: PlayedMoveFacts, analysis: EngineAnalysis) -> str:
    if (
        analysis.played_line.score.kind == "mate"
        and analysis.played_line.score.mate_for == "player"
    ):
        return "forced mate"
    if played.is_check:
        return "forcing move"
    if played.is_capture:
        return "capture"
    return "critical best move"


def _featured_best_claim(
    played: PlayedMoveFacts, quality_claim: str, analysis: EngineAnalysis
) -> str:
    if (
        analysis.played_line.score.kind == "mate"
        and analysis.played_line.score.mate_for == "player"
    ):
        return f"{quality_claim}; it delivered forced mate."
    if played.is_check:
        return f"{quality_claim}; it gave check in a critical position."
    if played.is_capture:
        return f"{quality_claim}; it captured in a critical position."
    if analysis.after_line is not None:
        return f"{quality_claim}; this was the critical move before {analysis.after_line.move_san}."
    return f"{quality_claim}; this was the critical move in the position."
