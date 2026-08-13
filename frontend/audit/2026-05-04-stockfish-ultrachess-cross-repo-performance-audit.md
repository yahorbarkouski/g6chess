# Stockfish + UltraChess Cross-Repo Performance Audit

Date: 2026-05-04
Repositories:

- G6 frontend: `/Users/yahorbarkouski/g6explanation-frontend`
- UltraChess React: `/Users/yahorbarkouski/ultrachess-react`

Auditor: Codex
Related event log: `./2026-05-04-stockfish-ultrachess-cross-repo-performance-audit-event-log.md`
Previous related audit: `./2026-05-04-stockfish-performance-audit.md`

## Executive Summary

Owning UltraChess React changes the recommended fix strategy. The best target is no longer just "make G6 avoid re-rendering the board"; it is "make the G6-to-UltraChess boundary express analysis updates atomically and semantically." UltraChess already has a strong internal performance model: external `BoardModel`, byte-scoped square subscriptions, refs-only drag, canvas arrows, and render-budget tests. The weak spot is the integration path G6 uses under high-frequency Stockfish updates.

The highest impact issues are:

- G6 mounts both desktop and mobile board trees at the same time. This creates two `UltraAnalysisBoard` components and therefore two `useChessGame()` board models/adapters, even though one layout is CSS-hidden.
- Stockfish updates are committed at the `AnalysisWorkspace` root, so centipawn/depth/PV noise fans out through both layouts and both board wrappers.
- G6 controls UltraChess position and managed arrows through separate phases: `positionFen` synchronizes in UltraChess layout effect, then G6's `useManagedArrows` effect calls `game.setManagedArrows`. A single analysis navigation/update can therefore become multiple board model commits.
- UltraChess protects model-driven updates well, but it is not hardened against hostile parent churn: `Chessboard`, `BoardGrid`, `PieceLayer`, and `ArrowsLayer` still execute when a host app re-renders them for unrelated engine UI changes.

The practical roadmap is:

1. In G6, mount only one board/layout for the active viewport.
2. In G6, split Stockfish raw state from display state and commit only semantic UI snapshots, not every `+630` to `+631` detail.
3. In UltraChess, add a first-class analysis-viewer API that applies `positionFen` and managed arrows in one model commit before paint.
4. In UltraChess, add "parent churn" render-budget tests and memoize the static/layer components that are demonstrably invoked by host app re-renders.

## Implementation Status

This audit has been followed by a fix pass on 2026-05-04:

- F-001: Fixed in G6. `AnalysisWorkspace` now uses a media-query render boundary so only the desktop or mobile layout mounts.
- F-002 and F-005: Improved in G6. Stockfish still exposes a React snapshot, but commits are now semantically keyed so centipawn noise such as `+630` to `+631` does not publish a new UI state.
- F-003: Fixed cross-repo. UltraChess core now has `BoardModel.syncPosition`, UltraChess React accepts `managedArrows`, and G6 passes managed arrows through the board instead of a separate post-render effect.
- F-004: Improved in UltraChess. Static board layers are memoized for stable props, and controlled-analysis parent-churn coverage was added around the new API.
- F-006: Fixed in G6. Managed arrow conversion is render-only and animation options are stable by `animationMs`.
- F-007: Improved in UltraChess. The `useChessGame({ fen })` docs now call out lifecycle semantics and direct controlled viewers to `positionFen`.
- F-008: Fixed in G6. Stockfish pre-analysis is now capped, proximity-based, de-duplicated, and replaceable.
- F-009: Fixed in G6. Vitest now has a storage setup file and the full G6 test suite passes.
- F-010: Improved. G6 has semantic Stockfish key tests and one-board mount coverage; UltraChess has core atomic-position tests and React controlled-analysis tests. Browser trace benchmarking remains a follow-up.

## Scope

