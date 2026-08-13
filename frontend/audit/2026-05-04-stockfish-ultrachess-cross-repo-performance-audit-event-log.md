# Audit Event Log

Date: 2026-05-04
Repositories:

- G6 frontend: `/Users/yahorbarkouski/g6explanation-frontend`
- UltraChess React: `/Users/yahorbarkouski/ultrachess-react`

Audit report: `./2026-05-04-stockfish-ultrachess-cross-repo-performance-audit.md`

## Resume State

- Current phase: Complete.
- Artifact paths:
  - `/Users/yahorbarkouski/g6explanation-frontend/audit/2026-05-04-stockfish-ultrachess-cross-repo-performance-audit.md`
  - `/Users/yahorbarkouski/g6explanation-frontend/audit/2026-05-04-stockfish-ultrachess-cross-repo-performance-audit-event-log.md`
- Last completed dimension: Cross-repo G6/UltraChess performance boundary audit.
- Next planned checks: None in this audit turn; implementation can start from the remediation roadmap.
- Known blockers:
  - G6 test suite fails at `src/components/analysis/AnalysisWorkspace.test.tsx:60` because `window.localStorage.clear` is not a function.
  - G6 frontend directory is not a Git repository.

## Timeline

### Step 001 - Reframe Scope Around UltraChess Ownership

- Action: Re-read the user's clarification that UltraChess React is owned and can be changed.
- Reason: The first audit treated UltraChess mostly as a dependency boundary; the new scope allows fixes in both repositories.
- Evidence inspected: User message, prior Stockfish audit artifacts.
- Observations:
  - The recommended fix path should include library API and benchmark changes, not only G6 host-app containment.
  - The audit should separate G6 responsibilities from UltraChess responsibilities.
- Outcome: Created a new cross-repo audit instead of overwriting the prior G6-only Stockfish audit.

### Step 002 - Load Audit and React Performance Guidance

- Action: Read the local audit skill and React performance guidance.
- Reason: The user asked for a deep, comprehensive audit; React re-render patterns are central to the issue.
- Evidence inspected:
  - `/Users/yahorbarkouski/.codex/skills/audit/SKILL.md`
  - `/Users/yahorbarkouski/.agents/skills/vercel-react-best-practices/SKILL.md`
- Observations:
  - Audit requires durable report and event log.
  - Relevant React guidance includes derived state, primitive dependencies, refs for transient values, and avoiding broad subscriptions.
- Outcome: Adopted report/event-log structure and source-backed findings.

### Step 003 - Locate and Check UltraChess Repository

- Action: Located `/Users/yahorbarkouski/ultrachess-react` and checked its Git status.
- Reason: The user said UltraChess is owned; local source needed to verify integration behavior.
- Evidence inspected:
  - `/Users/yahorbarkouski/ultrachess-react/package.json`
  - `git status --short`
- Observations:
  - UltraChess working tree was clean.
  - Root package describes an opinionated React chessboard with owned state, byte-scoped subscriptions, refs-only drag, and explicit budgets.
- Outcome: Confirmed UltraChess is available locally for source and validation.

### Step 004 - Check Repository Instructions

- Action: Searched both repositories for `AGENTS.md`.
- Reason: Audit workflow requires reading repo-specific instructions first.
- Evidence inspected:
  - `rg --files -g 'AGENTS.md' /Users/yahorbarkouski/g6explanation-frontend /Users/yahorbarkouski/ultrachess-react`
- Observations:
  - No `AGENTS.md` files were found.
  - G6 is not a Git repository, so `git status` is unavailable there.
- Outcome: No additional repository-specific instructions applied.

### Step 005 - Inspect G6 Stockfish Root State Flow

- Action: Re-read the G6 analysis workspace and Stockfish hook.
- Reason: The user's stated concern is high-frequency Stockfish updates causing unnecessary renders.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts`
- Observations:
  - `AnalysisWorkspace` calls `useStockfish({ multiPv: 3, targetDepth: 24 })`.
  - `useStockfish` commits exact `fen`, `lines`, `depth`, and `evalCp`.
  - Commits are throttled by time, not by visible semantic changes.
  - Engine-derived values are computed at workspace root and passed into both desktop and mobile layouts.
- Outcome: Confirmed F-002 and F-005.

### Step 006 - Inspect G6 Responsive Layout Mounting

