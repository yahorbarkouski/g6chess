"""Context-engine evidence and LLM-context builder."""

from __future__ import annotations

import chess

from g6explanation.context_engine.candidate_moves import (
    build_candidates,
    choose_key_candidate,
    choose_practical_alternative,
    engine_best_candidate,
    played_candidate,
    time_situation,
)
from g6explanation.context_engine.contracts import (
    CandidateMove,
    ColorName,
    ContextResult,
    EngineAnalysis,
    EngineLine,
    EvidencePacket,
    HumanMoveLikelihood,
    LLMContext,
    MoveContextRequest,
    MoveQuality,
    VerificationResult,
)
from g6explanation.context_engine.evidence_verification import EvidenceVerifier
from g6explanation.context_engine.exceptions import AnalysisError
from g6explanation.context_engine.explanation_agenda import (
    build_allowed_claims,
    build_concept_claims,
    build_human_note,
    build_key_move_context,
    build_main_point,
)
from g6explanation.context_engine.position_reconstruction import reconstruct_move_context
from g6explanation.context_engine.provider_protocols import (
    EngineAnalysisProvider,
    HumanMoveLikelihoodProvider,
    RootMoveAnalysisProvider,
)
from g6explanation.context_engine.signals import (
    calculate_beauty,
    calculate_significance,
    classify_quality,
)
from g6explanation.context_engine.signals.coach_diagnostics import build_move_diagnostic_tags

MOVE_CONTEXT_VERSION = "move_context.v4"
NON_BAD_QUALITY_LABELS = {"best", "forced", "excellent", "good", "neutral"}
TACTICAL_REPLY_TOLERANCE_CP = 75
VALUABLE_ATTACK_TARGETS = {chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN}
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}


