# Stockfish Performance Audit Event Log

Date: 2026-05-04
Repository: /Users/yahorbarkouski/g6explanation-frontend
Audit report: ./2026-05-04-stockfish-performance-audit.md

## Resume State

- Current phase: Complete.
- Artifact paths:
  - `audit/2026-05-04-stockfish-performance-audit.md`
  - `audit/2026-05-04-stockfish-performance-audit-event-log.md`
- Last completed dimension: Performance findings, checks, and remediation roadmap.
- Next planned checks: Browser React Profiler trace after baseline gates are fixed.
- Known blockers:
  - Directory is not a Git repository, so worktree status cannot be inspected with Git.
  - Final `bun run test` fails in `src/components/analysis/AnalysisWorkspace.test.tsx` because `window.localStorage.clear` is not a function.
  - Final `bun run typecheck`, `bun run lint`, and `bun run build` pass.

## Timeline

### Step 001 - Initialize Audit

- Action: Read audit skill instructions and React performance guidance.
- Reason: User requested a comprehensive performance deep-dive.
- Evidence inspected:
  - `/Users/yahorbarkouski/.codex/skills/audit/SKILL.md`
  - `/Users/yahorbarkouski/.agents/skills/vercel-react-best-practices/SKILL.md`
- Observations:
  - Audit workflow requires a report and event log.
  - Relevant React guidance emphasizes reducing subscriptions, derived state, transient refs, and transition semantics.
- Outcome: Created plan to inspect repo guidance, trace Stockfish path, run checks, and write artifacts.

### Step 002 - Establish Repository Context

- Action: Listed files, read README and package metadata, searched for repo-local instructions.
- Reason: Establish stack, commands, and constraints before judging code.
- Evidence inspected:
  - `README.md`
  - `package.json`
  - `find /Users/yahorbarkouski/g6explanation-frontend -name AGENTS.md -print`
  - `git status --short`
- Observations:
  - Stack is Bun, Vite, React, TypeScript, Tailwind, UltraChess, Stockfish.
  - No repo-local `AGENTS.md` exists.
  - Directory is not a Git repository.
- Outcome: Scope set to frontend performance audit with docs-only changes.

### Step 003 - Trace Stockfish Hook

- Action: Read `useStockfish` and UCI parsing/conversion.
- Reason: Identify how worker messages become React updates.
- Evidence inspected:
  - `src/hooks/useStockfish.ts`
  - `src/lib/stockfish-uci.ts`
- Observations:
  - Worker is created on hook mount.
  - UI state is committed through `setEngineState`.
  - Commit throttle is time-based at 80 ms.
  - Cache is in a ref, but visible state is still root React state.
  - MultiPV info is stored by `multipv`, not by depth.
- Outcome:
  - Created findings F-001, F-004, F-005, and F-007.

### Step 004 - Trace Workspace Render Path

- Action: Read `AnalysisWorkspace` top-level derivations, effects, and layouts.
- Reason: Determine which components are invalidated by Stockfish state.
- Evidence inspected:
  - `src/components/analysis/AnalysisWorkspace.tsx`
- Observations:
  - `useStockfish` is called directly in `AnalysisWorkspace`.
  - Both desktop and mobile layouts are mounted unconditionally.
  - `useStableEvalCp` stores every non-null eval in effect state.
  - Pre-analysis queues all timeline FENs on mount.
  - API polling can remap full analysis snapshots.
- Outcome:
  - Created findings F-001, F-002, F-003, F-006, F-009, and F-010.

### Step 005 - Inspect High-Frequency UI Consumers

- Action: Read board, eval, engine-lines, discovery, player, move-list, and morph-text components.
- Reason: Identify expensive render/effect/animation surfaces affected by engine updates.
- Evidence inspected:
  - `src/components/analysis/UltraAnalysisBoard.tsx`
  - `src/components/analysis/EvalBar.tsx`
  - `src/components/analysis/EngineLinesView.tsx`
  - `src/components/analysis/DiscoveryLine.tsx`
  - `src/components/analysis/MoveList.tsx`
  - `src/components/analysis/PlayerBar.tsx`
  - `src/components/ui/morph-text.tsx`
