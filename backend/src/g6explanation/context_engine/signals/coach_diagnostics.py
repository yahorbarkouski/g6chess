"""Deterministic review and coach-facing diagnostic tags."""

from __future__ import annotations

import chess

from g6explanation.context_engine.contracts import (
    CandidateMove,
    ConceptClaim,
    EngineAnalysis,
    EngineLine,
    MoveContextRequest,
    MoveDiagnosticTag,
    MoveDiagnosticTagKind,
    MoveDiagnosticTagSource,
    MoveQuality,
    MoveSignificance,
    PlayedMoveFacts,
    TimeSituation,
)
from g6explanation.context_engine.signals.quality import BAD_QUALITY_LABELS
from g6explanation.context_engine.signals.score_comparison import (
    absolute_cp_gap,
    absolute_wdl_expected_gap,
)

GOOD_OR_HOLDING_QUALITY = {"best", "forced", "excellent", "good", "neutral"}
HIGH_PLAYED_WDL_WIN = 800
WDL_EDGE_LIMIT = 25
WDL_DOMINANT_GAP = 80
WDL_BLUNDER_BAND = 150
SLOW_BLUNDER_THINK_TIME_SECONDS = 30


def build_move_diagnostic_tags(
    *,
    board: chess.Board,
    request: MoveContextRequest,
    played: PlayedMoveFacts,
    analysis: EngineAnalysis,
    quality: MoveQuality,
    significance: MoveSignificance,
    candidates: list[CandidateMove],
    concept_claims: list[ConceptClaim],
    time_situation: TimeSituation,
) -> list[MoveDiagnosticTag]:
    """Build deterministic tags that guide review wording without changing truth labels."""

    builder = _DiagnosticTagBuilder()
    _add_wdl_tags(builder, analysis, played, quality)
    _add_review_significance_tags(builder, analysis, quality, significance)
    _add_time_tags(builder, request, quality, concept_claims, time_situation)
    _add_candidate_tags(builder, played, quality, candidates, concept_claims)
    _add_rating_tags(builder, request, quality, candidates)
    _add_board_fact_tags(builder, board, played, quality, significance, concept_claims)
    return builder.tags


def _add_wdl_tags(
    builder: _DiagnosticTagBuilder,
    analysis: EngineAnalysis,
    played: PlayedMoveFacts,
    quality: MoveQuality,
) -> None:
    wdl_loss = quality.wdl_expected_score_loss
    if wdl_loss is not None and 0 < wdl_loss <= WDL_EDGE_LIMIT:
        builder.add(
            "wdl:edge",
            "wdl",
            "wdl_comparison",
            "WDL expected-score loss is near a label boundary.",
        )

    reference = _reference_line(analysis, played)
    use_reference_wdl = (
        reference is not None
        and analysis.played_line.score.kind == "cp"
        and reference.score.kind == "cp"
    )
    reference_wdl_gap = (
        absolute_wdl_expected_gap(analysis.played_line.wdl, reference.wdl)
        if use_reference_wdl and reference is not None
        else None
    )
    wdl_gap = max(wdl_loss or 0, reference_wdl_gap or 0)
    cp_gap = (
        absolute_cp_gap(analysis.played_line.score, reference.score)
        if use_reference_wdl and reference is not None
        else None
    )
    if wdl_gap >= WDL_DOMINANT_GAP and (cp_gap is None or cp_gap < wdl_gap):
        builder.add(
            "wdl:dominant",
            "wdl",
            "wdl_comparison",
            "WDL drives the review severity more strongly than centipawns.",
        )

    if (
        quality.label == "mistake"
        and wdl_loss is not None
        and wdl_loss > WDL_BLUNDER_BAND
        and quality.score_loss_vs_best_cp is not None
        and quality.score_loss_vs_best_cp <= 300
    ):
        builder.add(
            "wdl:blunder-capped",
            "wdl",
            "quality_classification",
            "A WDL-only blunder signal is capped below blunder without blunder-band centipawns.",
        )

    if (
        quality.label == "good"
        and analysis.played_line.wdl is not None
        and analysis.played_line.wdl.win >= HIGH_PLAYED_WDL_WIN
    ):
        builder.add(
            "coach:still-winning-caveat",
            "coach",
            "wdl_comparison",
            "The move lost value but the played line still has overwhelming winning chances.",
        )


