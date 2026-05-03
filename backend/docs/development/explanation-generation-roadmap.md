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
- durable real-eval JSONL and Markdown reports
- first expanded no-mock edge-case batch for castling, en passant, promotion,
  low-time play, beginner/intermediate/advanced rating levels,
  Black-perspective missed wins, and high-WDL good-not-best moves
- conservative deterministic concept detectors for material, king safety,
  development, open files, passed pawns, weak squares/outposts, initiative, and
  forcing move facts

Active phase:

```text
verifier hardening -> prompt changes only from eval failures -> API stabilization
```

## Ten-Step Track

| # | Step | Status | Exit criteria |
|---|---|---|---|
| 1 | Expand the real eval suite | Partial | No-mock cases include quiet positional moves, missed wins, already-lost mate defenses, promotions, castling, en passant, low-time cases, rating ladder cases, Black-perspective cases, and more high-WDL good-not-best moves. |
| 2 | Review eval output manually | Complete | Every failed, retried, or surprising record has a review category: context missing evidence, wrong context policy, prompt issue, verifier too weak, verifier too strict, model wording issue, or provider/runtime issue. |
| 3 | Add structured concept evidence | Complete | Deterministic tags exist for supported material, king safety, development, open files, passed pawns, weak squares, initiative, and forcing concepts before the LLM may mention them. |
| 4 | Harden the explanation verifier | Partial | Verification uses structured claims wherever possible for mentioned moves, concepts, material, mate, tactics, recommendation policy, side attribution, and best/practical-alternative language. |
| 5 | Improve prompt from eval failures | Partial | Prompt changes are tied to repeated eval failures and are followed by the full real eval gate. |
| 6 | Stabilize public API shape | Partial | Product API directly supports `explain_move(game_context, played_move, player_level) -> str` with PGN, FEN, UCI, player color, time control, and controlled failures. |
| 7 | Add durable eval reporting | Complete | JSONL eval records can produce a summary report with pass/fallback/retry rates, failure-code counts, latency, model metadata, Stockfish/Maia metadata, and manual-review fields. |
| 8 | Define promotion gates | Partial | Prompt/model/verifier changes compare against a frozen prior report and are promotable only when default checks pass and no-mock eval matches or improves prior results. |
| 9 | Broaden model/provider resilience | Partial | Provider has explicit timeout, retry/backoff policy, error taxonomy, model metadata, and optional comparison runs. |
| 10 | Prepare training data | Not started | Only verified context plus verified explanation plus reviewed eval records can enter training-data manifests. |

## Checkpoint Log

- 2026-05-03: expanded the real no-mock eval suite from 8 to 12 cases with
  castling, en passant, promotion, low-time, rating-ladder, Black-perspective,
  and missed-win coverage. Added typed concept claims and verifier support for
  special played-move facts. Latest full real eval passed 12/12 with Stockfish
  depth 16, real Maia, and OpenRouter `openai/gpt-5.5-20260423`; no fallback
  was used. `capablanca-g4` required one retry for
  `recommendation_policy_violation`, so it became the first manual-review item.
- 2026-05-03: added durable manual-review annotations for real eval records.
  `capablanca-g4` and `en-passant-intermediate` are classified as
  `model_wording_issue` for `openai/gpt-5.5-20260423` runs with two attempts and
  `recommendation_policy_violation`; the verifier correctly blocked the first
  attempts and the retries were acceptable. The repeated failure code is now
  evidence for a later prompt-policy clarification, not a context-policy change.
- 2026-05-03: added conservative deterministic concept evidence for concrete
  material changes, development from home squares, rook/queen open-file use,
  passed-pawn advances, knight outposts, checking initiative, and forced-mate
  king-safety failures. Material prose now requires a trusted `material`
  concept claim instead of incidental words such as "piece" in other concepts.
  The first full real eval exposed that promotion checks also need a typed
  `forcing_move` claim; after adding it, the full no-mock eval passed 12/12 with
  0 fallbacks and 0 retries.
- 2026-05-03: hardened material verification so specific claims such as queen,
  rook, bishop, knight, pawn, or exchange require the trusted material claim to
  name that material. Generic material evidence no longer authorizes a specific
  invented piece claim. Full no-mock eval passed 12/12 with 0 fallbacks and 0
  retries after this verifier change.
- 2026-05-03: bumped the prompt to `single_move_coach.v2` to clarify
  `recommendation_policy` wording after repeated reviewed
  `recommendation_policy_violation` retries. The change is evidence-backed by
  the manual-review log rather than a style preference. The first v2 real eval
  still found one high-WDL retry, which exposed a verifier-policy issue:
  positive language about a non-bad played move should not be treated like
  recommending an unplayed `do_not_recommend` alternative.
- 2026-05-03: after narrowing that verifier rule, the full prompt-v2 real eval
  passed 12/12. One `fools-mate-g4-blunder` retry for `unsupported_tactic_claim`
  was reviewed as `model_wording_issue`; the verifier correctly blocked an
  unsupported tactic phrase and the retry used supported king-safety/mate
  evidence.

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
