# Explanation Generation

## Purpose

Explanation generation turns a verified `LLMContext` into one verified public
explanation string.

This layer is downstream of the context engine. It does not calculate chess,
choose better moves, alter quality labels, or reinterpret Stockfish, Maia, or
deterministic rule evidence.

## Current Implementation

The context engine builds verified evidence packets and compact LLM contexts.
The explanation-generation package provides the downstream generation boundary
that makes model output safe to return.

Implemented pieces:

- explanation output and verification contracts
- deterministic baseline renderer
- explanation-text verifier
- static coach provider tests
- generation service with retry and fallback behavior
- OpenRouter adapter defaulting to `openai/gpt-5.5`
- public `explain_move(...) -> str` wrapper

Next work is broader real-game LLM evals and verifier hardening, not training or
fine-tuning.

## Boundary

Input:

- `ContextResult` from `MoveContextBuilder`
- static prompt ID and version
- player-facing verbosity or rating adaptation settings when product-approved

Output:

- public: one explanation string
- internal: private metadata with context version, prompt version, provider
  version, verifier version, attempts, fallback status, and failure codes

The model provider returns raw JSON to the generation layer. The public API
returns only the verified `explanation` string.

The OpenRouter provider reads `OPENROUTER_API_KEY` from the environment or
`.env`, uses `openai/gpt-5.5` by default, and can be overridden with
`G6EXPLANATION_OPENROUTER_MODEL`.

## Contracts

The raw model response must validate against:

```json
{
  "explanation": "string"
}
```

The generation layer includes contracts for:

- raw explanation response
- verified explanation result
- explanation verification issue
- explanation verification result
- generation attempt metadata

Schema failures are hard failures. The verifier may retry once with concrete
issue codes, but invalid output must never be returned directly.

## Deterministic Baseline

The deterministic baseline renderer writes a plain explanation from
`LLMContext`.

The baseline has three jobs:

- provide golden tests for the explanation contract
- prove the context contains enough evidence to explain the move without
  invention
- provide a safe fallback when model output or provider I/O fails verification

If the baseline cannot explain a case without inventing a claim, the context
packet is incomplete for that case.

The baseline is never used to judge whether model wording is better. Model output
is verified directly against the context packet.

## Explanation Verifier

Every generated explanation must pass deterministic checks before it can be
returned.

Minimum checks:

- JSON schema validation
- mentioned move validation against played move, supplied candidates, featured
  move, engine best, practical alternative, and explicitly allowed replies
- no unsupported PV continuations
- no unsupported mate, material, tactic, or concept claims
- material prose requires a trusted typed `material` concept claim; unrelated
  words such as "piece" in development claims do not authorize material claims
- specific material prose, such as queen, rook, bishop, knight, pawn, or
  exchange, must match the trusted material claim text
- concept language must be supported by typed `concept_claims`; free-form
  `allowed_claims` alone do not authorize strategic concepts
- quality label consistency with `LLMContext.quality`
- best move and practical alternative consistency
- side-to-move and player-perspective sanity
- no direct recommendation of a `do_not_recommend` move
- hard or engine-like alternatives caveated when the context marks them hard

Because free-form chess language is hard to verify, prompts should keep wording
close to `main_point`, typed `concept_claims`, supplied move contexts,
`human_note`, and `allowed_claims`.

## Retry And Fallback

Generation flow:

```text
build verified context
render baseline candidate
call provider for strict JSON
validate schema
verify explanation text
retry once with verifier failures if needed
return verified model explanation, verified baseline fallback, or controlled failure
```

Use deterministic baseline fallback for early product demos unless the product
surface explicitly wants a controlled failure.

## Provider Boundary

Use the small coach-provider protocol with static test implementations and the
OpenRouter real-model adapter.

The provider may:

- consume the static prompt and JSON context
- return raw schema-shaped output
- expose model and provider version metadata

The provider may not:

- call Stockfish or Maia
- modify the context packet
- choose or replace the best move
- bypass explanation verification

When changing model defaults or API parameters, check current provider docs first
and record model and prompt versions in generated metadata.

## Tests And Evals

Unit tests:

- schema accepts valid explanation output and rejects extra fields
- verifier rejects unsupported moves, PVs, mate claims, material claims, tactic
  claims, wrong side attribution, and wrong recommendation policy
- baseline renderer produces verified output for representative context packets
- static provider retry and fallback behavior is deterministic

Real-provider evals:

- Opera Game
- Game of the Century
- at least one quiet positional game
- synthetic edge cases for forced moves, immediate mate, high-WDL non-best moves,
  hard engine resources, practical alternatives, and ordinary blunders

Current opt-in smoke tests:

- `G6EXPLANATION_RUN_OPENROUTER=1 uv run pytest tests/g6explanation/explanation_generation/test_real_openrouter_generation.py -q`
- `G6EXPLANATION_RUN_OPENROUTER_STOCKFISH=1 uv run pytest tests/g6explanation/explanation_generation/test_real_openrouter_generation.py -q`

Current no-mock real eval:

- `G6EXPLANATION_RUN_REAL_LLM_EVAL=1 uv run pytest tests/g6explanation/real_game_evaluation/test_real_explanation_evaluation.py -q -s`

This eval uses real Stockfish, real Maia, and real OpenRouter output with
fallback disabled. It covers Opera Game, Game of the Century,
Kasparov-Topalov, Capablanca-Tartakower, synthetic forced-move, and synthetic
ordinary-blunder, high-WDL non-best, castling, en passant, promotion, low-time,
rating-ladder, Black-perspective, and missed-win edge cases.

Persist JSONL records and a Markdown report when running the real eval for
review:

```text
G6EXPLANATION_REAL_LLM_EVAL_OUTPUT=.evals/real-explanations.jsonl \
G6EXPLANATION_REAL_LLM_EVAL_REPORT=.evals/real-explanations.md \
G6EXPLANATION_RUN_REAL_LLM_EVAL=1 \
uv run pytest tests/g6explanation/real_game_evaluation/test_real_explanation_evaluation.py -q -s
```

The report summarizes pass, fallback, retry, failure-code, latency, model,
Stockfish, Maia, and manual-review fields. Review categories should be used for
failed, retried, or surprising records before changing context policy, prompt
rules, or verifier behavior. Durable annotations live in
`docs/development/real-explanation-manual-reviews.json` and apply only when the
case id, model, attempts, and failure codes still match the reviewed record.

Metrics:

- schema pass rate
- explanation verification pass rate
- unsupported move rate
- unsupported mate/material/tactic claim rate
- wrong best-move or recommendation rate
- rating fit, usefulness, latency, and cost

## Non-Goals

- training data generation
- fine-tuning
- model judging
- UI wording polish beyond one verified explanation string
- full-game review, dashboards, drills, or personalized memory
