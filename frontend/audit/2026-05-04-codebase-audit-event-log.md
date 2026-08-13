# Audit Event Log

Date: 2026-05-04
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Audit report: `./2026-05-04-codebase-audit.md`

## Resume State

- Current phase: Artifact writing complete; final validation complete.
- Artifact paths: `audit/2026-05-04-codebase-audit.md`, `audit/2026-05-04-codebase-audit-event-log.md`
- Last completed dimension: Final validation after artifact creation.
- Next planned checks: None for this audit turn.
- Known blockers: Workspace is not a Git repository. Browser visual QA was not performed. Current `bun run lint` fails on formatting/import ordering in `src/lib/game-analysis-mapping.test.ts`.

## Timeline

### Step 001 - Initialize Audit

- Action: Read audit skill instructions and templates from `/Users/yahorbarkouski/.codex/skills/audit/references/`.
- Reason: Establish required report and event-log structure.
- Evidence inspected: `report-template.md`, `event-log-template.md`.
- Observations: Audit requires durable report plus append-only event log.
- Outcome: Chose `audit/2026-05-04-codebase-audit.md` and `audit/2026-05-04-codebase-audit-event-log.md`.

### Step 002 - Establish Repository Baseline

- Action: Ran `git status --short`.
- Reason: Preserve user changes before creating audit artifacts.
- Evidence inspected: command output.
- Observations: Command failed with `fatal: not a git repository`.
- Outcome: Recorded no Git baseline available; proceeded docs-only without product code edits.

### Step 003 - Find Guidance And Metadata

- Action: Listed root files and searched for guidance/config files.
- Reason: Follow repository instructions and identify stack/checks.
- Evidence inspected: `README.md`, `package.json`, `biome.json`, `tsconfig*.json`, `vite.config.ts`, `.env.example`.
- Observations: No `AGENTS.md`; README documents Bun, Vite, React, TypeScript, Tailwind, UltraChess; checks are `typecheck`, `lint`, `build`.
- Outcome: Audit scope set to small Vite/React app plus assets/config.

### Step 004 - Source Inventory

- Action: Listed source files excluding `node_modules` and build output.
- Reason: Build a system map.
- Evidence inspected: `src/**`, `public/**`, root configs.
- Observations: About 5k source lines across active analysis components, chess helpers, mock data, Stockfish hook, and dormant API components.
- Outcome: Identified active runtime path and dormant API path.

### Step 005 - Read Domain Contracts

- Action: Read `src/types/analysis.ts`, `src/types/api.ts`, `src/data/mock-analysis.ts`, and `src/lib/api.ts`.
- Reason: Understand active and API-shaped data models.
- Evidence inspected: typed contracts and mock builder.
- Observations: Active model includes labels like `brilliant`, `great`, `book`, `forced`; API model includes `neutral`, `missed_win`, and different context packet concepts.
- Outcome: Created maintainability hypothesis for divergent/dormant contracts.

### Step 006 - Read Chess And Engine Helpers

- Action: Read `src/hooks/useStockfish.ts`, `src/lib/stockfish-uci.ts`, `src/hooks/useAnalysisBoard.ts`, and `src/lib/chess.ts`.
- Reason: Audit the highest-risk chess and runtime logic.
- Evidence inspected: worker lifecycle, parser regex, board preview/discovery state, FEN/SAN/UCI utilities.
- Observations: Stockfish is started via `new Worker("/stockfish/stockfish-18-single.js")`; parser uses a greedy regex for UCI info lines.
- Outcome: Opened engine parser and asset-delivery hypotheses.

### Step 007 - Read Active UI Path

- Action: Read `src/App.tsx`, `src/main.tsx`, and `src/components/analysis/*`.
- Reason: Trace active rendering and feature wiring.
- Evidence inspected: `AnalysisWorkspace`, board, move list, engine lines, eval bar, discovery line, settings, position info.
- Observations: App always renders `AnalysisWorkspace`, uses `MOCK_ANALYSIS`, calls `useStockfish` unconditionally, and pre-analyzes timeline FENs.
- Outcome: Confirmed eager engine startup risk.

### Step 008 - Identify Dormant API Path

