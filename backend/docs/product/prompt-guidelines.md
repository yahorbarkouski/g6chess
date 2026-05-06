# Prompt Guidelines

## Prompt Job

The prompt turns verified LLM context and optional verified line evidence into
segmented UI copy for one explanation. It must not ask the model to calculate
chess, infer missing evidence, or choose a different best move.

## Generation Contract

Use a strict internal response schema:

```json
{
  "segments": [
    {
      "text": "visible explanation text",
      "line_card_id": null,
      "line_card_anchor": null
    }
  ],
  "line_cards": []
}
```

The public one-move API returns the joined `explanation` string for
compatibility. Rich clients may use verified `segments` and `line_cards` from
`ExplanationResult` or game-analysis snapshots. Private verifier metadata may be
stored outside the public response.

## Static Prompt Rules

The static prompt should say:

- Use only the supplied context.
- Return visible `segments` plus optional `line_cards`, not a flat explanation
  field.
- Keep segments as natural sentence-sized prose. Do not split prose into tiny
  text fragments just to create a highlight.
- If a segment references a line card, include `line_card_anchor`: the exact
  short phrase inside `text` that the UI should highlight. Prefer plain idea
  phrases such as "the follow-up", "the longer line", or "the mating pattern"
  over notation-heavy anchors.
- Keep the visible text compact but useful, usually two to five segments and
  roughly 35 to 90 words.
- Use a line card only when supplied `line_evidence` makes a hidden variation
  helpful; copy line-card ids and full move sequences exactly from the supplied
  evidence.
- The line-card `why` should add a deeper look at the variation's follow-through
  instead of repeating the visible segment in different words. Do not read the
  move sequence aloud in the card prose; the move array is for board playback.
  Copy the supplied line-evidence title and `why` exactly.
- Avoid notation-heavy prose. Mention the played move and at most one key reply
  or alternative when needed, then describe the idea in plain language.
- Do not describe variations as "after MOVE, MOVE..." in visible text or card
  prose. Avoid generic capture/takes wording in line-card prose unless the
  supplied claim makes the capture itself the lesson.
- Use a concise, neutral explanatory voice rather than direct address or
  broadcast commentary.
- Write like a compact game-review note that explains the chess reason, not like
  a verdict card.
- Do not force a rigid sentence template. One compact sentence is preferred,
  with two short sentences only when contrast is useful.
- Avoid repeated `MOVE was QUALITY because ...` constructions in full-game
  chains. The move may still be mentioned directly, but the sentence should
  usually be shaped around the concrete chess function.
- For non-bad moves, usually lead with the supported chess function: development,
  center control, pressure, piece improvement, a threat, simplification, holding
  the position, or another typed concept claim.
- When supplied typed claims include a sacrifice, make the sacrifice the main
  chess point. If the claim names a queen or rook and the deterministic beauty
  label is `beautiful` or `brilliant`, that beauty wording is allowed. Start
  visible prose from the sacrifice itself; smaller attacks, quiet-move framing,
  hidden-resource language, hard-to-find caveats, or generic follow-up details
  are optional support only and should not lead.
- When supplied typed claims expose concrete board features such as attacks on
  valuable pieces, forks, center control, opened diagonals, or cleared piece
  routes, prefer that concrete board fact over generic continuation wording.
- When supplied material claims say a bad move immediately hung or lost a named
  piece to the opponent's reply, make that simple material loss the main chess
  reason. Do not replace it with generic follow-up, pressure, or long-line
  wording.
- When supplied typed claims include tactical proof for an apparent capture, or
  line evidence includes an objection line, answer that objection directly:
  explain why the capture fails or why the moved piece is not simply free, and
  name the attempted capture and reply when the supplied claim names them,
  before using generic follow-up wording.
- State serious outcomes clearly: forced moves, inaccuracies, mistakes,
  blunders, and missed wins must be named. For best, good, excellent, or
  neutral moves, explain the supported purpose naturally instead of forcing a
  visible label every time.
- For routine best moves, do not say "best move" unless the position is
  high-significance, critical, mating, forced, or the best-move status is itself
  the lesson.
- Even in high-significance positions, avoid the phrase "critical best move"
  when clearer chess wording is available. Prefer concrete roles such as key
  capture, forcing check, open-file move, decisive resource, or strongest
  continuation when supported.
- Do not use generic value-preservation filler such as "without giving up
  meaningful value" by itself when a typed concept claim gives a concrete chess
  reason. If no concrete concept is supplied, keep the holding explanation
  short.
- Do not lean on "no sharper alternative needed" as a default ending. Use it
  only when alternative comparison is the lesson; otherwise stop after the
  concrete chess reason.
- Explain the main reason and key move or idea when supplied.
- When a bad move allows a key reply, explain why that reply is good for the
  opponent and bad for the player. Do not stop at "it allowed MOVE."
- Choose the smallest sufficient teaching point. Do not list every supplied
  candidate or concept.
- For good high-WDL or good-not-best moves, explain why the played move still
  worked instead of caveating with a hidden engine resource unless that hidden
  idea is the central lesson.
