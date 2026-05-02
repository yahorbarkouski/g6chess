# Documentation Index

Start at the root `README.md` for setup and at `../AGENTS.md` for operating
rules. Docs are split by decision type. Product docs define what the system must
do. Development docs define how agents should build and verify it. ADRs record
durable decisions.

## Product Docs

- `product/end-goal.md`: product scope and API contract.
- `product/context-engine.md`: evidence packet, LLM context, and candidate
  policy.
- `product/product-understanding.md`: domain boundaries and failure modes.
- `product/prompt-guidelines.md`: prompt rules, claim limits, and verification
  loop.
- `product/explanation-generation.md`: next product slice for verified
  explanation generation, provider boundaries, verifier checks, and evals.

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

- `adr/README.md`: current concise decision records.
- `adr/0001-product-truth-boundary.md`: product and chess-truth boundary.
- `adr/0002-context-contract-and-verification.md`: context contracts and gates.
- `adr/0003-development-standards.md`: structure, docs, and workflow standards.

## Audit Reports

- `audits/`: scoped investigation reports and event logs. Read them when
  investigating prior findings, resuming an audit, or checking why a durable
  rule changed. These are evidence records, not operating guides; update
  product, development, or ADR docs for durable rules.

## Maintenance Rules

- Update product docs when product contracts or model behavior change.
- Update development docs when workflow, checks, structure, or testing changes.
- Update the concise ADR set for durable architecture, schema, data, verifier,
  model, or production-behavior decisions.
- Keep docs operational: rules, contracts, checklists, and examples only.
