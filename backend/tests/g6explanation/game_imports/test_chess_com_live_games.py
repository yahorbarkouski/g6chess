"""Tests for Chess.com public live-game PGN resolution."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping

import pytest

from g6explanation.game_imports import (
    ChessComLiveGameInvalidPgnError,
    ChessComLiveGameNotFinishedError,
    ChessComLiveGameNotFoundError,
    ChessComLiveGameResolver,
    ChessComLiveGameUnavailableError,
    InMemoryGameImportCache,
    extract_chess_com_live_game_id,
)

GAME_ID = "168193636078"
PUBLIC_PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.05.03"]
[Round "-"]
[White "OldFr3d"]
[Black "mantegnac"]
[Result "1-0"]
[WhiteElo "1269"]
[BlackElo "1232"]
[TimeControl "180"]
[Link "https://www.chess.com/game/live/168193636078"]

1. d4 d5 2. c4 c6 1-0
""".strip()


def test_extract_chess_com_live_game_id_accepts_supported_urls() -> None:
    assert extract_chess_com_live_game_id("https://www.chess.com/game/live/168193636078") == GAME_ID
    assert (
        extract_chess_com_live_game_id(
            "https://www.chess.com/analysis/game/live/168193636078?tab=analysis"
        )
        == GAME_ID
    )


def test_extract_chess_com_live_game_id_rejects_unsupported_urls() -> None:
    with pytest.raises(ChessComLiveGameNotFoundError):
        extract_chess_com_live_game_id("https://www.chess.com/member/mantegnac")


def test_resolver_finds_pgn_from_white_archive() -> None:
    transport = FakeChessComTransport(
        callback=_callback_payload(),
        white_archive_games=[_archive_game()],
    )
    resolver = ChessComLiveGameResolver(transport=transport, sleep=lambda _: None)

    imported = resolver.resolve(f"https://www.chess.com/game/live/{GAME_ID}")

    assert imported.pgn == PUBLIC_PGN
    assert imported.metadata.external_game_id == GAME_ID
    assert imported.metadata.title == "OldFr3d vs mantegnac"
    assert imported.metadata.white_rating == 1269
    assert imported.metadata.black_rating == 1232
    assert imported.metadata.time_control == "180"
    assert imported.metadata.allows_global_training is False
    assert transport.archive_calls == ["oldfr3d"]


def test_resolver_falls_back_to_black_archive() -> None:
    transport = FakeChessComTransport(
        callback=_callback_payload(),
        white_archive_games=[],
        black_archive_games=[_archive_game()],
    )
    resolver = ChessComLiveGameResolver(transport=transport, sleep=lambda _: None)

    imported = resolver.resolve(f"https://www.chess.com/game/live/{GAME_ID}")

    assert imported.metadata.black_username == "mantegnac"
    assert transport.archive_calls == ["oldfr3d", "mantegnac"]


def test_resolver_uses_cache_before_transport() -> None:
    transport = FakeChessComTransport(
        callback=_callback_payload(),
        white_archive_games=[_archive_game()],
    )
    cache = InMemoryGameImportCache()
    resolver = ChessComLiveGameResolver(cache=cache, transport=transport, sleep=lambda _: None)

    first = resolver.resolve(f"https://www.chess.com/game/live/{GAME_ID}")
    second = resolver.resolve(f"https://www.chess.com/game/live/{GAME_ID}")

    assert first == second
    assert transport.callback_calls == 1


def test_resolver_rejects_unfinished_games() -> None:
    transport = FakeChessComTransport(
        callback=_callback_payload(is_finished=False),
        white_archive_games=[_archive_game()],
    )
    resolver = ChessComLiveGameResolver(transport=transport, sleep=lambda _: None)

    with pytest.raises(ChessComLiveGameNotFinishedError):
        resolver.resolve(f"https://www.chess.com/game/live/{GAME_ID}")


def test_resolver_rejects_missing_callback_headers() -> None:
    transport = FakeChessComTransport(
        callback={"game": {"isFinished": True}},
        white_archive_games=[_archive_game()],
    )
    resolver = ChessComLiveGameResolver(transport=transport, sleep=lambda _: None)

    with pytest.raises(ChessComLiveGameUnavailableError):
        resolver.resolve(f"https://www.chess.com/game/live/{GAME_ID}")


