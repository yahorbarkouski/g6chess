from __future__ import annotations

import chess
import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    ContextResult,
    EngineAnalysis,
    EngineAnalysisBudget,
    EngineLine,
    HumanMoveLikelihood,
    MoveContextRequest,
    PlayedMoveFacts,
    PlayerLevel,
    Score,
    Wdl,
    WdlDelta,
)
from g6explanation.context_engine.exceptions import AnalysisError
from g6explanation.context_engine.signals import calculate_significance, classify_quality
from tests.g6explanation.context_engine.helpers import (
    StaticAnalysisProvider,
    StaticHumanLikelihoodProvider,
    analysis,
    engine_line,
)


def test_uses_practical_alternative_when_engine_best_is_hard_and_close() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 40), ("g1f3", 25)],
        played_score=-180,
        after_reply_uci="e7e5",
    )
    human = StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(player_level_probability=0.02, plus_400_probability=0.12),
            "g1f3": HumanMoveLikelihood(player_level_probability=0.32, plus_400_probability=0.40),
            "g2g4": HumanMoveLikelihood(player_level_probability=0.25, plus_400_probability=0.08),
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1250, "lichess"),
        time_control="blitz",
        clock_before_seconds=80,
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)

    assert result.evidence.quality.label == "mistake"
    assert result.evidence.significance.label == "critical"
    assert result.evidence.significance.score == 0.73
    assert result.llm_context.significance.label == "critical"
    assert result.llm_context.best_or_key_move is not None
    assert result.llm_context.best_or_key_move.move == "Nf3"
    assert result.llm_context.best_or_key_move.practicality == "practical_try"
    assert (
        result.llm_context.best_or_key_move.recommendation_policy == "use_as_practical_alternative"
    )
    assert _concept_kinds(result) >= {
        "move_quality",
        "practical_alternative",
        "opponent_resource",
    }


def test_caveats_hard_engine_best_instead_of_presenting_it_as_obvious() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="a2a3",
        top_scores=[("e2e4", 300), ("d2d4", 210)],
        played_score=-60,
        after_reply_uci="e7e5",
    )
    human = StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(player_level_probability=0.015, plus_400_probability=0.10),
            "a2a3": HumanMoveLikelihood(player_level_probability=0.20, plus_400_probability=0.02),
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="a2a3",
        player_color="white",
        player_level=PlayerLevel.rating(900, "lichess"),
        time_control="blitz",
        clock_before_seconds=20,
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)

    assert result.evidence.quality.label == "blunder"
    assert result.llm_context.best_or_key_move is not None
    assert result.llm_context.best_or_key_move.move == "e4"
    assert result.llm_context.best_or_key_move.recommendation_policy == "explain_as_hidden_resource"
    assert result.llm_context.best_or_key_move.findability in {"very_hard", "engine_like"}
    assert result.llm_context.human_note is not None


def test_low_significance_when_best_move_is_only_slightly_better() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="e2e4",
        top_scores=[("e2e4", 40), ("d2d4", 25)],
        played_score=40,
        after_reply_uci="e7e5",
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.quality.label == "best"
    assert result.evidence.significance.label == "low"
    assert result.evidence.significance.score == 0.05


def test_good_move_concept_claims_cover_exposed_alternatives() -> None:
    board = chess.Board()
    after_board = board.copy(stack=False)
    after_board.push(chess.Move.from_uci("d2d4"))
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=2),
        top_lines=[
            engine_line(board, "e2e4", 100, rank=1, wdl=Wdl(win=500, draw=400, loss=100)),
            engine_line(board, "g1f3", 95, rank=2, wdl=Wdl(win=490, draw=400, loss=110)),
        ],
        played_line=engine_line(
            board,
            "d2d4",
            70,
            rank=None,
            wdl=Wdl(win=480, draw=400, loss=120),
        ),
        after_line=engine_line(
            after_board,
            "d7d5",
            70,
            rank=1,
            wdl=Wdl(win=480, draw=400, loss=120),
        ),
    )
    human = StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(
                player_level_probability=0.005,
                plus_400_probability=0.12,
            ),
            "g1f3": HumanMoveLikelihood(
                player_level_probability=0.30,
                plus_400_probability=0.35,
            ),
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="d2d4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)

    assert result.evidence.quality.label == "good"
    assert result.llm_context.best_or_key_move is None
    assert result.llm_context.engine_best_move is not None
    assert result.llm_context.engine_best_move.move == "e4"
    assert result.llm_context.practical_alternative is not None
    assert result.llm_context.practical_alternative.move == "Nf3"
    assert _concept_keys(result) >= {
        ("hidden_resource", "engine_best_move", "e4"),
        ("hard_to_find", "engine_best_move", "e4"),
        ("practical_alternative", "practical_alternative", "Nf3"),
    }


