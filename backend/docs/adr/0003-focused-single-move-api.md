# ADR 0003: Focused Single-Move Explanation API

Date: 2026-04-30
Status: Accepted

## Context

ADR 0002 defined a broad chess improvement system with drills, weakness memory,
and training plans. That is too wide for the current product target.

The intended implementation is narrower: one API that explains one particular
move from one game context for a player at a given level.

## Decision

The current product target is:

```text
explain_move(game_context, played_move, player_level) -> explanation_string
```

The API returns one coach-quality explanation string. The string should explain
what happened, communicate the quality of the move, and mention the better move
or idea only when supported by evidence.

The implementation may use internal structured packets, Stockfish, Maia, concept
detectors, and deterministic verification. Those are internal mechanisms. The
public product output remains one explanation string.

The following are out of scope for the current implementation target:

- drills
- training plans
- weakness memory
- full-game review
- dashboards
- spaced repetition
- personalization across many games
- puzzle generation

## Consequences

Future implementation should optimize for correctness, clarity, and coaching
quality of the single explanation string.

This makes the first vertical slice smaller and easier to test:

```text
game context + one move + player level
  -> verified evidence packet
  -> generated explanation string
  -> deterministic verification
  -> API response
```

The architecture should still preserve evidence-first design. The LLM phrases
the explanation but does not create chess truth.

## Alternatives Considered

### Broad chess improvement platform

Rejected for now. It is too much product surface before the single-move
explanation contract works.

### Full-game review

Rejected for now. Selecting moments across a game is a separate product problem.
The current API receives the move to explain.

### Structured multi-field response

Rejected as the primary public contract. Internally structured output is useful
for verification, but the user-facing API target is one explanation string.

## Validation

This decision is working if implementation work:

- exposes or moves toward one focused explain-move API
- accepts enough context to reconstruct the exact position
- returns one explanation string
- includes move quality in the explanation
- adapts language to player level
- verifies that the explanation is supported by evidence
- avoids adding drills, training plans, dashboards, or memory systems
