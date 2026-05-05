"""Default opening-book metadata for full-game analysis."""

from __future__ import annotations

import csv
import io
import logging
import tempfile
import threading
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import chess

from g6explanation.context_engine.contracts import ColorName
from g6explanation.game_analysis.contracts import (
    BookLine,
    BookLineMove,
    OpeningBookMetadata,
)

LOGGER = logging.getLogger(__name__)

LICHESS_OPENINGS_BASE_URL = "https://raw.githubusercontent.com/lichess-org/chess-openings/master"
LICHESS_OPENINGS_FILES = ("a.tsv", "b.tsv", "c.tsv", "d.tsv", "e.tsv")
LICHESS_OPENINGS_SOURCE = "https://github.com/lichess-org/chess-openings"
DEFAULT_OPENING_BOOK_CACHE_DIR = Path.home() / ".cache" / "g6explanation" / "lichess-openings"
DOWNLOAD_TIMEOUT_SECONDS = 20
DEFAULT_MAX_BOOK_LINES = 3
DEFAULT_MAX_BOOK_DEPTH = 8

BookLookupFn = Callable[[chess.Board, chess.Move], bool]
BookMainLinesFn = Callable[[chess.Board], list[BookLine]]
HasBookMovesFn = Callable[[chess.Board], bool]
LookupOpeningFn = Callable[[chess.Board], "OpeningIdentity | None"]

_default_book: OpeningBookDatabase | None = None
_default_book_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class OpeningBookPly:
    """Minimal per-ply board data needed for sequential book detection."""

    ply: int
    san: str
    uci: str
    side: ColorName
    fen_before: str
    fen_after: str


@dataclass(frozen=True, slots=True)
class OpeningIdentity:
    """ECO identity for a named opening position."""

    eco: str
    name: str


@dataclass(frozen=True, slots=True)
class BookMoveEntry:
    """One available book move from a position."""

    san: str
    uci: str
    weight: int


@dataclass(slots=True)
class _MoveAccumulator:
    san: str
    uci: str
    weight: int = 0


class OpeningBookDatabase:
    """In-memory opening book built from the CC0 Lichess openings dataset."""

    def __init__(
        self,
        *,
        moves_by_epd: dict[str, tuple[BookMoveEntry, ...]],
        openings_by_epd: dict[str, OpeningIdentity],
    ) -> None:
        self._moves_by_epd = moves_by_epd
        self._openings_by_epd = openings_by_epd

    @classmethod
    def empty(cls) -> OpeningBookDatabase:
        return cls(moves_by_epd={}, openings_by_epd={})

    @classmethod
    def from_tsv_texts(cls, texts: Iterable[str]) -> OpeningBookDatabase:
        move_accumulators: dict[str, dict[str, _MoveAccumulator]] = {}
        openings_by_epd: dict[str, OpeningIdentity] = {}

        for text in texts:
            for row in _opening_rows(text):
                moves = _parse_pgn_line(row.pgn)
                if not moves:
                    continue
                board = chess.Board()
                for san, uci in moves:
                    move = chess.Move.from_uci(uci)
                    epd = board.epd()
                    by_uci = move_accumulators.setdefault(epd, {})
                    accumulator = by_uci.get(uci)
                    if accumulator is None:
                        accumulator = _MoveAccumulator(san=san, uci=uci)
                        by_uci[uci] = accumulator
                    accumulator.weight += 1
                    board.push(move)
                openings_by_epd[board.epd()] = OpeningIdentity(eco=row.eco, name=row.name)

        moves_by_epd = {
            epd: tuple(
                sorted(
                    (
                        BookMoveEntry(san=entry.san, uci=entry.uci, weight=entry.weight)
                        for entry in by_uci.values()
                    ),
                    key=lambda entry: (-entry.weight, entry.san, entry.uci),
                )
            )
            for epd, by_uci in move_accumulators.items()
        }
        return cls(moves_by_epd=moves_by_epd, openings_by_epd=openings_by_epd)

    @property
    def entry_count(self) -> int:
        return sum(len(entries) for entries in self._moves_by_epd.values())

    @property
    def opening_count(self) -> int:
        return len(self._openings_by_epd)

    def book_lookup(self, board: chess.Board, move: chess.Move) -> bool:
        return move.uci() in {entry.uci for entry in self._entries_for(board)}

    def has_book_moves(self, board: chess.Board) -> bool:
        return bool(self._entries_for(board))

    def lookup_opening(self, board: chess.Board) -> OpeningIdentity | None:
        return self._openings_by_epd.get(board.epd())

    def book_main_lines(
        self,
        board: chess.Board,
        *,
        max_lines: int = DEFAULT_MAX_BOOK_LINES,
        max_depth: int = DEFAULT_MAX_BOOK_DEPTH,
    ) -> list[BookLine]:
        lines: list[BookLine] = []
        root_entries = self._entries_for(board)
        if not root_entries:
            return lines

        root_opening = self.lookup_opening(board)
        for root_entry in root_entries[:max_lines]:
            line_board = board.copy(stack=False)
            line_moves: list[BookLineMove] = []
            line_opening = root_opening
            next_entry: BookMoveEntry | None = root_entry

            for _ in range(max_depth):
                if next_entry is None:
                    break
                move = chess.Move.from_uci(next_entry.uci)
                if move not in line_board.legal_moves:
                    break
                line_moves.append(BookLineMove(san=line_board.san(move), uci=move.uci()))
                line_board.push(move)
                opening_hit = self.lookup_opening(line_board)
                if opening_hit is not None:
                    line_opening = opening_hit
                next_entry = self._first_entry_for(line_board)

            if line_moves:
                lines.append(
                    BookLine(
                        moves=line_moves,
                        weight=root_entry.weight,
                        opening_name=line_opening.name if line_opening is not None else None,
                        eco=line_opening.eco if line_opening is not None else None,
                    )
                )
        return lines

    def _entries_for(self, board: chess.Board) -> tuple[BookMoveEntry, ...]:
        return self._moves_by_epd.get(board.epd(), ())

    def _first_entry_for(self, board: chess.Board) -> BookMoveEntry | None:
        entries = self._entries_for(board)
        return entries[0] if entries else None