def _add_review_significance_tags(
    builder: _DiagnosticTagBuilder,
    analysis: EngineAnalysis,
    quality: MoveQuality,
    significance: MoveSignificance,
) -> None:
    if quality.label == "forced" and analysis.played_line.score.kind == "mate":
        builder.add(
            "significance:critical",
            "review_significance",
            "legal_move_count",
            "The move was forced, but the position is a critical forced-mate position.",
        )
    if significance.label == "critical" and significance.score < 0.8:
        builder.add(
            "significance:high",
            "review_significance",
            "significance_policy",
            "The review attention sits near the high-to-critical boundary.",
        )


def _add_time_tags(
    builder: _DiagnosticTagBuilder,
    request: MoveContextRequest,
    quality: MoveQuality,
    concept_claims: list[ConceptClaim],
    time_situation: TimeSituation,
) -> None:
    under_pressure = time_situation in {"low_time", "time_scramble"}
    scramble = time_situation == "time_scramble"
    if scramble and quality.label in GOOD_OR_HOLDING_QUALITY:
        builder.add(
            "coach:fast-good-move-credit",
            "coach",
            "time_context",
            "A sound move under severe clock pressure deserves practical credit.",
        )
    if scramble and quality.label == "blunder":
        builder.add(
            "coach:time-scramble-blunder",
            "coach",
            "time_context",
            "The move remains a blunder, but the clock context should shape the wording.",
        )
    if scramble and quality.label in {"inaccuracy", "mistake"}:
        builder.add(
            "coach:time-scramble-miss",
            "coach",
            "time_context",
            "The miss remains objectively important, with time pressure as wording context.",
        )
    if under_pressure and quality.label == "missed_win":
        builder.add(
            "coach:missed-mate-under-time",
            "coach",
            "time_context",
            "A missed winning resource under low time should be caveated without changing truth.",
        )
    if (
        scramble
        and quality.label in GOOD_OR_HOLDING_QUALITY
        and _has_concept(concept_claims, "tactic")
    ):
        builder.add(
            "coach:fast-tactic-credit",
            "coach",
            "time_context",
            "A tactical move found in a scramble deserves practical credit.",
        )
    if (
        scramble
        and quality.label in GOOD_OR_HOLDING_QUALITY
        and _has_any_concept(concept_claims, {"forcing_move", "initiative"})
    ):
        builder.add(
            "coach:fast-forcing-resource",
            "coach",
            "time_context",
            "A forcing resource found in a scramble deserves practical credit.",
        )
    if scramble and _has_any_concept(concept_claims, {"castling", "en_passant", "promotion"}):
        builder.add(
            "coach:special-rule-under-time",
            "coach",
            "time_context",
            "A special-rule move under time pressure should be credited as a legal-move success.",
        )
    if (
        request.think_time_seconds is not None
        and request.think_time_seconds >= SLOW_BLUNDER_THINK_TIME_SECONDS
        and quality.label in BAD_QUALITY_LABELS
    ):
        builder.add(
            "coach:used-too-much-time-for-blunder",
            "coach",
            "time_context",
            "The player spent substantial think time before a serious objective mistake.",
        )
    if (
        request.clock_before_seconds is not None
        and request.clock_before_seconds <= 10
        and (request.increment_seconds or 0) >= 5
    ):
        builder.add(
            "coach:increment-context",
            "coach",
            "time_context",
            "A large increment makes a tiny remaining clock less desperate than no increment.",
        )
    if quality.label == "forced":
        builder.add(
            "coach:no-blame-forced",
            "coach",
            "legal_move_count",
            "A forced move should not be explained as a choice-based mistake.",
        )


