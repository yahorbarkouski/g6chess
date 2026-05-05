# Routing and Shareability Audit Report

Date: 2026-05-05
Repository: /Users/yahorbarkouski/g6explanation-frontend
Auditor: Codex
Related event log: ./2026-05-05-routing-shareability-audit-event-log.md

## Executive Summary

The current frontend can import a Chess.com URL, poll an analysis job, and keep that job alive across reloads in the same browser. It does not currently make the page URL represent the imported game, the selected move, or the backend job. A shared browser URL therefore does not carry the analysis state.

The "type g6 before your chess.com game" product promise is achievable, but it is not implemented yet. The natural production shape is:

- `https://g6chess.com/game/live/{chessComGameId}` for direct Chess.com link interception.
- Optional position state such as `?ply=23` or `#ply=23` for sharing the selected move.
- A backend idempotent lookup so the same external Chess.com game resolves to the same existing job/result instead of starting analysis again.

The sibling backend already has useful primitives, but the frontend is not wired to them:

- Anonymous public route: `GET /api/v1/public/chess-com/live-games/{external_game_id}` resolves a finished Chess.com live game and caches the resolved PGN metadata in Redis for 24 hours, but intentionally does not persist or enqueue server-side analysis.
- Authenticated route: `POST /api/v1/imports/chess-com/live-games/{external_game_id}` persists/deduplicates a `Game` row for a user and queues server analysis. `GET /api/v1/games/{game_id}/analysis` returns persisted analysis and Redis-caches completed responses for 24 hours.
- Backend analysis cache: `analysis_cache` stores Stockfish payloads keyed by canonical move sequence and analysis configuration fingerprint, reducing repeated server Stockfish work across duplicate games.

The current frontend instead calls `/api/game-analysis/import` and polls a returned `status_url`. That contract was not found in the sibling backend during this audit, so either the frontend targets a different API service or the frontend/backend contracts have drifted.

## Scope

- Included:
  - Frontend import page copy, URL validation, API calls, polling, reload persistence, selected-ply state, and browser Stockfish cache.
  - Sibling backend public Chess.com live-game routes, authenticated import/analysis routes, and analysis/cache persistence.
  - Product interpretation of `g6chess.com/...` direct navigation and shareable analysis URLs.
- Excluded:
  - Full implementation.
  - Production hosting rewrite configuration.
  - Live external Chess.com network verification.
- Repository instructions followed:
  - Frontend README.
  - Backend `AGENTS.md` and local `app/`, `app/api/`, `app/schemas/`, and `app/services/platform_sync/` guidance for read-only inspection.
- Constraints or blockers:
  - Frontend worktree already had uncommitted changes in analysis/import files; no product code was modified.
  - The sibling backend does not expose the frontend's current `/api/game-analysis/import` route.

## Methodology

I traced the current frontend from `App` into `AnalysisWorkspace`, the import panel, API client, mapping layer, local storage, tests, and Stockfish hook. Then I inspected the sibling backend route composition, public Chess.com live-game route, authenticated imports, game-analysis read endpoint, persistence models, and analysis job cache. Commands were source-read and `rg` based; no external network calls were needed.

## System Map

### Current Frontend Flow

1. `src/App.tsx` always renders `AnalysisWorkspace`; there is no router.
2. `AnalysisImportPanel` validates pasted Chess.com-like URLs and says users can type `g6` before a Chess.com game URL.
3. On submit, `AnalysisWorkspace` calls `startImportedGameAnalysis`, which posts to `/api/game-analysis/import`.
4. The frontend stores only `{ analysis_id, status_url, source }` under `localStorage["g6explanation.currentGameAnalysis"]`.
5. On reload in the same browser, `AnalysisWorkspace` reads that localStorage pointer and resumes polling the stored `status_url`.
6. The completed or partial snapshot is mapped into the board UI when at least one move has context.
7. Selected ply is React state only. It is initialized to `1`, updated inside the workspace, and never serialized into the URL.
8. Browser Stockfish results are cached only in a React ref `Map<string, CachedAnalysis>` keyed by FEN; the cache disappears on page reload and is not shareable.

### Current Backend Primitives