- Treat `diagnostic_tags` as deterministic review and wording guidance, not as
  new chess evidence. They may support time-pressure credit, WDL caveats,
  slow-blunder context, increment context, or no-blame forced-move wording, but
  objective `quality`, `significance`, `beauty`, candidates, and typed
  `concept_claims` remain the source of truth.
- Use time-pressure, clock, fast-move, increment, or spent-time wording only
  when `time_situation`, clock fields, `think_time_seconds`, or
  `diagnostic_tags` explicitly support it.
- For low-significance best, excellent, good, or neutral moves, avoid hidden
  resources, hard-to-find language, and comparison alternatives. One supported
  purpose for the played move is enough.
- For forced legal moves, keep the explanation centered on the lack of legal
  alternatives and avoid residual position-status detail unless it directly
  explains the move.
- Treat `engine_best_move` as objective truth and `practical_alternative` as a
  coaching option; do not collapse the two when both are supplied.
- Do not call a `practical_alternative` a better move unless typed
  `better_alternative` evidence supports that wording.
- For unplayed alternatives, use counterfactual wording, but keep the label
  aligned with the verified policy. Say "practical alternative" or "practical
  try" for `practical_alternative`; reserve "better move" or "better idea" for
  typed `better_alternative` evidence or direct-recommendation support. Do not
  phrase the alternative as if it was actually played.
- Respect recommendation policy fields; do not tell the player to play a
  `do_not_recommend` move.
- Add a caveat when the context marks the key move as hard to find.
- Match the player's level.
- Do not include raw engine data unless the context explicitly asks for it.
- Do not mention moves, lines, tactics, positional concepts, material wins, or
  mate claims that are not present in typed `concept_claims`, allowed claim text,
  supplied candidates, or supplied line evidence.
- Do not name opening systems or opening-family labels unless explicit opening
  metadata supplies that exact name. Without opening metadata, explain the
  verified board feature instead: center, diagonal, route, activity, or pawn
  structure.
- When a typed claim says a move recaptured or restored material balance, do not
  describe it as winning, gaining, or picking up material.
- When a typed claim says a move traded or exchanged material, describe it as a
  trade or exchange instead of a material win.
- Do not use named tactic labels such as fork, pin, skewer, back rank, or
  discovered attack unless a typed `tactic` concept claim names that same idea.
- On retries, repair the exact verifier issue instead of paraphrasing broadly;
  keep recommendation wording attached only to moves whose
  `recommendation_policy` allows it.
- Do not expose internal field names or workflow language such as
  `featured_move`, `move_quality`, `allowed_claims`, `concept_claims`,
  `recommendation_policy`, "verified context", "engine best move", "engine
  choice", "engine line", or "engine-listed".

## Dynamic Context Rules

Per-request context should provide:

- played move, quality, and severity
- player level and time situation
- main point
- objective best move, practical alternative, featured move, or key idea
- optional verified line evidence for hover cards
- candidate practicality and findability
- typed concept claims
- allowed claims
- diagnostic tags for review and coach-wording caveats
- forbidden claims when needed

Do not pass prompt instructions as dynamic fields. Keep the same LLM context
shape for production generation and future training examples.

## Claim Rules

The model may:

- summarize what changed
- explain why the played move worked or failed
- state serious move quality labels when the context requires them
- explain the supported better move or idea
- mention that a move was hard or easy to find when the context says so
- mention time pressure, fast play, increment context, or spent time when the
  context says so

The model may not:

- invent candidate moves or PV continuations
- override Stockfish, tablebase, legal-move, or verifier evidence
- turn Maia probability into quality
- claim material gain, mate, or tactics without allowed evidence
- claim an apparently capturable piece is safe, not free, or cannot be won
  cleanly without typed tactical-proof evidence
- turn a recapture or material recovery claim into a material-winning claim
- turn a trade or exchange claim into a material-winning claim
- claim positional concepts without typed concept-claim evidence
- silently change the best move or recommendation policy
- use vague claims such as "wins material" without deterministic support
- invent clock pressure or time-usage explanations without supplied time fields
  or diagnostic tags

## Rating Wording

- Beginner: one concrete reason and one concrete habit.
- Intermediate: the positional or tactical idea behind the move.
- Advanced: practical nuance, move order, and initiative without long lines.

Keep the chess specific. Do not hide uncertainty with confident generic advice.

## Template Shape

```text
System:
You are a chess coach for one verified move. The chess truth is already decided
by deterministic evidence. Phrase that evidence as concise, useful UI copy.
Return JSON with visible segments and optional verified line cards. Do not
introduce unsupported moves, lines, tactics, mate claims, or material claims.

User:
Write one explanation for this verified move context:
{llm_context_json}
Use only these optional line cards:
{line_evidence_json}
```

The exact wording can evolve, but every prompt version must preserve the claim
rules above.

## Verification Loop

1. Generate schema-valid JSON.
2. Join visible segments into the public explanation string.
3. Verify mentioned moves, line-card ids and move sequences, claims,
   mate/centipawn language, side attribution, and recommendation consistency.
4. Regenerate with verifier issues or return a controlled failure.
5. Never ship an explanation that fails verification.

## Prompt Versioning

Record prompt ID, prompt version, schema version, context version, provider
versions, and verifier version for generated examples. A prompt is promotable
only when it improves or matches the current baseline on frozen evals and
deterministic verification.
