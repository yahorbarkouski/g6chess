"""Candidate move construction from engine and human-likelihood evidence."""

from __future__ import annotations

import chess

from g6explanation.context_engine.candidate_moves.findability import assess_findability
from g6explanation.context_engine.candidate_moves.recommendation import (
    practicality,
    recommendation_policy,
)
from g6explanation.context_engine.candidate_moves.selection import candidate_sort_key
from g6explanation.context_engine.contracts import (
    CandidateMove,
    CandidateRole,
    EngineAnalysis,
    EngineLine,
    HumanMoveLikelihood,
    MoveContextRequest,
    TimeSituation,
)
from g6explanation.context_engine.signals.score_comparison import line_score_loss, score_as_cp


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

    return sorted(candidates.values(), key=candidate_sort_key)


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
    findability, source, confidence, skill_gap = assess_findability(
        probability=probability,
        plus_400_probability=plus_400_probability,
        evidence_source=human_likelihood.evidence_source if human_likelihood else None,
        board=board,
        move=move,
        situation=time_situation,
    )
    candidate_practicality = practicality(roles, score_loss, findability)
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
        practicality=candidate_practicality,
        recommendation_policy=recommendation_policy(candidate_practicality, findability, skill_gap),
    )


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
