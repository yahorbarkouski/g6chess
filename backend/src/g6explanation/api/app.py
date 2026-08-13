"""Public HTTP composition for analysis, imports, polling, and inspection."""

from __future__ import annotations

import os
from typing import Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from g6explanation.context_engine.exceptions import AnalysisError
from g6explanation.game_analysis import (
    GameAnalysisService,
    GameAnalysisSetupError,
    GameAnalysisSnapshot,
    GameAnalysisStartRequest,
    GameAnalysisStartResponse,
    GameAnalysisStoreError,
    game_analysis_service_from_env,
)
from g6explanation.game_imports import (
    ChessComLiveGameNotFinishedError,
    ChessComLiveGameNotFoundError,
    ChessComLiveGameUnavailableError,
    GameAnalysisImportRequest,
    GameAnalysisImportResponse,
    GameImportError,
    GameImportService,
    ImportPlayerLevelRequiredError,
    LichessGameInvalidPgnError,
    LichessGameNotFinishedError,
    LichessGameNotFoundError,
    LichessGameUnavailableError,
    LichessStudyChapterInvalidPgnError,
    LichessStudyChapterNotFoundError,
    LichessStudyChapterUnavailableError,
    game_import_service_from_env,
)
from g6explanation.security import AdmissionDenied, ApiProtection
from g6explanation.visualization.contracts import (
    VisualizationExample,
    VisualizationExampleCollection,
    VisualizationMoveContext,
)
from g6explanation.visualization.example_catalog import (
    VisualizationSetupError,
    build_visualization_context,
    find_visualization_example,
    visualization_examples,
)

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


class ApiProtectionBoundary(Protocol):
    """Subset of API protection used by route handlers."""

    def protect_game_analysis_start(
        self,
        *,
        request: Request,
        payload: GameAnalysisStartRequest,
    ) -> None: ...

    def protect_import_start(
        self,
        *,
        request: Request,
        payload: GameAnalysisImportRequest,
    ) -> None: ...

    def protect_cached_lookup(self, *, request: Request, external_game_id: str) -> None: ...

    def protect_poll(self, *, request: Request, analysis_id: str) -> None: ...


