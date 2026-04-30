# Documentation Index

Docs are split by decision type. Product docs define what the system must do.
Development docs define how agents should build and verify it. ADRs record
durable decisions.

## Product Docs

- `product/end-goal.md`: product scope and API contract.
- `product/context-engine.md`: evidence packet, LLM context, and candidate
  policy.
- `product/product-understanding.md`: domain boundaries and failure modes.
- `product/prompt-guidelines.md`: prompt rules, claim limits, and verification
  loop.

## Development Docs

- `development/implementation-quality.md`: code quality and package rules.
- `development/project-structure.md`: repo layout and naming rules.
- `development/development-flow.md`: checks, commits, and work sequencing.
- `development/quality-gates.md`: schema, chess, explanation, dataset, and
  model gates.
- `development/testing-playbook.md`: unit, integration, golden, adversarial, and
  eval test guidance.
- `development/agent-capabilities.md`: agent checklists and review priorities.

## ADRs

- `adr/README.md`: ADR format and when to write one.
- `adr/*.md`: accepted, superseded, proposed, or rejected decisions.

## Compatibility Paths

Top-level docs such as `end-goal.md` are short redirects for older ADR links and
agent instructions. New work should use the foldered paths above.

## Maintenance Rules

- Update product docs when product contracts or model behavior change.
- Update development docs when workflow, checks, structure, or testing changes.
- Add an ADR for durable architecture, schema, data, verifier, model, or
  production-behavior decisions.
- Keep docs operational: rules, contracts, checklists, and examples only.
