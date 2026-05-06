"""LLM-facing explanation agenda construction."""

from __future__ import annotations

import chess

from g6explanation.context_engine.concept_evidence import (
    build_immediate_material_punishment_claims,
    build_material_sacrifice_claims,
    build_move_concept_claims,
    build_tactical_objection_claims,
    immediate_material_punishment,
    verified_material_sacrifice,
)
from g6explanation.context_engine.contracts import (
    CandidateMove,
    ConceptClaim,
    ConceptClaimSubject,
    EngineAnalysis,
    KeyMoveContext,
    MainPoint,
    MoveBeauty,
    MoveQuality,
    PlayedMoveFacts,
    TimeSituation,
)
from g6explanation.context_engine.signals.quality import BAD_QUALITY_LABELS


def build_main_point(
    board: chess.Board,
    played: PlayedMoveFacts,
    quality: MoveQuality,
    key_candidate: CandidateMove | None,
    featured_candidate: CandidateMove | None,
    analysis: EngineAnalysis,
    beauty: MoveBeauty,
) -> MainPoint:
    quality_claim = build_quality_claim(played, quality)
    if quality.label == "forced":
        return MainPoint(
            concept="forced move",
            claim=f"{quality_claim}; the player had no legal alternative.",
        )
    if quality.label in BAD_QUALITY_LABELS and (
        punishment := immediate_material_punishment(board, played.uci, played.san, analysis)
    ):
        return MainPoint(
            concept="material loss",
            claim=(
                f"{quality_claim} because it hung the {punishment.piece_name} "
                f"to {punishment.reply_san}."
            ),
        )
    if quality.label in {"best", "excellent", "good"} and (
        sacrifice := verified_material_sacrifice(board, played.uci, played.san, analysis)
    ):
        adjective = "brilliant " if beauty.label == "brilliant" else ""
        return MainPoint(
            concept=f"{sacrifice.piece_name} sacrifice",
            claim=(
                f"{played.san} set up a {adjective}{sacrifice.piece_name} "
                f"sacrifice on {sacrifice.square_name}."
            ),
        )
    if key_candidate is None:
        if quality.label == "best" and featured_candidate is not None:
            return MainPoint(
                concept=_featured_best_concept(board, played, analysis),
                claim=_featured_best_claim(played, quality_claim, analysis, board),
            )
        if quality.label == "best":
            return MainPoint(
                concept="move purpose",
                claim=_non_bad_quality_claim(board, played, quality, analysis),
            )
        if quality.label in {"excellent", "good", "neutral"}:
            return MainPoint(
                concept="move purpose",
                claim=_non_bad_quality_claim(board, played, quality, analysis),
            )
        return MainPoint(
            concept="move quality",
            claim=f"{quality_claim}; it did not give up meaningful value.",
        )

    key_move = chess.Move.from_uci(key_candidate.uci)
    if key_candidate.practicality == "practical_try":
        return MainPoint(
            concept="practical alternative",
            claim=(
                f"{quality_claim}; {key_candidate.san} was a practical alternative "
                "that stayed close to best play."
            ),
        )

    if key_move in board.legal_moves and board.gives_check(key_move):
        return MainPoint(
            concept="forcing moves before quiet moves",
            claim=f"{quality_claim}; {key_candidate.san} would have been the key forcing check.",
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
        claim=f"{quality_claim}; {key_candidate.san} would have been better.",
    )


def build_allowed_claims(
    board: chess.Board,
    played: PlayedMoveFacts,
    quality: MoveQuality,
    key_candidate: CandidateMove | None,
    featured_candidate: CandidateMove | None,
    analysis: EngineAnalysis,
) -> list[str]:
    claims = [_allowed_quality_claim(board, played, quality, analysis)]
    punishment = (
        immediate_material_punishment(board, played.uci, played.san, analysis)
        if quality.label in BAD_QUALITY_LABELS
        else None
    )
    if punishment is not None:
        claims.append(punishment.played_loss_claim)
    if quality.label in {"best", "excellent", "good"} and (
        sacrifice := verified_material_sacrifice(board, played.uci, played.san, analysis)
    ):
        claims.append(sacrifice.sacrifice_claim)
        claims.append(sacrifice.material_claim)
    if key_candidate:
        claims.append(f"{key_candidate.san} would have been the key alternative")
        if key_candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
            claims.append(f"{key_candidate.san} was hard to find")
        if key_candidate.teachable_skill_gap:
            claims.append(f"{key_candidate.san} becomes more common at stronger levels")
        if key_candidate.practicality == "practical_try":
            claims.append(f"{key_candidate.san} was a practical alternative")
    if featured_candidate and not key_candidate:
        claims.append(f"{featured_candidate.san} was the key move")
    if analysis.after_line and quality.label in BAD_QUALITY_LABELS and punishment is None:
        claims.append(
            f"the opponent's key reply after {played.san} was {analysis.after_line.move_san}"
        )
    return list(dict.fromkeys(claims))


