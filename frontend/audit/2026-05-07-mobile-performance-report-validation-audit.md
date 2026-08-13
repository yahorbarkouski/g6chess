# Mobile Performance Report Validation Audit

Date: 2026-05-07
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Related event log: `./2026-05-07-mobile-performance-report-validation-audit-event-log.md`

## Executive Summary

The report is mostly directionally true about React render fan-out in the current mobile workspace. Its experiment numbers reproduce locally, the source has the same broad structure the report describes, and the one-large-`App` production chunk is real.

The report is not fully reliable as an implementation plan. It overstates or misstates a few points:

- Mobile inactive tab content is not still mounted in the current source; it is conditionally rendered.
- `useDocumentTitle(useMemo(...))` is not a per-step document-title write; it is keyed to `activeJob` and `importStatus`, not `currentPly`.
- `React.memo(MobileLayout)` by itself will not stop `currentPly` or `mobileTab` updates, because those props really change on each relevant interaction.
- Moving `currentPly` into an external store is not automatically the highest-leverage fix; many visible elements genuinely depend on ply. It also risks making URL sync, discovery/preview, board transitions, and navigation state harder to reason about.
- Code-splitting UltraChess is materially constrained by `src/main.tsx`, which initializes `ultrachess` before rendering the app, so a config-only split would not defer the WASM/bootstrap cost.

Best next move: keep the experiment harness, add a real-browser mobile/WebKit harness, then apply a smaller first implementation pass focused on component memo boundaries, stable board arrow references, and removing `MorphText` from high-frequency text. Treat external-store ply refactoring and broad manual chunking as second-pass work after measurement.

## Scope

- Included: the pasted report's methodology, claims F1-F14, current source paths, reproduced experiment output, production build chunk sizes, Stockfish activation, `MorphText`/framer-motion usage, and remediation order.
- Excluded: private backend latency, real iPhone Safari trace, Chrome DevTools or Safari Web Inspector flamegraph capture.
- Repository instructions followed: read `README.md`, `package.json`, and `audit/README.md`; treated older audit files as dated context only.
- Constraints: jsdom experiments reproduce render topology, not real mobile layout, paint, compositing, tap dispatch, or JavaScriptCore parse/compile timing.

## Methodology

I read the relevant workspace, board, engine, text-animation, routing, and build files; ran the new experiment harness with baseline logging; ran the focused performance tests; built production; inspected bundle output and dependency footprint; and compared the report's findings against line-level source evidence.

## System Map

- Entry/bootstrap: `src/main.tsx` dynamically imports React, ReactDOM, and `./App`, but imports and initializes `ultrachess` before rendering.
- Workspace state: `src/components/analysis/AnalysisWorkspace.tsx` owns `currentPly`, settings state, mobile tab state, board preview/discovery state, URL sync, and layout selection.
- Layouts: `DesktopLayout` and `MobileLayout` are plain functions inside `AnalysisWorkspace.tsx`; they receive a wide prop surface from `AnalysisGameWorkspace`.
- Board: `EngineAwareUltraAnalysisBoard` derives arrows, then renders `UltraAnalysisBoard`, which wraps `@ultrachess/react` and is not memoized.
- Browser engine: `StockfishAnalysisRuntime` isolates Stockfish snapshots behind an external store and `useSyncExternalStore` selectors.
- Animated text: `MorphText` calls framer-motion `useReducedMotion` and renders `torph` `TextMorph` when animation is allowed.
- Build: Vite/Rolldown emits a large `App-*.js` chunk plus separate React/client runtime chunks and `ultrachess-*.wasm`.

## Claim Verdicts