- Action: Searched imports for `BoardPanel`, `ContextPanel`, `ExampleSidebar`, `MoveStrip`, and API client usage.
- Reason: Check whether API-facing code is active.
- Evidence inspected: `rg` import search.
- Observations: API client and API components are present but not imported by `App` or `AnalysisWorkspace`.
- Outcome: Confirmed dormant-code cleanup finding.

### Step 009 - Run Static Gates

- Action: Ran `bun run typecheck` and `bun run lint`.
- Reason: Execute documented checks before deeper experiments.
- Evidence inspected: command outputs.
- Observations: `tsc -b` passed. Biome checked 39 files and passed.
- Outcome: Static quality gates passed.

### Step 010 - Run Production Build

- Action: Ran `bun run build`.
- Reason: Verify production compilation and output.
- Evidence inspected: Vite build output.
- Observations: Build passed; JS bundle about 340.83 kB gzip 106.63 kB; public Stockfish assets copied into `dist/stockfish`.
- Outcome: Build gate passed and asset-size question remained.

### Step 011 - Inspect Public Assets

- Action: Listed public and dist assets, measured sizes with `du`.
- Reason: Assess delivery cost.
- Evidence inspected: `public/stockfish`, `dist/stockfish`, `dist/assets`.
- Observations: `public/stockfish/stockfish-18-single.wasm` is 108 MB; JS wrapper is 20 KB.
- Outcome: Confirmed performance hypothesis.

### Step 012 - Measure Compressed Stockfish Size

- Action: Ran `gzip -c public/stockfish/stockfish-18-single.wasm | wc -c`.
- Reason: Estimate best-case transfer with common compression.
- Evidence inspected: command output.
- Observations: Gzip size was 76,867,389 bytes.
- Outcome: Confirmed asset remains very large even compressed.

### Step 013 - Run Dependency Audit

- Action: Ran `bun audit`.
- Reason: Cover dependency vulnerability dimension.
- Evidence inspected: Bun audit output.
- Observations: No vulnerabilities found.
- Outcome: Security audit did not identify package CVEs.

### Step 014 - Validate Mock Analysis Consistency

- Action: Ran a `bun -e` script importing `MOCK_ANALYSIS` and `ultrachess/inline`.
- Reason: Check whether generated move/FEN data is internally consistent.
- Evidence inspected: script output.
- Observations: 33 moves, 33 timeline points, 6 markers; no FEN-chain or marker mismatches.
- Outcome: Dismissed mock data integrity concern.

### Step 015 - Probe Stockfish CLI Directly

- Action: Copied Stockfish JS/WASM to `/tmp/g6sf-exp` as `.cjs`, started it under Node in a PTY, sent UCI commands, then removed the temp directory.
- Reason: Confirm score orientation and gather realistic UCI output.
- Evidence inspected: Stockfish output at depth 8 for start position and after `1. e4`.
- Observations: After `1. e4`, Black-to-move score was negative, so the code's black-to-move flip is directionally correct for White POV.
- Outcome: Dismissed score-orientation concern.

### Step 016 - Reproduce UCI Parser Bug

- Action: Ran a `bun -e` parser fixture with `info depth 8 seldepth 17 ...`.
- Reason: Test the parser against realistic Stockfish output.
- Evidence inspected: parser output and failing assertion.
- Observations: Parser returned `"depth": 17`; expected `8`.
- Outcome: Created F-001.

### Step 017 - Preview Production Output

- Action: Ran `bun run preview -- --port 4173 --strictPort` and queried headers with `curl -I`.
- Reason: Confirm served asset size and MIME behavior.
- Evidence inspected: headers for `/`, `/stockfish/stockfish-18-single.wasm`, and a font.
- Observations: WASM served as `application/wasm` with `Content-Length: 112992459`. Vite preview used `Cache-Control: no-cache`.
- Outcome: Strengthened F-002. Stopped preview server with Ctrl-C.

### Step 018 - Search For Tests

- Action: Searched for test files and framework references.
- Reason: Assess verification coverage.
- Evidence inspected: `package.json`, `README.md`, `src/**`.
- Observations: No `test` script, no test files, no test framework references.
- Outcome: Created F-004.

### Step 019 - Inspect Sound Integration