def build_concept_claims(
    board: chess.Board,
    played: PlayedMoveFacts,
    quality: MoveQuality,
    key_candidate: CandidateMove | None,
    featured_candidate: CandidateMove | None,
    engine_best_candidate: CandidateMove | None,
    practical_alternative: CandidateMove | None,
    analysis: EngineAnalysis,
) -> list[ConceptClaim]:
    quality_claim = build_quality_claim(played, quality)
    claims = [
        ConceptClaim(
            kind="move_quality",
            subject="played_move",
            claim=quality_claim,
            source="quality_classification",
            move_san=played.san,
        )
    ]
    material_punishment_claims = (
        build_immediate_material_punishment_claims(board, played.uci, played.san, analysis)
        if quality.label in BAD_QUALITY_LABELS
        else []
    )
    claims.extend(material_punishment_claims)
    sacrifice_claims = (
        build_material_sacrifice_claims(board, played.uci, played.san, analysis)
        if quality.label in {"best", "excellent", "good"}
        else []
    )
    claims.extend(sacrifice_claims)
    played_sacrifice_is_main_point = bool(sacrifice_claims)

    if quality.label == "forced":
        claims.append(
            ConceptClaim(
                kind="forced_move",
                subject="played_move",
                claim=f"{quality_claim}; the player had no legal alternative.",
                source="legal_move_count",
                move_san=played.san,
            )
        )
    if "forced mate" in quality.severity_text:
        claims.append(
            ConceptClaim(
                kind="forced_mate",
                subject="position",
                claim=quality.severity_text,
                source="quality_classification",
                move_san=played.san,
            )
        )
    if played.is_capture:
        claims.append(
            ConceptClaim(
                kind="capture",
                subject="played_move",
                claim=f"{played.san} was a capture",
                source="played_move_fact",
                move_san=played.san,
            )
        )
    played_move = chess.Move.from_uci(played.uci)
    if played_move in board.legal_moves and board.is_castling(played_move):
        claims.append(
            ConceptClaim(
                kind="castling",
                subject="played_move",
                claim=f"{played.san} was castling",
                source="played_move_fact",
                move_san=played.san,
            )
        )
    if played_move in board.legal_moves and board.is_en_passant(played_move):
        claims.append(
            ConceptClaim(
                kind="en_passant",
                subject="played_move",
                claim=f"{played.san} was an en passant capture",
                source="played_move_fact",
                move_san=played.san,
            )
        )
    if played.promotion is not None:
        claims.append(
            ConceptClaim(
                kind="promotion",
                subject="played_move",
                claim=f"{played.san} promoted to {played.promotion}",
                source="played_move_fact",
                move_san=played.san,
            )
        )
    if played.is_check:
        claims.append(
            ConceptClaim(
                kind="initiative",
                subject="played_move",
                claim=f"{played.san} forced the opponent to respond to check",
                source="played_move_fact",
                move_san=played.san,
            )
        )
    if quality.label in BAD_QUALITY_LABELS and "forced mate against the player" in (
        quality.severity_text
    ):
        claims.append(
            ConceptClaim(
                kind="king_safety",
                subject="position",
                claim=f"{played.san} left the king vulnerable to forced mate",
                source="quality_classification",
                move_san=played.san,
            )
        )
    claims.extend(
        build_move_concept_claims(
            board,
            played.uci,
            played.san,
            "played_move",
            line_pv_uci=analysis.played_line.pv_uci,
        )
    )
    claims.extend(build_tactical_objection_claims(board, played.uci, played.san, analysis))

    if featured_candidate is not None:
        claims.extend(
            _featured_concept_claims(
                board,
                played,
                quality,
                quality_claim,
                featured_candidate,
                analysis,
            )
        )
        if not (played_sacrifice_is_main_point and featured_candidate.uci == played.uci):
            claims.extend(_candidate_policy_concept_claims(featured_candidate, "featured_move"))
        claims.extend(
            build_move_concept_claims(
                board,
                featured_candidate.uci,
                featured_candidate.san,
                "featured_move",
                line_pv_uci=_line_pv_for_move(analysis, featured_candidate.uci),
            )
        )

    if engine_best_candidate is not None:
        if not (played_sacrifice_is_main_point and engine_best_candidate.uci == played.uci):
            claims.extend(
                _candidate_policy_concept_claims(engine_best_candidate, "engine_best_move")
            )
        claims.extend(
            build_move_concept_claims(
                board,
                engine_best_candidate.uci,
                engine_best_candidate.san,
                "engine_best_move",
                line_pv_uci=_line_pv_for_move(analysis, engine_best_candidate.uci),
            )
        )

    if practical_alternative is not None:
        claims.append(
            ConceptClaim(
                kind="practical_alternative",
                subject="practical_alternative",
                claim=f"{practical_alternative.san} was a practical alternative",
                source="candidate_policy",
                move_san=practical_alternative.san,
            )
        )
        claims.extend(
            _candidate_policy_concept_claims(practical_alternative, "practical_alternative")
        )
        claims.extend(
            build_move_concept_claims(
                board,
                practical_alternative.uci,
                practical_alternative.san,
                "practical_alternative",
                line_pv_uci=_line_pv_for_move(analysis, practical_alternative.uci),
            )
        )

    if key_candidate is not None:
        claims.extend(_key_candidate_concept_claims(board, key_candidate, analysis))

    if (
        analysis.after_line is not None
        and quality.label in BAD_QUALITY_LABELS
        and not material_punishment_claims
    ):
        claims.append(
            ConceptClaim(
                kind="opponent_resource",
                subject="opponent_reply",
                claim=(
                    f"the opponent's key reply after {played.san} was "
                    f"{analysis.after_line.move_san}"
                ),
                source="engine_line",
                move_san=analysis.after_line.move_san,
            )
        )

    return _unique_concept_claims(claims)


