# Codebase Audit Report

Date: 2026-05-05
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Auditor: Codex
Related event log: `./2026-05-05-codebase-audit-event-log.md`

## Executive Summary

The frontend is small, coherent, and well covered for the current import-to-board flow. Typecheck, Biome, Vitest, and the Vite production build all pass. The strongest parts of the codebase are the focused route/import tests, the snapshot mapping tests, and the isolation of Stockfish state behind a runtime store.

The main risks are at the boundaries: API responses and persisted job data are trusted as TypeScript shapes at runtime, polling follows backend-provided URLs directly, imported games are always mapped to white perspective, and the browser Stockfish path has large deployment assets with a silent failure mode. A dependency audit also currently fails on `happy-dom` advisories pulled through `vitest`.

## Scope

- Included: React/Vite runtime entry points, import and polling flow, API/type contracts, snapshot mapping, analysis workspace state, local Stockfish integration, routing, tests, package metadata, build output, and dependency audit.
- Excluded: Python backend implementation, deployed infrastructure, Chess.com API behavior, visual browser QA, and backend database/storage internals.
- Repository instructions followed: README commands and the audit skill workflow. No `AGENTS.md` was present.
- Constraints or blockers: The audit ran against the local working tree only. The initial `git status --short` showed modified product files, so product code was treated read-only. No backend server or real API credentials were available.

## Methodology

The audit used targeted source reads, contract tracing, and project gates. The highest-risk flows were traced from user entry through route parsing, import requests, polling, snapshot mapping, board state, Stockfish analysis, and tests. Existing checks were run before writing findings: `bun run typecheck`, `bun run lint`, `bun run test`, `bun run build`, and `bun audit`.

## System Map

- Runtime shell: `src/main.tsx` mounts `App`, which renders `AnalysisWorkspace`.
- Import boundary: `AnalysisImportPanel` builds `GameAnalysisImportRequest` values for Chess.com live URLs and PGN fallback. `src/lib/api.ts` sends requests to `VITE_G6_API_BASE_URL` or the localhost default.
- Routing: `src/lib/analysis-routing.ts` parses `/game/live/:id`, `/analysis/:id`, and `?analysis=&ply=` share links, then `AnalysisWorkspace` rewrites canonical URLs.
- Polling and persistence: `AnalysisWorkspace` stores active analysis jobs in `localStorage`, polls `status_url`, maps snapshots, and keeps share URLs updated.
- API contracts: `src/types/api.ts` mirrors backend payloads. `src/types/analysis.ts` is the frontend board/workspace model.
- Mapping: `src/lib/game-analysis-mapping.ts` converts `GameAnalysisSnapshot` moves with context into `AnalysisResponse`, move markers, timeline points, book lines, and explanation cards.
- Board and analysis UI: `AnalysisGameWorkspace` manages current ply, preview, discovery, mobile tabs, browser/server engine-line selection, and player metadata. `UltraAnalysisBoard` wraps UltraChess.
- Local engine: `useStockfish` creates `/stockfish/stockfish-18-single.js`, parses UCI info lines, caches analyses by FEN, and pre-analyzes nearby positions. `StockfishAnalysisRuntime` exposes snapshots through an external store.
- Tests: 10 Vitest files cover API calls, mapping, import routing, pre-analysis selection, position info interactions, engine display throttling, and a performance baseline.
- Build/deployment assets: `package.json` copies Stockfish worker and wasm into `public/stockfish` during postinstall. Vite copies them to `dist/stockfish`.

## Findings Overview

| ID | Severity | Category | Confidence | Title | Fix Priority |
| --- | --- | --- | --- | --- | --- |
| F-001 | High | security | High | Dependency audit fails on `happy-dom` advisories via `vitest` | Immediate |
| F-002 | Medium | typing | High | API and persisted job payloads are trusted without runtime validation | Immediate |
| F-003 | Medium | security | Medium | Polling follows unvalidated `status_url` values | Immediate |
| F-004 | Medium | correctness | High | Imported analyses are always mapped to white perspective | Near-term |
| F-005 | Medium | performance | High | Production output carries a 112 MB Stockfish wasm and a large JS chunk | Near-term |
| F-006 | Low | observability | High | Browser Stockfish failures are silent | Near-term |