@pytest.mark.parametrize(
    ("fen", "played_uci", "expected_san", "expected_kind"),
    [
        ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1", "O-O", "castling"),
        (
            "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3",
            "e5d6",
            "exd6",
            "en_passant",
        ),
        ("8/P7/8/8/8/8/8/k6K w - - 0 1", "a7a8q", "a8=Q+", "promotion"),
    ],
)
def test_special_played_move_concept_claims(
    fen: str,
    played_uci: str,
    expected_san: str,
    expected_kind: str,
) -> None:
    board = chess.Board(fen)
    engine_analysis = analysis(
        board,
        played_uci=played_uci,
        top_scores=[(played_uci, 100)],
        played_score=100,
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move=played_uci,
        player_color="white",
        player_level=PlayerLevel.rating(1600),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.played.san == expected_san
    assert expected_kind in _concept_kinds(result)


@pytest.mark.parametrize(
    ("fen", "played_uci", "expected_san", "expected_kind"),
    [
        ("8/8/8/8/8/3p4/4P3/4K2k w - - 0 1", "e2d3", "exd3", "material"),
        ("4k3/8/8/8/8/8/8/4K1N1 w - - 0 1", "g1f3", "Nf3", "development"),
        ("4k3/8/8/8/8/8/3P4/4K3 w - - 0 1", "d2d4", "d4", "center"),
        ("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1", "a1d1", "Rd1", "open_file"),
        ("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1", "e4e5", "e5", "passed_pawn"),
        ("4k3/8/8/8/2P1PN2/8/8/4K3 w - - 0 1", "f4d5", "Nd5", "weak_square"),
        ("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1", "e2e7", "Qe7+", "initiative"),
    ],
)
def test_deterministic_concept_claims_for_concrete_chess_features(
    fen: str,
    played_uci: str,
    expected_san: str,
    expected_kind: str,
) -> None:
    board = chess.Board(fen)
    engine_analysis = analysis(
        board,
        played_uci=played_uci,
        top_scores=[(played_uci, 100)],
        played_score=100,
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move=played_uci,
        player_color="white",
        player_level=PlayerLevel.rating(1600),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.played.san == expected_san
    assert expected_kind in _concept_kinds(result)


def test_recapture_restores_material_balance_instead_of_winning_pawn() -> None:
    pgn = "1. e4 c6 2. Nf3 d5 3. exd5 cxd5"
    board = chess.Board()
    for san in ["e4", "c6", "Nf3", "d5", "exd5"]:
        board.push_san(san)
    engine_analysis = analysis(
        board,
        played_uci="c6d5",
        top_scores=[("c6d5", 100)],
        played_score=100,
    )
    request = MoveContextRequest(
        pgn=pgn,
        ply=6,
        player_color="black",
        player_level=PlayerLevel.rating(1200),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.position.previous_move_uci == "e4d5"
    assert result.evidence.position.previous_move_san == "exd5"
    assert result.evidence.position.previous_move_was_capture is True
    assert "recapture" in _concept_kinds(result)
    assert "cxd5 recaptured the pawn on d5" in {
        claim.claim for claim in result.evidence.concept_claims
    }
    assert "cxd5 restored the material balance by recapturing the pawn on d5" in {
        claim.claim for claim in result.evidence.concept_claims
    }
    assert "cxd5 won a pawn immediately" not in result.evidence.allowed_claims
    assert "cxd5 won a pawn immediately" not in {
        claim.claim for claim in result.evidence.concept_claims
    }
    assert result.llm_context.main_point == "cxd5 recaptured the pawn on d5"
    assert result.llm_context.allowed_claims[0] == "cxd5 recaptured the pawn on d5"


def test_candidate_capture_recaptured_in_pv_is_trade_not_material_win() -> None:
    board = chess.Board("r2qkb1r/pp2pppp/2n2n2/1B1p4/3P2b1/5N1P/PPP2PP1/RNBQ1RK1 b kq - 0 7")
    played_move = chess.Move.from_uci("g4h5")
    after_board = board.copy(stack=False)
    after_board.push(played_move)
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=2),
        top_lines=[
            engine_line(
                board,
                "g4f3",
                300,
                rank=1,
                pv_uci=["g4f3", "d1f3"],
            ),
            engine_line(
                board,
                "g4h5",
                -300,
                rank=2,
                pv_uci=["g4h5", "g2g4"],
            ),
        ],
        played_line=engine_line(
            board,
            "g4h5",
            -300,
            rank=None,
            pv_uci=["g4h5", "g2g4"],
        ),
        after_line=engine_line(after_board, "g2g4", -320, rank=1),
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g4h5",
        player_color="black",
        player_level=PlayerLevel.rating(1200),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    bxf3_material_claims = [
        claim.claim
        for claim in result.evidence.concept_claims
        if claim.kind == "material" and claim.move_san == "Bxf3"
    ]
    assert bxf3_material_claims
    assert all(claim == "Bxf3 traded a bishop for a knight" for claim in bxf3_material_claims)
    assert all("won a knight" not in claim for claim in bxf3_material_claims)
    assert "Bxf3 would have been the better move" in {
        claim.claim for claim in result.evidence.concept_claims
    }
    assert "Bxf3 would have been the key alternative" in result.llm_context.allowed_claims


def test_knight_fork_context_exposes_attacked_rooks_as_board_fact() -> None:
    board = chess.Board("r1b3k1/1p1r2pn/p7/5p2/2NppP2/6B1/PPP3PP/2KR3R w - - 0 22")
    engine_analysis = analysis(
        board,
        played_uci="c4b6",
        top_scores=[("c4b6", 325), ("g3f2", 125)],
        played_score=325,
        after_reply_uci="d7d6",
        played_pv_uci=["c4b6", "d7d6", "b6a8"],
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="c4b6",
        player_color="white",
        player_level=PlayerLevel.rating(1215, "chess.com"),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    claim_text = {claim.claim for claim in result.evidence.concept_claims}
    assert "Nb6 attacked both rooks: the rook on d7 and the rook on a8" in claim_text
    assert "Nb6 forked both rooks: the rook on d7 and the rook on a8" in claim_text
    assert result.llm_context.main_point == (
        "Nb6 forked both rooks: the rook on d7 and the rook on a8 in a critical position."
    )
    assert result.llm_context.allowed_claims[0] == (
        "Nb6 forked both rooks: the rook on d7 and the rook on a8"
    )
    assert _concept_kinds(result) >= {"piece_activity", "tactic"}


@pytest.mark.parametrize(
    ("fen", "played_uci", "expected_san", "expected_claim"),
    [
        (
            chess.STARTING_FEN,
            "g2g3",
            "g3",
            "g3 opened the fianchetto square on g2 for the bishop",
        ),
        (
            chess.STARTING_FEN,
            "b2b3",
            "b3",
            "b3 opened the fianchetto square on b2 for the bishop",
        ),
        (
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1",
            "g7g6",
            "g6",
            "g6 opened the fianchetto square on g7 for the bishop",
        ),
        (
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1",
            "b7b6",
            "b6",
            "b6 opened the fianchetto square on b7 for the bishop",
        ),
    ],
)
def test_flank_pawn_move_exposes_fianchetto_development_fact(
    fen: str,
    played_uci: str,
    expected_san: str,
    expected_claim: str,
) -> None:
    board = chess.Board(fen)
    engine_analysis = analysis(
        board,
        played_uci=played_uci,
        top_scores=[(played_uci, 40), ("g1f3" if board.turn == chess.WHITE else "g8f6", 25)],
        played_score=40,
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move=played_uci,
        player_color="white" if board.turn == chess.WHITE else "black",
        player_level=PlayerLevel.rating(1400),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.played.san == expected_san
    assert expected_claim in {claim.claim for claim in result.evidence.concept_claims}
    assert result.llm_context.main_point == expected_claim
    assert result.llm_context.allowed_claims[0] == expected_claim
    assert "development" in _concept_kinds(result)


@pytest.mark.parametrize(
    ("fen", "played_uci", "unexpected_claim"),
    [
        (
            chess.STARTING_FEN,
            "g2g4",
            "g4 opened the fianchetto square on g2 for the bishop",
        ),
        (
            chess.STARTING_FEN,
            "b2b4",
            "b4 opened the fianchetto square on b2 for the bishop",
        ),
        (
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQK1NR w KQkq - 0 1",
            "g2g3",
            "g3 opened the fianchetto square on g2 for the bishop",
        ),
    ],
)
def test_fianchetto_fact_requires_normal_one_square_push_and_home_bishop(
    fen: str,
    played_uci: str,
    unexpected_claim: str,
) -> None:
    board = chess.Board(fen)
    engine_analysis = analysis(
        board,
        played_uci=played_uci,
        top_scores=[(played_uci, 40), ("g1f3", 25)],
        played_score=40,
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move=played_uci,
        player_color="white",
        player_level=PlayerLevel.rating(1400),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert unexpected_claim not in {claim.claim for claim in result.evidence.concept_claims}
    assert unexpected_claim not in result.llm_context.allowed_claims


def test_mate_transition_adds_king_safety_concept_claim() -> None:
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2")
    after_board = board.copy(stack=False)
    after_board.push(chess.Move.from_uci("g2g4"))
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.cp(20),
                rank=1,
                pv_uci=["e2e4"],
                pv_san=["e4"],
            )
        ],
        played_line=EngineLine(
            move_uci="g2g4",
            move_san="g4",
            score=Score.mate(mate_in=1, mate_for="opponent"),
            rank=None,
            pv_uci=["g2g4"],
            pv_san=["g4"],
        ),
        after_line=EngineLine(
            move_uci="d8h4",
            move_san=after_board.san(chess.Move.from_uci("d8h4")),
            score=Score.mate(mate_in=1, mate_for="opponent"),
            rank=1,
            pv_uci=["d8h4"],
            pv_san=[after_board.san(chess.Move.from_uci("d8h4"))],
        ),
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(900),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.quality.label == "blunder"
    assert "king_safety" in _concept_kinds(result)


def test_only_legal_move_is_forced_not_blunder() -> None:
    board = chess.Board("1Q2kb1r/p2n1ppp/4q3/4p1B1/4P3/8/PPP2PPP/2KR4 b k - 1 16")
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="d7b8",
                move_san="Nxb8",
                score=Score.mate(mate_in=1, mate_for="opponent"),
                rank=1,
                pv_uci=["d7b8"],
                pv_san=["Nxb8"],
            )
        ],
        played_line=EngineLine(
            move_uci="d7b8",
            move_san="Nxb8",
            score=Score.mate(mate_in=1, mate_for="opponent"),
            rank=None,
            pv_uci=["d7b8"],
            pv_san=["Nxb8"],
        ),
        after_line=EngineLine(
            move_uci="d1d8",
            move_san="Rd8#",
            score=Score.mate(mate_in=1, mate_for="opponent"),
            rank=1,
            pv_uci=["d1d8"],
            pv_san=["Rd8#"],
        ),
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="d7b8",
        player_color="black",
        player_level=PlayerLevel.rating(2400),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)
    played_candidate = next(
        candidate for candidate in result.evidence.candidates if "played_move" in candidate.roles
    )

    assert result.evidence.quality.label == "forced"
    assert result.llm_context.best_or_key_move is None
    assert result.llm_context.featured_move is not None
    assert result.llm_context.featured_move.move == "Nxb8"
    assert "only_legal_move" in played_candidate.roles
    assert played_candidate.practicality == "only_move"
    assert result.evidence.beauty.label == "low"
    assert result.evidence.beauty.score == 0.0
    assert "forced_move" in _concept_kinds(result)
    assert "capture" in _concept_kinds(result)