def create_app(
    game_analysis_service: GameAnalysisService | None = None,
    game_import_service: GameImportService | None = None,
    api_protection: ApiProtectionBoundary | None = None,
) -> FastAPI:
    app = FastAPI(
        title="G6 Chess API",
        version="0.1.0",
        docs_url=_docs_url_from_env(),
        redoc_url=_redoc_url_from_env(),
        openapi_url=_openapi_url_from_env(),
    )
    analysis_service = game_analysis_service or game_analysis_service_from_env()
    import_service = game_import_service or game_import_service_from_env(analysis_service)
    protection = api_protection or ApiProtection.from_env()

    def submit_game_analysis(
        request: GameAnalysisStartRequest,
        http_request: Request,
    ) -> GameAnalysisStartResponse:
        return start_game_analysis(request, http_request, analysis_service, protection)

    def read_game_analysis_state(
        analysis_id: str,
        http_request: Request,
    ) -> GameAnalysisSnapshot:
        return game_analysis_state(analysis_id, http_request, analysis_service, protection)

    def submit_imported_game_analysis(
        request: GameAnalysisImportRequest,
        http_request: Request,
    ) -> GameAnalysisImportResponse:
        return start_imported_game_analysis(request, http_request, import_service, protection)

    def read_cached_imported_game_analysis(
        external_game_id: str,
        http_request: Request,
    ) -> GameAnalysisImportResponse:
        return cached_imported_game_analysis(
            external_game_id,
            http_request,
            import_service,
            protection,
        )

    def read_cached_lichess_imported_game_analysis(
        external_game_id: str,
        http_request: Request,
    ) -> GameAnalysisImportResponse:
        return cached_lichess_imported_game_analysis(
            external_game_id,
            http_request,
            import_service,
            protection,
        )

    def read_cached_lichess_study_chapter_analysis(
        study_id: str,
        chapter_id: str,
        http_request: Request,
    ) -> GameAnalysisImportResponse:
        return cached_lichess_study_chapter_analysis(
            study_id,
            chapter_id,
            http_request,
            import_service,
            protection,
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins_from_env(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.add_api_route(
        "/api/visualization/health",
        health,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/visualization/examples",
        examples,
        methods=["GET"],
        response_model=VisualizationExampleCollection,
    )
    app.add_api_route(
        "/api/visualization/examples/{example_id}",
        example,
        methods=["GET"],
        response_model=VisualizationExample,
    )
    app.add_api_route(
        "/api/visualization/examples/{example_id}/contexts/{ply}",
        example_context,
        methods=["GET"],
        response_model=VisualizationMoveContext,
    )
    app.add_api_route(
        "/api/game-analysis",
        submit_game_analysis,
        methods=["POST"],
        response_model=GameAnalysisStartResponse,
    )
    app.add_api_route(
        "/api/game-analysis/import",
        submit_imported_game_analysis,
        methods=["POST"],
        response_model=GameAnalysisImportResponse,
    )
    app.add_api_route(
        "/api/game-analysis/import/chess-com/live/{external_game_id}",
        read_cached_imported_game_analysis,
        methods=["GET"],
        response_model=GameAnalysisImportResponse,
    )
    app.add_api_route(
        "/api/game-analysis/import/lichess/study/{study_id}/{chapter_id}",
        read_cached_lichess_study_chapter_analysis,
        methods=["GET"],
        response_model=GameAnalysisImportResponse,
    )
    app.add_api_route(
        "/api/game-analysis/import/lichess/{external_game_id}",
        read_cached_lichess_imported_game_analysis,
        methods=["GET"],
        response_model=GameAnalysisImportResponse,
    )
    app.add_api_route(
        "/api/game-analysis/{analysis_id}",
        read_game_analysis_state,
        methods=["GET"],
        response_model=GameAnalysisSnapshot,
    )
    return app


def health() -> dict[str, str]:
    return {"status": "ok"}


def _cors_origins_from_env() -> list[str]:
    raw_origins = os.getenv("G6EXPLANATION_CORS_ORIGINS")
    if raw_origins is None:
        return DEFAULT_CORS_ORIGINS
    configured_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return configured_origins or DEFAULT_CORS_ORIGINS


def _docs_url_from_env() -> str | None:
    return "/docs" if _bool_env("G6EXPLANATION_ENABLE_OPENAPI_DOCS", True) else None


def _redoc_url_from_env() -> str | None:
    return "/redoc" if _bool_env("G6EXPLANATION_ENABLE_OPENAPI_DOCS", True) else None


def _openapi_url_from_env() -> str | None:
    return "/openapi.json" if _bool_env("G6EXPLANATION_ENABLE_OPENAPI_DOCS", True) else None


def examples() -> VisualizationExampleCollection:
    return VisualizationExampleCollection(
        examples=[
            visualization_example.summary_contract()
            for visualization_example in visualization_examples()
        ]
    )


def example(example_id: str) -> VisualizationExample:
    selected = find_visualization_example(example_id)
    if selected is None:
        raise HTTPException(status_code=404, detail="Visualization example not found.")
    return selected


def example_context(example_id: str, ply: int) -> VisualizationMoveContext:
    if not _bool_env("G6EXPLANATION_ENABLE_VISUALIZATION_CONTEXTS", True):
        raise HTTPException(status_code=404, detail="Visualization context not found.")
    try:
        selected = build_visualization_context(example_id, ply)
    except VisualizationSetupError as exc:
        raise _public_http_exception(
            503, "visualization_unavailable", "Visualization unavailable."
        ) from exc
    except AnalysisError as exc:
        raise _public_http_exception(500, "analysis_failed", "Analysis failed.") from exc
    if selected is None:
        raise HTTPException(status_code=404, detail="Visualization context not found.")
    return selected


def start_game_analysis(
    request: GameAnalysisStartRequest,
    http_request: Request,
    service: GameAnalysisService,
    protection: ApiProtectionBoundary,
) -> GameAnalysisStartResponse:
    try:
        protection.protect_game_analysis_start(request=http_request, payload=request)
        return service.start(request)
    except AdmissionDenied as exc:
        raise _admission_http_exception(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (GameAnalysisSetupError, GameAnalysisStoreError) as exc:
        raise _public_http_exception(
            503, "analysis_unavailable", "Analysis is unavailable."
        ) from exc


def start_imported_game_analysis(
    request: GameAnalysisImportRequest,
    http_request: Request,
    service: GameImportService,
    protection: ApiProtectionBoundary,
) -> GameAnalysisImportResponse:
    try:
        protection.protect_import_start(request=http_request, payload=request)
        return service.start(request)
    except AdmissionDenied as exc:
        raise _admission_http_exception(exc) from exc
    except (
        ChessComLiveGameNotFoundError,
        LichessGameNotFoundError,
        LichessStudyChapterNotFoundError,
    ) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ChessComLiveGameNotFinishedError, LichessGameNotFinishedError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (
        ChessComLiveGameUnavailableError,
        LichessGameUnavailableError,
        LichessStudyChapterUnavailableError,
        GameAnalysisSetupError,
        GameAnalysisStoreError,
    ) as exc:
        raise _public_http_exception(
            503, "import_unavailable", "Game import is unavailable."
        ) from exc
    except ImportPlayerLevelRequiredError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "import_player_level_required", "message": str(exc)},
        ) from exc
    except (
        GameImportError,
        LichessGameInvalidPgnError,
        LichessStudyChapterInvalidPgnError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def cached_imported_game_analysis(
    external_game_id: str,
    http_request: Request,
    service: GameImportService,
    protection: ApiProtectionBoundary,
) -> GameAnalysisImportResponse:
    try:
        protection.protect_cached_lookup(request=http_request, external_game_id=external_game_id)
    except AdmissionDenied as exc:
        raise _admission_http_exception(exc) from exc
    response = service.cached_chess_com_live_game_analysis(external_game_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Cached game analysis not found.")
    return response


def cached_lichess_imported_game_analysis(
    external_game_id: str,
    http_request: Request,
    service: GameImportService,
    protection: ApiProtectionBoundary,
) -> GameAnalysisImportResponse:
    try:
        protection.protect_cached_lookup(request=http_request, external_game_id=external_game_id)
    except AdmissionDenied as exc:
        raise _admission_http_exception(exc) from exc
    response = service.cached_lichess_game_analysis(external_game_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Cached game analysis not found.")
    return response


def cached_lichess_study_chapter_analysis(
    study_id: str,
    chapter_id: str,
    http_request: Request,
    service: GameImportService,
    protection: ApiProtectionBoundary,
) -> GameAnalysisImportResponse:
    external_game_id = f"{study_id}/{chapter_id}"
    try:
        protection.protect_cached_lookup(
            request=http_request,
            external_game_id=external_game_id,
        )
    except AdmissionDenied as exc:
        raise _admission_http_exception(exc) from exc
    response = service.cached_lichess_study_chapter_analysis(study_id, chapter_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Cached game analysis not found.")
    return response


def game_analysis_state(
    analysis_id: str,
    http_request: Request,
    service: GameAnalysisService,
    protection: ApiProtectionBoundary,
) -> GameAnalysisSnapshot:
    try:
        protection.protect_poll(request=http_request, analysis_id=analysis_id)
        snapshot = service.get(analysis_id)
    except AdmissionDenied as exc:
        raise _admission_http_exception(exc) from exc
    except GameAnalysisStoreError as exc:
        raise _public_http_exception(
            503, "analysis_unavailable", "Analysis is unavailable."
        ) from exc
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Game analysis not found.")
    return snapshot


def _admission_http_exception(exc: AdmissionDenied) -> HTTPException:
    headers = (
        {"Retry-After": str(exc.retry_after_seconds)}
        if exc.retry_after_seconds is not None
        else None
    )
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.detail},
        headers=headers,
    )


def _public_http_exception(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


app = create_app()
