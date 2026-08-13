from __future__ import annotations

import importlib.util
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from dataclasses import dataclass, field
from types import SimpleNamespace

import chess
import pytest

from g6explanation.context_engine import maia_likelihood as maia_module
from g6explanation.context_engine.contracts import MoveContextRequest, PlayerLevel
from g6explanation.context_engine.maia_likelihood import (
    Maia2MoveLikelihoodProvider,
    maia2_rating_bucket,
)


def test_maia2_rating_bucket_matches_public_package_buckets() -> None:
    assert maia2_rating_bucket(900) == "<1100"
    assert maia2_rating_bucket(1200) == "1200-1299"
    assert maia2_rating_bucket(1999) == "1900-1999"
    assert maia2_rating_bucket(2000) == ">=2000"
    assert maia2_rating_bucket(2800) == ">=2000"


def test_maia2_provider_reuses_loaded_model_across_instances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_maia_runtime(monkeypatch)
    board, request = _starting_position_request()

    first_provider = Maia2MoveLikelihoodProvider(device="cpu", save_root="./maia2_models")
    second_provider = Maia2MoveLikelihoodProvider(device="cpu", save_root="./maia2_models")

    first_stats = first_provider.likelihoods(board, [chess.Move.from_uci("e2e4")], request)
    second_stats = second_provider.likelihoods(board, [chess.Move.from_uci("e2e4")], request)

    assert "e2e4" in first_stats
    assert "e2e4" in second_stats
    assert calls.from_pretrained == [("rapid", "cpu", "./maia2_models")]
    assert calls.prepare == 1


def test_maia2_provider_load_cache_is_thread_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_maia_runtime(monkeypatch, load_sleep_seconds=0.05)
    board, request = _starting_position_request()

    def likelihood_count() -> int:
        provider = Maia2MoveLikelihoodProvider(device="cpu", save_root="./maia2_models")
        stats = provider.likelihoods(board, [chess.Move.from_uci("e2e4")], request)
        return len(stats)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = [
            future.result()
            for future in as_completed(executor.submit(likelihood_count) for _ in range(8))
        ]

    assert results == [2] * 8
    assert calls.from_pretrained == [("rapid", "cpu", "./maia2_models")]
    assert calls.prepare == 1
    assert calls.inference == 16


@pytest.mark.skipif(
    os.getenv("G6EXPLANATION_RUN_MAIA2") != "1" or importlib.util.find_spec("maia2") is None,
    reason="Maia-2 smoke test requires optional runtime, model files, and opt-in env var",
)
def test_maia2_provider_returns_legal_move_likelihoods() -> None:
    board = chess.Board()
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200, "lichess"),
        time_control="rapid",
    )
    provider = Maia2MoveLikelihoodProvider(
        device="cpu",
        save_root=os.getenv("MAIA2_MODEL_ROOT", "./maia2_models"),
    )

    stats = provider.likelihoods(board, [chess.Move.from_uci("e2e4")], request)

    assert "e2e4" in stats
    assert stats["e2e4"].player_level_probability is not None
    assert stats["e2e4"].plus_400_probability is not None
    assert stats["e2e4"].player_level_bucket == "1200-1299"
    assert stats["e2e4"].plus_400_level_bucket == "1600-1699"
    assert all(chess.Move.from_uci(uci) in board.legal_moves for uci in stats)


def _starting_position_request() -> tuple[chess.Board, MoveContextRequest]:
    board = chess.Board()
    return board, MoveContextRequest(
        fen_before=board.fen(),
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1500, "test"),
        time_control="rapid",
    )


def _install_fake_maia_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    load_sleep_seconds: float = 0,
) -> _FakeMaiaCalls:
    maia_module.clear_maia2_model_cache()
    calls = _FakeMaiaCalls()

    def from_pretrained(*, type: str, device: str, save_root: str) -> object:
        if load_sleep_seconds:
            time.sleep(load_sleep_seconds)
        calls.from_pretrained.append((type, device, save_root))
        return object()

    def prepare() -> object:
        calls.prepare += 1
        return object()

    def inference_each(
        model: object,
        prepared: object,
        fen: str,
        elo_self: int,
        elo_opponent: int,
    ) -> tuple[dict[str, float], None]:
        calls.inference += 1
        return {"e2e4": 0.3, "d2d4": 0.2}, None

    def fake_import_module(name: str) -> object:
        if name == "maia2.model":
            return SimpleNamespace(from_pretrained=from_pretrained)
        if name == "maia2.inference":
            return SimpleNamespace(prepare=prepare, inference_each=inference_each)
        if name == "torch":
            return SimpleNamespace(inference_mode=lambda: nullcontext())
        raise ModuleNotFoundError(name)

    def fake_package_version(package_name: str) -> str:
        return f"fake-{package_name}"

    monkeypatch.setattr(maia_module, "import_module", fake_import_module)
    monkeypatch.setattr(maia_module, "_package_version", fake_package_version)
    return calls


@dataclass
class _FakeMaiaCalls:
    from_pretrained: list[tuple[str, str, str]] = field(
        default_factory=lambda: list[tuple[str, str, str]]()
    )
    prepare: int = 0
    inference: int = 0