class MoveContextBuilder:
    """Build evidence and LLM context for one move explanation."""

    def __init__(
        self,
        analysis_provider: EngineAnalysisProvider,
        human_likelihood_provider: HumanMoveLikelihoodProvider | None = None,
        human_candidate_limit: int = 3,
        evidence_verifier: EvidenceVerifier | None = None,
    ) -> None:
        self._analysis_provider = analysis_provider
        self._human_likelihood_provider = human_likelihood_provider
        self._human_candidate_limit = human_candidate_limit
        self._evidence_verifier = evidence_verifier or EvidenceVerifier()

    def build(self, request: MoveContextRequest) -> ContextResult:
        board, move, reconstructed = reconstruct_move_context(request)
        analysis = self._analysis_provider.analyze(board, move, request.player_color)
        _raise_verification_failure(
            self._evidence_verifier.verify_engine_analysis(board, move, analysis)
        )
        quality = classify_quality(
            analysis,
            reconstructed.played,
            legal_move_count=len(reconstructed.position.legal_moves_uci),
        )
        significance = calculate_significance(analysis, reconstructed.played)
        supplemental_reply_lines = self._supplemental_opponent_reply_lines(
            board=board,
            played_move=move,
            analysis=analysis,
            player_color=request.player_color,
            quality=quality,
            significance_label=significance.label,
        )
        if supplemental_reply_lines:
            analysis = analysis.model_copy(
                update={
                    "opponent_reply_lines": [
                        *analysis.opponent_reply_lines,
                        *supplemental_reply_lines,
                    ]
                }
            )
        candidate_moves = _candidate_moves_from_analysis(
            board, analysis_move_uci=[line.move_uci for line in analysis.top_lines]
        )
        if analysis.played_line.move_uci not in {candidate.uci() for candidate in candidate_moves}:
            candidate_moves.append(chess.Move.from_uci(analysis.played_line.move_uci))

        human_likelihoods: dict[str, HumanMoveLikelihood] = {}
        if self._human_likelihood_provider is not None:
            human_likelihoods = self._human_likelihood_provider.likelihoods(
                board, candidate_moves, request
            )
        supplemental_lines = self._supplemental_human_lines(
            board=board,
            analysis=analysis,
            human_likelihoods=human_likelihoods,
            player_color=request.player_color,
        )

        situation = time_situation(request)
        beauty = calculate_beauty(
            board=board,
            analysis=analysis,
            played=reconstructed.played,
            quality=quality,
            significance=significance,
            human_likelihoods=human_likelihoods,
        )
        candidates = build_candidates(
            board=board,
            analysis=analysis,
            human_likelihoods=human_likelihoods,
            request=request,
            time_situation=situation,
            supplemental_lines=supplemental_lines,
        )
        engine_best = engine_best_candidate(candidates)
        practical_alternative = choose_practical_alternative(candidates)
        key_candidate = choose_key_candidate(candidates, quality)
        featured_candidate = _featured_candidate(
            candidates=candidates,
            quality=quality,
            significance_label=significance.label,
            key_candidate=key_candidate,
        )
        main_point = build_main_point(
            board,
            reconstructed.played,
            quality,
            key_candidate,
            featured_candidate,
            analysis,
        )
        allowed_claims = build_allowed_claims(
            board,
            reconstructed.played,
            quality,
            key_candidate,
            featured_candidate,
            analysis,
        )
        concept_claims = build_concept_claims(
            board,
            reconstructed.played,
            quality,
            key_candidate,
            featured_candidate,
            engine_best,
            practical_alternative,
            analysis,
        )
        diagnostic_tags = build_move_diagnostic_tags(
            board=board,
            request=request,
            played=reconstructed.played,
            analysis=analysis,
            quality=quality,
            significance=significance,
            candidates=candidates,
            concept_claims=concept_claims,
            time_situation=situation,
        )
        evidence = EvidencePacket(
            context_version=MOVE_CONTEXT_VERSION,
            request=request,
            position=reconstructed.position,
            played=reconstructed.played,
            engine=analysis,
            quality=quality,
            significance=significance,
            beauty=beauty,
            candidates=candidates,
            main_point=main_point,
            concept_claims=concept_claims,
            allowed_claims=allowed_claims,
            diagnostic_tags=diagnostic_tags,
        )
        llm_context = LLMContext(
            played=reconstructed.played.san,
            quality=quality.label,
            significance=significance,
            beauty=beauty,
            player_level=request.player_level.label(),
            time_situation=situation,
            severity=quality.severity_text,
            main_point=main_point.claim,
            best_or_key_move=build_key_move_context(key_candidate),
            engine_best_move=build_key_move_context(engine_best),
            practical_alternative=build_key_move_context(practical_alternative),
            featured_move=build_key_move_context(featured_candidate),
            human_note=build_human_note(key_candidate, situation),
            concept_claims=concept_claims,
            allowed_claims=allowed_claims,
            diagnostic_tags=diagnostic_tags,
        )
        verification = self._evidence_verifier.verify(evidence, llm_context)
        _raise_verification_failure(verification)
        return ContextResult(evidence=evidence, llm_context=llm_context, verification=verification)

    def _supplemental_human_lines(
        self,
        board: chess.Board,
        analysis: EngineAnalysis,
        human_likelihoods: dict[str, HumanMoveLikelihood],
        player_color: ColorName,
    ) -> list[EngineLine]:
        if not isinstance(self._analysis_provider, RootMoveAnalysisProvider):
            return []
        existing_uci = {
            *[line.move_uci for line in analysis.top_lines],
            analysis.played_line.move_uci,
        }
        ranked_extra_moves: list[chess.Move] = []
        for uci, likelihood in sorted(
            human_likelihoods.items(),
            key=lambda item: (
                item[1].rank is None,
                item[1].rank or 999,
            ),
        ):
            if uci in existing_uci or not likelihood.is_top_human_move:
                continue
            move = chess.Move.from_uci(uci)
            if move in board.legal_moves:
                ranked_extra_moves.append(move)
            if len(ranked_extra_moves) >= self._human_candidate_limit:
                break
        if not ranked_extra_moves:
            return []
        lines = self._analysis_provider.analyze_root_moves(board, ranked_extra_moves, player_color)
        for line in lines:
            _validate_line_pv(board, line)
        return lines

    def _supplemental_opponent_reply_lines(
        self,
        board: chess.Board,
        played_move: chess.Move,
        analysis: EngineAnalysis,
        player_color: ColorName,
        quality: MoveQuality,
        significance_label: str,
    ) -> list[EngineLine]:
        if not isinstance(self._analysis_provider, RootMoveAnalysisProvider):
            return []
        if quality.label not in NON_BAD_QUALITY_LABELS or significance_label not in {
            "high",
            "critical",
        }:
            return []
        if not _moved_piece_attacks_valuable_target(board, played_move):
            return []

        after_board = board.copy(stack=False)
        after_board.push(played_move)
        existing = {line.move_uci for line in analysis.opponent_reply_lines}
        capture_moves = [
            move
            for move in _captures_moved_piece(after_board, played_move)
            if move.uci() not in existing
        ]
        if not capture_moves:
            return []

        lines = self._analysis_provider.analyze_root_moves(
            after_board,
            capture_moves[:2],
            player_color,
        )
        filtered_lines: list[EngineLine] = []
        for line in lines:
            _validate_line_pv(after_board, line)
            if _reply_line_preserves_player_value(line, analysis.played_line):
                filtered_lines.append(line)
        return filtered_lines


