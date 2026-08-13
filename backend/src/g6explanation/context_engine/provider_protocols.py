"""Provider protocols for context-engine evidence sources."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import chess

from g6explanation.context_engine.contracts import (
    ColorName,
    EngineAnalysis,
    EngineLine,
    HumanMoveLikelihood,
    MoveContextRequest,
)


class EngineAnalysisProvider(Protocol):
    def analyze(
        self, board: chess.Board, played_move: chess.Move, player_color: ColorName
    ) -> EngineAnalysis:
        """Analyze the move from the board before it is played."""
        ...


@runtime_checkable
class RootMoveAnalysisProvider(Protocol):
    def analyze_root_moves(
        self,
        board: chess.Board,
        root_moves: list[chess.Move],
        player_color: ColorName,
    ) -> list[EngineLine]:
        """Analyze explicit legal root moves from the board before the played move."""
        ...


class HumanMoveLikelihoodProvider(Protocol):
    def likelihoods(
        self,
        board: chess.Board,
        candidate_moves: list[chess.Move],
        request: MoveContextRequest,
    ) -> dict[str, HumanMoveLikelihood]:
        """Return human move likelihoods keyed by UCI move.

        Providers may include additional legal moves, such as top human-likeness
        moves, when they have evidence for them.
        """
        ...
