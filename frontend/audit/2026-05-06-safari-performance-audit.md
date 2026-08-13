# Safari Performance Audit Report

Date: 2026-05-06
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Related event log: `./2026-05-06-safari-performance-audit-event-log.md`

## Executive Summary

The current code has already fixed the broad Chrome-visible performance problems from the May 4 audits: only one responsive board mounts, browser Stockfish state is isolated behind an external store, and engine display commits are semantically gated. The focused tests confirm that backend-covered mainline positions do not re-render the board from browser-engine ticks and do not pre-analyze.

The remaining Safari lag is most likely not a React root fan-out bug. It is a WebKit/rendering hot path around move navigation:

1. `MoveList` applies `content-visibility: auto` to every move row, while the active move also calls `scrollIntoView({ block: "nearest" })`.
2. Each adjacent board step builds a `positionTransition`, and UltraChess resolves geometry with `getBoundingClientRect`, queries piece DOM nodes, then runs `Element.animate()` transforms.
3. The app globally marks every board piece with `will-change: transform`, encouraging persistent layer promotion on a dense board.
4. When backend lines are missing or still loading, the app can start a 108 MB browser Stockfish WASM worker and depth-16 pre-analysis near the current ply.

Chrome handles this mix well. Safari/WebKit is the browser where `content-visibility` is newer, has had recent compatibility bugs, and where compositing/scroll/layout interactions should be treated conservatively.

## Scope

- Included: active analysis board, move navigation, move list scrolling, board animation, browser Stockfish triggers, Safari/WebKit-specific rendering risks, focused tests, and prior audit comparison.
- Excluded: private backend latency, real Safari Web Inspector flamegraph capture, production CDN cache/compression behavior.
- Repository instructions followed: read `README.md`, `package.json`, and dated audit context selectively; did not treat old audit files as current source truth.
- Constraints: Safari exists locally via `safaridriver`, but no board-state browser harness currently exists that can load a completed analysis without the private backend or test-time mocks.

## Methodology

I compared current source against the older Stockfish/UltraChess performance findings, traced move navigation and board updates, searched for Safari-sensitive CSS/animation patterns, inspected UltraChess's distributed implementation in `node_modules`, checked Stockfish asset size, and ran focused performance/engine tests.

External WebKit context used:

- WebKit says Safari 18.0 added `content-visibility` support and describes it as a rendering/layout optimization hint: <https://webkit.org/blog/15865/webkit-features-in-safari-18-0/>
- WebKit's Web Animations article notes WAAPI avoids forced style invalidations in principle, while still recommending feature-specific testing in Safari: <https://webkit.org/blog/10266/web-animations-in-safari-13-1/>
- WebKit bug 283846 and related reports show recent Safari 18-era `content-visibility: auto` correctness issues around skipped content: <https://bugs.webkit.org/show_bug.cgi?id=283846>

## System Map

- App entry: `src/main.tsx` initializes UltraChess and renders `AnalysisWorkspace`.
- Workspace state: `src/components/analysis/AnalysisWorkspace.tsx` owns current ply, route sync, board preview/discovery state, layout selection, and browser-engine triggers.
- Board: `src/components/analysis/UltraAnalysisBoard.tsx` wraps `@ultrachess/react` with position FEN, managed arrows, highlighted squares, and a 45 ms transition.
- Move list: `src/components/analysis/MoveList.tsx` renders all move rows, memoizes rows/cells, applies `content-visibility: auto`, and scrolls the active cell into view.
- Browser engine: `src/hooks/useStockfish.ts` creates `/stockfish/stockfish-18-single.js`, backed by a 108 MB wasm asset, and publishes semantically gated snapshots through `StockfishAnalysisRuntime`.

## Findings Overview

| ID | Severity | Category | Confidence | Title | Fix Priority |
| --- | --- | --- | --- | --- | --- |
| F-001 | High | performance | High | `content-visibility: auto` plus active-row `scrollIntoView` is the top Safari-specific suspect | Immediate |
| F-002 | High | performance | Medium | Board-step animation and global piece `will-change` likely over-promote layers in Safari | Immediate |
| F-003 | Medium | performance | High | Browser Stockfish can still spend heavy Safari CPU while analysis is incomplete or missing server lines | Near-term |
| F-004 | Medium | performance | Medium | Backdrop blur, filter animations, and shimmer are small but Safari-sensitive graphics costs | Near-term |
| F-005 | Low | tooling | High | There is no real-browser Safari/WebKit performance harness for a completed analysis board | Near-term |

## Confirmed Findings

### F-001: `content-visibility: auto` Plus Active-Row `scrollIntoView`