1. Public guest bootstrap:
   - Route: `/api/v1/public/chess-com/live-games/{external_game_id}`.
   - Requires a numeric Chess.com live-game id.
   - Resolves callback headers, then fetches the matching monthly public archive PGN.
   - Caches the resolved normalized PGN in Redis under `public:chess_com:live_game:{external_game_id}` for `cache_ttl_public_live_game` seconds. Default is 86400.
   - Returns `AnalysisResponse(kind="guest_bootstrap")` with PGN headers/moves but empty `timeline`, `move_markers`, and `summary`.
   - Tests assert this route does not persist `Game` rows and does not enqueue server-side analysis.
2. Authenticated import:
   - Route: `/api/v1/imports/chess-com/live-games/{external_game_id}`.
   - Reuses an existing user-owned `Game` with the same `(user_id, platform, external_game_id)`.
   - Otherwise resolves the public game, persists a `Game`, and queues server-side analysis.
3. Authenticated analysis read:
   - Route: `/api/v1/games/{game_id}/analysis`.
   - Reads `Game.parsed_game_json` and `Game.analysis_payload_json`.
   - Returns partial timeline while a job is running.
   - Redis-caches completed analysis responses under `analysis:{user_id}:{game_id}` for `cache_ttl_analysis` seconds. Default is 86400.
4. Backend cross-game analysis cache:
   - Model: `AnalysisCache`.
   - Key: SHA-256 of the move sequence plus `analysis_config_fingerprint(time_class)`.
   - On a cache hit, the job completes from cached payload instead of rerunning server Stockfish.

## Findings Overview

| ID | Severity | Category | Confidence | Title | Fix Priority |
| --- | --- | --- | --- | --- | --- |
| F-001 | High | product-correctness | High | Import result is not represented in the browser URL | Immediate |
| F-002 | High | integration | High | Frontend import API contract does not match the inspected backend | Immediate |
| F-003 | Medium | product-correctness | High | `g6chess.com/game/live/{id}` direct navigation is promised but not implemented | Near-term |
| F-004 | Medium | storage | High | Frontend cache is local-only and does not make analysis shareable | Near-term |
| F-005 | Medium | architecture | Medium | Backend has two viable resolution models but no chosen public full-analysis contract | Strategic |

## Confirmed Findings

### F-001: Import Result Is Not Represented In The Browser URL

- Severity: High
- Category: product-correctness
- Confidence: High
- Status: Confirmed
- Evidence:
  - `/Users/yahorbarkouski/g6explanation-frontend/src/App.tsx` always renders `AnalysisWorkspace`; no router or route parsing exists.
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:89-180` holds active analysis/job state in React state and localStorage only.
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:1094-1128` reads/writes/removes `g6explanation.currentGameAnalysis`, but there is no `history.pushState`, `history.replaceState`, `window.location`, or query-param handling in the app code.
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:230-236` initializes `currentPly` to `1`; selected move state is not URL-backed.
- Impact:
  - Sharing the current page URL does not share the imported game, analysis job, or selected move.
  - A recipient with no matching localStorage sees the import screen.
  - A recipient with unrelated localStorage may resume their own previous job, which is worse than a clean miss.
- Reproduction or experiment:
  - Source trace and `rg` for URL/history APIs found no URL mutation or route parsing.
- Recommended fix:
  - Introduce a canonical route model, at minimum `/game/live/:externalGameId`.
  - On successful URL import or direct route load, call `window.history.replaceState` to canonicalize the URL.
  - Serialize selected ply as `?ply=N` or `#ply=N`, updated via `replaceState` while navigating.
  - On initial mount, parse the route before localStorage; route state must win over browser-local resume state.
- Verification:
  - Frontend tests for direct-load `/game/live/168193636078`, pasted Chess.com URL canonicalization, reload from canonical URL, and selected-ply restoration.
  - Browser smoke test opening a deep link in a clean profile.

### F-002: Frontend Import API Contract Does Not Match The Inspected Backend

- Severity: High
- Category: integration
- Confidence: High
- Status: Confirmed for inspected sibling backend
- Evidence:
  - Frontend posts `/api/game-analysis/import` from `/Users/yahorbarkouski/g6explanation-frontend/src/lib/api.ts:40-45`.
  - Frontend expects `{ analysis_id, status, status_url, source }` and a pollable `GameAnalysisSnapshot`.
  - `rg` over `/Users/yahorbarkouski/g6chess-backend` found no `/api/game-analysis/import`, `GameAnalysisSnapshot`, or `GameAnalysisImportResponse` implementation.
  - Backend routes are composed under `api_prefix="/api/v1"` in `/Users/yahorbarkouski/g6chess-backend/app/main.py:31`.
  - Backend import routes are `/api/v1/imports/chess-com/url` and `/api/v1/imports/chess-com/live-games/{external_game_id}`.
  - Backend analysis route is `/api/v1/games/{game_id}/analysis`.
