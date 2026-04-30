# Testing Playbook

## Philosophy

Test the contracts that keep explanations truthful:

```text
board state -> evidence -> LLM context -> explanation -> verifier
```

Prefer small deterministic tests until the core contracts are stable.

## Test First

Prioritize:

- PGN/FEN parsing and move replay
- UCI to SAN conversion
- legal move generation
- Stockfish output parsing
- score normalization from player perspective
- mate score representation
- WDL and MultiPV parsing
- played-move forced analysis
- evidence, LLM context, explanation, and verifier schemas
- deterministic verifier failures

## Test Data

- Use tiny fixed PGNs and FENs checked into the repo.
- Include White and Black perspective cases.
- Include mate, promotion, castling rights, and en passant.
- Include hard engine moves and human-common bad moves.
- Avoid tests that need internet access.
- Engine-dependent tests should use tiny fixed budgets and skip cleanly when the
  binary is unavailable.

## Unit Tests

Use unit tests for pure logic: score parsing, normalization, classification,
WDL deltas, phase, material, concept rules, schema validators, and verifier
checks.

Each fixed bug leaves a regression test.

## Integration Tests

Use integration tests for external binaries and model adapters:

- Stockfish startup and readiness
- MultiPV and WDL parsing
- `searchmoves` forced played-move analysis
- Maia inference returns legal move probabilities

Keep normal CI budgets small. Deeper analysis belongs in offline evals.

Real Maia evaluation is opt-in per ADR 0010:

```text
G6EXPLANATION_RUN_MAIA2=1 uv run pytest tests/g6explanation/context_engine/test_real_game_maia_evaluation.py -q
```

Use actual Maia in integration/evaluation tests, not ordinary unit tests. Static
human-likelihood providers remain the default for deterministic policy tests.

## Golden Tests

Golden tests should assert stable structured fields and supported claims, not
exact free-form explanation wording unless the wording is a product contract.

For heuristic scalar fields, assert labels and threshold behavior instead of
exact floats, except when a pure formula itself is the contract.

## Adversarial Tests

Create fixtures for:

- illegal move mention
- move outside supplied evidence
- mate/centipawn confusion
- unsupported material claim
- wrong side attribution
- unsupported follow-up recommendation
- hard move presented as obvious
- Maia probability treated as quality
- absent tactic tag used as fact

## Evaluation Tests

Prompt or model changes require evals:

- frozen gold set
- regression set
- rating ladder set
- concept set
- representative product set

Compare against the current baseline.

## Test Names

Name tests by behavior:

```text
test_normalizes_black_player_eval_from_player_perspective
test_rejects_explanation_with_unprovided_pv_move
test_represents_mate_score_without_centipawn_conversion
```
