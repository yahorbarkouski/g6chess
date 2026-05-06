# Explanation Generation

## Purpose

Explanation generation turns a verified `LLMContext` and optional verified line
evidence into segmented UI copy plus one derived public explanation string.

This layer is downstream of the context engine. It does not calculate chess,
choose better moves, alter quality labels, or reinterpret Stockfish, Maia, or
deterministic rule evidence.

## Current Implementation

The context engine builds verified evidence packets and compact LLM contexts.
The explanation-generation package provides the downstream generation boundary
that makes model output safe to return.

Implemented pieces:

- explanation output and verification contracts
- segmented visible explanation output with optional verified hover line cards
- deterministic baseline renderer
- explanation-text verifier
- static coach provider tests
- generation service with retry and fallback behavior
- OpenRouter adapter defaulting to `openai/gpt-5.5`
- public `explain_move(...) -> str` wrapper for FEN + UCI move input, explicit
  PGN ply input, or an existing `MoveContextRequest`

Next work is broadening real-game LLM evals, manually accepting high-quality
records, and preparing source-rights-safe training manifests. Fine-tuning stays
behind those gates.

## Boundary

Input:

- `ContextResult` from `MoveContextBuilder`
- static prompt ID and version
- player-facing verbosity or rating adaptation settings when product-approved

Output:

- public: one explanation string
- rich clients: verified visible segments and optional hover line cards
- internal: private metadata with context version, prompt version, provider
  version, verifier version, attempts, schema-valid attempt text, fallback
  status, and failure codes

The model provider returns raw JSON to the generation layer. Internally the raw
output is segmented UI copy plus optional hover line cards. The one-move public
API still returns only the verified joined `explanation` string, while
`ExplanationResult` and game-analysis snapshots expose `segments` and
`line_cards` for richer clients. Public input errors raise controlled
`ExplanationInputError` exceptions instead of silently guessing.

The OpenRouter provider reads `OPENROUTER_API_KEY` from the environment or
`.env`, uses `openai/gpt-5.5` by default, and can be overridden with
`G6EXPLANATION_OPENROUTER_MODEL`. Provider resilience settings are explicit:
`G6EXPLANATION_OPENROUTER_TIMEOUT_SECONDS`,
`G6EXPLANATION_OPENROUTER_MAX_RETRIES`,
`G6EXPLANATION_OPENROUTER_RETRY_BACKOFF_SECONDS`, and optional
`G6EXPLANATION_OPENROUTER_MAX_TOKENS`. There is no default completion-token cap;
set the env var only for constrained experiments.

