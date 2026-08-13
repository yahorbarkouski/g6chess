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
from g6explanation.explanation_generation.generation_service import ExplanationService
from g6explanation.explanation_generation.openrouter_chat import OpenRouterCoachModelProvider
from tests.g6explanation.context_engine.helpers import StaticAnalysisProvider
from tests.g6explanation.explanation_generation.helpers import best_context

STOCKFISH_BINARY = os.getenv("G6EXPLANATION_STOCKFISH_BINARY") or shutil.which("stockfish")


@pytest.mark.skipif(
    os.environ.get("G6EXPLANATION_RUN_OPENROUTER") != "1",
    reason="Real OpenRouter generation is opt-in.",
)
def test_real_openrouter_generates_verified_explanation() -> None:
    context = best_context()
    provider = OpenRouterCoachModelProvider.from_env()
    service = ExplanationService(
        context_builder=MoveContextBuilder(StaticAnalysisProvider(context.evidence.engine)),
        coach_provider=provider,
        use_baseline_fallback=False,
    )

    result = service.explain_context(context)

    assert result.finish_reason == "model"
    assert result.provider_name == "openrouter"
    assert result.model
    assert result.verification.passed
    assert context.llm_context.played in result.explanation


@pytest.mark.skipif(
    os.environ.get("G6EXPLANATION_RUN_OPENROUTER_STOCKFISH") != "1",
    reason="Real OpenRouter plus Stockfish generation is opt-in.",
)
@pytest.mark.skipif(
    STOCKFISH_BINARY is None,
    reason="stockfish is not installed; set G6EXPLANATION_STOCKFISH_BINARY",
)
def test_real_openrouter_generates_verified_explanation_from_stockfish_context() -> None:
    assert STOCKFISH_BINARY is not None
    request = MoveContextRequest(
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200, "lichess"),
        time_control="rapid",
    )
    context_builder = MoveContextBuilder(
        StockfishAnalysisProvider(
            binary_path=STOCKFISH_BINARY,
            depth=MIN_STOCKFISH_DEPTH,
            multipv=2,
            threads=1,
            hash_mb=16,
            show_wdl=True,
        )
    )
    service = ExplanationService(
        context_builder=context_builder,
        coach_provider=OpenRouterCoachModelProvider.from_env(),
        use_baseline_fallback=False,
    )

    result = service.explain(request)

    assert result.finish_reason == "model"
    assert result.verification.passed
    assert "e4" in result.explanation
