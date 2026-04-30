# ADR 0001: Initial Operating Model

Date: 2026-04-30
Status: Accepted

## Context

The repository is empty. The immediate need is not application scaffolding. The
immediate need is a coherent operating base that lets future implementation
proceed with high correctness, clear quality gates, and shared product
understanding.

The product has high hallucination risk because it combines chess engines,
human-like move models, and LLM-generated explanations. A fluent explanation can
be harmful if it invents moves, flips evaluation perspective, or teaches a false
lesson.

## Decision

We will create documentation and operating contracts before application code:

- root `AGENTS.md`
- `docs/product/product-understanding.md`
- `docs/development/quality-gates.md`
- `docs/development/testing-playbook.md`
- `docs/adr/README.md`
- accepted ADRs for durable decisions

We will not create broad application directories, empty packages, service
skeletons, or placeholder implementation files until a concrete vertical slice
requires them.

## Consequences

Future agents get a clear execution environment before code exists. The project
can maintain a high correctness bar without prematurely choosing framework,
service, or package boundaries.

This makes the first implementation slightly slower to start, but reduces
architectural drift and lowers the risk of training or product decisions being
made implicitly.

## Alternatives Considered

### Full repository scaffold now

Rejected. It would create false structure before the first vertical slice proves
what boundaries are useful.

### No documentation until implementation

Rejected. This product needs explicit quality gates and data/model boundaries
before code exists because incorrect early assumptions would poison later data,
tests, and model behavior.

## Validation

This decision is working if future implementation changes:

- read and follow `AGENTS.md`
- add ADRs for durable decisions
- create code only for concrete product slices
- include tests and verifier checks with new behavior
- preserve the separation between chess truth and LLM explanation
