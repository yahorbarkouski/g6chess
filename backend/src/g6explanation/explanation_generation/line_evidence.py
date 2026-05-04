"""Verified line evidence for rich explanation hover cards."""

from __future__ import annotations

from g6explanation.context_engine.contracts import CandidateMove, ContextResult, KeyMoveContext
from g6explanation.explanation_generation.contracts import (
    ExplanationLineCard,
    ExplanationLineEvidence,
)

BAD_QUALITY_LABELS = {"inaccuracy", "mistake", "blunder", "missed_win"}
HARD_FINDABILITY = {"hard", "very_hard", "engine_like"}


def build_line_evidence(context_result: ContextResult) -> list[ExplanationLineEvidence]:
    """Build compact verified line options the model may attach to segments."""

    evidence: list[ExplanationLineEvidence] = []
    played_line = _played_line_evidence(context_result)
    if played_line is not None:
        evidence.append(played_line)

    better_line = _better_line_evidence(context_result)
    if better_line is not None:
        evidence.append(better_line)

    return evidence


def line_card_from_evidence(line: ExplanationLineEvidence) -> ExplanationLineCard:
    return ExplanationLineCard(
        id=line.id,
        moves=line.moves,
        title=line.title,
        why=line.why,
    )


def _played_line_evidence(context_result: ContextResult) -> ExplanationLineEvidence | None:
    context = context_result.llm_context
    is_bad = context.quality in BAD_QUALITY_LABELS
    is_notable = context.significance.label in {"high", "critical"}
    if not is_bad and not is_notable:
        return None
    moves = _line_moves(
        context_result.evidence.engine.played_line.pv_san,
        fallback=[context.played, context_result.evidence.engine.after_line.move_san]
        if is_bad and context_result.evidence.engine.after_line is not None
        else None,
    )
    if moves is None:
        return None
    return ExplanationLineEvidence(
        id="played-line",
        role="played_line",
        moves=moves,
        title=f"Why {context.played} gets punished" if is_bad else f"Why {context.played} works",
        why=_played_line_why(context_result, is_bad=is_bad),
    )


def _better_line_evidence(context_result: ContextResult) -> ExplanationLineEvidence | None:
    context = context_result.llm_context
    for move_context in (
        context.practical_alternative,
        context.best_or_key_move,
        context.engine_best_move,
    ):
        if move_context is None or move_context.move == context.played:
            continue
        candidate = _candidate_for_move_context(context_result, move_context)
        if candidate is None:
            continue
        moves = _line_moves(candidate.pv_short_san)
        if moves is None:
            continue
        return ExplanationLineEvidence(
            id="better-line",
            role="better_line",
            moves=moves,
            title=f"Why {move_context.move} works",
            why=_better_line_why(context_result, move_context),
        )
    return None


def _candidate_for_move_context(
    context_result: ContextResult,
    move_context: KeyMoveContext,
) -> CandidateMove | None:
    return next(
        (
            candidate
            for candidate in context_result.evidence.candidates
            if candidate.san == move_context.move
        ),
        None,
    )


def _line_moves(
    moves: list[str],
    fallback: list[str] | None = None,
) -> list[str] | None:
    line = moves if len(moves) >= 2 else fallback
    if line is None or len(line) < 2:
        return None
    return line[:5]


def _played_line_why(context_result: ContextResult, *, is_bad: bool) -> str:
    context = context_result.llm_context
    reply = context_result.evidence.engine.after_line
    if not is_bad:
        return f"{context.main_point} This supplied line shows the continuation behind the move."
    if reply is None:
        return context.main_point
    return (
        f"{context.main_point} The line starts with {reply.move_san}, "
        "the supplied reply that shows how the opponent can punish the move."
    )


def _better_line_why(
    context_result: ContextResult,
    move_context: KeyMoveContext,
) -> str:
    reply = context_result.evidence.engine.after_line
    if context_result.llm_context.quality in BAD_QUALITY_LABELS and reply is not None:
        base = (
            f"{move_context.move} avoids the immediate {reply.move_san} resource "
            "from the played-move line."
        )
    else:
        base = move_context.reason
    if move_context.findability in HARD_FINDABILITY:
        return (
            f"{base} It is marked {move_context.findability}, "
            "so the line is a review point rather than obvious advice."
        )
    return base
