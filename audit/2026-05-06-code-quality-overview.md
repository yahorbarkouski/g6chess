# Code Quality Overview

Date: 2026-05-06
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Related event log: `./2026-05-06-code-quality-overview-event-log.md`

## Executive Summary

This repository is in good working shape for a compact public Vite/React frontend. The main import-to-analysis workflow is covered by focused tests, TypeScript is strict, Biome is clean, and the production build succeeds. The codebase shows clear product boundaries: the frontend imports games, polls the private analysis API, maps snapshots into a board model, renders the review surface, and uses browser Stockfish only as a fallback/exploration path.

The quality assertion is: **good application code, not yet release-clean operationally**. The biggest issues are not style or general maintainability failures. They are boundary and deployment risks: dependency audit currently fails through `vitest -> happy-dom`; API JSON and persisted jobs are still trusted as TypeScript shapes at runtime; stored/import response `status_url` values can still drive polling; `player_side` remains hardcoded even though route-level Lichess board orientation is now handled; browser Stockfish lacks an error state; and the built artifact is dominated by a 112 MB Stockfish wasm asset.

## Scope

- Included: README/package metadata, audit index, routing/import flow, API client, snapshot mapping, workspace state, persistence, Stockfish runtime, tests, TypeScript/Biome/Vitest/build/audit gates, Vercel headers/rewrites.
- Excluded: private backend behavior, real Chess.com/Lichess API behavior, deployed Vercel runtime, visual browser QA, accessibility tree inspection, production observability.
- Repository instructions followed: startup path from the provided AGENTS.md text; dated audit files treated as context and rechecked against current source.
- Constraints: no backend server was used, so backend contract claims are frontend-source and fixture based.

## Methodology

I traced the primary runtime path from route/import input through `src/lib/analysis-routing.ts`, `src/lib/api.ts`, `src/components/analysis/AnalysisWorkspace.tsx`, `src/lib/game-analysis-mapping.ts`, `src/components/analysis/StockfishAnalysisRuntime.tsx`, and `src/hooks/useStockfish.ts`. I also inspected the type contracts in `src/types/api.ts` and `src/types/analysis.ts`, reviewed test distribution, checked config/deployment files, and ran the current project gates.

## System Map

- App entry: `src/main.tsx` mounts `src/App.tsx`, which renders `AnalysisWorkspace`.
- Routing: `src/lib/analysis-routing.ts` parses Chess.com, Lichess, direct analysis, orientation, and ply state. It also builds canonical share paths and derives canonical polling paths with `analysisStatusUrl`.
- Import and polling: `src/lib/api.ts` sends import/cache/poll requests against `VITE_G6_API_BASE_URL` or localhost. `AnalysisWorkspace` owns active job state, Turnstile admission flow, polling, localStorage persistence, and URL updates.
- Data contracts: `src/types/api.ts` mirrors backend import/snapshot payloads. `src/types/analysis.ts` defines the frontend board/workspace model.
- Mapping: `src/lib/game-analysis-mapping.ts` maps snapshots and game skeletons into `AnalysisResponse`, timeline points, move markers, engine lines, book lines, and explanation cards.
- Board workspace: `AnalysisWorkspace.tsx` owns current ply, board orientation, discovery/preview, browser/server line selection, responsive layout selection, and move navigation.
- Browser engine: `src/hooks/useStockfish.ts` creates `/stockfish/stockfish-18-single.js`, parses UCI output, caches FEN analyses, throttles display commits, and pre-analyzes nearby missing positions. `StockfishAnalysisRuntime` publishes engine state through an external store and selector API.
- Tests: 13 Vitest files and 81 tests cover import/routing, analysis mapping, document title, chess formatting, Stockfish display gating, pre-analysis selection, workspace behavior, move list render scope, engine/book line display, and focused performance baselines.

## Findings Overview

