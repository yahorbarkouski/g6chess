from __future__ import annotations

import shutil

import pytest

from g6explanation.context_engine import MoveContextEngine
from g6explanation.context_engine.models import MoveContextRequest, PlayerLevel
from g6explanation.context_engine.providers import StockfishAnalyzer


@pytest.mark.skipif(shutil.which("stockfish") is None, reason="stockfish binary is not installed")
def test_stockfish_provider_builds_smoke_context() -> None:
    request = MoveContextRequest(
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200, "lichess"),
        time_control="rapid",
    )

    result = MoveContextEngine(StockfishAnalyzer(depth=4, multipv=2)).build(request)

    assert result.evidence.played.san == "e4"
    assert result.evidence.engine.top_lines
    assert result.evidence.candidates
    assert result.llm_context.played == "e4"