| Report Claim | Verdict | Notes |
| --- | --- | --- |
| Methodology / experiment harness exists and tests real workspace with selected child mocks | Confirmed | Harness exists at `src/components/analysis/AnalysisWorkspace.experiments.test.tsx` and reproduces the stated counters. |
| Hard numbers table | Confirmed with small drift | Local output matches closely; build/test machine reported `App` at 447.85 kB raw, not 437 kB. |
| F1: broad visible workspace re-render on state changes | Confirmed | `AnalysisGameWorkspace` owns all state and passes a large prop set into non-memoized layouts. |
| F2: `MorphText` re-renders around 5 times per step | Confirmed | Rapid-step experiment shows 154 renders for 30 clicks; source has steady-state MorphText in player clocks, eval, position title, and engine rows. |
| F3: `UltraAnalysisBoard` re-renders on parent commits | Confirmed | Component is a plain exported function, not `React.memo`. |
| F4: board arrow arrays can be fresh references | Confirmed, but narrower | Server/marker arrows are rebuilt when their dependencies change; browser arrows already use selector equality. |
| F5: one fat critical `App` chunk | Confirmed | Production build emits `App-YhxItsuM.js` at 447.85 kB raw / 131.42 kB gzip. |
| F6: URL writes on every step | Confirmed for URL only | `replaceAnalysisUrl` runs from a `currentPly` effect. `document.title` does not write every step. |
| F7: repeated `useReducedMotion` subscriptions | Confirmed as a risk | Multiple call sites exist; cost is plausible but not measured by current harness. |
| F8: Stockfish runtime can run for missing/loading/preview/discovery positions | Confirmed | Not active for backend-covered completed positions; still a heavy CPU path when enabled. |
| F9: mobile Safari tap latency | Plausible, not proven | jsdom wall-clock is useful as relative signal only; it does not measure Safari event dispatch or paint. |
| Tier 1.1: memo layouts + grouped props | Partially valid | Grouping props helps readability and child memoization, but layout memo alone cannot skip updates where `currentPly` or `mobileTab` changes. |
| Tier 1.2: external `currentPly` store | Needs redesign | Could reduce parent renders, but many consumers genuinely depend on ply; risky as first-pass surgery. |
| Tier 1.3: memo `UltraAnalysisBoard` | Valid | High-confidence low-risk if prop equality is explicit and tested. |
| Tier 1.4: stable arrows | Valid | Needed for board memo to pay off on settings/tab updates and no-op arrow changes. |
| Tier 1.5: only render visible mobile tab | Already true | Current mobile JSX conditionally renders `MoveList` or the analysis block. |
| Tier 2.6: reduce `MorphText` usage | Valid | Good ROI, especially clocks/eval rows/engine labels. |
| Tier 2.7: code split | Valid goal, plan needs correction | Must address top-level `ultrachess` init and actual route boundaries, not just `manualChunks`. |
| Tier 2.8: throttle URL replace | Valid | URL need not update synchronously for every rapid tap. |
| Tier 2.9: segment animation cost | Plausible | Source uses framer-motion layout IDs; current harness does not measure browser layout cost. |
| Tier 2.10: memo line rows | Valid | Useful after parent/prop stability work. |
| Tier 3 items | Mixed | Reasonable backlog, but should follow real-browser measurement. |

## Confirmed Findings

### F-001: Broad Workspace Render Fan-Out Is Real

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence: `AnalysisGameWorkspace` state is centralized at `src/components/analysis/AnalysisWorkspace.tsx:715`; both layouts are plain functions at `src/components/analysis/AnalysisWorkspace.tsx:1111` and `src/components/analysis/AnalysisWorkspace.tsx:1283`; the mobile layout receives ply, board, player, settings, tab, and content props at `src/components/analysis/AnalysisWorkspace.tsx:1015`.
- Impact: Interactions that should affect only controls or bottom content still cause board/player/eval/content re-renders.
- Reproduction or experiment: `VITE_PRINT_PERF_BASELINE=1 bun run test src/components/analysis/AnalysisWorkspace.experiments.test.tsx 2>&1 | grep experiment` reproduced mobile tab toggle counters with 4 board renders, 8 player renders, and 14 MorphText renders.
- Recommended fix: Introduce memo boundaries around high-cost leaf components first: board, player bars, eval bars, engine line rows, and content blocks. Use grouped props where it makes equality checks tractable, but do not expect layout memo alone to solve ply-driven updates.
- Verification: Re-run the experiment harness and require tab toggles/settings changes to show zero board/player renders unless the relevant props changed.

