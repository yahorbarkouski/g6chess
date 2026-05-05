# Stockfish Performance Audit Report

Date: 2026-05-04
Repository: /Users/yahorbarkouski/g6explanation-frontend
Auditor: Codex
Related event log: ./2026-05-04-stockfish-performance-audit-event-log.md

## Executive Summary

The browser is doing more work than the visual result justifies. The largest issue is not one missing `memo`; it is that high-frequency Stockfish updates are stored at the top of `AnalysisWorkspace`, so every accepted engine update re-renders the whole workspace. That includes the import panel, both responsive layout trees, a hidden board, move lists, player bars, animated text wrappers, and board-arrow effects.

The best optimization path is to reduce the rate and scope of UI-visible engine commits:

- Keep exact Stockfish data in refs or an external engine store.
- Publish a coarse UI snapshot only when user-visible meaning changes: depth milestone, best move changes, displayed eval bucket changes, arrow set changes, mate state changes, final result arrives.
- Mount only the active responsive layout, especially only one `UltraAnalysisBoard`.
- Lazy-start Stockfish and schedule pre-analysis as idle, cancellable background work.

## Scope

Included:

- Stockfish worker lifecycle, message handling, caching, pre-analysis, and UI state commits.
- React render/update paths from `useStockfish` into `AnalysisWorkspace`, board, eval bar, engine lines, move list, and responsive layouts.
- Animation and display components that amplify high-frequency updates.
- Bundle and worker asset size checks.
- Existing project gates: typecheck, lint, test, and direct Vite build.

Excluded:

- Browser React Profiler flamegraph capture. The source already confirms the dominant update paths, but a profiler trace should be added before and after fixes.
- Backend game-analysis performance.
- Product-level choice of exact Stockfish depth or MultiPV count.

Repository instructions followed:

- No `AGENTS.md` exists inside this repository.
- The directory is not a Git repository, so `git status --short` is unavailable.
- No product code was changed during the audit.

Constraints or blockers:

- Final validation: `bun run typecheck`, `bun run lint`, and `bun run build` pass.
- Final validation: `bun run test` fails in `src/components/analysis/AnalysisWorkspace.test.tsx` because `window.localStorage.clear` is not a function in the current test environment.

## Methodology

I traced the update path from Stockfish worker messages to React state, then followed all consumers of that state through the workspace layout. I also inspected high-frequency UI surfaces, responsive rendering, animation wrappers, board effects, API polling, and tests. I ran the repo gates, a direct Vite bundle build to a temporary output directory, asset-size checks, and a small benchmark of UCI-to-SAN conversion.

## System Map

Runtime entry:

- `src/main.tsx` renders `App`.
- `src/App.tsx` renders `AnalysisWorkspace`.

Primary analysis workspace:

- `src/components/analysis/AnalysisWorkspace.tsx` owns analysis data, current ply, board preview/discovery state, responsive tab state, import polling state, and Stockfish state.
- `useStockfish({ multiPv: 3, targetDepth: 24 })` is called directly in `AnalysisWorkspace`.
- `DesktopLayout` and `MobileLayout` are both rendered by `AnalysisWorkspace`; CSS classes hide the inactive layout.

Stockfish path:

- `src/hooks/useStockfish.ts` creates a Worker for `/stockfish/stockfish-18-single.js`.
- Worker `info` lines are parsed by `src/lib/stockfish-uci.ts`.
- Parsed MultiPV lines are converted to `BestLine[]`, cached, throttled, and committed into React state.
- `AnalysisWorkspace` derives `engineLines`, `serverEvalCp`, and `boardArrows` from that state.

High-frequency consumers:

- `EvalBar` animates height and label for the current eval.
- `EngineLinesView` renders best-line eval, expectation, source depth, and clickable PV moves.
- `UltraAnalysisBoard` receives derived arrows and calls `game.setManagedArrows` in an effect.
- `DiscoveryLineSidebar` displays the current custom-line eval.

Other repeated consumers:

- `MoveList` maps all move pairs on render.
- `PlayerBar` formats clocks and captured pieces.
- `PositionInfo` parses marker explanation text with a memoized parser.
- `AnalysisImportPanel` and API polling are unrelated to Stockfish but currently sit under the same root render.

## Findings Overview

