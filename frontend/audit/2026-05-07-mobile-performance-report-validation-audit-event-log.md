# Mobile Performance Report Validation Audit Event Log

Date: 2026-05-07
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Audit report: `./2026-05-07-mobile-performance-report-validation-audit.md`

## Resume State

- Current phase: Audit complete.
- Artifact paths:
  - `audit/2026-05-07-mobile-performance-report-validation-audit.md`
  - `audit/2026-05-07-mobile-performance-report-validation-audit-event-log.md`
- Last completed dimension: Claim-by-claim validation of the pasted mobile performance report.
- Next planned checks: Implement first-pass memo/arrow/MorphText/URL fixes, then run jsdom experiments and real-browser WebKit/Chromium traces.
- Known blockers: No real iPhone Safari trace or browser harness for the completed analysis board was run in this audit.

## Timeline

### Step 001 - Initialize Validation Audit

- Action: Read audit skill instructions, repository guidance, package metadata, and audit index.
- Reason: User requested a deep dive into whether the pasted mobile performance report is true.
- Evidence inspected: `README.md`, `package.json`, `audit/README.md`, audit skill templates.
- Observations: Repository expects README/package startup; audit reports are dated snapshots.
- Outcome: Scoped as docs-only validation audit.

### Step 002 - Check Worktree

- Action: Ran `git status --short`.
- Reason: Avoid overwriting user edits.
- Observations: Initial status showed modified analysis test files; later `git status` and `git diff` showed a clean tree.
- Outcome: No unrelated changes needed protection by the time artifacts were written.

### Step 003 - Inspect Experiment Harness

- Action: Read `src/components/analysis/AnalysisWorkspace.experiments.test.tsx`.
- Reason: Validate methodology and mocked boundaries.
- Observations: Harness mocks Stockfish, API mapping, UltraAnalysisBoard, EvalBar, MorphText, and wraps `AnalysisWorkspace` in a React Profiler.
- Outcome: Accepted harness as useful for render topology, not real browser paint/compositing.

### Step 004 - Trace Workspace and Layout State

- Action: Read `src/components/analysis/AnalysisWorkspace.tsx` around `AnalysisGameWorkspace`, `DesktopLayout`, `MobileLayout`, `EngineAwareUltraAnalysisBoard`, Stockfish triggers, URL sync, and helper functions.
- Reason: Validate F1, F4, F6, F8, and Tier 1 recommendations.
- Observations:
  - `AnalysisGameWorkspace` owns current ply and settings state.
  - Layout functions are not memoized and receive a large prop surface.
  - Mobile tab content is conditionally rendered, so inactive tab content is not mounted.
  - URL sync runs on current ply changes.
  - Title memo is not keyed to current ply.
- Outcome: Confirmed broad render fan-out, corrected the inactive-tab and document-title claims.

### Step 005 - Trace Board and Animated Text

- Action: Read `UltraAnalysisBoard.tsx`, `morph-text.tsx`, `PlayerBar.tsx`, `EvalBar.tsx`, `PositionInfo.tsx`, and `EngineLinesView.tsx`.
- Reason: Validate F2, F3, F7, and memoization recommendations.
- Observations:
  - `UltraAnalysisBoard` is not memoized.
  - `MorphText` calls framer-motion `useReducedMotion` and renders `TextMorph`.
  - High-frequency UI surfaces use MorphText several times per visible workspace.
- Outcome: Confirmed board memo and MorphText reduction as high-confidence work.

### Step 006 - Run Reported Experiments

- Action: Ran `VITE_PRINT_PERF_BASELINE=1 bun run test src/components/analysis/AnalysisWorkspace.experiments.test.tsx 2>&1 | tee /tmp/g6-mobile-experiments.log | grep experiment`.
- Reason: Check whether the pasted hard numbers reproduce.
- Observations:
  - Desktop mount: 2 commits, 29.99 ms total.
  - Mobile mount: 2 commits, 4.58 ms total.
  - Mobile step x5: 6 commits, 8.91 ms total.
  - Mobile tab x4: 5 commits, 16.41 ms total, 4 board renders.
  - Mobile settings toggle x4: 4 commits, 5.12 ms total, no child counters.
  - Mobile rapid step x30: 31 commits, 41.52 ms React work, 285.05 ms wall clock, 154 MorphText renders.
  - Mobile Stockfish ticks: 12 commits, 0.078 ms total, no child counters.
- Outcome: Confirmed the numbers with small drift.

### Step 007 - Build Production

- Action: Ran `bun run build`.
- Reason: Validate chunk sizes and code-splitting claim.
- Observations:
  - `App-YhxItsuM.js`: 447.85 kB raw / 131.42 kB gzip.
  - `client-CGIu27r4.js`: 178.94 kB raw / 56.50 kB gzip.
  - `ultrachess-D83hFvtg.wasm`: 157.88 kB raw / 57.24 kB gzip.
- Outcome: Confirmed large app chunk; corrected exact size.

### Step 008 - Inspect Bundle and Dependency Footprint

- Action: Ran `du -sh` for key dependencies and searched built assets for bundled library signatures.
- Reason: Validate the report's bundle composition claims.
- Observations:
  - Dependency install footprint includes large `stockfish`, `lucide-react`, `framer-motion`, UltraChess packages.
  - Built `App` chunk contains app, UltraChess board code, sonner, Vercel analytics, and other app dependencies.
- Outcome: Confirmed bundle concern, with note that install size is not bundle size.

