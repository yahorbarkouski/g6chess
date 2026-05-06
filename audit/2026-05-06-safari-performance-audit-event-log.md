# Safari Performance Audit Event Log

Date: 2026-05-06
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Audit report: `./2026-05-06-safari-performance-audit.md`

## Resume State

- Current phase: Audit complete.
- Artifact paths:
  - `audit/2026-05-06-safari-performance-audit.md`
  - `audit/2026-05-06-safari-performance-audit-event-log.md`
- Last completed dimension: Safari-specific rendering, scrolling, board animation, and browser Stockfish risk.
- Next planned checks: Implement A/B toggles for `content-visibility`, active-row scroll, global `will-change`, and board animation; capture Safari/WebKit traces.
- Known blockers: No current browser harness renders `MOCK_ANALYSIS` through the real board without backend or test mocks.

## Timeline

### Step 001 - Initialize Audit

- Action: Read audit skill instructions, `README.md`, `package.json`, and checked git status.
- Reason: User requested a deep-dive into Safari lag.
- Evidence inspected: `/Users/yahorbarkouski/.codex/skills/audit/SKILL.md`, `README.md`, `package.json`, `git status --short`.
- Observations: Repository expects README first; user edit exists in `src/components/analysis/AnalysisImportPanel.tsx`.
- Outcome: Scoped as docs-only audit; user edit left untouched.

### Step 002 - Read Current Runtime Hot Paths

- Action: Read `AnalysisWorkspace`, `UltraAnalysisBoard`, `StockfishAnalysisRuntime`, `useStockfish`, `useAnalysisBoard`, `MoveList`, `EngineLinesView`, `EvalBar`, and `styles.css`.
- Reason: Trace move stepping, board rendering, browser engine state, and CSS/compositor costs.
- Observations:
  - Current code conditionally mounts desktop or mobile layout via `useMediaQuery`.
  - Stockfish state is isolated through an external store and selectors.
  - Move rows use `content-visibility: auto`, and active cells call `scrollIntoView`.
  - Board pieces globally receive `will-change: transform`.
- Outcome: Confirmed older root render fan-out findings are mostly fixed; opened Safari-specific hypotheses.

### Step 003 - Compare Prior Performance Audits

- Action: Read May 4 Stockfish and cross-repo performance audits plus current audit index.
- Reason: Avoid treating historical fixed findings as current.
- Evidence inspected:
  - `audit/2026-05-04-stockfish-performance-audit.md`
  - `audit/2026-05-04-stockfish-ultrachess-cross-repo-performance-audit.md`
  - `audit/README.md`
- Observations: Prior fixes claimed one-board mounting, semantic Stockfish gating, atomic position/arrows, and capped pre-analysis. Current source matches those broad fixes.
- Outcome: Dismissed generic "Chrome also should be bad" root causes.

### Step 004 - Run Focused Tests

- Action: Ran current performance and engine/pre-analysis tests.
- Reason: Verify current protections before assigning blame.
- Commands:
  - `bun run perf:render`
  - `bun run test -- src/hooks/useStockfish.test.ts src/components/analysis/preanalysis.test.ts src/components/analysis/AnalysisWorkspace.performance.test.tsx`
- Observations:
  - Perf baseline passed.
  - Engine-only board renders: 0.
  - Engine-only board prop changes: 0.
  - Pre-analysis queued FENs: 0 for backend-covered mainline positions.
  - Focused test subset passed: 3 files, 17 tests.
- Outcome: Browser Stockfish is not the main completed-position hot path.

### Step 005 - Inspect Safari-Sensitive CSS and Animation Surfaces

- Action: Searched for `content-visibility`, `scrollIntoView`, `backdrop-blur`, `will-change`, transitions, filters, and framer-motion usage.
- Reason: Safari lag often concentrates in layout/paint/compositor paths.
- Evidence inspected: `rg` output across `src/components` and `src/styles.css`.
- Observations:
  - `content-visibility` appears only in `MoveList`.
  - `scrollIntoView` is tied to active move changes.
  - `backdrop-blur-sm` appears in navigation/mobile tabs.
  - `filter: blur` appears in animated icon transitions.
  - Infinite shimmer animation appears in loading UI.
