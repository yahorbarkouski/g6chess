# ADR 0009: Deterministic Move Beauty

Date: 2026-04-30
Status: Accepted

## Context

The context engine already exposes objective move quality and move significance.
Those fields do not capture a different product need: identifying sound moves
whose idea is aesthetically interesting, such as a sacrifice, quiet resource,
forcing sequence, or final mating pattern.

This signal must stay compact. The API should not expose a prose reason because
that would create another explanation that needs generation and verification.

## Decision

The context engine will expose one field:

```json
{
  "beauty": {
    "label": "low|notable|beautiful|brilliant",
    "score": 0.0
  }
}
```

Beauty means:

```text
How aesthetically interesting a sound move is because it contains a non-obvious idea.
```

The formula is:

```text
soundness =
  1.00 for best/excellent
  0.85 for good
  0.55 for neutral
  0.00 for inaccuracy/mistake/blunder/missed_win

idea_quality =
  0.18 * surprise +
  0.24 * sacrifice +
  0.22 * forcing +
  0.16 * quiet_resource +
  0.12 * significance.score +
  0.08 * mate_pattern

beauty.score = round(soundness * (0.65 * idea_quality + 0.35 * significance.score), 2)
```

Labels are:

```text
0.00 - 0.24 -> low
0.25 - 0.49 -> notable
0.50 - 0.74 -> beautiful
0.75 - 1.00 -> brilliant
```

The first version uses only deterministic evidence:

- engine quality and significance
- played-move PV forcingness
- material investment in the PV
- moved-piece capture risk after the move
- human-likelihood probability when available
- immediate or short forced mate

## Consequences

Beauty stays separate from quality and significance. A move can be best but not
beautiful, critical but not beautiful, beautiful but not critical, or both
beautiful and critical.

The score is intentionally conservative. Famous moves can still vary with engine
depth because the PV may change, but moved-piece capture risk prevents sound
sacrifices from disappearing completely when Stockfish chooses a different
defensive line.

## Alternatives Considered

### Use significance as beauty

Rejected. A routine only move can be highly significant without being beautiful.

### Let the LLM judge beauty

Rejected. Beauty must be reproducible and auditable inside the context engine.

### Require full motif detectors first

Rejected. Motif detectors will improve the signal later, but the first version
can already use sacrifices, forcingness, quiet resources, mate, and human
surprise.

## Validation

This decision is working if tests prove:

- routine best moves remain low beauty
- unsound unusual moves get zero beauty
- quiet sound sacrifices can be brilliant
- sacrificial forcing moves can be beautiful without being critical
- real famous-game examples produce plausible beauty labels
