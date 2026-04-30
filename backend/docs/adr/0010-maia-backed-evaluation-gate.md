# ADR 0010: Maia-Backed Evaluation Gate

Date: 2026-04-30
Status: Accepted

## Context

Static human-likelihood fixtures are useful for unit tests, but they cannot
validate the actual Maia-2 behavior that drives findability, surprise, and
beauty calibration. The context engine needs a real-model evaluation path so we
can see whether famous-game examples receive plausible human-likeness evidence.

At the same time, Maia-2 is a heavyweight optional dependency. It may require
Torch, local model files, and CPU/GPU resources. Normal unit tests should not
silently download models or fail when a contributor lacks the optional runtime.

## Decision

The repository will keep deterministic static providers for most unit tests and
add an opt-in real Maia evaluation gate:

```text
G6EXPLANATION_RUN_MAIA2=1 uv run pytest tests/g6explanation/context_engine/test_real_game_maia_evaluation.py -q
```

The test uses:

- real Stockfish for objective engine evidence
- real Maia-2 for human move likelihoods
- fixed famous-game PGNs
- label/range assertions, not exact probability snapshots

The gate is skipped unless:

- `G6EXPLANATION_RUN_MAIA2=1`
- `maia2` is importable
- Stockfish is available
- model files are available or the local environment is allowed to fetch them

## Consequences

Evaluation becomes more complete without making normal tests flaky. Static
providers remain the right choice for pure policy, schema, and builder tests.
Real Maia tests validate integration behavior and calibration examples.

Maia probabilities still never change objective move quality. They affect
findability, human-common roles, skill-gap evidence, and beauty surprise.

## Alternatives Considered

### Use actual Maia in most unit tests

Rejected. That would make the default test suite slow, stateful, and dependent
on optional model files.

### Keep Maia only as a smoke test

Rejected. A single opening-position smoke test proves the wrapper runs but does
not validate real context-engine evaluation behavior.

### Snapshot exact Maia probabilities

Rejected. Exact model decimals are too brittle across package, model, and
runtime changes. Evaluation tests should assert stable labels and broad
probability categories.

## Validation

This decision is working if:

- the normal test suite remains deterministic and fast
- the opt-in Maia gate runs real famous-game examples
- rare famous moves are marked hard or engine-like by Maia
- obvious tactical mates can be marked human-obvious by Maia
- beauty labels remain plausible when real Maia surprise is present