| ID | Severity | Category | Confidence | Title | Fix Priority |
| --- | --- | --- | --- | --- | --- |
| F-001 | High | performance | High | Stockfish updates re-render the entire workspace | Immediate |
| F-002 | High | performance | High | Hidden responsive layout trees, including hidden boards, stay mounted | Immediate |
| F-003 | High | performance | High | `useStableEvalCp` can add a second render for each eval change | Immediate |
| F-004 | High | performance | High | Engine commits are time-based, not semantic, so tiny eval churn reaches React | Immediate |
| F-005 | High | performance | High | Stockfish worker and 108 MB WASM start on initial workspace mount | Immediate |
| F-006 | Medium | performance | High | Pre-analysis eagerly keeps the worker busy across all timeline FENs | Near-term |
| F-007 | Medium | performance/correctness | Medium | MultiPV processing can mix depths and does full SAN conversion before commit filtering | Near-term |
| F-008 | Medium | performance | High | Animated text and height transitions amplify high-frequency engine updates | Near-term |
| F-009 | Medium | performance | High | Move list and player metadata work reruns on unrelated engine updates | Near-term |
| F-010 | Low | performance | Medium | Import polling remaps the full analysis snapshot every poll | Later |
| F-011 | Low | tooling | High | Current test gate fails on the workspace import test | Immediate prerequisite |

## Confirmed Findings

### F-001: Stockfish Updates Re-render the Entire Workspace

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - `AnalysisWorkspace` calls `useStockfish({ multiPv: 3, targetDepth: 24 })` at `src/components/analysis/AnalysisWorkspace.tsx:103`.
  - `useStockfish` commits `{ fen, lines, depth, evalCp }` into React state at `src/hooks/useStockfish.ts:89-95`.
  - `AnalysisWorkspace` passes derived Stockfish data through both layouts at `src/components/analysis/AnalysisWorkspace.tsx:360-434`.
  - Unrelated UI such as `AnalysisImportPanel` is rendered in the same root at `src/components/analysis/AnalysisWorkspace.tsx:352-358`.
- Impact:
  - Every accepted Stockfish UI commit invalidates the entire workspace render function, not just the engine panel.
  - The current 80 ms throttle permits up to 12.5 root updates per second while the engine is searching.
  - `startTransition` lowers priority, but it does not reduce the amount of work React must eventually do.
- Reproduction or experiment:
  - Source trace from worker `info` handling to `setEngineState`, then to root-level derivations and layout props.
- Recommended fix:
  - Move high-frequency engine state out of `AnalysisWorkspace` render state.
  - Keep exact engine data in refs or a `useSyncExternalStore` engine store.
  - Let only `EvalBar`, `EngineLinesView`, and board-arrow derivation subscribe to coarse selectors.
  - Keep `AnalysisWorkspace` responsible for stable position state, not every engine tick.
- Verification:
  - Add render counters or React Profiler traces. During a running search, changing `evalCp` should not re-render import panel, move list, player bars, or hidden layouts.

### F-002: Hidden Responsive Layout Trees Stay Mounted

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - `AnalysisWorkspace` renders `DesktopLayout` and `MobileLayout` unconditionally at `src/components/analysis/AnalysisWorkspace.tsx:360-434`.
  - Desktop layout is hidden with CSS at `src/components/analysis/AnalysisWorkspace.tsx:477`.
  - Mobile layout is hidden with CSS at `src/components/analysis/AnalysisWorkspace.tsx:609`.
  - Desktop board instance is mounted at `src/components/analysis/AnalysisWorkspace.tsx:501-511`.
  - Mobile board instance is mounted in the default `board` tab at `src/components/analysis/AnalysisWorkspace.tsx:637-647`.
- Impact:
  - Desktop users still mount the mobile board tree. Mobile users still mount the desktop board, sidebar, engine lines, and move list.
  - Hidden `UltraAnalysisBoard` instances still execute render work, memo work, and `useManagedArrows` effects.
  - This doubles some of the most expensive chessboard work before any memoization is considered.
- Reproduction or experiment:
  - Source trace confirms both trees are returned in JSX. CSS `hidden` does not unmount React components.
- Recommended fix:
  - Add a `useMediaQuery("(min-width: 1280px)")` or equivalent responsive store and conditionally mount only the active layout.
  - Better: share one board shell and switch only the surrounding navigation/sidebar layout.
  - Preserve mobile tab state, but do not mount inactive desktop/mobile board trees.