@dataclass(frozen=True, slots=True)
class _OpeningRow:
    eco: str
    name: str
    pgn: str


def run_opening_book_pass(
    plies: Sequence[OpeningBookPly],
    *,
    book_lookup_fn: BookLookupFn | None = None,
    book_main_lines_fn: BookMainLinesFn | None = None,
    has_book_moves_fn: HasBookMovesFn | None = None,
    lookup_opening_fn: LookupOpeningFn | None = None,
) -> dict[int, OpeningBookMetadata]:
    """Run a sequential opening-book pass over parsed game-analysis plies."""

    if (
        book_lookup_fn is None
        or book_main_lines_fn is None
        or has_book_moves_fn is None
        or lookup_opening_fn is None
    ):
        default_book = default_opening_book()
        book_lookup_fn = default_book.book_lookup if book_lookup_fn is None else book_lookup_fn
        book_main_lines_fn = (
            default_book.book_main_lines if book_main_lines_fn is None else book_main_lines_fn
        )
        has_book_moves_fn = (
            default_book.has_book_moves if has_book_moves_fn is None else has_book_moves_fn
        )
        lookup_opening_fn = (
            default_book.lookup_opening if lookup_opening_fn is None else lookup_opening_fn
        )

    metadata_by_ply: dict[int, OpeningBookMetadata] = {}
    book_ended: dict[ColorName, bool] = {"white": False, "black": False}
    running_opening: OpeningIdentity | None = None

    for ply in plies:
        is_book_move = False
        is_novelty = False
        book_lines: list[BookLine] = []
        board_before = chess.Board(ply.fen_before)
        played_move = chess.Move.from_uci(ply.uci)

        if not book_ended[ply.side]:
            if book_lookup_fn(board_before, played_move):
                is_book_move = True
                board_after = chess.Board(ply.fen_after)
                opening_hit = lookup_opening_fn(board_after)
                if opening_hit is not None:
                    running_opening = opening_hit
                book_lines = book_main_lines_fn(board_after)
            else:
                book_ended[ply.side] = True
                if has_book_moves_fn(board_before):
                    is_novelty = True

        opening_name = running_opening.name if running_opening is not None else None
        eco = running_opening.eco if running_opening is not None else None
        if is_book_move or is_novelty or book_lines or opening_name is not None or eco is not None:
            metadata_by_ply[ply.ply] = OpeningBookMetadata(
                is_book_move=is_book_move,
                is_novelty=is_novelty,
                book_lines=book_lines,
                opening_name=opening_name,
                eco=eco,
            )

    return metadata_by_ply


