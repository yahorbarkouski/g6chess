"""Asynchronous full-game analysis API."""

from g6explanation.game_analysis.analysis_runner import (
    GameAnalysisRunner,
    count_game_plies,
    game_analysis_context_workers_from_env,
    game_analysis_game,
    game_analysis_openrouter_concurrency_from_env,
    game_ply_requests,
)
from g6explanation.game_analysis.contracts import (
    BookLine,
    BookLineMove,
    GameAnalysisGame,
    GameAnalysisSnapshot,
    GameAnalysisStartRequest,
    GameAnalysisStartResponse,
    GameMainlineMove,
    GameMoveAnalysis,
    OpeningBookMetadata,
)
from g6explanation.game_analysis.job_service import (
    GameAnalysisService,
    GameAnalysisSubmissionError,
    game_analysis_service_from_env,
)
from g6explanation.game_analysis.modal_job_executor import ModalSpawnGameAnalysisExecutor
from g6explanation.game_analysis.opening_book import (
    OpeningBookPly,
    default_opening_book,
    prefetch_default_opening_book,
    run_opening_book_pass,
)
from g6explanation.game_analysis.provider_setup import (
    GameAnalysisSetupError,
    real_game_analysis_context_builder,
)
from g6explanation.game_analysis.state_store import (
    GameAnalysisStore,
    GameAnalysisStoreError,
    InMemoryGameAnalysisStore,
    RedisGameAnalysisStore,
)

__all__ = [
    "BookLine",
    "BookLineMove",
    "GameAnalysisGame",
    "GameAnalysisRunner",
    "GameAnalysisService",
    "GameAnalysisSetupError",
    "GameAnalysisSnapshot",
    "GameAnalysisStartRequest",
    "GameAnalysisStartResponse",
    "GameAnalysisStore",
    "GameAnalysisStoreError",
    "GameAnalysisSubmissionError",
    "GameMainlineMove",
    "GameMoveAnalysis",
    "InMemoryGameAnalysisStore",
    "ModalSpawnGameAnalysisExecutor",
    "OpeningBookMetadata",
    "OpeningBookPly",
    "RedisGameAnalysisStore",
    "count_game_plies",
    "default_opening_book",
    "game_analysis_context_workers_from_env",
    "game_analysis_game",
    "game_analysis_openrouter_concurrency_from_env",
    "game_analysis_service_from_env",
    "game_ply_requests",
    "prefetch_default_opening_book",
    "real_game_analysis_context_builder",
    "run_opening_book_pass",
]
