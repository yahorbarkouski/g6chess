from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

import chess
import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    ColorName,
    ConceptClaimKind,
    ContextResult,
    EngineAnalysis,
    EngineAnalysisBudget,
    EngineLine,
    FindabilityLabel,
    HumanMoveLikelihood,
    MoveContextRequest,
    MoveQualityLabel,
    PlayerLevel,
    RecommendationPolicy,
    Score,
    SignificanceLabel,
    TimeSituation,
    Wdl,
)
from g6explanation.context_engine.position_reconstruction import reconstruct_move_context
from g6explanation.explanation_generation.baseline_renderer import render_baseline_explanation
from g6explanation.explanation_generation.explanation_verification import ExplanationVerifier
from tests.g6explanation.context_engine.helpers import (
    StaticAnalysisProvider,
    StaticHumanLikelihoodProvider,
    pv_san,
)

PlayerSystem = Literal["manual-suite", "synthetic-edge", "historical-demo"]


def empty_expected_findability() -> dict[str, FindabilityLabel]:
    return {}


def empty_expected_policy() -> dict[str, RecommendationPolicy]:
    return {}


@dataclass(frozen=True)
class LineSpec:
    uci: str
    score: Score
    wdl: Wdl | None = None
    pv_uci: tuple[str, ...] = ()


@dataclass(frozen=True)
class HumanSpec:
    uci: str
    probability: float | None
    plus_400_probability: float | None = None
    rank: int | None = None
    is_top_human_move: bool = False


@dataclass(frozen=True)
class LabelingSuiteCase:
    case_id: str
    description: str
    fen_before: str
    played_uci: str
    player_color: ColorName
    top_lines: tuple[LineSpec, ...]
    played_line: LineSpec
    expected_quality: MoveQualityLabel
    expected_significance: SignificanceLabel
    expected_time_situation: TimeSituation = "unknown"
    player_rating: int = 1400
    player_system: PlayerSystem = "manual-suite"
    time_control: str | None = None
    clock_before_seconds: float | None = None
    increment_seconds: float | None = None
    human: tuple[HumanSpec, ...] = ()
    after_reply_uci: str | None = None
    expected_key_move: str | None = None
    expected_featured_move: str | None = None
    expected_findability: dict[str, FindabilityLabel] = field(
        default_factory=empty_expected_findability
    )
    expected_policy: dict[str, RecommendationPolicy] = field(default_factory=empty_expected_policy)
    expected_concepts: frozenset[ConceptClaimKind] = frozenset()
    target_tags: frozenset[str] = frozenset()

    def request(self) -> MoveContextRequest:
        return MoveContextRequest(
            fen_before=self.fen_before,
            played_move=self.played_uci,
            player_color=self.player_color,
            player_level=PlayerLevel.rating(self.player_rating, self.player_system),
            time_control=self.time_control,
            clock_before_seconds=self.clock_before_seconds,
            increment_seconds=self.increment_seconds,
        )


def cp_line(
    uci: str,
    cp: int,
    wdl: tuple[int, int, int] | None = None,
    pv: tuple[str, ...] = (),
) -> LineSpec:
    return LineSpec(uci=uci, score=Score.cp(cp), wdl=_wdl(wdl), pv_uci=pv)


def mate_line(
    uci: str,
    mate_in: int,
    mate_for: Literal["player", "opponent"],
    pv: tuple[str, ...] = (),
) -> LineSpec:
    return LineSpec(uci=uci, score=Score.mate(mate_in, mate_for), pv_uci=pv)


def human(
    uci: str,
    probability: float | None,
    plus_400_probability: float | None = None,
    rank: int | None = None,
    is_top_human_move: bool = False,
) -> HumanSpec:
    return HumanSpec(
        uci=uci,
        probability=probability,
        plus_400_probability=plus_400_probability,
        rank=rank,
        is_top_human_move=is_top_human_move,
    )


def tags(*values: str) -> frozenset[str]:
    return frozenset(values)


def _wdl(value: tuple[int, int, int] | None) -> Wdl | None:
    if value is None:
        return None
    win, draw, loss = value
    return Wdl(win=win, draw=draw, loss=loss)


START = chess.STARTING_FEN
BLACK_TO_MOVE_START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
FOOLS_WHITE = "rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2"
FOOLS_BLACK = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq g3 0 2"
FORCED_DEFENSE = "1Q2kb1r/p2n1ppp/4q3/4p1B1/4P3/8/PPP2PPP/2KR4 b k - 1 16"
CASTLING = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
EN_PASSANT = "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3"
PROMOTION = "8/P7/8/8/8/8/8/k6K w - - 0 1"
KNIGHT_FORK = "r1b3k1/1p1r2pn/p7/5p2/2NppP2/6B1/PPP3PP/2KR3R w - - 0 22"
BISHOP_TRADE = "r2qkb1r/pp2pppp/2n2n2/1B1p4/3P2b1/5N1P/PPP2PP1/RNBQ1RK1 b kq - 0 7"
OPEN_FILE = "4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1"
PASSED_PAWN = "4k3/8/8/8/4P3/8/8/4K3 w - - 0 1"
OUTPOST = "4k3/8/8/8/2P1PN2/8/8/4K3 w - - 0 1"
QUEEN_CHECK = "4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1"
MATERIAL_CAPTURE = "8/8/8/8/8/3p4/4P3/4K2k w - - 0 1"
MINOR_DEVELOPMENT = "4k3/8/8/8/8/8/8/4K1N1 w - - 0 1"
CENTER_PAWN = "4k3/8/8/8/8/8/3P4/4K3 w - - 0 1"
BLACK_KNIGHT_MOVE = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


