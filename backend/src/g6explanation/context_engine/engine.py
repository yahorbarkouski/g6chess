"""Context engine orchestration."""

from __future__ import annotations

import chess

from g6explanation.context_engine.board import reconstruct_board_context
from g6explanation.context_engine.exceptions import AnalysisError
from g6explanation.context_engine.heuristics import (
    build_allowed_claims,
    build_candidates,
    build_human_note,
    build_main_point,
    choose_key_candidate,
    classify_quality,
    time_situation,
)
from g6explanation.context_engine.models import (
    ContextResult,
    EvidencePacket,
    LLMContext,
    MoveContextRequest,
)
from g6explanation.context_engine.providers import EngineAnalyzer, HumanMoveProbabilityProvider


class MoveContextEngine:
    """Build evidence and LLM context for one move explanation."""

    def __init__(
        self,
        analyzer: EngineAnalyzer,
        human_provider: HumanMoveProbabilityProvider | None = None,
    ) -> None:
        self._analyzer = analyzer
        self._human_provider = human_provider

    def build(self, request: MoveContextRequest) -> ContextResult:
        board, move, board_context = reconstruct_board_context(request)
        analysis = self._analyzer.analyze(board, move, request.player_color)
        _validate_analysis(board, move, analysis)
        candidate_moves = _candidate_moves_from_analysis(
            board, analysis_move_uci=[line.move_uci for line in analysis.top_lines]
        )
        if analysis.played_line.move_uci not in {candidate.uci() for candidate in candidate_moves}:
            candidate_moves.append(chess.Move.from_uci(analysis.played_line.move_uci))

        human_stats = {}
        if self._human_provider is not None:
            human_stats = self._human_provider.probabilities(board, candidate_moves, request)

        situation = time_situation(request)
        quality = classify_quality(analysis, board_context.played)
        candidates = build_candidates(
            board=board,
            analysis=analysis,
            human_stats=human_stats,
            request=request,
            time_situation=situation,
        )
        key_candidate = choose_key_candidate(candidates, quality)
        main_point = build_main_point(board, board_context.played, quality, key_candidate, analysis)
        allowed_claims = build_allowed_claims(
            board_context.played, quality, key_candidate, analysis
        )
        evidence = EvidencePacket(
            context_version="move_context.v1",
            request=request,
            position=board_context.position,
            played=board_context.played,
            engine=analysis,
            quality=quality,
            candidates=candidates,
            main_point=main_point,
            allowed_claims=allowed_claims,
        )
        llm_context = LLMContext(
            played=board_context.played.san,
            quality=quality.label,
            player_level=request.player_level.label(),
            time_situation=situation,
            severity=quality.severity_text,
            main_point=main_point.claim,
            best_or_key_move=_key_move_context(key_candidate),
            human_note=build_human_note(key_candidate, situation),
            allowed_claims=allowed_claims,
        )
        return ContextResult(evidence=evidence, llm_context=llm_context)


def _validate_analysis(board: chess.Board, played_move: chess.Move, analysis) -> None:
    if not analysis.top_lines:
        raise AnalysisError("Engine analysis must include at least one top line.")
    if analysis.played_line.move_uci != played_move.uci():
        requested_move = played_move.uci()
        raise AnalysisError(
            f"Played line {analysis.played_line.move_uci} "
            f"does not match requested move {requested_move}."
        )
    for line in [*analysis.top_lines, analysis.played_line]:
        move = chess.Move.from_uci(line.move_uci)
        if move not in board.legal_moves:
            raise AnalysisError(
                f"Engine line move {line.move_uci} is illegal before the played move."
            )
    if analysis.after_line is not None:
        after_board = board.copy(stack=False)
        after_board.push(played_move)
        after_move = chess.Move.from_uci(analysis.after_line.move_uci)
        if after_move not in after_board.legal_moves:
            raise AnalysisError(
                f"After-line move {analysis.after_line.move_uci} is illegal after the played move."
            )


def _candidate_moves_from_analysis(
    board: chess.Board, analysis_move_uci: list[str]
) -> list[chess.Move]:
    moves: list[chess.Move] = []
    for uci in analysis_move_uci:
        move = chess.Move.from_uci(uci)
        if move in board.legal_moves:
            moves.append(move)
    return moves


def _key_move_context(candidate) -> dict[str, str] | None:
    if candidate is None:
        return None
    return {
        "move": candidate.san,
        "practicality": candidate.practicality,
        "findability": candidate.time_adjusted_findability,
        "reason": _key_move_reason(candidate),
        "recommendation_policy": candidate.recommendation_policy,
    }


def _key_move_reason(candidate) -> str:
    if candidate.practicality == "practical_try":
        return "it is close to the engine best move and more practical for the player"
    if candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
        return "it is objectively important but hard to find"
    if candidate.score_loss_vs_best_cp == 0:
        return "it is the engine's best move"
    return "it is a better practical move"
