# Training Data

## Purpose

Training data is a downstream artifact, not a substitute for chess truth. A
generated explanation can become a training example only after the context
engine, explanation verifier, source-rights gate, and manual review all accept
it.

## Eligible Sources

- `project_synthetic`: positions created inside this repository for coverage.
- `project_curated_historical_game_score`: historical game scores curated in
  this repository without importing a third-party commercial database export.
- `lichess_database_cc0`: Lichess database exports released under Creative
  Commons CC0.

Chess.com-derived data is not eligible for global training unless there is prior
written authorization. User-imported games may be explained for that user, but
they must not enter global training without explicit rights and product policy.

## Required Record Shape

An eval record must include:

- source rights metadata
- verified `LLMContext`
- final verified explanation
- provider and model metadata
- schema, context, prompt, and verifier versions
- Stockfish metadata with depth 16 or deeper
- fallback status
- manual review category

The training manifest excludes records that are not manually marked `accepted`,
failed verification, used fallback, lack source rights, lack `LLMContext`, lack
provider/model/version metadata, or used insufficient Stockfish depth.

## Review Standard

Manual acceptance means the explanation is suitable as supervised training data,
not merely that it passed deterministic verification. Reviewers should check:

- chess correctness and side perspective
- no unsupported moves, lines, tactics, mate, material, or positional claims
- helpfulness for the supplied player level
- concise wording
- source rights and metadata completeness

## Current Next Step

Broaden accepted seed coverage from the real eval suite. Use Lichess CC0
positions for random/open-web coverage, keep Chess.com out of training until
authorization exists, and compare any future fine-tune against the verified
GPT-5.5 baseline on frozen and blind no-mock evals.