### Step 009 - Run Focused Performance Tests

- Action: Ran `bun run test src/components/analysis/AnalysisWorkspace.experiments.test.tsx src/components/analysis/AnalysisWorkspace.performance.test.tsx`.
- Reason: Verify focused test suites still pass.
- Observations: 2 files and 13 tests passed.
- Outcome: Validation audit did not introduce product-code changes.

### Step 010 - Write Audit Artifacts

- Action: Added this event log, the paired report, and updated `audit/README.md`.
- Reason: Leave durable, source-grounded findings and a corrected remediation plan.
- Outcome: Audit artifacts complete.

## Command Log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 001 | `git status --short` | Check worktree | Passed | Initially showed modified tests; later clean. |
| 001 | `sed -n '1,260p' README.md` | Read repository guidance | Passed | Product boundary and checks. |
| 001 | `cat package.json` | Read scripts/deps | Passed | Build/test/perf scripts. |
| 001 | `sed -n '1,220p' audit/README.md` | Read audit index | Passed | Dated audit context. |
| 003 | `sed -n ... AnalysisWorkspace.experiments.test.tsx` | Inspect harness | Passed | Confirmed mocks and interactions. |
| 004 | `nl -ba src/components/analysis/AnalysisWorkspace.tsx ...` | Trace workspace/layout | Passed | Confirmed/corrected claims. |
| 005 | `rg -n "MorphText\|useReducedMotion\|replaceAnalysisUrl\|StockfishAnalysisRuntime..."` | Locate hot paths | Passed | Found relevant call sites. |
| 006 | `VITE_PRINT_PERF_BASELINE=1 bun run test src/components/analysis/AnalysisWorkspace.experiments.test.tsx 2>&1 \| tee /tmp/g6-mobile-experiments.log \| grep experiment` | Reproduce experiment numbers | Passed | Numbers closely matched report. |
| 007 | `bun run build` | Validate bundle shape | Passed | App chunk 447.85 kB raw. |
| 008 | `du -sh node_modules/framer-motion node_modules/torph node_modules/@ultrachess node_modules/ultrachess node_modules/border-beam node_modules/lucide-react node_modules/stockfish` | Dependency footprint context | Passed | Install footprint only, not bundle size. |
| 009 | `bun run test src/components/analysis/AnalysisWorkspace.experiments.test.tsx src/components/analysis/AnalysisWorkspace.performance.test.tsx` | Focused perf tests | Passed | 2 files, 13 tests. |

## Hypothesis Log

| ID | Hypothesis | Evidence For | Evidence Against | Status | Related Finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | The pasted hard numbers are fabricated or stale | None after rerun | Local experiment output closely matches | Dismissed | None |
| H-002 | Broad React fan-out exists | Central state and non-memoized layouts; counters reproduce | Some child props genuinely change on ply | Confirmed | F-001 |
| H-003 | Mobile inactive tab remains mounted | Report states it | Current JSX uses conditional render | Dismissed | None |
| H-004 | Board memoization is high-confidence work | Board not memoized; counters show board renders on tab/settings changes | Needs stable arrows for full value | Confirmed | F-002 |
| H-005 | MorphText is high-frequency overhead | Source call sites and 154 renders / 30 clicks | Real TextMorph cost not measured in jsdom | Confirmed risk | F-004 |
| H-006 | Document title writes on every ply step | Report states it | Dependencies exclude `currentPly`; hook guards equality | Dismissed | F-006 correction |
| H-007 | Code splitting can be handled mostly by config | Large app chunk exists | Top-level UltraChess import/init blocks true deferral | Needs redesign | F-005 |
| H-008 | External ply store should be first fix | Could isolate consumers | Many visible consumers depend on ply; route/discovery complexity | Needs follow-up | Roadmap |

## Files and Docs Inspected

Repository guidance:

- `README.md`
- `package.json`
- `audit/README.md`
- `audit/2026-05-06-safari-performance-audit.md`
- `audit/2026-05-06-safari-performance-audit-event-log.md`

Current source:

- `src/main.tsx`
- `vite.config.ts`
- `src/components/analysis/AnalysisWorkspace.tsx`
- `src/components/analysis/AnalysisWorkspace.experiments.test.tsx`
- `src/components/analysis/AnalysisWorkspace.performance.test.tsx`
- `src/components/analysis/UltraAnalysisBoard.tsx`
- `src/components/analysis/StockfishAnalysisRuntime.tsx`
- `src/hooks/useStockfish.ts`
- `src/hooks/useDocumentTitle.ts`
- `src/lib/document-title.ts`
- `src/lib/analysis-routing.ts`
- `src/components/ui/morph-text.tsx`
- `src/components/analysis/PlayerBar.tsx`
- `src/components/analysis/EvalBar.tsx`
- `src/components/analysis/PositionInfo.tsx`
- `src/components/analysis/EngineLinesView.tsx`
- `src/components/analysis/AnalysisSettingsPopover.tsx`
- `src/components/analysis/BoardSidebar.tsx`
- `src/components/loading-ui/text-shimmer.tsx`
- `src/components/ui/animated-icon-button.tsx`

Generated/build:

- `dist/assets/*` after `bun run build`
- selected key dependency directories under `node_modules`

## Blockers and Deferred Checks

- No real-device iPhone Safari trace was captured.
- No browser/WebKit harness was added during this validation pass.
- No product-code optimizations were implemented; this audit only validates and replans.
