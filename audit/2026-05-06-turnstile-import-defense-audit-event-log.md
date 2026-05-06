# Turnstile Import Defense Audit Event Log

Date: 2026-05-06
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Audit report: `./2026-05-06-turnstile-import-defense-audit.md`

## Resume State

- Current phase: report complete.
- Artifact paths:
  - `audit/2026-05-06-turnstile-import-defense-audit.md`
  - `audit/2026-05-06-turnstile-import-defense-audit-event-log.md`
- Last completed dimension: frontend import/Turnstile architecture, route import flow, Cloudflare documentation check.
- Next planned checks:
  - If implementing: update Turnstile flow tests first, then change `AnalysisImportPanel` and `AnalysisWorkspace`.
  - Verify backend token-validation ordering in the private backend.
  - Verify Cloudflare and Modal origin-gateway settings in production.
- Known blockers:
  - Backend source and live Cloudflare configuration are not available in this checkout.
  - Worktree already contains unrelated user edits, so product code was not changed during this audit.

## Timeline

### Step 001 - Initialize Audit

- Action: Read repository instructions from the prompt, then `README.md`, `package.json`, and audit skill instructions.
- Reason: Establish product boundary, setup, checks, and audit artifact expectations.
- Evidence inspected:
  - `README.md`
  - `package.json`
  - `/Users/yahorbarkouski/.codex/skills/audit/SKILL.md`
- Observations:
  - Frontend owns import UI and API client only.
  - README documents `VITE_G6_TURNSTILE_SITE_KEY`.
  - Audit workflow asks for report and event log artifacts.
- Outcome: Narrowed audit to import Turnstile behavior and surrounding defense design.

### Step 002 - Check Worktree

- Action: Ran `git status --short`.
- Reason: Avoid overwriting unrelated user edits.
- Evidence inspected:
  - Git status output.
- Observations:
  - Existing modifications in `bun.lock`, `package.json`, `src/App.tsx`, `AnalysisWorkspace.tsx`, engine-line and position-info files.
- Outcome:
  - Product code left untouched during audit.

### Step 003 - Search Turnstile and Import Surfaces

- Action: Ran ripgrep for Turnstile, import, 429, and token-related strings.
- Reason: Locate all relevant frontend and docs surfaces.
- Evidence inspected:
  - `src/components/analysis/AnalysisImportPanel.tsx`
  - `src/components/analysis/AnalysisWorkspace.tsx`
  - `src/lib/api.ts`
  - `src/types/api.ts`
  - Tests for API, import panel, and workspace route imports.
- Observations:
  - Turnstile implementation is local to the import panel.
  - Workspace owns route-triggered imports and shared Turnstile state.
  - API client already preserves `Retry-After` and backend error codes.
- Outcome:
  - Confirmed the main audit path.

### Step 004 - Inspect Existing Audit Context

- Action: Read `audit/README.md` and searched/read available Cloudflare/security plan files.
- Reason: Avoid contradicting recent local planning.
- Evidence inspected:
  - `audit/README.md`
  - `audit/2026-05-05-g6explanation-modal-defense-plan.md`
- Observations:
  - Audit index references `2026-05-05-cloudflare-rate-limit-security-plan.md`, but that file is missing.
  - `2026-05-05-g6explanation-modal-defense-plan.md` contains the relevant defense architecture and specifically warns not to hide Turnstile behind retry loops.
- Outcome:
  - Added missing-plan issue as a docs/process finding.

### Step 005 - Trace Manual Import Turnstile Flow

- Action: Read `AnalysisImportPanel` around request construction, submit handling, Turnstile rendering, and widget lifecycle.
- Reason: Determine whether the widget appears before or after a protected request.
- Evidence inspected:
  - `src/components/analysis/AnalysisImportPanel.tsx:187-188`
  - `src/components/analysis/AnalysisImportPanel.tsx:237-249`
  - `src/components/analysis/AnalysisImportPanel.tsx:642-663`
  - `src/components/analysis/AnalysisImportPanel.tsx:701-763`
- Observations:
  - Widget appears only when prompted or required.
  - Submit calls `onImport` before prompting, then prompts only on `turnstile_failed`.
  - Token is attached only opportunistically if it already exists.
- Outcome:
  - Confirmed F-001 and F-003.

### Step 006 - Trace Direct Route Import Flow

- Action: Read `AnalysisWorkspace` around cached lookup, pending route import, and Turnstile retry.
- Reason: Reproduce the production complaint for direct/random page imports.
- Evidence inspected:
  - `src/components/analysis/AnalysisWorkspace.tsx:403-439`
  - `src/components/analysis/AnalysisWorkspace.tsx:528-551`
- Observations:
  - Cached GET is attempted first.
  - On 404, first pending POST is tokenless because `turnstileRequired` starts false.
  - Turnstile only appears after backend returns `turnstile_failed`.
- Outcome:
  - Confirmed F-002.

### Step 007 - Check Tests

- Action: Read import panel and workspace Turnstile tests.
- Reason: Determine whether current behavior is accidental or explicitly locked by tests.
- Evidence inspected:
  - `src/components/analysis/AnalysisImportPanel.test.tsx:96-157`
  - `src/components/analysis/AnalysisWorkspace.test.tsx:309-365`
- Observations:
  - Tests explicitly assert tokenless first call and token-bearing retry.
- Outcome:
  - Recommended inverting these tests as part of the fix.

### Step 008 - Review Current Cloudflare Docs

