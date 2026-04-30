"""Deterministic context heuristics."""

from __future__ import annotations

import chess

from g6explanation.context_engine.models import (
    CandidateMove,
    EngineAnalysis,
    EngineLine,
    FindabilityLabel,
    HumanMoveStats,
    MainPoint,
    MoveContextRequest,
    MoveFacts,
    MoveQuality,
    MoveQualityLabel,
    MoveSignificance,
    PracticalityCategory,
    RecommendationPolicy,
    Score,
    SignificanceLabel,
    Wdl,
)

BAD_QUALITY_LABELS = {"inaccuracy", "mistake", "blunder", "missed_win"}
FINDABILITY_ORDER: list[FindabilityLabel] = [
    "obvious",
    "findable",
    "hard",
    "very_hard",
    "engine_like",
    "unknown",
]
QUALITY_ORDER: dict[MoveQualityLabel, int] = {
    "best": 0,
    "excellent": 1,
    "good": 2,
    "neutral": 3,
    "inaccuracy": 4,
    "mistake": 5,
    "blunder": 6,
    "missed_win": 6,
}


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
    played_line = analysis.played_line
    cp_loss = _score_loss_cp(best.score, played_line.score)
    wdl_delta = _wdl_delta(best.wdl, played_line.wdl)
    wdl_loss = _wdl_expected_score_loss(best.wdl, played_line.wdl)

    if played_line.score.kind == "mate" and played_line.score.mate_for == "opponent":
        label: MoveQualityLabel = "blunder"
    elif (
        best.score.kind == "mate"
        and best.score.mate_for == "player"
        and not _is_player_mate(played_line.score)
    ):
        label = "missed_win"
    elif played.uci == best.move_uci:
        label = "best"
    else:
        cp_label = _label_from_cp_loss(cp_loss)
        wdl_label = _label_from_wdl_loss(wdl_loss)
        label = _worse_label(cp_label, wdl_label)

    return MoveQuality(
        label=label,
        score_delta_cp_player_pov=None if cp_loss is None else -cp_loss,
        score_loss_vs_best_cp=cp_loss,
        wdl_delta_player_pov=wdl_delta,
        wdl_expected_score_loss=wdl_loss,
        severity_text=_severity_text(best.score, played_line.score, cp_loss, wdl_loss),
    )


def calculate_significance(analysis: EngineAnalysis, played: MoveFacts) -> MoveSignificance:
    """Measure how much this move deserves emphasis relative to alternatives."""

    if _has_mate_transition(analysis):
        return MoveSignificance(label="critical", score=1.0)

    reference = _significance_reference_line(analysis, played)
    if reference is None:
        return MoveSignificance(label="low", score=0.0)

    played_line = analysis.played_line
    cp_gap = _absolute_cp_gap(played_line.score, reference.score)
    wdl_gap = _absolute_wdl_expected_gap(played_line.wdl, reference.wdl)

    cp_score = 0.0 if cp_gap is None else _clamp(cp_gap / 300)
    wdl_score = 0.0 if wdl_gap is None else _clamp(wdl_gap / 180)
    score = round(max(cp_score, wdl_score), 2)
    return MoveSignificance(label=_significance_label(score), score=score)