## Confirmed Findings

### F-001: Dependency Audit Fails on `happy-dom` Advisories via `vitest`

- Severity: High
- Category: security
- Confidence: High
- Status: Confirmed
- Evidence: `bun audit` exits 1 and reports `happy-dom <20.0.0` through `vitest` with one critical VM context escape advisory and two high advisories. `package.json` uses `vitest` for tests, and `bun pm ls --depth 0` shows `vitest@4.1.5`.
- Impact: Runtime production users are not directly exposed because this is a dev/test dependency path. CI and local test environments still carry a known critical advisory, and any future audit gate will fail until the dependency tree is updated.
- Reproduction or experiment: Run `bun audit`.
- Recommended fix: Update `vitest` to a release that no longer resolves vulnerable `happy-dom`, or add a targeted override if compatible. Keep `jsdom` as the configured test environment unless a test suite explicitly needs `happy-dom`.
- Verification: `bun audit`, `bun run test`.

### F-002: API and Persisted Job Payloads Are Trusted Without Runtime Validation

- Severity: Medium
- Category: typing
- Confidence: High
- Status: Confirmed
- Evidence: `src/lib/api.ts:76` to `src/lib/api.ts:95` casts `response.json()` directly to generic `T`. `src/components/analysis/AnalysisWorkspace.tsx:1584` to `src/components/analysis/AnalysisWorkspace.tsx:1601` validates only `analysis_id` and `status_url` when reading stored jobs, then preserves unvalidated `source`. `src/lib/document-title.ts:20` to `src/lib/document-title.ts:36` assumes stored `source.white_username` and `source.black_username` are strings or null. `src/lib/game-analysis-mapping.ts:34` to `src/lib/game-analysis-mapping.ts:56` assumes deeply nested snapshot context fields exist.
- Impact: Backend contract drift, a partial response, or corrupted `localStorage` can crash rendering or convert a recoverable import problem into a generic failed state. This is especially risky because the app persists jobs between sessions and uses backend-owned snapshot data as the board model.
- Reproduction or experiment: Source trace. Existing tests use typed fixtures and do not cover malformed API payloads or malformed stored `source` values.
- Recommended fix: Add runtime schemas at the boundary for `GameAnalysisImportResponse`, `GameAnalysisSnapshot`, and `StoredGameAnalysisJob`. Reject or repair malformed stored jobs, show a specific contract error for malformed API payloads, and keep mapper internals typed against already-validated data.
- Verification: Add tests for malformed response JSON, missing nested snapshot fields, invalid stored `source`, and old localStorage shapes; then run `bun run test`.

### F-003: Polling Follows Unvalidated `status_url` Values

- Severity: Medium
- Category: security
- Confidence: Medium
- Status: Confirmed
- Evidence: `src/lib/api.ts:57` to `src/lib/api.ts:62` polls the supplied `statusUrl`. `src/lib/api.ts:98` to `src/lib/api.ts:103` returns absolute `http` and `https` URLs unchanged. `src/components/analysis/AnalysisWorkspace.tsx:1544` to `src/components/analysis/AnalysisWorkspace.tsx:1547` stores the backend response `status_url`, and `src/components/analysis/AnalysisWorkspace.tsx:1597` to `src/components/analysis/AnalysisWorkspace.tsx:1600` restores it from localStorage.
- Impact: A compromised or buggy backend response, or a corrupted persisted job, can make the browser issue polling requests to arbitrary HTTP(S) URLs. Fetch CORS still limits response access, but the request is still sent and the analysis flow can be held in a misleading failed/polling state.
- Reproduction or experiment: Source trace. Tests assert normal relative status URL polling but do not reject absolute or cross-origin `status_url` values.
- Recommended fix: Derive the polling path from `analysis_id` on the client, or validate `status_url` as a same-API-origin `/api/game-analysis/...` path before storing or polling. Drop stored jobs with invalid status URLs.
- Verification: Add tests for cross-origin response `status_url`, localStorage with an external `status_url`, and valid relative status URLs.