- Severity: High
- Category: performance
- Confidence: High
- Status: Likely root cause
- Evidence:
  - `MoveList` applies `contentVisibility: "auto"` and `containIntrinsicSize: "29px"` to every move row at `src/components/analysis/MoveList.tsx:35`.
  - Every active move cell runs `ref.current?.scrollIntoView({ block: "nearest" })` at `src/components/analysis/MoveList.tsx:149`.
  - Desktop keeps the move list visible next to the board; mobile mounts it in the moves tab.
  - WebKit only added `content-visibility` in Safari 18.0, and recent WebKit bugs document skipped-content behavior around `content-visibility: auto`.
- Impact:
  - Moving ply changes which row is active, asks Safari to reconcile skipped/visible row layout, and performs a scripted scroll in the same update cycle.
  - This directly matches a common user description: Chrome is fine, Safari feels sticky or delayed when stepping through moves.
- Reproduction or experiment:
  - Source trace is confirmed. Focused unit/perf tests do not exercise a real Safari layout engine, so final confirmation needs a WebKit trace.
- Recommended fix:
  - First A/B patch: remove `content-visibility` from `MoveRow` in Safari or remove it entirely for the current list size.
  - Replace unconditional `scrollIntoView` with a visibility check using the scroll container and defer the scroll to `requestAnimationFrame`.
  - If long games become a real issue, use explicit list virtualization instead of relying on `content-visibility`.
- Verification:
  - Add a WebKit/Chromium browser test that steps through 50 moves and records median frame time plus long tasks.
  - Safari trace should show fewer layout/recalculate-style events after the change.

### F-002: Board-Step Animation and Global Piece `will-change`

- Severity: High
- Category: performance
- Confidence: Medium
- Status: Likely contributor
- Evidence:
  - G6 generates a `boardTransitionMove` for adjacent ply steps at `src/components/analysis/AnalysisWorkspace.tsx:674`.
  - G6 passes a 45 ms animation config into UltraChess at `src/components/analysis/UltraAnalysisBoard.tsx:16` and `src/components/analysis/UltraAnalysisBoard.tsx:94`.
  - UltraChess syncs position in a layout effect and depends on `positionTransition`, `managedArrows`, `animation`, and `orientation` in `node_modules/@ultrachess/react/dist/index.js:2187`.
  - UltraChess measures the board with `getBoundingClientRect`, queries piece elements, schedules animation on `requestAnimationFrame`, and calls `piece.animate(...)` in `node_modules/@ultrachess/react/dist/index.js:2066`.
  - G6 applies `will-change: transform` to all `[data-piece]` nodes globally at `src/styles.css:147`.
- Impact:
  - Safari can end up keeping many piece layers promoted even when no piece is moving.
  - Every adjacent step combines board geometry reads, DOM queries, WAAPI transforms, and full board compositing.
- Reproduction or experiment:
  - Source trace confirms the path. The local WebKit/Safari trace is still needed to quantify layer count and paint/composite time.
- Recommended fix:
  - Remove global `will-change` and apply it only during drag or immediately around a running board animation.
  - A/B disable `positionTransition` in Safari first; if lag disappears, reintroduce a Safari-specific reduced animation path.
  - Consider a user-visible reduced-motion path that sets board `animationMs={0}` and skips transition objects.
- Verification:
  - Safari Web Inspector Layers/Timelines should show fewer persistent compositing layers and lower composite time during rapid move stepping.

### F-003: Browser Stockfish Still Has a Heavy Safari Path

- Severity: Medium
- Category: performance
- Confidence: High
- Status: Confirmed risk
- Evidence:
  - Stockfish worker construction happens when enabled at `src/hooks/useStockfish.ts:190`.
  - The wasm asset is 108 MB in both `public/stockfish` and `dist/stockfish`.
  - Browser analysis starts when discovery/preview/loading/missing-server-lines requires it via `browserAnalysisReasonForPosition` and `StockfishAnalysisRuntime` in `src/components/analysis/AnalysisWorkspace.tsx:657` and `src/components/analysis/StockfishAnalysisRuntime.tsx:82`.
  - Pre-analysis is capped but can still enqueue up to 12 nearby FENs at depth 16.
- Impact:
  - This is not the default hot path for backend-covered completed positions, but it can explain Safari lag while analysis is still loading, when server lines are absent, or during user discovery.
  - Safari users pay WASM fetch/compile and worker CPU on a browser that may already be stressed by board rendering.
- Reproduction or experiment:
  - `bun run perf:render` confirms backend-covered positions do not pre-analyze.
  - `du -sh public/stockfish/* dist/stockfish/*` confirms `stockfish-18-single.wasm` is 108 MB.
