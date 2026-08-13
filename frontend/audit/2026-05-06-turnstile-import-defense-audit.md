# Turnstile Import Defense Audit

Date: 2026-05-06
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Related event log: `./2026-05-06-turnstile-import-defense-audit-event-log.md`

## Executive Summary

The current frontend Turnstile behavior is inverted for production UX. The UI submits anonymous import starts without a token, waits for the backend to reject the expensive boundary, and only then renders Turnstile. That creates the visible "click, wait, then token required" failure mode and makes route imports look broken.

The right fix is not to remove Turnstile. The import start is the expensive anonymous operation that can fan out into Chess.com requests, Stockfish/Maia work, OpenRouter calls, and Modal worker spawn. Keep Turnstile at that admission boundary, but make the browser satisfy the challenge before the first `POST /api/game-analysis/import`. Pair it with backend Redis admission control and Cloudflare gateway controls so Turnstile is one layer, not the whole defense.

Preferred product behavior:

1. Cheap cached lookup GETs remain tokenless but rate-limited.
2. If a direct game route is uncached, render/execute Turnstile before starting the POST import.
3. Manual URL and PGN submissions collect a fresh token before the POST import, not after a rejection.
4. Backend denies missing/invalid tokens before Chess.com resolution or worker spawn.
5. Rate limits and idempotency decide abuse/cost control; Turnstile decides whether an anonymous browser may enter the expensive start path.

## Scope

- Included:
  - Frontend import flow in `AnalysisWorkspace`.
  - Import panel Turnstile lifecycle.
  - API client error shape and rate-limit behavior.
  - Existing audit plan context.
  - Current Cloudflare Turnstile documentation relevant to SPAs, server validation, and pre-clearance.
- Excluded:
  - Backend implementation verification, because this checkout contains only the public frontend.
  - Production Cloudflare dashboard configuration, because credentials and live rules are not available here.
- Repository instructions followed:
  - Read `README.md`, `package.json`, and audit index.
  - Treated dated audit reports as context only and verified against current source.
- Constraints:
  - Worktree already has unrelated user edits in `package.json`, `bun.lock`, and several source files.
  - The audit index references `2026-05-05-cloudflare-rate-limit-security-plan.md`, but that file is absent. The available security plan is `2026-05-05-g6explanation-modal-defense-plan.md`.

## System Map

Current frontend flow:

```text
Home URL/PGN submit
  -> build import request
  -> POST /api/game-analysis/import without token unless one already exists
  -> if backend returns code=turnstile_failed, render widget
  -> callback retries original POST with turnstile_token

Direct route /game/live/:id or /lichess/:id
  -> GET cached imported analysis
  -> on 404, set pendingRouteImportTarget
  -> POST /api/game-analysis/import without token while turnstileRequired=false
  -> if backend returns code=turnstile_failed, render widget
  -> callback retries route POST with turnstile_token

Polling
  -> GET status_url repeatedly
  -> respects 429 Retry-After when ApiError carries it
```

Relevant contracts:

- `GameAnalysisImportRequest.turnstile_token?: string | null` exists in `src/types/api.ts`.
- `ApiError` preserves backend `code` and `Retry-After` in `src/lib/api.ts`.
- The README says Turnstile is enabled by `VITE_G6_TURNSTILE_SITE_KEY`.

Cloudflare documentation checked:

- Turnstile client-side rendering: explicit rendering is the right fit for SPAs, and server validation remains part of the flow.
- Turnstile server-side validation: tokens can be forged, expire after five minutes, and are single-use, so backend validation is mandatory.
- Turnstile pre-clearance: can issue a `cf_clearance` cookie for Cloudflare-protected domains if the widget and zone are configured correctly.

## Findings Overview

| ID | Severity | Category | Confidence | Title | Fix Priority |
| --- | --- | --- | --- | --- | --- |
| F-001 | High | correctness/security | High | Import starts intentionally make an unauthenticated failing POST before Turnstile | Immediate |
| F-002 | High | UX/correctness | High | Direct route imports show a loading state while waiting for a preventable token-required failure | Immediate |
| F-003 | Medium | security/architecture | High | Turnstile is treated as a form retry detail instead of an admission policy | Immediate |
| F-004 | Medium | docs/process | High | Audit index points to a missing Cloudflare plan file | Near-term |

## Confirmed Findings

### F-001: Import Starts Submit Before Token Collection

- Severity: High
- Category: correctness/security
- Confidence: High
- Status: Confirmed
- Evidence:
  - `src/components/analysis/AnalysisImportPanel.tsx:187-188` shows Turnstile only after `turnstilePrompted` or `turnstileRequired`.
  - `src/components/analysis/AnalysisImportPanel.tsx:237-249` submits the import first, then prompts only after an `ApiError` with `code === "turnstile_failed"`.
  - `src/components/analysis/AnalysisImportPanel.test.tsx:96-157` explicitly tests this behavior: first call has no `turnstile_token`, second call has one.
