# ADR 0001: Product Truth Boundary

Date: 2026-04-30
Status: Accepted

## Decision

The product is one API that explains one move from one game:

```text
explain_move(game_context, played_move, player_level) -> explanation_string
```

Chess truth comes from deterministic reconstruction, Stockfish, optional Maia or
clean human-frequency evidence, rules, and verifiers. The LLM only words one
verified explanation string.

## Rules

- Keep drills, dashboards, full-game review, training plans, and memory systems
  out of the first product.
- Normalize scores from the analyzed player's point of view.
- Keep mate scores separate from centipawns.
- Store UCI for computation and SAN only for display.
- Use Lichess CC0 exports as the default open source for global training data.
- Do not train global models on user-imported games or Chess.com-derived data
  without explicit rights or prior written authorization.

## Validation

Work is aligned when it improves the correctness, clarity, or verification of
one evidence-grounded move explanation.
