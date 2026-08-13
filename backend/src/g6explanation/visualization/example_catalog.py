"""Real-game experiments for the context visualization API."""

from __future__ import annotations

import importlib.util
import io
import os
import shutil
from dataclasses import dataclass
from textwrap import dedent
from typing import Literal, cast

import chess
import chess.pgn

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    ColorName,
    MoveContextRequest,
    PlayerLevel,
)
from g6explanation.context_engine.maia_likelihood import Maia2MoveLikelihoodProvider, MaiaModelType
from g6explanation.context_engine.stockfish_analysis import (
    MIN_STOCKFISH_DEPTH,
    StockfishAnalysisProvider,
)
from g6explanation.visualization.contracts import (
    VisualizationExample,
    VisualizationMove,
    VisualizationMoveContext,
)

OPERA_GAME = dedent(
    """
    [Event "Casual Game"]
    [Site "Paris FRA"]
    [Date "1858.??.??"]
    [Round "?"]
    [White "Paul Morphy"]
    [Black "Duke Karl / Count Isouard"]
    [Result "1-0"]

    1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5
    6. Bc4 Nf6 7. Qb3 Qe7 8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5
    11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 14. Rd1 Qe6
    15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0
    """
).strip()

BYRNE_FISCHER = dedent(
    """
    [Event "Third Rosenwald Trophy"]
    [Site "New York, NY USA"]
    [Date "1956.10.17"]
    [Round "8"]
    [White "Donald Byrne"]
    [Black "Robert James Fischer"]
    [Result "0-1"]

    1. Nf3 Nf6 2. c4 g6 3. Nc3 Bg7 4. d4 O-O 5. Bf4 d5
    6. Qb3 dxc4 7. Qxc4 c6 8. e4 Nbd7 9. Rd1 Nb6 10. Qc5 Bg4
    11. Bg5 Na4 12. Qa3 Nxc3 13. bxc3 Nxe4 14. Bxe7 Qb6
    15. Bc4 Nxc3 16. Bc5 Rfe8+ 17. Kf1 Be6 18. Bxb6 Bxc4+
    19. Kg1 Ne2+ 20. Kf1 Nxd4+ 21. Kg1 Ne2+ 22. Kf1 Nc3+
    23. Kg1 axb6 24. Qb4 Ra4 25. Qxb6 Nxd1 26. h3 Rxa2
    27. Kh2 Nxf2 28. Re1 Rxe1 29. Qd8+ Bf8 30. Nxe1 Bd5
    31. Nf3 Ne4 32. Qb8 b5 33. h4 h5 34. Ne5 Kg7 35. Kg1 Bc5+
    36. Kf1 Ng3+ 37. Ke1 Bb4+ 38. Kd1 Bb3+ 39. Kc1 Ne2+
    40. Kb1 Nc3+ 41. Kc1 Rc2# 0-1
    """
).strip()

KASPAROV_TOPALOV = dedent(
    """
    [Event "Hoogovens Group A"]
    [Site "Wijk aan Zee NED"]
    [Date "1999.01.20"]
    [Round "4"]
    [White "Garry Kasparov"]
    [Black "Veselin Topalov"]
    [Result "1-0"]

    1. e4 d6 2. d4 Nf6 3. Nc3 g6 4. Be3 Bg7 5. Qd2 c6
    6. f3 b5 7. Nge2 Nbd7 8. Bh6 Bxh6 9. Qxh6 Bb7
    10. a3 e5 11. O-O-O Qe7 12. Kb1 a6 13. Nc1 O-O-O
    14. Nb3 exd4 15. Rxd4 c5 16. Rd1 Nb6 17. g3 Kb8
    18. Na5 Ba8 19. Bh3 d5 20. Qf4+ Ka7 21. Rhe1 d4
    22. Nd5 Nbxd5 23. exd5 Qd6 24. Rxd4 cxd4 25. Re7+ Kb6
    26. Qxd4+ Kxa5 27. b4+ Ka4 28. Qc3 Qxd5 29. Ra7 Bb7
    30. Rxb7 Qc4 31. Qxf6 Kxa3 32. Qxa6+ Kxb4 33. c3+ Kxc3
    34. Qa1+ Kd2 35. Qb2+ Kd1 36. Bf1 Rd2 37. Rd7 Rxd7
    38. Bxc4 bxc4 39. Qxh8 Rd3 40. Qa8 c3 41. Qa4+ Ke1
    42. f4 f5 43. Kc1 Rd2 44. Qa7 1-0
    """
).strip()


class VisualizationSetupError(RuntimeError):
    """Raised when the local production analysis stack is unavailable."""


@dataclass(frozen=True)
class RealGameExperiment:
    id: str
    title: str
    summary: str
    source: str
    pgn: str
    orientation: ColorName
    player_level: PlayerLevel
    time_control: str
    tags: tuple[str, ...]


EXPERIMENTS: tuple[RealGameExperiment, ...] = (
    RealGameExperiment(
        id="morphy-opera-1858",
        title="Morphy Opera Game, 1858",
        summary="Full-game context inspection for Paul Morphy's famous attacking game.",
        source="PGN: Paul Morphy vs Duke Karl / Count Isouard, Paris 1858",
        pgn=OPERA_GAME,
        orientation="white",
        player_level=PlayerLevel.rating(2400, "historical-demo"),
        time_control="classical",
        tags=("real game", "famous", "attack"),
    ),
    RealGameExperiment(
        id="byrne-fischer-1956",
        title="Byrne-Fischer Game of the Century, 1956",
        summary="Full-game context inspection for Fischer's tactical win over Donald Byrne.",
        source="PGN: Donald Byrne vs Robert James Fischer, New York 1956",
        pgn=BYRNE_FISCHER,
        orientation="black",
        player_level=PlayerLevel.rating(2400, "historical-demo"),
        time_control="classical",
        tags=("real game", "famous", "tactics"),
    ),
    RealGameExperiment(
        id="kasparov-topalov-1999",
        title="Kasparov-Topalov, Wijk aan Zee 1999",
        summary="Full-game context inspection for Kasparov's celebrated rook sacrifice game.",
        source="PGN: Garry Kasparov vs Veselin Topalov, Wijk aan Zee 1999",
        pgn=KASPAROV_TOPALOV,
        orientation="white",
        player_level=PlayerLevel.rating(2700, "historical-demo"),
        time_control="classical",
        tags=("real game", "famous", "sacrifice"),
    ),
)


