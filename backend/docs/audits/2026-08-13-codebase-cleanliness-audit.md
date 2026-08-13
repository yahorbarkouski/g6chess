# Codebase cleanliness audit

Date: 2026-08-13
Repository: `yahorbarkouski/g6chess`
Related event log: `2026-08-13-codebase-cleanliness-audit-event-log.md`

## Executive summary

The monorepo is in strong open-source shape. Its most important architectural
property is real rather than aspirational: Stockfish, Maia, deterministic rules,
and verifiers own chess truth; the language model only renders verified coaching
language. The backend has strict schemas, explicit provider boundaries, generated
frontend transport types, broad deterministic coverage, and a reproducible
repository-wide proof command.

This audit found and remediated five concrete issues:

1. provider and infrastructure exception text could enter anonymous polling JSON;
2. a Modal spawn failure could leave an analysis snapshot permanently pending;
3. GitHub Actions used mutable tags and retained checkout credentials;
4. a completed one-off migration tool remained in the product repository and
   embedded a personal email address; and
5. integration and structure documentation still described pre-monorepo or
   local-only runtime assumptions.

No committed secret, known dependency vulnerability, workflow syntax error, shell
error, contract drift, type error, lint error, or deterministic test failure was
found. The remaining risks are product-scale concerns rather than hidden code
defects: Modal jobs do not yet have durable queue/retry semantics, anonymous jobs
do not have user ownership, and several deterministic rule aggregators are dense
enough to deserve care when changed.

## Scope

- Included: backend, frontend, generated API contract, CI/CD, deployment entrypoints,
  documentation, dependencies, security boundaries, tests, and repository hygiene.
- Excluded: destructive production experiments and broad model-quality evaluation beyond
  the already completed production smoke.
- Repository instructions followed: root, backend, and frontend `AGENTS.md`; full backend
  product, development, and ADR documentation set.
- Constraints: real-provider checks will run only where they do not publish or mutate
  production state.

## Methodology

Source tracing, static checks, dependency audits, contract regeneration, focused runtime
experiments, and the repository's complete deterministic proof.

## System map

```text
React/Vite frontend
  -> generated TypeScript transport types
  -> FastAPI request and response contracts
  -> Redis pending snapshot
  -> local thread executor or production Modal worker
  -> per-ply context engine
       -> Stockfish objective analysis
       -> Maia human likelihoods
       -> deterministic labels, evidence, and verifiers
  -> verified GPT-5.6 Terra explanation wording
  -> Redis partial/final snapshots
  -> frontend polling and rendering
```

Repository size at audit time:

- 268 tracked files and about 67,000 tracked lines;
- 64 backend production files / 15,977 Python lines;
- 50 backend test files / 11,614 Python lines; and
- 54 frontend source files / 17,156 TypeScript, TSX, and CSS lines.

The backend import direction matches the documented architecture. `game_analysis`
orchestrates existing context and explanation services; `game_imports` resolves
canonical PGN and rights metadata; the API composes these boundaries. The generated
OpenAPI document is the transport source of truth and the frontend's public API
types project from generated types rather than copying backend schemas.

## Findings overview

| ID | Severity | Status | Finding |
| --- | --- | --- | --- |
| CLN-001 | High | Resolved | Worker submission failures could strand pending jobs. |
| CLN-002 | High | Resolved | Raw provider/infrastructure errors were returned in public snapshots. |
| CLN-003 | Medium | Resolved | CI actions were mutable and checkout credentials persisted unnecessarily. |
| CLN-004 | Medium | Resolved | A completed migration utility retained private author metadata and dead code. |
| CLN-005 | Medium | Resolved | Runtime and repository-structure docs had stale pre-Modal/pre-monorepo wording. |
| CLN-006 | Medium | Accepted | Durable retries, cancellation, and user/job ownership are not implemented. |
| CLN-007 | Low | Monitor | Four deterministic aggregation functions have cyclomatic complexity grade D. |

## Confirmed findings

### CLN-001: submission failures left a pending snapshot

`GameAnalysisService.start` persisted `pending` before calling the executor, but did
not handle a synchronous failure from Modal's spawn boundary. A rejected spawn could
therefore return an unstructured 500 and leave a pollable job pending until Redis
expiry. The service now converts the snapshot to `failed`, logs the private cause,
and raises a typed submission error that the API maps to the stable
`analysis_unavailable` 503 response. A regression test exercises the entire HTTP
boundary.

### CLN-002: public snapshots exposed private exception strings

The runner stored `str(exc)` in both job-level `error` and move-level
`explanation_error`. This contradicted the public error policy and could disclose
provider responses or infrastructure details. Public snapshots now contain stable,
generic failure messages. Detailed exception text and verification-attempt summaries
remain in server logs. Regression tests prove this for both context-provider and
OpenRouter-style failures.

### CLN-003: workflow supply-chain hardening

