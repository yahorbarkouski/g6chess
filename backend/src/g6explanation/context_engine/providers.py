"""Analysis provider interfaces and Stockfish implementation."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol

import chess
import chess.engine

from g6explanation.context_engine.board import chess_color
from g6explanation.context_engine.exceptions import AnalysisError
from g6explanation.context_engine.models import (
    ColorName,
    EngineAnalysis,
    EngineLine,
    HumanMoveStats,
    MoveContextRequest,
    Score,
    Wdl,
)


class EngineAnalyzer(Protocol):
    def analyze(
        self, board: chess.Board, played_move: chess.Move, player_color: ColorName
    ) -> EngineAnalysis:
        """Analyze the move from the board before it is played."""


class HumanMoveProbabilityProvider(Protocol):
    def probabilities(
        self,
        board: chess.Board,
        candidate_moves: list[chess.Move],
        request: MoveContextRequest,
    ) -> dict[str, HumanMoveStats]:
        """Return human move probabilities keyed by UCI move."""


@dataclass(frozen=True)
class StockfishAnalyzer:
    binary_path: str = "stockfish"
    depth: int = 12
    multipv: int = 5

    def analyze(
        self, board: chess.Board, played_move: chess.Move, player_color: ColorName
    ) -> EngineAnalysis:
        try:
            with chess.engine.SimpleEngine.popen_uci(self.binary_path) as engine:
                with suppress(chess.engine.EngineError):
                    engine.configure({"UCI_ShowWDL": True})

                limit = chess.engine.Limit(depth=self.depth)
                top_infos = engine.analyse(board, limit, multipv=self.multipv)
                if isinstance(top_infos, dict):
                    top_infos = [top_infos]
                played_info = engine.analyse(board, limit, root_moves=[played_move])

                after_board = board.copy(stack=False)
                after_board.push(played_move)
                after_info = engine.analyse(after_board, limit)

                engine_name = engine.id.get("name", "Stockfish")
        except FileNotFoundError as exc:
            raise AnalysisError(f"Stockfish binary not found: {self.binary_path}") from exc
        except chess.engine.EngineError as exc:
            raise AnalysisError(f"Stockfish analysis failed: {exc}") from exc

        top_lines = [
            _line_from_info(board, info, rank=index + 1, player_color=player_color)
            for index, info in enumerate(top_infos)
        ]
        played_line = _line_from_info(
            board,
            played_info,
            rank=None,
            player_color=player_color,
            fallback_move=played_move,
        )
        after_line = _line_from_info(
            after_board,
            after_info,
            rank=1,
            player_color=player_color,
        )
        return EngineAnalysis(
            engine_version=engine_name,
            analysis_budget={"kind": "depth", "value": self.depth, "multipv": self.multipv},
            top_lines=top_lines,
            played_line=played_line,
            after_line=after_line,
        )


def _line_from_info(
    board: chess.Board,
    info: dict,
    rank: int | None,
    player_color: ColorName,
    fallback_move: chess.Move | None = None,
) -> EngineLine:
    pv = list(info.get("pv") or [])
    if not pv and fallback_move is not None:
        pv = [fallback_move]
    if not pv:
        raise AnalysisError("Engine analysis did not include a principal variation.")

    move = pv[0]
    if move not in board.legal_moves:
        raise AnalysisError(
            f"Engine returned illegal move {move.uci()} for position {board.fen()}."
        )

    score_obj = info.get("score")
    if score_obj is None:
        raise AnalysisError("Engine analysis did not include a score.")

    return EngineLine(
        move_uci=move.uci(),
        move_san=board.san(move),
        score=_score_from_engine(score_obj, player_color),
        rank=rank,
        wdl=_wdl_from_info(info, player_color),
        pv_uci=[pv_move.uci() for pv_move in pv],
        pv_san=_pv_to_san(board, pv),
    )


def _score_from_engine(score_obj: chess.engine.PovScore, player_color: ColorName) -> Score:
    pov = score_obj.pov(chess_color(player_color))
    mate = pov.mate()
    if mate is not None:
        return Score.mate(mate_in=abs(mate), mate_for="player" if mate > 0 else "opponent")
    cp = pov.score()
    if cp is None:
        raise AnalysisError("Engine score was neither centipawn nor mate.")
    return Score.cp(cp)


def _wdl_from_info(info: dict, player_color: ColorName) -> Wdl | None:
    wdl_obj = info.get("wdl")
    if wdl_obj is None:
        return None
    try:
        pov = wdl_obj.pov(chess_color(player_color))
        return Wdl(win=pov.wins, draw=pov.draws, loss=pov.losses)
    except AttributeError:
        return None


def _pv_to_san(board: chess.Board, pv: list[chess.Move]) -> list[str]:
    replay = board.copy(stack=False)
    san_moves: list[str] = []
    for move in pv:
        if move not in replay.legal_moves:
            break
        san_moves.append(replay.san(move))
        replay.push(move)
    return san_moves