- Recommended fix:
  - Do not start browser Stockfish for loading positions by default in Safari. Prefer a user opt-in or idle start after the board is responsive.
  - Reduce Safari pre-analysis depth/count, or disable pre-analysis until the user enters discovery.
  - Add a compact "local engine paused" affordance instead of spending CPU automatically.
- Verification:
  - Network panel should show no Stockfish request on initial completed-analysis navigation.
  - Safari CPU profile during loading should not show Stockfish worker saturation unless the user opted in.

### F-004: Safari-Sensitive Graphics Effects

- Severity: Medium
- Category: performance
- Confidence: Medium
- Status: Likely contributor
- Evidence:
  - Navigation buttons use `backdrop-blur-sm` at `src/components/analysis/AnalysisNavigationBar.tsx:68`.
  - Mobile tabs use `backdrop-blur-sm` at `src/components/analysis/AnalysisWorkspace.tsx:1242`.
  - Animated icon transitions use CSS `filter: blur(...)` in `src/components/ui/animated-icon-button.tsx:45`.
  - Loading shimmer uses continuous framer-motion background-position animation in `src/components/loading-ui/text-shimmer.tsx:41`.
  - WebKit documents backdrop-filter support and implementation changes in Safari 18.0, so it is a real engine surface rather than a no-op.
- Impact:
  - These effects are unlikely to be the sole root cause, but they increase paint/composite work while Safari is already handling board transforms and scroll updates.
- Recommended fix:
  - Disable backdrop blur and filter blur in Safari first as a diagnostic.
  - Keep shimmer out of the board-critical viewport during move navigation.
- Verification:
  - Safari timeline should show reduced paint/composite work with blur effects disabled.

### F-005: Missing Real-Browser Safari Harness

- Severity: Low
- Category: tests
- Confidence: High
- Status: Confirmed
- Evidence:
  - Existing `AnalysisWorkspace.performance.test.tsx` uses jsdom and mocked board/engine paths.
  - The app has no mock-analysis route or browser harness that can render `MOCK_ANALYSIS` in Safari/WebKit without backend API mocks.
  - `safaridriver` and Safari are installed locally, and Playwright can target WebKit, but there is no ready fixture page to measure the completed board.
- Impact:
  - Source review can identify likely Safari hot paths, but regressions will keep slipping without an automated or semi-automated WebKit trace.
- Recommended fix:
  - Add a dev-only `/__perf/mock-analysis` route or Vite flag that renders `MOCK_ANALYSIS` through the real board.
  - Add a Playwright Chromium/WebKit script that steps moves, samples `performance.now()` deltas, and optionally captures trace artifacts.
- Verification:
  - CI or local command should compare WebKit and Chromium p95 step latency on the same mock game.

## Experiments and Checks

| Command or experiment | Purpose | Result | Notes |
| --- | --- | --- | --- |
| `git status --short` | Check for user edits before audit docs | Passed | Existing user edit in `src/components/analysis/AnalysisImportPanel.tsx`; left untouched |
| `bun run perf:render` | Check current render baseline | Passed | One board per layout; engine-only board renders: 0; pre-analysis queued FENs: 0 |
| `bun run test -- src/hooks/useStockfish.test.ts src/components/analysis/preanalysis.test.ts src/components/analysis/AnalysisWorkspace.performance.test.tsx` | Focus Stockfish/pre-analysis/perf tests | Passed | 3 files, 17 tests |
| `du -sh public/stockfish/* dist/stockfish/*` | Measure Stockfish assets | Passed | `stockfish-18-single.wasm` is 108 MB |
| `safaridriver --version` | Check Safari automation availability | Passed | Safari 26.4 WebDriver present |
| `bunx playwright install --dry-run chromium webkit` | Check WebKit/Chromium automation availability | Passed | Browser install targets are available |

## Remediation Roadmap

### Immediate

1. A/B remove `content-visibility: auto` from `MoveRow`.
2. Guard or defer active-row `scrollIntoView`.
3. A/B remove global piece `will-change`.
4. A/B set Safari board move animation to `0ms`.

### Near-Term

1. Gate browser Stockfish more conservatively for Safari while analysis is loading.
2. Remove backdrop/filter blur from board-critical controls on Safari if timeline confirms paint/composite pressure.
3. Add a real mock-analysis performance route and Chromium/WebKit step-navigation benchmark.

### Strategic

1. Replace `content-visibility` row skipping with measured virtualization only if real games need it.
2. Add Safari/WebKit performance budgets to release checks for move stepping, discovery, and line preview.

## Residual Risk

The audit did not capture a Safari Web Inspector trace, so F-001 and F-002 remain source-confirmed likely causes rather than profiler-confirmed root causes. The first implementation pass should be an A/B branch with a Safari trace before and after each diagnostic toggle.
