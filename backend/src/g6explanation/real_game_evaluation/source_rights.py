"""Source-rights contracts for real explanation eval and training records."""

from __future__ import annotations

from g6explanation.context_engine.contracts import ContextContract


class ExplanationDataSource(ContextContract):
    name: str
    url: str | None = None
    rights_basis: str
    allows_global_training: bool


PROJECT_SYNTHETIC_SOURCE = ExplanationDataSource(
    name="project_synthetic",
    rights_basis="Position and move created inside this repository for evaluation coverage.",
    allows_global_training=True,
)

PROJECT_HISTORICAL_GAME_SOURCE = ExplanationDataSource(
    name="project_curated_historical_game_score",
    rights_basis=(
        "Historical game score curated in this repository without importing a "
        "third-party commercial game database export."
    ),
    allows_global_training=True,
)

LICHESS_DATABASE_CC0_SOURCE = ExplanationDataSource(
    name="lichess_database_cc0",
    url="https://database.lichess.org/",
    rights_basis=(
        "Lichess database exports are released under Creative Commons CC0; the "
        "database page permits research, commercial use, modification, and redistribution."
    ),
    allows_global_training=True,
)

CHESS_COM_REQUIRES_AUTHORIZATION_SOURCE = ExplanationDataSource(
    name="chess_com_requires_authorization",
    url="https://www.chess.com/legal/user-agreement",
    rights_basis=(
        "Chess.com content requires prior written authorization for AI model "
        "training, machine-learning datasets, or competing educational tools."
    ),
    allows_global_training=False,
)