def test_immediate_checkmate_is_best_even_when_engine_prefers_another_mate() -> None:
    board = chess.Board("1Q6/5pk1/2p3p1/1p2N2p/1b5P/1bn5/r5P1/2K5 b - - 15 41")
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="b4a3",
                move_san="Ba3#",
                score=Score.mate(mate_in=1, mate_for="player"),
                rank=1,
                pv_uci=["b4a3"],
                pv_san=["Ba3#"],
            ),
            EngineLine(
                move_uci="a2c2",
                move_san="Rc2#",
                score=Score.mate(mate_in=1, mate_for="player"),
                rank=2,
                pv_uci=["a2c2"],
                pv_san=["Rc2#"],
            ),
        ],
        played_line=EngineLine(
            move_uci="a2c2",
            move_san="Rc2#",
            score=Score.mate(mate_in=1, mate_for="player"),
            rank=None,
            pv_uci=["a2c2"],
            pv_san=["Rc2#"],
        ),
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="a2c2",
        player_color="black",
        player_level=PlayerLevel.rating(2400),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.played.is_checkmate is True
    assert result.evidence.quality.label == "best"
    assert result.evidence.significance.label == "critical"
    assert result.llm_context.featured_move is not None
    assert result.llm_context.featured_move.move == "Rc2#"
    assert result.llm_context.featured_move.practicality == "clear_recommendation"
    assert result.llm_context.featured_move.reason == "it checkmates the opponent"
    assert result.llm_context.featured_move.recommendation_policy == "recommend_directly"
    assert "forced_mate" in _concept_kinds(result)