- Verification:
  - React Profiler should show one `UltraAnalysisBoard` mounted for the current viewport.
  - Add a temporary mount counter to `UltraAnalysisBoard`; it should count 1, not 2, on initial load.

### F-003: `useStableEvalCp` Can Add a Second Render for Each Eval Change

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - `nextEvalCp` is derived from Stockfish state at `src/components/analysis/AnalysisWorkspace.tsx:157-171`.
  - `useStableEvalCp` stores every non-null `nextEvalCp` in state via an effect at `src/components/analysis/AnalysisWorkspace.tsx:867-883`.
  - It returns `nextEvalCp ?? stableEvalCp` at `src/components/analysis/AnalysisWorkspace.tsx:885`.
- Impact:
  - When Stockfish commits a new non-null eval, the first render already displays `nextEvalCp`.
  - The effect then sets `stableEvalCp`; if the centipawn value changed, React schedules another render whose visible output is normally identical.
  - This is directly aligned with the concern about `+6.30` versus `+6.31`: every tiny accepted change can create extra render work.
- Reproduction or experiment:
  - Source trace of render followed by effect state update.
- Recommended fix:
  - Replace `stableEvalCp` state with a ref used only as fallback when `nextEvalCp` is null.
  - Or store a quantized display value and update only when its bucket changes.
  - Example policy: exact engine cache remains exact, eval bar display rounds to 0.1 pawns or a 10 to 25 cp bucket, engine-line text updates at a chosen precision.
- Verification:
  - During a search, one accepted Stockfish UI snapshot should cause at most one render of eval consumers.

### F-004: Engine Commits Are Time-Based, Not Semantic

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - `ENGINE_STATE_COMMIT_THROTTLE_MS` is 80 at `src/hooks/useStockfish.ts:13`.
  - `scheduleEngineStateCommit` flushes based on elapsed time only at `src/hooks/useStockfish.ts:101-115`.
  - The committed state includes exact `lines`, `depth`, and exact `evalCp` at `src/hooks/useStockfish.ts:89-95`.
  - `EvalBar` uses exact eval for height and label at `src/components/analysis/EvalBar.tsx:17-22`.
  - Engine-line labels use exact formatted eval and expectation at `src/components/analysis/EngineLinesView.tsx:97-103`.
- Impact:
  - A 1 cp change, a depth label increment, or a non-visible PV detail can publish a new state object.
  - Board arrows can be recomputed even when the visible arrow set is unchanged.
  - The browser sees a stream of urgent-looking visual changes even when the user cannot perceive them.
- Reproduction or experiment:
  - Source trace confirms no equality check, eval bucket, arrow-key comparison, best-move comparison, or depth milestone policy before `setEngineState`.
- Recommended fix:
  - Define a UI snapshot separate from exact analysis:
    - `fen`
    - `displayDepth`
    - `displayEvalBucket`
    - `bestMoveUci`
    - `visiblePvKey`
    - `visibleArrowKey`
    - `isMate`
    - `isFinal`
  - Commit only when one of those fields changes or on `bestmove`.
  - Suggested first policy:
    - Eval bar: 10 cp or 25 cp buckets, or 0.1 pawn display precision.
    - Engine lines: commit when best move changes, top two PV first 4 plies change, mate state changes, or depth crosses every 2 plies after depth 12.
    - Arrows: commit only when arrow tuples change.
    - Source label: update depth on milestones, not every depth if it causes visible churn.
- Verification:
  - Add a unit test for the snapshot reducer: `+630 -> +631` should not emit a new UI snapshot under the selected bucket policy.
  - Add a profiler test showing fewer commits during a fixed Stockfish message stream.

### F-005: Stockfish Worker and 108 MB WASM Start on Initial Mount

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - Worker is constructed immediately in `useStockfish` effect at `src/hooks/useStockfish.ts:176-183`.
  - `AnalysisWorkspace` always calls `useStockfish` at `src/components/analysis/AnalysisWorkspace.tsx:103`.
  - The copied Stockfish WASM is 108 MB: `public/stockfish/stockfish-18-single.wasm`.
  - `package.json:11` copies Stockfish JS/WASM into `public/stockfish`.