MANUAL_LABELING_SUITE: tuple[LabelingSuiteCase, ...] = (
    LabelingSuiteCase(
        "q001-nonbest-loss-zero-excellent",
        "Non-best move with no objective loss remains excellent, not best.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 40, (500, 400, 100)), cp_line("d2d4", 40, (500, 400, 100))),
        cp_line("d2d4", 40, (500, 400, 100)),
        "excellent",
        "low",
        target_tags=tags("quality:excellent", "significance:low"),
    ),
    LabelingSuiteCase(
        "q002-cp-loss-twenty-excellent",
        "Upper edge of excellent by centipawn loss.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100, (500, 400, 100)), cp_line("d2d4", 80, (490, 400, 110))),
        cp_line("d2d4", 80, (490, 400, 110)),
        "excellent",
        "low",
        target_tags=tags("quality:excellent", "significance:low"),
    ),
    LabelingSuiteCase(
        "q003-cp-loss-twenty-one-good",
        "Lower edge of good by centipawn loss.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100, (500, 400, 100)), cp_line("d2d4", 79, (489, 400, 111))),
        cp_line("d2d4", 79, (489, 400, 111)),
        "good",
        "low",
        target_tags=tags("quality:good", "significance:low"),
    ),
    LabelingSuiteCase(
        "q004-cp-loss-fifty-good",
        "Upper edge of good by centipawn loss.",
        START,
        "g1f3",
        "white",
        (cp_line("e2e4", 100, (500, 400, 100)), cp_line("g1f3", 50, (480, 400, 120))),
        cp_line("g1f3", 50, (480, 400, 120)),
        "good",
        "moderate",
        target_tags=tags("quality:good", "significance:moderate"),
    ),
    LabelingSuiteCase(
        "q005-cp-loss-fifty-one-neutral",
        "Lower edge of neutral by centipawn loss.",
        START,
        "g1f3",
        "white",
        (cp_line("e2e4", 100), cp_line("g1f3", 49)),
        cp_line("g1f3", 49),
        "neutral",
        "moderate",
        target_tags=tags("quality:neutral", "significance:moderate"),
    ),
    LabelingSuiteCase(
        "q006-cp-loss-seventy-five-neutral",
        "Upper edge of neutral by centipawn loss.",
        START,
        "c2c4",
        "white",
        (cp_line("e2e4", 100), cp_line("c2c4", 25)),
        cp_line("c2c4", 25),
        "neutral",
        "moderate",
        target_tags=tags("quality:neutral", "significance:moderate"),
    ),
    LabelingSuiteCase(
        "q007-cp-loss-seventy-six-inaccuracy",
        "Lower edge of inaccuracy by centipawn loss.",
        START,
        "c2c4",
        "white",
        (cp_line("e2e4", 100), cp_line("c2c4", 24)),
        cp_line("c2c4", 24),
        "inaccuracy",
        "moderate",
        target_tags=tags("quality:inaccuracy", "significance:moderate"),
    ),
    LabelingSuiteCase(
        "q008-cp-loss-one-fifty-inaccuracy",
        "Upper edge of inaccuracy by centipawn loss.",
        START,
        "b1c3",
        "white",
        (cp_line("e2e4", 100), cp_line("b1c3", -50)),
        cp_line("b1c3", -50),
        "inaccuracy",
        "high",
        target_tags=tags("quality:inaccuracy", "significance:high"),
    ),
    LabelingSuiteCase(
        "q009-cp-loss-one-fifty-one-mistake",
        "Lower edge of mistake by centipawn loss.",
        START,
        "b1c3",
        "white",
        (cp_line("e2e4", 100), cp_line("b1c3", -51)),
        cp_line("b1c3", -51),
        "mistake",
        "high",
        expected_key_move="e4",
        target_tags=tags("quality:mistake", "significance:high"),
    ),
    LabelingSuiteCase(
        "q010-cp-loss-three-hundred-mistake",
        "Upper edge of mistake by centipawn loss.",
        START,
        "a2a3",
        "white",
        (cp_line("e2e4", 160), cp_line("a2a3", -140)),
        cp_line("a2a3", -140),
        "mistake",
        "critical",
        expected_key_move="e4",
        target_tags=tags("quality:mistake", "significance:critical"),
    ),
    LabelingSuiteCase(
        "q011-cp-loss-three-oh-one-blunder",
        "Lower edge of blunder by centipawn loss.",
        START,
        "a2a3",
        "white",
        (cp_line("e2e4", 161), cp_line("a2a3", -140)),
        cp_line("a2a3", -140),
        "blunder",
        "critical",
        expected_key_move="e4",
        target_tags=tags("quality:blunder", "significance:critical"),
    ),
    LabelingSuiteCase(
        "q012-large-opening-blunder-with-reply",
        "Large opening blunder has opponent-resource support when a reply is supplied.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 120), cp_line("d2d4", 90)),
        cp_line("g2g4", -300),
        "blunder",
        "critical",
        after_reply_uci="e7e5",
        expected_key_move="e4",
        expected_concepts=frozenset({"opponent_resource"}),
        target_tags=tags("quality:blunder", "significance:critical", "concept:opponent_resource"),
    ),
    LabelingSuiteCase(
        "q013-black-perspective-cp-mistake",
        "Black-side score loss is still from the analyzed player's perspective.",
        AFTER_E4,
        "g7g5",
        "black",
        (cp_line("c7c5", 60), cp_line("e7e5", 25)),
        cp_line("g7g5", -200),
        "mistake",
        "critical",
        expected_key_move="c5",
        target_tags=tags("quality:mistake", "significance:critical", "perspective:black"),
    ),
    LabelingSuiteCase(
        "q014-black-perspective-best",
        "Black's first-line reply is best from Black perspective.",
        AFTER_E4,
        "c7c5",
        "black",
        (cp_line("c7c5", 60), cp_line("e7e5", 30)),
        cp_line("c7c5", 60),
        "best",
        "low",
        target_tags=tags("quality:best", "significance:low", "perspective:black"),
    ),
    LabelingSuiteCase(
        "q015-wdl-loss-ten-excellent",
        "WDL expected-score loss at the excellent upper edge.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100, (500, 400, 100)), cp_line("d2d4", 100, (490, 400, 110))),
        cp_line("d2d4", 100, (490, 400, 110)),
        "excellent",
        "low",
        target_tags=tags("quality:excellent", "significance:low", "wdl:edge"),
    ),
    LabelingSuiteCase(
        "q016-wdl-loss-eleven-good",
        "WDL expected-score loss moves the label to good.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100, (500, 400, 100)), cp_line("d2d4", 100, (489, 400, 111))),
        cp_line("d2d4", 100, (489, 400, 111)),
        "good",
        "low",
        target_tags=tags("quality:good", "significance:low", "wdl:edge"),
    ),
    LabelingSuiteCase(
        "q017-wdl-loss-eighty-inaccuracy",
        "WDL can make a move an inaccuracy without centipawn loss.",
        START,
        "g1f3",
        "white",
        (cp_line("e2e4", 100, (500, 400, 100)), cp_line("g1f3", 100, (420, 400, 180))),
        cp_line("g1f3", 100, (420, 400, 180)),
        "inaccuracy",
        "high",
        target_tags=tags("quality:inaccuracy", "significance:high", "wdl:dominant"),
    ),
    LabelingSuiteCase(
        "q018-wdl-only-blunder-capped-at-mistake",
        "A WDL-only blunder signal is capped at mistake without blunder-band centipawns.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 66, (202, 797, 1)), cp_line("d2d4", -162, (0, 73, 927))),
        cp_line("d2d4", -162, (0, 73, 927)),
        "mistake",
        "critical",
        target_tags=tags("quality:mistake", "significance:critical", "wdl:blunder-capped"),
    ),
    LabelingSuiteCase(
        "q019-high-wdl-floor-good",
        "A big centipawn loss remains good when the played line is still overwhelmingly winning.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 1000, (1000, 0, 0)), cp_line("d2d4", 700, (900, 100, 0))),
        cp_line("d2d4", 700, (900, 100, 0)),
        "good",
        "critical",
        target_tags=tags("quality:good", "significance:critical", "coach:still-winning-caveat"),
    ),
    LabelingSuiteCase(
        "q020-high-wdl-floor-under-one-second",
        "A strong non-best move under one second should receive time-pressure credit.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 1000, (1000, 0, 0)), cp_line("d2d4", 700, (900, 100, 0))),
        cp_line("d2d4", 700, (900, 100, 0)),
        "good",
        "critical",
        expected_time_situation="time_scramble",
        clock_before_seconds=0.8,
        increment_seconds=0,
        target_tags=tags(
            "quality:good",
            "significance:critical",
            "time:time_scramble",
            "coach:fast-good-move-credit",
        ),
    ),
    LabelingSuiteCase(
        "q021-missing-player-mate-is-missed-win",
        "Missing a forced mate is a missed win, not a centipawn mistake.",
        FOOLS_BLACK,
        "g8f6",
        "black",
        (mate_line("d8h4", 1, "player"), cp_line("g8f6", 100)),
        cp_line("g8f6", 100),
        "missed_win",
        "critical",
        expected_key_move="Qh4#",
        target_tags=tags("quality:missed_win", "significance:critical", "concept:forced_mate"),
    ),
    LabelingSuiteCase(
        "q022-playing-checkmate-is-best",
        "Immediate checkmate is best even when another mate also exists.",
        FOOLS_BLACK,
        "d8h4",
        "black",
        (mate_line("d8h4", 1, "player"), cp_line("g8f6", 100)),
        mate_line("d8h4", 1, "player"),
        "best",
        "critical",
        expected_featured_move="Qh4#",
        expected_concepts=frozenset({"forced_mate"}),
        target_tags=tags("quality:best", "significance:critical", "concept:forced_mate"),
    ),
    LabelingSuiteCase(
        "q023-allowing-forced-mate-is-blunder",
        "Allowing forced mate against the player is a blunder.",
        FOOLS_WHITE,
        "g2g4",
        "white",
        (cp_line("e2e4", 20), cp_line("d2d4", 0)),
        mate_line("g2g4", 1, "opponent"),
        "blunder",
        "critical",
        expected_concepts=frozenset({"king_safety"}),
        target_tags=tags("quality:blunder", "significance:critical", "concept:king_safety"),
    ),
    LabelingSuiteCase(
        "q024-already-lost-mate-best-defense",
        "The best defense in an already forced-mate position is still best.",
        FORCED_DEFENSE,
        "d7b8",
        "black",
        (mate_line("d7b8", 1, "opponent"),),
        mate_line("d7b8", 1, "opponent"),
        "forced",
        "low",
        expected_featured_move="Nxb8",
        expected_concepts=frozenset({"forced_move"}),
        target_tags=tags("quality:forced", "significance:critical", "concept:forced_move"),
    ),
    LabelingSuiteCase(
        "q025-worsening-already-lost-mate-blunder",
        "Shortening an already forced mate is still a blunder.",
        START,
        "d2d4",
        "white",
        (mate_line("e2e4", 5, "opponent"), cp_line("d2d4", 0)),
        mate_line("d2d4", 2, "opponent"),
        "blunder",
        "critical",
        target_tags=tags("quality:blunder", "significance:critical", "concept:forced_mate"),
    ),
    LabelingSuiteCase(
        "t026-classical-normal-findable-best",
        "Classical time should not worsen a findable best move.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 120), cp_line("d2d4", 85)),
        cp_line("g2g4", -120),
        "mistake",
        "critical",
        expected_time_situation="classical_or_no_pressure",
        time_control="classical",
        human=(human("e2e4", 0.12),),
        expected_findability={"e4": "findable"},
        expected_policy={"e4": "recommend_directly"},
        expected_key_move="e4",
        target_tags=tags("time:classical_or_no_pressure", "findability:e4:findable"),
    ),
    LabelingSuiteCase(
        "t027-rapid-normal-findable-best",
        "Rapid time should not worsen a findable best move.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 120), cp_line("d2d4", 85)),
        cp_line("g2g4", -120),
        "mistake",
        "critical",
        expected_time_situation="rapid_normal",
        time_control="rapid",
        human=(human("e2e4", 0.12),),
        expected_findability={"e4": "findable"},
        target_tags=tags("time:rapid_normal", "findability:e4:findable"),
    ),
    LabelingSuiteCase(
        "t028-blitz-normal-findable-best",
        "Blitz label alone should not worsen if exact clock is unknown.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 120), cp_line("d2d4", 85)),
        cp_line("g2g4", -120),
        "mistake",
        "critical",
        expected_time_situation="blitz_normal",
        time_control="blitz",
        human=(human("e2e4", 0.12),),
        expected_findability={"e4": "findable"},
        target_tags=tags("time:blitz_normal", "findability:e4:findable"),
    ),
    LabelingSuiteCase(
        "t029-bullet-time-scramble",
        "Bullet time control should create a scramble tag.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 120), cp_line("d2d4", 85)),
        cp_line("g2g4", -120),
        "mistake",
        "critical",
        expected_time_situation="time_scramble",
        time_control="bullet",
        human=(human("e2e4", 0.12),),
        expected_findability={"e4": "hard"},
        target_tags=tags("time:time_scramble", "findability:e4:hard"),
    ),
    LabelingSuiteCase(
        "t030-low-clock-worsens-findability",
        "Twenty seconds left should worsen a findable resource to hard.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 120), cp_line("d2d4", 85)),
        cp_line("g2g4", -120),
        "mistake",
        "critical",
        expected_time_situation="low_time",
        clock_before_seconds=20,
        increment_seconds=5,
        human=(human("e2e4", 0.12),),
        expected_findability={"e4": "hard"},
        target_tags=tags("time:low_time", "findability:e4:hard"),
    ),
    LabelingSuiteCase(
        "t031-ten-seconds-no-increment-scramble",
        "Ten seconds with no increment is a scramble.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 120), cp_line("d2d4", 85)),
        cp_line("g2g4", -120),
        "mistake",
        "critical",
        expected_time_situation="time_scramble",
        clock_before_seconds=10,
        increment_seconds=0,
        human=(human("e2e4", 0.12),),
        expected_findability={"e4": "hard"},
        target_tags=tags("time:time_scramble", "findability:e4:hard"),
    ),
    LabelingSuiteCase(
        "t032-ten-seconds-large-increment-low-time",
        "A large increment keeps ten seconds in low-time rather than scramble.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 120), cp_line("d2d4", 85)),
        cp_line("g2g4", -120),
        "mistake",
        "critical",
        expected_time_situation="low_time",
        clock_before_seconds=10,
        increment_seconds=5,
        human=(human("e2e4", 0.12),),
        expected_findability={"e4": "hard"},
        target_tags=tags("time:low_time", "findability:e4:hard"),
    ),
    LabelingSuiteCase(
        "t033-one-second-good-move-credit",
        "A good move with one second should be tagged as practical resilience.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100, (500, 400, 100)), cp_line("d2d4", 55, (480, 400, 120))),
        cp_line("d2d4", 55, (480, 400, 120)),
        "good",
        "moderate",
        expected_time_situation="time_scramble",
        clock_before_seconds=1,
        increment_seconds=0,
        target_tags=tags("quality:good", "time:time_scramble", "coach:fast-good-move-credit"),
    ),
    LabelingSuiteCase(
        "t034-one-second-blunder-context",
        "A blunder with one second should still be a blunder but phrased with time context.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 160), cp_line("d2d4", 110)),
        cp_line("g2g4", -220),
        "blunder",
        "critical",
        expected_time_situation="time_scramble",
        clock_before_seconds=1,
        increment_seconds=0,
        target_tags=tags("quality:blunder", "time:time_scramble", "coach:time-scramble-blunder"),
    ),
    LabelingSuiteCase(
        "t035-one-second-excellent-check",
        "An excellent checking move under one second deserves a fast-resource tag.",
        QUEEN_CHECK,
        "e2e7",
        "white",
        (cp_line("e2e7", 120), cp_line("e2a2", 105)),
        cp_line("e2e7", 120),
        "best",
        "low",
        expected_time_situation="time_scramble",
        clock_before_seconds=0.7,
        increment_seconds=0,
        expected_concepts=frozenset({"initiative"}),
        target_tags=tags("quality:best", "time:time_scramble", "coach:fast-forcing-resource"),
    ),
    LabelingSuiteCase(
        "t036-hard-best-with-time-scramble-hidden",
        "Low time should turn an already hard best move into a hidden resource.",
        START,
        "a2a3",
        "white",
        (cp_line("e2e4", 300), cp_line("d2d4", 210)),
        cp_line("a2a3", -60),
        "blunder",
        "critical",
        expected_time_situation="time_scramble",
        clock_before_seconds=5,
        increment_seconds=0,
        human=(human("e2e4", 0.015, 0.10),),
        expected_findability={"e4": "engine_like"},
        expected_policy={"e4": "explain_as_hidden_resource"},
        expected_key_move="e4",
        target_tags=tags("time:time_scramble", "policy:e4:explain_as_hidden_resource"),
    ),
    LabelingSuiteCase(
        "t037-teachable-skill-gap",
        "A hard best move common at stronger levels gets a teachable skill-gap tag.",
        START,
        "a2a3",
        "white",
        (cp_line("e2e4", 180), cp_line("d2d4", 130)),
        cp_line("a2a3", -80),
        "mistake",
        "critical",
        human=(human("e2e4", 0.03, 0.20),),
        expected_findability={"e4": "very_hard"},
        expected_policy={"e4": "explain_as_hidden_resource"},
        expected_key_move="e4",
        target_tags=tags("concept:teachable_skill_gap", "policy:e4:explain_as_hidden_resource"),
    ),
    LabelingSuiteCase(
        "t038-obvious-human-error-still-mistake",
        "A human-common bad move stays objectively bad.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 80), cp_line("d2d4", 50)),
        cp_line("g2g4", -140),
        "mistake",
        "critical",
        human=(human("g2g4", 0.45), human("e2e4", 0.08)),
        expected_findability={"g4": "obvious", "e4": "hard"},
        target_tags=tags("quality:mistake", "findability:g4:obvious", "coach:common-human-error"),
    ),
    LabelingSuiteCase(
        "t039-obvious-best-direct-recommendation",
        "An obvious best alternative should be recommended directly.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 80), cp_line("d2d4", 50)),
        cp_line("g2g4", -140),
        "mistake",
        "critical",
        human=(human("e2e4", 0.40),),
        expected_findability={"e4": "obvious"},
        expected_policy={"e4": "recommend_directly"},
        expected_key_move="e4",
        target_tags=tags("policy:e4:recommend_directly", "findability:e4:obvious"),
    ),
    LabelingSuiteCase(
        "t040-practical-alternative-beats-hidden-engine-best",
        "A practical alternative should be featured when the engine best is hard and close.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 40), cp_line("g1f3", 25)),
        cp_line("g2g4", -180),
        "mistake",
        "critical",
        human=(human("e2e4", 0.02, 0.12), human("g1f3", 0.32, 0.40)),
        expected_findability={"e4": "very_hard", "Nf3": "obvious"},
        expected_policy={"e4": "explain_as_hidden_resource", "Nf3": "use_as_practical_alternative"},
        expected_key_move="Nf3",
        expected_featured_move="Nf3",
        target_tags=tags("policy:Nf3:use_as_practical_alternative", "coach:practical-option"),
    ),
    LabelingSuiteCase(
        "t041-practical-alternative-in-low-time-worsens",
        "The same practical alternative becomes less findable in low time.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 40), cp_line("g1f3", 25)),
        cp_line("g2g4", -180),
        "mistake",
        "critical",
        expected_time_situation="low_time",
        clock_before_seconds=20,
        human=(human("e2e4", 0.02, 0.12), human("g1f3", 0.32, 0.40)),
        expected_findability={"e4": "engine_like", "Nf3": "findable"},
        expected_policy={"Nf3": "use_as_practical_alternative"},
        expected_key_move="Nf3",
        target_tags=tags("time:low_time", "findability:Nf3:findable"),
    ),
    LabelingSuiteCase(
        "t042-check-resource-improves-findability",
        "A checking resource improves one findability bucket.",
        QUEEN_CHECK,
        "e2a2",
        "white",
        (cp_line("e2e7", 180), cp_line("e2a2", -40)),
        cp_line("e2a2", -40),
        "mistake",
        "critical",
        human=(human("e2e7", 0.04),),
        expected_findability={"Qe7+": "findable"},
        expected_policy={"Qe7+": "recommend_directly"},
        expected_key_move="Qe7+",
        target_tags=tags("concept:forcing_move", "findability:Qe7+:findable"),
    ),
    LabelingSuiteCase(
        "t043-recognition-under-low-time",
        "A checking resource in low time loses the forcing-move boost.",
        QUEEN_CHECK,
        "e2a2",
        "white",
        (cp_line("e2e7", 180), cp_line("e2a2", -40)),
        cp_line("e2a2", -40),
        "mistake",
        "critical",
        expected_time_situation="low_time",
        clock_before_seconds=20,
        human=(human("e2e7", 0.04),),
        expected_findability={"Qe7+": "hard"},
        expected_key_move="Qe7+",
        target_tags=tags("time:low_time", "findability:Qe7+:hard"),
    ),
    LabelingSuiteCase(
        "t044-unknown-human-evidence",
        "Missing human evidence should remain unknown rather than invented.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 100), cp_line("d2d4", 50)),
        cp_line("g2g4", -100),
        "mistake",
        "critical",
        expected_findability={"e4": "unknown"},
        expected_policy={"e4": "recommend_directly"},
        target_tags=tags("findability:e4:unknown", "policy:e4:recommend_directly"),
    ),
    LabelingSuiteCase(
        "t045-spent-long-time-and-blundered-gap",
        "The target suite needs think-time evidence for slow blunders.",
        START,
        "g2g4",
        "white",
        (cp_line("e2e4", 160), cp_line("d2d4", 120)),
        cp_line("g2g4", -220),
        "blunder",
        "critical",
        expected_time_situation="rapid_normal",
        time_control="rapid",
        clock_before_seconds=180,
        increment_seconds=2,
        target_tags=tags("quality:blunder", "coach:used-too-much-time-for-blunder"),
    ),
    LabelingSuiteCase(
        "t046-increment-saves-low-clock-context",
        "Very low clock with a large increment should be less alarming than no increment.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100, (500, 400, 100)), cp_line("d2d4", 70, (485, 400, 115))),
        cp_line("d2d4", 70, (485, 400, 115)),
        "good",
        "low",
        expected_time_situation="low_time",
        clock_before_seconds=4,
        increment_seconds=10,
        target_tags=tags("time:low_time", "coach:increment-context"),
    ),
    LabelingSuiteCase(
        "t047-no-clock-rapid-should-not-claim-time-pressure",
        "Rapid without clock data should not imply low time.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100, (500, 400, 100)), cp_line("d2d4", 70, (485, 400, 115))),
        cp_line("d2d4", 70, (485, 400, 115)),
        "good",
        "low",
        expected_time_situation="rapid_normal",
        time_control="rapid",
        target_tags=tags("time:rapid_normal"),
    ),
    LabelingSuiteCase(
        "t048-low-time-forced-move-no-blame",
        "A forced move in low time should not get blame.",
        FORCED_DEFENSE,
        "d7b8",
        "black",
        (mate_line("d7b8", 1, "opponent"),),
        mate_line("d7b8", 1, "opponent"),
        "forced",
        "low",
        expected_time_situation="low_time",
        clock_before_seconds=15,
        increment_seconds=5,
        expected_featured_move="Nxb8",
        target_tags=tags("quality:forced", "time:low_time", "coach:no-blame-forced"),
    ),
    LabelingSuiteCase(
        "t049-low-time-missed-mate-hidden",
        "Low time should caveat a missed mate resource without downgrading objective truth.",
        FOOLS_BLACK,
        "g8f6",
        "black",
        (mate_line("d8h4", 1, "player"), cp_line("g8f6", 100)),
        cp_line("g8f6", 100),
        "missed_win",
        "critical",
        expected_time_situation="time_scramble",
        clock_before_seconds=2,
        increment_seconds=0,
        human=(human("d8h4", 0.04),),
        expected_findability={"Qh4#": "hard"},
        target_tags=tags(
            "quality:missed_win", "time:time_scramble", "coach:missed-mate-under-time"
        ),
    ),
    LabelingSuiteCase(
        "t050-under-one-second-no-time-control-string",
        "Exact clock should dominate a missing time-control label.",
        START,
        "e2e4",
        "white",
        (cp_line("e2e4", 80), cp_line("d2d4", 60)),
        cp_line("e2e4", 80),
        "best",
        "low",
        expected_time_situation="time_scramble",
        clock_before_seconds=0.4,
        increment_seconds=0,
        target_tags=tags("quality:best", "time:time_scramble", "coach:fast-good-move-credit"),
    ),
    LabelingSuiteCase(
        "s051-best-low-significance-small-gap",
        "Best move with a tiny alternative gap is low significance.",
        START,
        "e2e4",
        "white",
        (cp_line("e2e4", 100), cp_line("d2d4", 90)),
        cp_line("e2e4", 100),
        "best",
        "low",
        expected_featured_move=None,
        target_tags=tags("quality:best", "significance:low"),
    ),
    LabelingSuiteCase(
        "s052-best-moderate-significance-edge",
        "Best move reaches moderate significance at the score edge.",
        START,
        "e2e4",
        "white",
        (cp_line("e2e4", 100), cp_line("d2d4", 55)),
        cp_line("e2e4", 100),
        "best",
        "moderate",
        target_tags=tags("quality:best", "significance:moderate"),
    ),
    LabelingSuiteCase(
        "s053-best-high-significance-edge",
        "Best move reaches high significance when alternatives fall far enough behind.",
        START,
        "e2e4",
        "white",
        (cp_line("e2e4", 105), cp_line("d2d4", 0)),
        cp_line("e2e4", 105),
        "best",
        "high",
        expected_featured_move="e4",
        target_tags=tags("quality:best", "significance:high", "concept:critical_best_move"),
    ),
    LabelingSuiteCase(
        "s054-best-critical-significance-edge",
        "Best move reaches critical significance at the threshold.",
        START,
        "e2e4",
        "white",
        (cp_line("e2e4", 195), cp_line("d2d4", 0)),
        cp_line("e2e4", 195),
        "best",
        "critical",
        expected_featured_move="e4",
        target_tags=tags("quality:best", "significance:critical", "concept:critical_best_move"),
    ),
    LabelingSuiteCase(
        "s055-best-wdl-critical-without-cp-gap",
        "WDL can make a best move critical even if centipawns are flat.",
        START,
        "e2e4",
        "white",
        (cp_line("e2e4", 0, (700, 200, 100)), cp_line("d2d4", 0, (500, 200, 300))),
        cp_line("e2e4", 0, (700, 200, 100)),
        "best",
        "critical",
        expected_featured_move="e4",
        target_tags=tags("quality:best", "significance:critical", "wdl:dominant"),
    ),
    LabelingSuiteCase(
        "s056-played-not-best-low-significance",
        "A small miss should stay low attention.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100, (500, 400, 100)), cp_line("d2d4", 80, (490, 400, 110))),
        cp_line("d2d4", 80, (490, 400, 110)),
        "excellent",
        "low",
        target_tags=tags("quality:excellent", "significance:low"),
    ),
    LabelingSuiteCase(
        "s057-played-not-best-moderate-significance",
        "A good but noticeably worse move is moderate attention.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100), cp_line("d2d4", 40)),
        cp_line("d2d4", 40),
        "neutral",
        "moderate",
        target_tags=tags("quality:neutral", "significance:moderate"),
    ),
    LabelingSuiteCase(
        "s058-played-not-best-high-significance",
        "A meaningful non-best move is high attention before critical.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100), cp_line("d2d4", -20)),
        cp_line("d2d4", -20),
        "inaccuracy",
        "high",
        target_tags=tags("quality:inaccuracy", "significance:high"),
    ),
    LabelingSuiteCase(
        "s059-played-not-best-critical-significance",
        "A severe non-best move is critical attention.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 100), cp_line("d2d4", -100)),
        cp_line("d2d4", -100),
        "mistake",
        "critical",
        expected_key_move="e4",
        target_tags=tags("quality:mistake", "significance:critical"),
    ),
    LabelingSuiteCase(
        "s060-wdl-gap-critical-with-small-cp-gap",
        "WDL can make a small-centipawn miss critical.",
        START,
        "d2d4",
        "white",
        (cp_line("e2e4", 10, (500, 300, 200)), cp_line("d2d4", 0, (300, 300, 400))),
        cp_line("d2d4", 0, (300, 300, 400)),
        "mistake",
        "critical",
        target_tags=tags("quality:mistake", "significance:critical", "wdl:dominant"),
    ),
    LabelingSuiteCase(
        "s061-mate-transition-critical",
        "Mate transitions are always critical.",
        FOOLS_WHITE,
        "g2g4",
        "white",
        (cp_line("e2e4", 20),),
        mate_line("g2g4", 1, "opponent"),
        "blunder",
        "critical",
        target_tags=tags("quality:blunder", "significance:critical"),
    ),
    LabelingSuiteCase(
        "s062-forced-move-critical-position",
        "An only legal defense in a mate net is critical by mate transition.",
        FORCED_DEFENSE,
        "d7b8",
        "black",
        (mate_line("d7b8", 1, "opponent"),),
        mate_line("d7b8", 1, "opponent"),
        "forced",
        "low",
        target_tags=tags("quality:forced", "significance:critical"),
    ),
    LabelingSuiteCase(
        "s063-best-opening-development-low",
        "Routine opening development should be low attention.",
        START,
        "g1f3",
        "white",
        (cp_line("g1f3", 50), cp_line("e2e4", 40)),
        cp_line("g1f3", 50),
        "best",
        "low",
        expected_concepts=frozenset({"development"}),
        target_tags=tags("quality:best", "significance:low", "concept:development"),
    ),
    LabelingSuiteCase(
        "s064-quiet-critical-best",
        "A quiet best move can still be critical when alternatives collapse.",
        START,
        "h2h3",
        "white",
        (cp_line("h2h3", 250), cp_line("e2e4", 0)),
        cp_line("h2h3", 250),
        "best",
        "critical",
        expected_featured_move="h3",
        target_tags=tags("quality:best", "significance:critical", "coach:quiet-critical-resource"),
    ),
    LabelingSuiteCase(
        "s065-good-high-wdl-not-overexplained",
        "High-WDL good moves should be explained as still working, not as blame.",
        START,
        "g1f3",
        "white",
        (cp_line("e2e4", 500, (900, 100, 0)), cp_line("g1f3", 350, (830, 170, 0))),
        cp_line("g1f3", 350, (830, 170, 0)),
        "good",
        "high",
        target_tags=tags("quality:good", "significance:high", "coach:still-winning-caveat"),
    ),
    LabelingSuiteCase(
        "s066-critical-capture-best",
        "A critical best capture should expose capture support.",
        MATERIAL_CAPTURE,
        "e2d3",
        "white",
        (cp_line("e2d3", 260), cp_line("e1f2", 0)),
        cp_line("e2d3", 260),
        "best",
        "critical",
        expected_concepts=frozenset({"capture", "material"}),
        target_tags=tags("quality:best", "concept:capture", "concept:material"),
    ),
    LabelingSuiteCase(
        "s067-critical-check-best",
        "A critical checking best move should expose initiative support.",
        QUEEN_CHECK,
        "e2e7",
        "white",
        (cp_line("e2e7", 260), cp_line("e2a2", 0)),
        cp_line("e2e7", 260),
        "best",
        "critical",
        expected_concepts=frozenset({"initiative", "forcing_move"}),
        target_tags=tags("quality:best", "concept:initiative", "concept:forcing_move"),
    ),
    LabelingSuiteCase(
        "s068-missed-win-source-move-attention",
        "A source move before a puzzle solution should be critical if it allows the tactic.",
        KNIGHT_FORK,
        "g3f2",
        "white",
        (cp_line("c4b6", 325), cp_line("g3f2", 125)),
        cp_line("g3f2", 125),
        "mistake",
        "critical",
        expected_key_move="Nb6",
        target_tags=tags("quality:mistake", "significance:high", "concept:tactic"),
    ),
    LabelingSuiteCase(
        "s069-low-significance-neutral-endgame",
        "A neutral endgame move with tiny loss should stay low attention.",
        PASSED_PAWN,
        "e4e5",
        "white",
        (cp_line("e1f2", 100), cp_line("e4e5", 40)),
        cp_line("e4e5", 40),
        "neutral",
        "moderate",
        expected_concepts=frozenset({"passed_pawn"}),
        target_tags=tags("quality:neutral", "concept:passed_pawn"),
    ),
    LabelingSuiteCase(
        "s070-low-time-raises-review-interest-gap",
        "Low time may deserve review interest even when objective significance is low.",
        START,
        "e2e4",
        "white",
        (cp_line("e2e4", 100), cp_line("d2d4", 90)),
        cp_line("e2e4", 100),
        "best",
        "low",
        expected_time_situation="time_scramble",
        clock_before_seconds=1,
        increment_seconds=0,
        target_tags=tags("quality:best", "significance:low", "coach:fast-good-move-credit"),
    ),
    LabelingSuiteCase(
        "c071-castling-kingside",
        "Castling is a typed played-move fact.",
        CASTLING,
        "e1g1",
        "white",
        (cp_line("e1g1", 80), cp_line("e1c1", 70)),
        cp_line("e1g1", 80),
        "best",
        "low",
        expected_concepts=frozenset({"castling"}),
        expected_featured_move=None,
        target_tags=tags("quality:best", "concept:castling"),
    ),
    LabelingSuiteCase(
        "c072-castling-queenside",
        "Queenside castling is also a typed played-move fact.",
        CASTLING,
        "e1c1",
        "white",
        (cp_line("e1c1", 80), cp_line("e1g1", 70)),
        cp_line("e1c1", 80),
        "best",
        "low",
        expected_concepts=frozenset({"castling"}),
        target_tags=tags("quality:best", "concept:castling"),
    ),
    LabelingSuiteCase(
        "c073-en-passant",
        "En passant is a typed played-move fact.",
        EN_PASSANT,
        "e5d6",
        "white",
        (cp_line("e5d6", 100), cp_line("g1f3", 60)),
        cp_line("e5d6", 100),
        "best",
        "low",
        expected_concepts=frozenset({"en_passant", "capture"}),
        expected_featured_move=None,
        target_tags=tags("quality:best", "concept:en_passant", "concept:capture"),
    ),
    LabelingSuiteCase(
        "c074-promotion",
        "Promotion is a typed played-move fact.",
        PROMOTION,
        "a7a8q",
        "white",
        (cp_line("a7a8q", 900), cp_line("h1g2", 600)),
        cp_line("a7a8q", 900),
        "best",
        "critical",
        expected_concepts=frozenset({"promotion"}),
        expected_featured_move="a8=Q+",
        target_tags=tags("quality:best", "concept:promotion", "significance:critical"),
    ),
    LabelingSuiteCase(
        "c075-knight-fork-rooks",
        "A knight move attacking both rooks should expose fork and attacked-piece facts.",
        KNIGHT_FORK,
        "c4b6",
        "white",
        (cp_line("c4b6", 325, pv=("c4b6", "d7d6", "b6a8")), cp_line("g3f2", 125)),
        cp_line("c4b6", 325, pv=("c4b6", "d7d6", "b6a8")),
        "best",
        "critical",
        after_reply_uci="d7d6",
        expected_concepts=frozenset({"piece_activity", "tactic", "critical_best_move"}),
        expected_featured_move="Nb6",
        target_tags=tags("quality:best", "concept:tactic", "concept:piece_activity"),
    ),
    LabelingSuiteCase(
        "c076-bishop-knight-trade",
        "A candidate capture recaptured in the PV should be a trade, not a material win.",
        BISHOP_TRADE,
        "g4h5",
        "black",
        (cp_line("g4f3", 300, pv=("g4f3", "d1f3")), cp_line("g4h5", -300)),
        cp_line("g4h5", -300, pv=("g4h5", "g2g4")),
        "blunder",
        "critical",
        after_reply_uci="g2g4",
        expected_key_move="Bxf3",
        expected_concepts=frozenset({"material", "better_alternative"}),
        target_tags=tags("quality:blunder", "concept:material", "coach:trade-not-win"),
    ),
    LabelingSuiteCase(
        "c077-bishop-route-g3",
        "A flank pawn can open a bishop route without naming an opening system.",
        START,
        "g2g3",
        "white",
        (cp_line("g2g3", 40), cp_line("g1f3", 25)),
        cp_line("g2g3", 40),
        "best",
        "low",
        expected_concepts=frozenset({"development"}),
        target_tags=tags("quality:best", "concept:development"),
    ),
    LabelingSuiteCase(
        "c078-bishop-route-b3",
        "Another bishop-route pawn move should expose route facts.",
        START,
        "b2b3",
        "white",
        (cp_line("b2b3", 40), cp_line("g1f3", 25)),
        cp_line("b2b3", 40),
        "best",
        "low",
        expected_concepts=frozenset({"development"}),
        target_tags=tags("quality:best", "concept:development"),
    ),
    LabelingSuiteCase(
        "c079-black-bishop-route-g6",
        "Black bishop-route facts should work from Black perspective.",
        BLACK_TO_MOVE_START,
        "g7g6",
        "black",
        (cp_line("g7g6", 40), cp_line("g8f6", 25)),
        cp_line("g7g6", 40),
        "best",
        "low",
        expected_concepts=frozenset({"development"}),
        target_tags=tags("quality:best", "concept:development", "perspective:black"),
    ),
    LabelingSuiteCase(
        "c080-minor-piece-development",
        "Minor-piece development should be a concept claim.",
        MINOR_DEVELOPMENT,
        "g1f3",
        "white",
        (cp_line("g1f3", 60), cp_line("e1d2", 40)),
        cp_line("g1f3", 60),
        "best",
        "low",
        expected_concepts=frozenset({"development"}),
        target_tags=tags("quality:best", "concept:development"),
    ),
    LabelingSuiteCase(
        "c081-center-pawn",
        "A center pawn move should expose center control.",
        CENTER_PAWN,
        "d2d4",
        "white",
        (cp_line("d2d4", 60), cp_line("e1f2", 40)),
        cp_line("d2d4", 60),
        "best",
        "low",
        expected_concepts=frozenset({"center"}),
        target_tags=tags("quality:best", "concept:center"),
    ),
    LabelingSuiteCase(
        "c082-open-file-rook",
        "A rook move to an open file should expose open-file evidence.",
        OPEN_FILE,
        "a1d1",
        "white",
        (cp_line("a1d1", 100), cp_line("h1g1", 70)),
        cp_line("a1d1", 100),
        "best",
        "low",
        expected_concepts=frozenset({"open_file"}),
        target_tags=tags("quality:best", "concept:open_file"),
    ),
    LabelingSuiteCase(
        "c083-passed-pawn-advance",
        "A passed-pawn advance should expose pawn-structure evidence.",
        PASSED_PAWN,
        "e4e5",
        "white",
        (cp_line("e4e5", 120), cp_line("e1f2", 80)),
        cp_line("e4e5", 120),
        "best",
        "low",
        expected_concepts=frozenset({"passed_pawn"}),
        target_tags=tags("quality:best", "concept:passed_pawn"),
    ),
    LabelingSuiteCase(
        "c084-knight-outpost",
        "A knight move to a supported weak square should expose outpost evidence.",
        OUTPOST,
        "f4d5",
        "white",
        (cp_line("f4d5", 120), cp_line("e1f2", 80)),
        cp_line("f4d5", 120),
        "best",
        "low",
        expected_concepts=frozenset({"weak_square"}),
        target_tags=tags("quality:best", "concept:weak_square"),
    ),
    LabelingSuiteCase(
        "c085-queen-check-initiative",
        "A checking move should expose initiative.",
        QUEEN_CHECK,
        "e2e7",
        "white",
        (cp_line("e2e7", 100), cp_line("e2a2", 70)),
        cp_line("e2e7", 100),
        "best",
        "low",
        expected_concepts=frozenset({"initiative", "forcing_move"}),
        target_tags=tags("quality:best", "concept:initiative", "concept:forcing_move"),
    ),
    LabelingSuiteCase(
        "c086-material-capture",
        "A real capture with net material should expose material evidence.",
        MATERIAL_CAPTURE,
        "e2d3",
        "white",
        (cp_line("e2d3", 100), cp_line("e1f2", 60)),
        cp_line("e2d3", 100),
        "best",
        "low",
        expected_concepts=frozenset({"capture", "material"}),
        target_tags=tags("quality:best", "concept:capture", "concept:material"),
    ),
    LabelingSuiteCase(
        "c087-ordinary-capture-not-recapture",
        "An ordinary capture should not be called a recapture without move history.",
        MATERIAL_CAPTURE,
        "e2d3",
        "white",
        (cp_line("e2d3", 40), cp_line("e1f2", 20)),
        cp_line("e2d3", 40),
        "best",
        "low",
        expected_concepts=frozenset({"capture", "material"}),
        target_tags=tags("concept:capture", "coach:not-recapture"),
    ),
    LabelingSuiteCase(
        "c088-black-knight-development",
        "Black minor-piece development should be tagged from Black perspective.",
        BLACK_KNIGHT_MOVE,
        "g8f6",
        "black",
        (cp_line("g8f6", 60), cp_line("c7c5", 40)),
        cp_line("g8f6", 60),
        "best",
        "low",
        expected_concepts=frozenset({"development"}),
        target_tags=tags("quality:best", "concept:development", "perspective:black"),
    ),
    LabelingSuiteCase(
        "c089-opening-pawn-not-opening-name",
        "A generic opening pawn move should not imply a named opening.",
        START,
        "e2e4",
        "white",
        (cp_line("e2e4", 60), cp_line("d2d4", 50)),
        cp_line("e2e4", 60),
        "best",
        "low",
        expected_concepts=frozenset({"development"}),
        target_tags=tags("quality:best", "coach:no-unsupported-opening-name"),
    ),
    LabelingSuiteCase(
        "c090-low-time-castling",
        "Castling in low time should allow time context without changing quality.",
        CASTLING,
        "e1g1",
        "white",
        (cp_line("e1g1", 80), cp_line("e1c1", 70)),
        cp_line("e1g1", 80),
        "best",
        "low",
        expected_time_situation="time_scramble",
        clock_before_seconds=8,
        increment_seconds=0,
        expected_concepts=frozenset({"castling"}),
        target_tags=tags("quality:best", "time:time_scramble", "concept:castling"),
    ),
    LabelingSuiteCase(
        "c091-low-time-promotion",
        "Promotion under time pressure should be creditable.",
        PROMOTION,
        "a7a8q",
        "white",
        (cp_line("a7a8q", 900), cp_line("h1g2", 600)),
        cp_line("a7a8q", 900),
        "best",
        "critical",
        expected_time_situation="time_scramble",
        clock_before_seconds=2,
        increment_seconds=0,
        expected_concepts=frozenset({"promotion"}),
        target_tags=tags("quality:best", "time:time_scramble", "coach:fast-good-move-credit"),
    ),
    LabelingSuiteCase(
        "c092-low-time-knight-fork",
        "A tactical best move under time pressure should get fast-resource credit.",
        KNIGHT_FORK,
        "c4b6",
        "white",
        (cp_line("c4b6", 325, pv=("c4b6", "d7d6", "b6a8")), cp_line("g3f2", 125)),
        cp_line("c4b6", 325, pv=("c4b6", "d7d6", "b6a8")),
        "best",
        "critical",
        expected_time_situation="time_scramble",
        clock_before_seconds=1,
        increment_seconds=0,
        expected_concepts=frozenset({"tactic", "piece_activity", "critical_best_move"}),
        target_tags=tags("quality:best", "time:time_scramble", "coach:fast-tactic-credit"),
    ),
    LabelingSuiteCase(
        "c093-low-time-en-passant",
        "En passant under time pressure should be a specific legal-move success.",
        EN_PASSANT,
        "e5d6",
        "white",
        (cp_line("e5d6", 100), cp_line("g1f3", 60)),
        cp_line("e5d6", 100),
        "best",
        "low",
        expected_time_situation="time_scramble",
        clock_before_seconds=1,
        increment_seconds=0,
        expected_concepts=frozenset({"en_passant", "capture"}),
        target_tags=tags("quality:best", "time:time_scramble", "coach:special-rule-under-time"),
    ),
    LabelingSuiteCase(
        "c094-fork-miss-is-mistake",
        "Missing a concrete fork should expose the better tactic.",
        KNIGHT_FORK,
        "g3f2",
        "white",
        (cp_line("c4b6", 325, pv=("c4b6", "d7d6", "b6a8")), cp_line("g3f2", 125)),
        cp_line("g3f2", 125),
        "mistake",
        "critical",
        expected_key_move="Nb6",
        target_tags=tags("quality:mistake", "concept:tactic", "coach:missed-concrete-tactic"),
    ),
    LabelingSuiteCase(
        "c095-fork-miss-under-one-second",
        "Missing a tactic under one second still matters but needs time-context wording.",
        KNIGHT_FORK,
        "g3f2",
        "white",
        (cp_line("c4b6", 325, pv=("c4b6", "d7d6", "b6a8")), cp_line("g3f2", 125)),
        cp_line("g3f2", 125),
        "mistake",
        "critical",
        expected_time_situation="time_scramble",
        clock_before_seconds=0.9,
        increment_seconds=0,
        expected_key_move="Nb6",
        target_tags=tags("quality:mistake", "time:time_scramble", "coach:time-scramble-miss"),
    ),
    LabelingSuiteCase(
        "c096-ordinary-opening-blunder-low-rating",
        "A beginner opening blunder should stay direct and concrete.",
        START,
        "f2f3",
        "white",
        (cp_line("e2e4", 120), cp_line("d2d4", 90)),
        cp_line("f2f3", -230),
        "blunder",
        "critical",
        player_rating=650,
        target_tags=tags("quality:blunder", "rating:beginner", "coach:concrete-beginner-wording"),
    ),
    LabelingSuiteCase(
        "c097-advanced-engine-like-resource",
        "An advanced player can receive harder-resource nuance without moving truth.",
        START,
        "a2a3",
        "white",
        (cp_line("e2e4", 300), cp_line("d2d4", 210)),
        cp_line("a2a3", -60),
        "blunder",
        "critical",
        player_rating=2300,
        human=(human("e2e4", 0.015, 0.10),),
        expected_findability={"e4": "very_hard"},
        expected_policy={"e4": "explain_as_hidden_resource"},
        target_tags=tags("quality:blunder", "rating:advanced", "coach:advanced-practical-nuance"),
    ),
    LabelingSuiteCase(
        "c098-black-low-time-good-move",
        "Black can also make a good non-best move under time pressure.",
        AFTER_E4,
        "e7e5",
        "black",
        (cp_line("c7c5", 100, (500, 400, 100)), cp_line("e7e5", 60, (480, 400, 120))),
        cp_line("e7e5", 60, (480, 400, 120)),
        "good",
        "low",
        expected_time_situation="time_scramble",
        clock_before_seconds=1,
        increment_seconds=0,
        target_tags=tags("quality:good", "time:time_scramble", "perspective:black"),
    ),
    LabelingSuiteCase(
        "c099-black-low-time-blunder",
        "Black blunders under time pressure should preserve side attribution.",
        AFTER_E4,
        "g7g5",
        "black",
        (cp_line("c7c5", 100), cp_line("e7e5", 60)),
        cp_line("g7g5", -250),
        "blunder",
        "critical",
        expected_time_situation="time_scramble",
        clock_before_seconds=1,
        increment_seconds=0,
        target_tags=tags("quality:blunder", "time:time_scramble", "perspective:black"),
    ),
    LabelingSuiteCase(
        "c100-current-suite-sentinel",
        "Sentinel case: routine best move should produce a verified concise baseline.",
        START,
        "e2e4",
        "white",
        (cp_line("e2e4", 80), cp_line("d2d4", 60)),
        cp_line("e2e4", 80),
        "best",
        "low",
        target_tags=tags("quality:best", "significance:low", "explanation:verified"),
    ),
)


