"""Typed contracts for the visualization API."""

from __future__ import annotations

from pydantic import Field

from g6explanation.context_engine.contracts import (
    ColorName,
    ContextContract,
    ContextResult,
)


class VisualizationMove(ContextContract):
    """One replayable move in a visualization example."""

    ply: int = Field(ge=1)
    uci: str
    san: str
    fen_before: str
    fen_after: str
    player_color: ColorName
    has_context: bool


class VisualizationMoveContext(ContextContract):
    """Verified context-engine output for one replay ply."""

    ply: int = Field(ge=1)
    result: ContextResult


class VisualizationExampleSummary(ContextContract):
    """Compact example metadata for selectors."""

    id: str
    title: str
    source: str
    initial_fen: str
    orientation: ColorName
    move_count: int
    context_plies: list[int] = Field(default_factory=list[int])
    tags: list[str] = Field(default_factory=list[str])


class VisualizationExample(ContextContract):
    """Full payload consumed by the React visualization app."""

    id: str
    title: str
    summary: str
    source: str
    initial_fen: str
    orientation: ColorName
    player_level: str
    tags: list[str] = Field(default_factory=list[str])
    moves: list[VisualizationMove] = Field(default_factory=list[VisualizationMove])
    contexts: list[VisualizationMoveContext] = Field(default_factory=list[VisualizationMoveContext])

    def summary_contract(self) -> VisualizationExampleSummary:
        return VisualizationExampleSummary(
            id=self.id,
            title=self.title,
            source=self.source,
            initial_fen=self.initial_fen,
            orientation=self.orientation,
            move_count=len(self.moves),
            context_plies=[move.ply for move in self.moves if move.has_context],
            tags=self.tags,
        )


class VisualizationExampleCollection(ContextContract):
    """List response for available visualization examples."""

    examples: list[VisualizationExampleSummary] = Field(
        default_factory=list[VisualizationExampleSummary]
    )
