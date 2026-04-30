from __future__ import annotations

import importlib.util
import os
import shutil
from dataclasses import dataclass

import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import ColorName, MoveContextRequest, PlayerLevel
from g6explanation.context_engine.maia_likelihood import Maia2MoveLikelihoodProvider
from g6explanation.context_engine.stockfish_analysis import (
    MIN_STOCKFISH_DEPTH,
    StockfishAnalysisProvider,
)
from tests.g6explanation.context_engine.test_real_game_significance_examples import (
    BYRNE_FISCHER,
    KASPAROV_TOPALOV,
    OPERA_GAME,
)

STOCKFISH = shutil.which("stockfish")
HAS_MAIA2 = importlib.util.find_spec("maia2") is not None


@dataclass(frozen=True)
class MaiaEvaluationCase:
    game: str
    pgn: str
    ply: int
    player_color: ColorName
    rating: int
    expected_move: str
    expected_beauty: str
    expected_findability: str
    probability_kind: str


CASES = [
    MaiaEvaluationCase(
        game="Opera Game",
        pgn=OPERA_GAME,
        ply=33,
        player_color="white",
        rating=2400,
        expected_move="Rd8#",
        expected_beauty="beautiful",
        expected_findability="obvious",
        probability_kind="obvious",
    ),
    MaiaEvaluationCase(
        game="Game of the Century",
        pgn=BYRNE_FISCHER,
        ply=34,
        player_color="black",
        rating=2400,
        expected_move="Be6",
        expected_beauty="brilliant",
        expected_findability="engine_like",
        probability_kind="rare",
    ),
    MaiaEvaluationCase(
        game="Kasparov's Immortal",
        pgn=KASPAROV_TOPALOV,
        ply=47,
        player_color="white",
        rating=2800,
        expected_move="Rxd4",
        expected_beauty="beautiful",
        expected_findability="very_hard",
        probability_kind="rare",
    ),
]


@pytest.mark.skipif(
    os.getenv("G6EXPLANATION_RUN_MAIA2") != "1" or STOCKFISH is None or not HAS_MAIA2,
    reason="real-game Maia evaluation requires Stockfish, maia2, local models, and opt-in env var",
)
def test_real_game_context_uses_actual_maia_likelihoods() -> None:
    builder = MoveContextBuilder(
        StockfishAnalysisProvider(
            binary_path=STOCKFISH or "stockfish",
            depth=MIN_STOCKFISH_DEPTH,
            multipv=3,
            threads=1,
            hash_mb=64,
            show_wdl=True,
        ),
        Maia2MoveLikelihoodProvider(
            device="cpu",
            save_root=os.getenv("MAIA2_MODEL_ROOT", "./maia2_models"),
            top_move_limit=5,
        ),
    )

    for case in CASES:
        result = builder.build(
            MoveContextRequest(
                pgn=case.pgn,
                ply=case.ply,
                player_color=case.player_color,
                player_level=PlayerLevel.rating(case.rating, "historical-demo"),
                time_control="classical",
            )
        )
        played = next(
            candidate
            for candidate in result.evidence.candidates
            if "played_move" in candidate.roles
        )

        assert result.evidence.played.san == case.expected_move
        assert result.evidence.beauty.label == case.expected_beauty
        assert played.findability_source == "maia2_rapid"
        assert played.player_level_probability is not None
        assert played.player_level_bucket == ">=2000"
        assert played.plus_400_level_bucket == ">=2000"
        assert played.plus_400_probability is None
        assert played.time_adjusted_findability == case.expected_findability
        if case.probability_kind == "obvious":
            assert played.player_level_probability >= 0.30
            assert played.human_rank == 1
        else:
            assert played.player_level_probability < 0.01
            assert played.human_rank is not None
            assert played.human_rank > 5

        human_common = [
            candidate
            for candidate in result.evidence.candidates
            if "human_common_move" in candidate.roles
        ]
        assert human_common