### F-002: Board Reconciliation Avoidance Is the Highest-Confidence Tier 1 Fix

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence: `UltraAnalysisBoard` is exported as a normal function at `src/components/analysis/UltraAnalysisBoard.tsx:56`; it renders `Chessboard` at `src/components/analysis/UltraAnalysisBoard.tsx:103`; `EngineAwareUltraAnalysisBoard` returns it directly at `src/components/analysis/AnalysisWorkspace.tsx:1708`.
- Impact: Mobile tab toggles and settings changes can reconcile the board even when `fen`, `orientation`, `highlightedMove`, `transitionMove`, and arrows are semantically unchanged.
- Reproduction or experiment: Mobile tab toggle x4 produced `UltraAnalysisBoard: 4`; mobile settings arrow changes produced `UltraAnalysisBoard: 2`.
- Recommended fix: Wrap `UltraAnalysisBoard` in `React.memo` with explicit equality over board-rendering props. Pair this with arrow reference stability.
- Verification: Add focused tests proving tab changes do not render the board and arrow-count no-ops do not render the board.

### F-003: Arrow Reference Stability Is Real but Should Be Scoped

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence: `EngineAwareUltraAnalysisBoard` builds marker/server arrows in a `useMemo` at `src/components/analysis/AnalysisWorkspace.tsx:1684`; `buildEngineArrows` and `buildMarkerArrows` create new arrays at `src/components/analysis/AnalysisWorkspace.tsx:2500` and `src/components/analysis/AnalysisWorkspace.tsx:2533`. Browser arrows already use `useStockfishAnalysisSelector(..., areBoardArrowsEqual)` at `src/components/analysis/AnalysisWorkspace.tsx:1849`.
- Impact: Memoizing the board will be less effective unless semantically equal arrow arrays keep their previous reference.
- Recommended fix: Add a small `useStableBoardArrows` helper using the existing `areBoardArrowsEqual` comparator.
- Verification: Experiment counters should show no board render for tab toggles and settings actions that leave arrow content unchanged.

### F-004: `MorphText` Is Overused on High-Frequency Text

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence: `MorphText` calls `useReducedMotion` and `TextMorph` at `src/components/ui/morph-text.tsx:10`; player clocks use it at `src/components/analysis/PlayerBar.tsx:64`; eval bars use it at `src/components/analysis/EvalBar.tsx:46` and `src/components/analysis/EvalBar.tsx:102`; engine rows use it at `src/components/analysis/EngineLinesView.tsx:297` and `src/components/analysis/EngineLinesView.tsx:305`; position title/score rows use it at `src/components/analysis/PositionInfo.tsx:104` and `src/components/analysis/PositionInfo.tsx:312`.
- Impact: Repeated small animation wrappers compound on every ply step.
- Reproduction or experiment: Mobile rapid stepping x30 produced 154 `MorphText` renders, or about 5.13 per step.
- Recommended fix: Replace `MorphText` with plain spans for clocks, eval labels, and engine-row labels/evals. Keep it only where the animation is product-visible enough to justify cost, such as the move title, or add an opt-in `animate` policy.
- Verification: Experiment target should be about 1 `MorphText` render per step or less.

### F-005: Startup Bundle Cost Is Real, but the Proposed Split Needs a Different Design

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence: `src/main.tsx:1` statically imports `init` from `ultrachess`; `src/main.tsx:38` awaits `initUltrachess()` before rendering. Production build emits `App-YhxItsuM.js` at 447.85 kB raw / 131.42 kB gzip, `client-CGIu27r4.js` at 178.94 kB raw / 56.50 kB gzip, and `ultrachess-D83hFvtg.wasm` at 157.88 kB raw / 57.24 kB gzip.
- Impact: Mobile cold start pays parse/compile for the app chunk and initializes UltraChess before first render, including on the import home.
- Recommended fix: Move UltraChess initialization behind the analysis board route/workspace boundary, or render the import home before board runtime initialization. Then split board/analysis dependencies from import-home dependencies. Manual chunks can improve caching, but they do not by themselves defer top-level initialization.
- Verification: Production build plus browser network waterfall should show import home rendering without loading the board/runtime chunk or initializing UltraChess.

### F-006: URL Sync Is on the Step Path; Document Title Is Not

- Severity: Low
- Category: performance
- Confidence: High
- Status: Confirmed/Corrected
- Evidence: `replaceAnalysisUrl` runs in an effect keyed to `[currentPly, shareTarget]` at `src/components/analysis/AnalysisWorkspace.tsx:867`; it calls `history.replaceState` at `src/lib/analysis-routing.ts:209`. `useDocumentTitle` writes only if `document.title !== title`, and the title memo depends on `[activeJob, importStatus]`, not `currentPly`, at `src/components/analysis/AnalysisWorkspace.tsx:635` and `src/hooks/useDocumentTitle.ts:3`.
- Impact: URL writes are a plausible small cost during rapid stepping; title writes should not be blamed for per-step lag.
- Recommended fix: Debounce or idle-schedule `replaceAnalysisUrl` while preserving final shareability after navigation settles.
- Verification: Route tests should cover final URL after stepping; performance experiment should show no synchronous history call per click.