def test_resolver_rejects_missing_archive_match() -> None:
    transport = FakeChessComTransport(
        callback=_callback_payload(),
        white_archive_games=[],
        black_archive_games=[],
    )
    resolver = ChessComLiveGameResolver(transport=transport, sleep=lambda _: None)

    with pytest.raises(ChessComLiveGameNotFoundError):
        resolver.resolve(f"https://www.chess.com/game/live/{GAME_ID}")


def test_resolver_rejects_non_chess_archive_record() -> None:
    raw = {**_archive_game(), "rules": "chess960"}
    transport = FakeChessComTransport(callback=_callback_payload(), white_archive_games=[raw])
    resolver = ChessComLiveGameResolver(transport=transport, sleep=lambda _: None)

    with pytest.raises(ChessComLiveGameInvalidPgnError):
        resolver.resolve(f"https://www.chess.com/game/live/{GAME_ID}")


def test_resolver_rejects_invalid_archive_pgn() -> None:
    raw = {**_archive_game(), "pgn": '[Event "Broken"]\n\n*'}
    transport = FakeChessComTransport(callback=_callback_payload(), white_archive_games=[raw])
    resolver = ChessComLiveGameResolver(transport=transport, sleep=lambda _: None)

    with pytest.raises(ChessComLiveGameInvalidPgnError):
        resolver.resolve(f"https://www.chess.com/game/live/{GAME_ID}")


@pytest.mark.skipif(
    os.getenv("G6EXPLANATION_RUN_CHESSCOM_IMPORT") != "1",
    reason="set G6EXPLANATION_RUN_CHESSCOM_IMPORT=1 to resolve a real Chess.com PGN",
)
def test_real_chess_com_live_game_url_resolves_to_parseable_pgn() -> None:
    resolver = ChessComLiveGameResolver.from_env()

    imported = resolver.resolve("https://www.chess.com/game/live/168193636078")

    assert imported.metadata.external_game_id == "168193636078"
    assert "[White " in imported.pgn
    assert imported.metadata.allows_global_training is False


class FakeChessComTransport:
    """Typed fake for Chess.com HTTP GETs."""

    def __init__(
        self,
        *,
        callback: dict[str, object],
        white_archive_games: list[dict[str, object]] | None = None,
        black_archive_games: list[dict[str, object]] | None = None,
    ) -> None:
        self.callback = callback
        self.white_archive_games = white_archive_games or []
        self.black_archive_games = black_archive_games or []
        self.callback_calls = 0
        self.archive_calls: list[str] = []

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        assert headers["User-Agent"]
        assert timeout_seconds > 0
        if url.endswith(f"/callback/live/game/{GAME_ID}"):
            self.callback_calls += 1
            return 200, _json_bytes(self.callback)
        if "/player/oldfr3d/games/2026/05" in url:
            self.archive_calls.append("oldfr3d")
            return 200, _json_bytes({"games": self.white_archive_games})
        if "/player/mantegnac/games/2026/05" in url:
            self.archive_calls.append("mantegnac")
            return 200, _json_bytes({"games": self.black_archive_games})
        return 404, b"{}"


def _callback_payload(*, is_finished: bool = True) -> dict[str, object]:
    return {
        "game": {
            "isFinished": is_finished,
            "pgnHeaders": {
                "Date": "2026.05.03",
                "White": "OldFr3d",
                "Black": "mantegnac",
                "TimeControl": "180",
            },
        }
    }


def _archive_game() -> dict[str, object]:
    return {
        "url": f"https://www.chess.com/game/live/{GAME_ID}",
        "pgn": PUBLIC_PGN,
        "rules": "chess",
        "time_control": "180",
        "white": {"username": "OldFr3d", "rating": 1269},
        "black": {"username": "mantegnac", "rating": 1232},
    }


def _json_bytes(value: dict[str, object]) -> bytes:
    return json.dumps(value).encode("utf-8")
