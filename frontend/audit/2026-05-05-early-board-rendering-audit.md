# Early Board Rendering Audit Report

Date: 2026-05-05
Repository: /Users/yahorbarkouski/g6explanation-frontend
Related event log: ./2026-05-05-early-board-rendering-audit-event-log.md

## Executive Summary

The chess board does not render when Chess.com import succeeds. It renders only after the first polled game-analysis snapshot contains at least one move with `context !== null`.

That means the current UI is blocked on backend context generation, not merely on Chess.com resolution. In Modal-shaped deployments, it can also be blocked by worker cold start and provider setup because the initial job snapshot contains `total_plies` but no board moves.

The underlying product fix is to split "game skeleton" from "verified analysis." The backend already has the canonical PGN after Chess.com resolution and can derive SAN, UCI, FEN-before, FEN-after, move number, side, and clocks without Stockfish, Maia, or OpenRouter. That lightweight skeleton should be returned immediately and persisted in the initial snapshot. The frontend should render the board from that skeleton, then progressively enrich moves as analysis results arrive.

## Scope

- Included:
  - Frontend import, route import, polling, snapshot mapping, board mounting, move list, and loading indicator.
  - Backend import service, Chess.com resolver, game-analysis job service, runner snapshot writes, Modal executor, and public context admission guard in the sibling `/Users/yahorbarkouski/g6explanation` repo.
  - Tests and documentation that define current behavior.
- Excluded:
  - Implementing the fix.
  - Live Chess.com network calls.
  - Browser visual QA.
- Constraints:
  - Frontend worktree was clean at audit start.
  - Backend worktree had existing uncommitted changes, including API protection changes. Those were treated as current local evidence, not edited.

## Current Render Timeline

1. The user submits a Chess.com URL from `AnalysisImportPanel`. The request includes `include_context: true` today.
2. `AnalysisWorkspace.handleImportedGameAnalysis` clears `analysis`, posts `/api/game-analysis/import`, stores `{ analysis_id, status_url, source }`, sets status to `polling`, and updates the route.
3. While `analysis === null`, `AnalysisWorkspace` keeps rendering `AnalysisImportHome`, not the board workspace.
4. The polling effect calls `pollGameAnalysis(status_url)` every 1.2 seconds while the job is non-terminal.
5. The only frontend transition into the board workspace is this guard:
   `if (snapshot.moves.some((move) => move.context !== null)) setAnalysis(mapGameAnalysisSnapshot(...))`.
6. `mapGameAnalysisSnapshot` then filters out every move without context and builds board moves from `context.evidence.position.fen_before` and `fen_after`.
7. `AnalysisGameWorkspace` mounts only after that mapped `analysis` exists.

So the exact moment board rendering starts is: after the first successful poll whose snapshot has at least one move with a full `ContextResult`.

## Backend Timing

The backend import path resolves Chess.com first, so by the time `/api/game-analysis/import` returns, it already has a canonical PGN and source metadata.

Current backend flow:

1. `GameImportService.start()` checks an import-analysis cache, resolves Chess.com or PGN into `ImportedGame`, converts it into `GameAnalysisStartRequest`, starts analysis, and returns only `analysis_id`, `status`, `status_url`, and `source`.
2. `GameAnalysisService.start()` parses the PGN only enough to count plies, writes a pending snapshot with `total_plies` and `context_completed: 0`, then submits the runner.
3. With the Modal executor, the API returns while the remote worker is only spawned. The stored snapshot can remain `pending` with no moves until the worker starts.
4. `GameAnalysisRunner.run()` builds per-ply PGN requests with SAN/UCI/FEN/clocks, but it does not persist those lightweight moves.
5. The runner saves a move only after `_build_context()` finishes and `_move_from_context_result()` converts the full context into `GameMoveAnalysis`.

This is why the UI feels like it is waiting for "something on the backend to load": it is waiting for the first context build, and in production it may also be waiting for the Modal worker image/runtime.

## Findings Overview

| ID | Severity | Category | Confidence | Title | Fix Priority |
| --- | --- | --- | --- | --- | --- |
| F-001 | High | product-latency | High | Board mounting is blocked on first full context result | Immediate |
| F-002 | High | architecture | High | Backend discards the PGN-derived board skeleton until context completes | Immediate |
| F-003 | High | contract | High | Public API protection conflicts with the frontend's `include_context` dependency | Immediate |
| F-004 | Medium | maintainability | High | Frontend conflates board moves, timeline, markers, and full context | Near-term |

## Confirmed Findings

### F-001: Board Mounting Is Blocked On First Full Context Result

