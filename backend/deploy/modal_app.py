"""Modal deployment entrypoint for the game-analysis API."""

from __future__ import annotations

import os

import modal

APP_NAME = "g6explanation"
RUNTIME_SECRET_NAME = "g6explanation-runtime"
MAIA_VOLUME_NAME = "g6explanation-maia-models"
MAIA_MODEL_ROOT = "/models/maia2"
SOURCE_ROOT = "/root"

app = modal.App(APP_NAME)
runtime_secret = modal.Secret.from_name(RUNTIME_SECRET_NAME)
maia_models = modal.Volume.from_name(MAIA_VOLUME_NAME, create_if_missing=True)


def _image(*, include_maia: bool) -> modal.Image:
    optional_dependencies = ["deployment"]
    if include_maia:
        optional_dependencies.append("maia")
    image = modal.Image.debian_slim(python_version="3.11").pip_install_from_pyproject(
        "pyproject.toml",
        optional_dependencies=optional_dependencies,
    )
    if include_maia:
        image = image.apt_install("stockfish").env(
            {
                "MAIA2_MODEL_ROOT": MAIA_MODEL_ROOT,
                "G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_BINARY": "/usr/games/stockfish",
                "G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_DEPTH": "16",
                "G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_MULTIPV": "5",
                "G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_THREADS": "1",
                "G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_HASH_MB": "128",
                "G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS": "8",
                "G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY": "30",
            }
        )
    image = image.env({"PYTHONPATH": SOURCE_ROOT}).add_local_dir(
        "src/g6explanation",
        f"{SOURCE_ROOT}/g6explanation",
        copy=include_maia,
    )
    if include_maia:
        image = image.run_commands(
            'python -c "from g6explanation.game_analysis.opening_book import '
            "prefetch_default_opening_book; book = prefetch_default_opening_book(); "
            "print(f'Prefetched opening book entries={book.entry_count} "
            "named_positions={book.opening_count}')\""
        )
    return image


api_image = _image(include_maia=False)
worker_image = _image(include_maia=True)


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value is None else int(value)


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    return default if value is None else float(value)


@app.function(
    image=worker_image,
    secrets=[runtime_secret],
    volumes={MAIA_MODEL_ROOT: maia_models},
    cpu=_float_env("G6EXPLANATION_MODAL_WORKER_CPU", 8.0),
    memory=_int_env("G6EXPLANATION_MODAL_WORKER_MEMORY_MB", 16384),
    timeout=_int_env("G6EXPLANATION_MODAL_WORKER_TIMEOUT_SECONDS", 1800),
    startup_timeout=_int_env("G6EXPLANATION_MODAL_WORKER_STARTUP_TIMEOUT_SECONDS", 900),
    min_containers=_int_env("G6EXPLANATION_MODAL_WORKER_MIN_CONTAINERS", 0),
    max_containers=_int_env("G6EXPLANATION_MODAL_WORKER_MAX_CONTAINERS", 10),
    scaledown_window=_int_env("G6EXPLANATION_MODAL_WORKER_SCALEDOWN_SECONDS", 300),
)
def run_game_analysis_job(analysis_id: str, request_json: str) -> None:
    from g6explanation.game_analysis import (
        GameAnalysisRunner,
        GameAnalysisStartRequest,
        RedisGameAnalysisStore,
        game_analysis_context_workers_from_env,
        game_analysis_openrouter_concurrency_from_env,
    )

    request = GameAnalysisStartRequest.model_validate_json(request_json)
    runner = GameAnalysisRunner(
        context_workers=game_analysis_context_workers_from_env(),
        openrouter_concurrency=game_analysis_openrouter_concurrency_from_env(),
    )
    runner.run(
        analysis_id=analysis_id,
        request=request,
        store=_redis_store(RedisGameAnalysisStore),
    )


@app.function(
    image=api_image,
    secrets=[runtime_secret],
    cpu=_float_env("G6EXPLANATION_MODAL_API_CPU", 0.5),
    memory=_int_env("G6EXPLANATION_MODAL_API_MEMORY_MB", 1024),
    timeout=_int_env("G6EXPLANATION_MODAL_API_TIMEOUT_SECONDS", 120),
    startup_timeout=_int_env("G6EXPLANATION_MODAL_API_STARTUP_TIMEOUT_SECONDS", 300),
    min_containers=_int_env("G6EXPLANATION_MODAL_API_MIN_CONTAINERS", 0),
    max_containers=_int_env("G6EXPLANATION_MODAL_API_MAX_CONTAINERS", 20),
    scaledown_window=_int_env("G6EXPLANATION_MODAL_API_SCALEDOWN_SECONDS", 300),
)
@modal.asgi_app()
def fastapi_app() -> object:
    from g6explanation.game_analysis import (
        GameAnalysisRunner,
        GameAnalysisService,
        ModalSpawnGameAnalysisExecutor,
        RedisGameAnalysisStore,
    )
    from g6explanation.visualization.http_api import create_app

    analysis_service = GameAnalysisService(
        store=_redis_store(RedisGameAnalysisStore),
        runner=GameAnalysisRunner(),
        executor=ModalSpawnGameAnalysisExecutor(
            spawn_job=lambda analysis_id, request_json: run_game_analysis_job.spawn(
                analysis_id,
                request_json,
            )
        ),
    )
    return create_app(game_analysis_service=analysis_service)


def _redis_store(store_cls: type[object]) -> object:
    redis_url = os.environ.get("G6EXPLANATION_REDIS_URL")
    if redis_url is None:
        raise RuntimeError(
            f"G6EXPLANATION_REDIS_URL must be set in the Modal {RUNTIME_SECRET_NAME!r} secret."
        )
    return store_cls.from_url(
        redis_url,
        key_prefix=os.environ.get("G6EXPLANATION_GAME_ANALYSIS_REDIS_PREFIX", "g6:game_analysis"),
        ttl_seconds=_int_env("G6EXPLANATION_GAME_ANALYSIS_TTL_SECONDS", 24 * 60 * 60),
    )