- Observations:
  - `UltraAnalysisBoard` applies managed arrows in an effect when arrow arrays change.
  - `EvalBar` animates height and morphs labels.
  - `EngineLinesView` morphs source/eval/expectation and maps PV move buttons.
  - `MoveList` maps all rows on render.
  - `MorphText` defaults to `TextMorph`.
- Outcome:
  - Created findings F-002, F-008, and F-009.

### Step 006 - Run Project Gates

- Action: Ran typecheck, lint, build, direct Vite build, and tests.
- Reason: Establish validation baseline and detect existing blockers.
- Evidence inspected:
  - `bun run typecheck`
  - `bun run lint`
  - `bun run build`
  - `bunx vite build --outDir /tmp/g6explanation-vite-audit-build --emptyOutDir`
  - `bun run test`
- Observations:
  - Initial typecheck failed on `activeJob` possibly null.
  - Initial build failed because it runs typecheck first.
  - Initial lint failed on existing Biome formatting/import ordering.
  - Direct Vite build succeeds to `/tmp` with JS 491.44 kB and gzip 155.75 kB.
  - Initial tests passed: 3 files, 5 tests.
- Outcome:
  - Recorded initial gate state and bundle baseline. Final gate state was updated in Step 011.

### Step 007 - Measure Conversion Cost

- Action: Ran a Bun microbenchmark converting legal UCI PV lines to SAN 5,000 times.
- Reason: Check whether UCI-to-SAN conversion is likely the dominant bottleneck.
- Evidence inspected:
  - Inline `bun --eval` importing `parseUciInfo`, `uciInfoLinesToBestLines`, and `sideToMoveFromFen`.
- Observations:
  - 5,000 three-line conversions took about 54 ms total in Bun, about 0.0108 ms per update.
  - This suggests SAN conversion is not the primary local bottleneck, but it is still better to convert only accepted visible snapshots.
- Outcome:
  - F-007 severity kept at Medium rather than High.

### Step 008 - Check Asset Sizes and Dependencies

- Action: Checked Stockfish/public asset size and bundle output size.
- Reason: Determine startup and worker-load implications.
- Evidence inspected:
  - `ls -lh public/stockfish/stockfish-18-single.js public/stockfish/stockfish-18-single.wasm`
  - `/tmp/g6explanation-vite-audit-build/assets/index-DAo7FAe1.js`
  - `/tmp/g6explanation-vite-audit-build/assets/ultrachess-D83hFvtg.wasm`
  - `du -sh node_modules/...`
- Observations:
  - Public Stockfish WASM is 108 MB.
  - Direct Vite build JS is 480 KB on disk, 155.75 KB gzip.
  - UltraChess WASM is 154 KB on disk.
- Outcome:
  - F-005 confirmed as high priority.

### Step 009 - Inspect Tests

- Action: Read test files and test dependencies.
- Reason: Determine whether a performance regression harness can fit existing tooling.
- Evidence inspected:
  - `src/lib/api.test.ts`
  - `src/components/analysis/AnalysisImportPanel.test.tsx`
  - `src/lib/game-analysis-mapping.test.ts`
  - `package.json`
- Observations:
  - Vitest and Testing Library are present.
  - Existing tests cover API import, import panel behavior, and mapping.
  - No performance/render-count tests exist.
- Outcome:
  - Recommended adding deterministic Stockfish message replay tests after gates are green.

### Step 010 - Write Audit Artifacts

- Action: Created audit report and event log under `audit/`.
- Reason: Preserve findings, evidence, commands, and remediation path.
- Evidence inspected:
  - All prior steps.
- Observations:
  - The main fix path is render-scope reduction plus semantic engine snapshot gating, not blanket memoization.
- Outcome:
  - Audit artifacts completed.

### Step 011 - Final Validation Update

- Action: Re-ran lint, tests, typecheck, and build after writing docs.
- Reason: Ensure docs did not introduce lint issues and capture current gate status.
- Evidence inspected:
  - `bun run lint`
  - `bun run test`
  - `bun run typecheck`
  - `bun run build`
  - `src/components/analysis/AnalysisWorkspace.test.tsx`