- Outcome: Formed F-001 and F-004.

### Step 006 - Inspect UltraChess Distributed Board Implementation

- Action: Read relevant generated code in `node_modules/@ultrachess/react/dist/index.js`.
- Reason: Understand what G6 board props cause inside the third-party board.
- Evidence inspected:
  - `syncPositionFen` path around lines 2089-2116.
  - `Chessboard` layout effect around lines 2187-2208.
  - `AnimationRunner` around lines 1140-1166.
  - rendered board layers around lines 2463-2511.
- Observations:
  - Position sync measures/query pieces and schedules WAAPI transform animation.
  - The board renders DOM layers for grid, arrows, pieces, drag layer, coordinates, and live region.
  - G6's `managedArrows` prop keeps position/arrows atomic, but the animation path still performs DOM geometry work.
- Outcome: Formed F-002.

### Step 007 - Measure Local Engine Asset Size

- Action: Ran `du -sh public/stockfish/* dist/stockfish/*`.
- Reason: Quantify browser Stockfish cost.
- Observations: Stockfish wasm is 108 MB in source public assets and built dist assets.
- Outcome: Formed F-003 as confirmed risk, not default completed-position root cause.

### Step 008 - Check Safari/WebKit Automation Availability

- Action: Ran `safaridriver --version` and `bunx playwright install --dry-run chromium webkit`.
- Reason: Determine whether a browser trace could be automated immediately.
- Observations:
  - `safaridriver` is installed and reports Safari 26.4.
  - Playwright can install Chromium and WebKit targets.
  - App lacks a completed-analysis browser harness without backend/test mocks.
- Outcome: Formed F-005.

### Step 009 - External WebKit Context

- Action: Looked up WebKit documentation and bug context for `content-visibility`, backdrop filters, and Web Animations.
- Reason: Validate that the suspected surfaces are real Safari/WebKit implementation areas.
- Evidence inspected:
  - WebKit Safari 18.0 feature post.
  - WebKit Web Animations in Safari 13.1 post.
  - WebKit bug 283846 and related search results.
- Observations:
  - Safari 18.0 added `content-visibility` support.
  - WebKit documents recent `content-visibility` and backdrop-filter work.
  - WebKit has recent `content-visibility: auto` bugs.
- Outcome: Increased confidence in F-001 as Safari-specific suspect.

### Step 010 - Write Artifacts

- Action: Created this event log, paired report, and updated audit index.
- Reason: Leave durable findings and provenance.
- Outcome: Audit artifacts ready for validation.

## Command Log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 001 | `git status --short` | Check dirty worktree | Passed | User edit in `AnalysisImportPanel.tsx` |
| 001 | `sed -n '1,220p' README.md` | Read repo guidance | Passed | Product/API/checks context |
| 001 | `cat package.json` | Read scripts/deps | Passed | Vite/React/Stockfish scripts |
| 002 | `sed -n ... src/components/analysis/AnalysisWorkspace.tsx` | Trace workspace | Passed | Layout gate and browser-engine triggers |
| 002 | `sed -n ... src/components/analysis/UltraAnalysisBoard.tsx` | Trace board wrapper | Passed | Animation, managed arrows, board props |
| 002 | `sed -n ... src/hooks/useStockfish.ts` | Trace browser engine | Passed | Worker, semantic display gate, pre-analysis |
| 002 | `sed -n ... src/components/analysis/MoveList.tsx` | Trace move list | Passed | `content-visibility` and `scrollIntoView` |
| 004 | `bun run perf:render` | Current perf baseline | Passed | 1 file, 3 tests |
| 004 | `bun run test -- src/hooks/useStockfish.test.ts src/components/analysis/preanalysis.test.ts src/components/analysis/AnalysisWorkspace.performance.test.tsx` | Focused test subset | Passed | 3 files, 17 tests |
| 005 | `rg -n "backdrop|blur|shadow-|transition|animate|will-change|contentVisibility|scrollIntoView" src/components src/styles.css` | Find Safari-sensitive surfaces | Passed | Supported F-001/F-004 |
| 006 | `rg -n "useAnimation|AnimationRunner|animate\\(" node_modules/@ultrachess/react/dist/*.js` | Locate board animation internals | Passed | Supported F-002 |
| 007 | `du -sh public/stockfish/* dist/stockfish/*` | Measure Stockfish assets | Passed | Wasm is 108 MB |
| 008 | `safaridriver --version` | Check Safari automation | Passed | Safari 26.4 |
| 008 | `bunx playwright install --dry-run chromium webkit` | Check browser automation targets | Passed | Chromium/WebKit targets available |

