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
`LLMContext` plus verified line evidence derived from the evidence packet, not
raw engine state, and owns its own output schema, deterministic text verifier,
provider protocol, retry policy, and fallback policy before model output is
product-ready.

## Rules

- Stockfish is the required objective-strength source for production context.
- Stockfish depth-limited analysis must use depth 16 or deeper for production,
  engine-backed integration tests, evaluations, and visualization packets.
- `EvidenceVerifier` rejects non-static Stockfish evidence that cannot prove
  line depth 16 or deeper.
- Maia is optional human-likeness evidence; it affects findability, not move
  quality. Stronger-player comparison probabilities are present only when the
  Maia rating buckets differ; equal-bucket comparisons must be represented as
  unavailable instead of duplicated.
- Absolute engine WDL and signed WDL deltas are separate contracts. Absolute
  WDL values are 0..1000 and sum to 1000; deltas may be signed and sum to 0.
- Every recommended candidate must carry objective evidence and findability or
  `unknown`.
- LLM context separates objective `engine_best_move`, optional
  `practical_alternative`, and `featured_move`; `best_or_key_move` remains only
  as a compatibility key for the main better-move focus.
- Evidence packets and LLM contexts expose structured `concept_claims` for
  supported concept families. Free-form `allowed_claims` remain wording support,
  but they do not authorize unsupported strategic, tactical, mate, material, or
  forcing concepts by themselves.
- Evidence packets and LLM contexts expose structured `diagnostic_tags` for
  deterministic coach and review caveats, including WDL edge cases, time
  pressure, think-time usage, practical-option wording, rating-level wording, and
  no-blame forced-move wording. These tags guide explanation emphasis but do not
  change objective quality, significance, beauty, candidate policy, or concept
  truth.
- Legal played-move facts such as castling, en passant, and promotion are typed
  concept claims when exposed to the LLM.
- Supported concept claims include conservative deterministic evidence for
  net material gain or loss, material-recovery recaptures, verified immediate
  material trades from supplied PVs, king safety, development, open files,
  passed pawns, outposts, initiative, forcing move facts, direct attacks on
  valuable pieces, clear multi-target forks, opened bishop diagonal routes, and
  tactical proof lines showing why an apparently capturable tactic is not simply
  free.
- Move quality includes `forced` for positions with exactly one legal move so
  the context can describe the position outcome without assigning move blame.
- Immediate checkmates are quality `best` and significance `critical` even when
  Stockfish orders another mating move first.
- If the best line is already forced mate against the player, the engine-best
  defense is still `best`; only newly allowing mate or shortening the mate is a
  mate-transition blunder.
- Non-mating forced moves are capped at low beauty, and high played WDL win
  probability prevents non-mating moves from being labeled as ordinary mistakes
  or blunders.
- Non-mating WDL loss can make a move more serious, but it cannot be the only
  reason to call a move a `blunder`; below the centipawn blunder band, a
  WDL-only blunder signal is capped at `mistake`.
- Significance and beauty are deterministic compact signals with labels and
  scores, not generated prose.
- `MoveContextRequest` carries `think_time_seconds` when known. Time fields may
  affect findability, diagnostic tags, and wording verification, but they must
  not alter objective move quality.
- `EvidenceVerifier` blocks malformed context before generation.
- The explanation-generation raw output contract is sentence-sized segmented UI
  copy plus optional short anchors for verified hover line cards. Public plain
  text remains a derived joined string for compatibility.
- The explanation-generation layer must block unsupported moves, PVs, line-card
  ids or move sequences, tactics, material claims, mate claims, strategic concept
  claims, piece-attack claims, unsupported opening labels, unsupported time
  claims, and wrong-side attribution before any model output is product-ready.
- Line cards may only reference move sequences supplied as verified line
  evidence; models may write visible prose, short highlight anchors, and
  hover-card wording, but they may not invent card ids, alter supplied moves, or
  shorten the supplied line. Verified line cards are bounded at 16 SAN plies and
  should add follow-through beyond the visible segment instead of duplicating it.
  Objection line cards are allowed when verified reply evidence proves why an
  apparent capture fails.
  Full move arrays are for board visualization; explanation prose should avoid
  reading out long notation lines. Line-card title and `why` text must match the
  supplied line evidence exactly, and generic alternative line cards must not
  call an idea "better" unless verified better-move evidence supports that label.
- Model adapters cannot change context-engine truth. They may only produce raw
  schema-shaped explanation output for the generation layer to verify.
- Real eval records used for future training manifests must store source-rights
  metadata, verified `LLMContext`, prompt/schema/context/verifier versions, and
  the verified explanation text. Training manifests admit only manually accepted
  records whose source allows global training.

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
