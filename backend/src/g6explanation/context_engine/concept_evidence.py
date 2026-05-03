"""Deterministic chess concept evidence for LLM-facing claims."""

from __future__ import annotations

import chess

from g6explanation.context_engine.contracts import ConceptClaim, ConceptClaimSubject

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}
DEVELOPMENT_HOME_SQUARES = {
    chess.WHITE: {chess.B1, chess.C1, chess.F1, chess.G1},
    chess.BLACK: {chess.B8, chess.C8, chess.F8, chess.G8},
}
CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}


def build_move_concept_claims(
    board: chess.Board,
    move_uci: str,
    move_san: str,
    subject: ConceptClaimSubject,
) -> list[ConceptClaim]:
    """Return conservative concept claims that follow directly from one legal move."""

    move = chess.Move.from_uci(move_uci)
    if move not in board.legal_moves:
        return []
    piece = board.piece_at(move.from_square)
    if piece is None:
        return []

    after_board = board.copy(stack=False)
    after_board.push(move)
    claims: list[ConceptClaim] = []
    claims.extend(_material_claims(board, after_board, move, piece.color, move_san, subject))
    if board.gives_check(move):
        claims.append(
            ConceptClaim(
                kind="forcing_move",
                subject=subject,
                claim=f"{move_san} gave check",
                source="deterministic_detector",
                move_san=move_san,
            )
        )
    if _develops_minor_piece(piece, move):
        claims.append(
            ConceptClaim(
                kind="development",
                subject=subject,
                claim=f"{move_san} developed a piece",
                source="deterministic_detector",
                move_san=move_san,
            )
        )
    if _occupies_center(move):
        claims.append(
            ConceptClaim(
                kind="center",
                subject=subject,
                claim=f"{move_san} claimed the center",
                source="deterministic_detector",
                move_san=move_san,
            )
        )
    if _uses_open_file(after_board, piece, move):
        claims.append(
            ConceptClaim(
                kind="open_file",
                subject=subject,
                claim=f"{move_san} used an open file",
                source="deterministic_detector",
                move_san=move_san,
            )
        )
    if _advances_passed_pawn(after_board, piece, move):
        claims.append(
            ConceptClaim(
                kind="passed_pawn",
                subject=subject,
                claim=f"{move_san} advanced a passed pawn",
                source="deterministic_detector",
                move_san=move_san,
            )
        )
    if _occupies_knight_outpost(after_board, piece, move):
        claims.append(
            ConceptClaim(
                kind="weak_square",
                subject=subject,
                claim=f"{move_san} occupied an outpost",
                source="deterministic_detector",
                move_san=move_san,
            )
        )
    return claims


def _material_claims(
    board: chess.Board,
    after_board: chess.Board,
    move: chess.Move,
    player: chess.Color,
    move_san: str,
    subject: ConceptClaimSubject,
) -> list[ConceptClaim]:
    delta = _material_balance(after_board, player) - _material_balance(board, player)
    if delta == 0:
        return []
    material_detail = _material_detail(board, move, delta)
    if delta > 0:
        claim = f"{move_san} won {material_detail} immediately"
    else:
        claim = f"{move_san} gave up {material_detail} immediately"
    return [
        ConceptClaim(
            kind="material",
            subject=subject,
            claim=claim,
            source="deterministic_detector",
            move_san=move_san,
        )
    ]


def _material_detail(board: chess.Board, move: chess.Move, delta: int) -> str:
    if move.promotion is not None:
        promoted_piece = _piece_name(move.promotion)
        captured_piece = _captured_piece(board, move)
        if captured_piece is not None:
            captured_piece_name = _piece_name(captured_piece.piece_type)
            return (
                f"material by promoting to a {promoted_piece} and capturing a {captured_piece_name}"
            )
        return f"material by promoting to a {promoted_piece}"
    captured_piece = _captured_piece(board, move)
    if captured_piece is not None:
        return f"a {_piece_name(captured_piece.piece_type)}"
    return _material_value_name(abs(delta))


def _captured_piece(board: chess.Board, move: chess.Move) -> chess.Piece | None:
    if board.is_en_passant(move):
        captured_rank = chess.square_rank(move.from_square)
        captured_square = chess.square(chess.square_file(move.to_square), captured_rank)
        return board.piece_at(captured_square)
    return board.piece_at(move.to_square)


def _material_value_name(value: int) -> str:
    piece_names = {
        100: "a pawn",
        300: "a minor piece",
        500: "a rook",
        800: "material",
        900: "a queen",
    }
    return piece_names.get(value, "material")


def _piece_name(piece_type: chess.PieceType) -> str:
    names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king",
    }
    return names[piece_type]


def _material_balance(board: chess.Board, player: chess.Color) -> int:
    total = 0
    for piece in board.piece_map().values():
        value = PIECE_VALUES.get(piece.piece_type, 0)
        total += value if piece.color == player else -value
    return total


def _develops_minor_piece(piece: chess.Piece, move: chess.Move) -> bool:
    return (
        piece.piece_type in {chess.KNIGHT, chess.BISHOP}
        and move.from_square in DEVELOPMENT_HOME_SQUARES[piece.color]
    )


def _occupies_center(move: chess.Move) -> bool:
    return move.to_square in CENTER_SQUARES


def _uses_open_file(board: chess.Board, piece: chess.Piece, move: chess.Move) -> bool:
    if piece.piece_type not in {chess.ROOK, chess.QUEEN}:
        return False
    file_index = chess.square_file(move.to_square)
    return all(
        (piece_on_file := board.piece_at(chess.square(file_index, rank))) is None
        or piece_on_file.piece_type != chess.PAWN
        for rank in range(8)
    )


def _advances_passed_pawn(board: chess.Board, piece: chess.Piece, move: chess.Move) -> bool:
    if piece.piece_type != chess.PAWN or move.promotion is not None:
        return False
    return _is_passed_pawn(board, move.to_square, piece.color)


def _is_passed_pawn(board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    rank_range = range(rank_index + 1, 8) if color == chess.WHITE else range(rank_index - 1, -1, -1)
    for adjacent_file in range(max(0, file_index - 1), min(7, file_index + 1) + 1):
        for rank in rank_range:
            piece = board.piece_at(chess.square(adjacent_file, rank))
            if piece is not None and piece.color != color and piece.piece_type == chess.PAWN:
                return False
    return True


def _occupies_knight_outpost(board: chess.Board, piece: chess.Piece, move: chess.Move) -> bool:
    if piece.piece_type != chess.KNIGHT:
        return False
    rank_index = chess.square_rank(move.to_square)
    in_opponent_half = rank_index >= 4 if piece.color == chess.WHITE else rank_index <= 3
    if not in_opponent_half:
        return False
    friendly_pawn_attackers = [
        attacker
        for attacker in board.attackers(piece.color, move.to_square)
        if (attacker_piece := board.piece_at(attacker)) is not None
        and attacker_piece.piece_type == chess.PAWN
    ]
    opposing_pawn_attackers = [
        attacker
        for attacker in board.attackers(not piece.color, move.to_square)
        if (attacker_piece := board.piece_at(attacker)) is not None
        and attacker_piece.piece_type == chess.PAWN
    ]
    return bool(friendly_pawn_attackers) and not opposing_pawn_attackers
