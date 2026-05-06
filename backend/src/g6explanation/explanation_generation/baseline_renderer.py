"""Deterministic fallback explanation rendering."""

from __future__ import annotations

from g6explanation.context_engine.contracts import ContextResult, KeyMoveContext
from g6explanation.explanation_generation.contracts import ExplanationOutput, ExplanationSegment


def render_baseline_explanation(context_result: ContextResult) -> ExplanationOutput:
    """Render a conservative explanation from verified LLM context only."""

    context = context_result.llm_context
    parts = [_normalize_sentence(context.main_point)]
    has_sacrifice = _has_sacrifice_claim(context_result)

    teaching_move = context.featured_move or context.best_or_key_move
    move_sentence = (
        None
        if _has_simple_material_loss(context_result) or has_sacrifice
        else _teaching_move_sentence(teaching_move)
    )
    if move_sentence and move_sentence.lower() not in parts[0].lower():
        parts.append(move_sentence)

    if context.human_note and not has_sacrifice:
        parts.append(_normalize_sentence(context.human_note))

    deduped_parts = _dedupe(parts)
    return ExplanationOutput(
        segments=[ExplanationSegment(text=part, line_card_id=None) for part in deduped_parts[:6]],
        line_cards=[],
    )


def _teaching_move_sentence(move_context: KeyMoveContext | None) -> str | None:
    if move_context is None:
        return None
    caveat = ""
    if move_context.findability in {"hard", "very_hard", "engine_like"}:
        caveat = " It was hard to find, so the lesson is the idea rather than blame."
    return _normalize_sentence(
        f"The key move to understand was {move_context.move}: {move_context.reason}.{caveat}"
    )


def _normalize_sentence(text: str) -> str:
    stripped = " ".join(text.strip().split())
    if stripped.endswith((".", "!", "?")):
        return stripped
    return f"{stripped}."


def _dedupe(parts: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for part in parts:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(part)
    return deduped


def _has_simple_material_loss(context_result: ContextResult) -> bool:
    for claim in context_result.llm_context.concept_claims:
        if claim.kind != "material" or claim.subject != "played_move":
            continue
        if "hung" in claim.claim.lower():
            return True
    return False


def _has_sacrifice_claim(context_result: ContextResult) -> bool:
    return any(
        claim.kind == "sacrifice" and claim.subject == "played_move"
        for claim in context_result.llm_context.concept_claims
    )