def _add_candidate_tags(
    builder: _DiagnosticTagBuilder,
    played: PlayedMoveFacts,
    quality: MoveQuality,
    candidates: list[CandidateMove],
    concept_claims: list[ConceptClaim],
) -> None:
    if any(candidate.practicality == "practical_try" for candidate in candidates):
        builder.add(
            "coach:practical-option",
            "coach",
            "candidate_policy",
            "A practical alternative is available and should be framed as a coaching option.",
        )

    played_candidate = next(
        (candidate for candidate in candidates if "played_move" in candidate.roles),
        None,
    )
    if (
        played_candidate is not None
        and quality.label in BAD_QUALITY_LABELS
        and played_candidate.time_adjusted_findability == "obvious"
    ):
        builder.add(
            "coach:common-human-error",
            "coach",
            "human_likelihood",
            "A common human move can still be objectively bad.",
        )

    material_claims = [claim.claim.lower() for claim in concept_claims if claim.kind == "material"]
    if any("trade" in claim or "exchang" in claim for claim in material_claims):
        builder.add(
            "coach:trade-not-win",
            "coach",
            "deterministic_detector",
            "The material evidence describes a trade or exchange, not a material win.",
        )

    if played.is_capture and not _has_concept(concept_claims, "recapture"):
        builder.add(
            "coach:not-recapture",
            "coach",
            "played_move_fact",
            "The move was an ordinary capture, not a verified recapture.",
        )

    if quality.label in BAD_QUALITY_LABELS and _has_concept(concept_claims, "tactic"):
        builder.add(
            "coach:missed-concrete-tactic",
            "coach",
            "deterministic_detector",
            "The missed alternative has concrete tactic evidence.",
        )


def _add_rating_tags(
    builder: _DiagnosticTagBuilder,
    request: MoveContextRequest,
    quality: MoveQuality,
    candidates: list[CandidateMove],
) -> None:
    rating = request.player_level.rating_value()
    if rating is None:
        return
    if rating < 1000 and quality.label in BAD_QUALITY_LABELS:
        builder.add(
            "coach:concrete-beginner-wording",
            "coach",
            "rating_context",
            "Beginner-facing wording should stay direct and concrete.",
        )
    if rating >= 2200 and (
        quality.label in BAD_QUALITY_LABELS
        or any(
            "engine_best" in candidate.roles
            and "played_move" not in candidate.roles
            and candidate.time_adjusted_findability in {"very_hard", "engine_like"}
            for candidate in candidates
        )
    ):
        builder.add(
            "coach:advanced-practical-nuance",
            "coach",
            "rating_context",
            "Advanced players can receive harder-resource nuance without changing truth labels.",
        )


def _add_board_fact_tags(
    builder: _DiagnosticTagBuilder,
    board: chess.Board,
    played: PlayedMoveFacts,
    quality: MoveQuality,
    significance: MoveSignificance,
    concept_claims: list[ConceptClaim],
) -> None:
    if board.fullmove_number <= 3 and quality.label in GOOD_OR_HOLDING_QUALITY:
        builder.add(
            "coach:no-unsupported-opening-name",
            "coach",
            "deterministic_detector",
            (
                "Opening-phase wording must describe board features unless an opening name "
                "is supplied."
            ),
        )

    if (
        quality.label == "best"
        and significance.label == "critical"
        and not played.is_capture
        and not played.is_check
        and played.promotion is None
        and not _has_any_concept(
            concept_claims,
            {"castling", "en_passant", "material", "promotion", "tactic"},
        )
    ):
        builder.add(
            "coach:quiet-critical-resource",
            "coach",
            "significance_policy",
            "A quiet move can still be the critical resource in the position.",
        )


def _reference_line(analysis: EngineAnalysis, played: PlayedMoveFacts) -> EngineLine | None:
    if played.uci != analysis.top_lines[0].move_uci:
        return analysis.top_lines[0]
    return next(
        (line for line in analysis.top_lines[1:] if line.move_uci != played.uci),
        None,
    )


def _has_concept(concept_claims: list[ConceptClaim], kind: str) -> bool:
    return any(claim.kind == kind for claim in concept_claims)


def _has_any_concept(concept_claims: list[ConceptClaim], kinds: set[str]) -> bool:
    return any(claim.kind in kinds for claim in concept_claims)


class _DiagnosticTagBuilder:
    def __init__(self) -> None:
        self.tags: list[MoveDiagnosticTag] = []
        self._seen: set[str] = set()

    def add(
        self,
        tag: str,
        kind: MoveDiagnosticTagKind,
        source: MoveDiagnosticTagSource,
        claim: str,
    ) -> None:
        if tag in self._seen:
            return
        self._seen.add(tag)
        self.tags.append(MoveDiagnosticTag(tag=tag, kind=kind, source=source, claim=claim))
