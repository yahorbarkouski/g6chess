"""Deterministic evidence verification for context-engine packets."""

from __future__ import annotations

from dataclasses import dataclass, field

import chess

from g6explanation.context_engine.candidate_moves.findability import forcing_tier, time_situation
from g6explanation.context_engine.contracts import (
    CandidateMove,
    CandidateRole,
    ConceptClaim,
    EngineAnalysis,
    EngineLine,
    EvidencePacket,
    KeyMoveContext,
    LLMContext,
    MoveDiagnosticTag,
    PracticalityCategory,
    VerificationIssue,
    VerificationIssueCode,
    VerificationResult,
)
from g6explanation.context_engine.explanation_agenda import build_human_note
from g6explanation.context_engine.position_reconstruction import color_name
from g6explanation.context_engine.stockfish_analysis import MIN_STOCKFISH_DEPTH

VERIFIER_VERSION = "evidence_verifier.v1"
HARD_FINDABILITY = {"hard", "very_hard", "engine_like"}


class EvidenceVerifier:
    """Verify that evidence and compact LLM context stay inside chess facts."""

    def verify(
        self, evidence: EvidencePacket, llm_context: LLMContext | None = None
    ) -> VerificationResult:
        issues = _IssueCollector()
        board = _board_from_fen(evidence.position.fen_before, "$.position.fen_before", issues)
        _verify_request_fen(evidence, board, issues)
        _verify_fen_after(evidence, issues)

        played_move: chess.Move | None = None
        if board is not None:
            played_move = _verify_played_position(evidence, board, issues)
            _verify_candidates(evidence, board, issues)
            if played_move is not None:
                _verify_engine_analysis(
                    board=board,
                    played_move=played_move,
                    analysis=evidence.engine,
                    issues=issues,
                    path="$.engine",
                )

        if llm_context is not None:
            _verify_llm_context(evidence, llm_context, issues)

        return issues.result()

    def verify_engine_analysis(
        self,
        board: chess.Board,
        played_move: chess.Move,
        analysis: EngineAnalysis,
    ) -> VerificationResult:
        issues = _IssueCollector()
        _verify_engine_analysis(
            board=board,
            played_move=played_move,
            analysis=analysis,
            issues=issues,
            path="$.engine",
        )
        return issues.result()


@dataclass
class _IssueCollector:
    failures: list[VerificationIssue] = field(default_factory=list[VerificationIssue])
    warnings: list[VerificationIssue] = field(default_factory=list[VerificationIssue])

    def fail(self, code: VerificationIssueCode, path: str, message: str) -> None:
        self.failures.append(VerificationIssue(code=code, path=path, message=message))

    def warn(self, code: VerificationIssueCode, path: str, message: str) -> None:
        self.warnings.append(VerificationIssue(code=code, path=path, message=message))

    def result(self) -> VerificationResult:
        return VerificationResult(
            verifier_version=VERIFIER_VERSION,
            passed=not self.failures,
            failures=self.failures,
            warnings=self.warnings,
        )


def _board_from_fen(
    fen: str,
    path: str,
    issues: _IssueCollector,
    issue_code: VerificationIssueCode = "fen_before_invalid",
) -> chess.Board | None:
    try:
        return chess.Board(fen)
    except ValueError as exc:
        issues.fail(issue_code, path, f"FEN is invalid: {exc}.")
        return None


def _verify_request_fen(
    evidence: EvidencePacket,
    board: chess.Board | None,
    issues: _IssueCollector,
) -> None:
    if evidence.request.fen_before is None or board is None:
        return
    request_board = _board_from_fen(
        evidence.request.fen_before,
        "$.request.fen_before",
        issues,
        issue_code="fen_before_invalid",
    )
    if request_board is not None and request_board.fen() != board.fen():
        issues.fail(
            "request_fen_mismatch",
            "$.request.fen_before",
            "Request FEN does not match evidence position FEN.",
        )


def _verify_fen_after(evidence: EvidencePacket, issues: _IssueCollector) -> None:
    _board_from_fen(
        evidence.position.fen_after,
        "$.position.fen_after",
        issues,
        issue_code="fen_after_invalid",
    )


