# Codebase cleanliness audit event log

Date: 2026-08-13
Repository: `yahorbarkouski/g6chess`
Audit report: `2026-08-13-codebase-cleanliness-audit.md`

## Resume state

- Current phase: complete.
- Artifact paths: this event log and the paired audit report in `backend/docs/audits/`.
- Last completed dimension: source, dependency, secret, workflow, and complexity audit.
- Next planned checks: none.
- Known blockers: none.

## Timeline

### Step 001 - Initialize the audit

- Action: checked repository status and read root, backend, and frontend instructions,
  audit templates, backend product docs, development docs, and ADRs.
- Reason: establish the product truth boundary and repository quality requirements before
  judging implementation details.
- Evidence inspected: `AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md`, root README,
  backend documentation index, product docs, development docs, and ADRs 0001 through 0004.
- Observations: the required truth boundary is explicit; Modal publication is deliberately
  manual; the generated API contract is backend-owned.
- Outcome: audit scope and artifact locations fixed.

### Step 002 - Establish the deterministic baseline

- Action: ran `tools/prove.sh` before editing.
- Reason: distinguish pre-existing failures from audit remediation.
- Evidence inspected: backend format/lint/type/test output, generated OpenAPI diff,
  frontend install/audit/type/lint/test/build output.
- Observations: 445 backend tests and 112 frontend tests passed; generated contracts
  were unchanged; Bun reported no known vulnerabilities.
- Outcome: baseline green.

### Step 003 - Trace asynchronous failure boundaries

- Action: followed job creation, executor submission, runner exception handling,
  snapshot persistence, and API error mapping from caller to Redis.
- Reason: background boundaries commonly hide orphaned state and private error leakage.
- Evidence inspected: `job_service.py`, `modal_job_executor.py`, `analysis_runner.py`,
  `api/app.py`, contracts, integration docs, and API tests.
- Observations: synchronous spawn errors left pending state; raw exception strings were
  persisted publicly despite a documented non-disclosure contract.
- Outcome: CLN-001 and CLN-002 confirmed and remediated with HTTP-level regressions.

### Step 004 - Audit repository and supply-chain hygiene

- Action: scanned Git history and the working directory with Gitleaks, audited installed
  Python dependencies with pip-audit, inspected tracked blobs and author metadata, and
  analyzed workflows with actionlint and zizmor.
- Reason: open-source readiness includes history, CI trust, and local-file isolation.
- Evidence inspected: 145 commits, workflow definitions, ignore rules, package locks,
  tracked file inventory, and repository-local Git configuration.
- Observations: no committed secret or known dependency vulnerability; one ignored
  Vercel credential file; mutable Actions tags; persistent checkout credentials; an
  obsolete migration script with a personal email.
- Outcome: Actions pinned, credentials disabled, migration tool removed, future local
  commits configured for GitHub noreply authorship.

### Step 005 - Measure maintainability and documentation accuracy

- Action: mapped packages and line counts, ran Radon, inspected the highest-complexity
  functions, and compared runtime/structure docs against the actual monorepo.
- Reason: distinguish real design debt from harmless file-size or complexity metrics.
- Evidence inspected: all production packages, largest modules, D/C complexity blocks,
  project-structure docs, game-analysis integration docs, Modal docs, and training docs.
- Observations: average backend complexity is A; the high-complexity blocks are explicit
  deterministic policy aggregators. Three documentation areas were stale.
- Outcome: docs corrected; metric-driven production refactors rejected as unjustified.

### Step 006 - Prove the complete remediation

- Action: ran the full repository proof and inspected the final diff.
- Reason: verify the real artifact after code, workflow, tooling, and documentation edits.
- Evidence inspected: every backend quality gate, complete backend/frontend test suites,
  generated contract diff, production frontend build, and `git diff --check`.
- Observations: 447 backend tests passed with 11 opt-in skips; 112 frontend tests passed;
  all format, lint, type, dependency, contract, and build checks passed.
- Outcome: remediation complete.

## Command log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 001 | `git status --short` | Protect unrelated work | Passed | Worktree started clean. |
| 001 | targeted `sed`, `find`, and `rg --files` reads | Load instructions and system docs | Passed | Cross-cutting audit rules identified. |
| 002 | `./tools/prove.sh` | Establish full baseline | Passed | 445 backend and 112 frontend tests. |
| 003 | focused game-analysis tests | Prove failure-boundary fixes | Passed | 11 tests. |
| 004 | `uvx pip-audit --path ...` | Audit installed Python dependencies | Passed | No known vulnerabilities. |
| 004 | Gitleaks Git and directory scans | Detect committed/local secrets | Passed with local note | No Git leaks; one ignored Vercel JWT. |
| 004 | `actionlint` and `zizmor` | Validate and secure workflows | Passed | No reported findings after fixes. |
| 004 | ShellCheck | Validate operational shell scripts | Passed | One `CDPATH` syntax warning fixed. |
| 005 | Radon CC/MI | Locate maintainability hotspots | Passed with observations | Average CC A (3.64). |
| 006 | `./tools/prove.sh` | Prove final repository state | Passed | 447 backend and 112 frontend tests. |

## Hypothesis log

| ID | Hypothesis | Evidence for | Evidence against | Status | Related finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | The monorepo may contain stale frontend-only or backend-only assumptions after migration. | Structure docs showed a backend-only root. | Root docs and generated contracts already describe the monorepo. | Confirmed | CLN-005 |
| H-002 | Large orchestration modules may hide mixed responsibilities. | Several files are large and four functions grade D. | Package direction is clean; average CC is A; dense blocks aggregate explicit rules. | Rejected as a general defect | CLN-007 |
| H-003 | Deployment documentation may lag the live Modal worker architecture. | Integration wording described only a single process. | Modal-specific docs describe spawned workers. | Confirmed | CLN-005 |
| H-004 | Background submission failure may orphan persisted state. | Pending state is saved before executor submission. | No existing failure-path test. | Confirmed | CLN-001 |
| H-005 | Provider exceptions may cross the public API boundary. | Runner persisted `str(exc)` in snapshot fields. | Docs explicitly prohibit returning it. | Confirmed | CLN-002 |

## Files and docs inspected

- Repository guidance: root, backend, and frontend `AGENTS.md`; root README.
- Product and architecture: all files under `backend/docs/product/` and
  `backend/docs/adr/`.
- Development: all files under `backend/docs/development/`.

## Blockers and deferred checks

None.
