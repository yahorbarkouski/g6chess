"""Deterministic context heuristics."""

from __future__ import annotations

from dataclasses import replace

import chess

from g6explanation.context_engine.models import (
    CandidateMove,
    EngineAnalysis,
    EngineLine,
    HumanMoveStats,
    MainPoint,
    MoveContextRequest,
    MoveFacts,
    MoveQuality,
    Score,
)

BAD_QUALITY_LABELS = {"inaccuracy", "mistake", "blunder", "missed_win"}
FINDABILITY_ORDER = ["obvious", "findable", "hard", "very_hard", "engine_like", "unknown"]


def score_as_cp(score: Score) -> int:
    if score.kind == "cp":
        if score.value is None:
            raise ValueError("Centipawn score is missing value.")
        return score.value
    if score.mate_for == "player":
        return 100_000
    return -100_000


def classify_quality(analysis: EngineAnalysis, played: MoveFacts) -> MoveQuality:
    best = analysis.top_lines[0]
    best_cp = score_as_cp(best.score)
    played_cp = score_as_cp(analysis.played_line.score)
    loss = best_cp - played_cp
    delta = played_cp - best_cp

    if (
        analysis.played_line.score.kind == "mate"
        and analysis.played_line.score.mate_for == "opponent"
    ):
        label = "blunder"
    elif (
        best.score.kind == "mate"
        and best.score.mate_for == "player"
        and played.uci != best.move_uci
    ):
        label = "missed_win"
    elif played.uci == best.move_uci:
        label = "best"
    elif loss <= 20:
        label = "excellent"
    elif loss <= 50:
        label = "good"
    elif loss <= 70:
        label = "neutral"
    elif loss <= 150:
        label = "inaccuracy"
    elif loss <= 300:
        label = "mistake"
    else:
        label = "blunder"

    return MoveQuality(
        label=label,
        score_delta_cp_player_pov=None
        if best.score.kind == "mate" or analysis.played_line.score.kind == "mate"
        else delta,
        score_loss_vs_best_cp=None
        if best.score.kind == "mate" or analysis.played_line.score.kind == "mate"
        else loss,
        severity_text=_severity_text(best.score, analysis.played_line.score),
    )


def build_candidates(
    board: chess.Board,
    analysis: EngineAnalysis,
    human_stats: dict[str, HumanMoveStats],
    request: MoveContextRequest,
    time_situation: str,
) -> list[CandidateMove]:
    best_cp = score_as_cp(analysis.top_lines[0].score)
    best_move_uci = analysis.top_lines[0].move_uci
    candidates: dict[str, CandidateMove] = {}

    for line in analysis.top_lines:
        roles = ["engine_best"] if line.move_uci == best_move_uci else ["close_engine_alternative"]
        candidates[line.move_uci] = _candidate_from_line(
            line=line,
            roles=roles,
            best_cp=best_cp,
            human_stats=human_stats.get(line.move_uci),
            board=board,
            request=request,
            time_situation=time_situation,
        )

    if analysis.played_line.move_uci in candidates:
        existing = candidates[analysis.played_line.move_uci]
        candidates[analysis.played_line.move_uci] = replace(
            existing,
            roles=_append_role(existing.roles, "played_move"),
        )
    else:
        candidates[analysis.played_line.move_uci] = _candidate_from_line(
            line=analysis.played_line,
            roles=["played_move"],
            best_cp=best_cp,
            human_stats=human_stats.get(analysis.played_line.move_uci),
            board=board,
            request=request,
            time_situation=time_situation,
        )

    return sorted(candidates.values(), key=lambda candidate: _candidate_sort_key(candidate))


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
        return sorted(practical, key=lambda c: c.score_loss_vs_best_cp or 0)[0]

    for candidate in candidates:
        if "engine_best" in candidate.roles:
            return candidate
    return None


def build_main_point(
    board: chess.Board,
    played: MoveFacts,
    quality: MoveQuality,
    key_candidate: CandidateMove | None,
    analysis: EngineAnalysis,
) -> MainPoint:
    if key_candidate is None:
        return MainPoint(
            concept="move quality",
            claim=(
                f"{played.san} was {article(quality.label)} {quality.label} "
                "and did not require a sharper alternative."
            ),
        )

    key_move = chess.Move.from_uci(key_candidate.uci)
    if key_move in board.legal_moves and board.gives_check(key_move):
        return MainPoint(
            concept="forcing moves before quiet moves",
            claim=(
                f"{played.san} was {article(quality.label)} {quality.label}; "
                f"{key_candidate.san} was the key forcing check."
            ),
        )

    if analysis.after_line is not None:
        return MainPoint(
            concept="opponent resource",
            claim=(
                f"{played.san} was {article(quality.label)} {quality.label} "
                f"because it let the opponent improve with {analysis.after_line.move_san}."
            ),
        )

    return MainPoint(
        concept="better alternative",
        claim=(
            f"{played.san} was {article(quality.label)} {quality.label}; "
            f"{key_candidate.san} was the better move."
        ),
    )


