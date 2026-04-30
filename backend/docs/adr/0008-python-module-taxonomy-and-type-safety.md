# ADR 0008: Python Module Taxonomy And Type Safety

Date: 2026-04-30
Status: Accepted

## Context

The context engine now has enough code that generic Python file names make the
system harder to navigate. Names such as `heuristics.py`, `models.py`, and
`providers.py` hide product decisions: move-quality classification, candidate
recommendation policy, explanation agenda construction, schema contracts, and
external evidence adapters.

The package also ships `py.typed`, but development does not yet require a static
type checker. Runtime Pydantic validation catches malformed contracts, but it
does not protect internal module boundaries, provider protocols, typed dict
shapes, or accidental use of untyped values in deterministic chess policy code.

## Decision

Production modules must be named after their domain responsibility. Generic
catch-all modules such as `utils.py`, `common.py`, `helpers.py`, `models.py`,
`providers.py`, and `heuristics.py` are not acceptable for production code.

The current context-engine modules are organized as:

```text
contracts.py
position_reconstruction.py
move_quality.py
candidate_policy.py
explanation_agenda.py
move_context_builder.py
provider_protocols.py
stockfish_analysis.py
maia_likelihood.py
exceptions.py
```

Public Python names should also describe responsibility:

- `MoveContextBuilder` builds evidence and LLM context.
- `EngineAnalysisProvider` supplies objective engine analysis.
- `RootMoveAnalysisProvider` optionally analyzes explicit legal root moves.
- `HumanMoveLikelihoodProvider` supplies human-likeness evidence.
- `StockfishAnalysisProvider` and `Maia2MoveLikelihoodProvider` are concrete
  adapters.
- `ContextContract` is the frozen Pydantic base for schema contracts.

Type safety is now a required local gate. The repository uses mypy first for
Python/Pydantic checks and Pyright as a second strict checker for editor-aligned
feedback. Core context-engine code should be typed without `Any` or
`# type: ignore`. Unavoidable dynamic typing is isolated to external adapter
edges, especially Maia-2 and python-chess UCI info dictionaries.

## Consequences

Navigation improves because file names now map directly to the product
responsibilities described in the docs. Splitting the former catch-all modules
makes it clearer where chess truth, practical recommendation policy, provider
I/O, and LLM-facing agenda construction live.

The clean rename breaks old Python import paths. That is intentional for this
early package: incorrect names should not become long-term public contracts.

The required check set is slower because it now includes mypy and Pyright. In
exchange, future changes get faster feedback on schema shape, provider
protocols, literal roles, and accidental untyped values.

## Alternatives Considered

### Keep compatibility shims

Rejected. The package is still early, and keeping old modules such as
`heuristics.py` would preserve the navigation problem.

### Use only mypy

Rejected. Mypy is the primary gate, but Pyright catches different issues and
matches common editor feedback.

### Use only runtime Pydantic validation

Rejected. Runtime schema validation is necessary but does not protect internal
pure functions, provider protocols, or development-time refactors.

## Validation

This decision is working if:

- production modules remain named after single domain responsibilities
- new production catch-all modules are rejected during review
- `uv run mypy src tests` passes
- `uv run pyright` passes
- role, policy, and key-move context shapes are statically typed
- external adapter modules contain any unavoidable dynamic typing locally
