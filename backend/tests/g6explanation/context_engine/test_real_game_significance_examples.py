from __future__ import annotations

import shutil
from textwrap import dedent

import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import ColorName, MoveContextRequest, PlayerLevel
from g6explanation.context_engine.stockfish_analysis import StockfishAnalysisProvider

STOCKFISH = shutil.which("stockfish")

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
)

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
)

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
)


@pytest.mark.skipif(STOCKFISH is None, reason="stockfish binary is not installed")
def test_real_game_significance_and_beauty_examples_with_stockfish() -> None:
    engine = MoveContextBuilder(
        StockfishAnalysisProvider(
            binary_path=STOCKFISH or "stockfish",
            depth=10,
            multipv=3,
            threads=1,
            hash_mb=64,
            show_wdl=True,
        )
    )
    examples: list[tuple[str, str, int, ColorName, str]] = [
        ("Opera Game", OPERA_GAME, 33, "white", "Rd8#"),
        ("Game of the Century", BYRNE_FISCHER, 34, "black", "Be6"),
        ("Kasparov's Immortal", KASPAROV_TOPALOV, 47, "white", "Rxd4"),
    ]

    output: list[dict[str, object]] = []
    for game, pgn, ply, player_color, expected_san in examples:
        result = engine.build(
            MoveContextRequest(
                pgn=pgn,
                ply=ply,
                player_color=player_color,
                player_level=PlayerLevel.rating(2400, "historical-demo"),
                time_control="classical",
            )
        )
        output.append(
            {
                "game": game,
                "move": result.evidence.played.san,
                "quality": result.evidence.quality.label,
                "significance": result.evidence.significance.to_dict(),
                "beauty": result.evidence.beauty.to_dict(),
            }
        )
        assert result.evidence.played.san == expected_san

    assert output == [
        {
            "game": "Opera Game",
            "move": "Rd8#",
            "quality": "best",
            "significance": {"label": "critical", "score": 1.0},
            "beauty": {"label": "beautiful", "score": 0.68},
        },
        {
            "game": "Game of the Century",
            "move": "Be6",
            "quality": "best",
            "significance": {"label": "critical", "score": 1.0},
            "beauty": {"label": "brilliant", "score": 0.87},
        },
        {
            "game": "Kasparov's Immortal",
            "move": "Rxd4",
            "quality": "best",
            "significance": {"label": "high", "score": 0.56},
            "beauty": {"label": "beautiful", "score": 0.54},
        },
    ]
