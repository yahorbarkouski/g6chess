# Routing and Shareability Audit Event Log

Date: 2026-05-05
Repository: /Users/yahorbarkouski/g6explanation-frontend
Audit report: ./2026-05-05-routing-shareability-audit.md

## Resume State

- Current phase: Report complete; validation passed.
- Artifact paths:
  - `/Users/yahorbarkouski/g6explanation-frontend/audit/2026-05-05-routing-shareability-audit.md`
  - `/Users/yahorbarkouski/g6explanation-frontend/audit/2026-05-05-routing-shareability-audit-event-log.md`
- Last completed dimension: Frontend routing/storage and sibling backend cache/persistence.
- Next planned checks: None for this audit unless implementation is requested.
- Known blockers:
  - Frontend worktree had pre-existing/unrelated uncommitted code changes.
  - Sibling backend does not contain the frontend's current `/api/game-analysis/import` contract.
  - Production hosting rewrite config was not present in the frontend repo.

## Timeline

### Step 001 - Initialize Audit

- Action: Read audit skill instructions and established artifact shape.
- Reason: User asked for a deep dive and comprehensive current-versus-target view.
- Evidence inspected:
  - `/Users/yahorbarkouski/.codex/skills/audit/SKILL.md`
  - Audit report and event-log templates.
- Observations:
  - Skill requires durable report and event-log artifacts.
- Outcome:
  - Planned two new files in the existing `audit/` directory.

### Step 002 - Inspect Frontend Repository State

- Action: Ran `git status --short`, listed key repo files, read `README.md` and `package.json`.
- Reason: Establish project stack, checks, and dirty worktree before editing docs.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation-frontend/README.md`
  - `/Users/yahorbarkouski/g6explanation-frontend/package.json`
  - Existing `audit/` directory.
- Observations:
  - Stack is Bun, Vite, React, TypeScript, Tailwind, UltraChess.
  - README says import starts `POST /api/game-analysis/import` and polls returned `status_url`.
  - Worktree already had uncommitted changes in import/analysis UI files.
- Outcome:
  - No product code edits planned; audit docs only.

### Step 003 - Map Frontend Entry And API Layer

- Action: Read `src/App.tsx`, `src/main.tsx`, `src/lib/api.ts`, `src/types/api.ts`, and searched for routing/storage APIs.
- Reason: Determine whether page URL is parsed or mutated.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation-frontend/src/App.tsx`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/main.tsx`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/lib/api.ts`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/types/api.ts`
- Observations:
  - `App` always renders `AnalysisWorkspace`.
  - API client posts `/api/game-analysis/import` and polls arbitrary `status_url`.
  - No router, `history`, `location`, `URLSearchParams`, or route parser in app code.
- Outcome:
  - Confirmed missing URL state as a likely core issue.

### Step 004 - Trace Frontend Import Workspace

- Action: Read `AnalysisWorkspace.tsx`, including import polling and storage helpers.
- Reason: Understand local resume behavior and whether completed analysis is cached.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx`
- Observations:
  - `localStorage["g6explanation.currentGameAnalysis"]` stores `{ analysis_id, status_url, source }`.
  - On reload, the workspace polls the stored `status_url`.
  - Stored data does not include completed snapshot, selected ply, or external source route.
  - 404 clears local storage and active job.
- Outcome:
  - Confirmed same-browser resume exists, but shareable state does not.

### Step 005 - Trace Frontend Import Panel

- Action: Read `AnalysisImportPanel.tsx`.
- Reason: Evaluate the "g6 before your chess.com game" promise and accepted URL shapes.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisImportPanel.tsx`
- Observations:
  - Copy says users can type `g6` before a Chess.com game.
  - Validation accepts `chess.com/(game|live|analysis)/...` with optional subpaths and numeric ids.
  - Submit builds a `GameAnalysisImportRequest`.
- Outcome:
  - Confirmed product copy implies production-domain route behavior that does not exist yet.

### Step 006 - Inspect Frontend Tests And Mapping

- Action: Read `AnalysisWorkspace.test.tsx`, `api.test.ts`, and `game-analysis-mapping.ts`.
- Reason: Check expected behavior and whether tests cover URL/share behavior.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.test.tsx`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/lib/api.test.ts`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/lib/game-analysis-mapping.ts`
- Observations:
  - Tests assert import posts request, polls `status_url`, renders move, and stores job id in localStorage.
  - Tests assert "Back to import" clears localStorage.
  - No route, URL canonicalization, direct deep link, or selected-ply persistence tests.
- Outcome:
  - Added evidence for F-001 and F-004.

### Step 007 - Inspect Browser Stockfish Cache

