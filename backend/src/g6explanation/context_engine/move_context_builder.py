"""Context-engine evidence and LLM-context builder."""

from __future__ import annotations

import chess

from g6explanation.context_engine.candidate_policy import (
    build_candidates,
    choose_key_candidate,
    time_situation,
)
from g6explanation.context_engine.contracts import (
    ColorName,
    ContextResult,
    EngineAnalysis,
    EngineLine,
    EvidencePacket,
    HumanMoveLikelihood,
    LLMContext,
    MoveContextRequest,
)
from g6explanation.context_engine.exceptions import AnalysisError
from g6explanation.context_engine.explanation_agenda import (
    build_allowed_claims,
    build_human_note,
    build_key_move_context,
    build_main_point,
)
from g6explanation.context_engine.move_beauty import calculate_beauty
from g6explanation.context_engine.move_quality import calculate_significance, classify_quality
from g6explanation.context_engine.position_reconstruction import reconstruct_move_context
from g6explanation.context_engine.provider_protocols import (
    EngineAnalysisProvider,
    HumanMoveLikelihoodProvider,
    RootMoveAnalysisProvider,
)


class MoveContextBuilder:
    """Build evidence and LLM context for one move explanation."""

    def __init__(
        self,
        analysis_provider: EngineAnalysisProvider,
        human_likelihood_provider: HumanMoveLikelihoodProvider | None = None,
        human_candidate_limit: int = 3,
    ) -> None:
        self._analysis_provider = analysis_provider
        self._human_likelihood_provider = human_likelihood_provider
        self._human_candidate_limit = human_candidate_limit

    def build(self, request: MoveContextRequest) -> ContextResult:
        board, move, reconstructed = reconstruct_move_context(request)
        analysis = self._analysis_provider.analyze(board, move, request.player_color)
        _validate_analysis(board, move, analysis)
        candidate_moves = _candidate_moves_from_analysis(
            board, analysis_move_uci=[line.move_uci for line in analysis.top_lines]
        )
        if analysis.played_line.move_uci not in {candidate.uci() for candidate in candidate_moves}:
            candidate_moves.append(chess.Move.from_uci(analysis.played_line.move_uci))

        human_likelihoods: dict[str, HumanMoveLikelihood] = {}
        if self._human_likelihood_provider is not None:
            human_likelihoods = self._human_likelihood_provider.likelihoods(
                board, candidate_moves, request
            )
        supplemental_lines = self._supplemental_human_lines(
            board=board,
            analysis=analysis,
            human_likelihoods=human_likelihoods,
            player_color=request.player_color,
        )

        situation = time_situation(request)
        quality = classify_quality(analysis, reconstructed.played)
        significance = calculate_significance(analysis, reconstructed.played)
        beauty = calculate_beauty(
            board=board,
            analysis=analysis,
            played=reconstructed.played,
            quality=quality,
            significance=significance,
            human_likelihoods=human_likelihoods,
        )
        candidates = build_candidates(
            board=board,
            analysis=analysis,
            human_likelihoods=human_likelihoods,
            request=request,
            time_situation=situation,
            supplemental_lines=supplemental_lines,
        )
        key_candidate = choose_key_candidate(candidates, quality)
        main_point = build_main_point(board, reconstructed.played, quality, key_candidate, analysis)
        allowed_claims = build_allowed_claims(
            reconstructed.played, quality, key_candidate, analysis
        )
        evidence = EvidencePacket(
            context_version="move_context.v1",
            request=request,
            position=reconstructed.position,
            played=reconstructed.played,
            engine=analysis,
            quality=quality,
            significance=significance,
            beauty=beauty,
            candidates=candidates,
            main_point=main_point,
            allowed_claims=allowed_claims,
        )
        llm_context = LLMContext(
            played=reconstructed.played.san,
            quality=quality.label,
            significance=significance,
            beauty=beauty,
            player_level=request.player_level.label(),
            time_situation=situation,
            severity=quality.severity_text,
            main_point=main_point.claim,
            best_or_key_move=build_key_move_context(key_candidate),
            human_note=build_human_note(key_candidate, situation),
            allowed_claims=allowed_claims,
        )
        return ContextResult(evidence=evidence, llm_context=llm_context)

    def _supplemental_human_lines(
        self,
        board: chess.Board,
        analysis: EngineAnalysis,
        human_likelihoods: dict[str, HumanMoveLikelihood],
        player_color: ColorName,
    ) -> list[EngineLine]:
        if not isinstance(self._analysis_provider, RootMoveAnalysisProvider):
            return []
        existing_uci = {
            *[line.move_uci for line in analysis.top_lines],
            analysis.played_line.move_uci,
        }
        ranked_extra_moves: list[chess.Move] = []
        for uci, likelihood in sorted(
            human_likelihoods.items(),
            key=lambda item: (
                item[1].rank is None,
                item[1].rank or 999,
            ),
        ):
            if uci in existing_uci or not likelihood.is_top_human_move:
                continue
            move = chess.Move.from_uci(uci)
            if move in board.legal_moves:
                ranked_extra_moves.append(move)
            if len(ranked_extra_moves) >= self._human_candidate_limit:
                break
        if not ranked_extra_moves:
            return []
        lines = self._analysis_provider.analyze_root_moves(board, ranked_extra_moves, player_color)
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
