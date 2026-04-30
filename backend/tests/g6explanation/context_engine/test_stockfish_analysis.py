from __future__ import annotations

import shutil

import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import MoveContextRequest, PlayerLevel
from g6explanation.context_engine.stockfish_analysis import StockfishAnalysisProvider


@pytest.mark.skipif(shutil.which("stockfish") is None, reason="stockfish binary is not installed")
def test_stockfish_provider_builds_smoke_context() -> None:
    request = MoveContextRequest(
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200, "lichess"),
        time_control="rapid",
    )

    result = MoveContextBuilder(
        StockfishAnalysisProvider(depth=4, multipv=2, threads=1, hash_mb=16, show_wdl=True)
    ).build(request)

    assert result.evidence.played.san == "e4"
    assert 1 <= len(result.evidence.engine.top_lines) <= 2
    assert result.evidence.candidates
    assert result.llm_context.played == "e4"
    assert result.evidence.engine.analysis_budget.to_dict() == {
        "kind": "depth",
        "value": 4,
        "multipv": 2,
    }
    assert result.evidence.engine.engine_options["UCI_ShowWDL"] is True
    assert result.evidence.engine.engine_options["Threads"] == 1
    assert result.evidence.engine.engine_options["Hash"] == 16
    assert result.evidence.engine.played_line.move_uci == "e2e4"
    assert result.evidence.engine.played_line.depth is not None
    assert result.evidence.engine.played_line.nodes is not None
    assert result.evidence.engine.top_lines[0].pv_uci
    assert result.evidence.engine.played_line.pv_uci[0] == "e2e4"
    assert any(line.wdl is not None for line in result.evidence.engine.top_lines)
