"""Prompt construction for one verified move explanation."""

from __future__ import annotations

import json
from typing import Any, TypeAlias, cast

from g6explanation.context_engine.contracts import ContextResult
from g6explanation.explanation_generation.contracts import (
    PROMPT_ID,
    PROMPT_VERSION,
    CoachPrompt,
    ExplanationOutput,
    ExplanationVerificationIssue,
)
from g6explanation.explanation_generation.line_evidence import build_line_evidence

JsonValue: TypeAlias = dict[str, "JsonValue"] | list["JsonValue"] | str | int | float | bool | None


def build_coach_prompt(
    context_result: ContextResult,
    retry_issues: list[ExplanationVerificationIssue] | None = None,
) -> CoachPrompt:
    """Build the static prompt plus compact verified move context."""

    payload: dict[str, object] = {
        "task": "Write one verified chess-coach explanation for the played move.",
        "llm_context": context_result.llm_context.to_dict(),
        "line_evidence": [line.to_dict() for line in build_line_evidence(context_result)],
        "constraints": [
            "Use only supplied context.",
            (
                "Return exactly one JSON object with segments and line_cards. "
                "Do not return a flat explanation field."
            ),
            (
                "segments are visible UI text chunks. Each segment needs text and "
                "line_card_id. It also needs line_card_anchor when line_card_id "
                "is not null. Use null for line_card_id and line_card_anchor when "
                "no hover card belongs to that text."
            ),
            (
                "Segments should remain natural sentence-sized prose. Do not split "
                "sentences into tiny text fragments just to create highlights."
            ),
            (
                "line_card_anchor is the exact short phrase the UI should highlight "
                "inside that segment text. It must be an exact substring of text, "
                "no more than 60 characters, no more than 8 words, and not the "
                "whole sentence. Prefer plain idea phrases such as 'the follow-up', "
                "'the longer line', or 'the mating pattern' over notation-heavy anchors."
            ),
            (
                "line_cards are optional hover cards for supplied line_evidence only. "
                "Use at most two cards unless the context clearly needs more. "
                "The card why should add the follow-through or deeper point from "
                "the variation; do not repeat the visible segment in different words. "
                "Do not read the move sequence aloud in the card why. Copy the "
                "supplied line_evidence title and why exactly."
            ),
            (
                "If you use a line card, copy its id and moves exactly from line_evidence. "
                "Do not shorten long supplied move sequences, and do not create new "
                "line-card ids or new move sequences. The moves array is for board "
                "visualization; the visible text should explain the idea simply."
            ),
            (
                "Keep the visible explanation compact but not thin: usually two to five "
                "segments and roughly 35 to 90 visible words."
            ),
            (
                "Avoid notation-heavy prose. Mention the played move and at most one "
                "key reply or alternative when needed; otherwise describe the idea in "
                "plain language such as the knight forks both rooks, the bishop gets a "
                "diagonal, or the king is left exposed."
            ),
            (
                "Do not describe a variation as 'after MOVE, MOVE...' in visible text "
                "or card prose. Avoid generic capture/takes wording in line-card prose; "
                "use follow-up, pressure, idea, or mating pattern unless a supplied "
                "claim makes the capture itself the lesson."
            ),
            (
                "Use a neutral explanatory voice. Do not address the player directly, "
                "and do not write broadcast-style commentary."
            ),
            (
                "Write like a compact game-review note that explains the chess reason, "
                "not like a verdict card. Prefer one compact sentence. Use two short "
                "sentences only when a mistake, missed win, forced move, or hard "
                "alternative needs contrast."
            ),
            (
                "Avoid rigid templates and vary sentence shape naturally across moves. "
                "Do not start every explanation with the same quality label pattern, "
                "and avoid repeated 'MOVE was QUALITY because' constructions."
            ),
            (
                "For non-bad moves, usually lead with the concrete chess function of "
                "the move: develops, claims the center, keeps pressure, improves a "
                "piece, creates a threat, simplifies, or holds the position. Use only "
                "functions supported by the supplied claims."
            ),
            (
                "State serious outcomes clearly: forced moves, inaccuracies, mistakes, "
                "blunders, and missed wins must be named. For best, good, excellent, "
                "or neutral moves, explain the supported purpose naturally without "
                "forcing a visible quality label every time."
            ),
            (
                "For routine best moves, do not say 'best move' unless the position is "
                "high-significance, critical, mating, forced, or the best-move status "
                "is itself the lesson."
            ),
            (
                "Even in high-significance positions, avoid the phrase 'critical best "
                "move' unless no clearer chess wording is available. Prefer concrete "
                "role wording such as key capture, forcing check, open-file move, "
                "decisive resource, or strongest continuation when the supplied "
                "claims support it."
            ),
            (
                "Do not use generic value-preservation filler such as 'without giving "
                "up meaningful value' by itself when a typed concept claim gives a "
                "more concrete reason. If no concrete concept is supplied, keep the "
                "holding explanation short."
            ),
            (
                "Do not lean on 'no sharper alternative needed' as a default ending. "
                "Use that idea only when the supplied context makes an alternative "
                "comparison the lesson; otherwise stop after the concrete chess reason."
            ),
            (
                "Choose the smallest sufficient teaching point. Do not list every "
                "supplied candidate, concept, or line card. Mention at most one better, "
                "practical, or hidden move unless the main_point itself needs a direct contrast."
            ),
            (
                "When concept_claims supplies concrete board-feature facts such as a "
                "move attacking valuable pieces, forking pieces, opening a bishop route, "
                "opening a diagonal, or clearing a piece route, prefer that board fact "
                "over generic continuation wording."
            ),
            (
                "When a material concept_claim says a bad played move hung or lost a "
                "named piece to the opponent's immediate reply, make that simple "
                "material loss the main chess reason. Mention the reply only as the "
                "capture that wins the piece; do not replace it with generic "
                "follow-up, pressure, or long-line wording."
            ),
            (
                "When concept_claims includes tactical_proof or line_evidence includes "
                "an objection_line, answer the apparent objection directly: explain why "
                "the move is not simply free or why the capture fails, using the supplied "
                "reply line. Name the attempted capture and the reply when the supplied "
                "claim names them. Prefer this over a generic 'follow-up' sentence."
            ),
            (
                "When concept_claims includes sacrifice, make that sacrifice the main "
                "chess point. If the sacrifice claim names a queen or rook and beauty "
                "is beautiful or brilliant, it is fine to call it a beautiful or "
                "brilliant queen or rook sacrifice. Start the visible explanation from "
                "the sacrifice itself; smaller attack, quiet-move, hidden-resource, "
                "hard-to-find, or generic follow-up details are optional support only "
                "and should not lead."
            ),
            (
                "If a supplied claim says the move attacks or forks pieces, name the "
                "attacked pieces exactly as supplied before using any line-card continuation, "
                "unless a sacrifice claim is supplied and already gives the clearer main point."
            ),
            (
                "Do not name opening systems or opening-family labels unless supplied "
                "opening metadata gives that exact name. Without opening metadata, "
                "explain the board feature: center, diagonal, bishop route, piece "
                "activity, or pawn structure."
            ),
            (
                "For unplayed alternatives, use counterfactual review wording such as "
                "'MOVE was the practical alternative', 'MOVE would have kept more "
                "pressure', or 'MOVE would trade ...'. Use better-move wording only "
                "when a supplied better_alternative claim or direct recommendation "
                "policy supports it. Do not phrase an unplayed alternative as if the "
                "player actually made it."
            ),
            (
                "When a bad move allows a key reply, explain why that reply is good for "
                "the opponent and bad for the player. Do not stop at 'it allowed MOVE'."
            ),
            (
                "For good high-WDL or good-not-best moves, explain why the played move "
                "still worked; do not caveat with hidden engine resources unless that "
                "hidden idea is the central lesson."
            ),
            (
                "diagnostic_tags are deterministic review and wording guidance, not new "
                "chess lines. Use them to decide whether to credit fast moves, caveat "
                "time pressure, describe WDL edge cases, or avoid blame for forced moves; "
                "the objective quality, significance, and concept_claims remain the truth."
            ),
            (
                "Use time-pressure, clock, fast-move, increment, or spent-time wording "
                "only when time_situation, think_time_seconds, clock fields, or "
                "diagnostic_tags explicitly support it."
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
                "recommendation_policy, engine best move, engine choice, engine line, "
                "or engine-listed."
            ),
            (
                "Do not add moves, PV continuations, material claims, tactic claims, "
                "concept claims, or mate claims unless they are supplied in "
                "concept_claims, allowed_claims, candidates, or line_evidence."
            ),
            (
                "If concept_claims says a move recaptured or restored the material "
                "balance, describe it as a recapture or recovery; do not call it "
                "winning, gaining, or picking up material."
            ),
            (
                "If concept_claims says a move traded or exchanged material, describe "
                "that as a trade or exchange; do not call it winning, gaining, or "
                "picking up material."
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
                    "phrase that evidence as concise, useful UI copy. Return strict "
                    "JSON with visible segments, optional short line-card anchors, "
                    "and optional verified line cards."
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
                "schema": _strict_response_schema(ExplanationOutput.json_schema()),
            },
        },
    )


def _strict_response_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Adapt Pydantic JSON Schema to OpenAI/Azure strict structured-output rules."""

    strict_schema = cast(dict[str, JsonValue], dict(schema))
    _require_all_object_properties(strict_schema)
    return cast(dict[str, Any], strict_schema)


def _require_all_object_properties(value: JsonValue) -> None:
    if isinstance(value, dict):
        value.pop("default", None)
        properties = value.get("properties")
        if isinstance(properties, dict):
            value["required"] = list(properties)
        for child in value.values():
            _require_all_object_properties(child)
        return
    if isinstance(value, list):
        for child in value:
            _require_all_object_properties(child)


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
            "Use material gain or loss wording only when a supplied material concept_claim "
            "supports that direction and names the material; recapture, recovery, trade, "
            "or exchange claims must keep that exact material relationship."
        )
    if "mentioned_move_unsupported" in codes or "unsupported_pv" in codes:
        instructions.append(
            "Mention only the played move, supplied candidate moves, and explicitly "
            "allowed replies."
        )
    if not instructions:
        instructions.append("Rewrite using only the supplied allowed_claims and concept_claims.")
    return instructions