- Action: Read `src/lib/use-chesscom-move-sound.ts` and hook usage.
- Reason: Audit privacy and asset behavior.
- Evidence inspected: hard-coded Chess.com URLs and pool creation.
- Observations: Six external MP3 URLs, four `Audio` elements per URL, `preload = "auto"` on mount.
- Outcome: Created F-003.

### Step 020 - Write Artifacts

- Action: Created `audit/` and wrote report plus event log.
- Reason: Satisfy required audit artifacts.
- Evidence inspected: accumulated source readings and command results.
- Observations: Findings organized by severity, with evidence, impact, reproduction, fix path, and verification.
- Outcome: Report and event log added.

### Step 021 - Detect Concurrent Source Changes

- Action: Ran final `bun run lint` and saw failures in source files that were not part of the first source inventory.
- Reason: Validate docs-only audit artifacts.
- Evidence inspected: `src/lib/game-analysis-mapping.ts`, `src/components/analysis/AnalysisImportPanel.tsx`, `src/components/ui/animated-icon-button.tsx`, updated `src/components/analysis/AnalysisWorkspace.tsx`.
- Observations: The workspace changed during the audit. A new import-game/API path appeared in the active app.
- Outcome: Reopened the report to update the system map, findings, and validation status.

### Step 022 - Recheck Current Gates

- Action: Ran `bun run typecheck`, `bun run lint`, and `bun run build` against the current workspace.
- Reason: Record authoritative final validation.
- Evidence inspected: command outputs.
- Observations: `bun run typecheck` passed. `bun run build` passed. `bun run lint` failed while the workspace was still changing.
- Outcome: Added F-006 and updated validation notes.

### Step 023 - Update Artifacts For Current State

- Action: Patched the report and event log to reflect the new active import-game path and final lint failure.
- Reason: Keep the durable audit artifacts consistent with the current files.
- Evidence inspected: `AnalysisWorkspace`, `AnalysisImportPanel`, `api.ts`, `types/api.ts`, `game-analysis-mapping.ts`.
- Observations: The new API path is active, but legacy visualization API components remain unused.
- Outcome: Audit artifacts now describe current typecheck/build pass and lint failure.

### Step 024 - Detect Newly Added Tests

- Action: Re-ran validation and inspected newly added test files.
- Reason: The final lint target changed again after Step 023.
- Evidence inspected: `package.json`, `src/lib/api.test.ts`, `src/lib/game-analysis-mapping.test.ts`, `bun run test`, `bun run lint`.
- Observations: `package.json` now has `test: vitest run`; `bun run test` passed 2 files and 3 tests. Final `bun run lint` now fails on import ordering and array formatting in `src/lib/game-analysis-mapping.test.ts`.
- Outcome: Updated F-004 and F-006 to reflect the current test/lint state.

