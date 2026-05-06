"""Verified line evidence for rich explanation hover cards."""

from __future__ import annotations

from g6explanation.context_engine.contracts import (
    CandidateMove,
    ContextResult,
    EngineLine,
    KeyMoveContext,
)
from g6explanation.explanation_generation.contracts import (
    MAX_LINE_CARD_PLIES,
    ExplanationLineCard,
    ExplanationLineEvidence,
)

BAD_QUALITY_LABELS = {"inaccuracy", "mistake", "blunder", "missed_win"}
HARD_FINDABILITY = {"hard", "very_hard", "engine_like"}


def build_line_evidence(context_result: ContextResult) -> list[ExplanationLineEvidence]:
    """Build compact verified line options the model may attach to segments."""

    evidence: list[ExplanationLineEvidence] = []
    objection_line = _objection_line_evidence(context_result)
    if objection_line is not None:
        evidence.append(objection_line)

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
        title="How the mistake gets punished" if is_bad else "How the idea plays out",
        why=_played_line_why(context_result, is_bad=is_bad),
    )


def _objection_line_evidence(context_result: ContextResult) -> ExplanationLineEvidence | None:
    tactical_proof_text = " ".join(
        claim.claim
        for claim in context_result.llm_context.concept_claims
        if claim.kind == "tactical_proof"
    )
    if not tactical_proof_text:
        return None

    for line in context_result.evidence.engine.opponent_reply_lines:
        if len(line.pv_san) < 2:
            continue
        if line.pv_san[0] not in tactical_proof_text or line.pv_san[1] not in tactical_proof_text:
            continue
        moves = _line_moves([context_result.llm_context.played, *line.pv_san])
        if moves is None or len(moves) < 3:
            continue
        return ExplanationLineEvidence(
            id="objection-line",
            role="objection_line",
            moves=moves,
            title="Why the capture fails",
            why=(
                "The line shows the tactical reply behind the apparent capture, "
                "so the moved piece is not simply free."
            ),
        )
    return None


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
        engine_line = _engine_line_for_candidate(context_result, candidate)
        moves = _line_moves(
            engine_line.pv_san if engine_line is not None else candidate.pv_short_san
        )
        if moves is None:
            continue
        return ExplanationLineEvidence(
            id="better-line",
            role="better_line",
            moves=moves,
            title="How the alternative works",
            why=_better_line_why(move_context),
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


def _engine_line_for_candidate(
    context_result: ContextResult,
    candidate: CandidateMove,
) -> EngineLine | None:
    for line in context_result.evidence.engine.top_lines:
        if line.move_uci == candidate.uci:
            return line
    return None


def _line_moves(
    moves: list[str],
    fallback: list[str] | None = None,
) -> list[str] | None:
    line = moves if len(moves) >= 2 else fallback
    if line is None or len(line) < 2:
        return None
    return line[:MAX_LINE_CARD_PLIES]


def _played_line_why(
    context_result: ContextResult,
    *,
    is_bad: bool,
) -> str:
    if context_result.evidence.engine.played_line.score.kind == "mate":
        return "The full line shows the forcing pattern all the way to mate."
    if is_bad:
        return "The follow-up shows the opponent keeping pressure after the mistake."
    return "The follow-up shows how the move's idea keeps working after the first response."


def _better_line_why(move_context: KeyMoveContext) -> str:
    if move_context.findability in HARD_FINDABILITY:
        return (
            "The follow-up shows the idea, but it is hard to find, so it is a "
            "review point rather than obvious advice."
        )
    return "The follow-up shows how the alternative develops after the first response."
