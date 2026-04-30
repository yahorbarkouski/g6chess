# ADR 0012: Remove Legacy Documentation Redirects

Date: 2026-04-30
Status: Accepted

## Context

ADR 0011 split canonical documentation into `docs/product/` and
`docs/development/`, while keeping old top-level redirect files for compatibility.
That compatibility layer made the tree noisier and left agents with two possible
paths for the same guidance.

The project now prefers one canonical documentation structure with no legacy
redirects.

## Decision

Remove the old top-level documentation redirect files. Keep canonical guidance
only under:

- `docs/product/`
- `docs/development/`
- `docs/adr/`

Update active references and ADR links to the foldered paths. `AGENTS.md` must
use the foldered required-reading list.

## Consequences

Agents have one source of truth for each guide. Repository navigation is simpler
and stale top-level documents cannot drift from canonical guidance.

Older external references to deleted top-level files will break. The project
accepts that cost to avoid preserving legacy paths in the repo.

## Alternatives Considered

### Keep Redirect Files

Rejected. Redirect files preserve old navigation and make it easier for agents
to keep using legacy paths.

### Move All Docs Back To The Top Level

Rejected. The product/development split is clearer and matches how agents need
to reason about product decisions versus implementation workflow.

## Validation

This decision is working if:

- no old top-level guide files remain
- `AGENTS.md` uses only foldered guide paths
- `docs/README.md` points only to canonical folders
- repository search does not send agents to deleted guide paths