- Observations:
  - `bun run lint` passes and checks 47 files.
  - `bun run typecheck` passes.
  - `bun run build` passes and emits JS 491.44 kB, gzip 155.75 kB.
  - `bun run test` now runs 4 files and 6 tests, with 1 failing test.
  - Failing test: `src/components/analysis/AnalysisWorkspace.test.tsx:60`, `window.localStorage.clear is not a function`.
- Outcome:
  - Updated F-011 from type/lint/build gate failure to current test gate failure.

## Command Log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 002 | `pwd && rg --files -g '!*node_modules*' ...` | List repo files | Passed | Identified Vite/React structure |
| 002 | `find /Users/yahorbarkouski/g6explanation-frontend -name AGENTS.md -print` | Find repo instructions | Passed | No results |
| 002 | `git status --short` | Check worktree state | Failed | Not a Git repository |
| 002 | `sed -n '1,240p' README.md` | Read repo overview | Passed | Found commands and stack |
| 002 | `sed -n '1,240p' package.json` | Read scripts/dependencies | Passed | Bun, Vite, React, Stockfish |
| 003 | `rg -n "Stockfish|stockfish|evaluation|eval|..." src` | Find engine/update code | Passed | Located `useStockfish` and consumers |
| 003 | `nl -ba src/hooks/useStockfish.ts` | Trace worker state | Passed | Found worker lifecycle and commit throttle |
| 003 | `nl -ba src/lib/stockfish-uci.ts` | Trace UCI conversion | Passed | Found full SAN conversion per accepted info batch |
| 004 | `nl -ba src/components/analysis/AnalysisWorkspace.tsx` | Trace root render path | Passed | Found both layouts and eval stabilizer |
| 005 | `nl -ba src/components/analysis/UltraAnalysisBoard.tsx` | Trace board effects | Passed | Found managed arrow effect |
| 005 | `nl -ba src/components/analysis/EvalBar.tsx` | Trace eval display | Passed | Found height transition and morph label |
| 005 | `nl -ba src/components/analysis/EngineLinesView.tsx` | Trace line display | Passed | Found morph labels and PV map |
| 005 | `nl -ba src/components/analysis/MoveList.tsx` | Trace move list | Passed | Found full row map on render |
| 006 | `bun run typecheck` | Initial TypeScript gate | Failed | `activeJob` possibly null at that point |
| 006 | `bun run lint` | Initial Biome gate | Failed | Formatting/import-order issues at that point |
| 006 | `bun run build` | Initial production gate | Failed | Blocked by typecheck at that point |
| 006 | `bunx vite build --outDir /tmp/g6explanation-vite-audit-build --emptyOutDir` | Bundle output | Passed | JS 491.44 kB, gzip 155.75 kB |
| 006 | `bun run test` | Initial test gate | Passed | 3 files, 5 tests at that point |
| 007 | `bun --eval 'import ... uciInfoLinesToBestLines ...'` | Microbenchmark conversion | Passed | About 0.0108 ms per update in Bun |
| 008 | `ls -lh public/stockfish/...` | Asset size | Passed | Stockfish WASM 108 MB |
| 008 | `du -sh node_modules/...` | Dependency size context | Passed | Stockfish package 239 MB on disk |
| 010 | `mkdir -p audit` | Create audit artifact directory | Passed | Docs-only change |
| 011 | `bun run lint` | Final Biome gate | Passed | Checked 47 files |
| 011 | `bun run test` | Final test gate | Failed | `AnalysisWorkspace.test.tsx` localStorage setup failure |
| 011 | `bun run typecheck` | Final TypeScript gate | Passed | `tsc -b` passed |
| 011 | `bun run build` | Final production gate | Passed | JS 491.44 kB, gzip 155.75 kB |

## Hypothesis Log