| ID | Severity | Category | Confidence | Title | Fix Priority |
| --- | --- | --- | --- | --- | --- |
| F-001 | High | security | High | Dependency audit fails on `happy-dom` advisories through `vitest` | Immediate |
| F-002 | Medium | typing | High | Runtime API and persisted-job validation is still thin | Immediate |
| F-003 | Medium | security | Medium | Polling still accepts backend or stored `status_url` values | Immediate |
| F-004 | Medium | performance | High | Production artifact is 113 MB because of browser Stockfish | Near-term |
| F-005 | Low | observability | High | Browser Stockfish failures remain silent | Near-term |
| F-006 | Low | maintainability | High | `AnalysisWorkspace.tsx` is carrying too many responsibilities | Near-term |
| F-007 | Low | correctness | Medium | Player perspective remains under-modeled beyond board orientation | Near-term |

## Confirmed Findings

### F-001: Dependency Audit Fails on `happy-dom` Advisories Through `vitest`

- Severity: High
- Category: security
- Confidence: High
- Status: Confirmed
- Evidence: `bun audit` exits 1 and reports `happy-dom <20.0.0` via `vitest`, with one critical VM context escape advisory and two high advisories. `package.json` declares `vitest@^4.1.5`; `vite.config.ts:17` to `vite.config.ts:20` uses `jsdom`, not Happy DOM, but the advisory is still present in the installed dependency graph.
- Impact: This is not a production browser dependency, but it blocks a clean security gate and leaves local/CI test environments with a known critical advisory path.
- Reproduction or experiment: `bun audit`
- Recommended fix: Update `vitest` or apply a targeted compatible override so the vulnerable `happy-dom` path is gone. Keep the test environment on `jsdom` unless a test explicitly needs Happy DOM.
- Verification: `bun audit` and `bun run test`

### F-002: Runtime API and Persisted-Job Validation Is Still Thin

- Severity: Medium
- Category: typing
- Confidence: High
- Status: Confirmed
- Evidence: `src/lib/api.ts:66` to `src/lib/api.ts:85` casts `response.json()` directly to generic `T`. `src/components/analysis/AnalysisWorkspace.tsx:2178` to `src/components/analysis/AnalysisWorkspace.tsx:2200` validates only the top-level stored `analysis_id`, `status_url`, and orientation shape, then preserves unvalidated `source` and `game`. `src/lib/game-analysis-mapping.ts:32` to `src/lib/game-analysis-mapping.ts:71` assumes snapshot data is already structurally valid.
- Impact: Backend drift, partial responses, or corrupted localStorage can surface as render failures, confusing import failures, or incorrect board state instead of controlled contract errors.
- Reproduction or experiment: Source trace. The current tests use typed fixtures and focus on valid payloads.
- Recommended fix: Add runtime schemas or small boundary validators for `GameAnalysisImportResponse`, `GameAnalysisSnapshot`, and `StoredGameAnalysisJob`. Keep mapper internals typed against already-validated data.
- Verification: Add tests for malformed import responses, malformed snapshots, and corrupted stored jobs; run `bun run test`.

### F-003: Polling Still Accepts Backend or Stored `status_url` Values

- Severity: Medium
- Category: security
- Confidence: Medium
- Status: Confirmed
- Evidence: `src/lib/api.ts:39` to `src/lib/api.ts:43` accepts a `statusUrl`; `src/lib/api.ts:88` to `src/lib/api.ts:94` returns absolute HTTP(S) URLs unchanged. Newer route paths correctly derive direct analysis polling from `analysisStatusUrl` in `src/lib/analysis-routing.ts:178` to `src/lib/analysis-routing.ts:180`, but imported/cached/stored jobs still persist and poll `response.status_url` through `AnalysisWorkspace`.
- Impact: A compromised backend response or manually corrupted localStorage can make the browser send polling requests to arbitrary HTTP(S) URLs. CORS limits response access, but the request still leaves the browser and the UI can be forced into misleading states.
- Reproduction or experiment: Source trace plus existing tests that assert normal relative polling URLs.
- Recommended fix: Store/poll a client-derived `/api/game-analysis/{analysis_id}` path, or validate `status_url` as same API origin and expected path before storing or polling.
- Verification: Add tests for cross-origin `status_url` from import responses and localStorage, plus valid relative polling paths.

