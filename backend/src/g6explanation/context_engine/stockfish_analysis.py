"""Stockfish analysis provider."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass

import chess
import chess.engine

from g6explanation.context_engine.contracts import (
    ColorName,
    EngineAnalysis,
    EngineAnalysisBudget,
    EngineLine,
    EngineOptionValue,
    Score,
    Wdl,
)
from g6explanation.context_engine.exceptions import AnalysisError
from g6explanation.context_engine.position_reconstruction import chess_color


@dataclass(frozen=True)
class StockfishAnalysisProvider:
    binary_path: str = "stockfish"
    depth: int | None = 12
    nodes: int | None = None
    multipv: int = 5
    threads: int | None = None
    hash_mb: int | None = None
    show_wdl: bool = True
    syzygy_path: str | None = None

    def __post_init__(self) -> None:
        if self.depth is None and self.nodes is None:
            raise ValueError("StockfishAnalysisProvider requires either depth or nodes.")
        if self.depth is not None and self.nodes is not None:
            raise ValueError("StockfishAnalysisProvider accepts depth or nodes, not both.")
        if self.multipv < 1:
            raise ValueError("multipv must be at least 1.")

    def analyze(
        self, board: chess.Board, played_move: chess.Move, player_color: ColorName
    ) -> EngineAnalysis:
        try:
            with chess.engine.SimpleEngine.popen_uci(self.binary_path) as engine:
                applied_options = self._configure_engine(engine)
                limit = self._limit()
                raw_top_infos = engine.analyse(board, limit, multipv=self.multipv)
                top_infos = list(raw_top_infos)
                played_info = engine.analyse(board, limit, root_moves=[played_move])

                after_board = board.copy(stack=False)
                after_board.push(played_move)
                after_info = (
                    None if after_board.is_game_over() else engine.analyse(after_board, limit)
                )

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
        after_line = (
            None
            if after_info is None
            else _line_from_info(
                after_board,
                after_info,
                rank=1,
                player_color=player_color,
            )
        )
        return EngineAnalysis(
            engine_version=engine_name,
            analysis_budget=self._analysis_budget(),
            engine_options=applied_options,
            top_lines=top_lines,
            played_line=played_line,
            after_line=after_line,
        )

    def analyze_root_moves(
        self,
        board: chess.Board,
        root_moves: list[chess.Move],
        player_color: ColorName,
    ) -> list[EngineLine]:
        legal_root_moves = [move for move in root_moves if move in board.legal_moves]
        if not legal_root_moves:
            return []
        try:
            with chess.engine.SimpleEngine.popen_uci(self.binary_path) as engine:
                self._configure_engine(engine)
                limit = self._limit()
                return [
                    _line_from_info(
                        board,
                        engine.analyse(board, limit, root_moves=[move]),
                        rank=None,
                        player_color=player_color,
                        fallback_move=move,
                    )
                    for move in legal_root_moves
                ]
        except FileNotFoundError as exc:
            raise AnalysisError(f"Stockfish binary not found: {self.binary_path}") from exc
        except chess.engine.EngineError as exc:
            raise AnalysisError(f"Stockfish supplemental analysis failed: {exc}") from exc

    def _limit(self) -> chess.engine.Limit:
        if self.nodes is not None:
            return chess.engine.Limit(nodes=self.nodes)
        return chess.engine.Limit(depth=self.depth)

    def _analysis_budget(self) -> EngineAnalysisBudget:
        if self.nodes is not None:
            return EngineAnalysisBudget(kind="nodes", value=self.nodes, multipv=self.multipv)
        return EngineAnalysisBudget(kind="depth", value=self.depth, multipv=self.multipv)

    def _requested_options(self) -> dict[str, EngineOptionValue]:
        options: dict[str, EngineOptionValue] = {"UCI_ShowWDL": self.show_wdl}
        if self.threads is not None:
            options["Threads"] = self.threads
        if self.hash_mb is not None:
            options["Hash"] = self.hash_mb
        if self.syzygy_path:
            options["SyzygyPath"] = self.syzygy_path
        return options

    def _configure_engine(self, engine: chess.engine.SimpleEngine) -> dict[str, EngineOptionValue]:
        requested = self._requested_options()
        supported = {name: value for name, value in requested.items() if name in engine.options}
        if supported:
            with suppress(chess.engine.EngineError):
                engine.configure(supported)
        return supported


def _line_from_info(
    board: chess.Board,
    info: chess.engine.InfoDict,
    rank: int | None,
    player_color: ColorName,
    fallback_move: chess.Move | None = None,
) -> EngineLine:
    pv = _pv_from_info(info)
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
    if not isinstance(score_obj, chess.engine.PovScore):
        raise AnalysisError("Engine analysis did not include a score.")

    return EngineLine(
        move_uci=move.uci(),
        move_san=board.san(move),
        score=_score_from_engine(score_obj, player_color),
        rank=rank,
        wdl=_wdl_from_info(info, player_color),
        pv_uci=[pv_move.uci() for pv_move in pv],
        pv_san=_pv_to_san(board, pv),
        depth=_optional_int(info.get("depth")),
        seldepth=_optional_int(info.get("seldepth")),
        nodes=_optional_int(info.get("nodes")),
        nps=_optional_int(info.get("nps")),
        tbhits=_optional_int(info.get("tbhits")),
    )


def _pv_from_info(info: chess.engine.InfoDict) -> list[chess.Move]:
    pv = info.get("pv")
    if pv is None:
        return []
    return list(pv)


def _score_from_engine(score_obj: chess.engine.PovScore, player_color: ColorName) -> Score:
    pov = score_obj.pov(chess_color(player_color))
    mate = pov.mate()
    if mate is not None:
        return Score.mate(mate_in=abs(mate), mate_for="player" if mate > 0 else "opponent")
    cp = pov.score()
    if cp is None:
        raise AnalysisError("Engine score was neither centipawn nor mate.")
    return Score.cp(cp)


def _wdl_from_info(info: chess.engine.InfoDict, player_color: ColorName) -> Wdl | None:
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


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None