- Impact:
  - Initial page load can trigger a large worker/WASM fetch and compile even while verified server/mock analysis is already available.
  - The worker competes for CPU soon after mount due to current-position analysis and pre-analysis.
  - On slower laptops and mobile devices, this can make the app feel busy before the user asks for live browser Stockfish.
- Reproduction or experiment:
  - `ls -lh public/stockfish/stockfish-18-single.wasm` reports `108M`.
  - Source trace shows worker creation on mount.
- Recommended fix:
  - Lazy-create the worker only when browser engine data is needed:
    - user enters discovery,
    - user previews a line where server lines are missing or stale,
    - user explicitly enables live engine,
    - or after `requestIdleCallback` and only on suitable devices.
  - Use server/mock evals for initial render.
  - Consider serving compressed WASM with long-lived immutable caching and verifying production headers.
- Verification:
  - Network panel should show no Stockfish WASM request before the selected trigger.
  - Initial render should not create a worker.

### F-006: Pre-analysis Eagerly Keeps the Worker Busy

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - `PRE_ANALYZE_DEPTH` is 16 at `src/hooks/useStockfish.ts:12`.
  - `AnalysisWorkspace` builds all unique timeline FENs at `src/components/analysis/AnalysisWorkspace.tsx:185-195`.
  - It calls `stockfish.preAnalyze(preAnalyzeFens)` at `src/components/analysis/AnalysisWorkspace.tsx:196-200`.
  - `preAnalyze` replaces the queue with all FENs and starts processing when ready at `src/hooks/useStockfish.ts:338-349`.
- Impact:
  - Real games can enqueue dozens of depth-16 searches immediately.
  - Worker CPU does not block the main thread directly, but it competes for CPU, battery, thermal budget, and responsiveness.
  - The queue is not prioritized around the current ply or visible/next likely interactions.
- Reproduction or experiment:
  - Mock data currently has 33 timeline FENs, confirmed with a Bun import count.
- Recommended fix:
  - Make pre-analysis opt-in or idle-scheduled.
  - Prioritize current, previous, next, and currently previewed positions.
  - Pause pre-analysis while a user search is active, while the tab is hidden, and on low-power devices.
  - Add a max cache size and eviction policy.
- Verification:
  - Worker command logging should show no broad pre-analysis burst on initial mount.
  - Current-ply analysis should preempt background work without repeated `stop` churn.

### F-007: MultiPV Processing Can Mix Depths and Converts SAN Before Commit Filtering

- Severity: Medium
- Category: performance/correctness
- Confidence: Medium
- Status: Likely
- Evidence:
  - Each parsed `info` is stored by `multipv` only at `src/hooks/useStockfish.ts:212-215`.
  - The current map is sorted and converted at `src/hooks/useStockfish.ts:216-223`.
  - The commit uses `info.depth` from the latest line, not necessarily all lines at that depth, at `src/hooks/useStockfish.ts:223`.
  - `uciInfoLinesToBestLines` converts every PV to SAN at `src/lib/stockfish-uci.ts:56-75`, creating and disposing an `ultrachess` board per line at `src/lib/stockfish-uci.ts:82-101`.
- Impact:
  - The UI may publish a depth label based on one MultiPV line while other visible lines are from an older depth.
  - This can increase visible churn because one changing line causes the whole `lines` array to change.
  - Full SAN conversion happens before deciding whether the UI should commit the update.
- Reproduction or experiment:
  - A Bun microbenchmark converting 5,000 three-line snapshots with legal PVs took about 54 ms total, around 0.0108 ms per update in Bun. This suggests conversion is not the primary local bottleneck, but the current ordering still does avoidable work and weakens update semantics.
- Recommended fix:
  - Store raw UCI/score snapshots first.
  - Group or validate MultiPV by depth before publishing.
  - Run the semantic commit predicate before full SAN conversion when possible.
  - Convert to SAN only for snapshots that will be shown.
- Verification:
  - Unit-test mixed-depth message streams.
  - Ensure displayed `dN` means the visible top lines are all accepted for that depth policy.

