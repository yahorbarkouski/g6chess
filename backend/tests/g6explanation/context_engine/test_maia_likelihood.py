from __future__ import annotations

import importlib.util
import os

import chess
import pytest

from g6explanation.context_engine.contracts import MoveContextRequest, PlayerLevel
from g6explanation.context_engine.maia_likelihood import Maia2MoveLikelihoodProvider


@pytest.mark.skipif(
    os.getenv("G6EXPLANATION_RUN_MAIA2") != "1" or importlib.util.find_spec("maia2") is None,
    reason="Maia-2 smoke test requires optional runtime, model files, and opt-in env var",
)
def test_maia2_provider_returns_legal_move_likelihoods() -> None:
    board = chess.Board()
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200, "lichess"),
        time_control="rapid",
    )
    provider = Maia2MoveLikelihoodProvider(
        device="cpu",
        save_root=os.getenv("MAIA2_MODEL_ROOT", "./maia2_models"),
    )

    stats = provider.likelihoods(board, [chess.Move.from_uci("e2e4")], request)

    assert "e2e4" in stats
    assert stats["e2e4"].player_level_probability is not None
    assert stats["e2e4"].plus_400_probability is not None
    assert all(chess.Move.from_uci(uci) in board.legal_moves for uci in stats)