def test_manual_labeling_suite_has_one_hundred_unique_cases() -> None:
    assert len(MANUAL_LABELING_SUITE) == 100
    assert len({case.case_id for case in MANUAL_LABELING_SUITE}) == 100


@pytest.mark.parametrize("case", MANUAL_LABELING_SUITE, ids=lambda case: case.case_id)
def test_manual_labeling_suite_matches_current_deterministic_contracts(
    case: LabelingSuiteCase,
) -> None:
    result = _build_context(case)

    assert result.evidence.quality.label == case.expected_quality
    assert result.evidence.significance.label == case.expected_significance
    assert result.llm_context.time_situation == case.expected_time_situation
    assert result.verification.passed

    if case.expected_key_move is not None:
        assert result.llm_context.best_or_key_move is not None
        assert result.llm_context.best_or_key_move.move == case.expected_key_move
    if case.expected_featured_move is not None:
        assert result.llm_context.featured_move is not None
        assert result.llm_context.featured_move.move == case.expected_featured_move

    by_san = {candidate.san: candidate for candidate in result.evidence.candidates}
    for san, expected_findability in case.expected_findability.items():
        assert by_san[san].time_adjusted_findability == expected_findability
    for san, expected_policy in case.expected_policy.items():
        assert by_san[san].recommendation_policy == expected_policy

    concept_kinds = {claim.kind for claim in result.evidence.concept_claims}
    assert concept_kinds >= case.expected_concepts

    output = render_baseline_explanation(result)
    verification = ExplanationVerifier().verify(result, output)
    assert verification.passed
    assert output.explanation


