# ADR 0002: Context Contract And Verification

Date: 2026-04-30
Status: Accepted

## Decision

The context engine returns two internal artifacts:

- evidence packet: complete verified truth record for tests, debugging, evals,
  and future training data
- LLM context: compact deterministic projection for generation

Versioned Pydantic contracts define externally meaningful evidence, context,
candidate, quality, and verifier objects.

## Rules

- Stockfish is the required objective-strength source for production context.
- Maia is optional human-likeness evidence; it affects findability, not move
  quality.
- Every recommended candidate must carry objective evidence and findability or
  `unknown`.
- Significance and beauty are deterministic compact signals with labels and
  scores, not generated prose.
- `EvidenceVerifier` blocks malformed context before generation.
- Explanation verification blocks unsupported moves, PVs, tactics, material
  claims, mate claims, and wrong-side attribution.

## Validation

The default check set must pass:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
```

Run the real Maia gate only when work depends on actual Maia behavior:

```text
G6EXPLANATION_RUN_MAIA2=1 uv run pytest tests/g6explanation/context_engine/test_real_game_maia_evaluation.py -q
```