def _verify_played_position(
    evidence: EvidencePacket,
    board: chess.Board,
    issues: _IssueCollector,
) -> chess.Move | None:
    if color_name(board.turn) != evidence.position.side_to_move:
        issues.fail(
            "side_to_move_mismatch",
            "$.position.side_to_move",
            (
                f"Evidence side to move {evidence.position.side_to_move} "
                f"does not match FEN side to move {color_name(board.turn)}."
            ),
        )
    if color_name(board.turn) != evidence.request.player_color:
        issues.fail(
            "side_to_move_mismatch",
            "$.request.player_color",
            (
                f"Request player color {evidence.request.player_color} "
                f"does not match FEN side to move {color_name(board.turn)}."
            ),
        )
    if evidence.position.move_number != board.fullmove_number:
        issues.fail(
            "played_move_fact_mismatch",
            "$.position.move_number",
            "Position move number does not match FEN.",
        )
    if evidence.position.ply != board.ply():
        issues.fail(
            "played_move_fact_mismatch",
            "$.position.ply",
            "Position ply does not match FEN.",
        )

    legal_uci = {move.uci() for move in board.legal_moves}
    if set(evidence.position.legal_moves_uci) != legal_uci:
        issues.fail(
            "legal_moves_mismatch",
            "$.position.legal_moves_uci",
            "Recorded legal move set does not match FEN legal moves.",
        )

    try:
        move = chess.Move.from_uci(evidence.played.uci)
    except ValueError:
        issues.fail(
            "played_move_invalid_uci",
            "$.played.uci",
            f"Played move {evidence.played.uci!r} is not valid UCI.",
        )
        return None

    if move not in board.legal_moves:
        issues.fail(
            "played_move_illegal",
            "$.played.uci",
            f"Played move {move.uci()} is illegal in the evidence position.",
        )
        return None

    expected_san = board.san(move)
    expected_check = board.gives_check(move)
    expected_capture = board.is_capture(move)
    expected_promotion = chess.piece_symbol(move.promotion).upper() if move.promotion else None
    if not evidence.played.legal:
        issues.fail("played_move_fact_mismatch", "$.played.legal", "Played move is marked illegal.")
    if evidence.played.san != expected_san:
        issues.fail(
            "played_move_fact_mismatch",
            "$.played.san",
            f"Played SAN {evidence.played.san!r} does not match {expected_san!r}.",
        )
    if evidence.played.is_check != expected_check:
        issues.fail(
            "played_move_fact_mismatch",
            "$.played.is_check",
            "Played check flag does not match board replay.",
        )
    if evidence.played.is_capture != expected_capture:
        issues.fail(
            "played_move_fact_mismatch",
            "$.played.is_capture",
            "Played capture flag does not match board replay.",
        )
    if evidence.played.promotion != expected_promotion:
        issues.fail(
            "played_move_fact_mismatch",
            "$.played.promotion",
            "Played promotion field does not match UCI move.",
        )

    after_board = board.copy(stack=False)
    after_board.push(move)
    if evidence.played.is_checkmate != after_board.is_checkmate():
        issues.fail(
            "played_move_fact_mismatch",
            "$.played.is_checkmate",
            "Played checkmate flag does not match board replay.",
        )
    if after_board.fen() != evidence.position.fen_after:
        issues.fail(
            "fen_after_mismatch",
            "$.position.fen_after",
            "Evidence fen_after does not match applying the played move.",
        )
    return move


