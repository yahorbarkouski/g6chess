"""Candidate ordering and key-candidate selection."""

from __future__ import annotations

from g6explanation.context_engine.contracts import CandidateMove, MoveQuality
from g6explanation.context_engine.signals.quality import BAD_QUALITY_LABELS


def choose_key_candidate(
    candidates: list[CandidateMove], quality: MoveQuality
) -> CandidateMove | None:
    if quality.label not in BAD_QUALITY_LABELS:
        return None

    practical = [
        candidate
        for candidate in candidates
        if "played_move" not in candidate.roles and candidate.practicality == "practical_try"
    ]
    if practical:
        return sorted(practical, key=recommendation_sort_key)[0]

    hidden = [
        candidate
        for candidate in candidates
        if "played_move" not in candidate.roles
        and candidate.recommendation_policy == "explain_as_hidden_resource"
    ]
    if hidden:
        return sorted(hidden, key=recommendation_sort_key)[0]

    for candidate in candidates:
        if "engine_best" in candidate.roles:
            return candidate
    return None


def candidate_sort_key(candidate: CandidateMove) -> tuple[int, int, int]:
    if "engine_best" in candidate.roles:
        role_rank = 0
    elif candidate.practicality == "practical_try":
        role_rank = 1
    elif "played_move" in candidate.roles:
        role_rank = 2
    else:
        role_rank = 3
    human_rank = (
        candidate.human_rank
        if "human_common_move" in candidate.roles and candidate.human_rank
        else 999
    )
    score_loss = (
        candidate.score_loss_vs_best_cp if candidate.score_loss_vs_best_cp is not None else 99_999
    )
    return role_rank, score_loss, human_rank


def recommendation_sort_key(candidate: CandidateMove) -> tuple[int, float]:
    score_loss = (
        candidate.score_loss_vs_best_cp if candidate.score_loss_vs_best_cp is not None else 99_999
    )
    probability = candidate.player_level_probability or 0
    return score_loss, -probability
