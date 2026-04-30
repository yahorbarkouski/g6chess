"""Move-beauty policy."""

from __future__ import annotations

import chess

from g6explanation.context_engine.contracts import (
    BeautyLabel,
    EngineAnalysis,
    HumanMoveLikelihood,
    MoveBeauty,
    MoveQuality,
    MoveQualityLabel,
    MoveSignificance,
    PlayedMoveFacts,
    Score,
)

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}


def calculate_beauty(
    board: chess.Board,
    analysis: EngineAnalysis,
    played: PlayedMoveFacts,
    quality: MoveQuality,
    significance: MoveSignificance,
    human_likelihoods: dict[str, HumanMoveLikelihood],
) -> MoveBeauty:
    """Measure sound aesthetic interest from engine, PV, and human-likeness evidence."""

    soundness = _soundness(quality.label)
    if soundness == 0:
        return MoveBeauty(label="low", score=0.0)

    move = chess.Move.from_uci(played.uci)
    pv = _legal_prefix(board, analysis.played_line.pv_uci)
    surprise = _surprise_component(human_likelihoods.get(played.uci))
    sacrifice = max(
        _sacrifice_component(board, pv, board.turn),
        _moved_piece_sacrifice_component(board, move),
    )
    forcing_sequence = _forcing_sequence_component(board, pv)
    uniqueness = significance.score
    mate_pattern = _mate_pattern_component(board, move, analysis.played_line.score)
    quiet_resource = _quiet_resource_component(
        board=board,
        move=move,
        significance=significance,
        sacrifice=sacrifice,
        forcing_sequence=forcing_sequence,
        surprise=surprise,
        mate_pattern=mate_pattern,
    )

    idea_quality = (
        (0.18 * surprise)
        + (0.24 * sacrifice)
        + (0.22 * forcing_sequence)
        + (0.16 * quiet_resource)
        + (0.12 * uniqueness)
        + (0.08 * mate_pattern)
    )
    score = round(soundness * ((0.65 * idea_quality) + (0.35 * significance.score)), 2)
    return MoveBeauty(label=_beauty_label(score), score=score)


def _soundness(label: MoveQualityLabel) -> float:
    if label in {"best", "excellent"}:
        return 1.0
    if label == "good":
        return 0.85
    if label in {"forced", "neutral"}:
        return 0.55
    return 0.0


def _surprise_component(likelihood: HumanMoveLikelihood | None) -> float:
    probability = likelihood.player_level_probability if likelihood else None
    if probability is None:
        return 0.5
    return 1 - _clamp(probability / 0.30)


def _sacrifice_component(board: chess.Board, pv: list[chess.Move], player: chess.Color) -> float:
    if not pv:
        return 0.0

    replay = board.copy(stack=False)
    before = _material_balance(replay, player)
    min_delta = 0
    for move in pv[:6]:
        if move not in replay.legal_moves:
            break
        replay.push(move)
        min_delta = min(min_delta, _material_balance(replay, player) - before)

    material_invested = -min_delta
    return _clamp(material_invested / 500)


def _moved_piece_sacrifice_component(board: chess.Board, move: chess.Move) -> float:
    moved_piece = board.piece_at(move.from_square)
    if moved_piece is None:
        return 0.0

    after = board.copy(stack=False)
    if move not in after.legal_moves:
        return 0.0
    after.push(move)

    piece_after_move = after.piece_at(move.to_square)
    if piece_after_move is None:
        return 0.0

    attacker_values = [
        value
        for attacker in (
            after.piece_at(square)
            for square in after.attackers(not moved_piece.color, move.to_square)
        )
        if attacker is not None
        for value in [_piece_value(attacker)]
        if value > 0
    ]
    if not attacker_values:
        return 0.0

    capture_risk = _piece_value(piece_after_move) - min(attacker_values)
    if capture_risk <= 0:
        return 0.0
    return _clamp(capture_risk / 500)


def _forcing_sequence_component(board: chess.Board, pv: list[chess.Move]) -> float:
    if not pv:
        return 0.0

    replay = board.copy(stack=False)
    forcing = 0
    total = 0
    for move in pv[:6]:
        if move not in replay.legal_moves:
            break
        is_forcing = (
            replay.gives_check(move) or replay.is_capture(move) or move.promotion is not None
        )
        replay.push(move)
        if replay.is_checkmate():
            is_forcing = True
        forcing += int(is_forcing)
        total += 1

    if total == 0:
        return 0.0
    return forcing / total


def _quiet_resource_component(
    board: chess.Board,
    move: chess.Move,
    significance: MoveSignificance,
    sacrifice: float,
    forcing_sequence: float,
    surprise: float,
    mate_pattern: float,
) -> float:
    if board.gives_check(move) or board.is_capture(move) or move.promotion is not None:
        return 0.0
    if significance.score < 0.35:
        return 0.0
    if sacrifice < 0.4 and forcing_sequence < 0.5 and surprise < 0.75 and mate_pattern == 0:
        return 0.0
    return 1.0


def _mate_pattern_component(board: chess.Board, move: chess.Move, score: Score) -> float:
    if move in board.legal_moves:
        after = board.copy(stack=False)
        after.push(move)
        if after.is_checkmate():
            return 1.0

    if score.kind == "mate" and score.mate_for == "player" and score.mate_in is not None:
        return _clamp((6 - min(score.mate_in, 6)) / 5)
    return 0.0


def _legal_prefix(board: chess.Board, pv_uci: list[str]) -> list[chess.Move]:
    replay = board.copy(stack=False)
    legal_moves: list[chess.Move] = []
    for uci in pv_uci:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in replay.legal_moves:
            break
        legal_moves.append(move)
        replay.push(move)
    return legal_moves


def _material_balance(board: chess.Board, player: chess.Color) -> int:
    balance = 0
    for piece in board.piece_map().values():
        value = PIECE_VALUES.get(piece.piece_type, 0)
        balance += value if piece.color == player else -value
    return balance


def _piece_value(piece: chess.Piece) -> int:
    return PIECE_VALUES.get(piece.piece_type, 0)


def _beauty_label(score: float) -> BeautyLabel:
    if score >= 0.75:
        return "brilliant"
    if score >= 0.50:
        return "beautiful"
    if score >= 0.25:
        return "notable"
    return "low"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