### F-008: Animated Text and Height Transitions Amplify Engine Churn

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - `MorphText` wraps children with `TextMorph` by default at `src/components/ui/morph-text.tsx:10-17`.
  - `EvalBar` animates height on every eval change at `src/components/analysis/EvalBar.tsx:5-9`, `src/components/analysis/EvalBar.tsx:36`, and `src/components/analysis/EvalBar.tsx:49`.
  - `EvalBar` morphs the eval label at `src/components/analysis/EvalBar.tsx:38-54`.
  - `EngineLinesView` morphs source, labels, eval, and expectation at `src/components/analysis/EngineLinesView.tsx:51-54` and `src/components/analysis/EngineLinesView.tsx:94-103`.
- Impact:
  - Frequent value changes can cause repeated animation work, layout/paint work, and text morph calculations.
  - The animations are valuable for discrete move changes, but not for centipawn noise.
- Reproduction or experiment:
  - Source trace of all high-frequency fields using `MorphText`.
- Recommended fix:
  - Disable `MorphText` for live engine values or drive it from the coarse UI snapshot only.
  - Animate eval bar only when the bucket changes, not every raw cp.
  - Consider `transform: scaleY` for the bar fill if height animation shows paint cost in profiling.
- Verification:
  - Profiler/Performance panel should show fewer animation and paint tasks during search.

### F-009: Move List and Player Metadata Work Reruns on Unrelated Engine Updates

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence:
  - `MoveList` maps all move pairs into rows on render at `src/components/analysis/MoveList.tsx:59-72`.
  - Each `MoveCell` has an active-state effect for scrolling at `src/components/analysis/MoveList.tsx:137-144`.
  - `buildPlayerMeta` scans from ply 1 through `currentPly` on every workspace render at `src/components/analysis/AnalysisWorkspace.tsx:834-850`.
  - `playerMeta` is not memoized before being passed to both layouts.
- Impact:
  - Stockfish eval churn can rerun move-list and player metadata work even though `currentPly`, moves, clocks, and markers did not change.
  - The current mock has 33 moves, but full games can be much larger.
- Reproduction or experiment:
  - Mock analysis count: 33 moves, 33 timeline points, 6 markers. Real data likely has higher row counts.
- Recommended fix:
  - First fix F-001 and F-002 so these components are not under high-frequency engine updates.
  - Then memoize or precompute `playerMeta` from stable analysis/current-ply inputs.
  - Virtualize or window `MoveList` if full-game move counts become large.
- Verification:
  - Render counters should show no `MoveList` renders when only live engine eval changes.

### F-010: Import Polling Remaps the Full Analysis Snapshot Every Poll

- Severity: Low
- Category: performance
- Confidence: Medium
- Status: Confirmed
- Evidence:
  - Polling runs every 1.2 seconds while non-terminal at `src/components/analysis/AnalysisWorkspace.tsx:214-268`.
  - If any move has context, `setAnalysis(mapGameAnalysisSnapshot(snapshot, job.source))` runs at `src/components/analysis/AnalysisWorkspace.tsx:233-235`.
  - Mapping filters, sorts, and maps all context-complete moves at `src/lib/game-analysis-mapping.ts:24-33`.
- Impact:
  - This is low frequency compared with Stockfish, but it can still rebuild the entire analysis and trigger full workspace renders during imports.
  - If snapshots get large, every poll does full work even when no new move context arrived.
- Reproduction or experiment:
  - Source trace of polling and mapping.
- Recommended fix:
  - Track `snapshot.updated_at`, `context_completed`, and last mapped ply count before remapping.
  - Use incremental append/update mapping if snapshots become large.
  - Keep import progress state separate from board analysis state when possible.
- Verification:
  - Polls with unchanged `context_completed` should not call `setAnalysis`.

### F-011: Current Test Gate Fails on the Workspace Import Test

- Severity: Low
- Category: tooling
- Confidence: High
- Status: Confirmed
- Evidence:
  - Final `bun run test` fails in `src/components/analysis/AnalysisWorkspace.test.tsx:60`.
  - Failure: `TypeError: window.localStorage.clear is not a function`.
  - Final `bun run typecheck`, `bun run lint`, and `bun run build` pass.
- Impact:
  - Performance changes would be hard to validate cleanly until the baseline test gate passes.
  - The workspace import test is valuable because it covers the import/poll/map path, but the environment setup is currently brittle under the Bun/Vitest/jsdom stack.
- Reproduction or experiment:
  - `bun run test`