- Included:
  - Stockfish update flow in G6.
  - `AnalysisWorkspace`, `UltraAnalysisBoard`, board arrows, layout mounting, and engine-line rendering.
  - UltraChess React's `Chessboard`, `useChessGame`, board model, subscription store, arrow model, layer components, performance docs, and render-budget tests.
  - Local validation commands for both repositories.
- Excluded:
  - Browser profiler recording and flamegraph capture. This audit is source-backed and command-backed, but no Chrome trace was recorded.
  - Product code changes. The user asked for a new audit/recommendations, not implementation in this turn.
  - Network or package publication workflow for UltraChess.
- Repository instructions followed:
  - No `AGENTS.md` was found in either repository.
  - Audit skill workflow was followed: source map, findings, experiments, event log, final docs/lint check.
- Constraints or blockers:
  - G6 frontend is not a Git repository, so there is no local Git diff/status protection there.
  - G6 test suite is currently blocked by `window.localStorage.clear is not a function` in `src/components/analysis/AnalysisWorkspace.test.tsx:60`.

## Methodology

I traced the hot path from Stockfish worker messages to G6 React state, then from G6 props into UltraChess React and down into UltraChess core. I checked whether each layer had a stable ownership boundary, whether updates were semantic or raw, whether effects created extra commits, and whether existing tests actually cover the parent re-render pattern G6 produces.

I also ran the available quality gates:

- G6: `bun run lint`, `bun run typecheck`, `bun run build`, `bun run test`.
- UltraChess: `bun run lint`, `bun run typecheck`, `bun -F @ultrachess/react test`.

## System Map

### G6 Frontend

G6 is a Vite/React app using `@ultrachess/react` and a browser Stockfish worker:

- `/Users/yahorbarkouski/g6explanation-frontend/package.json:17-33` depends on `@ultrachess/core`, `@ultrachess/react`, `@ultrachess/pieces`, `@ultrachess/themes`, `stockfish`, and `ultrachess`.
- `/Users/yahorbarkouski/g6explanation-frontend/package.json:11` copies Stockfish JS/WASM into `public/stockfish`.
- `/Users/yahorbarkouski/g6explanation-frontend/public/stockfish/stockfish-18-single.wasm` is 108 MB locally.

Main G6 runtime flow:

```text
Stockfish worker info lines
  -> useStockfish()
  -> setEngineState({ fen, lines, depth, evalCp })
  -> AnalysisWorkspace render
  -> DesktopLayout and MobileLayout render
  -> UltraAnalysisBoard(s)
  -> Chessboard(positionFen)
  -> BoardModel.load()
  -> G6 useManagedArrows effect
  -> BoardModel.setManagedArrows()
```

### UltraChess React

UltraChess is a separate workspace with a performance-oriented public contract:

- `/Users/yahorbarkouski/ultrachess-react/package.json:5` describes owned state, byte-scoped subscriptions, refs-only drag, and explicit budgets.
- `/Users/yahorbarkouski/ultrachess-react/docs/PERFORMANCE.md:7-14` documents the core performance contract.
- `/Users/yahorbarkouski/ultrachess-react/docs/PERFORMANCE.md:42-50` lists byte-level snapshots, canvas arrows, refs-only drag, WAAPI animations, and SSR static board as core optimizations.
- `/Users/yahorbarkouski/ultrachess-react/packages/core/src/board-model.ts:1-13` states that public actions should produce at most one coherent snapshot commit.
- `/Users/yahorbarkouski/ultrachess-react/packages/core/src/subscribe-store.ts:1-7` documents byte-level per-square diffing.

UltraChess has good internal protections:

- Per-square listeners fire only when their board byte changes: `/Users/yahorbarkouski/ultrachess-react/packages/core/src/subscribe-store.ts:84-100`.
- Arrows preserve identity by key and no-op when the key set is unchanged: `/Users/yahorbarkouski/ultrachess-react/packages/core/src/arrow-model.ts:171-200`.
- Render-budget tests cover model-driven moves and selections: `/Users/yahorbarkouski/ultrachess-react/packages/react/test/render-budget.test.tsx:52-75`.