- Impact:
  - A legitimate user experiences an avoidable failed request before seeing verification.
  - Backend work may still parse/admit enough of the request to discover the missing token, depending on backend ordering.
  - Production looks slow and broken because the user action does not immediately lead to either verification or analysis.
- Reproduction or experiment:
  - Source trace and tests confirm the first POST is tokenless by design.
- Recommended fix:
  - Change import panel policy from "prompt after `turnstile_failed`" to "when Turnstile is enabled and no fresh token exists, render/execute Turnstile before calling `onImport`."
  - Keep backend `turnstile_failed` handling as recovery for expired/invalid tokens only.
- Verification:
  - Update panel tests so the first `onImport` call for URL/PGN includes `turnstile_token` when `VITE_G6_TURNSTILE_SITE_KEY` is set.
  - Add an expired-token test that resets and asks for a new token without producing a generic import failure.

### F-002: Direct Route Imports Delay Verification Until After a Failed POST

- Severity: High
- Category: UX/correctness
- Confidence: High
- Status: Confirmed
- Evidence:
  - `src/components/analysis/AnalysisWorkspace.tsx:403-439` performs a cached lookup first and sets `pendingRouteImportTarget` on clean `404`.
  - `src/components/analysis/AnalysisWorkspace.tsx:528-539` only pauses for Turnstile when `turnstileRequired` is already true. Initial value is false, so the first pending route POST is tokenless.
  - `src/components/analysis/AnalysisWorkspace.tsx:543-551` flips `turnstileRequired` only after a `turnstile_failed` error.
  - `src/components/analysis/AnalysisWorkspace.test.tsx:309-365` asserts the route import first posts without a token, then renders Turnstile and retries with a token.
- Impact:
  - Visiting a shared or prefixed game URL can sit in "submitting" until the backend rejects the missing token.
  - This is the exact production symptom described by the user.
- Reproduction or experiment:
  - Source trace and route test confirm the delay.
- Recommended fix:
  - Preserve the cheap cached GET path.
  - On `404`, if Turnstile is enabled, transition to a verification state and render the widget immediately.
  - Start `POST /api/game-analysis/import` only after receiving a token.
  - If Turnstile is disabled in local/dev, keep the current direct POST behavior.
- Verification:
  - Update the route test to assert no `startImportedGameAnalysis` call occurs before the Turnstile callback.
  - Add a cached-hit route test proving no Turnstile is required for an existing analysis.

### F-003: Turnstile Is Not Modeled as an Admission Boundary

- Severity: Medium
- Category: security/architecture
- Confidence: High
- Status: Confirmed
- Evidence:
  - The frontend owns a `turnstile_token` field, but there is no local policy object that says which operations require it.
  - `src/components/analysis/AnalysisImportPanel.tsx:660-661` only attaches a token opportunistically when one happens to exist.
  - `audit/2026-05-05-g6explanation-modal-defense-plan.md` already states that Turnstile should protect anonymous expensive starts and that missing/invalid tokens should be denied before Chess.com or worker work.
- Impact:
  - The policy is emergent from backend errors rather than explicit in UI behavior and tests.
  - It is easy to accidentally add another expensive import path that forgets to collect a token.
- Reproduction or experiment:
  - Source trace shows the token is optional at every frontend call site.
- Recommended fix:
  - Add a small frontend admission helper or state machine for import starts:
    - `cached_lookup`: no Turnstile, rate-limited.
    - `import_start`: Turnstile token required when site key exists.
    - `poll`: no Turnstile, respects `Retry-After`.
  - Backend should mirror this with route classification and Redis limits before expensive work.
- Verification:
  - Unit tests for URL submit, PGN submit, random game submit, direct route uncached import, direct route cached import, 429 cooldown, expired token, invalid token.

### F-004: Audit Index References a Missing Cloudflare Plan

- Severity: Medium
- Category: docs/process
- Confidence: High
- Status: Confirmed
- Evidence:
  - `audit/README.md` lists `2026-05-05-cloudflare-rate-limit-security-plan.md`.
  - `find audit -maxdepth 1 -type f` does not include that file.
  - `audit/2026-05-05-g6explanation-modal-defense-plan.md` appears to contain the relevant Cloudflare, rate-limit, Turnstile, and frontend 429 plan.
- Impact:
  - Future agents may fail to find the current security plan or assume guidance is missing.
- Recommended fix:
  - Either restore the missing file or update `audit/README.md` to point at `2026-05-05-g6explanation-modal-defense-plan.md`.
- Verification:
  - `find audit -maxdepth 1 -type f` and `audit/README.md` agree.

## Recommended Architecture

### What to Protect With Turnstile

Protect anonymous expensive starts:

- `POST /api/game-analysis/import` for Chess.com URL.
- `POST /api/game-analysis/import` for Lichess URL.
- `POST /api/game-analysis/import` for PGN.
- Any public `POST /api/game-analysis` path if it remains exposed.

Do not use interactive Turnstile for normal polling or cached lookup reads:

- `GET /api/game-analysis/import/chess-com/live/{id}`
- `GET /api/game-analysis/import/lichess/{id}`
- `GET /api/game-analysis/{analysis_id}`

