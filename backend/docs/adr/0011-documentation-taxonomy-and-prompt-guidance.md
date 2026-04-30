# ADR 0011: Documentation Taxonomy And Prompt Guidance

Date: 2026-04-30
Status: Accepted

## Context

The documentation mixed product decisions, development workflow, testing rules,
and prompt guidance at the same level under `docs/`. That made required reading
longer than necessary and made prompt behavior rules harder for agents to find.

Accepted ADRs already reference some old top-level document paths. Those ADRs
should remain immutable, so a restructure must preserve stable compatibility
paths.

## Decision

Canonical documentation is split by decision type:

- `docs/product/` for product scope, context-engine behavior, domain boundaries,
  and prompt guidance.
- `docs/development/` for implementation quality, repo structure, workflow,
  quality gates, testing, and agent checklists.
- `docs/adr/` for durable decisions.

Old top-level document paths remain as short redirects to preserve ADR links and
older agent instructions.

Prompt guidance is documented in `docs/product/prompt-guidelines.md`. It
codifies the existing rule that prompts may only turn verified LLM context into
one explanation string. Prompts must not ask the model to create chess truth,
invent moves, override evidence, or ship output that fails verification.

## Consequences

Future agents can identify whether a document governs product behavior or
development execution before editing. Prompt work has a single operational
checklist for static rules, dynamic context, claim limits, schema output, and
verification.

The repo keeps a few small compatibility files at the old top-level paths. This
adds minor duplication but avoids mutating accepted ADRs only to update links.

## Alternatives Considered

### Move docs without redirects

Rejected. Accepted ADRs and older agent instructions would point at missing
files.

### Keep prompt rules scattered

Rejected. Prompt behavior is safety-critical and should be reviewed through one
document.

### Put prompt guidance under development docs

Rejected. Prompt behavior affects product output and claim policy, so it belongs
with product documentation.

## Validation

This decision is working if:

- required-reading lists use foldered paths
- old top-level doc paths still resolve
- product docs stay concise and contract-focused
- development docs stay execution-focused
- prompt changes follow `docs/product/prompt-guidelines.md`