def _verify_engine_analysis(
    board: chess.Board,
    played_move: chess.Move,
    analysis: EngineAnalysis,
    issues: _IssueCollector,
    path: str,
) -> None:
    if not analysis.top_lines:
        issues.fail("engine_top_lines_empty", f"{path}.top_lines", "Engine top lines are empty.")
        return

    if analysis.played_line.move_uci != played_move.uci():
        issues.fail(
            "engine_played_line_mismatch",
            f"{path}.played_line.move_uci",
            (
                f"Played line {analysis.played_line.move_uci} does not match "
                f"requested move {played_move.uci()}."
            ),
        )

    is_static = analysis.analysis_budget.kind == "static"
    _verify_engine_metadata(analysis, issues, path, is_static)
    wdl_requested = analysis.engine_options.get("UCI_ShowWDL") is True
    minimum_depth = None if is_static else MIN_STOCKFISH_DEPTH

    for index, line in enumerate(analysis.top_lines):
        line_path = f"{path}.top_lines[{index}]"
        _verify_engine_line(
            board=board,
            line=line,
            path=line_path,
            issues=issues,
            require_metadata=not is_static,
            require_pv=not is_static,
            require_wdl=wdl_requested,
            minimum_depth=minimum_depth,
        )

    _verify_engine_line(
        board=board,
        line=analysis.played_line,
        path=f"{path}.played_line",
        issues=issues,
        require_metadata=not is_static,
        require_pv=not is_static,
        require_wdl=wdl_requested,
        minimum_depth=minimum_depth,
    )

    after_board = board.copy(stack=False)
    after_board.push(played_move)
    if after_board.is_game_over():
        if analysis.after_line is not None:
            issues.fail(
                "engine_after_line_unexpected",
                f"{path}.after_line",
                "Engine after_line is present even though the played move ends the game.",
            )
        return

    if analysis.after_line is None:
        if is_static:
            issues.warn(
                "engine_after_line_missing",
                f"{path}.after_line",
                "Static engine analysis has no after-move reply.",
            )
        else:
            issues.fail(
                "engine_after_line_missing",
                f"{path}.after_line",
                "Engine analysis must include an after-move reply when the game continues.",
            )
        return

    _verify_engine_line(
        board=after_board,
        line=analysis.after_line,
        path=f"{path}.after_line",
        issues=issues,
        require_metadata=not is_static,
        require_pv=not is_static,
        require_wdl=wdl_requested,
        minimum_depth=minimum_depth,
    )


def _verify_engine_metadata(
    analysis: EngineAnalysis,
    issues: _IssueCollector,
    path: str,
    is_static: bool,
) -> None:
    if not analysis.engine_version.strip():
        issues.fail(
            "engine_metadata_missing",
            f"{path}.engine_version",
            "Engine version is missing.",
        )
    if analysis.analysis_budget.value is None:
        issues.fail(
            "engine_metadata_missing",
            f"{path}.analysis_budget.value",
            "Engine analysis budget value is missing.",
        )
    if (
        not is_static
        and analysis.analysis_budget.kind == "depth"
        and analysis.analysis_budget.value is not None
    ):
        if not isinstance(analysis.analysis_budget.value, int):
            issues.fail(
                "engine_metadata_missing",
                f"{path}.analysis_budget.value",
                "Depth analysis budget value must be an integer.",
            )
        elif analysis.analysis_budget.value < MIN_STOCKFISH_DEPTH:
            issues.fail(
                "engine_depth_below_minimum",
                f"{path}.analysis_budget.value",
                (f"Depth-limited engine analysis must use at least {MIN_STOCKFISH_DEPTH} plies."),
            )
    if not is_static and analysis.analysis_budget.multipv is None:
        issues.fail(
            "engine_metadata_missing",
            f"{path}.analysis_budget.multipv",
            "Engine MultiPV budget is missing.",
        )


def _verify_engine_line(
    board: chess.Board,
    line: EngineLine,
    path: str,
    issues: _IssueCollector,
    require_metadata: bool,
    require_pv: bool,
    require_wdl: bool,
    minimum_depth: int | None,
) -> None:
    try:
        move = chess.Move.from_uci(line.move_uci)
    except ValueError:
        issues.fail(
            "engine_line_invalid_uci",
            f"{path}.move_uci",
            f"Engine line move {line.move_uci!r} is not valid UCI.",
        )
        return

    if move not in board.legal_moves:
        issues.fail(
            "engine_line_illegal",
            f"{path}.move_uci",
            f"Engine line move {line.move_uci} is illegal in its analyzed position.",
        )
        return

    expected_san = board.san(move)
    if line.move_san != expected_san:
        issues.fail(
            "engine_line_san_mismatch",
            f"{path}.move_san",
            f"Engine SAN {line.move_san!r} does not match {expected_san!r}.",
        )
    if require_metadata and line.depth is None and line.nodes is None:
        issues.fail(
            "engine_metadata_missing",
            path,
            "Engine line is missing both depth and nodes metadata.",
        )
    if minimum_depth is not None:
        if line.depth is None:
            issues.fail(
                "engine_depth_below_minimum",
                f"{path}.depth",
                "Real engine-backed lines must include depth metadata.",
            )
        elif line.depth < minimum_depth:
            issues.fail(
                "engine_depth_below_minimum",
                f"{path}.depth",
                f"Engine line depth must be at least {minimum_depth} plies.",
            )
    if require_wdl and line.wdl is None:
        issues.fail(
            "engine_wdl_missing",
            f"{path}.wdl",
            "WDL is missing even though UCI_ShowWDL was requested.",
        )
    _verify_engine_pv(board, line, path, issues, require_pv)


