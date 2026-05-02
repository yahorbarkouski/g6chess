from __future__ import annotations

import chess

from g6explanation.context_engine import EvidenceVerifier, MoveContextBuilder
from g6explanation.context_engine.contracts import (
    CandidateMove,
    ContextResult,
    EngineAnalysis,
    EngineAnalysisBudget,
    EngineLine,
    EvidencePacket,
    MoveContextRequest,
    PlayerLevel,
    Score,
    VerificationResult,
)
from g6explanation.context_engine.stockfish_analysis import MIN_STOCKFISH_DEPTH
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


def test_verifier_rejects_depth_budget_below_stockfish_minimum() -> None:
    board = chess.Board()
    played_move = chess.Move.from_uci("e2e4")
    engine_analysis = _depth_analysis(
        board,
        played_uci=played_move.uci(),
        budget_depth=MIN_STOCKFISH_DEPTH - 1,
        line_depth=MIN_STOCKFISH_DEPTH - 1,
    )

    verification = EvidenceVerifier().verify_engine_analysis(board, played_move, engine_analysis)

    assert "engine_depth_below_minimum" in _issue_codes(verification)


def test_verifier_rejects_non_static_line_below_stockfish_minimum() -> None:
    board = chess.Board()
    played_move = chess.Move.from_uci("e2e4")
    engine_analysis = _depth_analysis(
        board,
        played_uci=played_move.uci(),
        budget_depth=MIN_STOCKFISH_DEPTH,
        line_depth=MIN_STOCKFISH_DEPTH - 1,
    )

    verification = EvidenceVerifier().verify_engine_analysis(board, played_move, engine_analysis)

    assert "engine_depth_below_minimum" in _issue_codes(verification)


def test_verifier_rejects_node_limited_real_engine_lines_without_depth() -> None:
    board = chess.Board()
    played_move = chess.Move.from_uci("e2e4")
    engine_analysis = _node_analysis_without_depth(board, played_uci=played_move.uci())

    verification = EvidenceVerifier().verify_engine_analysis(board, played_move, engine_analysis)

    assert "engine_depth_below_minimum" in _issue_codes(verification)


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


def test_verifier_rejects_mismatched_llm_player_level() -> None:
    result = _valid_result()
    llm_context = result.llm_context.model_copy(update={"player_level": "2800 blitz"})

    verification = EvidenceVerifier().verify(result.evidence, llm_context)

    assert _issue_codes(verification) == {"llm_context_inconsistent"}


def test_verifier_rejects_mismatched_llm_time_situation() -> None:
    result = _valid_result()
    llm_context = result.llm_context.model_copy(update={"time_situation": "time_scramble"})

    verification = EvidenceVerifier().verify(result.evidence, llm_context)

    assert _issue_codes(verification) == {"llm_context_inconsistent"}


def test_verifier_rejects_mismatched_llm_human_note() -> None:
    result = _valid_result()
    llm_context = result.llm_context.model_copy(update={"human_note": "unsupported coaching note"})

    verification = EvidenceVerifier().verify(result.evidence, llm_context)

    assert _issue_codes(verification) == {"llm_context_inconsistent"}


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


def _depth_analysis(
    board: chess.Board,
    played_uci: str,
    budget_depth: int,
    line_depth: int,
) -> EngineAnalysis:
    played_move = chess.Move.from_uci(played_uci)
    after_board = board.copy(stack=False)
    after_board.push(played_move)
    return EngineAnalysis(
        engine_version="Stockfish test",
        analysis_budget=EngineAnalysisBudget(kind="depth", value=budget_depth, multipv=1),
        top_lines=[
            _engine_line_with_metadata(
                board,
                played_uci,
                depth=line_depth,
                nodes=1_000,
                rank=1,
            )
        ],
        played_line=_engine_line_with_metadata(
            board,
            played_uci,
            depth=line_depth,
            nodes=1_000,
        ),
        after_line=_engine_line_with_metadata(
            after_board,
            "e7e5",
            depth=line_depth,
            nodes=1_000,
            rank=1,
        ),
    )


def _node_analysis_without_depth(board: chess.Board, played_uci: str) -> EngineAnalysis:
    played_move = chess.Move.from_uci(played_uci)
    after_board = board.copy(stack=False)
    after_board.push(played_move)
    return EngineAnalysis(
        engine_version="Stockfish test",
        analysis_budget=EngineAnalysisBudget(kind="nodes", value=1_000_000, multipv=1),
        top_lines=[_engine_line_with_metadata(board, played_uci, depth=None, nodes=1_000, rank=1)],
        played_line=_engine_line_with_metadata(
            board,
            played_uci,
            depth=None,
            nodes=1_000,
        ),
        after_line=_engine_line_with_metadata(
            after_board,
            "e7e5",
            depth=None,
            nodes=1_000,
            rank=1,
        ),
    )


def _engine_line_with_metadata(
    board: chess.Board,
    uci: str,
    depth: int | None,
    nodes: int | None,
    rank: int | None = None,
) -> EngineLine:
    move = chess.Move.from_uci(uci)
    return EngineLine(
        move_uci=uci,
        move_san=board.san(move),
        score=Score.cp(10),
        rank=rank,
        pv_uci=[uci],
        pv_san=[board.san(move)],
        depth=depth,
        nodes=nodes,
    )