- Severity: High
- Category: product-latency
- Confidence: High
- Status: Confirmed
- Evidence:
  - `src/components/analysis/AnalysisWorkspace.tsx:146` stores `analysis` as `AnalysisResponse | null`.
  - `src/components/analysis/AnalysisWorkspace.tsx:240` to `src/components/analysis/AnalysisWorkspace.tsx:242` sets `analysis` only when a polled snapshot has a move with `context !== null`.
  - `src/components/analysis/AnalysisWorkspace.tsx:428` to `src/components/analysis/AnalysisWorkspace.tsx:448` renders `AnalysisImportHome` while `analysis` is null and only renders `AnalysisGameWorkspace` afterward.
  - `src/lib/game-analysis-mapping.ts:34` to `src/lib/game-analysis-mapping.ts:39` filters snapshot moves to context-bearing moves before creating board moves, timeline points, and markers.
- Impact:
  - A successful Chess.com import response still shows the import surface/spinner.
  - Pending/running snapshots with `total_plies` but no context cannot render a board.
  - Users perceive backend startup, worker cold start, and first Stockfish/Maia context latency as "the board is not loading."
- Reproduction or experiment:
  - Source trace. Existing frontend tests assert no board before import and board only after `pollGameAnalysis` resolves a context-bearing fixture.
- Recommended fix:
  - Render the workspace from a lightweight game skeleton as soon as it is available.
  - Keep the current progress indicator for analysis completion, but stop using first context availability as the board mount gate.
- Verification:
  - Add a frontend test where import returns a skeleton and the board renders before any analysis poll has context.
  - Add a frontend test where a pending snapshot with `total_plies > 0` and zero analyzed moves still keeps the board mounted.

### F-002: Backend Discards The PGN-Derived Board Skeleton Until Context Completes

- Severity: High
- Category: architecture
- Confidence: High
- Status: Confirmed
- Evidence:
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_imports/import_service.py:152` to `:160` resolves `ImportedGame` and returns source metadata, but no PGN-derived move list.
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/job_service.py:63` to `:92` counts plies, writes a pending snapshot, and returns a job pointer; the snapshot has no moves.
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/analysis_runner.py:360` to `:418` can derive SAN, UCI, side, FEN-before, FEN-after, clocks, and move number from the PGN before context work.
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/analysis_runner.py:260` to `:271` saves a move only after context build completes.
- Impact:
  - The cheapest board data exists before expensive analysis but is not exposed.
  - Modal worker startup delays first UI render even though the API process already resolved the game.
  - The frontend has no contract for showing the imported game while engine/model evidence is still pending.
- Reproduction or experiment:
  - Source trace through import service, job service, and runner.
- Recommended fix:
  - Extract a pure PGN-to-skeleton function, for example `game_move_skeleton_from_pgn(pgn, time_control)`.
  - Add a contract such as `GameMainlineMove` with `ply`, `move_number`, `player_color`, `san`, `uci`, `fen_before`, `fen_after`, `clock_before_seconds`, `remaining_clock_seconds`, and `think_time_seconds`.
  - Include that skeleton in the import response if the goal is board render immediately after Chess.com import returns.
  - Also persist the skeleton in the initial `GameAnalysisSnapshot` so reloads and direct analysis links can render before context completion.
  - Keep analyzed `GameMoveAnalysis` separate from skeleton moves. Do not create fake quality/significance/context placeholders.
- Verification:
  - Backend tests for Chess.com import response skeleton, PGN import response skeleton, pending snapshot skeleton, Modal-spawn pending snapshot skeleton, and clock-field parity.

### F-003: Public API Protection Conflicts With The Frontend's `include_context` Dependency