Current prompt version: `single_move_coach.v19`. Current explanation schema
version: `explanation_output.v4`. Version 2 made
`recommendation_policy` wording explicit so hard or hidden resources are framed
as review points, practical alternatives are framed as coaching options, and
`do_not_recommend` moves are never described as recommendations. Version 3 adds
stricter named-tactic wording rules and issue-specific retry repair
instructions after real evals showed unsupported tactic labels and
recommendation-policy retries. Version 4 makes the style contract concise,
neutral, and non-template-rigid: serious labels remain explicit, while good or
quiet moves may explain the supported purpose without repeating a visible
quality label every ply. Version 5 pushes the model further away from
verdict-first templates for every-move chains: non-bad moves should usually
lead with the concrete chess function, routine best moves should not say "best
move" unless that status is the lesson, and final prose must not expose
engine-meta phrases such as "engine best move" or "engine choice".
Version 6 also reduces verdict-first wording in the LLM-facing agenda itself:
non-bad `main_point` and `allowed_claims` prefer purpose/value-preservation
phrases over visible quality labels, and the prompt avoids "critical best move"
when a concrete chess role can say the same thing.
Version 7 removes "no sharper alternative needed" as the default non-bad
closing phrase; the model should stop after the concrete chess reason unless
the supplied context makes an alternative comparison the lesson.
Version 8 lets the non-bad agenda reuse deterministic played-move concept
claims, such as center, development, open-file, material, castling, en passant,
promotion, or outpost evidence, before falling back to generic "fits the
position" wording. Version 9 changes the raw model output from a flat
explanation string to visible `segments` plus optional verified `line_cards`.
It supplies compact line evidence to the model, asks for causal explanation
rather than "allowed MOVE" shorthand, and keeps plain-string compatibility by
joining segments after verification. Version 10 adds `line_card_anchor` so the
model keeps sentence-sized prose while marking the exact short phrase a rich UI
should highlight for each hover line card. Version 11 adds explicit
recapture/material-recovery wording guidance so the model does not turn a
recapture that restores balance into a material-winning claim. Version 12 adds
counterfactual wording guidance for unplayed alternatives and requires
trade/exchange material claims to stay trades or exchanges instead of becoming
material wins. Version 13 tells the model to prefer supplied concrete
board-feature facts over generic continuation wording. Version 14 removes
named-opening preparation concepts from the prompt contract: without explicit
opening metadata, the model should explain board geometry such as attacked
pieces, forks, center control, bishop diagonals, and open routes. Version 15
makes line cards less repetitive and more complete: line-card `why` text should
add the follow-through behind the visible segment, and verified line cards may
carry up to 16 SAN plies so longer forcing ideas, including mate nets, can be
shown without the old five-ply truncation. Version 16 keeps those full move
arrays for board visualization but asks visible text and card notes to avoid
reading out notation-heavy lines; explanations should mention only the move
notation needed for orientation and describe the rest as plain chess ideas. It
also requires card prose to copy the supplied line-evidence title and note so
the model does not invent notation-heavy "after move, move" summaries.
Version 17 removes "better idea" from generic alternative line-card wording and
from unplayed-alternative examples unless verified better-move evidence supports
that stronger label. Practical alternatives should stay practical alternatives.
Version 18 adds deterministic `diagnostic_tags` to the prompt payload for
review and coach-wording guidance: WDL edge cases, fast sound moves, time
scramble misses, slow blunders, increment context, no-blame forced moves, and
rating-level wording. These tags do not override objective quality,
significance, beauty, candidates, or typed concept claims.
Version 19 adds tactical-proof objection guidance: when the context supplies an
apparent-capture reply line, the model should explain why the capture fails or
why the moved piece is not simply free before using generic follow-up wording.
Version 20 makes immediate hung-piece mistakes concise: when a verified
material claim says the played move hung a named piece to the opponent's reply,
the model should use that simple material reason instead of generic follow-up,
pressure, or long-line wording.

## Contracts

The raw model response must validate against:

```json
{
  "segments": [
    {
      "text": "b5 was a blunder because it gave Black a forcing follow-up before the king could settle.",
      "line_card_id": "played-line",
      "line_card_anchor": "forcing follow-up"
    }
  ],
  "line_cards": [
    {
      "id": "played-line",
      "moves": ["b5", "Bxf3", "gxf3", "Rxb5", "Qd2", "Rh5", "h4", "Rxh4"],
      "title": "How the mistake gets punished",
      "why": "The follow-up shows the opponent keeping pressure after the mistake."
    }
  ]
}
```

`line_card_id` and `line_card_anchor` may be `null`. When a segment references a
line card, `line_card_anchor` is required, must be an exact short substring of
that segment text, and must not be a whole long sentence. Every line-card id and
move sequence must match supplied verified line evidence exactly. Line cards are
bounded at 16 SAN plies; their prose should explain the idea, not read the move
list aloud. The line-card title and `why` must also match supplied line evidence
exactly. The derived public string is the joined segment text.

The generation layer includes contracts for:

- raw explanation response
- verified explanation result
- explanation verification issue
- explanation verification result
- generation attempt metadata

Public `explain_move` accepts either:

- `explain_move(fen_before, played_move_uci, player_level, player_color=...)`
- `explain_move(pgn, player_level=..., player_color=..., pgn_ply=...)`
- `explain_move(move_context_request)`

PGN input requires an explicit ply. FEN input requires a played move. Ambiguous
mixed input is rejected.

Schema failures are hard failures. The verifier may retry once with concrete
issue codes, but invalid output must never be returned directly.

## Deterministic Baseline

The deterministic baseline renderer writes conservative segments from
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
  move, engine best, practical alternative, supplied line evidence, and
  explicitly allowed replies
- line-card id and move-sequence validation against supplied line evidence
- no unsupported PV continuations
- no unsupported mate, material, tactic, or concept claims
- direct "this move checkmates" wording requires mate evidence for that move,
  not only position-level forced-mate evidence; immediate-mate opponent replies
  are allowed only when the verified `after_line` is mate-in-one
- material prose requires a trusted typed `material` concept claim; unrelated
  words such as "piece" in development claims do not authorize material claims
- specific material prose, such as queen, rook, bishop, knight, pawn, or
  exchange, must match the trusted material claim text