def _verify_engine_pv(
    board: chess.Board,
    line: EngineLine,
    path: str,
    issues: _IssueCollector,
    require_pv: bool,
) -> None:
    if not line.pv_uci:
        if require_pv:
            issues.fail(
                "engine_pv_missing",
                f"{path}.pv_uci",
                "Engine line is missing a principal variation.",
            )
        return

    if line.pv_uci[0] != line.move_uci:
        issues.fail(
            "engine_pv_root_mismatch",
            f"{path}.pv_uci[0]",
            f"Engine line move {line.move_uci} does not match PV root {line.pv_uci[0]}.",
        )

    replay = board.copy(stack=False)
    pv_san: list[str] = []
    for index, uci in enumerate(line.pv_uci):
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            issues.fail(
                "engine_pv_invalid_uci",
                f"{path}.pv_uci[{index}]",
                f"PV move {uci!r} is not valid UCI.",
            )
            return
        if move not in replay.legal_moves:
            issues.fail(
                "engine_pv_illegal",
                f"{path}.pv_uci[{index}]",
                f"PV move {uci} is illegal when replayed.",
            )
            return
        pv_san.append(replay.san(move))
        replay.push(move)

    if line.pv_san and line.pv_san != pv_san:
        issues.fail(
            "engine_pv_san_mismatch",
            f"{path}.pv_san",
            "Engine PV SAN does not match replayed PV moves.",
        )
    if require_pv and not line.pv_san:
        issues.fail(
            "engine_pv_san_mismatch",
            f"{path}.pv_san",
            "Engine line is missing PV SAN.",
        )


def _verify_candidates(
    evidence: EvidencePacket,
    board: chess.Board,
    issues: _IssueCollector,
) -> None:
    seen: set[str] = set()
    has_played = False
    has_engine_best = False
    engine_best_uci = evidence.engine.top_lines[0].move_uci if evidence.engine.top_lines else None

    for index, candidate in enumerate(evidence.candidates):
        path = f"$.candidates[{index}]"
        if candidate.uci in seen:
            issues.fail("candidate_duplicate", f"{path}.uci", "Candidate move is duplicated.")
        seen.add(candidate.uci)
        if "played_move" in candidate.roles:
            has_played = has_played or candidate.uci == evidence.played.uci
        if "engine_best" in candidate.roles:
            has_engine_best = has_engine_best or candidate.uci == engine_best_uci
        _verify_candidate(
            candidate,
            board,
            evidence.position.previous_move_uci,
            evidence.position.previous_move_was_capture,
            issues,
            path,
        )

    if evidence.candidates and not has_played:
        issues.fail(
            "candidate_missing_played_move",
            "$.candidates",
            "No candidate is marked as the played move.",
        )
    if evidence.candidates and not has_engine_best:
        issues.fail(
            "candidate_missing_engine_best",
            "$.candidates",
            "No candidate is marked as the engine best move.",
        )


def _verify_candidate(
    candidate: CandidateMove,
    board: chess.Board,
    previous_move_uci: str | None,
    previous_move_was_capture: bool | None,
    issues: _IssueCollector,
    path: str,
) -> None:
    if not candidate.roles:
        issues.fail("candidate_missing_role", f"{path}.roles", "Candidate has no source role.")
    try:
        move = chess.Move.from_uci(candidate.uci)
    except ValueError:
        issues.fail(
            "candidate_illegal",
            f"{path}.uci",
            f"Candidate move {candidate.uci!r} is not valid UCI.",
        )
        return
    if move not in board.legal_moves:
        issues.fail(
            "candidate_illegal",
            f"{path}.uci",
            f"Candidate move {candidate.uci} is illegal in the evidence position.",
        )
        return
    expected_san = board.san(move)
    if candidate.san != expected_san:
        issues.fail(
            "candidate_san_mismatch",
            f"{path}.san",
            f"Candidate SAN {candidate.san!r} does not match {expected_san!r}.",
        )
    expected_forcing_tier = forcing_tier(
        board,
        move,
        previous_move_uci,
        previous_move_was_capture=previous_move_was_capture,
    )
    if candidate.forcing_tier != expected_forcing_tier:
        issues.fail(
            "candidate_forcing_tier_mismatch",
            f"{path}.forcing_tier",
            f"Candidate forcing tier {candidate.forcing_tier!r} does not match "
            f"{expected_forcing_tier!r}.",
        )
    if (
        candidate.recommendation_policy == "recommend_directly"
        and candidate.time_adjusted_findability in HARD_FINDABILITY
        and not _is_player_mate(candidate)
    ):
        issues.fail(
            "candidate_hard_direct_recommendation",
            f"{path}.recommendation_policy",
            "Hard-to-find candidate is recommended directly.",
        )
    if (
        candidate.recommendation_policy == "use_as_practical_alternative"
        and candidate.practicality != "practical_try"
    ):
        issues.fail(
            "candidate_policy_inconsistent",
            f"{path}.recommendation_policy",
            "Practical-alternative policy requires practical_try practicality.",
        )
    if (
        candidate.recommendation_policy == "explain_as_hidden_resource"
        and candidate.practicality != "hard_but_important"
    ):
        issues.fail(
            "candidate_policy_inconsistent",
            f"{path}.recommendation_policy",
            "Hidden-resource policy requires hard_but_important practicality.",
        )