def test_high_played_win_probability_prevents_bad_quality_label() -> None:
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.cp(1000),
                rank=1,
                wdl=Wdl(win=1000, draw=0, loss=0),
            )
        ],
        played_line=EngineLine(
            move_uci="d2d4",
            move_san="d4",
            score=Score.cp(700),
            rank=None,
            wdl=Wdl(win=900, draw=100, loss=0),
        ),
    )

    quality = classify_quality(
        engine_analysis,
        PlayedMoveFacts(uci="d2d4", san="d4", legal=True, is_check=False, is_capture=False),
    )

    assert quality.score_loss_vs_best_cp == 300
    assert quality.wdl_expected_score_loss == 50
    assert quality.label == "good"


def test_critical_significance_when_best_move_is_much_better_than_second_best() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="e2e4",
        top_scores=[("e2e4", 300), ("d2d4", -60)],
        played_score=300,
        after_reply_uci="e7e5",
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.quality.label == "best"
    assert result.evidence.significance.label == "critical"
    assert result.evidence.significance.score == 1.0
    assert result.llm_context.featured_move is not None
    assert result.llm_context.featured_move.move == "e4"
    assert "critical_best_move" in _concept_kinds(result)


def test_bad_move_context_separates_engine_best_from_practical_alternative() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 40), ("g1f3", 25)],
        played_score=-180,
        after_reply_uci="e7e5",
    )
    human = StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(player_level_probability=0.02, plus_400_probability=0.12),
            "g1f3": HumanMoveLikelihood(player_level_probability=0.32, plus_400_probability=0.40),
            "g2g4": HumanMoveLikelihood(player_level_probability=0.25, plus_400_probability=0.08),
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1250, "lichess"),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)

    assert result.llm_context.engine_best_move is not None
    assert result.llm_context.engine_best_move.move == "e4"
    assert result.llm_context.practical_alternative is not None
    assert result.llm_context.practical_alternative.move == "Nf3"
    assert result.llm_context.featured_move is not None
    assert result.llm_context.featured_move.move == "Nf3"


