# Prompt Guidelines

## Prompt Job

The prompt turns verified LLM context into one explanation string. It must not
ask the model to calculate chess, infer missing evidence, or choose a different
best move.

## Generation Contract

Use a strict internal response schema:

```json
{
  "explanation": "string"
}
```

The public API returns the `explanation` string only. Private verifier metadata
may be stored outside the public response.

## Static Prompt Rules

The static prompt should say:

- Use only the supplied context.
- Return exactly one concise explanation string.
- Use a concise, neutral explanatory voice rather than direct address or
  broadcast commentary.
- Do not force a rigid sentence template. One compact sentence is preferred,
  with two short sentences only when contrast is useful.
- State serious outcomes clearly: forced moves, inaccuracies, mistakes,
  blunders, and missed wins must be named. For best, good, excellent, or
  neutral moves, explain the supported purpose naturally instead of forcing a
  visible label every time.
- Explain the main reason and key move or idea when supplied.
- Choose the smallest sufficient teaching point. Do not list every supplied
  candidate or concept.
- For good high-WDL or good-not-best moves, explain why the played move still
  worked instead of caveating with a hidden engine resource unless that hidden
  idea is the central lesson.
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
- Respect recommendation policy fields; do not tell the player to play a
  `do_not_recommend` move.
- Add a caveat when the context marks the key move as hard to find.
- Match the player's level.
- Do not include raw engine data unless the context explicitly asks for it.
- Do not mention moves, lines, tactics, positional concepts, material wins, or
  mate claims that are not present in typed `concept_claims`, allowed claim text,
  or supplied candidates.
- Do not use named tactic labels such as fork, pin, skewer, back rank, or
  discovered attack unless a typed `tactic` concept claim names that same idea.
- On retries, repair the exact verifier issue instead of paraphrasing broadly;
  keep recommendation wording attached only to moves whose
  `recommendation_policy` allows it.
- Do not expose internal field names or workflow language such as
  `featured_move`, `move_quality`, `allowed_claims`, `concept_claims`,
  `recommendation_policy`, "verified context", or "engine-listed".

## Dynamic Context Rules

Per-request context should provide:

- played move, quality, and severity
- player level and time situation
- main point
- engine best move, practical alternative, featured move, or key idea
- candidate practicality and findability
- typed concept claims
- allowed claims
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

The model may not:

- invent candidate moves or PV continuations
- override Stockfish, tablebase, legal-move, or verifier evidence
- turn Maia probability into quality
- claim material gain, mate, or tactics without allowed evidence
- claim positional concepts without typed concept-claim evidence
- silently change the best move or recommendation policy
- use vague claims such as "wins material" without deterministic support

## Rating Wording

- Beginner: one concrete reason and one concrete habit.
- Intermediate: the positional or tactical idea behind the move.
- Advanced: practical nuance, move order, and initiative without long lines.

Keep the chess specific. Do not hide uncertainty with confident generic advice.

## Template Shape

```text
System:
You are a chess coach for one verified move. The chess truth is already decided
by deterministic evidence. Phrase that evidence as a concise, neutral
explanation. Return JSON with one field, "explanation". Do not introduce
unsupported moves, lines, tactics, mate claims, or material claims.

User:
Write one explanation for this verified move context:
{llm_context_json}
```

The exact wording can evolve, but every prompt version must preserve the claim
rules above.

## Verification Loop

1. Generate schema-valid JSON.
2. Extract `explanation`.
3. Verify mentioned moves, claims, mate/centipawn language, side attribution,
   and recommendation consistency.
4. Regenerate with verifier issues or return a controlled failure.
5. Never ship an explanation that fails verification.

## Prompt Versioning

Record prompt ID, prompt version, schema version, context version, provider
versions, and verifier version for generated examples. A prompt is promotable
only when it improves or matches the current baseline on frozen evals and
deterministic verification.
