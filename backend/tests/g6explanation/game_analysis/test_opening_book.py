from __future__ import annotations

import io
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

import chess
import chess.pgn
import pytest

from g6explanation.context_engine.contracts import MoveBeauty, MoveSignificance
from g6explanation.game_analysis import opening_book
from g6explanation.game_analysis.contracts import (
    BookLine,
    BookLineMove,
    GameAnalysisSnapshot,
    GameMoveAnalysis,
    OpeningBookMetadata,
)
from g6explanation.game_analysis.opening_book import (
    OpeningBookDatabase,
    OpeningBookPly,
    OpeningIdentity,
    run_opening_book_pass,
)

SAMPLE_TSV = """eco\tname\tpgn
C20\tKing's Pawn Game\t1. e4
C20\tKing's Pawn Game: Open Game\t1. e4 e5
C44\tKing's Pawn Game: Normal Variation\t1. e4 e5 2. Nf3 Nc6
B00\tOwen Defense\t1. e4 b6
"""


def test_opening_book_database_builds_book_lines_from_lichess_rows() -> None:
    book = OpeningBookDatabase.from_tsv_texts([SAMPLE_TSV])
    board = chess.Board()
    e4 = chess.Move.from_uci("e2e4")

    assert book.entry_count > 0
    assert book.opening_count == 4
    assert book.book_lookup(board, e4)

    board.push(e4)
    lines = book.book_main_lines(board)

    assert [line.moves[0].san for line in lines] == ["e5", "b6"]
    assert lines[0].weight > lines[1].weight
    assert [move.san for move in lines[0].moves] == ["e5", "Nf3", "Nc6"]
    assert lines[0].opening_name == "King's Pawn Game: Normal Variation"
    assert lines[0].eco == "C44"


def test_run_opening_book_pass_tracks_per_side_novelties_and_running_opening() -> None:
    plies = opening_book_plies("1. e4 e5 2. Nf3 Nc6 3. h3 a6 4. a3 *")
    book_moves = {"e4", "e5", "Nf3", "Nc6", "a6"}

    def book_lookup_fn(board: chess.Board, move: chess.Move) -> bool:
        return board.san(move) in book_moves

    def book_main_lines_fn(_board: chess.Board) -> list[BookLine]:
        return [
            BookLine(
                moves=[BookLineMove(san="stub", uci="a2a3")],
                weight=1,
                opening_name="King's Pawn Game",
                eco="C20",
            )
        ]

    first_book_epd = chess.Board(plies[0].fen_after).epd()

    def lookup_opening_fn(board: chess.Board) -> OpeningIdentity | None:
        if board.epd() == first_book_epd:
            return OpeningIdentity(eco="C20", name="King's Pawn Game")
        return None

    metadata = run_opening_book_pass(
        plies,
        book_lookup_fn=book_lookup_fn,
        book_main_lines_fn=book_main_lines_fn,
        has_book_moves_fn=lambda _board: True,
        lookup_opening_fn=lookup_opening_fn,
    )

    assert [metadata[ply].is_book_move for ply in range(1, 8)] == [
        True,
        True,
        True,
        True,
        False,
        True,
        False,
    ]
    assert [metadata[ply].is_novelty for ply in range(1, 8)] == [
        False,
        False,
        False,
        False,
        True,
        False,
        False,
    ]
    assert all(metadata[ply].opening_name == "King's Pawn Game" for ply in range(1, 8))


def test_snapshot_contract_round_trips_opening_book_metadata() -> None:
    now = datetime.now(UTC).isoformat()
    snapshot = GameAnalysisSnapshot(
        analysis_id="analysis-1",
        status="succeeded",
        total_plies=1,
        context_completed=1,
        explanation_required=0,
        explanation_completed=0,
        explanation_failed=0,
        explain_significance=["critical"],
        created_at=now,
        updated_at=now,
        moves=[
            GameMoveAnalysis(
                ply=1,
                san="e4",
                uci="e2e4",
                player_color="white",
                state="context_ready",
                requires_explanation=False,
                quality="excellent",
                significance=MoveSignificance(label="low", score=0.1),
                beauty=MoveBeauty(label="low", score=0.0),
                context_latency_seconds=0.01,
                opening_book=OpeningBookMetadata(
                    is_book_move=True,
                    book_lines=[
                        BookLine(
                            moves=[BookLineMove(san="e5", uci="e7e5")],
                            weight=2,
                            opening_name="King's Pawn Game: Open Game",
                            eco="C20",
                        )
                    ],
                    opening_name="King's Pawn Game",
                    eco="C20",
                ),
            )
        ],
    )

    round_tripped = GameAnalysisSnapshot.model_validate_json(snapshot.model_dump_json())

    assert round_tripped == snapshot
    assert round_tripped.moves[0].opening_book is not None
    assert round_tripped.moves[0].opening_book.book_lines[0].moves[0].uci == "e7e5"


def test_download_file_retries_transient_url_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "a.tsv"
    calls = 0
    sleeps: list[float] = []

    def fake_urlopen(url: str, *, timeout: float) -> FakeUrlResponse:
        nonlocal calls
        del url, timeout
        calls += 1
        if calls == 1:
            raise urllib.error.URLError(ConnectionResetError(104, "Connection reset by peer"))
        return FakeUrlResponse(b"eco\tname\tpgn\n")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    opening_book._download_file(  # pyright: ignore[reportPrivateUsage]
        "https://example.test/a.tsv",
        destination,
        max_retries=1,
        retry_backoff_seconds=0.25,
        sleep=sleeps.append,
    )

    assert calls == 2
    assert sleeps == [0.25]
    assert destination.read_bytes() == b"eco\tname\tpgn\n"


class FakeUrlResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> FakeUrlResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    def read(self) -> bytes:
        return self._body


def opening_book_plies(pgn: str) -> list[OpeningBookPly]:
    game = chess.pgn.read_game(io.StringIO(pgn))
    assert game is not None
    board = game.board()
    plies: list[OpeningBookPly] = []
    for ply, move in enumerate(game.mainline_moves(), start=1):
        fen_before = board.fen()
        san = board.san(move)
        board_after = board.copy(stack=False)
        board_after.push(move)
        plies.append(
            OpeningBookPly(
                ply=ply,
                san=san,
                uci=move.uci(),
                side="white" if board.turn == chess.WHITE else "black",
                fen_before=fen_before,
                fen_after=board_after.fen(),
            )
        )
        board.push(move)
    return plies
