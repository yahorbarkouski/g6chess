"""Deterministic chess concept evidence for LLM-facing claims."""

from __future__ import annotations

from collections.abc import Sequence

import chess

from g6explanation.context_engine.contracts import ConceptClaim, ConceptClaimSubject
from g6explanation.context_engine.move_history import (
    previous_board as board_before_previous_move,
)
from g6explanation.context_engine.move_history import (
    previous_move_details,
)

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
VALUABLE_ATTACK_TARGETS = {chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN}


def build_move_concept_claims(
    board: chess.Board,
    move_uci: str,
    move_san: str,
    subject: ConceptClaimSubject,
    line_pv_uci: Sequence[str] | None = None,
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
    claims.extend(_recapture_claims(board, move, move_san, subject))
    claims.extend(
        _material_claims(
            board,
            after_board,
            move,
            piece.color,
            move_san,
            subject,
            line_pv_uci,
        )
    )
    claims.extend(_attacked_piece_claims(after_board, piece, move, move_san, subject))
    claims.extend(_opened_bishop_route_claims(board, after_board, piece, move, move_san, subject))
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


def _attacked_piece_claims(
    after_board: chess.Board,
    piece: chess.Piece,
    move: chess.Move,
    move_san: str,
    subject: ConceptClaimSubject,
) -> list[ConceptClaim]:
    targets = _valuable_targets_attacked_by_moved_piece(after_board, piece.color, move.to_square)
    if not targets:
        return []

    target_phrase = _attacked_targets_phrase(targets)
    claims = [
        ConceptClaim(
            kind="piece_activity",
            subject=subject,
            claim=f"{move_san} attacked {target_phrase}",
            source="deterministic_detector",
            move_san=move_san,
        )
    ]
    if len(targets) >= 2:
        claims.append(
            ConceptClaim(
                kind="tactic",
                subject=subject,
                claim=f"{move_san} forked {target_phrase}",
                source="deterministic_detector",
                move_san=move_san,
            )
        )
    claims.extend(_same_type_fork_claims(targets, move_san, subject))
    return claims


def _valuable_targets_attacked_by_moved_piece(
    board: chess.Board,
    attacker_color: chess.Color,
    attacker_square: chess.Square,
) -> list[tuple[chess.Square, chess.Piece]]:
    targets: list[tuple[chess.Square, chess.Piece]] = []
    for square in board.attacks(attacker_square):
        target = board.piece_at(square)
        if (
            target is None
            or target.color == attacker_color
            or target.piece_type not in VALUABLE_ATTACK_TARGETS
        ):
            continue
        targets.append((square, target))
    return sorted(
        targets,
        key=lambda item: (
            -PIECE_VALUES[item[1].piece_type],
            _piece_name(item[1].piece_type),
            item[0],
        ),
    )


def _same_type_fork_claims(
    targets: list[tuple[chess.Square, chess.Piece]],
    move_san: str,
    subject: ConceptClaimSubject,
) -> list[ConceptClaim]:
    claims: list[ConceptClaim] = []
    by_piece_type: dict[chess.PieceType, list[tuple[chess.Square, chess.Piece]]] = {}
    for target in targets:
        by_piece_type.setdefault(target[1].piece_type, []).append(target)
    for grouped_targets in by_piece_type.values():
        if len(grouped_targets) < 2:
            continue
        target_phrase = _attacked_targets_phrase(grouped_targets)
        claims.append(
            ConceptClaim(
                kind="piece_activity",
                subject=subject,
                claim=f"{move_san} attacked {target_phrase}",
                source="deterministic_detector",
                move_san=move_san,
            )
        )
        claims.append(
            ConceptClaim(
                kind="tactic",
                subject=subject,
                claim=f"{move_san} forked {target_phrase}",
                source="deterministic_detector",
                move_san=move_san,
            )
        )
    return claims


def _attacked_targets_phrase(targets: list[tuple[chess.Square, chess.Piece]]) -> str:
    target_descriptions = [_attacked_target_description(square, piece) for square, piece in targets]
    if len(targets) == 2 and targets[0][1].piece_type == targets[1][1].piece_type:
        piece_type = targets[0][1].piece_type
        return f"both {_piece_plural_name(piece_type)}: {_join_phrases(target_descriptions)}"
    return _join_phrases(target_descriptions)


def _attacked_target_description(square: chess.Square, piece: chess.Piece) -> str:
    return f"the {_piece_name(piece.piece_type)} on {chess.square_name(square)}"


def _join_phrases(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _opened_bishop_route_claims(
    board: chess.Board,
    after_board: chess.Board,
    piece: chess.Piece,
    move: chess.Move,
    move_san: str,
    subject: ConceptClaimSubject,
) -> list[ConceptClaim]:
    if after_board.piece_at(move.from_square) is not None:
        return []
    claims: list[ConceptClaim] = []
    for bishop_square, bishop in board.piece_map().items():
        if bishop_square == move.from_square:
            continue
        if bishop.color != piece.color or bishop.piece_type != chess.BISHOP:
            continue
        direction = _diagonal_direction(bishop_square, move.from_square)
        if direction is None:
            continue
        if _first_occupied_square_on_ray(board, bishop_square, direction) != move.from_square:
            continue
        route = _open_route_on_ray(after_board, bishop_square, direction)
        if not route or route[0] != move.from_square:
            continue
        claims.append(
            ConceptClaim(
                kind="development",
                subject=subject,
                claim=_opened_bishop_route_claim(move_san, bishop_square, route),
                source="deterministic_detector",
                move_san=move_san,
            )
        )
    return claims


def _diagonal_direction(
    from_square: chess.Square,
    to_square: chess.Square,
) -> tuple[int, int] | None:
    file_delta = chess.square_file(to_square) - chess.square_file(from_square)
    rank_delta = chess.square_rank(to_square) - chess.square_rank(from_square)
    if file_delta == 0 or abs(file_delta) != abs(rank_delta):
        return None
    return (_sign(file_delta), _sign(rank_delta))


def _first_occupied_square_on_ray(
    board: chess.Board,
    from_square: chess.Square,
    direction: tuple[int, int],
) -> chess.Square | None:
    for square in _ray_squares(from_square, direction):
        if board.piece_at(square) is not None:
            return square
    return None


def _open_route_on_ray(
    board: chess.Board,
    from_square: chess.Square,
    direction: tuple[int, int],
) -> list[chess.Square]:
    route: list[chess.Square] = []
    for square in _ray_squares(from_square, direction):
        if board.piece_at(square) is not None:
            break
        route.append(square)
    return route


def _ray_squares(
    from_square: chess.Square,
    direction: tuple[int, int],
) -> list[chess.Square]:
    file_index = chess.square_file(from_square) + direction[0]
    rank_index = chess.square_rank(from_square) + direction[1]
    squares: list[chess.Square] = []
    while 0 <= file_index <= 7 and 0 <= rank_index <= 7:
        squares.append(chess.square(file_index, rank_index))
        file_index += direction[0]
        rank_index += direction[1]
    return squares


def _opened_bishop_route_claim(
    move_san: str,
    bishop_square: chess.Square,
    route: list[chess.Square],
) -> str:
    bishop_location = chess.square_name(bishop_square)
    through_square = chess.square_name(route[0])
    if len(route) == 1:
        return f"{move_san} opened {through_square} for the bishop on {bishop_location}"
    targets = [chess.square_name(square) for square in route[1:3]]
    return (
        f"{move_san} opened a diagonal route for the bishop on {bishop_location} "
        f"through {through_square} toward {_join_phrases(targets)}"
    )


def _sign(value: int) -> int:
    return 1 if value > 0 else -1


def _material_claims(
    board: chess.Board,
    after_board: chess.Board,
    move: chess.Move,
    player: chess.Color,
    move_san: str,
    subject: ConceptClaimSubject,
    line_pv_uci: Sequence[str] | None,
) -> list[ConceptClaim]:
    delta = _material_balance(after_board, player) - _material_balance(board, player)
    if delta == 0:
        return []
    material_detail = _material_detail(board, move, delta)
    if delta > 0:
        claim = _positive_material_claim(
            board,
            after_board,
            move,
            player,
            move_san,
            material_detail,
            line_pv_uci,
        )
        if claim is None:
            return []
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


def _positive_material_claim(
    board: chess.Board,
    after_board: chess.Board,
    move: chess.Move,
    player: chess.Color,
    move_san: str,
    material_detail: str,
    line_pv_uci: Sequence[str] | None,
) -> str | None:
    exchange_claim = _immediate_reply_exchange_claim(
        board,
        after_board,
        move,
        player,
        move_san,
        line_pv_uci,
    )
    previous = previous_move_details(board)
    before_previous = board_before_previous_move(board)
    if previous is None or before_previous is None or not previous.was_capture:
        if exchange_claim is not None:
            return exchange_claim
        return f"{move_san} won {material_detail} immediately"

    sequence_delta = _material_balance(after_board, player) - _material_balance(
        before_previous,
        player,
    )
    if _is_same_square_recapture(board, move):
        if sequence_delta == 0:
            return (
                f"{move_san} restored the material balance by recapturing "
                f"{_recapture_material_detail(board, move)}"
            )
        if sequence_delta > 0:
            if exchange_claim is not None:
                return exchange_claim
            return f"{move_san} won {_material_value_name(sequence_delta)} in the exchange"
        return None

    if sequence_delta <= 0:
        return None
    if exchange_claim is not None:
        return exchange_claim
    return f"{move_san} won {_material_value_name(sequence_delta)} in the sequence"


def _immediate_reply_exchange_claim(
    board: chess.Board,
    after_board: chess.Board,
    move: chess.Move,
    player: chess.Color,
    move_san: str,
    line_pv_uci: Sequence[str] | None,
) -> str | None:
    captured_piece = _captured_piece(board, move)
    moving_piece = board.piece_at(move.from_square)
    if captured_piece is None or moving_piece is None or move.promotion is not None:
        return None
    reply = _verified_immediate_recapture(after_board, move, line_pv_uci)
    if reply is None:
        return None
    reply_board = after_board.copy(stack=False)
    reply_board.push(reply)
    sequence_delta = _material_balance(reply_board, player) - _material_balance(board, player)
    if sequence_delta > 0:
        return None
    return (
        f"{move_san} traded {_piece_with_article(moving_piece.piece_type)} "
        f"for {_piece_with_article(captured_piece.piece_type)}"
    )


def _verified_immediate_recapture(
    after_board: chess.Board,
    move: chess.Move,
    line_pv_uci: Sequence[str] | None,
) -> chess.Move | None:
    if line_pv_uci is None or len(line_pv_uci) < 2 or line_pv_uci[0] != move.uci():
        return None
    try:
        reply = chess.Move.from_uci(line_pv_uci[1])
    except ValueError:
        return None
    if reply not in after_board.legal_moves or not after_board.is_capture(reply):
        return None
    if reply.to_square != move.to_square:
        return None
    captured_by_reply = _captured_piece(after_board, reply)
    moved_piece = after_board.piece_at(move.to_square)
    if captured_by_reply is None or moved_piece is None:
        return None
    if (
        captured_by_reply.color != moved_piece.color
        or captured_by_reply.piece_type != moved_piece.piece_type
    ):
        return None
    return reply


def _recapture_claims(
    board: chess.Board,
    move: chess.Move,
    move_san: str,
    subject: ConceptClaimSubject,
) -> list[ConceptClaim]:
    if not _is_same_square_recapture(board, move):
        return []
    return [
        ConceptClaim(
            kind="recapture",
            subject=subject,
            claim=f"{move_san} recaptured {_recapture_material_detail(board, move)}",
            source="deterministic_detector",
            move_san=move_san,
        )
    ]


def _is_same_square_recapture(board: chess.Board, move: chess.Move) -> bool:
    if not board.is_capture(move):
        return False
    previous = previous_move_details(board)
    if previous is None or not previous.was_capture:
        return False
    try:
        previous_move = chess.Move.from_uci(previous.uci)
    except ValueError:
        return False
    return move.to_square == previous_move.to_square


def _recapture_material_detail(board: chess.Board, move: chess.Move) -> str:
    captured_piece = _captured_piece(board, move)
    square_name = chess.square_name(move.to_square)
    if captured_piece is None:
        return f"on {square_name}"
    return f"the {_piece_name(captured_piece.piece_type)} on {square_name}"


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


def _piece_plural_name(piece_type: chess.PieceType) -> str:
    return f"{_piece_name(piece_type)}s"


def _piece_with_article(piece_type: chess.PieceType) -> str:
    return f"{_piece_article(piece_type)} {_piece_name(piece_type)}"


def _piece_article(piece_type: chess.PieceType) -> str:
    return "an" if _piece_name(piece_type)[0] in {"a", "e", "i", "o", "u"} else "a"


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
