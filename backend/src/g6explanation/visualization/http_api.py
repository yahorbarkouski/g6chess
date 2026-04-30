"""HTTP API for the local context visualization frontend."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from g6explanation.visualization.contracts import (
    VisualizationExample,
    VisualizationExampleCollection,
)
from g6explanation.visualization.example_catalog import (
    find_visualization_example,
    visualization_examples,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="G6 Explanation Visualization API",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=False,
        allow_methods=["GET"],
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


app = create_app()
