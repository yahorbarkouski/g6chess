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

The game-analysis import API may acquire a canonical PGN from a user-submitted
Chess.com live-game URL, Lichess game URL, or pasted PGN before starting that
same orchestration.
This import layer is source acquisition only; it does not create chess truth or
new training rights. Imported player levels are derived from source ratings:
Chess.com and Lichess imports require both side ratings from source data, and
pasted PGNs use Elo headers unless the caller provides explicit side ratings.
The import layer must not invent fallback ratings.

## Rules

- Keep drills, dashboards, training plans, and memory systems outside the
  chess-truth layer.
- Full-game analysis must be implemented as repeated verified one-move analyses
  plus job orchestration, not as a parallel chess engine policy.
- Normalize scores from the analyzed player's point of view.
- Keep mate scores separate from centipawns.
- Store UCI for computation and SAN only for display.
- Use Lichess CC0 exports as the default open source for global training data.
- Opening-book metadata may use the CC0 Lichess openings dataset for display
  context and continuation previews, but it must not override Stockfish move
  quality or explanation-verification policy.
- Do not train global models on user-imported games or Chess.com-derived data
  without explicit rights or prior written authorization.
- Mark Chess.com, Lichess, and manual PGN imports as
  `allows_global_training=false` in source metadata unless a future explicit
  source-rights policy authorizes a narrower use.

## Validation

Work is aligned when it improves the correctness, clarity, or verification of
one evidence-grounded move explanation.