- Action: Traced `DesktopLayout`, `MobileLayout`, and their board instances.
- Reason: The first audit identified duplicate hidden trees; UltraChess ownership made the hidden board cost more important to quantify.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:360-434`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:477`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:501-511`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:609`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:637-647`
- Observations:
  - Both layout components are always returned from render.
  - CSS classes hide one layout, but React still mounts both.
  - Both layouts include `UltraAnalysisBoard`.
- Outcome: Confirmed F-001.

### Step 007 - Inspect G6 UltraChess Wrapper

- Action: Read `UltraAnalysisBoard`.
- Reason: Needed to understand how each mounted board creates and drives UltraChess state.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/UltraAnalysisBoard.tsx`
- Observations:
  - Each board wrapper calls `useChessGame()`.
  - G6 passes `positionFen={fen}` into `Chessboard`.
  - G6 separately converts app `BoardArrow[]` to UltraChess `Arrow[]` and calls `game.setManagedArrows` in an effect.
  - The wrapper creates a fresh `animation` object inline.
- Outcome: Confirmed F-001, F-003, and F-006.

### Step 008 - Inspect UltraChess Model Lifecycle

- Action: Read `useChessGame` and `BoardModel`.
- Reason: Needed to determine whether G6 creates one model or more and how controlled FENs are applied.
- Evidence inspected:
  - `/Users/yahorbarkouski/ultrachess-react/packages/react/src/hooks/use-chess-game.ts`
  - `/Users/yahorbarkouski/ultrachess-react/packages/core/src/board-model.ts`
- Observations:
  - `useChessGame()` creates a fresh ultrachess adapter and `BoardModel` asynchronously.
  - `fen` is an effect dependency, so `useChessGame({ fen })` is model-lifecycle control, not a controlled-position update.
  - `BoardModel.load(fen)` clears history, redo, premoves, arrows, selection, last move, legal cache, then commits.
  - `setManagedArrows` is a separate model mutator and can commit separately.
- Outcome: Confirmed F-003 and F-007.

### Step 009 - Inspect UltraChess Subscription and Arrow Internals

- Action: Read the subscription store and arrow model.
- Reason: Needed to avoid blaming UltraChess for work it already prevents internally.
- Evidence inspected:
  - `/Users/yahorbarkouski/ultrachess-react/packages/core/src/subscribe-store.ts`
  - `/Users/yahorbarkouski/ultrachess-react/packages/core/src/arrow-model.ts`
- Observations:
  - Per-square listeners only fire when their board byte changes.
  - Global listeners fire on every model commit.
  - `setManaged` preserves arrow identity and no-ops when managed arrow keys do not change.
- Outcome:
  - Confirmed UltraChess has strong model-level protections.
  - Refined findings to focus on host parent churn and non-atomic integration rather than per-square subscriptions.

### Step 010 - Inspect UltraChess React Layers

- Action: Read `Chessboard`, `BoardGrid`, `PieceLayer`, and `ArrowsLayer`.
- Reason: Needed to understand what happens when a noisy host parent re-renders `<Chessboard>`.
- Evidence inspected:
  - `/Users/yahorbarkouski/ultrachess-react/packages/react/src/chessboard.tsx`
  - `/Users/yahorbarkouski/ultrachess-react/packages/react/src/components/board-grid.tsx`
  - `/Users/yahorbarkouski/ultrachess-react/packages/react/src/components/piece-layer.tsx`
  - `/Users/yahorbarkouski/ultrachess-react/packages/react/src/components/arrows-layer.tsx`
- Observations:
  - `Chessboard` is not memoized.
  - `BoardGrid` is not memoized despite a comment saying it re-renders only on orientation/focus changes.
  - `PieceLayer` is not memoized and rebuilds the 64 slot element list on parent render.
  - `ArrowsLayer` subscribes to arrows and redraws on arrows/orientation/palette dependencies.
- Outcome: Confirmed F-004.

### Step 011 - Inspect UltraChess Performance Contract and Tests

- Action: Read `docs/PERFORMANCE.md` and render-budget tests.
- Reason: Needed to compare documented budgets with the host-churn problem.
- Evidence inspected:
  - `/Users/yahorbarkouski/ultrachess-react/docs/PERFORMANCE.md`
  - `/Users/yahorbarkouski/ultrachess-react/packages/react/test/render-budget.test.tsx`
  - `/Users/yahorbarkouski/ultrachess-react/apps/benchmarks/bench/render-budget.bench.tsx`
- Observations:
  - The docs explicitly reject state/effect chains and emphasize external model ownership.
  - The render-budget tests cover model-driven selection and moves.
  - No inspected test simulates a host re-rendering the parent frequently with stable board model.