def _is_player_mate(candidate: CandidateMove) -> bool:
    return candidate.score.kind == "mate" and candidate.score.mate_for == "player"


def _verify_llm_context(
    evidence: EvidencePacket,
    llm_context: LLMContext,
    issues: _IssueCollector,
) -> None:
    expected_time_situation = time_situation(evidence.request)
    _fail_if_mismatch(
        llm_context.played,
        evidence.played.san,
        "$.llm_context.played",
        "LLM context played move does not match evidence.",
        issues,
    )
    _fail_if_mismatch(
        llm_context.quality,
        evidence.quality.label,
        "$.llm_context.quality",
        "LLM context quality does not match evidence.",
        issues,
    )
    _fail_if_mismatch(
        llm_context.significance,
        evidence.significance,
        "$.llm_context.significance",
        "LLM context significance does not match evidence.",
        issues,
    )
    _fail_if_mismatch(
        llm_context.beauty,
        evidence.beauty,
        "$.llm_context.beauty",
        "LLM context beauty does not match evidence.",
        issues,
    )
    _fail_if_mismatch(
        llm_context.severity,
        evidence.quality.severity_text,
        "$.llm_context.severity",
        "LLM context severity does not match evidence.",
        issues,
    )
    _fail_if_mismatch(
        llm_context.main_point,
        evidence.main_point.claim,
        "$.llm_context.main_point",
        "LLM context main point does not match evidence.",
        issues,
    )
    _fail_if_mismatch(
        llm_context.player_level,
        evidence.request.player_level.label(),
        "$.llm_context.player_level",
        "LLM context player level does not match request evidence.",
        issues,
    )
    _fail_if_mismatch(
        llm_context.time_situation,
        expected_time_situation,
        "$.llm_context.time_situation",
        "LLM context time situation does not match request evidence.",
        issues,
    )
    _fail_if_mismatch(
        llm_context.human_note,
        build_human_note(
            _matching_candidate_for_key_context(evidence, llm_context.best_or_key_move),
            expected_time_situation,
        ),
        "$.llm_context.human_note",
        "LLM context human note does not match deterministic candidate evidence.",
        issues,
    )

    unsupported_claims = [
        claim for claim in llm_context.allowed_claims if claim not in evidence.allowed_claims
    ]
    if unsupported_claims:
        issues.fail(
            "llm_context_claim_not_allowed",
            "$.llm_context.allowed_claims",
            f"LLM context includes unsupported claims: {unsupported_claims}.",
        )
    evidence_concept_claims = {_concept_claim_key(claim) for claim in evidence.concept_claims}
    llm_concept_claims = {_concept_claim_key(claim) for claim in llm_context.concept_claims}
    unsupported_concept_claims = [
        claim
        for claim in llm_context.concept_claims
        if _concept_claim_key(claim) not in evidence_concept_claims
    ]
    if unsupported_concept_claims:
        issues.fail(
            "llm_context_concept_claim_not_allowed",
            "$.llm_context.concept_claims",
            f"LLM context includes unsupported concept claims: {unsupported_concept_claims}.",
        )
    missing_concept_claims = [
        claim
        for claim in evidence.concept_claims
        if _concept_claim_key(claim) not in llm_concept_claims
    ]
    if missing_concept_claims:
        issues.fail(
            "llm_context_inconsistent",
            "$.llm_context.concept_claims",
            f"LLM context is missing evidence concept claims: {missing_concept_claims}.",
        )

    evidence_diagnostic_tags = {_diagnostic_tag_key(tag) for tag in evidence.diagnostic_tags}
    llm_diagnostic_tags = {_diagnostic_tag_key(tag) for tag in llm_context.diagnostic_tags}
    unsupported_diagnostic_tags = [
        tag
        for tag in llm_context.diagnostic_tags
        if _diagnostic_tag_key(tag) not in evidence_diagnostic_tags
    ]
    if unsupported_diagnostic_tags:
        issues.fail(
            "llm_context_inconsistent",
            "$.llm_context.diagnostic_tags",
            f"LLM context includes unsupported diagnostic tags: {unsupported_diagnostic_tags}.",
        )
    missing_diagnostic_tags = [
        tag
        for tag in evidence.diagnostic_tags
        if _diagnostic_tag_key(tag) not in llm_diagnostic_tags
    ]
    if missing_diagnostic_tags:
        issues.fail(
            "llm_context_inconsistent",
            "$.llm_context.diagnostic_tags",
            f"LLM context is missing evidence diagnostic tags: {missing_diagnostic_tags}.",
        )

    _verify_key_move_context(
        evidence=evidence,
        key_context=llm_context.best_or_key_move,
        path="$.llm_context.best_or_key_move",
        issues=issues,
    )
    _verify_key_move_context(
        evidence=evidence,
        key_context=llm_context.engine_best_move,
        path="$.llm_context.engine_best_move",
        issues=issues,
        required_role="engine_best",
    )
    _verify_key_move_context(
        evidence=evidence,
        key_context=llm_context.practical_alternative,
        path="$.llm_context.practical_alternative",
        issues=issues,
        required_practicality="practical_try",
    )
    _verify_key_move_context(
        evidence=evidence,
        key_context=llm_context.featured_move,
        path="$.llm_context.featured_move",
        issues=issues,
    )


