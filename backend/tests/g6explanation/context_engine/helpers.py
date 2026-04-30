from __future__ import annotations

from dataclasses import dataclass

import chess

from g6explanation.context_engine.contracts import (
    ColorName,
    EngineAnalysis,
    EngineAnalysisBudget,
    EngineLine,
    HumanMoveLikelihood,
    MoveContextRequest,
    Score,
    Wdl,
)


def engine_line(
    board: chess.Board,
    uci: str,
    cp: int,
    rank: int | None = None,
    wdl: Wdl | None = None,
) -> EngineLine:
    move = chess.Move.from_uci(uci)
    assert move in board.legal_moves
    return EngineLine(
        move_uci=uci,
        move_san=board.san(move),
        score=Score.cp(cp),
        rank=rank,
        wdl=wdl,
        pv_uci=[uci],
        pv_san=[board.san(move)],
    )


def analysis(
    board: chess.Board,
    played_uci: str,
    top_scores: list[tuple[str, int]],
    played_score: int,
    after_reply_uci: str | None = None,
) -> EngineAnalysis:
    played_move = chess.Move.from_uci(played_uci)
    after_board = board.copy(stack=False)
    after_board.push(played_move)
    return EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=len(top_scores)),
        top_lines=[
            engine_line(board, move_uci, score, rank=index + 1)
            for index, (move_uci, score) in enumerate(top_scores)
        ],
        played_line=engine_line(board, played_uci, played_score, rank=None),
        after_line=engine_line(after_board, after_reply_uci, played_score, rank=1)
        if after_reply_uci
        else None,
    )


@dataclass(frozen=True)
class StaticAnalysisProvider:
    engine_analysis: EngineAnalysis

    def analyze(
        self, board: chess.Board, played_move: chess.Move, player_color: ColorName
    ) -> EngineAnalysis:
        return self.engine_analysis


@dataclass(frozen=True)
class StaticHumanLikelihoodProvider:
    stats: dict[str, HumanMoveLikelihood]

    def likelihoods(
        self,
        board: chess.Board,
        candidate_moves: list[chess.Move],
        request: MoveContextRequest,
    ) -> dict[str, HumanMoveLikelihood]:
        return {
            move.uci(): self.stats[move.uci()]
            for move in candidate_moves
            if move.uci() in self.stats
        }
