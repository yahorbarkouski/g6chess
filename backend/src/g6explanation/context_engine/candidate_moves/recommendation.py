"""Candidate practicality and recommendation-policy decisions."""

from __future__ import annotations

from g6explanation.context_engine.contracts import (
    CandidateRole,
    FindabilityLabel,
    PracticalityCategory,
    RecommendationPolicy,
)


def practicality(
    roles: list[CandidateRole], score_loss: int | None, findability: FindabilityLabel
) -> PracticalityCategory:
    if "played_move" in roles:
        return "unknown_practicality"
    if "engine_best" in roles and findability in {"hard", "very_hard", "engine_like"}:
        return "hard_but_important"
    if "engine_best" in roles:
        return "clear_recommendation"
    if score_loss is not None and score_loss <= 50 and findability in {"obvious", "findable"}:
        return "practical_try"
    if score_loss is not None and score_loss <= 50 and findability == "unknown":
        return "unknown_practicality"
    return "engine_benchmark"


def recommendation_policy(
    practicality: PracticalityCategory,
    findability: FindabilityLabel,
    teachable_skill_gap: bool,
) -> RecommendationPolicy:
    if practicality == "clear_recommendation":
        return "recommend_directly"
    if practicality == "practical_try":
        return "use_as_practical_alternative"
    if practicality == "hard_but_important":
        if teachable_skill_gap or findability in {"very_hard", "engine_like"}:
            return "explain_as_hidden_resource"
        return "mention_with_caveat"
    if practicality == "only_move":
        return "mention_with_caveat"
    return "do_not_recommend"