def test_human_probability_does_not_change_objective_quality() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 80)],
        played_score=-140,
        after_reply_uci="e7e5",
    )
    human = StaticHumanLikelihoodProvider(
        {
            "g2g4": HumanMoveLikelihood(player_level_probability=0.45),
            "e2e4": HumanMoveLikelihood(player_level_probability=0.08),
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)
    played_candidate = next(
        candidate for candidate in result.evidence.candidates if "played_move" in candidate.roles
    )

    assert played_candidate.time_adjusted_findability == "obvious"
    assert result.evidence.quality.label == "mistake"


def test_normalizes_black_player_scores_from_black_perspective() -> None:
    board = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    engine_analysis = analysis(
        board,
        played_uci="g7g5",
        top_scores=[("c7c5", 60)],
        played_score=-200,
        after_reply_uci="d2d4",
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g7g5",
        player_color="black",
        player_level=PlayerLevel.rating(1300),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.position.side_to_move == "black"
    assert result.evidence.quality.label == "mistake"
    assert result.evidence.quality.score_delta_cp_player_pov == -260


def test_mate_scores_are_classified_without_centipawn_delta() -> None:
    analysis_with_mate = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.mate(mate_in=3, mate_for="player"),
                rank=1,
            )
        ],
        played_line=EngineLine(
            move_uci="a2a3",
            move_san="a3",
            score=Score.cp(20),
            rank=None,
        ),
    )
    quality = classify_quality(
        analysis_with_mate,
        PlayedMoveFacts(uci="a2a3", san="a3", legal=True, is_check=False, is_capture=False),
    )

    assert quality.label == "missed_win"
    assert quality.score_delta_cp_player_pov is None
    assert "forced mate" in quality.severity_text


