from __future__ import annotations

import chess

from g6explanation.context_engine import EvidenceVerifier, MoveContextBuilder
from g6explanation.context_engine.contracts import (
    CandidateMove,
    ContextResult,
    EngineAnalysis,
    EvidencePacket,
    MoveContextRequest,
    PlayerLevel,
    VerificationResult,
)
from tests.g6explanation.context_engine.helpers import StaticAnalysisProvider, analysis


def test_verifier_accepts_builder_packet_and_llm_context() -> None:
    result = _valid_result()

    assert result.verification.passed is True
    assert result.verification.failures == []
    assert EvidenceVerifier().verify(result.evidence, result.llm_context).passed is True


def test_verifier_rejects_invalid_played_move_uci() -> None:
    result = _valid_result()
    evidence = result.evidence.model_copy(
        update={"played": result.evidence.played.model_copy(update={"uci": "a1a1"})}
    )

    verification = EvidenceVerifier().verify(evidence, result.llm_context)

    assert "played_move_invalid_uci" in _issue_codes(verification)


def test_verifier_rejects_mismatched_fen_after() -> None:
    result = _valid_result()
    position = result.evidence.position.model_copy(
        update={"fen_after": result.evidence.position.fen_before}
    )
    evidence = result.evidence.model_copy(update={"position": position})

    verification = EvidenceVerifier().verify(evidence, result.llm_context)

    assert "fen_after_mismatch" in _issue_codes(verification)


def test_verifier_rejects_missing_played_move_analysis() -> None:
    result = _valid_result()
    board = chess.Board(result.evidence.position.fen_before)
    wrong_analysis = analysis(
        board,
        played_uci="d2d4",
        top_scores=[("e2e4", 45), ("d2d4", 25)],
        played_score=25,
        after_reply_uci="d7d5",
    )
    evidence = result.evidence.model_copy(update={"engine": wrong_analysis})

    verification = EvidenceVerifier().verify(evidence, result.llm_context)

    assert "engine_played_line_mismatch" in _issue_codes(verification)


def test_verifier_rejects_illegal_pv_move() -> None:
    result = _valid_result()
    top_line = result.evidence.engine.top_lines[0].model_copy(
        update={"pv_uci": ["e2e4", "e2e4"], "pv_san": ["e4", "e4"]}
    )
    evidence = _replace_engine(
        result, result.evidence.engine.model_copy(update={"top_lines": [top_line]})
    )

    verification = EvidenceVerifier().verify(evidence, result.llm_context)

    assert "engine_pv_illegal" in _issue_codes(verification)


def test_verifier_rejects_pv_root_mismatch() -> None:
    result = _valid_result()
    top_line = result.evidence.engine.top_lines[0].model_copy(
        update={"pv_uci": ["d2d4"], "pv_san": ["d4"]}
    )
    evidence = _replace_engine(
        result, result.evidence.engine.model_copy(update={"top_lines": [top_line]})
    )

    verification = EvidenceVerifier().verify(evidence, result.llm_context)

    assert "engine_pv_root_mismatch" in _issue_codes(verification)


def test_verifier_rejects_missing_wdl_when_show_wdl_was_requested() -> None:
    result = _valid_result()
    engine = result.evidence.engine.model_copy(update={"engine_options": {"UCI_ShowWDL": True}})
    evidence = result.evidence.model_copy(update={"engine": engine})

    verification = EvidenceVerifier().verify(evidence, result.llm_context)

    assert "engine_wdl_missing" in _issue_codes(verification)


def test_verifier_rejects_direct_recommendation_for_hard_move() -> None:
    result = _valid_result()
    candidates = [
        _direct_hard_candidate(candidate) if "engine_best" in candidate.roles else candidate
        for candidate in result.evidence.candidates
    ]
    evidence = result.evidence.model_copy(update={"candidates": candidates})

    verification = EvidenceVerifier().verify(evidence, result.llm_context)

    assert "candidate_hard_direct_recommendation" in _issue_codes(verification)


def test_verifier_rejects_unsupported_llm_claim() -> None:
    result = _valid_result()
    llm_context = result.llm_context.model_copy(
        update={"allowed_claims": [*result.llm_context.allowed_claims, "unsupported claim"]}
    )

    verification = EvidenceVerifier().verify(result.evidence, llm_context)

    assert _issue_codes(verification) == {"llm_context_claim_not_allowed"}


def _valid_result() -> ContextResult:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="e2e4",
        top_scores=[("e2e4", 45), ("d2d4", 25)],
        played_score=45,
        after_reply_uci="e7e5",
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    return MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)


def _issue_codes(verification: VerificationResult) -> set[str]:
    return {issue.code for issue in verification.failures}


def _replace_engine(result: ContextResult, engine: EngineAnalysis) -> EvidencePacket:
    return result.evidence.model_copy(update={"engine": engine})


def _direct_hard_candidate(candidate: CandidateMove) -> CandidateMove:
    return candidate.model_copy(
        update={
            "time_adjusted_findability": "engine_like",
            "recommendation_policy": "recommend_directly",
        }
    )
