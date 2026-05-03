from __future__ import annotations

from typing import cast

import pytest

from g6explanation.context_engine.contracts import (
    CandidateMove,
    ConceptClaim,
    ConceptClaimKind,
    Score,
)
from g6explanation.explanation_generation.contracts import (
    ExplanationOutput,
    ExplanationVerificationResult,
)
from g6explanation.explanation_generation.explanation_verification import ExplanationVerifier
from tests.g6explanation.explanation_generation.helpers import (
    best_context,
    hard_engine_best_context,
    mistake_context_with_practical_alternative,
)


def test_verifier_accepts_grounded_model_explanation() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake because it let the opponent improve with e5. "
            "Nf3 was a practical alternative close to the engine best move."
        )
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_unsupported_move() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(explanation="g4 was a mistake, and a3 was the better move.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "mentioned_move_unsupported" in _failure_codes(verification)


def test_verifier_rejects_uci_move_mentions() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(explanation="g2g4 was a mistake because Nf3 was better.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "uci_move_mentioned" in _failure_codes(verification)


def test_verifier_rejects_explanation_that_omits_played_move() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(explanation="This was a mistake because Nf3 was better.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "played_move_missing" in _failure_codes(verification)


def test_verifier_rejects_unsupported_pv_continuation() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(explanation="g4 was a mistake; the line then goes e5 and Nc6.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "mentioned_move_unsupported" in _failure_codes(verification)


def test_verifier_rejects_unsupported_mate_claim() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(explanation="g4 was a mistake because it allowed checkmate.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_mate_claim" in _failure_codes(verification)


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
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake because g4 checkmated the opponent. "
            "Nf3 was a practical alternative close to the engine best move."
        )
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
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake, and g4 checkmates the opponent. "
            "Nf3 was a practical alternative close to the engine best move."
        )
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
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake because it allowed Qh4#, an immediate checkmate. "
            "Nf3 was a practical alternative close to the engine best move."
        )
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_unsupported_material_claim() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(explanation="g4 was a mistake because it loses a queen.")

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
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake because it lost material. "
            "Nf3 was a practical alternative close to the engine best move."
        )
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


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
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake because it lost a queen. "
            "Nf3 was a practical alternative close to the engine best move."
        )
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
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake even though it won a pawn. "
            "Nf3 was a practical alternative close to the engine best move."
        )
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_unsupported_tactic_claim() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(explanation="g4 was a mistake because it walks into a fork.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_tactic_claim" in _failure_codes(verification)


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
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake because it walked into a fork. "
            "Nf3 was a practical alternative close to the engine best move."
        )
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
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake because it walked into a fork. "
            "Nf3 was a practical alternative close to the engine best move."
        )
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "unsupported_tactic_claim" in _failure_codes(verification)


def test_verifier_rejects_unsupported_concept_claim() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake because it damaged king safety. "
            "Nf3 was a practical alternative close to the engine best move."
        )
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
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake because it damaged king safety. "
            "Nf3 was a practical alternative close to the engine best move."
        )
    )

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
    output = ExplanationOutput(explanation="e4 was the best move and a critical move.")

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
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake because it damaged king safety. "
            "Nf3 was a practical alternative close to the engine best move."
        )
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
    output = ExplanationOutput(
        explanation=(
            f"g4 was a mistake because the {phrase} detail mattered. "
            "Nf3 was a practical alternative close to the engine best move."
        )
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
    output = ExplanationOutput(
        explanation=(
            f"g4 was a mistake because the {phrase} detail mattered. "
            "Nf3 was a practical alternative close to the engine best move."
        )
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_rejects_wrong_quality_label() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(explanation="g4 was good because Nf3 was another option.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "quality_label_missing" in _failure_codes(verification)


def test_verifier_rejects_best_move_inconsistency() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(explanation="g4 was a mistake, but Nf3 was the best move.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "best_move_inconsistent" in _failure_codes(verification)


def test_verifier_rejects_hard_move_without_caveat() -> None:
    context = hard_engine_best_context()
    output = ExplanationOutput(explanation="a3 was a blunder; e4 was the better move.")

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "hard_move_uncaveated" in _failure_codes(verification)


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
    output = ExplanationOutput(explanation="g4 was a mistake, so you should play e4.")

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
    output = ExplanationOutput(explanation="e4 was the best move, so it was fine to play e4.")

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_still_rejects_recommending_bad_played_move() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake, but you should play g4 anyway. "
            "Nf3 was a practical alternative close to the engine best move."
        )
    )

    verification = ExplanationVerifier().verify(context, output)

    assert not verification.passed
    assert "recommendation_policy_violation" in _failure_codes(verification)


def test_verifier_allows_recommendation_language_for_different_move_near_bad_move() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(
        explanation="g4 was a mistake; you should play Nf3 as the practical alternative."
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def test_verifier_allows_negative_advice_about_bad_played_move() -> None:
    context = mistake_context_with_practical_alternative()
    output = ExplanationOutput(
        explanation=(
            "g4 was a mistake; do not play g4 in this structure. "
            "Nf3 was a practical alternative close to the engine best move."
        )
    )

    verification = ExplanationVerifier().verify(context, output)

    assert verification.passed


def _failure_codes(verification: ExplanationVerificationResult) -> set[str]:
    return {failure.code for failure in verification.failures}


def _candidate(candidates: list[CandidateMove], uci: str) -> CandidateMove:
    return next(candidate for candidate in candidates if candidate.uci == uci)
