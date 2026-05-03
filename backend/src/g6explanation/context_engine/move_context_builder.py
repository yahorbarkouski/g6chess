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
        quality = classify_quality(
            analysis,
            reconstructed.played,
            legal_move_count=len(reconstructed.position.legal_moves_uci),
        )
        significance = calculate_significance(analysis, reconstructed.played)
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
        evidence = EvidencePacket(
            context_version="move_context.v1",
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
