from __future__ import annotations

from dataclasses import dataclass

import chess

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    ColorName,
    ContextResult,
    EngineAnalysis,
    EngineAnalysisBudget,
    EngineLine,
    HumanMoveLikelihood,
    MoveContextRequest,
    PlayerLevel,
    Score,
    Wdl,
)


def engine_line(
    board: chess.Board,
    uci: str,
    cp: int,
    rank: int | None = None,
    wdl: Wdl | None = None,
    pv_uci: list[str] | None = None,
) -> EngineLine:
    move = chess.Move.from_uci(uci)
    assert move in board.legal_moves
    full_pv_uci = pv_uci or [uci]
    return EngineLine(
        move_uci=uci,
        move_san=board.san(move),
        score=Score.cp(cp),
        rank=rank,
        wdl=wdl,
        pv_uci=full_pv_uci,
        pv_san=pv_san(board, full_pv_uci),
    )


def analysis(
    board: chess.Board,
    played_uci: str,
    top_scores: list[tuple[str, int]],
    played_score: int,
    after_reply_uci: str | None = None,
    played_pv_uci: list[str] | None = None,
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
        played_line=engine_line(board, played_uci, played_score, rank=None, pv_uci=played_pv_uci),
        after_line=engine_line(after_board, after_reply_uci, played_score, rank=1)
        if after_reply_uci
        else None,
    )


def pv_san(board: chess.Board, pv_uci: list[str]) -> list[str]:
    replay = board.copy(stack=False)
    san_moves: list[str] = []
    for uci in pv_uci:
        move = chess.Move.from_uci(uci)
        assert move in replay.legal_moves
        san_moves.append(replay.san(move))
        replay.push(move)
    return san_moves


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


def na4_tactical_objection_context() -> ContextResult:
    """Return a static Byrne-Fischer 11...Na4 context with a verified Nxa4 objection."""

    board = chess.Board("r2q1rk1/pp2ppbp/1np2np1/2Q3B1/3PP1b1/2N2N2/PP3PPP/3RKB1R b K - 6 11")
    after_board = board.copy(stack=False)
    after_board.push(chess.Move.from_uci("b6a4"))
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=2),
        top_lines=[
            engine_line(
                board,
                "b6a4",
                250,
                rank=1,
                pv_uci=["b6a4", "c5a3", "a4c3"],
            ),
            engine_line(board, "d8d6", 80, rank=2),
        ],
        played_line=engine_line(
            board,
            "b6a4",
            250,
            rank=None,
            pv_uci=["b6a4", "c5a3", "a4c3"],
        ),
        after_line=engine_line(after_board, "c5a3", 250, rank=1),
        opponent_reply_lines=[
            engine_line(
                after_board,
                "c3a4",
                280,
                rank=None,
                pv_uci=["c3a4", "f6e4"],
            )
        ],
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="b6a4",
        player_color="black",
        player_level=PlayerLevel.rating(2300, "historical-demo"),
        opponent_level=PlayerLevel.rating(2400, "historical-demo"),
        time_control="classical",
    )
    return MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)