def visualization_examples() -> list[VisualizationExample]:
    """Return real-game experiment metadata without precomputed context packets."""

    return [_build_example_metadata(experiment) for experiment in EXPERIMENTS]


def find_visualization_example(example_id: str) -> VisualizationExample | None:
    """Find one real-game experiment by ID without building context packets."""

    experiment = _find_experiment(example_id)
    if experiment is None:
        return None
    return _build_example_metadata(experiment)


def build_visualization_context(example_id: str, ply: int) -> VisualizationMoveContext | None:
    """Build a fresh production context packet for one real-game ply."""

    experiment = _find_experiment(example_id)
    if experiment is None:
        return None
    moves = _mainline_moves(experiment.pgn)
    if ply < 1 or ply > len(moves):
        return None

    board = _board_before_ply(experiment.pgn, ply)
    request = MoveContextRequest(
        pgn=experiment.pgn,
        ply=ply,
        player_color=_color_name(board.turn),
        player_level=experiment.player_level,
        time_control=experiment.time_control,
    )
    return VisualizationMoveContext(ply=ply, result=_production_builder().build(request))


def _find_experiment(example_id: str) -> RealGameExperiment | None:
    return next((experiment for experiment in EXPERIMENTS if experiment.id == example_id), None)


def _build_example_metadata(experiment: RealGameExperiment) -> VisualizationExample:
    game = _read_game(experiment.pgn)
    board = game.board()
    moves: list[VisualizationMove] = []
    for ply, move in enumerate(game.mainline_moves(), start=1):
        fen_before = board.fen()
        san = board.san(move)
        player_color = _color_name(board.turn)
        board.push(move)
        moves.append(
            VisualizationMove(
                ply=ply,
                uci=move.uci(),
                san=san,
                fen_before=fen_before,
                fen_after=board.fen(),
                player_color=player_color,
                has_context=True,
            )
        )

    return VisualizationExample(
        id=experiment.id,
        title=experiment.title,
        summary=experiment.summary,
        source=experiment.source,
        initial_fen=game.board().fen(),
        orientation=experiment.orientation,
        player_level=experiment.player_level.label(),
        tags=list(experiment.tags),
        moves=moves,
        contexts=[],
    )


def _production_builder() -> MoveContextBuilder:
    stockfish_binary = os.getenv("G6_VISUALIZATION_STOCKFISH_BINARY") or shutil.which("stockfish")
    if stockfish_binary is None:
        raise VisualizationSetupError(
            "Stockfish is required for visualization context generation. "
            "Install stockfish or set G6_VISUALIZATION_STOCKFISH_BINARY."
        )

    analysis = StockfishAnalysisProvider(
        binary_path=stockfish_binary,
        depth=_int_env("G6_VISUALIZATION_STOCKFISH_DEPTH", MIN_STOCKFISH_DEPTH),
        multipv=_int_env("G6_VISUALIZATION_STOCKFISH_MULTIPV", 5),
        threads=_optional_int_env("G6_VISUALIZATION_STOCKFISH_THREADS"),
        hash_mb=_optional_int_env("G6_VISUALIZATION_STOCKFISH_HASH_MB"),
        show_wdl=True,
    )
    return MoveContextBuilder(analysis, _maia_provider())


def _maia_provider() -> Maia2MoveLikelihoodProvider:
    if importlib.util.find_spec("maia2") is None:
        raise VisualizationSetupError(
            "Maia-2 is required for production visualization context generation. "
            "Install the project with the maia extra."
        )
    model_type = os.getenv("G6_VISUALIZATION_MAIA2_MODEL", "auto")
    if model_type not in {"auto", "rapid", "blitz"}:
        raise VisualizationSetupError(
            "G6_VISUALIZATION_MAIA2_MODEL must be one of: auto, rapid, blitz."
        )
    device = os.getenv("G6_VISUALIZATION_MAIA2_DEVICE", "cpu")
    if device not in {"cpu", "gpu"}:
        raise VisualizationSetupError("G6_VISUALIZATION_MAIA2_DEVICE must be cpu or gpu.")
    return Maia2MoveLikelihoodProvider(
        model_type=cast(MaiaModelType, model_type),
        device=cast("Literal['cpu', 'gpu']", device),
        save_root=os.getenv("MAIA2_MODEL_ROOT", "./maia2_models"),
        top_move_limit=_int_env("G6_VISUALIZATION_MAIA2_TOP_MOVES", 5),
    )


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _optional_int_env(name: str) -> int | None:
    value = os.getenv(name)
    return None if value is None else int(value)


def _read_game(pgn: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("Visualization PGN could not be parsed.")
    return game


def _mainline_moves(pgn: str) -> list[chess.Move]:
    return list(_read_game(pgn).mainline_moves())


def _board_before_ply(pgn: str, ply: int) -> chess.Board:
    game = _read_game(pgn)
    moves = list(game.mainline_moves())
    board = game.board()
    for move in moves[: ply - 1]:
        board.push(move)
    return board


def _color_name(color: chess.Color) -> ColorName:
    return "white" if color == chess.WHITE else "black"