def default_opening_book() -> OpeningBookDatabase:
    """Return the process-global default book, downloading source data if needed."""

    global _default_book
    with _default_book_lock:
        if _default_book is None:
            try:
                _default_book = _load_default_opening_book()
            except Exception as exc:
                LOGGER.warning(
                    "Opening-book download/load failed; continuing without book: %s", exc
                )
                _default_book = OpeningBookDatabase.empty()
        return _default_book


def prefetch_default_opening_book() -> OpeningBookDatabase:
    """Download and validate the default book source for deployment image builds."""

    book = _load_default_opening_book()
    if book.entry_count == 0 or book.opening_count == 0:
        raise RuntimeError(
            "Default opening book loaded no entries from "
            f"{LICHESS_OPENINGS_SOURCE}; refusing to prefetch an empty book."
        )
    return book


def reset_default_opening_book_for_tests() -> None:
    """Reset the process-global book cache for tests."""

    global _default_book
    with _default_book_lock:
        _default_book = None


def ensure_default_opening_data(
    cache_dir: Path = DEFAULT_OPENING_BOOK_CACHE_DIR,
) -> tuple[Path, ...]:
    """Ensure the default Lichess opening TSV files exist locally."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename in LICHESS_OPENINGS_FILES:
        path = cache_dir / filename
        if not path.exists() or path.stat().st_size == 0:
            _download_file(f"{LICHESS_OPENINGS_BASE_URL}/{filename}", path)
        paths.append(path)
    source_path = cache_dir / "SOURCE.txt"
    if not source_path.exists():
        source_path.write_text(
            f"Source: {LICHESS_OPENINGS_SOURCE}\nLicense: CC0-1.0\n",
            encoding="utf-8",
        )
    return tuple(paths)


def _load_default_opening_book() -> OpeningBookDatabase:
    paths = ensure_default_opening_data()
    texts = [path.read_text(encoding="utf-8") for path in paths]
    book = OpeningBookDatabase.from_tsv_texts(texts)
    LOGGER.info(
        "Loaded default opening book: entries=%s named_positions=%s source=%s",
        book.entry_count,
        book.opening_count,
        LICHESS_OPENINGS_SOURCE,
    )
    return book


def _download_file(url: str, destination: Path) -> None:
    LOGGER.info("Downloading opening-book source: url=%s destination=%s", url, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (
        urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response,
        tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as tmp,
    ):
        tmp.write(response.read())
        temporary_path = Path(tmp.name)
    temporary_path.replace(destination)


def _opening_rows(text: str) -> Iterable[_OpeningRow]:
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for row in reader:
        eco = (row.get("eco") or "").strip()
        name = (row.get("name") or "").strip()
        pgn = (row.get("pgn") or "").strip()
        if eco and name and pgn:
            yield _OpeningRow(eco=eco, name=name, pgn=pgn)


def _parse_pgn_line(pgn: str) -> list[tuple[str, str]]:
    board = chess.Board()
    moves: list[tuple[str, str]] = []
    for raw_token in pgn.split():
        token = raw_token.strip()
        if not token or token[0].isdigit() or token in {"*", "1-0", "0-1", "1/2-1/2"}:
            continue
        while token.endswith(("!", "?")):
            token = token[:-1]
        try:
            move = board.parse_san(token)
        except (
            chess.InvalidMoveError,
            chess.IllegalMoveError,
            chess.AmbiguousMoveError,
            ValueError,
        ):
            return []
        moves.append((board.san(move), move.uci()))
        board.push(move)
    return moves


if __name__ == "__main__":
    loaded_book = prefetch_default_opening_book()
    print(
        "Prefetched opening book "
        f"entries={loaded_book.entry_count} named_positions={loaded_book.opening_count} "
        f"source={LICHESS_OPENINGS_SOURCE}"
    )
