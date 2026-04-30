# End Goal

This document defines the focused product we are building first.

The target is not a broad chess training platform. It is one API that explains
one move from one game as clearly as an excellent chess coach would.

## One-Sentence Goal

Build a single chess explanation API that receives a game context, one played
move, and the player's level, then returns one clear explanation string
describing what happened and the quality of the move.

## Product Scope

The product is an evidence-grounded move explainer.

It answers this user question:

```text
In this game, at this exact move, what happened, how good or bad was my move,
and what should I understand from it?
```

That is the whole first product.

## Explicit Non-Goals

Do not build these into the initial product:

- drills
- training plans
- weekly plans
- spaced repetition
- weakness memory
- full-game review
- dashboards
- opening repertoire advice
- generic chess tutoring
- puzzle generation
- personalization across many games
- multi-mode product surfaces

Those may become future products, but they are not part of the current
implementation target.

## The Single API

The implementation should converge on one public capability:

```text
explain_move(game_context, played_move, player_level) -> explanation_string
```

The exact transport can be decided later. The product contract is stable:

- input includes enough game context to reconstruct the position before and
  after the move
- input identifies the exact move to explain
- input includes the player side and level
- output is one user-facing explanation string

The response may be wrapped in JSON for transport, but the product output is a
single explanation string, not a multi-part lesson plan.

## Required Input Understanding

The API must understand the move in context. It should not explain a move from
SAN text alone.

The input should provide or allow deriving:

- game moves or FEN before the move
- played move
- player color
- player rating or level
- time control if available
- move number
- legal moves
- position before the move
- position after the move

The implementation may accept PGN, FEN plus move, or a normalized request shape.
That is a future implementation choice. The product requirement is that the
system explains the actual move in the actual game position.

## Internal Evidence Contract

Even though the public output is one string, the system should internally build
a structured evidence packet.

That packet should answer:

- Was the move legal?
- What was the position before the move?
- What did the move change?
- What was Stockfish's view before the move?
- What was Stockfish's view of the played move?
- What did the move allow after it was played?
- What was the best or most practical alternative?
- How realistic was each proposed alternative for this player's level and time
  situation?
- How large was the evaluation or WDL swing?
- Was the move a blunder, mistake, inaccuracy, good move, or neutral move?
- Was the move human-common at this player level, if Maia evidence is available?
- Which tactical or strategic concepts are safely supported?

The explanation string should be derived from this evidence. The LLM may phrase
the explanation, but it may not create chess truth.

## Output Standard

The output must be one coherent string.

It should normally include:

- move quality
- what changed in the position
- why the played move worked or failed
- the better move or better idea when relevant
- a caveat when the best move was hard to find for the player's level or time
  situation
- the key concept the player should understand
- language appropriate to the player's level

It should not include:

- raw engine dumps
- long principal variations
- multiple independent sections
- drills
- training recommendations
- unrelated chess advice
- unsupported tactical claims
- moves not present in the evidence packet

## Coaching Standard

The string should sound like a strong coach explaining one moment, not like an
engine translating centipawns into prose.

Bad:

```text
This is a blunder because Stockfish says the evaluation goes from +0.4 to -1.9.
Best move was Qh5.
```

Better:

```text
This was a serious mistake: g4 looks active, but it spends a tempo before you
deal with Black's forcing reply. Qh5+ was the important move because it checks
first and keeps Black reacting; after g4, Black gets time to consolidate and
your attack loses its force.
```

The explanation should be short enough to read quickly and specific enough that
the player understands the chess reason.

## Rating-Level Adaptation

The same move should be explained differently depending on the player's level.

For a lower-rated player, prefer concrete language:

```text
This move was a mistake because it ignored a forcing check. Before making a
quiet attacking move, first look for checks and captures.
```

For an intermediate player, include the idea:

```text
The problem is move order. Qh5+ forces Black to respond immediately, while g4
lets Black improve the defense before your attack creates a real threat.
```

For a stronger player, include practical nuance:

```text
The issue is not that g4 is impossible in principle; it is that the forcing move
comes first. Qh5+ uses tempo to keep the initiative, while g4 lets Black solve
the immediate tactical problem.
```

The goal is not to simplify everything. The goal is to choose the most useful
level of explanation for the player.

## Public API Success Criteria

The first product is successful when the API can reliably:

- reconstruct the relevant position from the request
- verify the played move
- analyze the move with objective chess evidence
- classify the move quality
- generate one clear explanation string
- adapt that string to the player's level
- avoid invented moves and unsupported claims
- reject or fail clearly when the input is insufficient

## Highest-Level Implementation Shape

The system should have these internal capabilities:

```text
request intake
  receives game context, move identifier, player side, and player level

position reconstruction
  identifies fen_before, fen_after, legal moves, SAN, UCI, side to move

evidence generation
  runs Stockfish and optional Maia/rule detectors for this one move

incident construction
  normalizes the evidence into one move-explanation packet

coach generation
  produces one explanation string from the packet

verification
  checks that the explanation does not contradict the packet

api response
  returns the final explanation string or a clear failure
```

These are capabilities, not required early directories.

## Verification Standard

The verifier exists to protect the single string.

Before returning the explanation, the system should check:

- any mentioned move is legal or present in supplied engine evidence
- claimed best move matches the evidence or is marked as a practical alternative
- mate and centipawn claims are not confused
- side attribution is correct
- move quality matches the normalized swing
- tactical claims are supported by evidence
- the explanation is appropriate for the player level

If verification fails, the system should regenerate or return a controlled
failure. It should not return fluent but unsupported prose.

## Product Decision Heuristics

When choosing between implementation options, prefer the option that:

- improves correctness of the one explanation string
- makes the evidence packet more reliable
- makes unsupported claims easier to catch
- improves rating-appropriate phrasing
- keeps the API contract small
- avoids building future product modes early

Defer anything whose main value is:

- multi-game personalization
- broad UI surface area
- drill generation
- training recommendations
- analytics dashboards
- large dataset work before the single-move contract works

## First Useful Slice

The first useful slice is:

```text
input:
  one position or game context
  one played move
  player color
  player level

internal:
  reconstruct position
  analyze with Stockfish
  classify move quality
  build evidence packet
  generate explanation
  verify explanation

output:
  one explanation string
```

This slice should be small, real, and testable.

## Final Product Promise

The API should be able to return an explanation like:

```text
This was a mistake: the move looks active, but it ignores Black's immediate
forcing reply. The important idea was to check first with Qh5+, because that
keeps Black defending; after your move, Black gets time to stabilize and your
attack loses momentum.
```

That is the implementation target.
