from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

import chess
import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    HumanMoveLikelihood,
    MoveContextRequest,
    PlayerLevel,
)
from g6explanation.context_engine.stockfish_analysis import (
    MIN_STOCKFISH_DEPTH,
    StockfishAnalysisProvider,
)

STOCKFISH_BINARY = os.getenv("G6EXPLANATION_STOCKFISH_BINARY") or shutil.which("stockfish")

pytestmark = pytest.mark.skipif(
    STOCKFISH_BINARY is None,
    reason="stockfish is not installed; set G6EXPLANATION_STOCKFISH_BINARY",
)


def test_stockfish_golden_opening_context_records_metadata_and_wdl() -> None:
    result = _stockfish_builder(depth=MIN_STOCKFISH_DEPTH, multipv=2).build(
        MoveContextRequest(
            fen_before=chess.STARTING_FEN,
            played_move="e2e4",
            player_color="white",
            player_level=PlayerLevel.rating(1200, "lichess"),
            time_control="rapid",
        )
    )

    assert result.verification.passed is True
    assert result.evidence.position.side_to_move == "white"
    assert result.evidence.played.san == "e4"
    assert result.evidence.engine.engine_version
    assert result.evidence.engine.analysis_budget.multipv == 2
    assert result.evidence.engine.engine_options["UCI_ShowWDL"] is True
    assert all(line.wdl is not None for line in result.evidence.engine.top_lines)
    assert result.evidence.engine.played_line.wdl is not None
    assert result.evidence.engine.after_line is not None
    assert result.evidence.engine.after_line.wdl is not None


def test_stockfish_golden_black_to_move_keeps_player_perspective() -> None:
    result = _stockfish_builder(depth=MIN_STOCKFISH_DEPTH, multipv=2).build(
        MoveContextRequest(
            fen_before="rnbqkbnr/pppppppp/8/4P3/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            played_move="c7c5",
            player_color="black",
            player_level=PlayerLevel.rating(1500, "lichess"),
            time_control="blitz",
        )
    )

    assert result.verification.passed is True
    assert result.evidence.position.side_to_move == "black"
    assert result.evidence.played.uci == "c7c5"
    assert result.evidence.engine.played_line.move_uci == "c7c5"
    assert result.llm_context.played == result.evidence.played.san


def test_stockfish_golden_forces_played_move_outside_top_multipv() -> None:
    result = _stockfish_builder(depth=MIN_STOCKFISH_DEPTH, multipv=1).build(
        MoveContextRequest(
            fen_before=chess.STARTING_FEN,
            played_move="a2a3",
            player_color="white",
            player_level=PlayerLevel.rating(900, "lichess"),
            time_control="blitz",
        )
    )

    assert result.verification.passed is True
    assert len(result.evidence.engine.top_lines) == 1
    assert result.evidence.engine.top_lines[0].move_uci != "a2a3"
    assert result.evidence.engine.played_line.move_uci == "a2a3"
    assert result.evidence.engine.played_line.pv_uci[0] == "a2a3"


def test_stockfish_golden_game_over_after_played_has_no_after_line() -> None:
    result = _stockfish_builder(depth=MIN_STOCKFISH_DEPTH, multipv=1).build(
        MoveContextRequest(
            fen_before="7k/5Q2/7K/8/8/8/8/8 w - - 0 1",
            played_move="f7f8",
            player_color="white",
            player_level=PlayerLevel.rating(1800, "lichess"),
            time_control="rapid",
        )
    )

    assert result.verification.passed is True
    assert result.evidence.played.san == "Qf8#"
    assert result.evidence.engine.played_line.move_uci == "f7f8"
    assert result.evidence.engine.after_line is None


def test_stockfish_golden_supplements_top_human_move_with_root_analysis() -> None:
    result = MoveContextBuilder(
        _stockfish_provider(depth=MIN_STOCKFISH_DEPTH, multipv=1),
        StaticTopHumanProvider("h2h3"),
    ).build(
        MoveContextRequest(
            fen_before=chess.STARTING_FEN,
            played_move="g2g4",
            player_color="white",
            player_level=PlayerLevel.rating(1000, "lichess"),
            time_control="rapid",
        )
    )

    supplemental = next(
        candidate for candidate in result.evidence.candidates if candidate.uci == "h2h3"
    )

    assert result.verification.passed is True
    assert "human_common_move" in supplemental.roles
    assert supplemental.engine_rank is None
    assert supplemental.player_level_probability == 0.35
    assert supplemental.plus_400_probability == 0.45


@dataclass(frozen=True)
class StaticTopHumanProvider:
    move_uci: str

    def likelihoods(
        self,
        board: chess.Board,
        candidate_moves: list[chess.Move],
        request: MoveContextRequest,
    ) -> dict[str, HumanMoveLikelihood]:
        return {
            self.move_uci: HumanMoveLikelihood(
                player_level_probability=0.35,
                plus_400_probability=0.45,
                evidence_source="static_human_top_move",
                rank=1,
                is_top_human_move=True,
            )
        }


def _stockfish_builder(depth: int, multipv: int) -> MoveContextBuilder:
    return MoveContextBuilder(_stockfish_provider(depth=depth, multipv=multipv))


def _stockfish_provider(depth: int, multipv: int) -> StockfishAnalysisProvider:
    assert STOCKFISH_BINARY is not None
    return StockfishAnalysisProvider(
        binary_path=STOCKFISH_BINARY,
        depth=depth,
        multipv=multipv,
        threads=1,
        hash_mb=16,
        show_wdl=True,
    )