- Impact:
  - The current frontend import flow cannot interoperate with the inspected backend without an API adapter, proxy, or separate service.
  - Route/shareability work could be built on the wrong contract if this is not resolved first.
- Reproduction or experiment:
  - Source search for the current frontend endpoint in the backend returned no matches.
- Recommended fix:
  - Decide which contract is authoritative:
    - Keep the frontend snapshot contract and add/restore backend endpoints for it.
    - Or migrate frontend to backend `AnalysisResponse`, `/public/chess-com/live-games/{id}`, `/imports/...`, and `/games/{id}/analysis`.
  - Add contract tests across frontend API client fixtures and backend route responses.
- Verification:
  - Integration test or MSW-style frontend test using real backend response shapes.
  - Backend route test for any new public/share endpoint.

### F-003: `g6chess.com/game/live/{id}` Direct Navigation Is Promised But Not Implemented

- Severity: Medium
- Category: product-correctness
- Confidence: High
- Status: Confirmed
- Evidence:
  - Import copy says: "or type g6 before your chess.com game" in `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisImportPanel.tsx:87-90`.
  - URL validation accepts Chess.com-style URL shapes in `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisImportPanel.tsx:26-27`.
  - There is no route parser for the production-domain equivalent path.
  - Backend authenticated URL extraction supports `chess.com/(analysis/)?game/live/{id}` only in `/Users/yahorbarkouski/g6chess-backend/app/api/imports.py:51-56`.
  - Backend public route only supports numeric live-game ids.
- Impact:
  - A user who changes `www.chess.com/game/live/123` to `g6chess.com/game/live/123` would only reach the SPA shell, not automatically resolve the game.
  - The frontend's copy also shows `chess.com/game/...`, while the backend public/import primitives are centered on `game/live/{id}`.
- Reproduction or experiment:
  - Source trace found no route parser and no route test.
- Recommended fix:
  - Add a route parser that recognizes:
    - `/game/live/:id`
    - `/analysis/game/live/:id` if Chess.com analysis links need to preserve that shape.
    - Potentially `/game/:id` only if the backend can resolve it.
  - Update copy to show the exact production-domain shape, for example `g6chess.com/game/live/...`.
  - Configure production hosting to serve the SPA for these deep links.
- Verification:
  - Tests for all accepted path variants.
  - Browser test loading a deep URL directly, not only navigating from `/`.

### F-004: Frontend Cache Is Local-Only And Does Not Make Analysis Shareable

- Severity: Medium
- Category: storage
- Confidence: High
- Status: Confirmed
- Evidence:
  - Frontend localStorage stores only the job pointer in `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:1094-1128`.
  - It does not store a completed `GameAnalysisSnapshot`.
  - Browser Stockfish cache is a `useRef(new Map())` in `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts:71`; it is process-local and lost on reload.
  - Frontend tests assert localStorage contains the job id after import and is cleared by "Back to import", but do not assert URL state.
- Impact:
  - The current reload persistence is useful only for the same browser.
  - It cannot prevent a fresh recipient from starting or resolving analysis again.
  - It cannot restore selected move state after share/reload.
- Reproduction or experiment:
  - Source trace of storage APIs and tests.
- Recommended fix:
  - Treat URL as the share contract, not localStorage.
  - Keep localStorage only as a convenience fallback for same-browser in-progress jobs.
  - If client-side Stockfish analysis remains part of the guest experience, consider IndexedDB only as a performance cache, not as the source of truth.
- Verification:
  - Clean-browser deep-link test.
  - Same-browser reload test.
  - Back-to-import test should clear local resume state without destroying canonical external-id route behavior unexpectedly.

### F-005: Backend Has Two Viable Resolution Models But No Chosen Public Full-Analysis Contract