def test_engine_best_in_already_lost_forced_mate_is_not_a_blunder() -> None:
    analysis_with_opponent_mate = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.mate(mate_in=5, mate_for="opponent"),
                rank=1,
            )
        ],
        played_line=EngineLine(
            move_uci="e2e4",
            move_san="e4",
            score=Score.mate(mate_in=5, mate_for="opponent"),
            rank=None,
        ),
    )
    played = PlayedMoveFacts(
        uci="e2e4",
        san="e4",
        legal=True,
        is_check=False,
        is_capture=False,
    )

    quality = classify_quality(analysis_with_opponent_mate, played)
    significance = calculate_significance(analysis_with_opponent_mate, played)

    assert quality.label == "best"
    assert quality.severity_text == (
        "the move was the best defense in a position already losing by forced mate"
    )
    assert significance.label == "low"


def test_worsening_an_already_lost_forced_mate_is_a_blunder() -> None:
    analysis_with_opponent_mate = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.mate(mate_in=5, mate_for="opponent"),
                rank=1,
            )
        ],
        played_line=EngineLine(
            move_uci="d2d4",
            move_san="d4",
            score=Score.mate(mate_in=2, mate_for="opponent"),
            rank=None,
        ),
    )

    quality = classify_quality(
        analysis_with_opponent_mate,
        PlayedMoveFacts(uci="d2d4", san="d4", legal=True, is_check=False, is_capture=False),
    )

    assert quality.label == "blunder"
    assert quality.severity_text == "the move shortened the forced mate against the player"


def test_mate_transition_sets_significance_to_critical() -> None:
    analysis_with_mate = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.mate(mate_in=3, mate_for="player"),
                rank=1,
            )
        ],
        played_line=EngineLine(
            move_uci="a2a3",
            move_san="a3",
            score=Score.cp(20),
            rank=None,
        ),
    )

    significance = calculate_significance(
        analysis_with_mate,
        PlayedMoveFacts(uci="a2a3", san="a3", legal=True, is_check=False, is_capture=False),
    )

    assert significance.label == "critical"
    assert significance.score == 1.0


def test_wdl_loss_can_make_quality_worse_than_centipawns() -> None:
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.cp(100),
                rank=1,
                wdl=Wdl(win=400, draw=500, loss=100),
                pv_uci=["e2e4"],
                pv_san=["e4"],
            )
        ],
        played_line=EngineLine(
            move_uci="d2d4",
            move_san="d4",
            score=Score.cp(90),
            rank=None,
            wdl=Wdl(win=100, draw=600, loss=300),
            pv_uci=["d2d4"],
            pv_san=["d4"],
        ),
    )

    quality = classify_quality(
        engine_analysis,
        PlayedMoveFacts(uci="d2d4", san="d4", legal=True, is_check=False, is_capture=False),
    )

    assert quality.score_loss_vs_best_cp == 10
    assert quality.wdl_expected_score_loss == 250
    assert quality.wdl_delta_player_pov == WdlDelta(win=-300, draw=100, loss=200)
    assert quality.label == "blunder"