The missing contract is a host-app scenario: a live analysis app re-rendering the parent every 80 ms or less due to Stockfish updates.

## Findings Overview

| ID | Severity | Category | Confidence | Title | Fix Priority |
| --- | --- | --- | --- | --- | --- |
| F-001 | High | performance | High | G6 mounts two live UltraChess boards/adapters because desktop and mobile layouts are both rendered | Immediate |
| F-002 | High | architecture | High | Stockfish state lives at the G6 workspace root and fans out through the whole analysis UI | Immediate |
| F-003 | High | architecture | High | Position FEN and managed arrows are synchronized as separate board model updates | Immediate |
| F-004 | High | performance | High | UltraChess render budgets do not cover host parent churn, the pattern G6 creates | Immediate |
| F-005 | High | performance | High | Stockfish commits are time-throttled but not semantically gated | Immediate |
| F-006 | Medium | performance | High | G6 creates fresh animation objects and arrow arrays during engine churn | Near-term |
| F-007 | Medium | API design | Medium | `useChessGame({ fen })` semantics are awkward for controlled analysis boards | Near-term |
| F-008 | Medium | performance | High | Eager Stockfish pre-analysis enqueues every timeline FEN regardless of user intent | Near-term |
| F-009 | Medium | tests | High | The G6 test harness is failing before it can protect performance regressions | Immediate |
| F-010 | Medium | tests | High | There is no cross-repo performance contract test for G6 plus UltraChess | Strategic |

## Confirmed Findings

### F-001: G6 Mounts Two Live UltraChess Boards/Adapters

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - `AnalysisWorkspace` renders `DesktopLayout` at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:360-395`.
  - It also renders `MobileLayout` at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:397-434`.
  - The desktop layout is hidden with CSS at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:477`, but still mounted.
  - The mobile layout is hidden with CSS at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:609`, but still mounted.
  - Desktop board instance: `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:501-511`.
  - Mobile board instance: `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:637-647`.
  - Each `UltraAnalysisBoard` calls `useChessGame()` at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/UltraAnalysisBoard.tsx:67`.
  - `useChessGame()` asynchronously creates an ultrachess adapter and `BoardModel` at `/Users/yahorbarkouski/ultrachess-react/packages/react/src/hooks/use-chess-game.ts:41-69`.
- Impact:
  - The hidden layout is not a cheap CSS detail. It owns a second board model lifecycle, adapter initialization, subscriptions, effects, arrow layers, and position synchronization path.
  - Every high-frequency Stockfish root render can invoke both board wrappers.
  - On mobile, desktop board work is wasted; on desktop, mobile board work is wasted.
- Reproduction or experiment:
  - Source trace is sufficient. Both layout components are in the same render output, and CSS classes control visibility after React has already reconciled them.
- Recommended fix:
  - G6 should mount only one active layout at a time. Use a `useMediaQuery("(min-width: 1280px)")` gate, a responsive layout component that has one board slot, or a single board shell reused by desktop/mobile panels.
  - Prefer moving the board out of duplicated layout subtrees and switching only surrounding panels/tabs responsively.
  - Keep UltraChess unchanged for this specific issue; library ownership does not make hidden duplicate consumers cheap.
- Verification:
  - Add a G6 test with an instrumented `UltraAnalysisBoard` or mocked `useChessGame` and assert only one board instance is mounted per viewport.
  - In browser profiler, viewport resize should mount/unmount one board rather than keeping two board lifecycles live.

### F-002: Stockfish State Fans Out Through the Whole G6 Workspace

- Severity: High
- Category: architecture
- Confidence: High
- Status: Confirmed
- Evidence:
  - `AnalysisWorkspace` calls `useStockfish` at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:103`.
  - The resulting `stockfish.lines`, `stockfish.depth`, `stockfish.evalCp`, and `stockfish.isAnalyzing` participate in root-level derived values at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:104-180`.
  - Both layout trees receive the derived engine data at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:372-376` and `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:409-413`.
  - `useStockfish` commits React state with exact engine lines/depth/eval at `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts:89-95`.