### F-004: Production Artifact Is 113 MB Because of Browser Stockfish

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence: `package.json` `postinstall` copies Stockfish worker/wasm assets into `public/stockfish`. `src/hooks/useStockfish.ts:190` to `src/hooks/useStockfish.ts:197` constructs `/stockfish/stockfish-18-single.js`. Current `bun run build` succeeds and emits `dist/assets/App-qGgJVo8r.js` at 435.88 kB minified, while `du -sh dist dist/stockfish/stockfish-18-single.wasm` reports `dist` at 113 MB and the wasm at 112 MB.
- Impact: The worker is lazy relative to normal render, but every deployment still needs to build, upload, cache, and serve a very large public asset. This raises hosting and cold-cache risk, especially on constrained devices or networks.
- Reproduction or experiment: `bun run build`; `du -sh dist dist/assets/* dist/stockfish/*`
- Recommended fix: Add explicit bundle/asset budgets. Decide whether browser Stockfish should be a separately cached CDN asset, a smaller fallback build, a capability-gated optional feature, or delayed until user intent.
- Verification: CI asset budget report and browser test proving fallback analysis still loads after the asset strategy changes.

### F-005: Browser Stockfish Failures Remain Silent

- Severity: Low
- Category: observability
- Confidence: High
- Status: Confirmed
- Evidence: `src/hooks/useStockfish.ts:190` to `src/hooks/useStockfish.ts:280` creates and manages the worker but does not catch constructor failures or attach `worker.onerror` / `worker.onmessageerror`. `src/components/analysis/StockfishAnalysisRuntime.tsx:7` to `src/components/analysis/StockfishAnalysisRuntime.tsx:14` exposes readiness and analysis state, but no error state.
- Impact: Missing worker assets, wasm/MIME/CSP failures, unsupported browsers, or worker crashes look like absent or stale browser engine lines. Users get no clear nonblocking explanation.
- Reproduction or experiment: Source trace.
- Recommended fix: Track `error: string | null` in `useStockfish`, publish it through the runtime snapshot, attach worker error handlers, and render a compact unavailable state where browser-only lines are expected.
- Verification: Hook tests for throwing `Worker` constructor and `worker.onerror`; workspace tests for engine unavailable fallback.

### F-006: `AnalysisWorkspace.tsx` Is Carrying Too Many Responsibilities

- Severity: Low
- Category: maintainability
- Confidence: High
- Status: Confirmed
- Evidence: `src/components/analysis/AnalysisWorkspace.tsx` is 2,521 lines, much larger than the next largest product files. It owns route restoration, import submission, cache lookup, Turnstile flow, polling, localStorage, document title, board workspace state, responsive layout, engine-line selection, board controls, and a large set of helper functions.
- Impact: The file is still understandable, but unrelated changes are more likely to conflict and regression tests have to exercise a broad surface for small behavior changes.
- Reproduction or experiment: `find src -maxdepth 3 -type f | sort | xargs wc -l | sort -nr`
- Recommended fix: Split by existing boundaries: a `useGameAnalysisJob` hook for route/import/polling/persistence, a board view-model hook for current-ply/preview/discovery/engine-line selection, and keep layout components mostly presentational.
- Verification: Existing `AnalysisWorkspace` tests should remain behaviorally identical after extraction; add hook-level tests for persistence/polling edge cases.

### F-007: Player Perspective Remains Under-Modeled Beyond Board Orientation

- Severity: Low
- Category: correctness
- Confidence: Medium
- Status: Likely
- Evidence: `src/lib/game-analysis-mapping.ts:49` to `src/lib/game-analysis-mapping.ts:53` and `src/lib/game-analysis-mapping.ts:88` to `src/lib/game-analysis-mapping.ts:92` still hardcode `player_side: "white"`. Recent tests show Lichess `/black` routes and pasted URLs orient the board correctly through `activeBoardOrientation`, but `analysis.player_side` still drives player-relative behavior such as moved-by-player sound/metadata in `AnalysisWorkspace`.
- Impact: Lichess board orientation is now handled better than the older general audit suggested, but the frontend still lacks a durable "analyzed player" or perspective contract. Any player-relative UI beyond board orientation may be wrong for black-side or neutral PGN analyses.
- Reproduction or experiment: Source trace plus tests around Lichess black orientation.
- Recommended fix: Add an explicit perspective/analyzed-player field to the import metadata or frontend selection model, and map `analysis.player_side` from that field instead of route orientation fallback.
- Verification: Tests for black-side player-relative behavior, not just board orientation.