def test_wdl_gap_can_make_significance_critical_without_centipawn_gap() -> None:
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.cp(0),
                rank=1,
                wdl=Wdl(win=500, draw=300, loss=200),
                pv_uci=["e2e4"],
                pv_san=["e4"],
            )
        ],
        played_line=EngineLine(
            move_uci="a2a3",
            move_san="a3",
            score=Score.cp(0),
            rank=None,
            wdl=Wdl(win=300, draw=300, loss=400),
            pv_uci=["a2a3"],
            pv_san=["a3"],
        ),
    )

    significance = calculate_significance(
        engine_analysis,
        PlayedMoveFacts(uci="a2a3", san="a3", legal=True, is_check=False, is_capture=False),
    )

    assert significance.label == "critical"
    assert significance.score == 1.0


@pytest.mark.parametrize(
    ("probability", "expected"),
    [
        (0.30, "obvious"),
        (0.12, "findable"),
        (0.04, "hard"),
        (0.01, "very_hard"),
        (0.009, "engine_like"),
    ],
)
def test_findability_probability_thresholds(probability: float, expected: str) -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 100)],
        played_score=-100,
    )
    human = StaticHumanLikelihoodProvider(
        {"e2e4": HumanMoveLikelihood(player_level_probability=probability)}
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)
    candidate = next(
        candidate for candidate in result.evidence.candidates if candidate.uci == "e2e4"
    )

    assert candidate.time_adjusted_findability == expected


def test_low_time_worsens_findability_without_changing_quality() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 100)],
        played_score=-100,
    )
    human = StaticHumanLikelihoodProvider(
        {"e2e4": HumanMoveLikelihood(player_level_probability=0.12)}
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
        clock_before_seconds=20,
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)
    candidate = next(
        candidate for candidate in result.evidence.candidates if candidate.uci == "e2e4"
    )

    assert candidate.time_adjusted_findability == "hard"
    assert result.evidence.quality.label == "mistake"


def test_plus_400_probability_marks_teachable_skill_gap() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 100)],
        played_score=-100,
    )
    human = StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(
                player_level_probability=0.03,
                plus_400_probability=0.20,
            )
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)
    candidate = next(
        candidate for candidate in result.evidence.candidates if candidate.uci == "e2e4"
    )

    assert candidate.teachable_skill_gap is True
    assert candidate.recommendation_policy == "explain_as_hidden_resource"
    assert result.llm_context.human_note is not None


def test_unknown_human_evidence_stays_unknown_findability() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 100)],
        played_score=-100,
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)
    candidate = next(
        candidate for candidate in result.evidence.candidates if candidate.uci == "e2e4"
    )

    assert candidate.time_adjusted_findability == "unknown"
    assert candidate.findability_source == "unknown"


def test_rejects_analyzer_that_returns_different_played_move() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="a2a3",
        top_scores=[("e2e4", 50)],
        played_score=-20,
        after_reply_uci="e7e5",
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    engine = MoveContextBuilder(StaticAnalysisProvider(engine_analysis))

    with pytest.raises(AnalysisError, match="engine_played_line_mismatch"):
        engine.build(request)


def test_rejects_engine_line_with_illegal_pv_move() -> None:
    board = chess.Board()
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.cp(10),
                rank=1,
                pv_uci=["e2e4", "e2e4"],
                pv_san=["e4", "e4"],
            )
        ],
        played_line=EngineLine(
            move_uci="g2g4",
            move_san="g4",
            score=Score.cp(-100),
            rank=None,
            pv_uci=["g2g4"],
            pv_san=["g4"],
        ),
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    engine = MoveContextBuilder(StaticAnalysisProvider(engine_analysis))

    with pytest.raises(AnalysisError, match="engine_pv_illegal"):
        engine.build(request)


def _concept_kinds(result: ContextResult) -> set[str]:
    return {claim.kind for claim in result.evidence.concept_claims}


def _concept_keys(result: ContextResult) -> set[tuple[str, str, str | None]]:
    return {(claim.kind, claim.subject, claim.move_san) for claim in result.evidence.concept_claims}