- Impact:
  - A tiny engine-detail update can re-run the whole workspace render path: layout, board wrapper props, arrows, sidebars, engine lines, move list parents, and mobile tabs.
  - UltraChess's byte-scoped internal store cannot prevent work that happens before the board model boundary.
  - This is the source of the user's concern about `+630` versus `+631`: the app treats raw engine noise as UI state.
- Reproduction or experiment:
  - Source trace from `useStockfish` state setter to root-level props confirms the fan-out.
- Recommended fix:
  - G6 should keep volatile raw Stockfish output outside React render state, for example in refs or an external store with `useSyncExternalStore`.
  - Expose a small semantic display snapshot:
    - `fen`
    - `displayDepthBucket`
    - `displayEvalBucket`
    - `topMoveKey`
    - `visibleLineKeys`
    - `isAnalyzing`
  - Commit the snapshot only when a visible semantic key changes. Exact centipawn values can stay in the cache for tooltips/debug, but they should not drive the main render loop.
  - Move engine-line UI subscriptions close to the engine panels instead of subscribing at the workspace root.
- Verification:
  - Create a mocked Stockfish stream test that emits many eval-only changes in the same bucket and assert `AnalysisWorkspace` board subtree render count stays flat.
  - In profiler, a stream of `+630`, `+631`, `+632` for the same PV should update the eval text only when the chosen display bucket changes.

### F-003: Position FEN and Managed Arrows Are Separate Board Model Updates

- Severity: High
- Category: architecture
- Confidence: High
- Status: Confirmed
- Evidence:
  - G6 passes `positionFen={fen}` into `Chessboard` at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/UltraAnalysisBoard.tsx:90-97`.
  - G6 separately synchronizes arrows through `useManagedArrows` at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/UltraAnalysisBoard.tsx:109-142`.
  - UltraChess `Chessboard` syncs `positionFen` in a layout effect at `/Users/yahorbarkouski/ultrachess-react/packages/react/src/chessboard.tsx:349-360`.
  - That path calls `game.load(targetFen)` at `/Users/yahorbarkouski/ultrachess-react/packages/react/src/chessboard.tsx:223-227`.
  - `BoardModel.load` clears arrows and commits at `/Users/yahorbarkouski/ultrachess-react/packages/core/src/board-model.ts:372-381`.
  - `game.setManagedArrows` can then commit separately at `/Users/yahorbarkouski/ultrachess-react/packages/core/src/board-model.ts:470-473`.
- Impact:
  - A single user intent, "show this analyzed position with these engine arrows," can become two UltraChess snapshot commits.
  - Because G6 arrow sync is in `useEffect`, it happens after paint, so a position change can briefly clear managed arrows before re-adding them.
  - The library's "one coherent update per user intent" model is partially bypassed by the current public boundary.
- Reproduction or experiment:
  - Source trace shows `load` clears all arrows, then G6 effect re-applies managed arrows. ArrowModel's no-op protections help only when keys are unchanged; they cannot make `load + setManagedArrows` atomic.
- Recommended fix:
  - Add an UltraChess first-class analysis API, then use it from G6. Suggested shape:
    - `game.syncAnalysisPosition({ fen, transition, managedArrows, preserveUserArrows })`
    - or `<Chessboard positionFen managedArrows positionTransition ... />` with UltraChess applying position and managed arrows in the same layout effect/model action.
  - The core operation should load the FEN, preserve or replace user arrows according to options, install managed arrows, and emit one snapshot commit.
  - G6 should delete its local `useManagedArrows` effect once UltraChess owns this prop.
- Verification:
  - UltraChess unit test: controlled position plus managed arrows causes exactly one model commit and no intermediate empty-managed-arrow snapshot.
  - G6 integration test: selecting a move changes board position and engine arrows without two board commits.

