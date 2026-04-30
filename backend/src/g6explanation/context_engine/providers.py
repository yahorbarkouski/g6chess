"""Analysis provider interfaces, Stockfish, and Maia-2 integrations."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any, Literal, Protocol

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
        """Return human move probabilities keyed by UCI move.

        Providers may include additional legal moves, such as top human-likeness
        moves, when they have evidence for them.
        """


@dataclass(frozen=True)
class StockfishAnalyzer:
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
            raise ValueError("StockfishAnalyzer requires either depth or nodes.")
        if self.depth is not None and self.nodes is not None:
            raise ValueError("StockfishAnalyzer accepts depth or nodes, not both.")
        if self.multipv < 1:
            raise ValueError("multipv must be at least 1.")

    def analyze(
        self, board: chess.Board, played_move: chess.Move, player_color: ColorName
    ) -> EngineAnalysis:
        try:
            with chess.engine.SimpleEngine.popen_uci(self.binary_path) as engine:
                applied_options = self._configure_engine(engine)
                limit = self._limit()
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

    def _analysis_budget(self) -> dict[str, int | str | bool | None]:
        if self.nodes is not None:
            return {"kind": "nodes", "value": self.nodes, "multipv": self.multipv}
        return {"kind": "depth", "value": self.depth, "multipv": self.multipv}

    def _requested_options(self) -> dict[str, int | str | bool]:
        options: dict[str, int | str | bool] = {"UCI_ShowWDL": self.show_wdl}
        if self.threads is not None:
            options["Threads"] = self.threads
        if self.hash_mb is not None:
            options["Hash"] = self.hash_mb
        if self.syzygy_path:
            options["SyzygyPath"] = self.syzygy_path
        return options

    def _configure_engine(
        self, engine: chess.engine.SimpleEngine
    ) -> dict[str, int | str | bool | None]:
        requested = self._requested_options()
        supported = {name: value for name, value in requested.items() if name in engine.options}
        if supported:
            with suppress(chess.engine.EngineError):
                engine.configure(supported)
        return supported


@dataclass
class Maia2ProbabilityProvider:
    model_type: Literal["auto", "rapid", "blitz"] = "auto"
    device: Literal["cpu", "gpu"] = "cpu"
    save_root: str = "./maia2_models"
    top_move_limit: int = 5
    _model: Any = field(default=None, init=False, repr=False)
    _prepared: Any = field(default=None, init=False, repr=False)
    _inference_each: Any = field(default=None, init=False, repr=False)
    _loaded_model_type: str | None = field(default=None, init=False, repr=False)

    def probabilities(
        self,
        board: chess.Board,
        candidate_moves: list[chess.Move],
        request: MoveContextRequest,
    ) -> dict[str, HumanMoveStats]:
        model_type = self._select_model_type(request)
        self._load(model_type)
        elo_self = _rating_or_default(request.player_level)
        elo_opponent = (
            _rating_or_default(request.opponent_level) if request.opponent_level else elo_self
        )
        plus_400 = elo_self + 400

        move_probs, _ = self._inference_each(
            self._model, self._prepared, board.fen(), elo_self, elo_opponent
        )
        plus_400_probs, _ = self._inference_each(
            self._model, self._prepared, board.fen(), plus_400, elo_opponent
        )
        legal_uci = {move.uci() for move in board.legal_moves}
        ranked_uci = [uci for uci in move_probs if uci in legal_uci][: self.top_move_limit]
        candidate_uci = {move.uci() for move in candidate_moves}
        included_uci = candidate_uci | set(ranked_uci)
        package_version = _package_version("maia2")
        ranks = {uci: rank for rank, uci in enumerate(move_probs, start=1) if uci in legal_uci}

        return {
            uci: HumanMoveStats(
                player_level_probability=move_probs.get(uci),
                plus_400_probability=plus_400_probs.get(uci),
                evidence_source=f"maia2_{model_type}",
                model_type=model_type,
                model_version=package_version,
                rank=ranks.get(uci),
                is_top_human_move=uci in ranked_uci,
            )
            for uci in included_uci
            if uci in legal_uci
        }

    def _select_model_type(self, request: MoveContextRequest) -> Literal["rapid", "blitz"]:
        if self.model_type in {"rapid", "blitz"}:
            return self.model_type
        control = (request.time_control or "").lower()
        if "bullet" in control or "blitz" in control:
            return "blitz"
        return "rapid"

    def _load(self, model_type: Literal["rapid", "blitz"]) -> None:
        if self._model is not None and self._loaded_model_type == model_type:
            return
        try:
            from maia2 import inference, model
        except ModuleNotFoundError as exc:
            raise AnalysisError(
                "Maia2ProbabilityProvider requires the optional maia2==0.9 package. "
                "Install the project with the 'maia' extra to enable it."
            ) from exc
        self._model = model.from_pretrained(
            type=model_type,
            device=self.device,
            save_root=self.save_root,
        )
        self._prepared = inference.prepare()
        self._inference_each = inference.inference_each
        self._loaded_model_type = model_type


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
        depth=_optional_int(info.get("depth")),
        seldepth=_optional_int(info.get("seldepth")),
        nodes=_optional_int(info.get("nodes")),
        nps=_optional_int(info.get("nps")),
        tbhits=_optional_int(info.get("tbhits")),
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


def _rating_or_default(level: Any) -> int:
    if level is not None:
        rating = level.rating_value()
        if rating is not None:
            return rating
    return 1500


def _package_version(package_name: str) -> str | None:
    with suppress(metadata.PackageNotFoundError):
        return metadata.version(package_name)
    return None


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None