@pytest.mark.skipif(
    os.getenv("G6EXPLANATION_RUN_MANUAL_LABELING_TARGET_EVAL") != "1",
    reason="Manual target labeling eval is opt-in because it documents known product gaps.",
)
def test_manual_labeling_suite_target_tags_are_represented_by_current_context() -> None:
    missing_by_case: dict[str, set[str]] = {}
    for case in MANUAL_LABELING_SUITE:
        current = _current_tags(_build_context(case))
        missing = set(case.target_tags) - current
        if missing:
            missing_by_case[case.case_id] = missing

    assert not missing_by_case, _format_missing_tags(missing_by_case)


def _build_context(case: LabelingSuiteCase) -> ContextResult:
    board, played_move, _ = reconstruct_move_context(case.request())
    analysis = _analysis_from_case(case, board, played_move)
    human_provider = None
    if case.human:
        human_provider = StaticHumanLikelihoodProvider(
            {
                item.uci: HumanMoveLikelihood(
                    player_level_probability=item.probability,
                    plus_400_probability=item.plus_400_probability,
                    evidence_source="manual-suite",
                    rank=item.rank,
                    is_top_human_move=item.is_top_human_move,
                )
                for item in case.human
            }
        )
    return MoveContextBuilder(StaticAnalysisProvider(analysis), human_provider).build(
        case.request()
    )


