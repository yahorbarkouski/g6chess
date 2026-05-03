# Product End Goal

## Product Contract

Build one API:

```text
explain_move(game_context, played_move, player_level) -> explanation_string
```

The API explains one move from one game. It returns one coach-quality string.
The LLM may phrase the explanation, but it must not create chess truth.

## User Question

Answer exactly this:

```text
At this move in my game, what happened, how good was my move, and what should I understand?
```

## In Scope

- Reconstruct the position before and after the move.
- Verify the played move is legal.
- Use Stockfish for objective strength.
- Use Maia or clean human-frequency evidence for findability when available.
- Classify move quality from verified evidence.
- Explain the key better move or idea when evidence supports it.
- Adapt wording to player level and time situation.
- Return one concise explanation string.

## Out Of Scope

- Drills, plans, dashboards, puzzle generation, and full-game review.
- Opening repertoire advice.
- Multi-game personalization or weakness memory.
- Generic chess tutoring disconnected from the requested move.
- Any LLM-generated chess claim that is not backed by supplied evidence.

## Required Input Understanding

The request must provide or allow deriving:

- position before the move, from PGN, FEN, or normalized context
- exact played move, preferably UCI
- player color and player level
- legal moves, SAN, UCI, `fen_before`, and `fen_after`
- move number, time control, and clock data when available

Reject ambiguous input. Do not explain a move from SAN text alone.

## Internal Evidence

Before generation, build a structured evidence packet containing:

- position reconstruction and legality checks
- Stockfish top lines and forced played-move analysis
- score or mate values from the analyzed player's point of view
- candidate moves with objective value and findability or `unknown`
- move quality, significance, and beauty signals
- supported concept claims and forbidden claims
- provider, schema, prompt, and verifier version metadata where applicable

The explanation must be derived from this packet.

## Output Standard

The final public response is one coherent string. It should include:

- the move quality
- what changed in the position
- why the played move worked or failed
- the better move or idea when supported
- a caveat when the better move was hard for the player level or time situation
- the one key lesson for this position

It must not include raw engine dumps, unsupported tactics, invented PV moves,
multi-section lessons, or unrelated advice.

## Rating Adaptation

- Lower-rated players: use concrete language and simple forcing-move checks.
- Intermediate players: explain the idea, such as move order or initiative.
- Stronger players: include practical nuance without overexplaining basics.

Do not dumb down the chess. Choose the explanation depth that helps this player
understand this position.

## Verification Requirement

Before returning the string, verify:

- mentioned moves are legal or present in supplied evidence
- best-move and practical-alternative claims match the packet
- mate and centipawn claims stay separate
- side attribution and evaluation perspective are correct
- tactic, material, and concept claims are explicitly supported

If verification fails, regenerate or return a controlled failure. Never return
fluent but unsupported prose.

## First Useful Slice

```text
input: position/game context + one move + player color + player level
  -> reconstruct position
  -> run Stockfish
  -> classify move quality
  -> build evidence packet and LLM context
  -> generate one explanation string
  -> verify the string
output: one explanation string
```

Build this slice before adding broader product surfaces.

## Current Path

The truth-building part of the first slice is the context engine: position
reconstruction, Stockfish analysis, optional Maia likelihoods, move
classification, candidate policy, evidence packets, and compact `LLMContext`.

The explanation-generation slice described in
`docs/product/explanation-generation.md` now provides strict explanation schema,
deterministic baseline fallback, explanation verification, static provider tests,
retry behavior, an OpenRouter adapter, and the public
`explain_move(...) -> str` wrapper for FEN, explicit-ply PGN, or existing
context-request input.