def build_allowed_claims(
    played: MoveFacts,
    quality: MoveQuality,
    key_candidate: CandidateMove | None,
    analysis: EngineAnalysis,
) -> list[str]:
    claims = [f"{played.san} was {article(quality.label)} {quality.label}"]
    if key_candidate:
        claims.append(f"{key_candidate.san} was the key alternative")
        if key_candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
            claims.append(f"{key_candidate.san} was hard to find")
    if analysis.after_line:
        claims.append(
            f"the opponent's key reply after {played.san} was {analysis.after_line.move_san}"
        )
    return claims


def build_human_note(key_candidate: CandidateMove | None, time_situation: str) -> str | None:
    if key_candidate is None:
        return None
    if key_candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
        time_phrase = (
            "" if time_situation == "unknown" else f" in {time_situation.replace('_', ' ')}"
        )
        return (
            f"This move was {key_candidate.time_adjusted_findability} to find{time_phrase}; "
            "the useful lesson is the idea, not that it was obvious."
        )
    return None


def time_situation(request: MoveContextRequest) -> str:
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


def article(label: str) -> str:
    return "an" if label[0].lower() in {"a", "e", "i", "o", "u"} else "a"


def _candidate_from_line(
    line: EngineLine,
    roles: list[str],
    best_cp: int,
    human_stats: HumanMoveStats | None,
    board: chess.Board,
    request: MoveContextRequest,
    time_situation: str,
) -> CandidateMove:
    score_cp = score_as_cp(line.score)
    score_loss = best_cp - score_cp
    probability = human_stats.player_level_probability if human_stats else None
    plus_400_probability = human_stats.plus_400_probability if human_stats else None
    findability = _findability(probability, time_situation)
    practicality = _practicality(roles, score_loss, findability)
    return CandidateMove(
        san=line.move_san,
        uci=line.move_uci,
        roles=roles,
        engine_rank=line.rank,
        score=line.score,
        score_loss_vs_best_cp=None if line.score.kind == "mate" else score_loss,
        pv_short_san=(line.pv_san or [])[:3],
        player_level_probability=probability,
        plus_400_probability=plus_400_probability,
        time_adjusted_findability=findability,
        practicality=practicality,
        recommendation_policy=_recommendation_policy(practicality),
    )


def _findability(probability: float | None, situation: str) -> str:
    if probability is None:
        return "unknown"
    if probability >= 0.30:
        label = "obvious"
    elif probability >= 0.12:
        label = "findable"
    elif probability >= 0.04:
        label = "hard"
    elif probability >= 0.01:
        label = "very_hard"
    else:
        label = "engine_like"

    if situation in {"low_time", "time_scramble"}:
        label = _worsen_findability(label)
    return label


def _worsen_findability(label: str) -> str:
    order = ["obvious", "findable", "hard", "very_hard", "engine_like"]
    if label not in order:
        return label
    return order[min(order.index(label) + 1, len(order) - 1)]


def _practicality(roles: list[str], score_loss: int, findability: str) -> str:
    if "played_move" in roles:
        return "unknown_practicality"
    if findability in {"hard", "very_hard", "engine_like"}:
        return "hard_but_important" if "engine_best" in roles else "engine_benchmark"
    if "engine_best" in roles:
        return (
            "clear_recommendation"
            if findability in {"obvious", "findable", "unknown"}
            else "hard_but_important"
        )
    if score_loss <= 50 and findability in {"obvious", "findable"}:
        return "practical_try"
    if score_loss <= 50:
        return "unknown_practicality"
    return "engine_benchmark"


def _recommendation_policy(practicality: str) -> str:
    if practicality == "clear_recommendation":
        return "recommend_directly"
    if practicality == "practical_try":
        return "use_as_practical_alternative"
    if practicality == "hard_but_important":
        return "mention_with_caveat"
    return "do_not_recommend"


def _candidate_sort_key(candidate: CandidateMove) -> tuple[int, int]:
    role_rank = 0 if "engine_best" in candidate.roles else 1
    return (
        role_rank,
        candidate.score_loss_vs_best_cp if candidate.score_loss_vs_best_cp is not None else 99_999,
    )


def _append_role(roles: list[str], role: str) -> list[str]:
    return roles if role in roles else [*roles, role]


def _severity_text(best: Score, played: Score) -> str:
    if best.kind == "mate" or played.kind == "mate":
        if played.kind == "mate" and played.mate_for == "opponent":
            return "the move allowed a forced mate against the player"
        if best.kind == "mate" and best.mate_for == "player":
            return "the best line had a forced mate for the player"
        return "the move changed a forced-mate evaluation"
    return f"from {_score_band(score_as_cp(best))} to {_score_band(score_as_cp(played))}"


def _score_band(cp: int) -> str:
    if cp >= 300:
        return "winning"
    if cp >= 150:
        return "clearly better"
    if cp >= 50:
        return "slightly better"
    if cp > -50:
        return "roughly equal"
    if cp > -150:
        return "slightly worse"
    if cp > -300:
        return "clearly worse"
    return "losing"
