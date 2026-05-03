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
            "State the move quality clearly.",
            (
                "Do not add moves, PV continuations, material claims, tactic claims, "
                "concept claims, or mate claims unless they are supplied in "
                "allowed_claims or candidates."
            ),
            (
                "Treat engine_best_move as objective truth and practical_alternative "
                "as a coaching option."
            ),
            (
                "Respect recommendation_policy fields: never tell the player to play "
                "a do_not_recommend move."
            ),
            "Caveat hard, very_hard, or engine_like alternatives.",
            "Do not include raw engine numbers, WDL, centipawns, or Stockfish dumps.",
        ],
    }
    if retry_issues:
        payload["previous_verifier_failures"] = [issue.to_dict() for issue in retry_issues]

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
                    "phrase that evidence clearly for the player. Return strict JSON "
                    "with one field named explanation."
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