- Outcome: Confirmed F-004 and F-010.

### Step 012 - Inspect Stockfish Asset and Pre-Analysis Flow

- Action: Checked G6 package scripts, Stockfish asset size, worker creation, and pre-analysis queue.
- Reason: Needed to separate Stockfish CPU/asset concerns from UltraChess board rendering.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation-frontend/package.json`
  - `/Users/yahorbarkouski/g6explanation-frontend/public/stockfish`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx:182-197`
  - `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts:176-183`
- Observations:
  - Local Stockfish WASM is 108 MB.
  - The app builds all unique timeline FENs and passes them to `stockfish.preAnalyze`.
  - The worker is separate from UltraChess WASM/adapter work.
- Outcome: Confirmed F-008 and scoped Stockfish work as a G6 concern.

### Step 013 - Run UltraChess Validation

- Action: Ran UltraChess lint, typecheck, and React package tests.
- Reason: Needed to establish current library health before recommending changes.
- Commands:
  - `bun run lint`
  - `bun run typecheck`
  - `bun -F @ultrachess/react test`
- Observations:
  - Lint passed.
  - Typecheck passed.
  - React package tests passed: 18 files, 156 tests.
  - Git status remained clean afterward.
- Outcome: UltraChess baseline is healthy.

### Step 014 - Run G6 Validation

- Action: Ran G6 lint, typecheck, build, and test.
- Reason: Needed to establish current frontend health and blockers.
- Commands:
  - `bun run lint`
  - `bun run typecheck`
  - `bun run build`
  - `bun run test`
- Observations:
  - Lint passed before this second report was added.
  - Typecheck passed.
  - Build passed; Vite output included JS bundle around 491.56 kB, gzip around 155.82 kB.
  - Tests failed because `window.localStorage.clear` is not a function at `AnalysisWorkspace.test.tsx:60`.
- Outcome: Confirmed F-009.

### Step 015 - Write Cross-Repo Audit Report

- Action: Created the report and this event log under G6 `audit/`.
- Reason: The audit skill requires durable artifacts.
- Evidence created:
  - `/Users/yahorbarkouski/g6explanation-frontend/audit/2026-05-04-stockfish-ultrachess-cross-repo-performance-audit.md`
  - `/Users/yahorbarkouski/g6explanation-frontend/audit/2026-05-04-stockfish-ultrachess-cross-repo-performance-audit-event-log.md`
- Observations:
  - The report identifies ten findings and a staged remediation roadmap.
- Outcome: Documentation added; final lint check still needed.

### Step 016 - Run Final Docs/Lint Check

- Action: Ran G6 lint after adding the new audit report and event log.
- Reason: Docs-only audit output should still pass the repository's formatting/lint gate.
- Command:
  - `bun run lint`
- Observations:
  - Biome checked 47 files and reported no fixes.
- Outcome: Final audit artifacts pass the available lint gate.