### F-004: UltraChess Render Budgets Do Not Cover Host Parent Churn

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - UltraChess render-budget tests wrap `<Chessboard game={model} />` and assert model-driven updates at `/Users/yahorbarkouski/ultrachess-react/packages/react/test/render-budget.test.tsx:52-75`.
  - `Chessboard` is a normal exported function at `/Users/yahorbarkouski/ultrachess-react/packages/react/src/chessboard.tsx:248`, not a memoized boundary.
  - `BoardGrid` is a normal function even though its comment says it re-renders only on orientation/focus changes: `/Users/yahorbarkouski/ultrachess-react/packages/react/src/components/board-grid.tsx:67-79`.
  - `PieceLayer` is a normal function that reconstructs 64 slots each parent render: `/Users/yahorbarkouski/ultrachess-react/packages/react/src/components/piece-layer.tsx:126-143`.
  - `ArrowsLayer` redraw effects depend on props and subscribed arrow slices at `/Users/yahorbarkouski/ultrachess-react/packages/react/src/components/arrows-layer.tsx:245-300`.
- Impact:
  - UltraChess is optimized for board-model actions, but G6's problem is parent renders from live engine state.
  - Parent churn still invokes layer render functions and some effects even when the `BoardModel` snapshot did not change.
  - The existing tests can pass while a real app still pays unnecessary work during Stockfish streams.
- Reproduction or experiment:
  - The existing render-budget test does not call React Testing Library `rerender` with the same model and changed irrelevant parent props. It therefore does not measure this failure mode.
- Recommended fix:
  - Add UltraChess "host parent churn" tests:
    - Render a parent with `<Chessboard game={model} animation={{ durationMs: 60 }} />`.
    - Rerender the parent many times with unrelated state changes and semantically identical object props.
    - Assert no model commit, no arrow canvas redraw, and no piece slot re-render except where props actually changed.
  - Consider memoizing `Chessboard` or at least static/layer components with narrow comparators:
    - `BoardGrid`: compare orientation, focusedSquare, renderSquare, readOnly, ariaLabel, handler refs.
    - `PieceLayer`: compare model, orientation, pieces.
    - `ArrowsLayer`: compare model, orientation, palette, below.
  - Normalize object props inside `Chessboard` to primitive dependencies where possible, especially `animation`.
- Verification:
  - New UltraChess test fails before memo/normalization and passes after.
  - Run `bun -F @ultrachess/react test` and the benchmark suite relevant to render budgets.

### F-005: Stockfish Commits Are Time-Throttled But Not Semantically Gated

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - `useStockfish` schedules commits by elapsed time at `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts:101-115`.
  - Every committed state carries exact `lines`, `depth`, and `evalCp` at `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts:89-95`.
  - UCI `info` lines are parsed and converted to best lines at `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts:212-227`.
  - `useStableEvalCp` introduces effect-driven state that can add another render after an eval change at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:867-885`.
- Impact:
  - The throttle reduces update frequency, but a commit every 80 ms is still up to 12.5 root updates per second.
  - Tiny non-visible changes still push React work.
  - The stabilizer hook preserves fallback eval, but it does not solve semantic noise and can add one more state update.
- Reproduction or experiment:
  - Source trace confirms the engine commit key is time, not display semantics.
- Recommended fix:
  - Replace the current commit rule with semantic gating:
    - Keep exact engine analysis in a ref/cache.
    - Build a UI snapshot using quantized eval and stable line keys.
    - Commit only when the UI snapshot's key changes.
  - Example display gating:
    - Mate changes always commit.
    - Eval bucket commits every 10 or 25 centipawns depending on UI density.
    - Depth display commits on integer depth changes only if the line key is stable for a minimum window or reaches a meaningful threshold.
    - PV commits when the first move changes, the visible top N moves reorder, or the root line key changes.
  - Derive stable eval during render from the display snapshot and position key; remove effect-backed `useStableEvalCp`.
- Verification:
  - Unit-test a sequence of engine info messages where only centipawn noise changes; assert one UI snapshot commit.
  - Unit-test a PV first move change; assert immediate commit.
  - Profile 30 seconds of analysis and compare root commit count before/after.

### F-006: G6 Creates Fresh Animation Objects and Arrow Arrays During Engine Churn

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - `UltraAnalysisBoard` creates a fresh `animation` object inline at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/UltraAnalysisBoard.tsx:87-89`.
  - UltraChess `Chessboard` has `animation` in the `positionFen` sync effect dependencies at `/Users/yahorbarkouski/ultrachess-react/packages/react/src/chessboard.tsx:349-360`.
  - G6 builds board arrows from engine/server lines at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:114-133`.
  - G6 converts `BoardArrow[]` to UltraChess `Arrow[]` in `useManagedArrows` at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/UltraAnalysisBoard.tsx:109-142`.
  - UltraChess `arrowModel.setManaged` avoids commits when arrow keys are unchanged at `/Users/yahorbarkouski/ultrachess-react/packages/core/src/arrow-model.ts:171-200`, but the G6 effect and conversion work still run when `arrows` reference changes.
