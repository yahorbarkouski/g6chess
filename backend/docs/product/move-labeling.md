# Move Labeling

## Purpose

This document describes how the current implementation marks moves. It is a
description of today's behavior, not a proposal for ideal chess terminology.

The main source of truth is the context engine. It attaches three independent
signals to every analyzed move:

| Signal | Question it answers | Labels today | Product use |
| --- | --- | --- | --- |
| Move quality | Was the played move objectively good for the player? | `best`, `forced`, `excellent`, `good`, `neutral`, `inaccuracy`, `mistake`, `blunder`, `missed_win` | Primary verdict and explanation contract. |
| Significance | How much does this move deserve attention? | `low`, `moderate`, `high`, `critical` | Full-game analysis decides which moves need explanations from this. |
| Beauty | Was a sound move aesthetically or practically special? | `low`, `notable`, `beautiful`, `brilliant` | Optional praise or UI emphasis. It is not objective move quality. |

There is no current `great` quality label. `brilliant` exists only as a beauty
label, and can only apply to moves that are sound enough under the quality
policy.

## Where Labels Appear

The context engine builds one `EvidencePacket` and one compact `LLMContext` for
the move. Both include the quality, significance, and beauty signals. The
full-game API copies those same signals into each `GameMoveAnalysis` record:

```json
{
  "quality": "mistake",
  "significance": {
    "label": "critical",
    "score": 0.73
  },
  "beauty": {
    "label": "low",
    "score": 0.0
  }
}
```

The game-analysis API defaults to explaining only moves whose significance is
`critical`, although callers may request other significance labels.

The coach model may phrase the explanation, but it may not change these labels.
The explanation verifier requires serious quality labels to be named in the
visible explanation. `forced`, `inaccuracy`, `mistake`, `blunder`, and
`missed_win` must be explicit. `best`, `excellent`, `good`, and `neutral` may be
implicit when clearer chess wording is better.

## Move Quality

Move quality is the main answer to "how good was this move?" It is calculated
from Stockfish evidence normalized from the analyzed player's point of view.
Maia or human-frequency evidence does not change objective move quality.

The implementation compares:

- Stockfish's best top line, `analysis.top_lines[0]`
- the forced analysis of the played move, `analysis.played_line`
- centipawn loss versus best when both scores are centipawn scores
- WDL expected-score loss when both lines have WDL
- mate transitions, kept separate from centipawn scores

WDL expected score is calculated on a 0 to 1000 scale:

```text
expected_score = win + (draw * 0.5)
loss = best_expected_score - played_expected_score
```

### Quality Label Table

| Label | Current meaning | Main trigger |
| --- | --- | --- |
| `best` | The played move is the top objective move, or it directly checkmates. | Played UCI equals the first Stockfish line, or the played move is checkmate. Immediate checkmate is `best` even when another mating move was also available. |
| `forced` | The player had exactly one legal move. This is not praise or blame. | Legal move count is exactly one, unless the move checkmates first. The position can still be winning or losing. |
| `excellent` | Nearly no objective loss. | Normal centipawn loss is 20 or less, or WDL expected-score loss is 10 or less. |
| `good` | A small loss, or a still-winning non-best move. | Normal centipawn loss is 50 or less, or WDL loss is 25 or less. Also used by the high-WDL floor when the player still has at least 800/1000 Stockfish win probability after the move. |
| `neutral` | A small but noticeable loss, or a mate position that did not get worse. | Normal centipawn loss is 75 or less, or WDL loss is 45 or less. Also used when the player was already losing by forced mate and the move did not shorten that mate. |
| `inaccuracy` | A moderate objective loss. | Normal centipawn loss is 150 or less, or WDL loss is 80 or less. |
| `mistake` | A serious objective loss. | Normal centipawn loss is 300 or less, or WDL loss is 150 or less. |
| `blunder` | A very large non-mating loss, a newly allowed forced mate, or a worsened forced mate. | Normal centipawn loss is above 300, the move newly allows forced mate against the player, or it shortens an already forced mate against the player. A WDL-only blunder signal is capped at `mistake` unless centipawn loss is also in the blunder band. |
| `missed_win` | The best line had forced mate for the player, but the played move did not preserve a forced mate. | Mate-specific today. It does not currently mean every non-mating missed large advantage. |

### Normal Thresholds

