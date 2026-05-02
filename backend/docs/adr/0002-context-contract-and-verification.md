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

Explanation generation is a separate downstream boundary. It consumes verified
`LLMContext`, not raw engine state, and must add its own output schema,
deterministic text verifier, provider protocol, retry policy, and fallback policy
before real model output is product-ready.

## Rules

- Stockfish is the required objective-strength source for production context.
- Stockfish depth-limited analysis must use depth 16 or deeper for production,
  engine-backed integration tests, evaluations, and visualization packets.
- Maia is optional human-likeness evidence; it affects findability, not move
  quality. Stronger-player comparison probabilities are present only when the
  Maia rating buckets differ; equal-bucket comparisons must be represented as
  unavailable instead of duplicated.
- Every recommended candidate must carry objective evidence and findability or
  `unknown`.
- LLM context separates objective `engine_best_move`, optional
  `practical_alternative`, and `featured_move`; `best_or_key_move` remains only
  as a compatibility key for the main better-move focus.
- Move quality includes `forced` for positions with exactly one legal move so
  the context can describe the position outcome without assigning move blame.
- Immediate checkmates are quality `best` and significance `critical` even when
  Stockfish orders another mating move first.
- Non-mating forced moves are capped at low beauty, and high played WDL win
  probability prevents non-mating moves from being labeled as ordinary mistakes
  or blunders.
- Significance and beauty are deterministic compact signals with labels and
  scores, not generated prose.
- `EvidenceVerifier` blocks malformed context before generation.
- The future explanation-generation layer must block unsupported moves, PVs,
  tactics, material claims, mate claims, and wrong-side attribution before any
  model output is product-ready.
- Model adapters cannot change context-engine truth. They may only produce raw
  schema-shaped explanation output for the generation layer to verify.

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