- Impact:
  - UltraChess avoids some downstream commits, but the host still pays render/effect/conversion costs.
  - Inline animation object identity can retrigger effects even when the board position is unchanged. The effect returns early if FEN matches, but it still executes.
- Reproduction or experiment:
  - Source trace confirms object/array creation occurs during render and effect dependencies observe reference identity.
- Recommended fix:
  - In G6, memoize animation options by `animationMs`, or pass primitive props and let UltraChess normalize.
  - In G6, compute arrow semantic keys before creating arrays and reuse previous arrays when keys are unchanged.
  - In UltraChess, if `managedArrows` becomes first-class, accept app arrows and do internal key diff before any model commit.
  - In UltraChess, normalize `animation` into primitive deps (`durationMs`, `easing`) for effects.
- Verification:
  - Add a test that parent re-renders with identical `animationMs` and identical arrow keys do not call `game.setManagedArrows` and do not run position sync work.

### F-007: `useChessGame({ fen })` Semantics Are Awkward For Controlled Analysis Boards

- Severity: Medium
- Category: API design
- Confidence: Medium
- Status: Likely
- Evidence:
  - `useChessGame` accepts `fen` and passes it to `createUltrachessAdapter(fen)` at `/Users/yahorbarkouski/ultrachess-react/packages/react/src/hooks/use-chess-game.ts:32-55`.
  - The effect depends on `fen`, so changing `fen` recreates and disposes the model at `/Users/yahorbarkouski/ultrachess-react/packages/react/src/hooks/use-chess-game.ts:61-69`.
  - G6 avoids this by calling `useChessGame()` without `fen` and controlling `positionFen` through `Chessboard` at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/UltraAnalysisBoard.tsx:67-97`.
- Impact:
  - The hook has an attractive but dangerous surface for analysis viewers. Passing changing FENs into `useChessGame({ fen })` would recreate the model per navigation.
  - G6's workaround is reasonable today but pushes controlled synchronization into component/effect props instead of a model-level API.
- Reproduction or experiment:
  - Source trace confirms `fen` is a lifecycle dependency rather than an initial-only value.
- Recommended fix:
  - Rename or split the API:
    - `useChessGame({ initialFen })` for one-time initialization.
    - `useControlledChessGame` or `useAnalysisBoardModel` for controlled FEN updates.
  - Document that changing `fen` recreates the model if the current API is kept.
  - Prefer the atomic analysis API from F-003 for G6.
- Verification:
  - Type/API tests cover that `initialFen` does not recreate on parent render.
  - Docs include a G6-style analysis viewer example.

### F-008: Eager Stockfish Pre-Analysis Enqueues Every Timeline FEN

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - G6 builds `preAnalyzeFens` from all unique timeline points at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:182-193`.
  - It calls `stockfish.preAnalyze(preAnalyzeFens)` in an effect at `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:195-197`.
  - The Stockfish worker is created when the hook is enabled at `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts:176-183`.