## Command Log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 002 | `sed -n '1,220p' /Users/yahorbarkouski/.codex/skills/audit/SKILL.md` | Load audit workflow | Passed | Required report and event log. |
| 002 | `sed -n '1,220p' /Users/yahorbarkouski/.agents/skills/vercel-react-best-practices/SKILL.md` | Load React performance guidance | Passed | Relevant guidance: semantic state, primitive deps, refs for transient state. |
| 003 | `git status --short` in `/Users/yahorbarkouski/ultrachess-react` | Check library worktree | Passed | Clean. |
| 004 | `rg --files -g 'AGENTS.md' /Users/yahorbarkouski/g6explanation-frontend /Users/yahorbarkouski/ultrachess-react` | Find repo instructions | Passed | No files found. |
| 004 | `git status --short` in `/Users/yahorbarkouski/g6explanation-frontend` | Check G6 worktree | Failed as not applicable | Directory is not a Git repository. |
| 005 | `nl -ba src/components/analysis/AnalysisWorkspace.tsx` excerpts | Trace root render and layout flow | Passed | Confirmed root Stockfish subscription and duplicated layout trees. |
| 005 | `nl -ba src/hooks/useStockfish.ts` excerpts | Trace Stockfish commit behavior | Passed | Confirmed time-throttled exact state commits. |
| 007 | `nl -ba src/components/analysis/UltraAnalysisBoard.tsx` excerpts | Trace G6 board wrapper | Passed | Confirmed one `useChessGame()` per board wrapper and separate managed-arrow effect. |
| 008 | `nl -ba packages/react/src/hooks/use-chess-game.ts` excerpts | Trace UltraChess model lifecycle | Passed | `fen` is an effect dependency. |
| 008 | `nl -ba packages/core/src/board-model.ts` excerpts | Trace model commits | Passed | `load` clears arrows; `setManagedArrows` can commit separately. |
| 009 | `nl -ba packages/core/src/subscribe-store.ts` excerpts | Inspect subscription model | Passed | Per-square diffing works as documented. |
| 009 | `nl -ba packages/core/src/arrow-model.ts` excerpts | Inspect arrow identity/no-op behavior | Passed | Managed arrows no-op if key set is unchanged. |
| 010 | `nl -ba packages/react/src/chessboard.tsx` excerpts | Inspect React board root and render tree | Passed | Board/layers not protected from parent churn. |
| 010 | `nl -ba packages/react/src/components/board-grid.tsx` excerpts | Inspect grid layer | Passed | Not memoized. |
| 010 | `nl -ba packages/react/src/components/piece-layer.tsx` excerpts | Inspect piece layer | Passed | Rebuilds 64 slots on parent render. |
| 010 | `nl -ba packages/react/src/components/arrows-layer.tsx` excerpts | Inspect arrow layer | Passed | Canvas redraw/effects depend on layer props and arrow slices. |
| 011 | `nl -ba docs/PERFORMANCE.md` excerpts | Inspect UltraChess performance docs | Passed | Internal model budgets documented; host-churn budget absent. |
| 011 | `nl -ba packages/react/test/render-budget.test.tsx` excerpts | Inspect render budget tests | Passed | Tests cover model actions, not parent churn. |
| 012 | `ls -lh public/stockfish` | Check Stockfish asset size | Passed | WASM is 108 MB locally. |
| 013 | `bun run lint` in `/Users/yahorbarkouski/ultrachess-react` | Validate UltraChess lint | Passed | Biome lint. |
| 013 | `bun run typecheck` in `/Users/yahorbarkouski/ultrachess-react` | Validate UltraChess types | Passed | Turbo reported 13 successful tasks. |
| 013 | `bun -F @ultrachess/react test` in `/Users/yahorbarkouski/ultrachess-react` | Validate UltraChess React package | Passed | 18 files, 156 tests. |
| 014 | `bun run lint` in `/Users/yahorbarkouski/g6explanation-frontend` | Validate G6 lint | Passed | Before second report was added. |
| 014 | `bun run typecheck` in `/Users/yahorbarkouski/g6explanation-frontend` | Validate G6 types | Passed | `tsc -b`. |
| 014 | `bun run build` in `/Users/yahorbarkouski/g6explanation-frontend` | Validate G6 production build | Passed | Vite build succeeded. |
| 014 | `bun run test` in `/Users/yahorbarkouski/g6explanation-frontend` | Validate G6 tests | Failed | `window.localStorage.clear is not a function`. |
| 016 | `bun run lint` in `/Users/yahorbarkouski/g6explanation-frontend` | Validate audit Markdown after writing | Passed | Biome checked 47 files; no fixes applied. |

## Hypothesis Log

| ID | Hypothesis | Evidence For | Evidence Against | Status | Related Finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | Stockfish updates are rendered too frequently because G6 commits raw engine details into root React state. | `useStockfish` commits exact lines/depth/eval; `AnalysisWorkspace` derives engine props at root. | Time throttle limits frequency somewhat. | Confirmed | F-002, F-005 |
| H-002 | Hidden responsive layouts are cheap because they are CSS-hidden. | None after source trace. | Both desktop and mobile layout components are mounted; each contains `UltraAnalysisBoard`. | Dismissed | F-001 |
| H-003 | Owning UltraChess means the board library can absorb all Stockfish churn. | UltraChess has byte-scoped internal subscriptions. | Host parent renders still invoke board/layer functions before model subscriptions help. | Dismissed | F-002, F-004 |
| H-004 | UltraChess already batches position and arrow changes. | BoardModel actions generally commit once. | G6 drives position through `positionFen` and arrows through a separate effect; `load` clears arrows before `setManagedArrows`. | Dismissed | F-003 |
| H-005 | UltraChess render budgets cover the G6 scenario. | Render-budget tests exist and pass. | Tests cover model actions, not noisy host parent rerenders. | Dismissed | F-004, F-010 |
| H-006 | Managed arrow identity churn causes board model commits on every engine update. | G6 creates fresh arrays/effect dependencies. | UltraChess arrow model no-ops by key when managed arrows are unchanged. | Partially confirmed | F-006 |
| H-007 | `useChessGame({ fen })` is appropriate for controlled analysis navigation. | Hook accepts `fen`. | Hook effect depends on `fen`, recreating model lifecycle on changes. | Dismissed | F-007 |
| H-008 | Stockfish pre-analysis can add CPU pressure unrelated to board rendering. | G6 enqueues every unique timeline FEN; worker starts on hook mount. | No profiler trace measured the magnitude. | Likely | F-008 |
| H-009 | G6 has a passing test harness ready for render-count regression tests. | Existing tests exist. | `bun run test` fails before assertions due localStorage shim. | Dismissed | F-009 |

