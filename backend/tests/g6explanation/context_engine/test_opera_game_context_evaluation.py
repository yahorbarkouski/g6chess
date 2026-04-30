from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
from textwrap import dedent
from typing import Literal, cast

import chess
import chess.pgn
import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import ColorName, MoveContextRequest, PlayerLevel
from g6explanation.context_engine.maia_likelihood import Maia2MoveLikelihoodProvider, MaiaModelType
from g6explanation.context_engine.stockfish_analysis import (
    MIN_STOCKFISH_DEPTH,
    StockfishAnalysisProvider,
)

STOCKFISH = os.getenv("G6_OPERA_EVAL_STOCKFISH_BINARY") or shutil.which("stockfish")
HAS_MAIA2 = importlib.util.find_spec("maia2") is not None

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


@pytest.mark.skipif(
    os.getenv("G6EXPLANATION_RUN_OPERA_EVAL") != "1" or STOCKFISH is None or not HAS_MAIA2,
    reason=(
        "Opera full-game context eval requires G6EXPLANATION_RUN_OPERA_EVAL=1, "
        "Stockfish, maia2, and local Maia models."
    ),
)
def test_prints_opera_game_context_for_every_move() -> None:
    builder = _production_like_builder()
    game = _read_game(OPERA_GAME)
    board = game.board()

    print("\n=== Opera Game full context evaluation ===", flush=True)
    for ply, move in enumerate(game.mainline_moves(), start=1):
        fen_before = board.fen()
        san = board.san(move)
        player_color = _color_name(board.turn)
        result = builder.build(
            MoveContextRequest(
                pgn=OPERA_GAME,
                ply=ply,
                player_color=player_color,
                player_level=PlayerLevel.rating(2400, "historical-demo"),
                time_control="classical",
            )
        )

        print(
            json.dumps(
                {
                    "game": {
                        "event": game.headers.get("Event"),
                        "white": game.headers.get("White"),
                        "black": game.headers.get("Black"),
                        "result": game.headers.get("Result"),
                    },
                    "move": {
                        "ply": ply,
                        "move_number": board.fullmove_number,
                        "player_color": player_color,
                        "san": san,
                        "uci": move.uci(),
                        "fen_before": fen_before,
                    },
                    "context_result": result.to_dict(),
                },
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
        board.push(move)


def _production_like_builder() -> MoveContextBuilder:
    return MoveContextBuilder(
        StockfishAnalysisProvider(
            binary_path=STOCKFISH or "stockfish",
            depth=_int_env("G6_OPERA_EVAL_STOCKFISH_DEPTH", MIN_STOCKFISH_DEPTH),
            multipv=_int_env("G6_OPERA_EVAL_STOCKFISH_MULTIPV", 5),
            threads=_optional_int_env("G6_OPERA_EVAL_STOCKFISH_THREADS"),
            hash_mb=_optional_int_env("G6_OPERA_EVAL_STOCKFISH_HASH_MB"),
            show_wdl=True,
        ),
        Maia2MoveLikelihoodProvider(
            model_type=_maia_model_type(),
            device=_maia_device(),
            save_root=os.getenv("MAIA2_MODEL_ROOT", "./maia2_models"),
            top_move_limit=_int_env("G6_OPERA_EVAL_MAIA2_TOP_MOVES", 5),
        ),
    )


def _read_game(pgn: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("Opera game PGN could not be parsed.")
    return game


def _color_name(color: chess.Color) -> ColorName:
    return "white" if color == chess.WHITE else "black"


def _maia_model_type() -> MaiaModelType:
    model_type = os.getenv("G6_OPERA_EVAL_MAIA2_MODEL", "auto")
    if model_type not in {"auto", "rapid", "blitz"}:
        raise ValueError("G6_OPERA_EVAL_MAIA2_MODEL must be one of: auto, rapid, blitz.")
    return cast(MaiaModelType, model_type)


def _maia_device() -> Literal["cpu", "gpu"]:
    device = os.getenv("G6_OPERA_EVAL_MAIA2_DEVICE", "cpu")
    if device not in {"cpu", "gpu"}:
        raise ValueError("G6_OPERA_EVAL_MAIA2_DEVICE must be cpu or gpu.")
    return cast("Literal['cpu', 'gpu']", device)


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _optional_int_env(name: str) -> int | None:
    value = os.getenv(name)
    return None if value is None else int(value)