- Impact:
  - Engine work can start before the user needs those positions.
  - On long timelines, G6 can put CPU pressure on the same session where the board/UI is already handling live analysis.
  - This is separate from UltraChess. Owning the board library cannot make Stockfish CPU work disappear.
- Reproduction or experiment:
  - Source trace confirms all unique timeline FENs are sent to pre-analysis.
- Recommended fix:
  - Make pre-analysis demand-shaped:
    - Current position first.
    - Neighboring plies next.
    - Marked moves or visible move-list window next.
    - Use `requestIdleCallback`/idle timers and cancel on navigation/import.
  - Add a budget, for example max queued FENs per idle period and max total pre-analysis depth while the user is interacting.
  - Consider starting Stockfish lazily only when analysis panel/engine arrows are visible or when browser engine lines are needed.
- Verification:
  - Add a unit test for queue ordering and cancellation.
  - Profile long imported games and compare worker busy time during first paint/navigation.

### F-009: The G6 Test Harness Is Failing Before It Can Protect Performance Regressions

- Severity: Medium
- Category: tests
- Confidence: High
- Status: Confirmed
- Evidence:
  - `bun run test` fails in G6 with `TypeError: window.localStorage.clear is not a function`.
  - The failure points to `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.test.tsx:60`.
- Impact:
  - Performance refactors in `AnalysisWorkspace` would be risky without a passing behavioral test baseline.
  - The exact area we need to change has a blocked test suite.
- Reproduction or experiment:
  - Command run: `bun run test`.
- Recommended fix:
  - Fix the jsdom/localStorage test shim first.
  - Then add render-count tests around Stockfish stream behavior, viewport layout mounting, and board prop stability.
- Verification:
  - `bun run test` passes before starting performance implementation.

### F-010: There Is No Cross-Repo Performance Contract Test

- Severity: Medium
- Category: tests
- Confidence: High
- Status: Confirmed
- Evidence:
  - UltraChess has local render-budget tests for model actions at `/Users/yahorbarkouski/ultrachess-react/packages/react/test/render-budget.test.tsx:52-75`.
  - G6 has no passing test gate today because of F-009.
  - No inspected test covers "Stockfish stream -> G6 root update -> UltraChess board remains quiet."
- Impact:
  - G6 can regress UltraChess integration without UltraChess CI noticing.
  - UltraChess can preserve its own model budget while still being too easy to misuse from a live-analysis host app.
- Reproduction or experiment:
  - Source/test inspection found no cross-repo or host-churn coverage.
- Recommended fix:
  - In UltraChess, add parent-churn tests that simulate a noisy host.
  - In G6, add a mocked `@ultrachess/react` board test or Profiler-based test that counts board wrapper commits during a Stockfish info stream.
  - Add a small benchmark fixture that can be run with local G6 pointing to local UltraChess package builds.
- Verification:
  - CI should fail if 100 engine info messages cause board model reinitialization, duplicate board mounts, or repeated board-layer commits.

## Architectural Themes

### Ownership Boundaries

UltraChess owns board state well once the update is inside `BoardModel`. G6 owns the engine stream. The current boundary uses React props/effects for a high-frequency, multi-field analysis update. That is the wrong boundary shape. The new boundary should be a single analysis update operation that UltraChess can apply atomically and G6 can call only when semantic display state changes.

### Semantic Versus Raw Updates

The browser should not be asked to care about every raw Stockfish detail. Store exact engine output for correctness and debugging, but render a human-scale snapshot. For this UI, `+630` and `+631` are the same state unless a component explicitly displays exact centipawns.

### Hidden Work

CSS-hidden React trees still mount, render, run effects, and own resources. This matters more now that we know each board wrapper creates a board model/adapter. Responsive CSS should not be used as a lifecycle boundary for expensive interactive subsystems.