### F-004: Imported Analyses Are Always Mapped to White Perspective

- Severity: Medium
- Category: correctness
- Confidence: High
- Status: Confirmed
- Evidence: `src/lib/game-analysis-mapping.ts:42` to `src/lib/game-analysis-mapping.ts:56` hardcodes `player_side: "white"`. `AnalysisGameWorkspace` uses `analysis.player_side` for board orientation and sound/player perspective at `src/components/analysis/AnalysisWorkspace.tsx:416` to `src/components/analysis/AnalysisWorkspace.tsx:423`, board orientation at `src/components/analysis/AnalysisWorkspace.tsx:479`, and engine-line player-side selection at `src/components/analysis/AnalysisWorkspace.tsx:1276` to `src/components/analysis/AnalysisWorkspace.tsx:1279`.
- Impact: Imported games where the relevant user played black will default to the wrong board orientation and can color/evaluate explanations from the wrong player perspective. The UI has a flip button, but first-load orientation and perspective-sensitive labels still start wrong.
- Reproduction or experiment: Source trace. Mapping tests assert title, headers, classifications, and eval conversion, but there is no black-player import fixture.
- Recommended fix: Extend the backend import metadata or frontend import request with an explicit perspective field. For Chess.com URLs, capture the analyzed username if available; for PGN, expose a user-selected side or default to neutral board orientation. Map `player_side` from that contract instead of hardcoding white.
- Verification: Add mapping and workspace tests for black perspective, including initial board orientation, player metadata, and engine-line coloring.

### F-005: Production Output Carries a 112 MB Stockfish Wasm and a Large JS Chunk

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence: `package.json:11` copies Stockfish assets to `public/stockfish` on postinstall. `src/hooks/useStockfish.ts:196` creates `new Worker("/stockfish/stockfish-18-single.js")`. `bun run build` passes but reports `dist/assets/index-6p-JO7U5.js` at 520.67 kB minified, over Vite's warning threshold. `du -sh dist dist/stockfish/stockfish-18-single.wasm` reports `dist` at 113 MB and `dist/stockfish/stockfish-18-single.wasm` at 112 MB.
- Impact: The initial JS chunk is already above the default warning budget, and the deployment artifact is dominated by a very large public wasm. Even if the engine is created lazily, hosts still need to store, deploy, cache, and serve the asset. This can increase deploy time, cache pressure, and failure rates on constrained hosting.
- Reproduction or experiment: Run `bun run build`, then `du -sh dist dist/stockfish/stockfish-18-single.wasm dist/stockfish/stockfish-18-single.js`.
- Recommended fix: Add explicit bundle and asset budgets. Consider code-splitting route-level UI, moving the Stockfish worker behind a versioned CDN or optional engine package, serving compressed wasm with long cache headers, or using a smaller engine build for browser fallback analysis.
- Verification: Build budget check in CI, production asset size report, and browser test that engine fallback still loads after any asset strategy change.

### F-006: Browser Stockfish Failures Are Silent

- Severity: Low
- Category: observability
- Confidence: High
- Status: Confirmed
- Evidence: `src/hooks/useStockfish.ts:190` to `src/hooks/useStockfish.ts:280` creates the worker and handles UCI messages, but no `worker.onerror`, `worker.onmessageerror`, constructor failure handling, or error state is exposed. `StockfishAnalysisSnapshot` in `src/components/analysis/StockfishAnalysisRuntime.tsx:7` to `src/components/analysis/StockfishAnalysisRuntime.tsx:14` contains readiness and analysis state but no error.
- Impact: Missing worker assets, unsupported wasm, MIME/CSP problems, or worker crashes leave discovery and preview positions without browser engine lines. Users see absent or stale analysis instead of a clear nonblocking engine-unavailable state.
- Reproduction or experiment: Source trace. The test suite mocks the happy path and display gating, but does not simulate worker construction or runtime errors.
- Recommended fix: Track `error: string | null` in `useStockfish`, attach worker error handlers, catch worker construction failures, clear stale engine output on fatal errors, and render a compact unavailable state where browser-only lines are expected.
- Verification: Hook tests with a throwing Worker constructor and `worker.onerror`; workspace tests for missing-server-lines fallback showing a stable unavailable state.

