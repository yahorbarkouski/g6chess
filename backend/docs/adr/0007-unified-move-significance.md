# ADR 0007: Unified Move Significance

Date: 2026-04-30
Status: Accepted

## Context

The context engine needs to tell the explanation model how much the requested
move deserves emphasis. Earlier discussion separated ideas like move impact and
choice criticality, but that adds conceptual overhead and exposes distinctions
that are not useful for the first API.

The product needs one strict field that is easy to test and hard for an LLM to
misinterpret.

## Decision

The context engine will expose one field:

```json
{
  "significance": {
    "label": "low|moderate|high|critical",
    "score": 0.0
  }
}
```

No prose reason is stored with significance.

The formula is:

1. Mate transitions are `1.0`.
2. If the played move is not the engine best move, compare the played move to the
   engine best move.
3. If the played move is the engine best move, compare it to the next distinct
   engine line.
4. Compute:

```text
cp_component = clamp(abs(cp(played) - cp(comparison)) / 300, 0, 1)
wdl_component = clamp(abs(expected_score(played) - expected_score(comparison)) / 180, 0, 1)
score = round(max(cp_component, wdl_component), 2)
```

Where:

```text
expected_score = win + 0.5 * draw
```

Labels are:

```text
0.00 - 0.14 -> low
0.15 - 0.34 -> moderate
0.35 - 0.64 -> high
0.65 - 1.00 -> critical
```

## Consequences

The LLM receives a compact signal instead of another prose explanation. The
metric is deterministic, testable, and based on Stockfish/WDL evidence rather
than model-generated justification.

This keeps significance separate from human findability. A move can be highly
significant and still hard to find.

## Alternatives Considered

### Separate move impact and choice criticality fields

Rejected. The distinction is useful internally for discussion, but too verbose
for the current context contract.

### Significance with a generated reason

Rejected. The formula is the reason. Prose reasons would create another field
that must be generated, verified, and debugged.

### Use move quality label as significance

Rejected. A best move can be highly significant if the alternatives are much
worse, and a mistake can be low significance if the engine gap is tiny.

## Validation

This decision is working if tests prove:

- small gaps produce low significance
- large bad-move gaps produce critical significance
- best moves can be critical when much better than the second line
- WDL gaps can drive significance even when centipawns are close
- mate transitions always produce critical significance