When no mate or forced-move special case applies, the system assigns one label
from centipawn loss and one label from WDL loss, then takes the worse label with
one guardrail: WDL may make a non-mating move more serious, but it may not be the
only reason the move becomes a `blunder`. If centipawn loss is below the blunder
band, a WDL-only blunder signal is capped at `mistake`. This keeps sharp
positions from looking like both sides are constantly blundering when Stockfish
WDL swings harder than the centipawn evaluation.

| Loss type | `excellent` | `good` | `neutral` | `inaccuracy` | `mistake` | `blunder` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Centipawns | 0-20 | 21-50 | 51-75 | 76-150 | 151-300 | 301+ |
| WDL expected score | 0-10 | 11-25 | 26-45 | 46-80 | 81-150 | 151+ |

The high-WDL floor is a current guardrail: if the normal thresholds would mark
a non-mating move as `inaccuracy`, `mistake`, or `blunder`, but the played line
still has at least 800/1000 win probability for the player, the quality becomes
`good`.

### Quality Special Cases

Special cases are applied before the normal threshold table:

1. A played checkmate is `best`.
2. Exactly one legal move is `forced`.
3. Playing Stockfish's first top line is `best`.
4. Missing a forced mate for the player is `missed_win`.
5. Allowing forced mate against the player is usually `blunder`.
6. If the player was already losing by forced mate, the best defense is still
   `best`; a move that does not shorten the mate can be `neutral`; a move that
   shortens the mate is `blunder`.

The quality object also stores diagnostic fields:

| Field | Meaning |
| --- | --- |
| `score_delta_cp_player_pov` | Negative centipawn delta from the player's point of view, or `null` for mate cases. |
| `score_loss_vs_best_cp` | Non-negative centipawn loss versus best, or `null` for mate cases. |
| `wdl_delta_player_pov` | Signed change in win/draw/loss counts versus best, when WDL is available. |
| `wdl_expected_score_loss` | Non-negative WDL expected-score loss versus best, when WDL is available. |
| `severity_text` | A compact explanation of the score transition for downstream wording. |

## Move Significance

Significance answers "should this move get attention?" It is deliberately
separate from quality. A move can be `best` and `critical` if it is the only
move that preserves a large advantage, and a move can be `blunder` and
`critical` if it throws away the position.

The score is a 0.0 to 1.0 scalar. Mate transitions and played checkmates always
return `critical` with score `1.0`.

For non-mate cases, the reference line depends on what was played:

- if the played move is not Stockfish's first line, compare the played line to
  the first line
- if the played move is Stockfish's first line, compare it to the next distinct
  top line
- if there is no reference line, significance is `low` with score `0.0`

The numeric score is:

```text
cp_score = abs(cp_gap) / 300
wdl_score = abs(wdl_expected_score_gap) / 180
score = round(clamp(max(cp_score, wdl_score), 0, 1), 2)
```

| Significance label | Score range |
| --- | ---: |
| `critical` | 0.65 to 1.00 |
| `high` | 0.35 to 0.64 |
| `moderate` | 0.15 to 0.34 |
| `low` | 0.00 to 0.14 |

## Move Beauty

Beauty answers "was this sound move special?" It is not a replacement for
quality. A move can be `best` with `low` beauty, and a move cannot get a beauty
bonus if it is objectively bad.

The beauty score is 0.0 to 1.0. Its label thresholds are:

| Beauty label | Score range |
| --- | ---: |
| `brilliant` | 0.75 to 1.00 |
| `beautiful` | 0.50 to 0.74 |
| `notable` | 0.25 to 0.49 |
| `low` | 0.00 to 0.24 |

The scoring starts with a quality-based soundness multiplier:

| Quality label | Beauty soundness multiplier |
| --- | ---: |
| `best`, `excellent` | 1.00 |
| `good` | 0.85 |
| `forced`, `neutral` | 0.55 |
| `inaccuracy`, `mistake`, `blunder`, `missed_win` | 0.00 |

Non-mating `forced` moves are hard-capped at `low` beauty with score `0.0`
because the player had no meaningful choice.

The current beauty formula combines:

| Component | What it measures |
| --- | --- |
| Surprise | How uncommon the move appears for the player's level. Unknown human evidence defaults to a middle value. |
| Sacrifice | Whether the PV or moved piece shows material investment or capture risk. |
| Forcing sequence | How much of the first six PV moves are checks, captures, promotions, or mate. |
| Quiet resource | Whether a quiet move is significant and supported by another non-obvious idea. |
| Uniqueness | The move's significance score. |
| Mate pattern | Immediate checkmate or a short forced-mate score for the player. |

The implemented formula is:

```text
idea_quality =
  0.18 * surprise
  + 0.24 * sacrifice
  + 0.22 * forcing_sequence
  + 0.16 * quiet_resource
  + 0.12 * significance
  + 0.08 * mate_pattern

beauty_score = round(soundness * ((0.65 * idea_quality) + (0.35 * significance)), 2)
```

## Related Signals That Are Not Move Labels

The system also tracks candidate-move policy. These fields affect wording and
which move is featured, but they do not change the quality label.

| Field | Current values | Meaning |
| --- | --- | --- |
| Findability | `obvious`, `findable`, `hard`, `very_hard`, `engine_like`, `unknown` | How realistic the move was for the player, using Maia or static rules where available. |
| Recommendation policy | `recommend_directly`, `mention_with_caveat`, `use_as_practical_alternative`, `explain_as_hidden_resource`, `do_not_recommend` | Whether the explanation may recommend, caveat, or suppress the move. |
| Candidate role | `played_move`, `engine_best`, `practical_alternative`, `human_common_move`, and others | Why the candidate is present in the evidence packet. |

Important product rule: findability changes coaching language, not objective
move quality. A human-common move can still be a `mistake`, and a hard engine
resource can still be the objective best move.

## Reviewer Comment Targets

These are the highest-value questions for a strong chess reviewer:

| Area | Current behavior | Useful review question |
| --- | --- | --- |
| Terminology | No `great` label; quality uses `excellent`, `good`, `neutral`, and bad labels. | Should the public product add or rename labels, or keep the internal labels and map them to user-facing terms? |
| `missed_win` | Only used when the best line is forced mate for the player and the move misses that mate. | Should non-mating missed wins, such as throwing away a decisive advantage, get a separate label? |
| Centipawn thresholds | `excellent` 0-20, `good` 21-50, `neutral` 51-75, `inaccuracy` 76-150, `mistake` 151-300, `blunder` 301+. | Are these bands too harsh or too lenient across opening, middlegame, and endgame positions? |
| WDL thresholds | WDL loss can make a move worse than the centipawn band. | Do the WDL thresholds produce better human labels than centipawns alone? |
| High-WDL floor | A non-mating bad label becomes `good` when the played line still has at least 800/1000 win probability. | Is `good` the right label for a move that loses a lot of centipawns but keeps an overwhelmingly won position? |
| Forced moves | Exactly-one-legal-move positions become `forced`, not `best`, `mistake`, or `blunder`. | Should forced moves carry a separate position status, such as "forced but lost"? |
| Already-lost mate | A best defense in a forced-mate position is not a blunder; shortening the mate is a blunder. | Does this match how a coach should review hopeless positions? |
| Significance | Uses 300 cp or 180 WDL expected-score gap as the scale to `critical`. | Should more game context, such as phase or player rating, alter what counts as significant? |
| Beauty | Heuristic formula rewards sound surprise, sacrifice, forcing play, quiet resources, uniqueness, and mate patterns. | Does the formula produce labels a strong player would agree with, especially `brilliant`? |
| Explanation default | Full-game analysis explains `critical` moves by default. | Should `high` moves also be explained by default for game-review UX? |

## Source Locations

The current implementation is defined in:

- `src/g6explanation/context_engine/contracts.py`
- `src/g6explanation/context_engine/signals/quality.py`
- `src/g6explanation/context_engine/signals/significance.py`
- `src/g6explanation/context_engine/signals/beauty.py`
- `src/g6explanation/context_engine/signals/score_comparison.py`
- `src/g6explanation/context_engine/move_context_builder.py`
- `src/g6explanation/game_analysis/contracts.py`
- `src/g6explanation/game_analysis/analysis_runner.py`

The most relevant tests are:

- `tests/g6explanation/context_engine/test_move_context_builder.py`
- `tests/g6explanation/context_engine/signals/test_beauty.py`
- `tests/g6explanation/context_engine/test_real_game_significance_examples.py`
- `tests/g6explanation/explanation_generation/test_explanation_verification.py`