def _verify_key_move_context(
    evidence: EvidencePacket,
    key_context: KeyMoveContext | None,
    path: str,
    issues: _IssueCollector,
    required_role: CandidateRole | None = None,
    required_practicality: PracticalityCategory | None = None,
) -> None:
    if key_context is None:
        return

    matching_candidate = _matching_candidate_for_key_context(evidence, key_context)
    if matching_candidate is None:
        issues.fail(
            "llm_context_inconsistent",
            f"{path}.move",
            "LLM move context does not match any evidence candidate.",
        )
        return

    if required_role is not None and required_role not in matching_candidate.roles:
        issues.fail(
            "llm_context_inconsistent",
            f"{path}.move",
            f"LLM move context must reference a candidate with role {required_role}.",
        )
    if (
        required_practicality is not None
        and matching_candidate.practicality != required_practicality
    ):
        issues.fail(
            "llm_context_inconsistent",
            f"{path}.practicality",
            f"LLM move context must reference {required_practicality} practicality.",
        )

    _fail_if_mismatch(
        key_context.practicality,
        matching_candidate.practicality,
        f"{path}.practicality",
        "LLM move-context practicality does not match candidate evidence.",
        issues,
    )
    _fail_if_mismatch(
        key_context.findability,
        matching_candidate.time_adjusted_findability,
        f"{path}.findability",
        "LLM move-context findability does not match candidate evidence.",
        issues,
    )
    _fail_if_mismatch(
        key_context.recommendation_policy,
        matching_candidate.recommendation_policy,
        f"{path}.recommendation_policy",
        "LLM move-context recommendation policy does not match candidate evidence.",
        issues,
    )


def _matching_candidate_for_key_context(
    evidence: EvidencePacket, key_context: KeyMoveContext | None
) -> CandidateMove | None:
    if key_context is None:
        return None
    return next(
        (candidate for candidate in evidence.candidates if candidate.san == key_context.move),
        None,
    )


def _concept_claim_key(claim: ConceptClaim) -> tuple[str, str, str, str, str | None]:
    return (claim.kind, claim.subject, claim.claim, claim.source, claim.move_san)


def _diagnostic_tag_key(tag: MoveDiagnosticTag) -> tuple[str, str, str, str]:
    return (tag.tag, tag.kind, tag.source, tag.claim)


def _fail_if_mismatch(
    actual: object,
    expected: object,
    path: str,
    message: str,
    issues: _IssueCollector,
) -> None:
    if actual != expected:
        issues.fail("llm_context_inconsistent", path, message)
