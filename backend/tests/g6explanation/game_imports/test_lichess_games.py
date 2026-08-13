"""Tests for Lichess public game PGN resolution."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping

import pytest

from g6explanation.game_imports import (
    InMemoryGameImportCache,
    LichessGameInvalidPgnError,
    LichessGameNotFinishedError,
    LichessGameNotFoundError,
    LichessGameResolver,
    extract_lichess_game_id,
)

GAME_ID = "fY44h4OY"
PUBLIC_PGN = """
[Event "rated blitz game"]
[Site "https://lichess.org/fY44h4OY"]
[Date "2018.03.29"]
[Round "-"]
[White "pveldman"]
[Black "thibault"]
[Result "1-0"]
[GameId "fY44h4OY"]
[UTCDate "2018.03.29"]
[UTCTime "01:38:15"]
[WhiteElo "1610"]
[BlackElo "1601"]
[WhiteRatingDiff "+10"]
[BlackRatingDiff "-10"]
[Variant "Standard"]
[TimeControl "180+0"]
[ECO "C62"]
[Opening "Ruy Lopez: Steinitz Defense"]
[Termination "Normal"]

1. e4 { [%clk 0:03:00] } 1... e5 { [%clk 0:03:00] } 2. Nf3 { [%clk 0:02:59] } 1-0
""".strip()


def test_extract_lichess_game_id_accepts_supported_urls() -> None:
    assert extract_lichess_game_id("https://lichess.org/fY44h4OY") == GAME_ID
    assert extract_lichess_game_id("https://lichess.org/fY44h4OY/black#56") == GAME_ID
    assert extract_lichess_game_id("https://www.lichess.org/fY44h4OY/white") == GAME_ID
    assert extract_lichess_game_id("https://lichess.org/game/export/fY44h4OY") == GAME_ID
    assert extract_lichess_game_id("lichess.org/fY44h4OY") == GAME_ID


def test_extract_lichess_game_id_rejects_unsupported_urls() -> None:
    with pytest.raises(LichessGameNotFoundError):
        extract_lichess_game_id("https://lichess.org/@/thibault")
    with pytest.raises(LichessGameNotFoundError):
        extract_lichess_game_id("https://www.chess.com/game/live/168193636078")


def test_resolver_exports_parseable_standard_pgn() -> None:
    transport = FakeLichessTransport(payload=_game_payload())
    resolver = LichessGameResolver(transport=transport, sleep=lambda _: None)

    imported = resolver.resolve(f"https://lichess.org/{GAME_ID}/black#56")

    assert imported.pgn == PUBLIC_PGN
    assert imported.metadata.source == "lichess_game_url"
    assert imported.metadata.source_url == f"https://lichess.org/{GAME_ID}"
    assert imported.metadata.external_game_id == GAME_ID
    assert imported.metadata.title == "pveldman vs thibault"
    assert imported.metadata.white_rating == 1610
    assert imported.metadata.black_rating == 1601
    assert imported.metadata.time_control == "180+0"
    assert imported.metadata.result == "1-0"
    assert imported.metadata.allows_global_training is False
    assert transport.calls == 1


def test_resolver_uses_json_ratings_when_pgn_headers_omit_elos() -> None:
    pgn_without_elos = "\n".join(
        line
        for line in PUBLIC_PGN.splitlines()
        if not line.startswith("[WhiteElo ") and not line.startswith("[BlackElo ")
    )
    resolver = LichessGameResolver(
        transport=FakeLichessTransport(payload=_game_payload(pgn=pgn_without_elos)),
        sleep=lambda _: None,
    )

    imported = resolver.resolve(f"https://lichess.org/{GAME_ID}")

    assert imported.metadata.white_rating == 1610
    assert imported.metadata.black_rating == 1601


def test_resolver_uses_cache_before_transport() -> None:
    transport = FakeLichessTransport(payload=_game_payload())
    cache = InMemoryGameImportCache()
    resolver = LichessGameResolver(cache=cache, transport=transport, sleep=lambda _: None)

    first = resolver.resolve(f"https://lichess.org/{GAME_ID}")
    second = resolver.resolve(f"https://lichess.org/{GAME_ID}")

    assert first == second
    assert transport.calls == 1


def test_resolver_rejects_unfinished_games() -> None:
    resolver = LichessGameResolver(
        transport=FakeLichessTransport(payload=_game_payload(status="started")),
        sleep=lambda _: None,
    )

    with pytest.raises(LichessGameNotFinishedError):
        resolver.resolve(f"https://lichess.org/{GAME_ID}")


def test_resolver_rejects_non_standard_variants() -> None:
    resolver = LichessGameResolver(
        transport=FakeLichessTransport(payload=_game_payload(variant="chess960")),
        sleep=lambda _: None,
    )

    with pytest.raises(LichessGameInvalidPgnError):
        resolver.resolve(f"https://lichess.org/{GAME_ID}")


def test_resolver_rejects_invalid_pgn() -> None:
    resolver = LichessGameResolver(
        transport=FakeLichessTransport(payload=_game_payload(pgn='[Event "Broken"]\n\n*')),
        sleep=lambda _: None,
    )

    with pytest.raises(LichessGameInvalidPgnError):
        resolver.resolve(f"https://lichess.org/{GAME_ID}")


@pytest.mark.skipif(
    os.getenv("G6EXPLANATION_RUN_LICHESS_IMPORT") != "1",
    reason="set G6EXPLANATION_RUN_LICHESS_IMPORT=1 to resolve a real Lichess PGN",
)
def test_real_lichess_game_url_resolves_to_parseable_pgn() -> None:
    resolver = LichessGameResolver()

    imported = resolver.resolve("https://lichess.org/fY44h4OY")

    assert imported.metadata.external_game_id == "fY44h4OY"
    assert "[White " in imported.pgn
    assert imported.metadata.white_rating is not None
    assert imported.metadata.black_rating is not None
    assert imported.metadata.allows_global_training is False


class FakeLichessTransport:
    """Typed fake for Lichess HTTP GETs."""

    def __init__(self, *, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        assert headers["User-Agent"]
        assert headers["Accept"] == "application/json"
        assert timeout_seconds > 0
        self.calls += 1
        if url.startswith(f"https://lichess.org/game/export/{GAME_ID}?"):
            return 200, json.dumps(self.payload).encode("utf-8")
        return 404, b"{}"


def _game_payload(
    *,
    pgn: str = PUBLIC_PGN,
    status: str = "resign",
    variant: str = "standard",
) -> dict[str, object]:
    return {
        "id": GAME_ID,
        "rated": True,
        "variant": variant,
        "speed": "blitz",
        "perf": "blitz",
        "createdAt": 1522287495000,
        "lastMoveAt": 1522288095000,
        "status": status,
        "players": {
            "white": {"user": {"name": "pveldman", "id": "pveldman"}, "rating": 1610},
            "black": {"user": {"name": "thibault", "id": "thibault"}, "rating": 1601},
        },
        "winner": "white",
        "clock": {"initial": 180, "increment": 0, "totalTime": 180},
        "pgn": pgn,
    }