- Severity: Medium
- Category: architecture
- Confidence: Medium
- Status: Likely
- Evidence:
  - Public guest bootstrap returns `kind="guest_bootstrap"` with empty server analysis artifacts and explicitly says browser Stockfish supplies analysis in `/Users/yahorbarkouski/g6chess-backend/app/services/platform_sync/chess_com_public_live_game_service.py:116-145`.
  - Tests assert the public bootstrap does not persist rows or enqueue jobs in `/Users/yahorbarkouski/g6chess-backend/tests/api_contracts/integration/test_public_live_games_api.py:107-144`.
  - Authenticated import persists games and queues analysis, and analysis retrieval is user-scoped in `/Users/yahorbarkouski/g6chess-backend/app/api/games.py:185-260`.
  - Analysis results are persisted on `Game.analysis_payload_json` and cached in Redis when ready.
  - Cross-game server analysis cache exists in `AnalysisCache`, keyed by move sequence plus analysis fingerprint.
- Impact:
  - The desired UX depends on a product decision:
    - Anonymous public links that show browser-side analysis only.
    - Authenticated/user-owned links that show persisted server analysis only to the owner.
    - Public share links that expose a sanitized/published server analysis snapshot.
  - Without that decision, frontend routing can make the URL pretty but cannot guarantee "analysis will not start again" for every recipient.
- Reproduction or experiment:
  - Backend source and contract-test trace.
- Recommended fix:
  - Pick the public sharing contract.
  - If public full analysis is desired, add an anonymous `GET /api/v1/public/chess-com/live-games/{id}/analysis` or `GET /api/v1/public/analyses/{analysis_id}` that:
    - Resolves by external id.
    - Reuses existing completed analysis by external id or analysis cache.
    - Starts one shared public job if no compatible completed result exists.
    - Returns status/progress and final sanitized `AnalysisResponse`.
    - Uses analysis fingerprinting for invalidation.
  - If public full analysis is not desired, make the product copy explicit that guest links run browser-side analysis and do not expose server-generated explanations.
- Verification:
  - Backend route tests for first request, in-progress polling, completed cache hit, stale fingerprint reanalysis, and public data redaction.

## What We Have Now Versus What We Want

### Now

- Import page accepts pasted Chess.com URLs and PGN.
- The current frontend page URL stays wherever the user started, usually `/`.
- Same-browser reload resumes only because localStorage remembers `{ analysis_id, status_url, source }`.
- Share links do not include game id, analysis id, or selected ply.
- Frontend selected move starts over at ply 1 after reload/share.
- Frontend browser Stockfish cache is in memory only.
- Inspected backend public guest route caches resolved PGN metadata, not full analysis.
- Inspected backend authenticated flow persists full analysis, but behind user-owned game ids.
- Frontend API contract appears drifted from the inspected backend.

### Target

- Pasting `https://www.chess.com/game/live/{id}` or opening `https://g6chess.com/game/live/{id}` enters the same code path.
- Once the app recognizes a Chess.com game, it canonicalizes the URL to the production-domain route.
- The selected ply is encoded in the URL, for example `https://g6chess.com/game/live/{id}?ply=23`.
- Reloading or opening the URL in a clean browser resolves the same Chess.com game.
- Backend import/analysis is idempotent by canonical external id and analysis fingerprint.
- Completed analysis is loaded from persisted backend storage or cache when compatible.
- In-progress analysis is polled from a stable route/job id, not only a browser-local localStorage key.
- PGN fallback receives a shareable analysis id only if the backend persists PGN submissions.

## Recommended Product/Technical Direction

### Recommended Route Contract

Use canonical production URLs:

- `https://g6chess.com/game/live/{externalGameId}`
- `https://g6chess.com/game/live/{externalGameId}?ply={ply}`

Use a separate route for non-Chess.com/PGN analysis:

- `https://g6chess.com/analysis/{analysisId}`
- `https://g6chess.com/analysis/{analysisId}?ply={ply}`

Reasoning:

- Chess.com links already contain a stable external id.
- Production-domain path rewriting is easy for users to understand: replace `www.chess.com` with `g6chess.com`.
- `analysisId` is the only stable option for PGN because there is no public external id.
- Ply as a query param is debuggable, copyable, and easy to preserve through server/CDN rewrites.

### Recommended State Priority On App Load

1. Route state from `window.location`.
2. Query/hash state such as `ply`.
3. Browser localStorage resume pointer.
4. Empty import page.

Route state should win because a copied URL is intentional and portable. localStorage should only resume unfinished work when no route is present.

### Recommended Backend Behavior

For Chess.com URL shares:

1. Extract external live-game id.
2. Resolve the public Chess.com game.
3. Check whether a compatible completed public/shared analysis exists.
4. If yes, return it immediately.
5. If no, create or reuse one public analysis job keyed by `(platform, external_game_id, analysis_fingerprint)`.
6. Poll a stable status URL until ready.
7. Cache final response in Redis and persist the authoritative payload.