Those should be protected with Cloudflare rate limits, backend Redis limits, adaptive polling, and idempotent cached responses.

### Frontend Policy

Use explicit rendering because this is a Vite/React SPA. Load the Turnstile script early when `VITE_G6_TURNSTILE_SITE_KEY` is configured, then render the widget when the user has a valid import candidate or an uncached route needs import.

Proposed states:

```text
idle
  -> validating_input
  -> verifying_browser
  -> submitting_import
  -> polling
  -> succeeded | failed | cooldown
```

Important details:

- No first POST without token when Turnstile is enabled.
- Do not keep a token after any submit attempt. Tokens are single-use and five-minute scoped.
- If backend returns `turnstile_failed`, treat it as stale/invalid token recovery, reset, and ask for a new token.
- If backend returns `429`, show cooldown and do not render Turnstile as the fix.
- For direct routes, keep the cached GET first. Only request Turnstile if the GET returns clean `404`.
- Use Turnstile `action` such as `import_start`. Add `cData` only if it is non-sensitive and validated server-side.

### Backend Policy

Backend has to remain authoritative:

- Validate token with Cloudflare Siteverify before Chess.com resolution, PGN parsing that can become expensive, job creation, or worker spawn.
- Validate `hostname` and `action` in the Siteverify response.
- Include normalized client IP when available from trusted Cloudflare/Modal headers.
- Add Redis admission checks before expensive work:
  - per-IP import start limit;
  - per-source idempotency lock for same Chess.com/Lichess URL;
  - per-PGN hash idempotency lock;
  - global worker-spawn budget;
  - Chess.com egress budget;
  - poll limit.
- Missing/invalid token should be a fast `403` with stable code like `turnstile_required` or `turnstile_failed`.
- Rate limit should be `429` with `Retry-After` and a stable code like `import_start_rate_limited`.

### Cloudflare Policy

Use Cloudflare for coarse gateway defense and origin bypass resistance:

- Frontend and API hostnames should be proxied by Cloudflare.
- API origin must not be reachable directly outside Cloudflare/Modal proxy auth.
- Apply WAF and route allowlists at the edge.
- Apply edge rate limits for global API, import starts, cached lookups, and polling.
- Treat Cloudflare limits as coarse filters only; Redis remains the product-aware limit.

Pre-clearance is worth considering if the API is behind Cloudflare WAF challenges and you want a smoother SPA/fetch experience. It lets a Turnstile widget issue `cf_clearance` for a protected zone, but it requires correct hostname/zone configuration. It should complement, not replace, backend Siteverify for import-start tokens unless you intentionally move the challenge decision entirely to WAF for that endpoint.

## Remediation Roadmap

### Immediate

1. Frontend: change URL, PGN, random game, and uncached route imports so no `POST /api/game-analysis/import` fires before Turnstile succeeds when the site key is configured.
2. Frontend: add a clear verification state instead of showing a delayed generic import failure.
3. Frontend tests: invert the existing Turnstile tests so they fail on the current tokenless first POST.
4. Backend: ensure missing token is rejected before any resolver/job work.

### Near-Term

1. Backend: split `turnstile_required`, `turnstile_failed`, and `turnstile_expired` or document one stable code with clear frontend handling.
2. Backend: add Redis idempotency locks for external source and PGN hash before worker spawn.
3. Frontend: add cooldown UI for 429 on submit, cached lookup, and poll surfaces.
4. Docs: fix the audit index missing-plan reference.

### Strategic

1. Put Cloudflare pre-clearance behind a feature flag if WAF-protected fetch requests become necessary.
2. Add observability for challenge outcomes, denied starts, allowed starts, duplicate source reuse, worker spawns, and upstream Chess.com failures.
3. Run staging drills for direct route load, repeated imports, duplicate games, expired Turnstile token, and blocked direct origin access.

## Experiments and Checks

| Command or experiment | Purpose | Result | Notes |
| --- | --- | --- | --- |
| `git status --short` | Check worktree before audit artifacts | Passed | Existing user edits found; product code left untouched. |
| `rg -n "turnstile|Turnstile|429|import" src README.md audit/README.md` | Locate Turnstile/import/rate-limit code paths | Passed | Turnstile handling is concentrated in `AnalysisImportPanel` and `AnalysisWorkspace`. |
| `sed -n ... src/components/analysis/AnalysisImportPanel.tsx` | Trace manual import behavior | Passed | First POST happens before challenge unless token already exists. |
| `sed -n ... src/components/analysis/AnalysisWorkspace.tsx` | Trace direct route behavior | Passed | Route import first POST happens before `turnstileRequired` is true. |
| Cloudflare docs review | Check current Turnstile guidance | Passed | SPA explicit rendering is appropriate; server validation is mandatory; pre-clearance is available for protected zones. |

## Residual Risk

This audit cannot prove the backend currently performs token validation before expensive work, because backend source is outside this checkout. The frontend evidence is enough to explain the production UX issue, but the full security fix must be verified in the private backend and Cloudflare configuration.

No product-code checks were run because this was a docs-only audit and the worktree contains unrelated user edits.