## Risks and Follow-Ups

- Shared in-progress `?ply=` links are intentionally clamped once and do not jump when later snapshots add more moves. `AnalysisWorkspace.test.tsx:265` to `src/components/analysis/AnalysisWorkspace.test.tsx:292` asserts this. Confirm whether that is desired for shared links to still-running analyses.
- `apiError` only displays string `detail` values at `src/lib/api.ts:106` to `src/lib/api.ts:114`. FastAPI validation errors often use object/list details, so users may see only `API request failed with 422`.
- The frontend has no durable API contract document beyond TypeScript mirrors and tests. Backend/frontend contract changes should be versioned or documented together.

## Experiments and Checks

| Command or experiment | Purpose | Result | Notes |
| --- | --- | --- | --- |
| `git status --short` | Check worktree before audit edits | Observed modified product files initially | Product code was treated read-only |
| `bun run typecheck` | TypeScript project references | Passed | No output after `tsc -b` |
| `bun run lint` | Biome check | Passed | 61 files checked |
| `bun run test` | Unit and integration tests | Passed | 10 files, 44 tests |
| `bun run build` | Production build | Passed with warning | JS chunk warning at 520.67 kB |
| `du -sh dist dist/stockfish/stockfish-18-single.wasm dist/stockfish/stockfish-18-single.js` | Build artifact sizing | Completed | `dist` 113 MB, wasm 112 MB, worker JS 24 KB |
| `bun audit` | Dependency advisory scan | Failed | 3 advisories via `happy-dom <20.0.0` |
| Source trace: API JSON and localStorage | Validate runtime contract assumptions | Finding | F-002 |
| Source trace: polling target handling | Validate URL trust boundary | Finding | F-003 |
| Source trace: perspective mapping | Validate player-side model | Finding | F-004 |

## Architectural Themes

- Boundary validation is thin. The codebase has useful TypeScript contracts, but the runtime boundary still trusts network JSON and persisted browser state.
- The app cleanly separates server engine lines from browser engine fallback, but the fallback path needs operational treatment: explicit error state, asset budget, and deployment strategy.
- Tests cover the intended user flow well. The largest remaining test gaps are negative contract tests, corrupted persistence tests, dependency/security gates, and browser engine failure tests.
- The README is concise and accurate for local execution, but there is no documented frontend/backend contract for `GameAnalysisSnapshot`, polling URL ownership, or player perspective semantics.

## Remediation Roadmap

### Immediate

- Update or override the `happy-dom` dependency path so `bun audit` passes.
- Add runtime validation for import responses, snapshots, and stored jobs.
- Stop polling arbitrary absolute `status_url` values; derive or validate same-origin API polling paths.

### Near-Term

- Add a player perspective contract and map imported analyses from that contract.
- Add tests for malformed backend payloads, malformed localStorage, cross-origin status URLs, and black-side imports.
- Add Stockfish worker error handling and user-visible unavailable state.
- Add bundle and public asset budget checks.

### Strategic

- Document the frontend/backend game-analysis contract with field ownership, versioning, nullability, and migration behavior.
- Split heavy UI/engine code where practical and define a production browser-engine asset strategy.
- Add a lightweight release checklist that runs typecheck, lint, tests, build, and dependency audit.

## Documentation Updates Needed

- README or `docs/` contract page for `GameAnalysisImportResponse`, `GameAnalysisSnapshot`, and polling semantics.
- Deployment note for Stockfish asset generation, expected size, cache headers, and failure handling.
- Test strategy note for contract validation and negative payload fixtures.

## Residual Risk

The backend was not available, so backend contract claims were inferred from frontend types and fixtures. No visual browser QA was run, so layout/accessibility risks are limited to source-level observations. Dependency advisory status is current only for the local `bun audit` run on 2026-05-05.