For authenticated users:

- Existing user-owned import can keep using `Game`, but the frontend should still canonicalize to the external-id route or redirect to an owned game route intentionally.

For PGN:

- Persist PGN submissions under an `analysis_id` if shareability matters.
- Otherwise label PGN fallback as local/session-only.

## Experiments and Checks

| Command or experiment | Purpose | Result | Notes |
| --- | --- | --- | --- |
| `git status --short` | Check dirty worktree before audit docs | Passed | Existing frontend analysis/import edits were present before this audit. |
| `rg --files ...` | Map frontend project structure | Passed | Vite/React app with no router files. |
| `rg -n "localStorage|history|location|URLSearchParams|game-analysis"` | Find URL/storage behavior | Passed | localStorage exists; no URL mutation/parsing found. |
| `sed -n ... src/components/analysis/AnalysisWorkspace.tsx` | Trace frontend import lifecycle | Passed | Polls `status_url`, stores job pointer, maps snapshot. |
| `sed -n ... src/hooks/useStockfish.ts` | Trace browser Stockfish cache | Passed | In-memory FEN cache only. |
| `rg -n "/api/game-analysis|GameAnalysisSnapshot" /Users/yahorbarkouski/g6chess-backend` | Check backend support for frontend contract | No matches | Confirms contract drift for inspected backend. |
| `sed -n ... app/api/public_live_games.py` | Inspect public Chess.com route | Passed | Anonymous route resolves live-game id. |
| `sed -n ... chess_com_public_live_game_service.py` | Inspect public resolver/cache | Passed | Redis PGN cache; guest bootstrap only. |
| `sed -n ... app/api/imports.py` | Inspect authenticated import | Passed | User-owned import and dedupe. |
| `sed -n ... app/api/games.py` | Inspect analysis read/cache | Passed | Persisted analysis response cached in Redis after ready. |
| `sed -n ... job_service.py` | Inspect server analysis cache | Passed | `AnalysisCache` by move sequence and analysis fingerprint. |
| `bun run lint` | Validate frontend repo after docs-only audit artifacts | Passed | `biome check .` passed. |

## Architectural Themes

- URL state is currently missing, so the app cannot support direct links or sharing.
- Browser-local persistence is being used for resume convenience, but it is not a share contract.
- The backend already has pieces for idempotent resolution and caching, but they are split between anonymous guest bootstrap and authenticated full analysis.
- The frontend and inspected backend speak different API contracts.
- The product copy implies direct production-domain navigation before the route layer exists.

## Remediation Roadmap

### Immediate

- Decide the authoritative API contract for the import site.
- Add a frontend route parser for `/game/live/:externalGameId`.
- Canonicalize pasted Chess.com URLs with `history.replaceState`.
- Ensure route state overrides localStorage on load.
- Update tests to assert URL changes and direct deep-link loading.

### Near-Term

- Add selected-ply URL state.
- Align accepted URL shapes between frontend validation and backend extraction.
- Decide whether guest deep links use public bootstrap or full server analysis.
- If using backend public bootstrap, adapt frontend `AnalysisResponse` types/mappers to support `kind="guest_bootstrap"` with no markers.
- If using full analysis, add a public/shared persisted analysis endpoint.

### Strategic

- Add a stable public analysis resource keyed by canonical source plus analysis fingerprint.
- Make PGN fallback shareable through `/analysis/{analysisId}`.
- Add production hosting rewrite rules for SPA deep links.
- Add end-to-end tests for production-domain URL replacement:
  - Chess.com link pasted.
  - `g6chess.com/game/live/{id}` loaded directly.
  - Analysis in progress shared.
  - Completed analysis shared.
  - Selected ply shared.

## Documentation Updates Needed

- Frontend README should describe canonical routes and the API contract after implementation.
- Import page copy should use the exact final production URL pattern.
- Backend API docs should clarify anonymous guest bootstrap versus persisted/shared analysis.
- A short ADR should record the public analysis visibility/caching decision.

## Residual Risk

- I did not verify the real production host/CDN rewrite setup.
- I did not hit live Chess.com or backend endpoints over the network.
- The frontend may be targeting an API service other than the sibling `/Users/yahorbarkouski/g6chess-backend`; if so, this report's backend mismatch finding applies to the inspected sibling backend only.
- Existing uncommitted frontend changes were treated as current code and were not modified.