- Severity: High
- Category: contract
- Confidence: High
- Status: Confirmed in the current local backend worktree
- Evidence:
  - `src/components/analysis/AnalysisImportPanel.tsx:392` to `:402` sends `include_context: true`.
  - `src/components/analysis/AnalysisWorkspace.tsx:1614` to `:1621` also sends `include_context: true` for route imports.
  - `/Users/yahorbarkouski/g6explanation/deploy/modal_app.py:56` to `:63` sets `G6EXPLANATION_ALLOW_PUBLIC_INCLUDE_CONTEXT=false`.
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/security/admission.py:258` to `:264` rejects public requests that ask for full context when that flag is false.
  - Backend test `/Users/yahorbarkouski/g6explanation/tests/g6explanation/game_imports/test_game_analysis_import_api.py:253` to `:279` asserts `include_context: true` is denied before Chess.com resolution when public context is disabled.
- Impact:
  - If that backend config is deployed as-is, the current frontend import request is rejected with `include_context_forbidden` before Chess.com is even fetched.
  - If the frontend changes to `include_context: false` without a replacement contract, the current mapper cannot hydrate board FENs or engine lines because it depends on `context.evidence`.
- Reproduction or experiment:
  - Source trace and backend contract test.
- Recommended fix:
  - Stop making public board hydration depend on full `ContextResult`.
  - Add redacted, frontend-owned display fields outside `context`: at minimum the skeleton fields above; for analyzed moves, expose compact engine/display data needed for markers and lines.
  - Change public frontend imports to omit `include_context` or set it to `false` after the display contract exists.
- Verification:
  - Backend public-protection test showing `include_context: false` import returns a skeleton and later compact analysis data.
  - Frontend API/workspace tests using `context: null` snapshots with skeleton/display fields.

### F-004: Frontend Conflates Board Moves, Timeline, Markers, And Full Context

- Severity: Medium
- Category: maintainability
- Confidence: High
- Status: Confirmed
- Evidence:
  - `src/lib/game-analysis-mapping.ts:67` to `:82` creates `GameMove` from context evidence position fields.
  - `src/lib/game-analysis-mapping.ts:84` onward creates timeline and marker data from the same context-bearing move.
  - `src/components/analysis/MoveList.tsx:33` to `:82` can already render moves without markers, but the workspace never supplies skeleton-only moves.
  - `src/components/analysis/PositionInfo.tsx:44` to `:88` can already show a current move with no marker, but the workspace never mounts early enough to use that state.
- Impact:
  - A missing context packet means no board, no move list, and no selected move, even though PGN-derived move navigation would be valid.
  - Public context redaction and early board rendering are harder than they need to be.
- Reproduction or experiment:
  - Source trace.
- Recommended fix:
  - Split frontend mapping into:
    - `mapGameSkeleton(...)` for board/move-list data.
    - `mapAnalyzedMove(...)` or `mergeGameAnalysisSnapshot(...)` for labels, engine lines, explanation cards, and timeline enrichment.
  - Let `AnalysisGameWorkspace` mount with empty `move_markers` and sparse `timeline`.
  - Use copy such as "Analysis is loading for this move" when `currentMarker` is missing.
  - Decide whether browser Stockfish should auto-start for skeleton-only positions. The current `missing-server-lines` logic would start browser analysis when no server lines exist; that may be useful, but it should be explicit because it spends client CPU while backend analysis is also running.
- Verification:
  - Frontend tests for skeleton-only rendering, sparse marker enrichment, and no-crash behavior with empty timeline/markers.
  - A performance test or browser smoke test if browser Stockfish is enabled during backend pending state.

## Suggested Fix Shape

### Backend Contract

Add a lightweight move contract that is explicitly not chess-truth analysis:

```ts
interface GameMainlineMove {
  ply: number;
  move_number: number;
  player_color: "white" | "black";
  san: string;
  uci: string;
  fen_before: string;
  fen_after: string;
  clock_before_seconds?: number | null;
  remaining_clock_seconds?: number | null;
  think_time_seconds?: number | null;
}
```

Then expose it in one of these ways:

- Preferred: add `game: { total_plies, moves }` to both `GameAnalysisImportResponse` and `GameAnalysisSnapshot`.
- Acceptable: add `mainline_moves` to `GameAnalysisSnapshot` and `initial_snapshot` to the import response.

The preferred shape lets the frontend render immediately after POST success and also keeps reload/direct-link polling useful.

### Backend Implementation

1. Extract PGN traversal logic from `game_ply_requests()` so one function produces skeleton moves and another wraps those moves into context-engine requests.
2. In `GameAnalysisService.start()`, persist the initial snapshot with the skeleton before spawning local or Modal work.
3. In `GameImportService.start()`, include the same skeleton in `GameAnalysisImportResponse`.
4. Keep `GameMoveAnalysis.context` optional and disabled for public requests.
5. Add compact analyzed-display fields if the frontend needs engine lines, evals, or main-point text without full context.

### Frontend Implementation

1. Extend `src/types/api.ts` with the skeleton contract and import/snapshot fields.
2. Extend `src/types/analysis.ts` only if the current `GameMove` fields are insufficient; they already cover the board-critical fields.
3. Replace the current `analysis` gate with a board model that can be built from the skeleton.
4. Change polling merge behavior:
   - skeleton moves drive board, navigation, move list, player clocks, and route ply.
   - analyzed moves enrich markers, timeline, book lines, explanation cards, and server engine lines.
5. Change public import requests to `include_context: false` after the compact display contract is available.
6. Keep the top progress indicator based on `context_completed / total_plies`.

### Tests

- Frontend:
  - import response with skeleton renders `analysis-board` before `pollGameAnalysis` returns context.
  - pending snapshot with skeleton and `moves: []` keeps the board mounted and shows progress.
  - later snapshot enriches the same move with marker/explanation.
  - public request omits `include_context`.
- Backend:
  - Chess.com import includes skeleton derived from archive PGN.
  - PGN import includes skeleton.
  - Modal-spawn start persists skeleton while snapshot remains pending.
  - public `include_context: false` import succeeds and `include_context: true` still fails when configured.

## Residual Risk

- I did not run live Chess.com import or frontend browser QA.
- Backend files are in a dirty worktree, so the public-context admission behavior should be confirmed before treating it as deployed truth.
- The exact compact analyzed-display contract needs a product choice: either expose enough redacted engine/explanation fields for the current frontend UI, or keep the early board as navigation-only until full internal tools can request context.
