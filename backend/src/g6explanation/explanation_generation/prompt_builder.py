"""Prompt construction for one verified move explanation."""

from __future__ import annotations

import json

from g6explanation.context_engine.contracts import ContextResult
from g6explanation.explanation_generation.contracts import (
    PROMPT_ID,
    PROMPT_VERSION,
    CoachPrompt,
    ExplanationOutput,
    ExplanationVerificationIssue,
)


def build_coach_prompt(
    context_result: ContextResult,
    retry_issues: list[ExplanationVerificationIssue] | None = None,
) -> CoachPrompt:
    """Build the static prompt plus compact verified move context."""

    payload: dict[str, object] = {
        "task": "Write one verified chess-coach explanation for the played move.",
        "llm_context": context_result.llm_context.to_dict(),
        "constraints": [
            "Use only supplied context.",
            "Return exactly one JSON object with an explanation string.",
            (
                "Use a neutral explanatory voice. Do not address the player directly, "
                "and do not write broadcast-style commentary."
            ),
            (
                "Prefer one compact sentence. Use two short sentences only when a "
                "mistake, missed win, forced move, or hard alternative needs contrast."
            ),
            (
                "Avoid rigid templates and vary sentence shape naturally across moves. "
                "Do not start every explanation with the same quality label pattern."
            ),
            (
                "State serious outcomes clearly: forced moves, inaccuracies, mistakes, "
                "blunders, and missed wins must be named. For best, good, excellent, "
                "or neutral moves, explain the supported purpose naturally without "
                "forcing a visible quality label every time."
            ),
            (
                "Choose the smallest sufficient teaching point. Do not list every "
                "supplied candidate or concept. Mention at most one better, practical, "
                "or hidden move unless the main_point itself needs a direct contrast."
            ),
            (
                "For good high-WDL or good-not-best moves, explain why the played move "
                "still worked; do not caveat with hidden engine resources unless that "
                "hidden idea is the central lesson."
            ),
            (
                "For low-significance best, excellent, good, or neutral moves, do not "
                "mention hidden resources, hard-to-find language, or comparison "
                "alternatives. One supported purpose for the played move is enough."
            ),
            (
                "Reserve hard-to-find and hidden-resource wording for high or critical "
                "review points, missed wins, bad moves, or unplayed alternatives that "
                "the context makes the lesson."
            ),
            (
                "For forced legal moves, keep the explanation centered on the lack of "
                "legal alternatives. Do not add residual position status unless it "
                "directly explains the move."
            ),
            (
                "Do not expose internal wording such as featured move, move quality, "
                "verified context, supplied context, allowed_claims, concept_claims, "
                "recommendation_policy, or engine-listed."
            ),
            (
                "Do not add moves, PV continuations, material claims, tactic claims, "
                "concept claims, or mate claims unless they are supplied in "
                "concept_claims, allowed_claims, or candidates."
            ),
            (
                "Do not use named tactic labels such as fork, pin, skewer, "
                "deflection, decoy, overload, discovered attack, zwischenzug, "
                "intermezzo, or back rank unless concept_claims includes kind "
                "tactic naming that same idea."
            ),
            (
                "Treat engine_best_move as objective truth and practical_alternative "
                "as a coaching option."
            ),
            (
                "Do not call a practical_alternative a better move or better "
                "alternative unless a supplied better_alternative claim supports that wording."
            ),
            (
                "Respect recommendation_policy fields: never tell the player to play "
                "a do_not_recommend move."
            ),
            (
                "Use recommendation_policy literally: recommend_directly allows direct "
                "advice; use_as_practical_alternative is a practical coaching option; "
                "mention_with_caveat and explain_as_hidden_resource are review points "
                "that need hard/hidden caveats; do_not_recommend must not be called "
                "the better move, recommendation, or move to play."
            ),
            "Caveat hard, very_hard, or engine_like alternatives.",
            "Do not include raw engine numbers, WDL, centipawns, or Stockfish dumps.",
        ],
    }
    if retry_issues:
        payload["previous_verifier_failures"] = [issue.to_dict() for issue in retry_issues]
        payload["retry_repair_instructions"] = _retry_repair_instructions(retry_issues)

    return CoachPrompt(
        prompt_id=PROMPT_ID,
        prompt_version=PROMPT_VERSION,
        context_version=context_result.evidence.context_version,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a chess coach for one verified move. The chess truth is "
                    "already decided by deterministic evidence. Your job is only to "
                    "phrase that evidence as a concise, neutral explanation. Return "
                    "strict JSON with one field named explanation."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, sort_keys=True, separators=(",", ":")),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "single_move_explanation",
                "strict": True,
                "schema": ExplanationOutput.json_schema(),
            },
        },
    )


def _retry_repair_instructions(
    retry_issues: list[ExplanationVerificationIssue],
) -> list[str]:
    codes = {issue.code for issue in retry_issues}
    instructions: list[str] = []
    if "unsupported_tactic_claim" in codes:
        instructions.append(
            "Remove named tactic labels unless a supplied tactic concept_claim names the tactic."
        )
    if "recommendation_policy_violation" in codes:
        instructions.append(
            "Attach recommendation wording only to moves marked recommend_directly or "
            "use_as_practical_alternative."
        )
    if "unsupported_mate_claim" in codes:
        instructions.append(
            "Use mate wording only for supplied forced_mate claims or verified "
            "immediate mate moves."
        )
    if "unsupported_material_claim" in codes:
        instructions.append(
            "Use material wording only when a supplied material concept_claim names the material."
        )
    if "mentioned_move_unsupported" in codes or "unsupported_pv" in codes:
        instructions.append(
            "Mention only the played move, supplied candidate moves, and explicitly "
            "allowed replies."
        )
    if not instructions:
        instructions.append("Rewrite using only the supplied allowed_claims and concept_claims.")
    return instructions
