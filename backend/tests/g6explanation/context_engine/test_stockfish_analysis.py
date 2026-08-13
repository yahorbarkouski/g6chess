from __future__ import annotations

import os
import shutil

import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import MoveContextRequest, PlayerLevel
from g6explanation.context_engine.stockfish_analysis import (
    MIN_STOCKFISH_DEPTH,
    StockfishAnalysisProvider,
)

STOCKFISH_BINARY = os.getenv("G6EXPLANATION_STOCKFISH_BINARY") or shutil.which("stockfish")


def test_stockfish_provider_rejects_depth_below_minimum() -> None:
    with pytest.raises(ValueError, match=f"at least {MIN_STOCKFISH_DEPTH}"):
        StockfishAnalysisProvider(depth=MIN_STOCKFISH_DEPTH - 1)


@pytest.mark.skipif(
    STOCKFISH_BINARY is None,
    reason="stockfish is not installed; set G6EXPLANATION_STOCKFISH_BINARY",
)
def test_stockfish_provider_builds_smoke_context() -> None:
    assert STOCKFISH_BINARY is not None
    request = MoveContextRequest(
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200, "lichess"),
        time_control="rapid",
    )

    result = MoveContextBuilder(
        StockfishAnalysisProvider(
            binary_path=STOCKFISH_BINARY,
            depth=MIN_STOCKFISH_DEPTH,
            multipv=2,
            threads=1,
            hash_mb=16,
            show_wdl=True,
        )
    ).build(request)

    assert result.verification.passed is True
    assert result.evidence.played.san == "e4"
    assert 1 <= len(result.evidence.engine.top_lines) <= 2
    assert result.evidence.candidates
    assert result.llm_context.played == "e4"
    assert result.evidence.engine.analysis_budget.to_dict() == {
        "kind": "depth",
        "value": MIN_STOCKFISH_DEPTH,
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
