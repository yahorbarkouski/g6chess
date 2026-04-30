"""Candidate move construction and recommendation policy."""

from __future__ import annotations

import chess

from g6explanation.context_engine.contracts import (
    CandidateMove,
    CandidateRole,
    EngineAnalysis,
    EngineLine,
    FindabilityLabel,
    HumanMoveLikelihood,
    MoveContextRequest,
    MoveQuality,
    PracticalityCategory,
    RecommendationPolicy,
    TimeSituation,
)
from g6explanation.context_engine.move_quality import (
    BAD_QUALITY_LABELS,
    line_score_loss,
    score_as_cp,
)

FINDABILITY_STEPS: tuple[FindabilityLabel, ...] = (
    "obvious",
    "findable",
    "hard",
    "very_hard",
    "engine_like",
)


def build_candidates(
    board: chess.Board,
    analysis: EngineAnalysis,
    human_likelihoods: dict[str, HumanMoveLikelihood],
    request: MoveContextRequest,
    time_situation: TimeSituation,
    supplemental_lines: list[EngineLine] | None = None,
) -> list[CandidateMove]:
    best = analysis.top_lines[0]
    best_cp = score_as_cp(best.score)
    best_move_uci = best.move_uci
    candidates: dict[str, CandidateMove] = {}

    for line in analysis.top_lines:
        score_loss = line_score_loss(best_cp, line)
        roles: list[CandidateRole] = (
            ["engine_best"] if line.move_uci == best_move_uci else ["close_engine_alternative"]
        )
        if score_loss is not None and score_loss <= 50 and "engine_best" not in roles:
            roles.append("practical_alternative")
        candidates[line.move_uci] = _candidate_from_line(
            line=line,
            roles=_roles_with_human_likelihood(roles, human_likelihoods.get(line.move_uci)),
            best_cp=best_cp,
            human_likelihood=human_likelihoods.get(line.move_uci),
            board=board,
            time_situation=time_situation,
        )

    for line in supplemental_lines or []:
        if line.move_uci in candidates:
            continue
        score_loss = line_score_loss(best_cp, line)
        roles = ["human_common_move"]
        if score_loss is not None and score_loss <= 50:
            roles.append("practical_alternative")
        candidates[line.move_uci] = _candidate_from_line(
            line=line,
            roles=roles,
            best_cp=best_cp,
            human_likelihood=human_likelihoods.get(line.move_uci),
            board=board,
            time_situation=time_situation,
        )

    if analysis.played_line.move_uci in candidates:
        existing = candidates[analysis.played_line.move_uci]
        candidates[analysis.played_line.move_uci] = existing.model_copy(
            update={"roles": _append_role(existing.roles, "played_move")}
        )
    else:
        candidates[analysis.played_line.move_uci] = _candidate_from_line(
            line=analysis.played_line,
            roles=_roles_with_human_likelihood(
                ["played_move"], human_likelihoods.get(analysis.played_line.move_uci)
            ),
            best_cp=best_cp,
            human_likelihood=human_likelihoods.get(analysis.played_line.move_uci),
            board=board,
            time_situation=time_situation,
        )

    return sorted(candidates.values(), key=_candidate_sort_key)


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
        return sorted(practical, key=_recommendation_sort_key)[0]

    hidden = [
        candidate
        for candidate in candidates
        if "played_move" not in candidate.roles
        and candidate.recommendation_policy == "explain_as_hidden_resource"
    ]
    if hidden:
        return sorted(hidden, key=_recommendation_sort_key)[0]

    for candidate in candidates:
        if "engine_best" in candidate.roles:
            return candidate
    return None


def time_situation(request: MoveContextRequest) -> TimeSituation:
    clock = request.clock_before_seconds
    increment = request.increment_seconds or 0
    if clock is not None:
        if clock <= 10 and increment <= 2:
            return "time_scramble"
        if clock <= 30:
            return "low_time"

    control = (request.time_control or "").lower()
    if "bullet" in control:
        return "time_scramble"
    if "blitz" in control:
        return "blitz_normal"
    if "rapid" in control:
        return "rapid_normal"
    if "classical" in control:
        return "classical_or_no_pressure"
    return "unknown"


