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
    calculate_significance,
    choose_key_candidate,
    classify_quality,
    time_situation,
)
from g6explanation.context_engine.models import (
    CandidateMove,
    ContextResult,
    EngineAnalysis,
    EngineLine,
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
        human_candidate_limit: int = 3,
    ) -> None:
        self._analyzer = analyzer
        self._human_provider = human_provider
        self._human_candidate_limit = human_candidate_limit

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
        supplemental_lines = self._supplemental_human_lines(
            board=board,
            analysis=analysis,
            human_stats=human_stats,
            player_color=request.player_color,
        )

        situation = time_situation(request)
        quality = classify_quality(analysis, board_context.played)
        significance = calculate_significance(analysis, board_context.played)
        candidates = build_candidates(
            board=board,
            analysis=analysis,
            human_stats=human_stats,
            request=request,
            time_situation=situation,
            supplemental_lines=supplemental_lines,
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
            significance=significance,
            candidates=candidates,
            main_point=main_point,
            allowed_claims=allowed_claims,
        )
        llm_context = LLMContext(
            played=board_context.played.san,
            quality=quality.label,
            significance=significance,
            player_level=request.player_level.label(),
            time_situation=situation,
            severity=quality.severity_text,
            main_point=main_point.claim,
            best_or_key_move=_key_move_context(key_candidate),
            human_note=build_human_note(key_candidate, situation),
            allowed_claims=allowed_claims,
        )
        return ContextResult(evidence=evidence, llm_context=llm_context)

    def _supplemental_human_lines(
        self,
        board: chess.Board,
        analysis: EngineAnalysis,
        human_stats: dict[str, object],
        player_color: str,
    ) -> list[EngineLine]:
        if not hasattr(self._analyzer, "analyze_root_moves"):
            return []
        existing_uci = {
            *[line.move_uci for line in analysis.top_lines],
            analysis.played_line.move_uci,
        }
        ranked_extra_moves: list[chess.Move] = []
        for uci, stats in sorted(
            human_stats.items(),
            key=lambda item: (
                getattr(item[1], "rank", None) is None,
                getattr(item[1], "rank", 999) or 999,
            ),
        ):
            if uci in existing_uci or not getattr(stats, "is_top_human_move", False):
                continue
            move = chess.Move.from_uci(uci)
            if move in board.legal_moves:
                ranked_extra_moves.append(move)
            if len(ranked_extra_moves) >= self._human_candidate_limit:
                break
        if not ranked_extra_moves:
            return []
        lines = self._analyzer.analyze_root_moves(board, ranked_extra_moves, player_color)
        for line in lines:
            _validate_line_pv(board, line)
        return lines


def _validate_analysis(
    board: chess.Board, played_move: chess.Move, analysis: EngineAnalysis
) -> None:
    if not analysis.top_lines:
        raise AnalysisError("Engine analysis must include at least one top line.")
    if analysis.played_line.move_uci != played_move.uci():
        requested_move = played_move.uci()
        raise AnalysisError(
            f"Played line {analysis.played_line.move_uci} "
            f"does not match requested move {requested_move}."
        )
    for line in [*analysis.top_lines, analysis.played_line]:
        try:
            move = chess.Move.from_uci(line.move_uci)
        except ValueError as exc:
            raise AnalysisError(f"Engine line move {line.move_uci} is not valid UCI.") from exc
        if move not in board.legal_moves:
            raise AnalysisError(
                f"Engine line move {line.move_uci} is illegal before the played move."
            )
        _validate_line_pv(board, line)
    if analysis.after_line is not None:
        after_board = board.copy(stack=False)
        after_board.push(played_move)
        try:
            after_move = chess.Move.from_uci(analysis.after_line.move_uci)
        except ValueError as exc:
            raise AnalysisError(
                f"After-line move {analysis.after_line.move_uci} is not valid UCI."
            ) from exc
        if after_move not in after_board.legal_moves:
            raise AnalysisError(
                f"After-line move {analysis.after_line.move_uci} is illegal after the played move."
            )
        _validate_line_pv(after_board, analysis.after_line)


def _candidate_moves_from_analysis(
    board: chess.Board, analysis_move_uci: list[str]
) -> list[chess.Move]:
    moves: list[chess.Move] = []
    for uci in analysis_move_uci:
        move = chess.Move.from_uci(uci)
        if move in board.legal_moves:
            moves.append(move)
    return moves


def _validate_line_pv(board: chess.Board, line: EngineLine) -> None:
    if not line.pv_uci:
        return
    if line.pv_uci[0] != line.move_uci:
        raise AnalysisError(
            f"Engine line move {line.move_uci} does not match PV root {line.pv_uci[0]}."
        )
    replay = board.copy(stack=False)
    for uci in line.pv_uci:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise AnalysisError(f"PV move {uci} is not valid UCI.") from exc
        if move not in replay.legal_moves:
            raise AnalysisError(f"PV move {uci} is illegal when replayed.")
        replay.push(move)


def _key_move_context(candidate: CandidateMove | None) -> dict[str, str] | None:
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
    if candidate.recommendation_policy == "explain_as_hidden_resource":
        return "it is an important hidden resource that becomes more visible with stronger play"
    if candidate.time_adjusted_findability in {"hard", "very_hard", "engine_like"}:
        return "it is objectively important but hard to find"
    if candidate.score_loss_vs_best_cp == 0:
        return "it is the engine's best move"
    return "it is a better practical move"
