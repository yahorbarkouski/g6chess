# ADR 0009: Evidence Verification Gate

Date: 2026-04-30
Status: Accepted

## Context

The context engine now produces a structured evidence packet and compact LLM
context before any public explanation generation. That packet is becoming a
product contract, not a debug object, so malformed evidence must be rejected
before it can drive an explanation, fixture, eval, or future training sample.

This changes schema contracts and verifier pass/fail rules, so it requires an
ADR.

## Decision

The context engine will use a deterministic `EvidenceVerifier` before returning
`ContextResult`.

`VerificationResult` contains structured `VerificationIssue` objects with a
stable issue code, JSON path, and message. Verification failures are blockers:
`MoveContextBuilder` raises `AnalysisError` instead of returning a context when
the verifier fails. Warnings may describe missing non-production static-test
evidence, but they do not block when failures are absent.

The verifier checks:

- FEN validity, side-to-move consistency, legal played move replay, legal move
  set, SAN/check/capture/promotion facts, and `fen_after`.
- Engine metadata, forced played-move analysis, legal root moves, legal PV
  replay, PV root consistency, after-move reply legality, and WDL when
  `UCI_ShowWDL` was requested.
- Candidate move legality, required played/best candidates, source roles, and
  recommendation-policy consistency for hard-to-find moves.
- Compact LLM context consistency with the evidence packet, including allowed
  claims and key-move fields.

The verifier does not call Stockfish, Maia, or an LLM. It validates supplied
evidence only.

## Consequences

Bad provider output fails earlier and with stable failure codes. Evidence
packets become safer to use for explanation generation and future golden/eval
fixtures because they carry an explicit verifier result.

The builder has one more hard gate, so static tests must provide enough evidence
to satisfy deterministic chess checks. Optional or intentionally incomplete
static-test evidence can produce warnings, but production Stockfish evidence
must include metadata, PVs, after-move analysis when the game continues, and WDL
when requested.

## Alternatives Considered

### Keep validation inside `MoveContextBuilder`

Rejected. Builder-private checks are hard to reuse for golden fixtures, evals,
and future explanation verification.

### Return failed context with warnings

Rejected. The product contract requires chess truth before wording. Returning a
failed context would make downstream explanation code responsible for rejecting
bad evidence.

### Let Pydantic validation be enough

Rejected. Pydantic validates shape, but it cannot prove legal move replay,
side-to-move perspective, PV legality, or claim containment.

## Validation

This decision is working if:

- verifier unit tests cover passing packets and major failure classes
- builder tests fail through `EvidenceVerifier` for invalid provider output
- Stockfish integration tests produce passing verification results
- `VerificationResult` JSON Schema exports with structured issues
- Ruff, mypy, Pyright, and pytest pass