## Command Log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 002 | `git status --short` | Establish baseline | Blocked | Not a Git repository. |
| 003 | `rg --files -g 'AGENTS.md' -g 'README*' -g 'package.json' ...` | Find guidance/config | Passed | Found README, package/config files, no AGENTS. |
| 003 | `sed -n '1,240p' README.md` | Read repo docs | Passed | Documents Bun/Vite/React and checks. |
| 003 | `sed -n '1,240p' package.json` | Read scripts/deps | Passed | No test script; postinstall copies Stockfish. |
| 003 | `sed -n '1,260p' biome.json` | Read lint config | Passed | Biome excludes node_modules, dist, public/stockfish. |
| 004 | `rg --files -g '!node_modules' -g '!dist' -g '!build'` | Source inventory | Passed | Listed app files and public assets. |
| 004 | `wc -l src/**/*.ts src/**/*.tsx src/*.ts src/*.tsx` | Size source | Passed | About 5k source lines including duplicate glob matches. |
| 005 | `nl -ba src/types/api.ts` | Read API contract | Passed | API model differs from active model. |
| 005 | `nl -ba src/types/analysis.ts` | Read active contract | Passed | Active model supports mock board workflow. |
| 005 | `nl -ba src/data/mock-analysis.ts` | Read mock generator | Passed | Builds Morphy game from SAN. |
| 006 | `nl -ba src/hooks/useStockfish.ts` | Read worker lifecycle | Passed | Worker starts eagerly; cache uses parsed depth. |
| 006 | `nl -ba src/lib/stockfish-uci.ts` | Read parser | Passed | Greedy regex identified. |
| 006 | `nl -ba src/hooks/useAnalysisBoard.ts` | Read board state | Passed | Handles preview/discovery and sound hook. |
| 006 | `nl -ba src/lib/chess.ts` | Read chess helpers | Passed | FEN/SAN/UCI/material/eval helpers. |
| 007 | `nl -ba src/components/analysis/AnalysisWorkspace.tsx` | Read active app composition | Passed | Unconditional `useStockfish`; startup pre-analysis. |
| 008 | `rg -n "BoardPanel|ContextPanel|ExampleSidebar|MoveStrip|listExamples|getExample|getMoveContext|VisualizationExample" src` | Find dormant API usage | Passed | API path not imported by active app. |
| 009 | `bun run typecheck` | TypeScript gate | Passed | `tsc -b`. |
| 009 | `bun run lint` | Initial Biome gate | Passed | Checked 39 files before concurrent source changes. |
| 010 | `bun run build` | Initial production build | Passed | Vite build succeeded. |
| 011 | `find public -maxdepth 3 -type f -print | sort | xargs -n1 ls -lh` | Public asset inventory | Passed | Stockfish WASM 108 MB. |
| 011 | `du -h public/stockfish/* dist/assets/*` | Asset sizes | Passed | Confirmed Stockfish size. |
| 012 | `gzip -c public/stockfish/stockfish-18-single.wasm | wc -c` | Compressed size | Passed | 76,867,389 bytes. |
| 013 | `bun audit` | Dependency vulnerability check | Passed | No vulnerabilities found. |
| 014 | `bun -e 'import { MOCK_ANALYSIS } ...'` | Mock consistency | Passed | No move/FEN/marker failures. |
| 015 | `node /tmp/g6sf-exp/stockfish-18-single.cjs` | Stockfish CLI experiment | Passed | Score orientation checked. |
| 016 | `bun -e 'import { parseUciInfo } ...'` | Parser depth fixture | Failed | Expected depth 8, got 17. |
| 017 | `bun run preview -- --port 4173 --strictPort` | Serve production build | Passed | Preview server started and later stopped. |
| 017 | `curl -I http://127.0.0.1:4173/stockfish/stockfish-18-single.wasm` | Confirm served WASM | Passed | 112,992,459 byte `application/wasm`. |
| 018 | `rg --files ... | rg '(test|spec)'` | Search tests | No matches | Confirms no test files. |
| 018 | `rg -n "vitest|jest|testing-library|playwright|cypress|test\\(" package.json src README.md` | Search test framework | No matches | Only unrelated regex split output. |
| 021 | `bun run lint` | Intermediate lint validation | Failed | Workspace was changing; failures moved between files. |
| 022 | `bun run typecheck` | Final TypeScript validation | Passed | `tsc -b`. |
| 022 | `bun run build` | Final production build | Passed | 2175 modules transformed; JS gzip 155.75 kB. |
| 024 | `bun run test` | Vitest validation | Passed | 2 files and 3 tests passed. |
| 024 | `bun run lint` | Final lint validation | Failed | Current workspace fails on `src/lib/game-analysis-mapping.test.ts` import order and formatting. |

## Hypothesis Log

| ID | Hypothesis | Evidence For | Evidence Against | Status | Related Finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | UCI score sign conversion may be wrong for black-to-move positions. | Code flips scores for black-to-move positions. | Stockfish CLI after `1. e4` returned a negative score for Black to move, so flipping to White POV is correct. | Dismissed | None |
| H-002 | UCI parser may misread depth when `seldepth` appears. | Regex uses greedy `.*depth`. | None; reproduction failed as expected. | Confirmed | F-001 |
| H-003 | Browser engine is too large for eager startup. | 108 MB WASM, unconditional hook, startup pre-analysis. | None; build/preview confirms asset is shipped. | Confirmed | F-002 |
| H-004 | Mock analysis data may be internally inconsistent. | Data is generated programmatically and markers are hand-entered. | Bun consistency script found no failures. | Dismissed | None |
| H-005 | Sound integration may create third-party startup requests. | External Chess.com MP3 URLs, `preload = "auto"`, 24 audio elements. | Did not run browser network trace, but static behavior is explicit. | Confirmed | F-003 |
| H-006 | Tests cover the highest-risk chess and engine primitives. | Tests were added for API and game-analysis mapping. | No test currently covers Stockfish UCI parsing, chess helpers, mock data consistency, or Stockfish hook behavior. | Dismissed for now | F-004 |
| H-007 | Legacy visualization API UI is dormant beside the active import-game API path. | `AnalysisWorkspace` renders `AnalysisImportPanel`; import search still isolates `BoardPanel`, `ContextPanel`, `ExampleSidebar`, and `MoveStrip`. | The new import-game path is active, so not all API code is dormant. | Confirmed | F-005 |
| H-008 | Source files changed during the audit, invalidating the first gate snapshot. | Final lint and file inventory included new import-game files absent from the initial inventory. | Current typecheck/build pass after the changes stabilized. | Confirmed | F-006 |