Every third-party GitHub Action is now pinned to an immutable commit with the readable
release tag retained as a comment. Every checkout sets `persist-credentials: false`.
Dependabot already monitors the GitHub Actions ecosystem, so these pins can continue
to receive update pull requests. `actionlint` and `zizmor` pass after the change.

### CLN-004: obsolete migration utility

`tools/migrate_monorepo.py` reproduced the already completed history migration, had no
caller or documentation reference, and embedded a personal author email. It was
deleted. The remaining root tool, `tools/prove.sh`, is the useful operational lever.
The repository-local Git author email was also changed to the GitHub noreply address
to prevent future commits from reintroducing the personal address.

### CLN-005: documentation drift

The integration guide described all analysis as in-process even though production
spawns a Modal worker, and the structure guide showed the old backend-only root.
Both now describe the actual monorepo and distinguish the local thread executor from
the production worker. The training-data guide now names GPT-5.6 Terra as the current
comparison baseline. Historical GPT-5.5 evaluation records remain unchanged because
they accurately identify the model that produced those records.

## Risks and follow-ups

- Redis is a snapshot store, not a durable queue. A worker lost after successful
  submission is not automatically retried or recovered.
- Anonymous job identifiers are not tied to user ownership. Turnstile, request limits,
  and rate limiting control abuse, but they are not authorization.
- The liveness endpoint is intentionally shallow. Operational monitoring should pair
  it with a real import/analysis canary when availability guarantees become stricter.
- Git history contains author emails from already-public commits. They are authorship
  metadata, not credentials. Rewriting public history would be disruptive and was not
  part of this remediation.
- Local ignored files contain deployment credentials. They are excluded by both root
  and backend ignore rules and were not found in any commit; this audit did not rotate
  credentials that never entered Git, per the repository owner's direction.

## Experiments and checks

- `./tools/prove.sh`: backend formatting, lint, mypy, pyright, all tests; OpenAPI
  regeneration; frontend frozen install, dependency audit, generated types,
  typecheck, lint, tests, and production build. Final result: 447 backend tests
  passed with 11 opt-in tests skipped; 112 frontend tests passed.
- Focused job-boundary suite: 11 tests passed after the failure-path changes.
- `pip-audit` against the backend virtual environment: no known vulnerabilities;
  the local project package was correctly skipped because it is not on PyPI.
- Bun audit: no known vulnerabilities.
- Gitleaks Git scan: 145 commits and about 3.81 MB scanned, no leaks.
- Gitleaks working-directory scan: one JWT-shaped value in ignored
  `.vercel/.env.production.local`; no tracked occurrence.
- `actionlint`: all workflows valid.
- `zizmor`: no reported workflow security findings after remediation; seven
  tool-suppressed findings remained suppressed.
- ShellCheck: `tools/prove.sh` and `backend/run.sh` pass after correcting explicit
  `CDPATH` assignment syntax.
- Radon: 827 backend blocks, average complexity A (3.64). Four policy aggregation
  functions grade D; 47 additional blocks grade C.
- Current tracked blobs: only `backend/uv.lock` and `frontend/public/demo.png`
  exceed 500 KB; neither is an unexpected binary or model artifact.

## Architectural themes

- The truth/wording separation is the codebase's strongest design choice and is
  enforced in package direction, schemas, deterministic verifiers, and tests.
- Boundary validation is concentrated appropriately: Pydantic/FastAPI at HTTP,
  explicit provider adapters for external I/O, and generated TypeScript at transport.
- High line counts in verifier/evidence modules mostly come from explicit domain rules.
  Splitting them solely to reduce file size would make the chess policy harder to trace.
- Complexity is concentrated in rule aggregation rather than hidden mutable state.
  Future refactors should extract named policy units only when a rule family gains a
  separate reason to change.
- The repository's strongest maintenance lever is `tools/prove.sh`: one command proves
  both applications and the shared contract.

## Remediation roadmap

1. **Completed now:** sanitize public failures, make submission atomic from the
   caller's perspective, harden Actions, delete migration residue, and correct docs.
2. **Before multi-user accounts:** add authenticated job ownership and enforce it on
   polling/import routes.
3. **Before availability commitments:** introduce durable job leases, retry/recovery,
   cancellation, and an end-to-end production canary.
4. **When changing dense rule areas:** add behavior characterization first, then
   extract one coherent policy family at a time. Do not perform metric-driven rewrites.

## Documentation updates needed

Completed in this change:

- `development/game-analysis-integration.md`
- `development/project-structure.md`
- `development/training-data.md`

No ADR update is required. The implementation now conforms to the existing public
error policy and Modal architecture rather than introducing a new decision.

## Residual risk

The deterministic local suite does not prove future provider behavior or production
infrastructure availability. The GPT-5.6 Terra promotion and a fresh production game
analysis were already verified before this audit; this change does not alter prompts,
model settings, chess truth, or provider request payloads, so a new no-mock model gate
is not required. A production redeploy should still be followed by one import/poll
smoke because the job-submission boundary changed.
