# Quality Gates

Quality gates prevent fluent but unreliable chess explanations.

## Gate 0: Decision

Update the concise ADR set before changing data rights, schema contracts,
Stockfish or Maia configuration, verifier policy, training data, model promotion
criteria, or production explanation behavior.

## Gate 1: Schema

Version and validate externally meaningful objects:

- evidence packet
- LLM context
- explanation output
- verifier result
- dataset manifest
- evaluation result

Schema failures are hard failures.

## Gate 2: Chess Truth

Before explanation, verify:

- valid FEN
- legal played move from `fen_before`
- correct `fen_after`
- side-to-move, player color, and perspective consistency
- separate centipawn and mate representations
- Stockfish version, options, budget, and MultiPV metadata, with depth-limited
  real-engine analysis at depth 16 or deeper
- legal PV replay

## Gate 3: Explanation

Every production explanation must pass:

- schema validation
- deterministic explanation-output verification
- legal move validation for mentioned moves
- best-move and practical-alternative consistency
- no unsupported PV moves
- no unsupported tactic, material, or mate claims
- correct side attribution
- hard alternatives caveated when context marks them hard

Failure blocks raw model output. The generation layer may retry once with
verifier issues, then return a verified deterministic fallback or a controlled
failure.

## Gate 4: Tests And Types

Run the required local checks:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
```

Add tests where the risk lives: parsers, score normalization, move legality,
schemas, verifiers, provider adapters, and prompt/eval regressions.

## Gate 5: Dataset

A sample can enter training only if rights are known, schemas pass, deterministic
chess verification passes, explanation verification passes, quality review
passes, and all generation/provider/verifier versions are recorded.

## Gate 6: Model Promotion

Promote prompts, fine-tunes, judges, or rewriters only when they match or beat
the current baseline on frozen evals and deterministic verification.

Minimum metrics: schema pass rate, verification pass rate, unsupported-claim
rate, wrong best-move rate, illegal-move rate, rating fit, usefulness, latency,
and cost.

## Gate 7: Product

A feature is product-ready only if it improves the user's understanding of the
requested move, supported better idea, or explanation clarity.

## Optional Maia Evaluation Gate

Run this gate only when work depends on real Maia behavior:

```text
G6EXPLANATION_RUN_MAIA2=1 uv run pytest tests/g6explanation/context_engine/test_real_game_maia_evaluation.py -q
```

It is intentionally outside the default required check set.

## Optional OpenRouter Evaluation Gates

Run these gates only when work depends on actual LLM provider behavior:

```text
G6EXPLANATION_RUN_OPENROUTER=1 uv run pytest tests/g6explanation/explanation_generation/test_real_openrouter_generation.py -q
G6EXPLANATION_RUN_OPENROUTER_STOCKFISH=1 uv run pytest tests/g6explanation/explanation_generation/test_real_openrouter_generation.py -q
G6EXPLANATION_RUN_REAL_LLM_EVAL=1 uv run pytest tests/g6explanation/real_game_evaluation/test_real_explanation_evaluation.py -q -s
```

They require `OPENROUTER_API_KEY` in the environment or `.env`. The real LLM eval
also requires local Stockfish, `maia2`, and local Maia model files. It disables
deterministic fallback, so every passing case used real model output.

Use `G6EXPLANATION_REAL_LLM_EVAL_OUTPUT=.evals/real-explanations.jsonl` to keep
JSONL records for manual review. Use `G6EXPLANATION_REAL_LLM_EVAL_CASES` only for
local debugging; the product gate should run the full curated case list.
Use `G6EXPLANATION_REAL_LLM_EVAL_REPORT=.evals/real-explanations.md` to create
the durable summary report used for manual review and promotion comparisons.
Manual-review annotations default to
`docs/development/real-explanation-manual-reviews.json` and can be overridden
with `G6EXPLANATION_REAL_LLM_EVAL_MANUAL_REVIEWS`.
Failed, retried, fallback, or surprising records must be reviewed before
changing prompt, verifier, model, or context policy.

## Completion Note

Report checks run, gates passed, skipped gates with reasons, and residual risk.