| ID | Hypothesis | Evidence For | Evidence Against | Status | Related Finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | Stockfish state commits re-render too much of the app | `useStockfish` lives in `AnalysisWorkspace`; state committed via `setEngineState`; root renders all panels | None found | Confirmed | F-001 |
| H-002 | Tiny centipawn changes reach React even when visually unnecessary | Commit throttle is time-based only; exact `evalCp` is state | Eval bar rounds to 0.1, but exact value still drives height and state | Confirmed | F-004 |
| H-003 | Responsive CSS hiding still mounts hidden expensive trees | Both desktop/mobile layouts are unconditional JSX; hidden classes only affect CSS | Mobile sub-tabs conditionally mount parts, but layout itself remains | Confirmed | F-002 |
| H-004 | `useStableEvalCp` doubles renders | Effect stores every non-null displayed eval after render | React bails if same primitive, but Stockfish cp often changes | Confirmed | F-003 |
| H-005 | UCI-to-SAN conversion is the main bottleneck | Conversion happens before commit filtering and creates chess boards | Bun microbenchmark is very fast | Partially dismissed | F-007 |
| H-006 | Worker startup is a startup bottleneck | Worker starts on mount; Stockfish WASM is 108 MB | Production compression/caching not verified | Confirmed risk | F-005 |
| H-007 | Existing tests are absent | Initial file list did not emphasize tests | Current package and source include Vitest tests | Dismissed | F-011 |
| H-008 | Import polling contributes lower-frequency full renders | Poll effect remaps full snapshots | Poll interval is 1.2 s, much slower than Stockfish | Confirmed low priority | F-010 |

## Files and Docs Inspected

Repository guidance:

- `README.md`: stack and project commands.
- `package.json`: scripts, dependencies, Stockfish copy step.

Stockfish and chess logic:

- `src/hooks/useStockfish.ts`: worker lifecycle, throttling, cache, pre-analysis queue.
- `src/lib/stockfish-uci.ts`: UCI info parsing and PV conversion.
- `src/lib/chess.ts`: FEN/move/eval helpers.

Workspace and analysis UI:

- `src/components/analysis/AnalysisWorkspace.tsx`: root state, layout rendering, derived engine/eval/arrow state, import polling.
- `src/components/analysis/UltraAnalysisBoard.tsx`: board wrapper and managed arrow effect.
- `src/components/analysis/EvalBar.tsx`: eval bar display and animation.
- `src/components/analysis/EngineLinesView.tsx`: engine-line rendering.
- `src/components/analysis/DiscoveryLine.tsx`: discovery eval rendering.
- `src/components/analysis/MoveList.tsx`: move-list mapping and active scroll effect.
- `src/components/analysis/PlayerBar.tsx`: player metadata display.
- `src/components/analysis/PositionInfo.tsx`: marker explanation rendering.
- `src/components/ui/morph-text.tsx`: text morph wrapper.

Import/API:

- `src/components/analysis/AnalysisImportPanel.tsx`: import UI and progress display.
- `src/lib/api.ts`: import and poll API calls.
- `src/lib/game-analysis-mapping.ts`: snapshot-to-analysis mapping.

Tests:

- `src/lib/api.test.ts`: import API test.
- `src/components/analysis/AnalysisImportPanel.test.tsx`: import UI tests.
- `src/components/analysis/AnalysisWorkspace.test.tsx`: workspace import/poll/map test and current failing localStorage setup.
- `src/lib/game-analysis-mapping.test.ts`: mapping tests.

Assets/build:

- `public/stockfish/stockfish-18-single.js`
- `public/stockfish/stockfish-18-single.wasm`
- `/tmp/g6explanation-vite-audit-build/assets/index-DAo7FAe1.js`
- `/tmp/g6explanation-vite-audit-build/assets/ultrachess-D83hFvtg.wasm`

## Blockers and Deferred Checks

- Browser profiling was not run. Recommended next check: deterministic Stockfish message replay in browser with React Profiler, before and after fixing F-001 through F-004.
- Production WASM delivery was not verified. Need deployed headers or preview server with compression to confirm whether the 108 MB WASM is compressed and cached.
- Baseline `bun run test` is blocked by `AnalysisWorkspace.test.tsx` localStorage setup. Fix F-011 before using the test suite as a release gate.