## Files and Docs Inspected

### G6 Frontend

- `/Users/yahorbarkouski/g6explanation-frontend/package.json`
  - Scripts, dependency versions, Stockfish postinstall copy path.
- `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx`
  - Root Stockfish subscription, engine-line derivation, pre-analysis, desktop/mobile layout mounting, board instances, stable eval hook.
- `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/UltraAnalysisBoard.tsx`
  - `useChessGame`, `Chessboard` props, managed arrow conversion/effect, animation object identity.
- `/Users/yahorbarkouski/g6explanation-frontend/src/hooks/useStockfish.ts`
  - Worker lifecycle, UCI parsing, cache update, throttled React state commits.
- `/Users/yahorbarkouski/g6explanation-frontend/public/stockfish`
  - Local Stockfish JS/WASM asset sizes.

### UltraChess React

- `/Users/yahorbarkouski/ultrachess-react/package.json`
  - Workspace scripts and package description.
- `/Users/yahorbarkouski/ultrachess-react/README.md`
  - Public package overview.
- `/Users/yahorbarkouski/ultrachess-react/docs/PERFORMANCE.md`
  - Performance contract, budgets, and anti-patterns.
- `/Users/yahorbarkouski/ultrachess-react/packages/react/src/chessboard.tsx`
  - Controlled position sync, render tree, effects, callback stabilization.
- `/Users/yahorbarkouski/ultrachess-react/packages/react/src/hooks/use-chess-game.ts`
  - Board model lifecycle and `fen` dependency.
- `/Users/yahorbarkouski/ultrachess-react/packages/react/src/hooks/use-board-subscription.ts`
  - `useSyncExternalStore`-based slice subscriptions.
- `/Users/yahorbarkouski/ultrachess-react/packages/react/src/components/board-grid.tsx`
  - Static grid render path.
- `/Users/yahorbarkouski/ultrachess-react/packages/react/src/components/piece-layer.tsx`
  - Piece layer and 64 slot construction.
- `/Users/yahorbarkouski/ultrachess-react/packages/react/src/components/arrows-layer.tsx`
  - Canvas arrow layer and redraw dependencies.
- `/Users/yahorbarkouski/ultrachess-react/packages/core/src/board-model.ts`
  - Board model mutators, `load`, `setManagedArrows`, commit behavior.
- `/Users/yahorbarkouski/ultrachess-react/packages/core/src/subscribe-store.ts`
  - Global and per-square subscription mechanics.
- `/Users/yahorbarkouski/ultrachess-react/packages/core/src/arrow-model.ts`
  - Managed arrow replacement and identity preservation.
- `/Users/yahorbarkouski/ultrachess-react/packages/core/src/adapters/ultrachess.ts`
  - Ultrachess adapter lifecycle context.
- `/Users/yahorbarkouski/ultrachess-react/packages/react/test/render-budget.test.tsx`
  - Existing render budget coverage.
- `/Users/yahorbarkouski/ultrachess-react/apps/benchmarks/bench/render-budget.bench.tsx`
  - Benchmark context for render budgets.

## Blockers and Deferred Checks

- G6 `bun run test` is blocked by the localStorage shim issue:
  - Command: `bun run test`
  - Failure: `window.localStorage.clear is not a function`
  - Location: `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.test.tsx:60`
  - Residual risk: Performance changes in the workspace cannot be safely regression-tested until this is fixed.
- No browser profiler trace was recorded:
  - Deferred check: Chrome Performance trace for live Stockfish stream before and after changes.
  - Residual risk: Findings are source-confirmed, but exact millisecond savings are not quantified.
- No implementation was performed:
  - Deferred check: API design spike for UltraChess atomic analysis updates.
  - Residual risk: Proposed API names should be finalized during implementation.
