from __future__ import annotations

from dataclasses import dataclass

import chess

from g6explanation.context_engine.models import (
    EngineAnalysis,
    EngineLine,
    HumanMoveStats,
    MoveContextRequest,
    Score,
)


def engine_line(board: chess.Board, uci: str, cp: int, rank: int | None = None) -> EngineLine:
    move = chess.Move.from_uci(uci)
    assert move in board.legal_moves
    return EngineLine(
        move_uci=uci,
        move_san=board.san(move),
        score=Score.cp(cp),
        rank=rank,
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
        analysis_budget={"kind": "static", "value": 1, "multipv": len(top_scores)},
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
class StaticAnalyzer:
    engine_analysis: EngineAnalysis

    def analyze(
        self, board: chess.Board, played_move: chess.Move, player_color: str
    ) -> EngineAnalysis:
        return self.engine_analysis


@dataclass(frozen=True)
class StaticHumanProvider:
    stats: dict[str, HumanMoveStats]

    def probabilities(
        self,
        board: chess.Board,
        candidate_moves: list[chess.Move],
        request: MoveContextRequest,
    ) -> dict[str, HumanMoveStats]:
        return {
            move.uci(): self.stats[move.uci()]
            for move in candidate_moves
            if move.uci() in self.stats
        }
