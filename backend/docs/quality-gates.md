# Quality Gates

Quality gates are the checkpoints that keep the system from becoming a fluent
but unreliable chess explainer.

## Gate 0: Decision Gate

Required before implementation when a change affects:

- data source or data rights
- incident or explanation schemas
- Stockfish configuration
- Maia configuration
- verifier policy
- model-training data
- model promotion criteria
- production explanation behavior

Output: accepted ADR in `docs/adr/`.

## Gate 1: Schema Gate

All externally meaningful objects must validate against versioned schemas.

Minimum schema-covered objects:

- incident packet
- explanation output
- verifier result
- dataset manifest
- evaluation result

Schema failures are hard failures.

## Gate 2: Chess Truth Gate

Any incident packet must pass deterministic checks before it can be used for
explanation, training, or evaluation.

Required checks:

- FEN is valid.
- Played move is legal from `fen_before`.
- `fen_after` matches applying the played move.
- Side-to-move, player color, and score perspective are consistent.
- Centipawn scores and mate scores use separate representations.
- Stockfish version, depth or nodes, options, and MultiPV are recorded.
- WDL values are recorded when enabled.
- PV moves are legal when replayed from the analyzed position.

## Gate 3: Explanation Verification Gate

Every production explanation must pass:

- JSON/schema validation.
- Legal move validation for mentioned moves.
- Best move consistency with incident evidence.
- No unsupported PV moves.
- No unsupported tactic or material claims.
- No mate/centipawn confusion.
- Correct side attribution.
- Recommended alternatives include objective evidence and findability or
  explicitly mark findability as unknown.
- Hard-to-find alternatives are caveated instead of presented as obvious.

If this gate fails, regenerate or route to review. Do not show the failed output
as final.

## Gate 4: Test Gate

Code changes must include tests at the level where the risk lives.

Static type checks are part of this gate for Python code:

- `uv run mypy src tests`
- `uv run pyright`

Expected test types:

- Unit tests for parsers, score normalization, classification, and detectors.
- Property tests for FEN/move replay and perspective normalization where useful.
- Integration tests for Stockfish and Maia wrappers.
- Golden tests for incident packets and explanations.
- Regression tests for every fixed hallucination or chess correctness bug.

Tests should not depend on internet access. Engine-dependent tests should use
small fixed positions and stable budgets.

## Gate 5: Dataset Gate

A sample can enter training only if:

- source rights are known
- incident schema is valid
- deterministic chess verifier passes
- explanation schema is valid
- unsupported-claim check passes
- quality score meets the current threshold
- generation, verifier, prompt, and model versions are recorded

Rejected samples should be retained when useful for preference, critic, or
regression datasets.

## Gate 6: Model Promotion Gate

A prompted model, fine-tuned model, judge, or rewriter can be promoted only if it
beats or matches the current production candidate on frozen evals.

Minimum metrics:

- schema pass rate
- deterministic verification pass rate
- unsupported claim rate
- wrong best-move claim rate
- illegal move mention rate
- rating appropriateness
- explanation clarity
- explanation usefulness
- latency and cost

Human-reviewed evals override model-judge-only optimism.

## Gate 7: Product Gate

Before a feature is considered product-ready, verify that it improves at least
one user-facing outcome from `docs/end-goal.md`:

- the user understands what changed
- the user sees a concrete better move or better idea when evidence supports it
- the explanation is short enough to read quickly

Engine-perfect but pedagogically useless output does not pass.

## Required Completion Note

Every substantial change should report:

- tests run
- gates passed
- gates intentionally skipped and why
- residual risks
