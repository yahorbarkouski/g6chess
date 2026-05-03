"""Real Stockfish, Maia, and LLM evaluation helpers."""

from g6explanation.real_game_evaluation.explanation_evaluation import (
    REAL_EXPLANATION_EVAL_CASES,
    RealEvaluationSetupError,
    RealExplanationEvalCase,
    RealExplanationEvalRecord,
    RealExplanationEvalSummary,
    run_real_explanation_evaluation,
    select_real_explanation_eval_cases,
)
from g6explanation.real_game_evaluation.real_games import (
    BYRNE_FISCHER,
    CAPABLANCA_TARTAKOWER,
    KASPAROV_TOPALOV,
    OPERA_GAME,
    REAL_GAME_FIXTURES,
    RealGameFixture,
    board_before_ply,
    color_name,
    read_game,
    san_at_ply,
)

__all__ = [
    "BYRNE_FISCHER",
    "CAPABLANCA_TARTAKOWER",
    "KASPAROV_TOPALOV",
    "OPERA_GAME",
    "REAL_EXPLANATION_EVAL_CASES",
    "REAL_GAME_FIXTURES",
    "RealEvaluationSetupError",
    "RealExplanationEvalCase",
    "RealExplanationEvalRecord",
    "RealExplanationEvalSummary",
    "RealGameFixture",
    "board_before_ply",
    "color_name",
    "read_game",
    "run_real_explanation_evaluation",
    "san_at_ply",
    "select_real_explanation_eval_cases",
]
