# Testing Playbook

This document defines how tests should be created once implementation begins.

## Testing Philosophy

Test the contracts that keep chess explanations truthful:

```text
board state -> evidence -> incident -> explanation -> verifier
```

Prefer small, deterministic tests over broad end-to-end tests until the core
contracts are stable.

## What To Test First

The earliest implementation should prioritize tests for:

- PGN/FEN parsing and move replay
- UCI to SAN conversion
- legal move generation
- Stockfish output parsing
- score normalization from player perspective
- mate score representation
- WDL parsing
- MultiPV parsing
- played-move forced analysis
- incident packet schema validation
- explanation schema validation
- deterministic verifier checks

## Test Data Rules

- Use tiny fixed PGNs and FENs checked into the repo.
- Include positions for both White and Black to move.
- Include at least one mate score case.
- Include at least one promotion case.
- Include at least one castling-rights-sensitive case.
- Include at least one en passant case.
- Include one "engine best move is not human-obvious" case.
- Include one "played move is human-common but engine-bad" case.

Avoid tests that require downloading datasets or calling external APIs.

## Unit Tests

Use unit tests for pure logic:

- score parsing
- score normalization
- swing classification
- WDL delta calculation
- phase classification
- material counting
- concept tag rules
- schema validators
- explanation field validators

Each bug in these areas should leave behind a regression test.

## Integration Tests

Use integration tests for external binaries and models:

- Stockfish UCI startup and readiness.
- Stockfish `MultiPV` response parsing.
- Stockfish `searchmoves` for the played move.
- `UCI_ShowWDL` parsing when enabled.
- Maia inference wrapper returns legal move probabilities.

Keep engine budgets tiny in normal CI. Deeper analysis belongs in offline evals.

## Golden Tests

Golden tests should cover stable examples:

```text
input PGN/FEN
  -> expected incident packet fields
  -> expected verifier behavior
  -> expected explanation shape
```

Do not assert exact free-form wording unless the wording is part of a product
contract. Prefer checking structured fields and supported claims.

## Adversarial Tests

Create adversarial fixtures for common failures:

- explanation mentions an illegal move
- explanation names a move outside top lines and played line
- explanation says "mate" when score is centipawn
- explanation says "wins a queen" when material check does not support it
- explanation attributes White's advantage to Black
- explanation recommends unsupported follow-up actions
- explanation presents a hard-to-find engine move as obvious
- explanation treats Maia probability as move quality
- explanation uses a tactic tag absent from incident evidence

These fixtures should be used by the deterministic verifier.

## Evaluation Tests

Model and prompt changes require evals, not just unit tests.

Maintain:

- frozen gold set: human-reviewed, never trained on
- regression set: examples from past failures
- rating ladder set: same position explained to different ratings
- concept set: one or more examples per supported concept
- product set: representative single-move explanations

Promotion should compare against the current baseline, not just an absolute
score.

## Test Naming

Name tests by behavior:

```text
test_normalizes_black_player_eval_from_player_perspective
test_rejects_explanation_with_unprovided_pv_move
test_represents_mate_score_without_centipawn_conversion
```

Avoid names that only restate implementation details.

## When Tests Are Not Enough

Use manual or human-coach review for:

- explanation clarity
- rating appropriateness
- lesson usefulness
- explanation wording

Record reviewed examples as eval fixtures when possible.
