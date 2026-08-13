"""Curated real-game PGNs used by real-provider evaluations."""

from __future__ import annotations

import io
from dataclasses import dataclass
from textwrap import dedent

import chess
import chess.pgn

from g6explanation.context_engine.contracts import ColorName, PlayerLevel

OPERA_GAME = dedent(
    """
    [Event "Casual Game"]
    [Site "Paris FRA"]
    [Date "1858.??.??"]
    [Round "?"]
    [White "Paul Morphy"]
    [Black "Duke Karl / Count Isouard"]
    [Result "1-0"]

    1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5
    6. Bc4 Nf6 7. Qb3 Qe7 8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5
    11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 14. Rd1 Qe6
    15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0
    """
).strip()

BYRNE_FISCHER = dedent(
    """
    [Event "Third Rosenwald Trophy"]
    [Site "New York, NY USA"]
    [Date "1956.10.17"]
    [Round "8"]
    [White "Donald Byrne"]
    [Black "Robert James Fischer"]
    [Result "0-1"]

    1. Nf3 Nf6 2. c4 g6 3. Nc3 Bg7 4. d4 O-O 5. Bf4 d5
    6. Qb3 dxc4 7. Qxc4 c6 8. e4 Nbd7 9. Rd1 Nb6 10. Qc5 Bg4
    11. Bg5 Na4 12. Qa3 Nxc3 13. bxc3 Nxe4 14. Bxe7 Qb6
    15. Bc4 Nxc3 16. Bc5 Rfe8+ 17. Kf1 Be6 18. Bxb6 Bxc4+
    19. Kg1 Ne2+ 20. Kf1 Nxd4+ 21. Kg1 Ne2+ 22. Kf1 Nc3+
    23. Kg1 axb6 24. Qb4 Ra4 25. Qxb6 Nxd1 26. h3 Rxa2
    27. Kh2 Nxf2 28. Re1 Rxe1 29. Qd8+ Bf8 30. Nxe1 Bd5
    31. Nf3 Ne4 32. Qb8 b5 33. h4 h5 34. Ne5 Kg7 35. Kg1 Bc5+
    36. Kf1 Ng3+ 37. Ke1 Bb4+ 38. Kd1 Bb3+ 39. Kc1 Ne2+
    40. Kb1 Nc3+ 41. Kc1 Rc2# 0-1
    """
).strip()

KASPAROV_TOPALOV = dedent(
    """
    [Event "Hoogovens Group A"]
    [Site "Wijk aan Zee NED"]
    [Date "1999.01.20"]
    [Round "4"]
    [White "Garry Kasparov"]
    [Black "Veselin Topalov"]
    [Result "1-0"]

    1. e4 d6 2. d4 Nf6 3. Nc3 g6 4. Be3 Bg7 5. Qd2 c6
    6. f3 b5 7. Nge2 Nbd7 8. Bh6 Bxh6 9. Qxh6 Bb7
    10. a3 e5 11. O-O-O Qe7 12. Kb1 a6 13. Nc1 O-O-O
    14. Nb3 exd4 15. Rxd4 c5 16. Rd1 Nb6 17. g3 Kb8
    18. Na5 Ba8 19. Bh3 d5 20. Qf4+ Ka7 21. Rhe1 d4
    22. Nd5 Nbxd5 23. exd5 Qd6 24. Rxd4 cxd4 25. Re7+ Kb6
    26. Qxd4+ Kxa5 27. b4+ Ka4 28. Qc3 Qxd5 29. Ra7 Bb7
    30. Rxb7 Qc4 31. Qxf6 Kxa3 32. Qxa6+ Kxb4 33. c3+ Kxc3
    34. Qa1+ Kd2 35. Qb2+ Kd1 36. Bf1 Rd2 37. Rd7 Rxd7
    38. Bxc4 bxc4 39. Qxh8 Rd3 40. Qa8 c3 41. Qa4+ Ke1
    42. f4 f5 43. Kc1 Rd2 44. Qa7 1-0
    """
).strip()