def _analysis_from_case(
    case: LabelingSuiteCase,
    board: chess.Board,
    played_move: chess.Move,
) -> EngineAnalysis:
    after_board = board.copy(stack=False)
    after_board.push(played_move)
    return EngineAnalysis(
        engine_version="static-manual-labeling-suite",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=len(case.top_lines)),
        top_lines=[
            _engine_line(board, spec, rank=index + 1) for index, spec in enumerate(case.top_lines)
        ],
        played_line=_engine_line(board, case.played_line, rank=None),
        after_line=_engine_line(after_board, cp_line(case.after_reply_uci, 0), rank=1)
        if case.after_reply_uci is not None
        else None,
    )


def _engine_line(board: chess.Board, spec: LineSpec, rank: int | None) -> EngineLine:
    move = chess.Move.from_uci(spec.uci)
    assert move in board.legal_moves
    pv_uci = list(spec.pv_uci or (spec.uci,))
    return EngineLine(
        move_uci=spec.uci,
        move_san=board.san(move),
        score=spec.score,
        rank=rank,
        wdl=spec.wdl,
        pv_uci=pv_uci,
        pv_san=pv_san(board, pv_uci),
    )


def _current_tags(result: ContextResult) -> set[str]:
    output = render_baseline_explanation(result)
    tags = {
        f"quality:{result.evidence.quality.label}",
        f"significance:{result.evidence.significance.label}",
        f"beauty:{result.evidence.beauty.label}",
        f"time:{result.llm_context.time_situation}",
        f"perspective:{result.evidence.request.player_color}",
        "explanation:verified",
    }
    for claim in result.evidence.concept_claims:
        tags.add(f"concept:{claim.kind}")
    for candidate in result.evidence.candidates:
        tags.add(f"findability:{candidate.san}:{candidate.time_adjusted_findability}")
        tags.add(f"policy:{candidate.san}:{candidate.recommendation_policy}")
        tags.add(f"practicality:{candidate.san}:{candidate.practicality}")
        for role in candidate.roles:
            tags.add(f"role:{candidate.san}:{role}")
    if result.llm_context.human_note:
        tags.add("human_note:present")
    explanation = output.explanation.lower()
    if "low time" in explanation or "time scramble" in explanation:
        tags.add("explanation:mentions-time-pressure")
    if "hard" in explanation:
        tags.add("explanation:hard-caveat")
    rating = result.evidence.request.player_level.rating_value()
    if rating is not None:
        if rating < 1000:
            tags.add("rating:beginner")
        elif rating >= 2200:
            tags.add("rating:advanced")
    return tags


def _format_missing_tags(missing_by_case: dict[str, set[str]]) -> str:
    lines = [
        "Manual target labels not represented by current context/explanation tags:",
        f"{sum(len(tags) for tags in missing_by_case.values())} missing tags across "
        f"{len(missing_by_case)} cases.",
    ]
    for case_id, missing in sorted(missing_by_case.items()):
        lines.append(f"- {case_id}: {', '.join(sorted(missing))}")
    return "\n".join(lines)