## Hypothesis Log

| ID | Hypothesis | Evidence For | Evidence Against | Status | Related Finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | Root Stockfish updates re-render the whole workspace | Historical audits | Current external store/selectors and perf tests show no board renders on backend-covered engine ticks | Dismissed for current source | None |
| H-002 | Both desktop and mobile boards are mounted | Historical audits | Current `isDesktopLayout` conditional renders one layout; perf test confirms one board | Dismissed | None |
| H-003 | Move list `content-visibility` plus active scroll is Safari hot path | Source uses both; WebKit recently added `content-visibility` and has related bugs | No Safari trace yet | Likely | F-001 |
| H-004 | Board WAAPI transition plus global `will-change` hurts Safari compositing | Source confirms geometry reads, DOM queries, WAAPI, all-piece `will-change` | No layer/compositor trace yet | Likely | F-002 |
| H-005 | Browser Stockfish is causing all Safari lag | Worker/wasm is heavy and can start on loading/missing lines | Focused tests prove not started for backend-covered completed positions | Partial | F-003 |
| H-006 | Backdrop/filter/shimmer graphics are the main root cause | Safari-sensitive graphics found | They are small and not always active during board stepping | Possible contributor | F-004 |

## Files and Docs Inspected

Repository guidance:

- `README.md`: product boundary, local setup, checks, Stockfish asset note.
- `package.json`: scripts, dependencies, Stockfish postinstall.
- `audit/README.md`: current and historical audit index.

Current source:

- `src/components/analysis/AnalysisWorkspace.tsx`: layout selection, current ply, board transition, browser Stockfish trigger.
- `src/components/analysis/UltraAnalysisBoard.tsx`: UltraChess wrapper, animation, arrows, highlighted squares.
- `src/components/analysis/MoveList.tsx`: move rows, `content-visibility`, active-row scrolling.
- `src/components/analysis/StockfishAnalysisRuntime.tsx`: external store and engine selector subscriptions.
- `src/hooks/useStockfish.ts`: worker lifecycle, display gate, pre-analysis.
- `src/hooks/useAnalysisBoard.ts`: preview/discovery board state and FEN derivation.
- `src/components/analysis/EvalBar.tsx`: eval transition.
- `src/components/analysis/EngineLinesView.tsx`: morphing engine text and line previews.
- `src/components/analysis/AnalysisNavigationBar.tsx`: blur/transition nav controls.
- `src/components/loading-ui/text-shimmer.tsx`: infinite loading shimmer.
- `src/components/ui/animated-icon-button.tsx`: blur-filter icon transition.
- `src/styles.css`: global text rendering, board CSS, piece `will-change`.

Dependencies:

- `node_modules/@ultrachess/react/dist/index.js`: board sync, animation runner, layer composition.

External:

- WebKit Safari 18.0 features post.
- WebKit Web Animations in Safari 13.1 post.
- WebKit bug 283846 and related search results.

## Blockers and Deferred Checks

- No Safari/WebKit flamegraph was captured because the app lacks a completed-analysis browser harness independent of the private backend.
- No product code was changed in this audit. The recommended next step is an A/B implementation branch with real Safari traces after each diagnostic change.
