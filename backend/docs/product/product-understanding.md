# Product Understanding

## Thesis

This product is an evidence-grounded chess coach for one move. It is not an LLM
chess calculator and not a prose wrapper around raw engine output.

```text
Stockfish + Maia + rules + verifiers = truth and diagnosis
LLM = wording for one verified explanation
```

## System Boundary

```text
PGN/FEN
  -> position reconstruction
  -> Stockfish analysis
  -> optional Maia/frequency/tablebase/rule evidence
  -> evidence packet
  -> LLM context
  -> coach LLM
  -> deterministic verifier
  -> final explanation string or controlled failure
```

The LLM is downstream of evidence.

## Stable Domain Objects

- `PositionContext`: FEN, side to move, legal moves, move number, phase.
- `PlayedMove`: UCI for computation, SAN for display, player color/rating.
- `EngineLine`: move, score kind/value, WDL, PV, depth/nodes, engine version.
- `StockfishAnalysis`: top lines, forced played-move analysis, after-move reply.
- `MaiaAnalysis`: human-likeness probabilities by level and time control.
- `CandidateMove`: objective value, findability, practicality, policy.
- `ConceptTags`: tactical or strategic claims with source and confidence.
- `IncidentPacket`: complete evidence object for one move.
- `LLMContext`: compact verified generation input.
- `Explanation`: one verified user-facing string.
- `VerificationResult`: deterministic pass/fail checks and issue codes.

## Evidence Roles

Stockfish answers objective strength, score swing, best lines, and tactical
opportunities.

Maia or clean frequencies answer human likelihood and findability. They never
answer objective quality.

Rules and feature detectors answer which concrete claims are safe to make.

The LLM answers only how to phrase supported facts for the target player.

## Good Explanation

A good explanation is:

- correct according to verified chess evidence
- specific to the position
- clear for the player's level
- concise enough to read quickly
- useful enough to change the player's next decision

A fluent explanation with unsupported chess claims is a failure.

## Failure Modes

- evaluation perspective flips between White, Black, side to move, and player
- mate is converted into centipawns
- the LLM invents a legal-looking but unsupported line
- tactics are asserted from plausible wording instead of deterministic evidence
- every mistake becomes generic "checks, captures, threats" advice
- hard engine moves are presented as obvious
- Maia probability is treated as move quality
- training data uses unlicensed or user-imported games without rights

## Data Policy

Use clean, explicitly permitted sources for global datasets. Lichess public data
is the expected default. Do not use Chess.com-derived data for global training
without a license.

User-imported games may answer that user's request. They must not enter global
training unless explicit rights and product policy allow it.
