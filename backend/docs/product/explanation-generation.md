# Explanation Generation

## Purpose

Explanation generation turns a verified `LLMContext` into one verified public
explanation string.

This layer is downstream of the context engine. It does not calculate chess,
choose better moves, alter quality labels, or reinterpret Stockfish, Maia, or
deterministic rule evidence.

## Current Next Slice

The context engine already builds verified evidence packets and compact LLM
contexts. The next product slice is not prompt tuning. It is the generation
boundary that makes model output safe to return.

Build this slice in this order:

1. Explanation output and verification contracts.
2. Deterministic baseline renderer.
3. Explanation-text verifier.
4. Static coach provider for tests.
5. Generation service with retry and fallback behavior.
6. Real model adapter.
7. Frozen real-game and adversarial evals.
8. Public `explain_move(...) -> str` wrapper.

Do not start training or fine-tuning before this slice can generate, verify, and
trace explanations from real context packets.

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

## Contracts

The raw model response must validate against:

```json
{
  "explanation": "string"
}
```

The generation layer should introduce contracts for:

- raw explanation response
- verified explanation result
- explanation verification issue
- explanation verification result
- generation attempt metadata

Schema failures are hard failures. The verifier may retry once with concrete
issue codes, but invalid output must never be returned directly.

## Deterministic Baseline

Before a real model adapter, add a deterministic baseline renderer that writes a
plain explanation from `LLMContext`.

The baseline has three jobs:

- provide golden tests for the explanation contract
- prove the context contains enough evidence to explain the move without
  invention
- provide a safe fallback while model prompts are still immature

If the baseline cannot explain a case without inventing a claim, the context
packet is incomplete for that case.

## Explanation Verifier

Every generated explanation must pass deterministic checks before it can be
returned.

Minimum checks:

- JSON schema validation
- mentioned move validation against played move, supplied candidates, featured
  move, engine best, practical alternative, and explicitly allowed replies
- no unsupported PV continuations
- no unsupported mate, material, tactic, or concept claims
- quality label consistency with `LLMContext.quality`
- best move and practical alternative consistency
- side-to-move and player-perspective sanity
- no direct recommendation of a `do_not_recommend` move
- hard or engine-like alternatives caveated when the context marks them hard

Because free-form chess language is hard to verify, the first prompt should keep
wording close to `main_point`, supplied move contexts, `human_note`, and
`allowed_claims`.

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

Use a small coach-provider protocol with a static test implementation and a
concrete real-model adapter.

The provider may:

- consume the static prompt and JSON context
- return raw schema-shaped output
- expose model and provider version metadata

The provider may not:

- call Stockfish or Maia
- modify the context packet
- choose or replace the best move
- bypass explanation verification

When implementing an OpenAI adapter, check the current official OpenAI API docs
first and record the model and prompt versions in generated metadata.

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