def build_human_note(
    key_candidate: CandidateMove | None, time_situation: TimeSituation
) -> str | None:
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


def build_key_move_context(candidate: CandidateMove | None) -> KeyMoveContext | None:
    if candidate is None:
        return None
    return KeyMoveContext(
        move=candidate.san,
        practicality=candidate.practicality,
        findability=candidate.time_adjusted_findability,
        reason=_key_move_reason(candidate),
        recommendation_policy=candidate.recommendation_policy,
    )


def build_quality_claim(played: PlayedMoveFacts, quality: MoveQuality) -> str:
    if quality.label == "best":
        return f"{played.san} was the best move"
    if quality.label == "forced":
        return f"{played.san} was forced"
    if quality.label == "missed_win":
        return f"{played.san} missed a winning move"
    if quality.label in {"excellent", "good", "neutral"}:
        return f"{played.san} was {quality.label}"
    return f"{played.san} was {article(quality.label)} {quality.label}"


def _allowed_quality_claim(
    board: chess.Board,
    played: PlayedMoveFacts,
    quality: MoveQuality,
    analysis: EngineAnalysis,
) -> str:
    if quality.label in BAD_QUALITY_LABELS or quality.label == "forced":
        return build_quality_claim(played, quality)
    return _non_bad_quality_claim(board, played, quality, analysis)


def _non_bad_quality_claim(
    board: chess.Board,
    played: PlayedMoveFacts,
    quality: MoveQuality,
    analysis: EngineAnalysis | None = None,
) -> str:
    if purpose_claim := _primary_played_purpose_claim(board, played, analysis):
        return purpose_claim
    if quality.label == "best":
        return f"{played.san} fits the position"
    if quality.label == "excellent":
        return f"{played.san} kept the position very strong"
    if quality.label == "good":
        return f"{played.san} kept the position solid"
    return f"{played.san} held the position"


def _primary_played_purpose_claim(
    board: chess.Board,
    played: PlayedMoveFacts,
    analysis: EngineAnalysis | None = None,
) -> str | None:
    claim = _primary_played_purpose_claim_with_kind(board, played, analysis)
    return claim[1] if claim is not None else None


def _primary_played_purpose_kind(
    board: chess.Board,
    played: PlayedMoveFacts,
    analysis: EngineAnalysis | None = None,
) -> str | None:
    claim = _primary_played_purpose_claim_with_kind(board, played, analysis)
    return claim[0] if claim is not None else None


