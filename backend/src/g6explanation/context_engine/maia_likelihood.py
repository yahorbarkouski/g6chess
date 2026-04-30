"""Maia-2 human move-likelihood provider."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from importlib import import_module, metadata
from typing import Literal, cast

import chess

from g6explanation.context_engine.contracts import (
    HumanMoveLikelihood,
    MoveContextRequest,
    PlayerLevel,
)
from g6explanation.context_engine.exceptions import AnalysisError

MaiaModelType = Literal["auto", "rapid", "blitz"]
LoadedMaiaModelType = Literal["rapid", "blitz"]
InferenceEach = Callable[
    [object, object, str, int, int],
    tuple[Mapping[str, float], object],
]
MAIA2_BUCKET_START = 1100
MAIA2_BUCKET_END = 2000
MAIA2_BUCKET_INTERVAL = 100


@dataclass
class Maia2MoveLikelihoodProvider:
    model_type: MaiaModelType = "auto"
    device: Literal["cpu", "gpu"] = "cpu"
    save_root: str = "./maia2_models"
    top_move_limit: int = 5
    _model: object | None = field(default=None, init=False, repr=False)
    _prepared: object | None = field(default=None, init=False, repr=False)
    _inference_each: InferenceEach | None = field(default=None, init=False, repr=False)
    _loaded_model_type: LoadedMaiaModelType | None = field(default=None, init=False, repr=False)

    def likelihoods(
        self,
        board: chess.Board,
        candidate_moves: list[chess.Move],
        request: MoveContextRequest,
    ) -> dict[str, HumanMoveLikelihood]:
        model_type = self._select_model_type(request)
        self._load(model_type)
        if self._model is None or self._prepared is None or self._inference_each is None:
            raise AnalysisError("Maia-2 provider was not loaded correctly.")

        elo_self = _rating_or_default(request.player_level)
        elo_opponent = (
            _rating_or_default(request.opponent_level) if request.opponent_level else elo_self
        )
        plus_400 = elo_self + 400
        player_bucket = maia2_rating_bucket(elo_self)
        plus_400_bucket = maia2_rating_bucket(plus_400)

        move_probs, _ = self._inference_each(
            self._model, self._prepared, board.fen(), elo_self, elo_opponent
        )
        plus_400_probs: Mapping[str, float] = {}
        if plus_400_bucket != player_bucket:
            plus_400_probs, _ = self._inference_each(
                self._model, self._prepared, board.fen(), plus_400, elo_opponent
            )
        legal_uci = {move.uci() for move in board.legal_moves}
        ranked_uci = [uci for uci in move_probs if uci in legal_uci][: self.top_move_limit]
        candidate_uci = {move.uci() for move in candidate_moves}
        included_uci = candidate_uci | set(ranked_uci)
        package_version = _package_version("maia2")
        ranks = {uci: rank for rank, uci in enumerate(move_probs, start=1) if uci in legal_uci}

        return {
            uci: HumanMoveLikelihood(
                player_level_probability=move_probs.get(uci),
                plus_400_probability=plus_400_probs.get(uci)
                if plus_400_bucket != player_bucket
                else None,
                player_level_bucket=player_bucket,
                plus_400_level_bucket=plus_400_bucket,
                evidence_source=f"maia2_{model_type}",
                model_type=model_type,
                model_version=package_version,
                rank=ranks.get(uci),
                is_top_human_move=uci in ranked_uci,
            )
            for uci in included_uci
            if uci in legal_uci
        }

    def _select_model_type(self, request: MoveContextRequest) -> LoadedMaiaModelType:
        if self.model_type == "rapid":
            return "rapid"
        if self.model_type == "blitz":
            return self.model_type
        control = (request.time_control or "").lower()
        if "bullet" in control or "blitz" in control:
            return "blitz"
        return "rapid"

    def _load(self, model_type: LoadedMaiaModelType) -> None:
        if self._model is not None and self._loaded_model_type == model_type:
            return
        try:
            inference_module = import_module("maia2.inference")
            model_module = import_module("maia2.model")
        except ModuleNotFoundError as exc:
            raise AnalysisError(
                "Maia2MoveLikelihoodProvider requires the optional maia2==0.9 package. "
                "Install the project with the 'maia' extra to enable it."
            ) from exc

        from_pretrained = cast(Callable[..., object], model_module.from_pretrained)
        prepare = cast(Callable[[], object], inference_module.prepare)
        inference_each = cast(InferenceEach, inference_module.inference_each)

        self._model = from_pretrained(
            type=model_type,
            device=self.device,
            save_root=self.save_root,
        )
        self._prepared = prepare()
        self._inference_each = inference_each
        self._loaded_model_type = model_type


def _rating_or_default(level: PlayerLevel | None) -> int:
    if level is not None:
        rating = level.rating_value()
        if rating is not None:
            return rating
    return 1500


def maia2_rating_bucket(rating: int) -> str:
    if rating < MAIA2_BUCKET_START:
        return f"<{MAIA2_BUCKET_START}"
    if rating >= MAIA2_BUCKET_END:
        return f">={MAIA2_BUCKET_END}"
    lower = (
        (rating - MAIA2_BUCKET_START) // MAIA2_BUCKET_INTERVAL
    ) * MAIA2_BUCKET_INTERVAL + MAIA2_BUCKET_START
    upper = lower + MAIA2_BUCKET_INTERVAL - 1
    return f"{lower}-{upper}"


def _package_version(package_name: str) -> str | None:
    with suppress(metadata.PackageNotFoundError):
        return metadata.version(package_name)
    return None
