"""Tests for importing one public Lichess study chapter."""

from __future__ import annotations

import os
from collections.abc import Mapping

import pytest

from g6explanation.game_imports import (
    InMemoryGameImportCache,
    LichessStudyChapterInvalidPgnError,
    LichessStudyChapterNotFoundError,
    LichessStudyChapterResolver,
    extract_lichess_study_chapter_identity,
)

STUDY_ID = "ybdiAVdQ"
CHAPTER_ID = "2pHkbFS9"
STUDY_PGN = """
[Event "Annotated game"]
[Site "https://lichess.org/study/ybdiAVdQ/2pHkbFS9"]
[Date "2026.08.13"]
[Round "-"]
[White "Alpha"]
[Black "Beta"]
[Result "1-0"]
[WhiteElo "1600"]
[BlackElo "1500"]
[Variant "Standard"]
[TimeControl "180+2"]

1. e4 { [%clk 0:03:01] } 1... e5 { [%clk 0:02:59] } 2. Nf3 1-0
""".strip()


def test_extract_study_chapter_identity_accepts_canonical_urls() -> None:
    identity = extract_lichess_study_chapter_identity(
        f"https://lichess.org/study/{STUDY_ID}/{CHAPTER_ID}#12"
    )

    assert identity.study_id == STUDY_ID
    assert identity.chapter_id == CHAPTER_ID
    assert identity.external_game_id == f"{STUDY_ID}/{CHAPTER_ID}"


@pytest.mark.parametrize(
    "url",
    [
        f"https://lichess.org/study/{STUDY_ID}",
        "https://lichess.org/@/thibault",
        f"https://example.com/study/{STUDY_ID}/{CHAPTER_ID}",
    ],
)
def test_extract_study_chapter_identity_rejects_unsupported_urls(url: str) -> None:
    with pytest.raises(LichessStudyChapterNotFoundError):
        extract_lichess_study_chapter_identity(url)


def test_resolver_exports_parseable_standard_chapter_pgn() -> None:
    transport = FakeStudyTransport(pgn=STUDY_PGN)
    resolver = LichessStudyChapterResolver(transport=transport, sleep=lambda _: None)

    imported = resolver.resolve(f"https://lichess.org/study/{STUDY_ID}/{CHAPTER_ID}")

    assert imported.pgn == STUDY_PGN
    assert imported.metadata.source == "lichess_study_chapter_url"
    assert imported.metadata.source_url == (f"https://lichess.org/study/{STUDY_ID}/{CHAPTER_ID}")
    assert imported.metadata.external_game_id == f"{STUDY_ID}/{CHAPTER_ID}"
    assert imported.metadata.title == "Alpha vs Beta"
    assert imported.metadata.white_rating == 1600
    assert imported.metadata.black_rating == 1500
    assert imported.metadata.time_control == "180+2"
    assert imported.metadata.allows_global_training is False
    assert "study" in imported.metadata.rights_basis.lower()
    assert transport.calls == 1


def test_resolver_uses_cache_before_transport() -> None:
    transport = FakeStudyTransport(pgn=STUDY_PGN)
    resolver = LichessStudyChapterResolver(
        cache=InMemoryGameImportCache(),
        transport=transport,
        sleep=lambda _: None,
    )

    first = resolver.resolve(f"https://lichess.org/study/{STUDY_ID}/{CHAPTER_ID}")
    second = resolver.resolve(f"https://lichess.org/study/{STUDY_ID}/{CHAPTER_ID}")

    assert first == second
    assert transport.calls == 1


def test_resolver_rejects_non_standard_chapter_pgn() -> None:
    resolver = LichessStudyChapterResolver(
        transport=FakeStudyTransport(pgn=STUDY_PGN.replace('"Standard"', '"Chess960"')),
        sleep=lambda _: None,
    )

    with pytest.raises(LichessStudyChapterInvalidPgnError):
        resolver.resolve(f"https://lichess.org/study/{STUDY_ID}/{CHAPTER_ID}")


@pytest.mark.skipif(
    os.getenv("G6EXPLANATION_RUN_LICHESS_STUDY_IMPORT") != "1",
    reason="set G6EXPLANATION_RUN_LICHESS_STUDY_IMPORT=1 to resolve a real study chapter",
)
def test_real_lichess_study_chapter_resolves_to_parseable_pgn() -> None:
    imported = LichessStudyChapterResolver().resolve(
        f"https://lichess.org/study/{STUDY_ID}/{CHAPTER_ID}"
    )

    assert imported.metadata.external_game_id == f"{STUDY_ID}/{CHAPTER_ID}"
    assert imported.metadata.allows_global_training is False
    assert imported.pgn


class FakeStudyTransport:
    """Typed fake for Lichess study PGN HTTP GETs."""

    def __init__(self, *, pgn: str) -> None:
        self.pgn = pgn
        self.calls = 0

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        assert headers["User-Agent"]
        assert headers["Accept"] == "application/x-chess-pgn"
        assert timeout_seconds > 0
        assert url.startswith(f"https://lichess.org/api/study/{STUDY_ID}/{CHAPTER_ID}.pgn?")
        assert "comments=false" in url
        assert "variations=false" in url
        assert "clocks=true" in url
        self.calls += 1
        return 200, self.pgn.encode("utf-8")