## Files And Docs Inspected

Root/config:

- `README.md`: stack and documented commands.
- `package.json`: scripts, dependencies, Stockfish `postinstall`.
- `biome.json`: lint/format configuration.
- `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`: strict TypeScript configuration.
- `vite.config.ts`: Vite plugins/server.
- `.env.example`: dormant API base URL.
- `.gitignore`: excludes `dist`, `node_modules`, local env files, tsbuildinfo.

Active app:

- `index.html`, `src/main.tsx`, `src/App.tsx`: entry path.
- `src/components/analysis/AnalysisWorkspace.tsx`: active composition and Stockfish usage.
- `src/components/analysis/AnalysisImportPanel.tsx`: active import-game form and progress display.
- `src/components/analysis/UltraAnalysisBoard.tsx`: board wrapper and drag adapter.
- `src/components/analysis/EngineLinesView.tsx`: engine line rendering.
- `src/components/analysis/MoveList.tsx`: move list rendering.
- `src/components/analysis/PositionInfo.tsx`: explanation rendering and move preview links.
- `src/components/analysis/EvalBar.tsx`, `BoardSidebar.tsx`, `AnalysisSettingsPopover.tsx`, `AnalysisNavigationBar.tsx`, `PlayerBar.tsx`, `DiscoveryLine.tsx`: supporting UI.

Domain and engine:

- `src/types/analysis.ts`: active data model.
- `src/data/mock-analysis.ts`: mock game generator.
- `src/hooks/useAnalysisBoard.ts`: preview/discovery board state.
- `src/hooks/useStockfish.ts`: worker lifecycle, queue, cache, pre-analysis.
- `src/lib/chess.ts`: chess helpers.
- `src/lib/stockfish-uci.ts`: UCI parser and conversion.
- `src/lib/analysis-format.ts`: label formatting.
- `src/lib/game-analysis-mapping.ts`: maps game-analysis API snapshots to the board model.
- `src/lib/use-chesscom-move-sound.ts`: sound integration.
- `src/lib/api.test.ts`: import API test added during audit.
- `src/lib/game-analysis-mapping.test.ts`: game-analysis mapping test added during audit.

Dormant API path:

- `src/types/api.ts`: backend-shaped visualization contract.
- `src/lib/api.ts`: typed fetch wrappers.
- `src/components/BoardPanel.tsx`, `ContextPanel.tsx`, `ExampleSidebar.tsx`, `MoveStrip.tsx`: unused API UI components.

Assets:

- `public/stockfish/stockfish-18-single.js`
- `public/stockfish/stockfish-18-single.wasm`
- `public/fonts/ABCDiatypeVariable-Trial.woff2`
- `public/fonts/ABCOtto-Medium-Trial.woff2`
- `public/favicon.svg`

## Blockers And Deferred Checks

- Git baseline blocked: `git status --short` failed because this workspace is not a Git repository.
- Final lint blocked: `bun run lint` currently fails on Biome import-order/formatting errors in `src/lib/game-analysis-mapping.test.ts`.
- Browser visual QA deferred: no UI changes were made, and the audit focused on source/behavioral risks. A future visual pass should use a browser trace to confirm initial network requests and layout behavior.
- Backend integration deferred: live API behavior was not exercised; only the frontend import path and mapping code were inspected.
- CI audit deferred: no repository metadata or CI configuration was present.
- License verification deferred: trial font and Chess.com audio license status could not be confirmed from local files.