def _raise_verification_failure(verification: VerificationResult) -> None:
    if verification.passed:
        return
    first_failure = verification.failures[0]
    raise AnalysisError(
        f"Evidence verification failed: {first_failure.code}: {first_failure.message}"
    )


def _candidate_moves_from_analysis(
    board: chess.Board, analysis_move_uci: list[str]
) -> list[chess.Move]:
    moves: list[chess.Move] = []
    for uci in analysis_move_uci:
        move = chess.Move.from_uci(uci)
        if move in board.legal_moves:
            moves.append(move)
    return moves


def _featured_candidate(
    candidates: list[CandidateMove],
    quality: MoveQuality,
    significance_label: str,
    key_candidate: CandidateMove | None,
) -> CandidateMove | None:
    if key_candidate is not None:
        return key_candidate
    if quality.label == "forced":
        return played_candidate(candidates)
    played = played_candidate(candidates)
    if quality.label == "best" and played is not None and played.forcing_tier == "mate":
        return played
    if quality.label == "best" and significance_label in {"high", "critical"}:
        return played
    return None


def _moved_piece_attacks_valuable_target(board: chess.Board, played_move: chess.Move) -> bool:
    piece = board.piece_at(played_move.from_square)
    if piece is None:
        return False
    after_board = board.copy(stack=False)
    after_board.push(played_move)
    for square in after_board.attacks(played_move.to_square):
        target = after_board.piece_at(square)
        if (
            target is not None
            and target.color != piece.color
            and target.piece_type in VALUABLE_ATTACK_TARGETS
        ):
            return True
    return False


def _captures_moved_piece(after_board: chess.Board, played_move: chess.Move) -> list[chess.Move]:
    captures = [
        move
        for move in after_board.legal_moves
        if after_board.is_capture(move) and move.to_square == played_move.to_square
    ]
    return sorted(
        captures,
        key=lambda move: (
            _piece_value(after_board.piece_at(move.from_square)),
            move.uci(),
        ),
    )


def _piece_value(piece: chess.Piece | None) -> int:
    if piece is None:
        return 0
    return PIECE_VALUES.get(piece.piece_type, 0)


def _reply_line_preserves_player_value(line: EngineLine, reference_line: EngineLine) -> bool:
    score = line.score
    reference_score = reference_line.score
    if reference_score.kind == "mate":
        return (
            reference_score.mate_for == "player"
            and score.kind == "mate"
            and score.mate_for == "player"
        )
    if score.kind == "mate":
        return score.mate_for == "player"
    if score.value is None or reference_score.value is None:
        return False
    return score.value >= reference_score.value - TACTICAL_REPLY_TOLERANCE_CP


def _validate_line_pv(board: chess.Board, line: EngineLine) -> None:
    if not line.pv_uci:
        return
    if line.pv_uci[0] != line.move_uci:
        raise AnalysisError(
            f"Engine line move {line.move_uci} does not match PV root {line.pv_uci[0]}."
        )
    replay = board.copy(stack=False)
    for uci in line.pv_uci:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise AnalysisError(f"PV move {uci} is not valid UCI.") from exc
        if move not in replay.legal_moves:
            raise AnalysisError(f"PV move {uci} is illegal when replayed.")
        replay.push(move)