def _primary_played_purpose_claim_with_kind(
    board: chess.Board,
    played: PlayedMoveFacts,
    analysis: EngineAnalysis | None = None,
) -> tuple[str, str] | None:
    move = chess.Move.from_uci(played.uci)
    if move not in board.legal_moves:
        return None
    if board.is_castling(move):
        return ("castling", f"{played.san} castled")
    if board.is_en_passant(move):
        return ("en_passant", f"{played.san} was an en passant capture")
    if played.promotion is not None:
        return ("promotion", f"{played.san} promoted to {played.promotion}")

    claims: list[ConceptClaim] = []
    if analysis is not None:
        claims.extend(build_material_sacrifice_claims(board, played.uci, played.san, analysis))
        claims.extend(build_tactical_objection_claims(board, played.uci, played.san, analysis))
    claims.extend(
        build_move_concept_claims(
            board,
            played.uci,
            played.san,
            "played_move",
            line_pv_uci=analysis.played_line.pv_uci if analysis is not None else None,
        )
    )
    priority: tuple[str, ...] = (
        "sacrifice",
        "tactical_proof",
        "forced_mate",
        "tactic",
        "piece_activity",
        "forcing_move",
        "recapture",
        "material",
        "center",
        "development",
        "open_file",
        "passed_pawn",
        "weak_square",
    )
    by_kind = {claim.kind: claim.claim for claim in claims}
    for kind in priority:
        if kind in by_kind:
            return (kind, by_kind[kind])
    if played.is_capture:
        return ("capture", f"{played.san} captured")
    return None


def article(label: str) -> str:
    return "an" if label[0].lower() in {"a", "e", "i", "o", "u"} else "a"


def _key_move_reason(candidate: CandidateMove) -> str:
    if candidate.score.kind == "mate" and candidate.score.mate_for == "player":
        return "it checkmates the opponent"
    if candidate.practicality == "only_move":
        return "it is the only legal move"
    if candidate.practicality == "practical_try":
        return "it stays close to best play while being more practical for the player"
    if candidate.recommendation_policy == "explain_as_hidden_resource":
        return "it is an important hidden resource that becomes more visible with stronger play"
    if candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
        return "it is objectively important but hard to find"
    if candidate.score_loss_vs_best_cp == 0:
        return "it is the strongest move in the position"
    return "it is a better practical move"


def _featured_best_concept(
    board: chess.Board,
    played: PlayedMoveFacts,
    analysis: EngineAnalysis,
) -> str:
    if (
        analysis.played_line.score.kind == "mate"
        and analysis.played_line.score.mate_for == "player"
    ):
        return "forced mate"
    primary_kind = _primary_played_purpose_kind(board, played, analysis)
    if primary_kind in {"sacrifice", "tactic", "piece_activity", "recapture", "development"}:
        return primary_kind.replace("_", " ")
    if played.is_check:
        return "forcing move"
    if played.is_capture:
        return "capture"
    return "critical move"


def _featured_best_claim(
    played: PlayedMoveFacts,
    quality_claim: str,
    analysis: EngineAnalysis,
    board: chess.Board | None = None,
) -> str:
    if (
        analysis.played_line.score.kind == "mate"
        and analysis.played_line.score.mate_for == "player"
    ):
        return f"{played.san} delivered forced mate."
    if board is not None and (
        purpose_claim := _primary_played_purpose_claim(
            board,
            played,
            analysis,
        )
    ):
        return f"{purpose_claim} in a critical position."
    if played.is_check:
        return f"{played.san} gave check in a critical position."
    if played.is_capture:
        return f"{played.san} captured in a critical position."
    if analysis.after_line is not None:
        return f"{played.san} was the critical move before {analysis.after_line.move_san}."
    return f"{played.san} was the critical move in the position."


def _featured_concept_claims(
    board: chess.Board,
    played: PlayedMoveFacts,
    quality: MoveQuality,
    quality_claim: str,
    featured_candidate: CandidateMove,
    analysis: EngineAnalysis,
) -> list[ConceptClaim]:
    if featured_candidate.uci != played.uci:
        return []
    if (
        analysis.played_line.score.kind == "mate"
        and analysis.played_line.score.mate_for == "player"
    ):
        return [
            ConceptClaim(
                kind="forced_mate",
                subject="featured_move",
                claim=f"{quality_claim}; it delivered forced mate.",
                source="engine_line",
                move_san=played.san,
            )
        ]
    if played.is_check:
        return [
            ConceptClaim(
                kind="forcing_move",
                subject="featured_move",
                claim=f"{quality_claim}; it gave check in a critical position.",
                source="played_move_fact",
                move_san=played.san,
            ),
            ConceptClaim(
                kind="initiative",
                subject="featured_move",
                claim=f"{played.san} kept the initiative with check",
                source="deterministic_detector",
                move_san=played.san,
            ),
        ]
    if played.is_capture:
        return [
            ConceptClaim(
                kind="capture",
                subject="featured_move",
                claim=f"{quality_claim}; it captured in a critical position.",
                source="played_move_fact",
                move_san=played.san,
            )
        ]
    if quality.label != "best":
        return []
    return [
        ConceptClaim(
            kind="critical_best_move",
            subject="featured_move",
            claim=_featured_best_claim(played, quality_claim, analysis, board),
            source="candidate_policy",
            move_san=played.san,
        )
    ]