### Library Resilience

UltraChess's current benchmarks prove the board behaves well when the model changes. They do not prove the board behaves well when a host parent re-renders aggressively. Since G6 is a real host with that exact behavior, UltraChess should add this as a supported performance contract.

## Remediation Roadmap

### Immediate

1. Fix G6's test harness failure around `window.localStorage.clear`, so future changes can be protected.
2. Change G6 layout mounting so only one `UltraAnalysisBoard` is mounted per viewport.
3. Add G6 semantic Stockfish snapshots:
   - Raw cache/ref remains exact.
   - React state receives only visible/semantic changes.
   - Remove effect-backed `useStableEvalCp`.
4. Add an UltraChess atomic analysis update API for `positionFen + managedArrows`.
5. Replace G6 `useManagedArrows` with that API once available.

### Near-Term

1. Add UltraChess parent-churn render-budget tests.
2. Memoize/normalize UltraChess layer components based on measured parent-churn failures.
3. Stabilize G6 animation options and arrow arrays by semantic keys.
4. Make Stockfish pre-analysis idle, cancellable, and proximity-based.
5. Document the right UltraChess pattern for live analysis viewers.

### Strategic

1. Create a cross-repo benchmark fixture:
   - Mock Stockfish stream of 500 info lines.
   - One active board.
   - Assert root/board/layer commit budgets.
2. Consider a local workspace/link workflow so G6 can test unreleased UltraChess changes before publication.
3. Add browser profiler traces for:
   - Import/open game.
   - Live analysis for 30 seconds.
   - Move navigation with engine arrows.
   - Mobile and desktop viewport separately.

## Experiments and Checks

| Command or experiment | Purpose | Result | Notes |
| --- | --- | --- | --- |
| `rg --files -g 'AGENTS.md' /Users/yahorbarkouski/g6explanation-frontend /Users/yahorbarkouski/ultrachess-react` | Check repo-specific instructions | Passed with no files found | No local repo instructions to apply. |
| `git status --short` in `/Users/yahorbarkouski/ultrachess-react` | Check working tree before audit docs | Passed | Clean. |
| `git status --short` in `/Users/yahorbarkouski/g6explanation-frontend` | Check working tree | Not applicable | G6 frontend is not a Git repo. |
| `bun run lint` in G6 | Validate current frontend lint/docs formatting | Passed | Biome checked 47 files before and after this second report was added. |
| `bun run typecheck` in G6 | Validate TypeScript | Passed | `tsc -b`. |
| `bun run build` in G6 | Validate production build | Passed | Vite build succeeded; JS bundle reported around 491.56 kB gzip 155.82 kB. |
| `bun run test` in G6 | Validate current tests | Failed | Blocked by `window.localStorage.clear is not a function` in `AnalysisWorkspace.test.tsx:60`. |
| `bun run lint` in UltraChess | Validate library lint | Passed | Biome lint checked 153 files. |
| `bun run typecheck` in UltraChess | Validate library types | Passed | Turbo reported 13 successful tasks. |
| `bun -F @ultrachess/react test` | Validate React package tests | Passed | 18 files, 156 tests. |

## Documentation Updates Needed

- UltraChess `docs/PERFORMANCE.md` should add a "Host parent churn" budget once tests exist.
- UltraChess docs should include a live analysis viewer recipe with controlled FEN plus managed arrows.
- G6 should document the engine UI snapshot policy: exact raw cache versus coarse visible state.
- G6 should document why only one board mounts responsively, so future CSS layout work does not reintroduce duplicate board lifecycles.

## Residual Risk

- No browser Performance trace was captured. Source evidence is strong enough to prioritize changes, but trace data is still needed to quantify before/after wins.
- I did not inspect published package build output for UltraChess beyond local source and tests.
- I did not implement or benchmark the proposed API, so exact function names and prop shapes should be finalized during implementation.
