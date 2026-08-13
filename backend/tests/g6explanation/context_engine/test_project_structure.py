from __future__ import annotations

from pathlib import Path


def test_legacy_flat_context_engine_wrappers_are_removed() -> None:
    context_engine = Path("src/g6explanation/context_engine")

    assert not (context_engine / "move_quality.py").exists()
    assert not (context_engine / "move_beauty.py").exists()
    assert not (context_engine / "candidate_policy.py").exists()