- Action: Read `useStockfish.ts`.
- Reason: User specifically asked whether game analysis is cached.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts`
- Observations:
  - Browser Stockfish cache is `useRef<Map<string, CachedAnalysis>>(new Map())`.
  - It is keyed by FEN and is not persisted to localStorage/IndexedDB/backend.
- Outcome:
  - Confirmed browser analysis cache is in-memory only.

### Step 008 - Inspect Sibling Backend Instructions

- Action: Read backend `AGENTS.md` and local guidance for `app/`, `app/api/`, `app/schemas/`, and `platform_sync`.
- Reason: Backend inspection was required to answer cache/persistence questions.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6chess-backend/AGENTS.md`
  - `/Users/yahorbarkouski/g6chess-backend/app/AGENTS.md`
  - `/Users/yahorbarkouski/g6chess-backend/app/api/AGENTS.md`
  - `/Users/yahorbarkouski/g6chess-backend/app/schemas/AGENTS.md`
  - `/Users/yahorbarkouski/g6chess-backend/app/services/platform_sync/AGENTS.md`
- Observations:
  - Backend guidance allowed read-only inspection and emphasizes thin routes, typed schemas, and persistence boundaries.
- Outcome:
  - Continued read-only backend trace.

### Step 009 - Search Backend For Frontend Contract

- Action: Searched sibling backend for `/api/game-analysis`, `GameAnalysisSnapshot`, `GameAnalysisImportResponse`, `snapshot_version`, and related terms.
- Reason: Verify whether current frontend API exists.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6chess-backend/app`
  - `/Users/yahorbarkouski/g6chess-backend/tests`
  - `/Users/yahorbarkouski/g6chess-backend/docs`
- Observations:
  - No matching current frontend import contract was found.
  - Backend API prefix is `/api/v1`.
- Outcome:
  - Confirmed frontend/backend contract mismatch for the inspected sibling backend.

### Step 010 - Inspect Backend Public Chess.com Bootstrap

- Action: Read `app/api/public_live_games.py`, `chess_com_public_live_game_service.py`, and public route tests.
- Reason: Determine whether production-domain Chess.com routes can be resolved and cached.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6chess-backend/app/api/public_live_games.py`
  - `/Users/yahorbarkouski/g6chess-backend/app/services/platform_sync/chess_com_public_live_game_service.py`
  - `/Users/yahorbarkouski/g6chess-backend/tests/api_contracts/integration/test_public_live_games_api.py`
- Observations:
  - Public route resolves numeric live-game id.
  - Resolver checks Redis cache first.
  - It fetches Chess.com callback data, then monthly public archive PGN.
  - It caches resolved normalized PGN metadata for `cache_ttl_public_live_game`.
  - Guest bootstrap response intentionally has empty `timeline`, `move_markers`, and `summary`.
  - Tests assert public bootstrap does not persist game rows or enqueue analysis.
- Outcome:
  - Identified public bootstrap as useful for direct link resolution, not full cached server analysis.

### Step 011 - Inspect Backend Authenticated Import And Game Analysis

