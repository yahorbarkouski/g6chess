# Product Understanding

For the full implementation target, read `end-goal.md` first. For the evidence
packet and LLM context design, read `context-engine.md`. This document is the
compact domain brief that supports both.

## Product Thesis

The system explains one chess move using verified evidence. It should feel like
a strong coach explaining the critical point of a position, not like a chat
layer over an engine.

The central promise:

```text
Given a game context, one played move, engine evidence, human-likeness evidence,
concept tags, and player level, return one clear explanation string describing
what happened and the quality of the move.
```

## Non-Negotiable Architecture

```text
PGN/FEN
  -> position parser
  -> Stockfish analysis
  -> Maia analysis
  -> rule and feature detectors
  -> structured incident packet
  -> coach LLM
  -> deterministic verifier
  -> final explanation string or controlled failure
```

The LLM is downstream of evidence. It is not the source of truth.

## Initial Implementation Bias

The first real implementation should be a narrow vertical slice, not broad
scaffolding:

```text
single PGN or FEN
  -> one analyzed move
  -> Stockfish evidence
  -> normalized incident packet
  -> deterministic checks
  -> prompted explanation
  -> verified explanation string
```

Only create directories, packages, services, or workers when this slice needs
them.

## Core Domain Objects

These concepts should stay stable even if the concrete storage or language
changes:

- `PositionContext`: FEN, side to move, move number, phase, legal moves.
- `PlayedMove`: UCI for computation, SAN for human display, player color/rating.
- `EngineLine`: move, score, score type, WDL, PV, depth/nodes, engine version.
- `StockfishAnalysis`: before-move top lines, played-move forced analysis,
  after-move opponent opportunity.
- `MaiaAnalysis`: played move probability, candidate probabilities by rating,
  human-common and teachable-gap signals.
- `CandidateMove`: a possible move with engine value, score loss versus best,
  human probability or unknown, findability, practicality, and recommendation
  policy.
- `ConceptTags`: tactical, strategic, and behavioral tags with detector source.
- `IncidentPacket`: complete evidence object for one explainable moment.
- `Explanation`: one verified coach-quality string returned by the API.
- `VerificationResult`: deterministic checks on evidence, LLM context, and later
  explanation output.
- `EvaluationRun`: frozen set results for comparing prompts/models.

## Evidence Boundaries

Stockfish answers:

- What was objectively strong?
- What changed after the move?
- What did the move allow?
- Was there a forced mate or tablebase result?

Maia answers:

- Was the played move human-common at this rating?
- Was the engine move likely to be missed?
- Does the move become more likely at higher ratings?
- Should the best move be recommended directly or explained as hard to find?

Rules and feature detectors answer:

- Which concepts are supported by board state or engine lines?
- Which material, king-safety, tactic, and behavior claims are safe to make?

The LLM answers:

- How should this be explained to this player?
- How should the move quality be communicated clearly?
- Which supported better move or idea should be mentioned?

## Product Quality Definition

An explanation is good only if it is:

- correct according to verified chess evidence
- clear for the target rating
- specific to the position
- actionable
- concise enough to read quickly
- specific enough to teach the move's key idea

An explanation is bad if it is fluent but unsupported.

## Known Failure Modes

- Evaluation perspective flips between White, Black, side to move, and player.
- Mate scores are treated as huge centipawn scores.
- The LLM invents a line not present in evidence.
- The explanation says a tactic exists because the words sound plausible.
- The model explains every mistake as "look for checks, captures, threats."
- Beginner explanations expose too much engine line detail.
- The training set rewards style over chess correctness.
- Synthetic data gradually drifts away from human-coach usefulness.
- User-imported games leak into global training data without rights.

## Data Policy Baseline

Use clean, explicitly permitted sources for global datasets. Lichess public data
is the expected default. Chess.com-derived data is excluded from global training
unless there is a license or written permission.

User-imported games may be used to answer that user's requested move explanation.
They must not enter global training unless the product has explicit rights and
the user/data policy allows it.
