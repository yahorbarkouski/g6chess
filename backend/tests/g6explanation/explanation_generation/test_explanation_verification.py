from __future__ import annotations

from typing import cast

import chess
import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    CandidateMove,
    ConceptClaim,
    ConceptClaimKind,
    ContextResult,
    MoveContextRequest,
    PlayerLevel,
    Score,
)
from g6explanation.explanation_generation.contracts import (
    ExplanationLineCard,
    ExplanationOutput,
    ExplanationSegment,
    ExplanationVerificationResult,
)
from g6explanation.explanation_generation.explanation_verification import ExplanationVerifier
from tests.g6explanation.context_engine.helpers import StaticAnalysisProvider, analysis
from tests.g6explanation.explanation_generation.helpers import (
    best_context,
    hard_engine_best_context,
    mistake_context_with_practical_alternative,
    rich_output,
)


def test_verifier_accepts_grounded_model_explanation() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output(
        "g4 was a mistake because it let the opponent improve with e5. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_unsupported_move() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output("g4 was a mistake, and a3 was the better move.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "mentioned_move_unsupported" in _failure_codes(verification)


def test_verifier_rejects_uci_move_mentions() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output("g2g4 was a mistake because Nf3 was better.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "uci_move_mentioned" in _failure_codes(verification)


def test_verifier_rejects_explanation_that_omits_played_move() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output("This was a mistake because Nf3 was better.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "played_move_missing" in _failure_codes(verification)


def test_verifier_accepts_castling_word_as_played_move_mention() -> None:
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    engine_analysis = analysis(
        board,
        played_uci="e1g1",
        top_scores=[("e1g1", 100), ("a1a8", 80)],
        played_score=100,
    )
    context = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(
        MoveContextRequest(
            fen_before=board.fen(),
            played_move="e1g1",
            player_color="white",
            player_level=PlayerLevel.rating(1200),
        )
    )
    output = rich_output("Castling was the best move.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_unsupported_pv_continuation() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output("g4 was a mistake; the line then goes e5 and Nc6.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "mentioned_move_unsupported" in _failure_codes(verification)


def test_verifier_rejects_unsupported_mate_claim() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output("g4 was a mistake because it allowed checkmate.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_mate_claim" in _failure_codes(verification)


def test_verifier_accepts_verified_line_card_segments() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(
        segments=[
            ExplanationSegment(
                text="g4 was a mistake because e5 is the reply that lets Black improve.",
                line_card_id="played-line",
                line_card_anchor="e5",
            )
        ],
        line_cards=[
            ExplanationLineCard(
                id="played-line",
                moves=["g4", "e5"],
                title="Why g4 gets punished",
                why="g4 was a mistake because it let the opponent improve with e5.",
            )
        ],
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_line_card_with_changed_moves() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(
        segments=[
            ExplanationSegment(
                text="g4 was a mistake because e5 is the reply that lets Black improve.",
                line_card_id="played-line",
                line_card_anchor="e5",
            )
        ],
        line_cards=[
            ExplanationLineCard(
                id="played-line",
                moves=["g4", "Nc6"],
                title="Why g4 gets punished",
                why="g4 was a mistake because it let the opponent improve with e5.",
            )
        ],
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "line_card_move_mismatch" in _failure_codes(verification)


def test_verifier_rejects_mating_move_claim_from_position_mate_evidence_only() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="forced_mate",
        subject="position",
        claim="g4 allowed forced mate against the player",
        source="quality_classification",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake because g4 checkmated the opponent. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_mate_claim" in _failure_codes(verification)


def test_verifier_accepts_mating_move_claim_when_move_has_mate_evidence() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="forced_mate",
        subject="played_move",
        claim="g4 checkmates the opponent",
        source="engine_line",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake, and g4 checkmates the opponent. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_accepts_mating_opponent_reply_from_after_line() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="opponent_resource",
        subject="opponent_reply",
        claim="the opponent's key reply after g4 was Qh4#",
        source="engine_line",
        move_san="Qh4#",
    )
    after_line = context.evidence.engine.after_line
    assert after_line is not None
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={
                    "engine": context.evidence.engine.model_copy(
                        update={
                            "after_line": after_line.model_copy(
                                update={
                                    "move_uci": "d8h4",
                                    "move_san": "Qh4#",
                                    "score": Score.mate(mate_in=1, mate_for="opponent"),
                                }
                            )
                        }
                    ),
                    "concept_claims": [*context.evidence.concept_claims, claim],
                }
            ),
            "llm_context": context.llm_context.model_copy(
                update={
                    "allowed_claims": [
                        *context.llm_context.allowed_claims,
                        "the opponent's key reply after g4 was Qh4#",
                    ],
                    "concept_claims": [*context.llm_context.concept_claims, claim],
                }
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake because it allowed Qh4#, an immediate checkmate. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_does_not_treat_square_reference_as_move() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="material",
        subject="played_move",
        claim="g4 lost a pawn immediately",
        source="deterministic_detector",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake because it lost the h2 pawn. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_accepts_multiple_verified_immediate_mates() -> None:
    context = best_context()
    top_line = context.evidence.engine.top_lines[0].model_copy(
        update={"move_san": "Rd8#", "score": Score.mate(mate_in=1, mate_for="player")}
    )
    candidate = context.evidence.candidates[0].model_copy(update={"san": "Rd8#"})
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={
                    "played": context.evidence.played.model_copy(
                        update={"san": "e4#", "is_checkmate": True}
                    ),
                    "engine": context.evidence.engine.model_copy(
                        update={"top_lines": [top_line, *context.evidence.engine.top_lines[1:]]}
                    ),
                    "candidates": [candidate, *context.evidence.candidates[1:]],
                }
            ),
            "llm_context": context.llm_context.model_copy(
                update={
                    "played": "e4#",
                    "allowed_claims": [
                        *context.llm_context.allowed_claims,
                        "Rd8# was another immediate mate",
                    ],
                }
            ),
        }
    )
    output = rich_output(
        "e4# was the best move and delivered forced mate. "
        "Rd8# was another immediate mate, but e4# also checkmated the opponent."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_unsupported_material_claim() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output("g4 was a mistake because it loses a queen.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_material_claim" in _failure_codes(verification)


def test_verifier_accepts_supported_material_claim() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="material",
        subject="played_move",
        claim="g4 lost material immediately",
        source="deterministic_detector",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake because it lost material. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


@pytest.mark.parametrize(
    "explanation",
    [
        "e4 won a pawn immediately.",
        "e4 is winning a pawn immediately.",
        "e4 gains a pawn immediately.",
        "e4 picked up a pawn immediately.",
    ],
)
def test_verifier_rejects_unsupported_material_gain_variants(explanation: str) -> None:
    context = best_context()

    verification = ExplanationVerifier().verify(context, rich_output(explanation))

    assert not verification.passed
    assert "unsupported_material_claim" in _failure_codes(verification)


def test_verifier_rejects_specific_material_claim_not_in_material_evidence() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="material",
        subject="played_move",
        claim="g4 lost material immediately",
        source="deterministic_detector",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake because it lost a queen. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_material_claim" in _failure_codes(verification)


def test_verifier_accepts_specific_material_claim_when_evidence_matches() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="material",
        subject="played_move",
        claim="g4 won a pawn immediately",
        source="deterministic_detector",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake even though it won a pawn. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


@pytest.mark.parametrize(
    "explanation",
    [
        "g4 was a mistake even though it was winning a pawn. "
        "Nf3 was a practical alternative that stayed close to best play.",
        "g4 was a mistake even though it gains a pawn. "
        "Nf3 was a practical alternative that stayed close to best play.",
        "g4 was a mistake even though it picked up a pawn. "
        "Nf3 was a practical alternative that stayed close to best play.",
    ],
)
def test_verifier_accepts_supported_material_gain_variants(explanation: str) -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="material",
        subject="played_move",
        claim="g4 won a pawn immediately",
        source="deterministic_detector",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )

    verification = ExplanationVerifier().verify(context, rich_output(explanation))

    assert verification.passed


def test_verifier_checks_piece_type_inside_material_gain_phrase_only() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="material",
        subject="played_move",
        claim="g4 won a pawn immediately",
        source="deterministic_detector",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake even though it won a pawn while the rook stayed active. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_accepts_recapture_wording_when_recapture_is_supported() -> None:
    context = _recapture_context()
    output = rich_output("cxd5 recaptured the pawn on d5 and claimed the center.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_material_gain_when_support_is_only_recapture_recovery() -> None:
    context = _recapture_context()
    output = rich_output("cxd5 is winning a pawn immediately and claiming the center.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_material_claim" in _failure_codes(verification)


@pytest.mark.parametrize(
    "trade_phrase",
    [
        "it traded a bishop for a knight",
        "it was a bishop-for-knight trade",
    ],
)
def test_verifier_accepts_material_trade_wording_when_trade_is_supported(
    trade_phrase: str,
) -> None:
    context = _context_with_extra_claim(
        mistake_context_with_practical_alternative(),
        ConceptClaim(
            kind="material",
            subject="practical_alternative",
            claim="Nf3 traded a bishop for a knight",
            source="deterministic_detector",
            move_san="Nf3",
        ),
    )
    output = rich_output(
        f"g4 was a mistake. Nf3 was a practical alternative because {trade_phrase}."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


@pytest.mark.parametrize(
    "unsupported_phrase",
    [
        "it immediately won a knight",
        "it was a queen-for-pawn trade",
    ],
)
def test_verifier_rejects_material_win_when_support_is_only_trade(
    unsupported_phrase: str,
) -> None:
    context = _context_with_extra_claim(
        mistake_context_with_practical_alternative(),
        ConceptClaim(
            kind="material",
            subject="practical_alternative",
            claim="Nf3 traded a bishop for a knight",
            source="deterministic_detector",
            move_san="Nf3",
        ),
    )
    output = rich_output(
        f"g4 was a mistake. Nf3 was a practical alternative because {unsupported_phrase}."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_material_claim" in _failure_codes(verification)


def test_verifier_rejects_unsupported_tactic_claim() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output("g4 was a mistake because it walks into a fork.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_tactic_claim" in _failure_codes(verification)


def test_verifier_does_not_match_tactic_terms_inside_words() -> None:
    context = best_context()
    output = rich_output("e4 was the best move, keeping the position stable.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_accepts_supported_tactic_claim() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="tactic",
        subject="played_move",
        claim="g4 walked into a fork",
        source="deterministic_detector",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake because it walked into a fork. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_tactic_claim_not_named_by_tactic_evidence() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="tactic",
        subject="played_move",
        claim="g4 walked into a pin",
        source="deterministic_detector",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake because it walked into a fork. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_tactic_claim" in _failure_codes(verification)


def test_verifier_accepts_supported_rook_fork_and_square_references() -> None:
    context = _rook_fork_context()
    output = rich_output(
        "Nb6 forked both rooks: the rook on d7 and the rook on a8. "
        "It also attacked the bishop on c8, so the multi-piece attack is the "
        "concrete point of the move."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_unsupported_attack_claim() -> None:
    context = best_context()
    output = rich_output("e4 was the best move because it attacked both rooks.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_concept_claim" in _failure_codes(verification)


def test_verifier_accepts_supported_fianchetto_claim() -> None:
    context = _fianchetto_context()
    output = rich_output("g3 opened the fianchetto square on g2 for the bishop.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_unsupported_fianchetto_claim() -> None:
    context = best_context()
    output = rich_output("e4 was the best move because it prepared a fianchetto.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_concept_claim" in _failure_codes(verification)


def test_verifier_rejects_unsupported_concept_claim() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output(
        "g4 was a mistake because it damaged king safety. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_concept_claim" in _failure_codes(verification)


def test_verifier_accepts_supported_concept_claim() -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind="king_safety",
        subject="played_move",
        claim="g4 damaged king safety",
        source="deterministic_detector",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        "g4 was a mistake because it damaged king safety. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_allows_central_space_when_center_claim_is_supported() -> None:
    context = best_context()
    output = rich_output("e4 was the best move, claiming central space.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_accepts_critical_move_wording_from_best_move_significance() -> None:
    context = best_context()
    context = context.model_copy(
        update={
            "llm_context": context.llm_context.model_copy(
                update={
                    "significance": context.llm_context.significance.model_copy(
                        update={"label": "critical"}
                    )
                }
            )
        }
    )
    output = rich_output("e4 was the best move and a critical move.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_accepts_critical_move_wording_for_critical_alternative() -> None:
    context = mistake_context_with_practical_alternative()
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={
                    "significance": context.evidence.significance.model_copy(
                        update={"label": "critical", "score": 1.0}
                    )
                }
            ),
            "llm_context": context.llm_context.model_copy(
                update={
                    "significance": context.llm_context.significance.model_copy(
                        update={"label": "critical", "score": 1.0}
                    )
                }
            ),
        }
    )
    output = rich_output("g4 was a mistake; the critical move was Nf3 as a practical alternative.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_does_not_accept_concept_from_allowed_claims_alone() -> None:
    context = mistake_context_with_practical_alternative()
    context = context.model_copy(
        update={
            "llm_context": context.llm_context.model_copy(
                update={
                    "allowed_claims": [
                        *context.llm_context.allowed_claims,
                        "g4 damaged king safety",
                    ]
                }
            )
        }
    )
    output = rich_output(
        "g4 was a mistake because it damaged king safety. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_concept_claim" in _failure_codes(verification)


@pytest.mark.parametrize(
    ("kind", "phrase"),
    [
        ("castling", "castling"),
        ("en_passant", "en passant"),
        ("promotion", "promotion"),
    ],
)
def test_verifier_rejects_unsupported_special_move_concepts(
    kind: str,
    phrase: str,
) -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output(
        f"g4 was a mistake because the {phrase} detail mattered. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_concept_claim" in _failure_codes(verification)


@pytest.mark.parametrize(
    ("kind", "phrase"),
    [
        ("castling", "castling"),
        ("en_passant", "en passant"),
        ("promotion", "promotion"),
    ],
)
def test_verifier_accepts_supported_special_move_concepts(
    kind: str,
    phrase: str,
) -> None:
    context = mistake_context_with_practical_alternative()
    claim = ConceptClaim(
        kind=cast(ConceptClaimKind, kind),
        subject="played_move",
        claim=f"g4 involved {phrase}",
        source="played_move_fact",
        move_san="g4",
    )
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )
    output = rich_output(
        f"g4 was a mistake because the {phrase} detail mattered. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_wrong_quality_label() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output("g4 was good because Nf3 was another option.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "quality_label_missing" in _failure_codes(verification)


def test_verifier_allows_implicit_positive_quality_label() -> None:
    context = best_context()
    output = rich_output("e4 fits the position; no sharper alternative is needed.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_still_requires_bad_quality_label() -> None:
    context = hard_engine_best_context()
    output = rich_output("a3 let the opponent improve with e5.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "quality_label_missing" in _failure_codes(verification)


def test_verifier_rejects_internal_prompt_language() -> None:
    context = best_context()
    output = rich_output("e4 was the featured move and the best move.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "internal_language" in _failure_codes(verification)


def test_verifier_rejects_engine_meta_language() -> None:
    context = best_context()
    output = rich_output("e4 was the engine best move.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "internal_language" in _failure_codes(verification)


def test_verifier_allows_engine_like_findability_caveat() -> None:
    context = hard_engine_best_context()
    output = rich_output("a3 was a blunder; e4 was an engine-like hidden resource.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_best_move_inconsistency() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output("g4 was a mistake, but Nf3 was the best move.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "best_move_inconsistent" in _failure_codes(verification)


def test_verifier_rejects_hard_move_without_caveat() -> None:
    context = hard_engine_best_context()
    output = rich_output("a3 was a blunder; e4 was the better move.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "hard_move_uncaveated" in _failure_codes(verification)


def test_verifier_allows_hard_played_move_when_quality_is_non_bad() -> None:
    context = best_context()
    engine_best = context.llm_context.engine_best_move
    assert engine_best is not None
    context = context.model_copy(
        update={
            "llm_context": context.llm_context.model_copy(
                update={
                    "engine_best_move": engine_best.model_copy(
                        update={
                            "findability": "hard",
                            "recommendation_policy": "mention_with_caveat",
                        }
                    )
                }
            )
        }
    )
    output = rich_output("e4 was the best move.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_do_not_recommend_move() -> None:
    context = mistake_context_with_practical_alternative()
    candidate = _candidate(context.evidence.candidates, "e2e4").model_copy(
        update={"recommendation_policy": "do_not_recommend"}
    )
    candidates = [
        candidate if existing.uci == candidate.uci else existing
        for existing in context.evidence.candidates
    ]
    context = context.model_copy(
        update={
            "evidence": context.evidence.model_copy(update={"candidates": candidates}),
        }
    )
    output = rich_output("g4 was a mistake, so you should play e4.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "recommendation_policy_violation" in _failure_codes(verification)


def test_verifier_allows_positive_language_for_non_bad_played_move() -> None:
    context = best_context()
    played = _candidate(context.evidence.candidates, "e2e4").model_copy(
        update={"recommendation_policy": "do_not_recommend"}
    )
    candidates = [
        played if existing.uci == played.uci else existing
        for existing in context.evidence.candidates
    ]
    context = context.model_copy(
        update={"evidence": context.evidence.model_copy(update={"candidates": candidates})}
    )
    output = rich_output("e4 was the best move, so it was fine to play e4.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_still_rejects_recommending_bad_played_move() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output(
        "g4 was a mistake, but you should play g4 anyway. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "recommendation_policy_violation" in _failure_codes(verification)


def test_verifier_allows_recommendation_language_for_different_move_near_bad_move() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output("g4 was a mistake; you should play Nf3 as the practical alternative.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_allows_negative_advice_about_bad_played_move() -> None:
    context = mistake_context_with_practical_alternative()
    output = rich_output(
        "g4 was a mistake; do not play g4 in this structure. "
        "Nf3 was a practical alternative that stayed close to best play."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def _failure_codes(verification: ExplanationVerificationResult) -> set[str]:
    return {failure.code for failure in verification.failures}


def _candidate(candidates: list[CandidateMove], uci: str) -> CandidateMove:
    return next(candidate for candidate in candidates if candidate.uci == uci)


def _context_with_extra_claim(context: ContextResult, claim: ConceptClaim) -> ContextResult:
    return context.model_copy(
        update={
            "evidence": context.evidence.model_copy(
                update={"concept_claims": [*context.evidence.concept_claims, claim]}
            ),
            "llm_context": context.llm_context.model_copy(
                update={"concept_claims": [*context.llm_context.concept_claims, claim]}
            ),
        }
    )


def _rook_fork_context() -> ContextResult:
    board = chess.Board("r1b3k1/1p1r2pn/p7/5p2/2NppP2/6B1/PPP3PP/2KR3R w - - 0 22")
    engine_analysis = analysis(
        board,
        played_uci="c4b6",
        top_scores=[("c4b6", 325), ("g3f2", 125)],
        played_score=325,
        after_reply_uci="d7d6",
        played_pv_uci=["c4b6", "d7d6", "b6a8"],
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="c4b6",
        player_color="white",
        player_level=PlayerLevel.rating(1215, "chess.com"),
    )
    return MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)


def _fianchetto_context() -> ContextResult:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g3",
        top_scores=[("g2g3", 40), ("g1f3", 25)],
        played_score=40,
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g3",
        player_color="white",
        player_level=PlayerLevel.rating(1400),
    )
    return MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)


def _recapture_context() -> ContextResult:
    pgn = "1. e4 c6 2. Nf3 d5 3. exd5 cxd5"
    board = chess.Board()
    for san in ["e4", "c6", "Nf3", "d5", "exd5"]:
        board.push_san(san)
    engine_analysis = analysis(
        board,
        played_uci="c6d5",
        top_scores=[("c6d5", 100)],
        played_score=100,
    )
    return MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(
        MoveContextRequest(
            pgn=pgn,
            ply=6,
            player_color="black",
            player_level=PlayerLevel.rating(1200),
        )
    )
