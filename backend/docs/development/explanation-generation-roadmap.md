# Explanation Generation Roadmap

This is the durable implementation ledger for the current product track. Keep it
updated after every coherent checkpoint so future agents can resume without
losing the plan during context summarization.

## Operating Rule

Work the roadmap in order unless a later item blocks an earlier one. Each
checkpoint should leave:

- code, tests, and docs aligned
- full default checks passing
- real no-mock eval rerun when prompt, provider, verifier, or eval behavior
  changes
- a checkpoint commit when checks pass

Do not start training-data work until the eval, review, promotion, verifier, and
provider gates below are mature.

## Current State

Completed foundation:

- strict explanation schema
- deterministic baseline renderer
- explanation verifier
- static provider tests
- OpenRouter `openai/gpt-5.5` adapter
- retry/fallback orchestration
- public `explain_move(request) -> str`
- no-mock Stockfish + Maia + OpenRouter eval harness
- structured `concept_claims` contract for currently supported concept evidence

Active phase:

```text
broader eval suite -> manual review loop -> concept detectors
```

## Ten-Step Track

| # | Step | Status | Exit criteria |
|---|---|---|---|
| 1 | Expand the real eval suite | Partial | No-mock cases include quiet positional moves, missed wins, already-lost mate defenses, promotions, castling, en passant, low-time cases, rating ladder cases, Black-perspective cases, and more high-WDL good-not-best moves. |
| 2 | Review eval output manually | Not started | Every failed, retried, or surprising record has a review category: context missing evidence, wrong context policy, prompt issue, verifier too weak, verifier too strict, model wording issue, or provider/runtime issue. |
| 3 | Add structured concept evidence | Partial | Deterministic tags exist for supported material, king safety, development, open files, passed pawns, weak squares, initiative, and forcing concepts before the LLM may mention them. |
| 4 | Harden the explanation verifier | Partial | Verification uses structured claims wherever possible for mentioned moves, concepts, material, mate, tactics, recommendation policy, side attribution, and best/practical-alternative language. |
| 5 | Improve prompt from eval failures | Partial | Prompt changes are tied to repeated eval failures and are followed by the full real eval gate. |
| 6 | Stabilize public API shape | Partial | Product API directly supports `explain_move(game_context, played_move, player_level) -> str` with PGN, FEN, UCI, player color, time control, and controlled failures. |
| 7 | Add durable eval reporting | Complete | JSONL eval records can produce a summary report with pass/fallback/retry rates, failure-code counts, latency, model metadata, Stockfish/Maia metadata, and manual-review fields. |
| 8 | Define promotion gates | Partial | Prompt/model/verifier changes compare against a frozen prior report and are promotable only when default checks pass and no-mock eval matches or improves prior results. |
| 9 | Broaden model/provider resilience | Partial | Provider has explicit timeout, retry/backoff policy, error taxonomy, model metadata, and optional comparison runs. |
| 10 | Prepare training data | Not started | Only verified context plus verified explanation plus reviewed eval records can enter training-data manifests. |

## Resume Checklist

At the start of each continuation:

1. Read this file, `docs/product/explanation-generation.md`, and
   `docs/development/quality-gates.md`.
2. Run `git status --short`.
3. Identify the first roadmap row that is not complete.
4. Implement the narrowest coherent slice for that row.
5. Update this roadmap status and the relevant product/development docs.
6. Run required checks and any opt-in real eval gate required by the change.
7. Commit a checkpoint.