- Recommended fix:
  - Install a Storage-compatible localStorage test shim in Vitest setup, or stub `window.localStorage` in `AnalysisWorkspace.test.tsx` before calling `.clear()`.
  - Keep the test, then add performance-oriented tests after the gate is green.
- Verification:
  - `bun run typecheck`, `bun run lint`, `bun run test`, and `bun run build` all pass.

## Experiments and Checks

| Command or experiment | Purpose | Result | Notes |
| --- | --- | --- | --- |
| `find /Users/yahorbarkouski/g6explanation-frontend -name AGENTS.md -print` | Check repo instructions | Passed | No repo-local `AGENTS.md` found |
| `git status --short` | Check dirty worktree | Blocked | Directory is not a Git repository |
| `bun run typecheck` | TypeScript gate | Passed | Final validation passed |
| `bun run lint` | Biome gate | Passed | Final validation checked 47 files |
| `bun run build` | Production build gate | Passed | JS 491.44 kB, gzip 155.75 kB; UltraChess WASM 157.88 kB |
| `bunx vite build --outDir /tmp/g6explanation-vite-audit-build --emptyOutDir` | Bundle build without workspace mutation | Passed | JS 491.44 kB, gzip 155.75 kB; UltraChess WASM 157.88 kB |
| `bun run test` | Existing test gate | Failed | `AnalysisWorkspace.test.tsx` fails on `window.localStorage.clear` |
| UCI-to-SAN Bun benchmark | Estimate conversion cost | Passed | About 0.0108 ms per three-line update in Bun |
| `ls -lh public/stockfish/stockfish-18-single.wasm` | Worker asset size | Passed | 108 MB |

## Architectural Themes

High-frequency state needs a smaller blast radius.

The engine can update frequently, but the app should not treat every engine detail as root workspace state. The UI needs a display snapshot; the engine needs exact analysis data. Those are different contracts.

Responsive CSS hiding is not render isolation.

The current breakpoint strategy hides DOM visually while keeping React work alive. This matters most for board instances and move lists.

Precision should match perception.

Exact centipawns are useful for cache and final analysis, but live rendering should use buckets, milestones, and final flushes. The user does not benefit from `+6.30` to `+6.31` updates during search.

Animations should be event-driven.

Move changes and mode changes are good animation triggers. Raw engine churn is not.

## Remediation Roadmap

### Immediate

1. Fix the failing `AnalysisWorkspace` test environment setup so the baseline test gate is green.
2. Replace `useStableEvalCp` state with a ref or quantized display state.
3. Add semantic engine UI snapshot gating so `+630 -> +631` does not commit by default.
4. Conditionally mount one responsive layout and one `UltraAnalysisBoard`.
5. Lazy-start Stockfish instead of creating the worker on initial workspace mount.

### Near-Term

1. Move exact engine data into an engine store/ref layer and expose `useSyncExternalStore` selectors for eval, lines, arrows, status, and final state.
2. Redesign pre-analysis as an idle, priority-aware, cancellable queue.
3. Group MultiPV snapshots by depth and convert PVs to SAN only for accepted visible snapshots.
4. Disable `MorphText` for live eval/depth fields or feed it only coarse snapshots.
5. Add render-count tests or profiling scripts that assert unrelated components do not re-render during engine updates.

### Strategic

1. Add a browser performance harness using React Profiler or Playwright traces with a deterministic Stockfish message replay.
2. Define budgets: max UI commits per second during search, max initial JS/WASM bytes before interaction, max mounted board count, max renders for move list during engine search.
3. Verify production delivery for Stockfish WASM: compression, cache headers, lazy load behavior, and fallback behavior on slow devices.

## Documentation Updates Needed

- Add a short architecture note for the engine pipeline: exact engine cache versus UI display snapshot.
- Document the chosen eval/depth/PV commit policy so future changes do not reintroduce raw Stockfish churn.
- Add performance gate commands once a profiler harness exists.

## Residual Risk

- Without a browser profiler trace, this audit ranks issues by source-confirmed render topology and update frequency rather than measured frame time.
- The real impact depends on production server compression for the 108 MB Stockfish WASM and target device class.
- Real imported games may be much larger than the current mock, which would increase the impact of `MoveList`, mapping, and pre-analysis findings.