## Risks and Follow-Ups

- Real mobile Safari performance remains unproven. jsdom actualDuration and click wall-clock are useful relative signals, but they do not measure layout, paint, compositing, WebKit event dispatch, JavaScriptCore parse/compile, or actual tap latency.
- Existing May 6 Safari audit remains relevant. This report validates React fan-out, but Safari-specific suspects like `content-visibility`, board animation, and global `will-change` still need real-browser A/B traces.
- The experiment harness currently mocks heavy children. That is useful for render topology, but it intentionally excludes the actual UltraChess reconciliation and DOM/WAAPI costs.

## Experiments and Checks

| Command or experiment | Purpose | Result | Notes |
| --- | --- | --- | --- |
| `git status --short` | Check worktree before audit | Passed | Initially showed modified tests, later clean; no product files changed. |
| `VITE_PRINT_PERF_BASELINE=1 bun run test src/components/analysis/AnalysisWorkspace.experiments.test.tsx 2>&1 \| grep experiment` | Reproduce pasted experiment numbers | Passed | Numbers closely matched the report. |
| `bun run test src/components/analysis/AnalysisWorkspace.experiments.test.tsx src/components/analysis/AnalysisWorkspace.performance.test.tsx` | Verify focused perf suites | Passed | 2 files, 13 tests. |
| `bun run build` | Verify production chunk shape | Passed | `App` 447.85 kB raw / 131.42 kB gzip. |
| `du -sh node_modules/framer-motion node_modules/torph node_modules/@ultrachess node_modules/ultrachess node_modules/border-beam node_modules/lucide-react node_modules/stockfish` | Check dependency footprint | Passed | Not bundle sizes, but confirms large dependency surfaces. |

## Revised Remediation Plan

### Immediate

1. Keep the experiment harness and add explicit assertions for the interactions that should stop rendering the board/player bars after fixes.
2. Memoize `UltraAnalysisBoard` with a manual prop comparator.
3. Add stable board-arrow references for marker/server arrow paths.
4. Replace `MorphText` with plain text in player clocks, eval bars, and engine rows.
5. Debounce or idle-schedule `replaceAnalysisUrl` for rapid stepping.

### Near-Term

1. Memoize `PlayerBar`, `HorizontalEvalBar`/`EvalBar`, `EngineLinesView` rows, and the mobile analysis/moves content blocks where props can be made stable.
2. Split workspace props into stable grouped objects only where it directly supports memo equality and testability.
3. Add a dev-only real-board performance route backed by `MOCK_ANALYSIS`.
4. Capture Chromium and WebKit/Safari traces for step x50, tab toggle, settings changes, and cold import-home load.
5. Revisit Safari-specific items from `audit/2026-05-06-safari-performance-audit.md`: `content-visibility`, active-row `scrollIntoView`, board animation, and global piece `will-change`.

### Strategic

1. Redesign cold-start boundaries so import home does not initialize UltraChess or load board-heavy chunks.
2. Consider a `currentPly` external store only after leaf memoization results are known. If pursued, define selectors for board, move list, nav, URL sync, and position info separately, and add regression tests around direct-load ply, discovery/preview exit, and route updates.
3. Gate browser Stockfish more conservatively on coarse pointers or low-power devices: lower depth, fewer MultiPV lines, no loading-state pre-analysis unless the user opts in.
4. Add a repeatable mobile performance budget command that reports render counts, real browser step latency, and startup chunk/waterfall deltas.

## Documentation Updates Needed

- Add this report and event log to `audit/README.md`.
- If fixes are implemented, update the May 6 Safari performance audit with status notes where its suspects are confirmed or dismissed by real-browser traces.

## Residual Risk

This audit validates the pasted report against source and local reproducible experiments. It does not prove the absolute mobile Safari impact or expected 3-4x improvement estimate. Those require a real-device or WebKit trace after each diagnostic change.
