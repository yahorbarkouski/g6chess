# ADR 0006: Production Context Evidence

Date: 2026-04-30
Status: Accepted

## Context

The context engine has a useful first slice, but production explanations need
stronger evidence contracts before any LLM phrasing is introduced. The current
implementation needs durable decisions for schema validation, Stockfish
configuration, Maia integration, and verifier-facing context fields.

These decisions affect schema contracts, Stockfish options, Maia configuration,
and verifier policy, so they require an ADR before implementation.

## Decision

The context engine will validate all public internal context objects with
versioned Pydantic v2 models. This includes evidence packets, LLM context,
move quality, candidate moves, and the initial verifier result contract.

Stockfish remains the required objective-strength source behind the
`EngineAnalyzer` provider boundary. The provider records engine version,
analysis budget, applied UCI options, WDL when available, depth/nodes metadata,
tablebase hits, and legal SAN/ UCI PV replay. The supported analysis budget is
depth or nodes, plus MultiPV, threads, hash, optional `UCI_ShowWDL`, and optional
Syzygy path.

Maia-2 is the first human-likeness provider. It remains optional and is loaded
lazily through `Maia2ProbabilityProvider` so normal context-engine tests do not
require Torch models. The provider uses the official `maia2==0.9` package when
installed, selects blitz or rapid by time control, runs position-wise inference
for player Elo and player Elo plus 400, and records probabilities as human
likelihood evidence only. Maia output never changes objective move quality.

The deterministic context policy is:

- mate transitions override centipawn and WDL formulas
- otherwise quality uses the worse label from centipawn loss and WDL expected
  score loss from the analyzed player's point of view
- findability uses Maia probability thresholds, `+400` skill-gap comparison,
  time pressure, and forcing move shape
- hard engine moves are caveated, close practical alternatives can be preferred,
  and unknown human evidence stays explicitly unknown
- the LLM context receives only the chosen agenda and allowed claims

## Consequences

Schemas become stricter and catch malformed context earlier. Stockfish output is
more auditable because options, budget, WDL, PV legality, and search metadata are
recorded. Maia can improve recommendation wording without becoming a source of
objective chess truth.

The optional Maia provider adds a heavy runtime path for users who install the
extra, but it does not burden the default package or CI path. Because Maia-2
pins `chess==1.10.0`, the project accepts `chess>=1.10,<2` and keeps tests
protecting the shared python-chess behavior the context engine relies on.

## Alternatives Considered

### Keep dataclasses only

Rejected. Dataclasses are lightweight but do not provide runtime contract
validation or JSON Schema export for evidence, LLM context, and verifier
objects.

### Make Maia-2 a required dependency

Rejected. The package pulls in a model-serving stack that is inappropriate for
the default context-engine install and would make normal local checks brittle.

### Let Stockfish ranking alone decide recommendations

Rejected. ADR 0005 requires candidate practicality and hard-move caveats so the
explanation does not overstate engine-only moves as obvious.

## Validation

This decision is working if:

- evidence and LLM context objects validate through Pydantic
- Stockfish integration tests verify MultiPV, WDL, forced played-move analysis,
  metadata, and legal PV replay
- Maia smoke tests skip unless the optional runtime is explicitly available
- unit tests prove Maia probabilities affect findability but not objective
  quality
- hard best moves are caveated and close practical alternatives are selected
  deterministically
