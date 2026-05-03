# Context Engine

## Purpose

The context engine converts one requested move into verified evidence and a
compact LLM context for one explanation string.

It decides chess truth, practical relevance, and safe claims. The LLM only
phrases those decisions.

## Artifacts

### Evidence Packet

Complete internal truth record used for verification, tests, debugging, evals,
and future training data. It may contain raw engine details and diagnostic
metadata.

### LLM Context

Small deterministic projection used for generation. It contains only facts,
decisions, typed concept claims, and allowed claim text needed to write one
explanation.

Do not put generic prompt rules, tone rules, or style instructions in the LLM
context. Put them in the static prompt.

## Required Inputs

- game context, such as PGN or FEN before the move
- exact played move, preferably UCI
- player color
- player level or rating

Useful optional inputs:

- time control, clock before move, increment
- move number or ply
- recent move history
- opponent rating and game result

Reject ambiguous input.

## Required Evidence

Deterministic board state is mandatory:

- valid `fen_before`
- side to move and player color
- legal move list
- played move legality
- SAN and UCI notation
- correct `fen_after`
- castling and en passant rights

Stockfish is mandatory for production-quality explanations:

- top candidate moves
- forced analysis of the played move
- after-move reply or opportunity
- centipawn or mate score
- WDL when available
- engine version, options, depth/nodes, and MultiPV metadata
- depth 16 or deeper for every depth-limited production, evaluation,
  visualization, or integration-test context
- line depth 16 or deeper for every non-static Stockfish-backed packet, including
  node-limited runs

Maia, empirical frequencies, Syzygy, and concept detectors are optional. They
may improve wording, but they must not override deterministic legality,
tablebase truth, or Stockfish objective strength.

## Candidate Rules

Every candidate exposed to the LLM must include:

- UCI and SAN
- role, such as `played_move`, `engine_best`, or `practical_alternative`
- objective score or mate value from the player's point of view
- score loss versus best when available
- short PV only when useful and legal
- findability or `unknown`
- forcing tier, such as `check`, `recapture`, `ordinary_capture`, or `quiet`
- Maia player and comparison buckets when Maia evidence is available
- practicality category
- recommendation policy

Recommendation policies:

- `recommend_directly`: strong and reasonably findable
- `mention_with_caveat`: important but hard to find
- `use_as_practical_alternative`: close to best and easier to find
- `explain_as_hidden_resource`: critical because it was hard to see
- `do_not_recommend`: useful internally, not for the explanation

Findability changes wording, not objective move quality. If Maia maps the player
level and stronger comparison level into the same public rating bucket, the
stronger comparison probability is unavailable rather than copied from the
player-level probability.

## Core Signals

Move quality answers whether the move was good. Normalize all score deltas from
the analyzed player's point of view. Represent mate separately from centipawns.
Use absolute WDL only for engine lines and signed WDL deltas only for quality
comparison. Use `forced` when the player had exactly one legal move; the
position may still be winning or losing, but the move itself is not a mistake.
Immediate checkmate is `best` even when another checkmate is also available. If
the best line is already forced mate against the player, the engine-best defense
is still `best`; only newly allowing mate or shortening the mate should be
treated as a mate-transition blunder. If the played move preserves high
Stockfish WDL win probability, do not label the move as a normal mistake or
blunder solely because it was not the top engine move.

Move significance answers how much this move deserves emphasis. It is one strict
`label` plus `score`; do not add generated prose reasons. Labels are `low`,
`moderate`, `high`, and `critical`. Mate transitions and immediate checkmates
are always critical.

Move beauty answers whether a sound move contains a non-obvious aesthetic idea.
It is one strict `label` plus `score`; do not let the LLM judge beauty. Labels
are `low`, `notable`, `beautiful`, and `brilliant`. Unsound moves do not get a
beauty bonus. Non-mating `forced` moves are capped at low beauty because the
player had no choice.

## LLM Context Shape

The compact context should include:

- played move and quality
- position facts, including previous move UCI when known
- player level and time situation
- severity from the player's point of view
- significance and beauty signals
- the main explanation point
- objective engine best move
- practical alternative when it differs from the engine best
- featured move for the current explanation focus
- the key move or idea
- candidate practicality and findability
- human note when backed by evidence
- typed `concept_claims` for every supported concept family
- allowed claim text and any necessary forbidden claims

It should not include:

- raw engine dumps
- unsupported concept labels
- broad style rules
- prompt instructions
- moves or PV lines the verifier cannot check

## Explanation Agenda

Choose one agenda before generation:

- objective mistake, best move findable: recommend directly
- objective mistake, best move hard: explain with caveat
- engine best barely better: explain the idea, not engine precision
- only move: mention the exact move despite difficulty
- good or beautiful move: explain the idea that made it work

The agenda is a deterministic teaching decision, not prose polish.

## Concept Claims

Concept language exposed to the model must be structured. `concept_claims` carry
the concept kind, subject, claim text, source, and related SAN move when one
exists. The explanation verifier treats these typed claims as the authority for
concept language.

Free-form `allowed_claims` are still useful as compact wording evidence, but
they are not enough to authorize positional, tactical, mate, material, or forcing
concepts by themselves. For example, a model may discuss king safety only after a
deterministic detector adds a `king_safety` concept claim; adding a sentence to
`allowed_claims` is not sufficient.

## Pitfalls To Prevent

- recommending hard engine moves as obvious
- treating Maia probability as quality
- changing quality because the player was low on time
- overvaluing tiny engine preferences
- allowing unsupported tactic or material claims
- allowing unsupported strategic concept claims through free-form strings
- mixing White, Black, side-to-move, and player perspectives
- letting generated text introduce new PV moves

## Acceptance Criteria

The context engine is working when:

- reconstruction and played-move legality are deterministic
- scores are player-perspective and mate-aware
- every recommended move has objective evidence
- every recommended move has findability or `unknown`
- hard best moves are caveated
- close practical alternatives are recognized
- optional human evidence affects wording only
- the LLM context is compact enough for one explanation
- the verifier can trace every explanation claim back to the evidence packet
