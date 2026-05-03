"""Real provider setup for full-game analysis jobs."""

from __future__ import annotations

import importlib.util
import os
import shutil
from typing import Literal, cast

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.maia_likelihood import Maia2MoveLikelihoodProvider, MaiaModelType
from g6explanation.context_engine.stockfish_analysis import (
    MIN_STOCKFISH_DEPTH,
    StockfishAnalysisProvider,
)


class GameAnalysisSetupError(RuntimeError):
    """Raised when real game-analysis providers are not locally available."""


def real_game_analysis_context_builder() -> MoveContextBuilder:
    """Build the real Stockfish+Maia context builder used by the async API."""

    stockfish_binary = (
        os.getenv("G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_BINARY")
        or os.getenv("G6_REAL_LLM_EVAL_STOCKFISH_BINARY")
        or os.getenv("G6EXPLANATION_STOCKFISH_BINARY")
        or shutil.which("stockfish")
    )
    if stockfish_binary is None:
        raise GameAnalysisSetupError(
            "Game analysis requires Stockfish on PATH or "
            "G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_BINARY."
        )
    if importlib.util.find_spec("maia2") is None:
        raise GameAnalysisSetupError(
            "Game analysis requires maia2. Install with `uv sync --extra maia`."
        )

    return MoveContextBuilder(
        StockfishAnalysisProvider(
            binary_path=stockfish_binary,
            depth=_int_env("G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_DEPTH", MIN_STOCKFISH_DEPTH),
            multipv=_int_env("G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_MULTIPV", 5),
            threads=_optional_int_env("G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_THREADS"),
            hash_mb=_optional_int_env("G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_HASH_MB"),
            show_wdl=True,
        ),
        Maia2MoveLikelihoodProvider(
            model_type=_maia_model_type(),
            device=_maia_device(),
            save_root=os.getenv("MAIA2_MODEL_ROOT", "./maia2_models"),
            top_move_limit=_int_env("G6EXPLANATION_GAME_ANALYSIS_MAIA2_TOP_MOVES", 5),
        ),
    )


def _maia_model_type() -> MaiaModelType:
    value = os.getenv("G6EXPLANATION_GAME_ANALYSIS_MAIA2_MODEL", "auto")
    if value not in {"auto", "rapid", "blitz"}:
        raise GameAnalysisSetupError(
            "G6EXPLANATION_GAME_ANALYSIS_MAIA2_MODEL must be auto, rapid, or blitz."
        )
    return cast(MaiaModelType, value)


def _maia_device() -> Literal["cpu", "gpu"]:
    value = os.getenv("G6EXPLANATION_GAME_ANALYSIS_MAIA2_DEVICE", "cpu")
    if value not in {"cpu", "gpu"}:
        raise GameAnalysisSetupError("G6EXPLANATION_GAME_ANALYSIS_MAIA2_DEVICE must be cpu or gpu.")
    return cast(Literal["cpu", "gpu"], value)


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _optional_int_env(name: str) -> int | None:
    value = os.getenv(name)
    return None if value is None else int(value)