## Strengths

- The main workflow has real coverage. `bun run test` passes 13 files and 81 tests, including import, route, share URL, Lichess orientation, Turnstile, snapshot mapping, book-line rendering, and performance-focused render tests.
- TypeScript config is strict: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, unused locals/params, and switch fallthrough checks are enabled in `tsconfig.app.json`.
- The app has a clean product boundary. README explicitly keeps the private chess truth/explanation engine out of this frontend and treats this repo as UI plus API contract.
- Routing is centralized and tested rather than scattered through components.
- Browser Stockfish state is isolated behind an external store with selectors, avoiding broad React re-render pressure from every engine tick.
- The Vercel config includes useful security/cache headers and SPA rewrites for the route families the app owns.

## Experiments and Checks

| Command or experiment | Purpose | Result | Notes |
| --- | --- | --- | --- |
| `git status --short` | Confirm worktree state before writing audit files | Clean before audit artifacts | No tracked user edits observed in scoped paths |
| `bun run typecheck` | TypeScript project references | Passed | `tsc -b` completed |
| `bun run lint` | Biome check | Passed | 60 files checked |
| `bun run test` | Unit/integration/perf tests | Passed | 13 files, 81 tests |
| `bun run build` | Production build | Passed | Largest JS chunk: 435.88 kB minified |
| `bun audit` | Dependency advisory scan | Failed | 3 advisories through `happy-dom <20.0.0` |
| `du -sh dist dist/assets/* dist/stockfish/*` | Build artifact size | Completed | `dist` 113 MB; Stockfish wasm 112 MB |
| Source trace: API/persistence | Boundary validation review | Finding | F-002/F-003 |
| Source trace: Stockfish runtime | Engine failure/deploy review | Finding | F-004/F-005 |
| Source trace: workspace size/responsibilities | Maintainability review | Finding | F-006 |

## Quality Assessment

Overall grade: **B / production-promising but not release-clean**.

The implementation is much healthier than a typical prototype: checks pass, tests are meaningful, types are strict, and domain boundaries are visible. The areas holding it back are the exact areas that tend to hurt public products after launch: runtime contract validation, dependency audit cleanliness, large optional assets, and explicit failure states around external/browser engine paths.

## Remediation Roadmap

### Immediate

1. Make `bun audit` pass by removing the vulnerable `happy-dom` path.
2. Stop trusting imported/cached/stored `status_url`; derive or strictly validate polling URLs.
3. Add runtime validation for import responses, snapshots, and stored jobs.

### Near-Term

1. Add Stockfish worker error handling and user-visible unavailable state.
2. Add bundle and public asset budgets, including a Stockfish-specific size check.
3. Split `AnalysisWorkspace` into route/job and board-view-model hooks.
4. Make player perspective explicit in the frontend/backend contract.

### Strategic

1. Publish a frontend/backend contract note for import responses, snapshots, polling semantics, nullability, and versioning.
2. Define a production browser-engine asset strategy: CDN/versioned cache, smaller build, or opt-in fallback.
3. Add a release checklist that includes typecheck, lint, tests, build, dependency audit, and asset-size review.

## Documentation Updates Needed

- README or contract doc for `GameAnalysisImportResponse`, `GameAnalysisSnapshot`, polling URL ownership, and player perspective.
- Deployment note for Stockfish asset size, cache headers, and failure handling.
- Audit index update for this code-quality overview.

## Residual Risk

No backend or real external import was exercised, so API compatibility is inferred from frontend contracts and tests. No visual browser QA or accessibility inspection was run. Local ignored environment files were observed but are not tracked by git and are covered by `.gitignore`; they were not treated as repository findings.