- material-gain prose, such as winning, gaining, or picking up a pawn or piece,
  requires a trusted material-gain claim; recapture or material-recovery claims
  do not authorize gain wording
- material trade prose, such as trading or exchanging a bishop for a knight,
  requires a trusted material trade claim with the same material terms
- recapture prose requires a trusted typed `recapture` concept claim from recent
  move history
- tactic prose requires a trusted typed `tactic` concept claim that names the
  same tactic
- apparent-capture or "not free" prose requires trusted typed
  `tactical_proof` concept evidence and supplied reply-line moves
- attack prose about valuable pieces requires trusted `piece_activity` or
  `tactic` concept evidence naming the attacked material
- named opening-system prose requires explicit opening metadata; board geometry
  alone authorizes diagonal, route, center, activity, or pawn-structure wording,
  not an opening label
- concept language must be supported by typed `concept_claims`; free-form
  `allowed_claims` alone do not authorize strategic concepts
- quality-label consistency with `LLMContext.quality`; forced moves,
  inaccuracies, mistakes, blunders, and missed wins must be named, while best,
  excellent, good, and neutral moves may omit a visible label if they do not
  conflict with the context quality
- no internal prompt or context language such as "featured move", "move
  quality", "supplied context", `allowed_claims`, `concept_claims`, or
  `recommendation_policy`; no engine-meta wording such as "engine best move",
  "engine choice", or "engine line"
- best move and practical alternative consistency
- side-to-move and player-perspective sanity
- no direct recommendation of a `do_not_recommend` move
- positive wording about a non-bad played move is allowed even if the played
  candidate itself is not a future recommendation target
- hard or engine-like alternatives caveated when the context marks them hard

Because free-form chess language is hard to verify, prompts should keep wording
close to `main_point`, typed `concept_claims`, supplied move contexts,
`human_note`, and `allowed_claims`.

## Retry And Fallback

Generation flow:

```text
build verified context
derive verified line evidence
render baseline candidate
call provider for strict JSON
validate schema
verify explanation text
retry once with verifier failures if needed
return verified model segments plus joined string, verified baseline fallback, or
controlled failure
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
- apply bounded retries for transport errors and retryable provider HTTP
  statuses

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
Kasparov-Topalov, Capablanca-Tartakower, synthetic forced-move, synthetic
ordinary-blunder, high-WDL non-best, castling, en passant, promotion,
recapture-recovery, low-time, rating-ladder, Black-perspective, missed-win edge
cases, and Lichess CC0 puzzle-source and puzzle-solution positions.

Persist JSONL records and a Markdown report when running the real eval for
review:

```text
G6EXPLANATION_REAL_LLM_EVAL_OUTPUT=.evals/real-explanations.jsonl \
G6EXPLANATION_REAL_LLM_EVAL_REPORT=.evals/real-explanations.md \
G6EXPLANATION_RUN_REAL_LLM_EVAL=1 \
uv run pytest tests/g6explanation/real_game_evaluation/test_real_explanation_evaluation.py -q -s
```

The report summarizes pass, fallback, retry, failure-code, latency, model,
source, Stockfish, Maia, failed-attempt explanation text, and manual-review
fields.
Review categories should be used for failed, retried, or surprising records
before changing context policy, prompt rules, or verifier behavior. Durable
annotations live in
`docs/development/real-explanation-manual-reviews.json` and apply only when the
case id, model, attempts, and failure codes still match the reviewed record.

Promotion gates compare a candidate real-eval report against the prior promoted
report. A candidate is not promotable if it covers fewer cases, has more failed
or fallback cases, lowers pass rate, increases retries, increases failure-code
counts, or leaves manual-review-required records unresolved.

Training-data manifests are conservative. A generated explanation is eligible
only when the eval record passed verification, did not use fallback, has source
rights allowing global training, includes the verified `LLMContext`, has
provider/model/schema/context/prompt/verifier metadata, has Stockfish depth 16 or
deeper, includes the verified explanation text, and is manually marked
`accepted`.

Metrics:

- schema pass rate
- explanation verification pass rate
- unsupported move rate
- unsupported mate/material/tactic claim rate
- wrong best-move or recommendation rate
- rating fit, usefulness, latency, and cost

## Non-Goals

- ungated training data generation
- ungated fine-tuning
- model judging
- broad UI wording polish beyond verified explanation segments and line cards
- full-game review, dashboards, drills, or personalized memory
