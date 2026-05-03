"""Deterministic verification for generated explanation text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from g6explanation.context_engine.contracts import (
    CandidateMove,
    ConceptClaim,
    ContextResult,
    KeyMoveContext,
)
from g6explanation.explanation_generation.contracts import (
    ExplanationOutput,
    ExplanationVerificationIssue,
    ExplanationVerificationIssueCode,
    ExplanationVerificationResult,
)

EXPLANATION_VERIFIER_VERSION = "explanation_verifier.v1"

SAN_MOVE_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:O-O(?:-O)?|[KQRBN](?:[a-h]|[1-8])?x?[a-h][1-8](?:=[QRBN])?|"
    r"[a-h](?:x[a-h])?[1-8](?:=[QRBN])?)"
    r"[+#]?"
    r"(?![A-Za-z0-9])"
)
UCI_MOVE_RE = re.compile(r"(?<![A-Za-z0-9])[a-h][1-8][a-h][1-8][qrbn]?(?![A-Za-z0-9])")
RAW_ENGINE_RE = re.compile(
    r"\b(?:stockfish|centipawns?|wdl|engine evaluation|eval(?:uation)? score)\b|"
    r"(?<![A-Za-z0-9])[+-]\d+(?:\.\d+)?(?![A-Za-z0-9])",
    re.IGNORECASE,
)
MATERIAL_RE = re.compile(
    r"\b(?:wins?|loses?|lost|drops?|dropped|hangs?|hung)\s+material\b|"
    r"\b(?:wins?|loses?|lost|drops?|dropped|hangs?|hung)\s+"
    r"(?:a\s+|the\s+)?(?:pawn|piece|queen|rook|bishop|knight|exchange)\b",
    re.IGNORECASE,
)
MATERIAL_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "pawn": ("pawn", "pawns"),
    "queen": ("queen", "queens"),
    "rook": ("rook", "rooks"),
    "bishop": ("bishop", "bishops"),
    "knight": ("knight", "knights"),
    "exchange": ("exchange",),
}
TACTIC_TERMS = {
    "fork",
    "pin",
    "skewer",
    "deflection",
    "decoy",
    "overload",
    "overloaded",
    "discovered attack",
    "zwischenzug",
    "intermezzo",
    "back rank",
}
CONCEPT_ALIASES_BY_KIND: dict[str, tuple[str, ...]] = {
    "forced_move": ("forced move", "only legal move", "no legal alternative"),
    "forcing_move": (
        "forcing move",
        "forcing check",
        "gave check",
        "with check",
        "checking move",
    ),
    "forced_mate": ("forced mate", "checkmate", "mate"),
    "critical_best_move": ("critical move", "critical best move"),
    "capture": ("captured", "capture"),
    "castling": ("castled", "castling", "castle"),
    "en_passant": ("en passant",),
    "promotion": ("promotion", "promoted", "promotes"),
    "practical_alternative": ("practical alternative", "practical try"),
    "better_alternative": ("better move", "better alternative"),
    "opponent_resource": (
        "opponent resource",
        "opponent's key reply",
        "let the opponent",
        "allowed the opponent",
        "opponent improve",
    ),
    "hidden_resource": ("hidden resource",),
    "hard_to_find": ("hard to find", "difficult to find", "engine-like", "engine like"),
    "teachable_skill_gap": ("stronger players", "stronger levels"),
    "king_safety": (
        "king safety",
        "king was exposed",
        "king is exposed",
        "exposed king",
        "unsafe king",
    ),
    "center": ("center", "centre", "central"),
    "development": ("development", "developing", "undeveloped"),
    "initiative": ("initiative",),
    "space": ("space advantage", "space"),
    "pawn_structure": (
        "pawn structure",
        "isolated pawn",
        "isolated pawns",
        "weak pawn",
        "weak pawns",
    ),
    "passed_pawn": ("passed pawn", "passed pawns"),
    "open_file": ("open file", "open files", "file control"),
    "piece_activity": (
        "piece activity",
        "active piece",
        "active pieces",
        "inactive piece",
        "inactive pieces",
    ),
    "weak_square": ("weak square", "weak squares", "outpost"),
}
CAVEAT_TERMS = {
    "hard",
    "difficult",
    "not obvious",
    "hidden",
    "engine-like",
    "engine like",
    "tough",
    "not easy",
}
RECOMMENDATION_TERMS = {
    "should",
    "needed",
    "had to",
    "play",
    "try",
    "recommend",
}
HARD_FINDABILITY = {"hard", "very_hard", "engine_like"}


class ExplanationVerifier:
    """Verify model prose against supplied context evidence."""

    def verify(
        self,
        context_result: ContextResult,
        output: ExplanationOutput,
    ) -> ExplanationVerificationResult:
        issues = _IssueCollector()
        explanation = output.explanation.strip()
        if not explanation:
            issues.fail("empty_explanation", "$.explanation", "Explanation cannot be empty.")
            return issues.result()

        allowed_aliases = _allowed_move_aliases(context_result)
        mentions = _move_mentions(explanation)
        _verify_played_move_mentioned(context_result, mentions, issues)
        _verify_move_mentions(mentions, allowed_aliases, issues)
        _verify_quality(context_result, explanation, issues)
        _verify_supported_claim_terms(context_result, explanation, issues)
        _verify_best_move_consistency(context_result, explanation, mentions, issues)
        _verify_recommendation_policy(context_result, explanation, mentions, issues)
        _verify_hard_move_caveats(context_result, explanation, mentions, issues)
        _verify_side_attribution(context_result, explanation, issues)
        _verify_pv_language(context_result, explanation, mentions, allowed_aliases, issues)
        return issues.result()


@dataclass(frozen=True)
class _MoveMention:
    token: str
    normalized: str
    path: str
    is_uci: bool = False


@dataclass
class _IssueCollector:
    failures: list[ExplanationVerificationIssue] = field(
        default_factory=list[ExplanationVerificationIssue]
    )
    warnings: list[ExplanationVerificationIssue] = field(
        default_factory=list[ExplanationVerificationIssue]
    )

    def fail(self, code: ExplanationVerificationIssueCode, path: str, message: str) -> None:
        self.failures.append(ExplanationVerificationIssue(code=code, path=path, message=message))

    def result(self) -> ExplanationVerificationResult:
        return ExplanationVerificationResult(
            verifier_version=EXPLANATION_VERIFIER_VERSION,
            passed=not self.failures,
            failures=self.failures,
            warnings=self.warnings,
        )


def _allowed_move_aliases(context_result: ContextResult) -> set[str]:
    aliases = _san_aliases(context_result.llm_context.played)
    for candidate in context_result.evidence.candidates:
        aliases.update(_san_aliases(candidate.san))
    after_line = context_result.evidence.engine.after_line
    if after_line and _move_is_allowed_by_claims(after_line.move_san, context_result):
        aliases.update(_san_aliases(after_line.move_san))
    return aliases


def _move_is_allowed_by_claims(san: str, context_result: ContextResult) -> bool:
    claim_text = _support_text(context_result)
    return any(alias.lower() in claim_text for alias in _san_aliases(san))


def _san_aliases(san: str) -> set[str]:
    stripped = san.strip()
    if not stripped:
        return set()
    without_suffix = stripped.rstrip("+#")
    return {stripped.lower(), without_suffix.lower()}


def _move_mentions(explanation: str) -> list[_MoveMention]:
    mentions: list[_MoveMention] = []
    seen_ranges: set[tuple[int, int]] = set()
    for match in UCI_MOVE_RE.finditer(explanation):
        seen_ranges.add(match.span())
        token = match.group(0)
        mentions.append(
            _MoveMention(
                token=token,
                normalized=token.lower(),
                path=f"$.explanation[{match.start()}:{match.end()}]",
                is_uci=True,
            )
        )
    for match in SAN_MOVE_RE.finditer(explanation):
        if match.span() in seen_ranges:
            continue
        token = match.group(0)
        mentions.append(
            _MoveMention(
                token=token,
                normalized=token.rstrip("+#").lower(),
                path=f"$.explanation[{match.start()}:{match.end()}]",
            )
        )
    return mentions


def _verify_move_mentions(
    mentions: list[_MoveMention],
    allowed_aliases: set[str],
    issues: _IssueCollector,
) -> None:
    for mention in mentions:
        if mention.is_uci:
            issues.fail(
                "uci_move_mentioned",
                mention.path,
                f"Explanation mentioned UCI move {mention.token}; use supplied SAN display moves.",
            )
            continue
        if mention.normalized not in allowed_aliases:
            issues.fail(
                "mentioned_move_unsupported",
                mention.path,
                f"Explanation mentioned {mention.token}, which is not supplied in the context.",
            )


def _verify_played_move_mentioned(
    context_result: ContextResult,
    mentions: list[_MoveMention],
    issues: _IssueCollector,
) -> None:
    played_aliases = _san_aliases(context_result.llm_context.played)
    mentioned_aliases = {mention.normalized for mention in mentions if not mention.is_uci}
    if not _aliases_mentioned(played_aliases, mentioned_aliases):
        issues.fail(
            "played_move_missing",
            "$.explanation",
            f"Explanation does not mention the played move {context_result.llm_context.played}.",
        )


def _verify_quality(
    context_result: ContextResult,
    explanation: str,
    issues: _IssueCollector,
) -> None:
    expected = _quality_phrases(context_result.llm_context.quality)
    text = explanation.lower()
    if not any(phrase in text for phrase in expected):
        issues.fail(
            "quality_label_missing",
            "$.explanation",
            f"Explanation does not clearly state quality {context_result.llm_context.quality}.",
        )
        return

    played = context_result.llm_context.played.lower().rstrip("+#")
    for label in _all_quality_labels() - {context_result.llm_context.quality}:
        for phrase in _quality_phrases(label):
            if f"{played} was {phrase}" in text or f"{played} was a {phrase}" in text:
                issues.fail(
                    "quality_label_conflict",
                    "$.explanation",
                    f"Explanation conflicts with quality {context_result.llm_context.quality}.",
                )
                return


def _verify_supported_claim_terms(
    context_result: ContextResult,
    explanation: str,
    issues: _IssueCollector,
) -> None:
    text = explanation.lower()
    support = _support_text(context_result)
    if ("mate" in text or "checkmate" in text or "#" in explanation) and "mate" not in support:
        issues.fail(
            "unsupported_mate_claim",
            "$.explanation",
            "Explanation includes a mate claim not present in supplied claims.",
        )
    if MATERIAL_RE.search(explanation):
        material_support = _trusted_claim_text(context_result, {"material"})
        unsupported_material_term = _unsupported_material_term(text, material_support)
        if unsupported_material_term is not None:
            issues.fail(
                "unsupported_material_claim",
                "$.explanation",
                (
                    "Explanation includes a material claim not present in supplied "
                    f"claims: {unsupported_material_term}."
                ),
            )
    tactic = next((term for term in TACTIC_TERMS if term in text), None)
    if tactic and tactic not in support:
        issues.fail(
            "unsupported_tactic_claim",
            "$.explanation",
            f"Explanation includes unsupported tactic claim {tactic!r}.",
        )
    concept = _unsupported_concept_claim(text, context_result, support)
    if concept is not None:
        issues.fail(
            "unsupported_concept_claim",
            "$.explanation",
            f"Explanation includes unsupported concept claim {concept!r}.",
        )
    if RAW_ENGINE_RE.search(explanation):
        issues.fail(
            "raw_engine_dump",
            "$.explanation",
            "Explanation includes raw engine/evaluation data.",
        )


def _verify_best_move_consistency(
    context_result: ContextResult,
    explanation: str,
    mentions: list[_MoveMention],
    issues: _IssueCollector,
) -> None:
    engine_best = context_result.llm_context.engine_best_move
    if engine_best is None:
        return
    best_aliases = _san_aliases(engine_best.move)
    text = explanation.lower()
    for mention in mentions:
        if mention.is_uci or mention.normalized in best_aliases:
            continue
        if (
            f"{mention.normalized} was the best" in text
            or f"best move was {mention.normalized}" in text
            or f"best was {mention.normalized}" in text
        ):
            issues.fail(
                "best_move_inconsistent",
                mention.path,
                f"Explanation calls {mention.token} best, but engine best is {engine_best.move}.",
            )


def _verify_recommendation_policy(
    context_result: ContextResult,
    explanation: str,
    mentions: list[_MoveMention],
    issues: _IssueCollector,
) -> None:
    text = explanation.lower()
    mentioned = {mention.normalized for mention in mentions if not mention.is_uci}
    for candidate in context_result.evidence.candidates:
        if candidate.recommendation_policy != "do_not_recommend":
            continue
        if not _candidate_is_mentioned(candidate, mentioned):
            continue
        if _has_recommendation_language(text, _san_aliases(candidate.san)):
            issues.fail(
                "recommendation_policy_violation",
                "$.explanation",
                f"Explanation recommends {candidate.san}, which is marked do_not_recommend.",
            )


def _verify_hard_move_caveats(
    context_result: ContextResult,
    explanation: str,
    mentions: list[_MoveMention],
    issues: _IssueCollector,
) -> None:
    text = explanation.lower()
    if any(term in text for term in CAVEAT_TERMS):
        return
    mentioned = {mention.normalized for mention in mentions if not mention.is_uci}
    for move_context in _move_contexts(context_result):
        if move_context.findability not in HARD_FINDABILITY:
            continue
        if not _aliases_mentioned(_san_aliases(move_context.move), mentioned):
            continue
        if move_context.recommendation_policy in {
            "mention_with_caveat",
            "explain_as_hidden_resource",
        }:
            issues.fail(
                "hard_move_uncaveated",
                "$.explanation",
                f"Explanation mentions hard move {move_context.move} without a caveat.",
            )


def _verify_side_attribution(
    context_result: ContextResult,
    explanation: str,
    issues: _IssueCollector,
) -> None:
    player = context_result.evidence.request.player_color
    opponent = "black" if player == "white" else "white"
    text = explanation.lower()
    if re.search(rf"\b(?:as|for)\s+{opponent}\b|\b{opponent}\s+should have\b", text):
        issues.fail(
            "side_attribution_unsupported",
            "$.explanation",
            f"Explanation appears to attribute the player's move to {opponent}.",
        )


def _verify_pv_language(
    context_result: ContextResult,
    explanation: str,
    mentions: list[_MoveMention],
    allowed_aliases: set[str],
    issues: _IssueCollector,
) -> None:
    if len(mentions) < 2:
        return
    text = explanation.lower()
    if not any(marker in text for marker in {" then ", " followed by ", " line ", " sequence "}):
        return
    allowed_reply_aliases = _allowed_reply_aliases(context_result)
    for mention in mentions[1:]:
        if (
            mention.normalized not in allowed_aliases
            and mention.normalized not in allowed_reply_aliases
        ):
            issues.fail(
                "unsupported_pv",
                mention.path,
                f"Explanation appears to introduce unsupported continuation {mention.token}.",
            )


def _allowed_reply_aliases(context_result: ContextResult) -> set[str]:
    after_line = context_result.evidence.engine.after_line
    if after_line is None:
        return set()
    if not _move_is_allowed_by_claims(after_line.move_san, context_result):
        return set()
    return _san_aliases(after_line.move_san)


def _support_text(context_result: ContextResult) -> str:
    parts = [
        context_result.evidence.main_point.concept,
        context_result.evidence.main_point.claim,
        context_result.llm_context.main_point,
        context_result.llm_context.severity,
        context_result.llm_context.human_note or "",
        *context_result.llm_context.allowed_claims,
    ]
    for concept_claim in _trusted_concept_claims(context_result):
        parts.extend(
            [
                concept_claim.kind.replace("_", " "),
                concept_claim.subject.replace("_", " "),
                concept_claim.claim,
            ]
        )
    for move_context in _move_contexts(context_result):
        parts.append(move_context.reason)
    return " ".join(parts).lower()


def _move_contexts(context_result: ContextResult) -> list[KeyMoveContext]:
    contexts = [
        context_result.llm_context.best_or_key_move,
        context_result.llm_context.engine_best_move,
        context_result.llm_context.practical_alternative,
        context_result.llm_context.featured_move,
    ]
    return [context for context in contexts if context is not None]


def _quality_phrases(label: str) -> set[str]:
    if label == "missed_win":
        return {"missed a winning move", "missed win", "missed a win"}
    if label == "forced":
        return {"forced", "only legal move", "no legal alternative"}
    return {label}


def _all_quality_labels() -> set[str]:
    return {
        "best",
        "forced",
        "excellent",
        "good",
        "neutral",
        "inaccuracy",
        "mistake",
        "blunder",
        "missed_win",
    }


def _candidate_is_mentioned(candidate: CandidateMove, mentioned: set[str]) -> bool:
    return _aliases_mentioned(_san_aliases(candidate.san), mentioned)


def _aliases_mentioned(aliases: set[str], mentioned: set[str]) -> bool:
    return any(alias in mentioned for alias in aliases)


def _has_recommendation_language(text: str, aliases: set[str]) -> bool:
    for alias in aliases:
        if re.search(rf"\b{re.escape(alias)}\s+was\s+(?:the\s+|a\s+)?better\b", text) or re.search(
            rf"\bbetter\s+move\s+was\s+{re.escape(alias)}\b", text
        ):
            return True
        for match in re.finditer(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text):
            start = max(0, match.start() - 36)
            end = min(len(text), match.end() + 36)
            window = text[start:end]
            if any(term in window for term in RECOMMENDATION_TERMS):
                return True
    return False


def _unsupported_concept_claim(
    text: str,
    context_result: ContextResult,
    support: str,
) -> str | None:
    supported_kinds = _trusted_concept_kinds(context_result)
    has_structured_concepts = bool(
        context_result.evidence.concept_claims or context_result.llm_context.concept_claims
    )
    for kind, aliases in CONCEPT_ALIASES_BY_KIND.items():
        if not any(_contains_phrase(text, alias) for alias in aliases):
            continue
        if kind in supported_kinds:
            continue
        if not has_structured_concepts and any(
            _contains_phrase(support, alias) for alias in aliases
        ):
            continue
        return kind.replace("_", " ")
    return None


def _trusted_concept_kinds(context_result: ContextResult) -> set[str]:
    return {claim.kind for claim in _trusted_concept_claims(context_result)}


def _trusted_claim_text(context_result: ContextResult, kinds: set[str]) -> str:
    parts: list[str] = []
    for claim in _trusted_concept_claims(context_result):
        if claim.kind in kinds:
            parts.extend([claim.kind.replace("_", " "), claim.claim])
    return " ".join(parts).lower()


def _unsupported_material_term(text: str, material_support: str) -> str | None:
    if not material_support:
        return "material"
    for term, aliases in MATERIAL_TERM_ALIASES.items():
        if not any(_contains_phrase(text, alias) for alias in aliases):
            continue
        if any(_contains_phrase(material_support, alias) for alias in aliases):
            continue
        return term
    return None


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _trusted_concept_claims(context_result: ContextResult) -> list[ConceptClaim]:
    llm_claim_keys = {
        _concept_claim_key(claim) for claim in context_result.llm_context.concept_claims
    }
    return [
        claim
        for claim in context_result.evidence.concept_claims
        if _concept_claim_key(claim) in llm_claim_keys
    ]


def _concept_claim_key(claim: ConceptClaim) -> tuple[str, str, str, str, str | None]:
    return (claim.kind, claim.subject, claim.claim, claim.source, claim.move_san)