def build_candidates(
    board: chess.Board,
    analysis: EngineAnalysis,
    human_stats: dict[str, HumanMoveStats],
    request: MoveContextRequest,
    time_situation: str,
    supplemental_lines: list[EngineLine] | None = None,
) -> list[CandidateMove]:
    best = analysis.top_lines[0]
    best_cp = score_as_cp(best.score)
    best_move_uci = best.move_uci
    candidates: dict[str, CandidateMove] = {}

    for line in analysis.top_lines:
        score_loss = _line_score_loss(best_cp, line)
        roles = ["engine_best"] if line.move_uci == best_move_uci else ["close_engine_alternative"]
        if score_loss is not None and score_loss <= 50 and "engine_best" not in roles:
            roles.append("practical_alternative")
        candidates[line.move_uci] = _candidate_from_line(
            line=line,
            roles=_roles_with_human_stats(roles, human_stats.get(line.move_uci)),
            best_cp=best_cp,
            human_stats=human_stats.get(line.move_uci),
            board=board,
            request=request,
            time_situation=time_situation,
        )

    for line in supplemental_lines or []:
        if line.move_uci in candidates:
            continue
        score_loss = _line_score_loss(best_cp, line)
        roles = ["human_common_move"]
        if score_loss is not None and score_loss <= 50:
            roles.append("practical_alternative")
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
        candidates[analysis.played_line.move_uci] = existing.model_copy(
            update={"roles": _append_role(existing.roles, "played_move")}
        )
    else:
        candidates[analysis.played_line.move_uci] = _candidate_from_line(
            line=analysis.played_line,
            roles=_roles_with_human_stats(
                ["played_move"], human_stats.get(analysis.played_line.move_uci)
            ),
            best_cp=best_cp,
            human_stats=human_stats.get(analysis.played_line.move_uci),
            board=board,
            request=request,
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


def build_main_point(
    board: chess.Board,
    played: MoveFacts,
    quality: MoveQuality,
    key_candidate: CandidateMove | None,
    analysis: EngineAnalysis,
) -> MainPoint:
    quality_claim = build_quality_claim(played, quality)
    if key_candidate is None:
        if quality.label == "best":
            return MainPoint(
                concept="move quality",
                claim=f"{quality_claim}; no sharper alternative is needed for this moment.",
            )
        return MainPoint(
            concept="move quality",
            claim=f"{quality_claim}; it did not lose meaningful value versus the engine choice.",
        )

    key_move = chess.Move.from_uci(key_candidate.uci)
    if key_candidate.practicality == "practical_try":
        return MainPoint(
            concept="practical alternative",
            claim=(
                f"{quality_claim}; {key_candidate.san} was a practical alternative "
                "close to the engine best move."
            ),
        )

    if key_move in board.legal_moves and board.gives_check(key_move):
        return MainPoint(
            concept="forcing moves before quiet moves",
            claim=f"{quality_claim}; {key_candidate.san} was the key forcing check.",
        )

    if analysis.after_line is not None and quality.label in BAD_QUALITY_LABELS:
        return MainPoint(
            concept="opponent resource",
            claim=(
                f"{quality_claim} because it let the opponent improve with "
                f"{analysis.after_line.move_san}."
            ),
        )

    return MainPoint(
        concept="better alternative",
        claim=f"{quality_claim}; {key_candidate.san} was the better move.",
    )


def build_allowed_claims(
    played: MoveFacts,
    quality: MoveQuality,
    key_candidate: CandidateMove | None,
    analysis: EngineAnalysis,
) -> list[str]:
    claims = [build_quality_claim(played, quality)]
    if key_candidate:
        claims.append(f"{key_candidate.san} was the key alternative")
        if key_candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
            claims.append(f"{key_candidate.san} was hard to find")
        if key_candidate.teachable_skill_gap:
            claims.append(f"{key_candidate.san} becomes more common at stronger levels")
        if key_candidate.practicality == "practical_try":
            claims.append(f"{key_candidate.san} was a practical alternative")
    if analysis.after_line and quality.label in BAD_QUALITY_LABELS:
        claims.append(
            f"the opponent's key reply after {played.san} was {analysis.after_line.move_san}"
        )
    return list(dict.fromkeys(claims))


def build_human_note(key_candidate: CandidateMove | None, time_situation: str) -> str | None:
    if key_candidate is None:
        return None
    if key_candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
        time_phrase = (
            "" if time_situation == "unknown" else f" in {time_situation.replace('_', ' ')}"
        )
        if key_candidate.teachable_skill_gap:
            return (
                f"{key_candidate.san} was {key_candidate.time_adjusted_findability} to find"
                f"{time_phrase}, but it becomes more common for stronger players; the useful "
                "lesson is the idea, not that it was obvious."
            )
        return (
            f"{key_candidate.san} was {key_candidate.time_adjusted_findability} to find"
            f"{time_phrase}; the useful lesson is the idea, not that it was obvious."
        )
    if key_candidate.teachable_skill_gap:
        return (
            f"{key_candidate.san} is a teachable upgrade: it is more common for stronger "
            "players while still realistic enough to mention."
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


def build_quality_claim(played: MoveFacts, quality: MoveQuality) -> str:
    if quality.label == "best":
        return f"{played.san} was the best move"
    if quality.label == "missed_win":
        return f"{played.san} missed a winning move"
    return f"{played.san} was {article(quality.label)} {quality.label}"


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
    score_loss = _line_score_loss(best_cp, line)
    probability = human_stats.player_level_probability if human_stats else None
    plus_400_probability = human_stats.plus_400_probability if human_stats else None
    move = chess.Move.from_uci(line.move_uci)
    findability, source, confidence, skill_gap = _findability(
        probability=probability,
        plus_400_probability=plus_400_probability,
        evidence_source=human_stats.evidence_source if human_stats else None,
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
        human_rank=human_stats.rank if human_stats else None,
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
    situation: str,
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
    order = ["obvious", "findable", "hard", "very_hard", "engine_like"]
    if label not in order:
        return label
    return order[min(order.index(label) + 1, len(order) - 1)]  # type: ignore[return-value]


def _improve_findability(label: FindabilityLabel) -> FindabilityLabel:
    order = ["obvious", "findable", "hard", "very_hard", "engine_like"]
    if label not in order:
        return label
    return order[max(order.index(label) - 1, 0)]  # type: ignore[return-value]


def _practicality(
    roles: list[str], score_loss: int | None, findability: FindabilityLabel
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


def _append_role(roles: list[str], role: str) -> list[str]:
    return roles if role in roles else [*roles, role]


def _roles_with_human_stats(roles: list[str], human_stats: HumanMoveStats | None) -> list[str]:
    if human_stats and (human_stats.is_top_human_move or _is_human_common(human_stats)):
        return _append_role(roles, "human_common_move")
    return roles


def _is_human_common(human_stats: HumanMoveStats) -> bool:
    return (
        human_stats.player_level_probability is not None
        and human_stats.player_level_probability >= 0.30
    )


def _line_score_loss(best_cp: int, line: EngineLine) -> int | None:
    if line.score.kind == "mate":
        return None
    return max(0, best_cp - score_as_cp(line.score))


def _score_loss_cp(best: Score, played: Score) -> int | None:
    if best.kind == "mate" or played.kind == "mate":
        return None
    return max(0, score_as_cp(best) - score_as_cp(played))


def _wdl_delta(best: Wdl | None, played: Wdl | None) -> Wdl | None:
    if best is None or played is None:
        return None
    return Wdl(
        win=played.win - best.win,
        draw=played.draw - best.draw,
        loss=played.loss - best.loss,
    )


def _wdl_expected_score_loss(best: Wdl | None, played: Wdl | None) -> int | None:
    if best is None or played is None:
        return None
    return max(0, _wdl_expected_score(best) - _wdl_expected_score(played))


def _wdl_expected_score(wdl: Wdl) -> int:
    return round(wdl.win + (wdl.draw * 0.5))


def _label_from_cp_loss(loss: int | None) -> MoveQualityLabel:
    if loss is None:
        return "neutral"
    if loss <= 20:
        return "excellent"
    if loss <= 50:
        return "good"
    if loss <= 90:
        return "neutral"
    if loss <= 150:
        return "inaccuracy"
    if loss <= 300:
        return "mistake"
    return "blunder"


def _label_from_wdl_loss(loss: int | None) -> MoveQualityLabel:
    if loss is None:
        return "neutral"
    if loss <= 10:
        return "excellent"
    if loss <= 25:
        return "good"
    if loss <= 45:
        return "neutral"
    if loss <= 80:
        return "inaccuracy"
    if loss <= 150:
        return "mistake"
    return "blunder"


def _worse_label(left: MoveQualityLabel, right: MoveQualityLabel) -> MoveQualityLabel:
    return left if QUALITY_ORDER[left] >= QUALITY_ORDER[right] else right


def _is_player_mate(score: Score) -> bool:
    return score.kind == "mate" and score.mate_for == "player"


def _has_mate_transition(analysis: EngineAnalysis) -> bool:
    best = analysis.top_lines[0].score
    played = analysis.played_line.score
    if best.kind == "mate" and best.mate_for == "player" and not _is_player_mate(played):
        return True
    return played.kind == "mate" and played.mate_for == "opponent"


def _significance_reference_line(analysis: EngineAnalysis, played: MoveFacts) -> EngineLine | None:
    if played.uci != analysis.top_lines[0].move_uci:
        return analysis.top_lines[0]
    return next(
        (line for line in analysis.top_lines[1:] if line.move_uci != played.uci),
        None,
    )


def _absolute_cp_gap(left: Score, right: Score) -> int | None:
    if left.kind == "mate" or right.kind == "mate":
        return None
    return abs(score_as_cp(left) - score_as_cp(right))


def _absolute_wdl_expected_gap(left: Wdl | None, right: Wdl | None) -> int | None:
    if left is None or right is None:
        return None
    return abs(_wdl_expected_score(left) - _wdl_expected_score(right))


def _significance_label(score: float) -> SignificanceLabel:
    if score >= 0.65:
        return "critical"
    if score >= 0.35:
        return "high"
    if score >= 0.15:
        return "moderate"
    return "low"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _severity_text(
    best: Score,
    played: Score,
    cp_loss: int | None,
    wdl_loss: int | None,
) -> str:
    if best.kind == "mate" or played.kind == "mate":
        if played.kind == "mate" and played.mate_for == "opponent":
            return "the move allowed a forced mate against the player"
        if best.kind == "mate" and best.mate_for == "player":
            return "the best line had a forced mate for the player"
        return "the move changed a forced-mate evaluation"
    text = f"from {_score_band(score_as_cp(best))} to {_score_band(score_as_cp(played))}"
    if wdl_loss is not None and wdl_loss > 45:
        return f"{text}, with expected score dropping by {wdl_loss}/1000"
    if cp_loss is not None:
        return f"{text}, losing {cp_loss} centipawns versus the best move"
    return text


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