- Action: Read `app/api/imports.py`, `app/api/games.py`, `game_import_service.py`, `models/game.py`, `models/analysis.py`, and `job_service.py`.
- Reason: Determine whether full analysis is persisted or cached.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6chess-backend/app/api/imports.py`
  - `/Users/yahorbarkouski/g6chess-backend/app/api/games.py`
  - `/Users/yahorbarkouski/g6chess-backend/app/services/platform_sync/game_import_service.py`
  - `/Users/yahorbarkouski/g6chess-backend/app/models/game.py`
  - `/Users/yahorbarkouski/g6chess-backend/app/models/analysis.py`
  - `/Users/yahorbarkouski/g6chess-backend/app/services/game_analysis/job_service.py`
- Observations:
  - Authenticated import deduplicates owned games by `(user_id, platform, external_game_id)`.
  - Game rows persist `parsed_game_json` and `analysis_payload_json`.
  - Completed analysis responses are Redis-cached for `cache_ttl_analysis`.
  - `AnalysisCache` stores Stockfish payloads by move sequence plus analysis config fingerprint.
- Outcome:
  - Confirmed backend has persisted/cached full analysis, but user-scoped and not the current frontend contract.

### Step 012 - Write Audit Artifacts

- Action: Added the report and this event log.
- Reason: Preserve findings and remediation plan.
- Evidence inspected:
  - All above source files and command output.
- Observations:
  - Main answer: yes, production-domain Chess.com deep links are feasible, but URL state and API alignment are missing.
- Outcome:
  - Created audit artifacts.

### Step 013 - Validate Frontend Repository

- Action: Ran `bun run lint` after adding audit docs.
- Reason: Audit workflow requires the relevant repo gate for docs-only changes when available.
- Evidence inspected:
  - Biome output from `bun run lint`.
  - `git status --short`.
- Observations:
  - `bun run lint` passed: `Checked 55 files in 15ms. No fixes applied.`
  - Worktree includes additional unrelated modified/untracked files beyond the audit docs; they were not modified by this audit.
- Outcome:
  - Validation passed for this audit.

## Command Log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 002 | `git status --short` | Check dirty state | Passed | Existing modified frontend files present. |
| 002 | `rg --files -g 'AGENTS.md' -g 'README*' -g 'package.json' ...` | Map frontend files | Passed | Found Vite/React structure. |
| 002 | `sed -n '1,220p' README.md` | Read frontend docs | Passed | Import flow documented as `/api/game-analysis/import`. |
| 002 | `sed -n '1,220p' package.json` | Read scripts/deps | Passed | `bun run lint`, `test`, `typecheck`, `build`. |
| 003 | `sed -n '1,260p' src/App.tsx` | Read frontend entry | Passed | No router. |
| 003 | `sed -n '1,320p' src/lib/api.ts` | Read API client | Passed | Posts `/api/game-analysis/import`. |
| 003 | `rg -n "localStorage|history|location|URLSearchParams|game-analysis" src` | Find URL/storage behavior | Passed | localStorage found; URL mutation absent. |
| 004 | `sed -n '1,260p' src/components/analysis/AnalysisWorkspace.tsx` | Trace import lifecycle | Passed | Polling and localStorage pointer. |
| 004 | `sed -n '1060,1155p' src/components/analysis/AnalysisWorkspace.tsx` | Read storage helpers | Passed | Stores job pointer only. |
| 005 | `sed -n '1,470p' src/components/analysis/AnalysisImportPanel.tsx` | Inspect import copy and URL validation | Passed | Copy promises `g6`; validation accepts Chess.com URLs. |
| 006 | `sed -n '1,230p' src/components/analysis/AnalysisWorkspace.test.tsx` | Inspect frontend import tests | Passed | No URL/share assertions. |
| 007 | `sed -n '1,520p' src/hooks/useStockfish.ts` | Inspect browser Stockfish cache | Passed | In-memory cache only. |
| 008 | `sed -n '1,220p' /Users/yahorbarkouski/g6chess-backend/AGENTS.md` | Read backend guidance | Passed | Read-only backend inspection. |
| 009 | `rg -n 'api/game-analysis|/game-analysis|GameAnalysisSnapshot|GameAnalysisImportResponse' /Users/yahorbarkouski/g6chess-backend` | Check frontend contract in backend | No matches | Confirms mismatch for inspected backend. |
| 010 | `sed -n '1,260p' /Users/yahorbarkouski/g6chess-backend/app/api/public_live_games.py` | Inspect public route | Passed | Anonymous live-game route. |
| 010 | `sed -n '1,360p' .../chess_com_public_live_game_service.py` | Inspect public resolver/cache | Passed | Redis cache and guest bootstrap. |
| 010 | `sed -n '1,260p' .../test_public_live_games_api.py` | Inspect backend contract tests | Passed | Tests confirm no server analysis for guest bootstrap. |
| 011 | `sed -n '1,330p' .../app/api/imports.py` | Inspect authenticated import | Passed | Dedupe and queue behavior. |
| 011 | `sed -n '1,360p' .../app/api/games.py` | Inspect analysis read route | Passed | Persisted analysis and Redis cache. |
| 011 | `sed -n '1,480p' .../job_service.py` | Inspect server analysis cache | Passed | AnalysisCache by move sequence and fingerprint. |
| 012 | `git diff --stat` | Understand existing dirty scope | Passed | Existing code diffs large; no product code touched. |
| 013 | `bun run lint` | Run frontend lint/docs gate | Passed | `biome check .` passed. |
| 013 | `git status --short` | Confirm final worktree state | Passed | Audit docs added; unrelated changes left untouched. |

## Hypothesis Log

| ID | Hypothesis | Evidence For | Evidence Against | Status | Related Finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | The frontend modifies the page URL after import. | User observed it does not. | Source search found no history/location mutation. | Confirmed false | F-001 |
| H-002 | The frontend caches completed game analysis. | Same-browser reload resumes. | localStorage stores only job pointer; completed snapshot is not stored. | Confirmed false | F-004 |
| H-003 | Browser Stockfish cache makes shares fast. | `useStockfish` has a cache. | Cache is a ref-local `Map` lost on reload and unavailable to recipients. | Confirmed false | F-004 |
| H-004 | The inspected backend supports the frontend `/api/game-analysis/import` route. | README/frontend types expect it. | Backend search found no matching route/schema. | Confirmed false for sibling backend | F-002 |
| H-005 | Backend can resolve public Chess.com live ids. | Public route and resolver exist. | Only numeric live-game ids; not all frontend URL shapes. | Confirmed with scope limits | F-003 |
| H-006 | Backend caches full game analysis. | `Game.analysis_payload_json`, Redis analysis cache, `AnalysisCache`. | Public guest route intentionally does not enqueue/persist server analysis. | Confirmed with distinction | F-005 |

## Files and Docs Inspected

### Frontend

- `/Users/yahorbarkouski/g6explanation-frontend/README.md` - documented current import flow.
- `/Users/yahorbarkouski/g6explanation-frontend/package.json` - scripts and dependencies.
- `/Users/yahorbarkouski/g6explanation-frontend/src/App.tsx` - app entry; no router.
- `/Users/yahorbarkouski/g6explanation-frontend/src/main.tsx` - React root.
- `/Users/yahorbarkouski/g6explanation-frontend/src/lib/api.ts` - API paths and base URL behavior.
- `/Users/yahorbarkouski/g6explanation-frontend/src/types/api.ts` - frontend import/snapshot contract.
- `/Users/yahorbarkouski/g6explanation-frontend/src/types/analysis.ts` - board analysis shape.
- `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx` - import lifecycle, polling, localStorage, current ply.
- `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisImportPanel.tsx` - import copy, URL validation, request construction.
- `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.test.tsx` - frontend import tests.
- `/Users/yahorbarkouski/g6explanation-frontend/src/lib/api.test.ts` - API client test.
- `/Users/yahorbarkouski/g6explanation-frontend/src/lib/game-analysis-mapping.ts` - snapshot-to-board mapper.
- `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts` - in-memory browser Stockfish cache.
- `/Users/yahorbarkouski/g6explanation-frontend/vite.config.ts` - dev server/test config.

### Backend

- `/Users/yahorbarkouski/g6chess-backend/AGENTS.md` - backend repo instructions.
- `/Users/yahorbarkouski/g6chess-backend/app/AGENTS.md` - runtime code guidance.
- `/Users/yahorbarkouski/g6chess-backend/app/api/AGENTS.md` - route-layer guidance.
- `/Users/yahorbarkouski/g6chess-backend/app/schemas/AGENTS.md` - schema guidance.
- `/Users/yahorbarkouski/g6chess-backend/app/services/platform_sync/AGENTS.md` - platform sync guidance.
- `/Users/yahorbarkouski/g6chess-backend/app/main.py` - API prefix.
- `/Users/yahorbarkouski/g6chess-backend/app/api/__init__.py` - router composition.
- `/Users/yahorbarkouski/g6chess-backend/app/api/public_live_games.py` - anonymous public Chess.com route.
- `/Users/yahorbarkouski/g6chess-backend/app/api/imports.py` - authenticated Chess.com import routes.
- `/Users/yahorbarkouski/g6chess-backend/app/api/games.py` - authenticated analysis read route.
- `/Users/yahorbarkouski/g6chess-backend/app/schemas/games.py` - `AnalysisResponse` contract.
- `/Users/yahorbarkouski/g6chess-backend/app/schemas/imports.py` - import response contracts.
- `/Users/yahorbarkouski/g6chess-backend/app/core/cache.py` - Redis cache wrapper.
- `/Users/yahorbarkouski/g6chess-backend/app/core/config.py` - cache TTL settings.
- `/Users/yahorbarkouski/g6chess-backend/app/models/game.py` - persisted game and analysis payload fields.
- `/Users/yahorbarkouski/g6chess-backend/app/models/analysis.py` - jobs, ply rows, analysis cache, narratives.
- `/Users/yahorbarkouski/g6chess-backend/app/services/platform_sync/chess_com_public_live_game_service.py` - public Chess.com resolver/cache.
- `/Users/yahorbarkouski/g6chess-backend/app/services/platform_sync/game_import_service.py` - game persistence and enqueue behavior.
- `/Users/yahorbarkouski/g6chess-backend/app/services/game_analysis/job_service.py` - job lifecycle and cache behavior.
- `/Users/yahorbarkouski/g6chess-backend/tests/api_contracts/integration/test_public_live_games_api.py` - public route contract tests.

## Blockers and Deferred Checks

- Did not run live external Chess.com API calls; source and tests were enough to answer this audit.
- Did not run backend tests; this was a frontend audit with read-only backend inspection.
- Did not verify production hosting rewrite rules.
- Did not inspect any separate API service that might implement `/api/game-analysis/import`; if such a service exists, it should be audited next.
