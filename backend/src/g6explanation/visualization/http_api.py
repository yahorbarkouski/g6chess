"""HTTP API for the local context visualization frontend."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
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


def create_app(game_analysis_service: GameAnalysisService | None = None) -> FastAPI:
    app = FastAPI(
        title="G6 Explanation Visualization API",
        version="0.1.0",
    )
    analysis_service = game_analysis_service or game_analysis_service_from_env()

    def submit_game_analysis(request: GameAnalysisStartRequest) -> GameAnalysisStartResponse:
        return start_game_analysis(request, analysis_service)

    def read_game_analysis_state(analysis_id: str) -> GameAnalysisSnapshot:
        return game_analysis_state(analysis_id, analysis_service)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
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
        "/api/game-analysis/{analysis_id}",
        read_game_analysis_state,
        methods=["GET"],
        response_model=GameAnalysisSnapshot,
    )
    return app


def health() -> dict[str, str]:
    return {"status": "ok"}


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
    try:
        selected = build_visualization_context(example_id, ply)
    except VisualizationSetupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AnalysisError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if selected is None:
        raise HTTPException(status_code=404, detail="Visualization context not found.")
    return selected


def start_game_analysis(
    request: GameAnalysisStartRequest,
    service: GameAnalysisService,
) -> GameAnalysisStartResponse:
    try:
        return service.start(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (GameAnalysisSetupError, GameAnalysisStoreError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def game_analysis_state(
    analysis_id: str,
    service: GameAnalysisService,
) -> GameAnalysisSnapshot:
    try:
        snapshot = service.get(analysis_id)
    except GameAnalysisStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Game analysis not found.")
    return snapshot


app = create_app()
