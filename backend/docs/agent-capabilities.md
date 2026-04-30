# Agent Capabilities And Checks

This document describes the capabilities future agents should build and use. It
is not a request to create all tools immediately.

## Required Agent Capabilities

Agents working in this repository should be able to:

- parse and replay chess games deterministically
- call Stockfish through UCI and parse results
- call Maia-2 or a replacement human-likeness model
- validate JSON schemas
- run deterministic chess verification
- run focused unit and integration tests
- run model/prompt evals against frozen sets
- inspect data manifests and source rights
- update ADRs when decisions change

## Future Local Checks

Once implementation exists, add commands for:

```text
format
lint
typecheck
unit tests
integration tests
schema validation
deterministic verifier fixtures
golden incident tests
model eval smoke test
data-source manifest validation
```

The current Python typecheck commands are:

```text
uv run mypy src tests
uv run pyright
```

Broader schema, verifier, eval, and data checks should be exposed through a
single documented command only after those stacks exist.

## Pre-Implementation Checklist

Before starting a new feature:

- What product slice is being changed?
- Which ADRs govern this area?
- Which schema contracts are involved?
- Which verifier checks protect the behavior?
- What test fixture will prove the behavior?
- What failure mode should be added to regression tests?

## Completion Checklist

Before calling a task done:

- Relevant tests were run.
- Schema changes were validated.
- Chess correctness checks pass.
- New behavior is covered by tests or eval fixtures.
- ADRs/docs were updated if contracts changed.
- Skipped checks and residual risks are named.

## Review Checklist

When reviewing code, prioritize:

- wrong side or perspective
- illegal moves
- unsupported PV references
- mate/centipawn confusion
- unlicensed or ambiguous data use
- explanations that depend on LLM-invented facts
- tests that mock away the core chess risk
- broad scaffolding that is not required by the current slice
