# ADR 0001: Product Truth Boundary

Date: 2026-04-30
Status: Accepted

## Decision

The core product truth boundary is one API that explains one move from one game:

```text
explain_move(game_context, played_move, player_level) -> explanation_string
```

Chess truth comes from deterministic reconstruction, Stockfish, optional Maia or
clean human-frequency evidence, rules, and verifiers. The LLM only words one
verified explanation string.

The asynchronous game-analysis API may orchestrate this one-move pipeline across
every ply of a PGN and persist partial Redis snapshots for polling. It does not
define separate move-quality, significance, beauty, candidate, concept, or
explanation policy.

## Rules

- Keep drills, dashboards, training plans, and memory systems outside the
  chess-truth layer.
- Full-game analysis must be implemented as repeated verified one-move analyses
  plus job orchestration, not as a parallel chess engine policy.
- Normalize scores from the analyzed player's point of view.
- Keep mate scores separate from centipawns.
- Store UCI for computation and SAN only for display.
- Use Lichess CC0 exports as the default open source for global training data.
- Do not train global models on user-imported games or Chess.com-derived data
  without explicit rights or prior written authorization.

## Validation

Work is aligned when it improves the correctness, clarity, or verification of
one evidence-grounded move explanation.
