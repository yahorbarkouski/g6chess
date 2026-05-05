"""Modal-backed job launcher for game-analysis deployments."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass

from g6explanation.game_analysis.contracts import GameAnalysisStartRequest

ModalSpawn = Callable[[str, str], object]


@dataclass(frozen=True)
class ModalSpawnGameAnalysisExecutor:
    """Submit game-analysis jobs to a Modal function instead of local threads."""

    spawn_job: ModalSpawn

    def submit(
        self,
        fn: Callable[..., object],
        /,
        *args: object,
        **kwargs: object,
    ) -> Future[object]:
        del fn, args
        analysis_id = _analysis_id_from_kwargs(kwargs)
        request = _request_from_kwargs(kwargs)
        spawned_call = self.spawn_job(analysis_id, request.model_dump_json())
        future: Future[object] = Future()
        future.set_result(spawned_call)
        return future


def _analysis_id_from_kwargs(kwargs: dict[str, object]) -> str:
    value = kwargs.get("analysis_id")
    if not isinstance(value, str) or not value:
        raise ValueError("Modal game-analysis jobs require analysis_id.")
    return value


def _request_from_kwargs(kwargs: dict[str, object]) -> GameAnalysisStartRequest:
    value = kwargs.get("request")
    if not isinstance(value, GameAnalysisStartRequest):
        raise TypeError("Modal game-analysis jobs require GameAnalysisStartRequest.")
    return value