def _candidate_from_line(
    line: EngineLine,
    roles: list[CandidateRole],
    best_cp: int,
    human_likelihood: HumanMoveLikelihood | None,
    board: chess.Board,
    time_situation: TimeSituation,
) -> CandidateMove:
    score_loss = line_score_loss(best_cp, line)
    probability = human_likelihood.player_level_probability if human_likelihood else None
    plus_400_probability = human_likelihood.plus_400_probability if human_likelihood else None
    move = chess.Move.from_uci(line.move_uci)
    findability, source, confidence, skill_gap = _findability(
        probability=probability,
        plus_400_probability=plus_400_probability,
        evidence_source=human_likelihood.evidence_source if human_likelihood else None,
        board=board,
        move=move,
        situation=time_situation,
    )
    practicality = _practicality(roles, score_loss, findability)
    return CandidateMove(
        san=line.move_san,
        uci=line.move_uci,
        roles=roles,
        engine_rank=line.rank,
        human_rank=human_likelihood.rank if human_likelihood else None,
        score=line.score,
        score_loss_vs_best_cp=score_loss,
        wdl=line.wdl,
        pv_short_san=line.pv_san[:3],
        player_level_probability=probability,
        plus_400_probability=plus_400_probability,
        time_adjusted_findability=findability,
        findability_source=source,
        findability_confidence=confidence,
        teachable_skill_gap=skill_gap,
        practicality=practicality,
        recommendation_policy=_recommendation_policy(practicality, findability, skill_gap),
    )


def _findability(
    probability: float | None,
    plus_400_probability: float | None,
    evidence_source: str | None,
    board: chess.Board,
    move: chess.Move,
    situation: TimeSituation,
) -> tuple[FindabilityLabel, str, str, bool]:
    if probability is None:
        return "unknown", evidence_source or "unknown", "none", False

    label = _base_findability(probability)
    if move in board.legal_moves and _is_forcing_move(board, move):
        label = _improve_findability(label)
    if situation in {"low_time", "time_scramble"}:
        label = _worsen_findability(label)

    skill_gap = _teachable_skill_gap(probability, plus_400_probability)
    confidence = "model_time_adjusted" if situation != "unknown" else "model"
    return label, evidence_source or "human_probability", confidence, skill_gap


def _base_findability(probability: float) -> FindabilityLabel:
    if probability >= 0.30:
        return "obvious"
    if probability >= 0.12:
        return "findable"
    if probability >= 0.04:
        return "hard"
    if probability >= 0.01:
        return "very_hard"
    return "engine_like"


def _is_forcing_move(board: chess.Board, move: chess.Move) -> bool:
    return board.gives_check(move) or board.is_capture(move) or move.promotion is not None


def _teachable_skill_gap(probability: float, plus_400_probability: float | None) -> bool:
    if plus_400_probability is None:
        return False
    return plus_400_probability >= 0.12 and plus_400_probability - probability >= 0.08


def _worsen_findability(label: FindabilityLabel) -> FindabilityLabel:
    if label not in FINDABILITY_STEPS:
        return label
    return FINDABILITY_STEPS[min(FINDABILITY_STEPS.index(label) + 1, len(FINDABILITY_STEPS) - 1)]


def _improve_findability(label: FindabilityLabel) -> FindabilityLabel:
    if label not in FINDABILITY_STEPS:
        return label
    return FINDABILITY_STEPS[max(FINDABILITY_STEPS.index(label) - 1, 0)]


def _practicality(
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


def _recommendation_policy(
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


def _candidate_sort_key(candidate: CandidateMove) -> tuple[int, int, int]:
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


def _recommendation_sort_key(candidate: CandidateMove) -> tuple[int, float]:
    score_loss = (
        candidate.score_loss_vs_best_cp if candidate.score_loss_vs_best_cp is not None else 99_999
    )
    probability = candidate.player_level_probability or 0
    return score_loss, -probability


def _append_role(roles: list[CandidateRole], role: CandidateRole) -> list[CandidateRole]:
    return roles if role in roles else [*roles, role]


def _roles_with_human_likelihood(
    roles: list[CandidateRole], human_likelihood: HumanMoveLikelihood | None
) -> list[CandidateRole]:
    if human_likelihood and (
        human_likelihood.is_top_human_move or _is_human_common(human_likelihood)
    ):
        return _append_role(roles, "human_common_move")
    return roles


def _is_human_common(human_likelihood: HumanMoveLikelihood) -> bool:
    return (
        human_likelihood.player_level_probability is not None
        and human_likelihood.player_level_probability >= 0.30
    )