- Action: Browsed current Cloudflare Turnstile and challenge documentation.
- Reason: Security behavior is current, high-stakes, and should be verified against primary docs.
- Evidence inspected:
  - Cloudflare Turnstile client-side rendering docs.
  - Cloudflare Turnstile server-side validation docs.
  - Cloudflare Turnstile pre-clearance docs.
- Observations:
  - Explicit rendering is recommended for SPAs and dynamic content.
  - Server-side validation is mandatory because tokens can be forged, expire after five minutes, and are single-use.
  - Pre-clearance can issue `cf_clearance` for protected zones, but requires correct zone/hostname configuration.
- Outcome:
  - Recommended keeping Turnstile at import-start admission and considering pre-clearance only if WAF-protected fetches are desired.

## Command Log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 001 | `sed -n '1,220p' README.md` | Read startup docs | Passed | README defines import contract and Turnstile env var. |
| 001 | `sed -n '1,220p' package.json` | Read scripts/deps | Passed | Bun/Vite/React app. |
| 001 | `sed -n '1,220p' /Users/yahorbarkouski/.codex/skills/audit/SKILL.md` | Follow audit workflow | Passed | Report and event log expected. |
| 002 | `git status --short` | Check dirty worktree | Passed | Existing unrelated edits present. |
| 003 | `rg -n "turnstile|Turnstile|cf-turnstile|rate limit|rateLimit|429|captcha|token|required|import" src README.md audit/README.md` | Locate relevant code | Passed | Turnstile concentrated in panel/workspace. |
| 004 | `find audit -maxdepth 1 -type f -print | sort` | Verify audit files | Passed | Referenced Cloudflare plan filename absent. |
| 004 | `sed -n '1,260p' audit/2026-05-05-g6explanation-modal-defense-plan.md` | Read available security plan | Passed | Contains Cloudflare/Turnstile/Redis defense plan. |
| 005 | `sed -n '1,260p' src/components/analysis/AnalysisImportPanel.tsx` | Trace panel submit flow | Passed | First submit happens before Turnstile. |
| 005 | `sed -n '260,560p' src/components/analysis/AnalysisImportPanel.tsx` | Trace random game and UI | Passed | Random game uses same retry-after-failure behavior. |
| 005 | `sed -n '560,800p' src/components/analysis/AnalysisImportPanel.tsx` | Trace widget lifecycle | Passed | Explicit render script loaded only when widget mounted. |
| 006 | `sed -n '150,460p' src/components/analysis/AnalysisWorkspace.tsx` | Trace route cached lookup | Passed | 404 creates pending import. |
| 006 | `sed -n '510,620p' src/components/analysis/AnalysisWorkspace.tsx` | Trace pending route import | Passed | Initial pending POST is tokenless. |
| 007 | `sed -n '90,170p' src/components/analysis/AnalysisImportPanel.test.tsx` | Inspect panel test | Passed | Test locks in tokenless first POST. |
| 007 | `sed -n '300,375p' src/components/analysis/AnalysisWorkspace.test.tsx` | Inspect route test | Passed | Test locks in route retry behavior. |

## Hypothesis Log

| ID | Hypothesis | Evidence For | Evidence Against | Status | Related Finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | Production delay is caused by frontend waiting for backend `turnstile_failed` before rendering Turnstile. | Panel/workspace source and tests show tokenless first POST followed by challenge retry. | None found. | Confirmed | F-001, F-002 |
| H-002 | Turnstile should be removed entirely because rate limits exist. | Rate limits protect repeated volume. | Import start is an expensive anonymous admission boundary; existing security plan and Cloudflare docs support using Turnstile plus server validation. | Dismissed | F-003 |
| H-003 | Pre-clearance could improve SPA/fetch protection. | Cloudflare docs support Turnstile issuing `cf_clearance` for protected zones. | Requires correct Cloudflare zone/hostname/WAF setup and does not replace backend admission policy by itself. | Open | None |
| H-004 | API client cannot surface rate limits. | None. | `src/lib/api.ts` preserves `Retry-After` and codes; workspace polling respects `429`. | Dismissed | None |

## Files and Docs Inspected

Frontend:

- `README.md`: product boundary and API contract.
- `package.json`: scripts and dependencies.
- `index.html`: confirms Turnstile script is not loaded globally.
- `src/lib/api.ts`: API error and retry-after handling.
- `src/types/api.ts`: import request includes optional `turnstile_token`.
- `src/components/analysis/AnalysisImportPanel.tsx`: manual URL/PGN/random import and Turnstile widget.
- `src/components/analysis/AnalysisWorkspace.tsx`: direct route import and shared Turnstile state.

Tests:

- `src/lib/api.test.ts`: rate-limit error preservation.
- `src/components/analysis/AnalysisImportPanel.test.tsx`: current Turnstile retry behavior.
- `src/components/analysis/AnalysisWorkspace.test.tsx`: current direct-route Turnstile retry behavior.

Audit docs:

- `audit/README.md`: audit index.
- `audit/2026-05-05-g6explanation-modal-defense-plan.md`: current available Cloudflare/Modal/frontend defense context.

External docs:

- Cloudflare Turnstile client-side rendering.
- Cloudflare Turnstile server-side validation.
- Cloudflare Turnstile pre-clearance.

## Blockers and Deferred Checks

- Backend token-validation order must be verified in the private backend.
- Production Cloudflare WAF/rate-limit/pre-clearance configuration must be checked in the Cloudflare dashboard.
- No source checks were run because this audit changed docs only and product code was intentionally left untouched due to unrelated worktree edits.