def _key_candidate_concept_claims(
    board: chess.Board,
    key_candidate: CandidateMove,
    analysis: EngineAnalysis,
) -> list[ConceptClaim]:
    claims: list[ConceptClaim] = []
    if key_candidate.score.kind == "mate" and key_candidate.score.mate_for == "player":
        claims.append(
            ConceptClaim(
                kind="forced_mate",
                subject="key_move",
                claim=f"{key_candidate.san} checkmates the opponent",
                source="engine_line",
                move_san=key_candidate.san,
            )
        )
    if key_candidate.practicality == "practical_try":
        claims.append(
            ConceptClaim(
                kind="practical_alternative",
                subject="practical_alternative",
                claim=f"{key_candidate.san} was a practical alternative",
                source="candidate_policy",
                move_san=key_candidate.san,
            )
        )
    else:
        if _candidate_gives_check(board, key_candidate):
            claims.append(
                ConceptClaim(
                    kind="forcing_move",
                    subject="key_move",
                    claim=f"{key_candidate.san} would have been the key forcing check",
                    source="deterministic_detector",
                    move_san=key_candidate.san,
                )
            )
            claims.append(
                ConceptClaim(
                    kind="initiative",
                    subject="key_move",
                    claim=f"{key_candidate.san} kept the initiative with check",
                    source="deterministic_detector",
                    move_san=key_candidate.san,
                )
            )
        claims.append(
            ConceptClaim(
                kind="better_alternative",
                subject="key_move",
                claim=f"{key_candidate.san} would have been the better move",
                source="candidate_policy",
                move_san=key_candidate.san,
            )
        )

    claims.extend(_candidate_policy_concept_claims(key_candidate, "key_move"))
    claims.extend(
        build_move_concept_claims(
            board,
            key_candidate.uci,
            key_candidate.san,
            "key_move",
            line_pv_uci=_line_pv_for_move(analysis, key_candidate.uci),
        )
    )
    return claims


def _candidate_policy_concept_claims(
    candidate: CandidateMove,
    subject: ConceptClaimSubject,
) -> list[ConceptClaim]:
    claims: list[ConceptClaim] = []
    if candidate.recommendation_policy == "explain_as_hidden_resource":
        claims.append(
            ConceptClaim(
                kind="hidden_resource",
                subject=subject,
                claim=f"{candidate.san} was an important hidden resource",
                source="candidate_policy",
                move_san=candidate.san,
            )
        )
    if candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
        claims.append(
            ConceptClaim(
                kind="hard_to_find",
                subject=subject,
                claim=f"{candidate.san} was hard to find",
                source="human_likelihood",
                move_san=candidate.san,
            )
        )
    if candidate.teachable_skill_gap:
        claims.append(
            ConceptClaim(
                kind="teachable_skill_gap",
                subject=subject,
                claim=f"{candidate.san} becomes more common at stronger levels",
                source="human_likelihood",
                move_san=candidate.san,
            )
        )
    return claims


def _candidate_gives_check(board: chess.Board, candidate: CandidateMove) -> bool:
    move = chess.Move.from_uci(candidate.uci)
    return move in board.legal_moves and board.gives_check(move)


def _line_pv_for_move(analysis: EngineAnalysis, move_uci: str) -> list[str] | None:
    if analysis.played_line.move_uci == move_uci:
        return analysis.played_line.pv_uci
    for line in analysis.top_lines:
        if line.move_uci == move_uci:
            return line.pv_uci
    return None


def _unique_concept_claims(claims: list[ConceptClaim]) -> list[ConceptClaim]:
    unique: dict[tuple[str, str, str, str, str | None], ConceptClaim] = {}
    for claim in claims:
        key = (claim.kind, claim.subject, claim.claim, claim.source, claim.move_san)
        unique[key] = claim
    return list(unique.values())