CAPABLANCA_TARTAKOWER = dedent(
    """
    [Event "New York"]
    [Site "New York, NY USA"]
    [Date "1924.03.23"]
    [Round "6"]
    [White "Jose Raul Capablanca"]
    [Black "Savielly Tartakower"]
    [Result "1-0"]
    [ECO "A40"]
    [PlyCount "103"]

    1. d4 e6 2. Nf3 f5 3. c4 Nf6 4. Bg5 Be7 5. Nc3 O-O
    6. e3 b6 7. Bd3 Bb7 8. O-O Qe8 9. Qe2 Ne4 10. Bxe7 Nxc3
    11. bxc3 Qxe7 12. a4 Bxf3 13. Qxf3 Nc6 14. Rfb1 Rae8
    15. Qh3 Rf6 16. f4 Na5 17. Qf3 d6 18. Re1 Qd7
    19. e4 fxe4 20. Qxe4 g6 21. g3 Kf8 22. Kg2 Rf7
    23. h4 d5 24. cxd5 exd5 25. Qxe8+ Qxe8 26. Rxe8+ Kxe8
    27. h5 Rf6 28. hxg6 hxg6 29. Rh1 Kf8 30. Rh7 Rc6
    31. g4 Nc4 32. g5 Ne3+ 33. Kf3 Nf5 34. Bxf5 gxf5
    35. Kg3 Rxc3+ 36. Kh4 Rf3 37. g6 Rxf4+ 38. Kg5 Re4
    39. Kf6 Kg8 40. Rg7+ Kh8 41. Rxc7 Re8 42. Kxf5 Re4
    43. Kf6 Rf4+ 44. Ke5 Rg4 45. g7+ Kg8 46. Rxa7 Rg1
    47. Kxd5 Rc1 48. Kd6 Rc2 49. d5 Rc1 50. Rc7 Ra1
    51. Kc6 Rxa4 52. d6 1-0
    """
).strip()


@dataclass(frozen=True)
class RealGameFixture:
    id: str
    title: str
    summary: str
    source: str
    pgn: str
    orientation: ColorName
    player_level: PlayerLevel
    time_control: str
    tags: tuple[str, ...]


REAL_GAME_FIXTURES: tuple[RealGameFixture, ...] = (
    RealGameFixture(
        id="morphy-opera-1858",
        title="Morphy Opera Game, 1858",
        summary="Paul Morphy's famous attacking game.",
        source="PGN: Paul Morphy vs Duke Karl / Count Isouard, Paris 1858",
        pgn=OPERA_GAME,
        orientation="white",
        player_level=PlayerLevel.rating(2400, "historical-demo"),
        time_control="classical",
        tags=("real game", "famous", "attack"),
    ),
    RealGameFixture(
        id="byrne-fischer-1956",
        title="Byrne-Fischer Game of the Century, 1956",
        summary="Fischer's tactical win over Donald Byrne.",
        source="PGN: Donald Byrne vs Robert James Fischer, New York 1956",
        pgn=BYRNE_FISCHER,
        orientation="black",
        player_level=PlayerLevel.rating(2400, "historical-demo"),
        time_control="classical",
        tags=("real game", "famous", "tactics"),
    ),
    RealGameFixture(
        id="kasparov-topalov-1999",
        title="Kasparov-Topalov, Wijk aan Zee 1999",
        summary="Kasparov's celebrated rook sacrifice game.",
        source="PGN: Garry Kasparov vs Veselin Topalov, Wijk aan Zee 1999",
        pgn=KASPAROV_TOPALOV,
        orientation="white",
        player_level=PlayerLevel.rating(2700, "historical-demo"),
        time_control="classical",
        tags=("real game", "famous", "sacrifice"),
    ),
    RealGameFixture(
        id="capablanca-tartakower-1924",
        title="Capablanca-Tartakower, New York 1924",
        summary="Capablanca's quiet positional and rook-endgame conversion.",
        source="PGN: Jose Raul Capablanca vs Savielly Tartakower, New York 1924",
        pgn=CAPABLANCA_TARTAKOWER,
        orientation="white",
        player_level=PlayerLevel.rating(2400, "historical-demo"),
        time_control="classical",
        tags=("real game", "positional", "endgame"),
    ),
)


def read_game(pgn: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("Real-game PGN could not be parsed.")
    return game


def board_before_ply(pgn: str, ply: int) -> chess.Board:
    game = read_game(pgn)
    moves = list(game.mainline_moves())
    if ply < 1 or ply > len(moves):
        raise ValueError(f"ply must be between 1 and {len(moves)}.")
    board = game.board()
    for move in moves[: ply - 1]:
        board.push(move)
    return board


def san_at_ply(pgn: str, ply: int) -> str:
    board = board_before_ply(pgn, ply)
    move = list(read_game(pgn).mainline_moves())[ply - 1]
    return board.san(move)


def color_name(color: chess.Color) -> ColorName:
    return "white" if color == chess.WHITE else "black"
