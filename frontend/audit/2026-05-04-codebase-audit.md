# Codebase Audit Report

Date: 2026-05-04
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Auditor: Codex
Related event log: `./2026-05-04-codebase-audit-event-log.md`

## Executive Summary

The project is a small Vite/React/TypeScript front end for a chess explanation board. During the audit the workspace changed: an import-game/API path appeared in the active app after the first source inventory and first passing lint/typecheck run. This report reflects the current workspace as of final validation.

The main risks are concentrated in runtime engine integration and verification discipline. A confirmed UCI parser bug reports `seldepth` as the engine `depth`, which makes browser Stockfish appear deeper than it is and can admit shallow evaluations into UI/cache paths. The app also eagerly ships and starts a 108 MB Stockfish WASM engine on mount, then begins pre-analysis across all positions. That is a serious cold-start and mobile-performance concern, especially now that the UI can also consume verified API analysis.

The current `typecheck`, `build`, and `test` commands pass, but `bun run lint` is red on formatting/import ordering in a newly added mapping test. Secondary risks are limited durable tests around chess/engine primitives, automatic third-party audio preloading from Chess.com, and a mixed API surface where the new import-game path is active while older visualization API components remain unused.

## Scope

- Included: source under `src/`, Vite/Bun/TypeScript/Biome configuration, public assets, documented project commands, build output characteristics, and targeted Stockfish/chess experiments.
- Excluded: dependency source under `node_modules`, full visual QA in a browser, live backend API behavior, and production CDN/server configuration outside this workspace.
- Repository instructions followed: no `AGENTS.md` found. Followed `README.md` commands and the audit skill workflow.
- Constraints or blockers: the workspace is not a Git repository, so no `git status` baseline was available. Source files changed during the audit, so initial and final gate results differ.

## Methodology

I mapped the entry points and source layout, read the active runtime path from `src/main.tsx` to `AnalysisWorkspace`, inspected chess helpers and Stockfish integration, checked public assets and package scripts, then ran the documented gates and targeted experiments. The targeted checks included mock move/FEN consistency, Stockfish CLI behavior, UCI parser behavior, production preview headers, static import searches, and vulnerability audit.

## System Map

- Runtime entry: `index.html` loads `src/main.tsx`; `src/App.tsx` renders `AnalysisWorkspace`.
- Active domain model: `src/types/analysis.ts` backs the board workflow.
- Mock data: `src/data/mock-analysis.ts` builds the Morphy Opera game from SAN using `ultrachess/inline`; it produces moves, timeline points, and six marker explanations.
- API import path: `src/components/analysis/AnalysisImportPanel.tsx` is rendered by `AnalysisWorkspace`; `src/lib/api.ts` starts and polls `/api/game-analysis/import`; `src/lib/game-analysis-mapping.ts` maps `GameAnalysisSnapshot` into the active board model.
- Board state: `src/hooks/useAnalysisBoard.ts` handles preview/discovery line state, drag moves, board highlights, and move sounds.
- Chess utilities: `src/lib/chess.ts` wraps FEN validation, SAN/UCI conversion, material, clocks, and eval formatting.
- Browser engine: `src/hooks/useStockfish.ts` starts `public/stockfish/stockfish-18-single.js` as a worker, sends UCI commands, caches lines by FEN, and pre-analyzes timeline FENs. `src/lib/stockfish-uci.ts` parses UCI output and converts PV UCI to SAN.
- UI composition: `src/components/analysis/*` renders the board, engine lines, move list, player bars, settings, eval bar, and position explanation.
- Styling/assets: Tailwind 4 via Vite, local trial fonts under `public/fonts`, Stockfish JS/WASM copied by `postinstall` into `public/stockfish`.
- Legacy API UI path: `BoardPanel`, `ContextPanel`, `ExampleSidebar`, and `MoveStrip` are present but not imported by the active app.
- Verification: package scripts provide typecheck, lint, build, and test. Current `typecheck`, `build`, and `test` pass; current `lint` fails on formatting/import ordering.

## Findings Overview

| ID | Severity | Category | Confidence | Title | Fix Priority |
| --- | --- | --- | --- | --- | --- |
| F-001 | High | correctness | High | UCI parser reads `seldepth` as search depth | Immediate |
| F-002 | High | performance | High | Browser Stockfish is a 108 MB eager startup dependency | Immediate |
| F-003 | Medium | security/privacy | High | Move sounds preload third-party Chess.com audio by default | Near-term |
| F-004 | Medium | tests | High | Tests now exist, but chess and engine parser coverage is still missing | Immediate |
| F-005 | Cleanup | maintainability | High | Legacy visualization API UI remains beside the new import-game path | Near-term |
| F-006 | Medium | maintainability | High | Current lint gate is red on newly added test formatting | Immediate |

## Confirmed Findings

### F-001: UCI Parser Reads `seldepth` As Search Depth

- Severity: High
- Category: correctness
- Confidence: High
- Status: Confirmed
- Evidence: `src/lib/stockfish-uci.ts:13` uses `^info\s+.*depth\s+(\d+).*...`, so the greedy `.*depth` can match the `depth` substring inside `seldepth`. `src/hooks/useStockfish.ts:223` stores `info.depth`, `src/hooks/useStockfish.ts:225` caches it, and `src/components/analysis/AnalysisWorkspace.tsx:126-130` uses that depth for eval-bar gating.
- Impact: Browser Stockfish depth is overstated. A line like actual `depth 8 seldepth 17` is displayed and cached as depth 17. That can make the eval bar accept shallow analysis earlier than intended and can make cache completeness checks believe a shallower result is deeper than it is.
- Reproduction or experiment: `bun -e 'import { parseUciInfo } from "./src/lib/stockfish-uci.ts"; const line="info depth 8 seldepth 17 multipv 1 score cp -46 nodes 5040 nps 360000 hashfull 1 time 14 pv e7e5 g1f3 b8c6 f1c4"; const parsed=parseUciInfo(line); console.log(JSON.stringify(parsed, null, 2)); if (parsed?.depth !== 8) process.exit(1);'` failed and printed `"depth": 17`.
- Recommended fix: Replace the regex with token-based UCI parsing. Parse whitespace-delimited tokens, read the value immediately after a token equal to `depth`, separately capture `seldepth` if needed, then read `multipv`, `score cp|mate`, and `pv`. Do not match substrings inside other UCI tokens.
- Verification: Add unit tests for lines containing both `depth` and `seldepth`, mate scores, cp scores, MultiPV lines, missing PV lines, and black-to-move score conversion. The current failing reproduction should pass with depth 8.

### F-002: Browser Stockfish Is A 108 MB Eager Startup Dependency

- Severity: High
- Category: performance
- Confidence: High
- Status: Confirmed
- Evidence: `package.json:11` copies `stockfish-18-single.js` and `stockfish-18-single.wasm` into `public/stockfish`. `src/hooks/useStockfish.ts:176-183` creates the worker whenever the hook is enabled, and `src/components/analysis/AnalysisWorkspace.tsx:73` calls it unconditionally. `src/components/analysis/AnalysisWorkspace.tsx:150-165` pre-analyzes every unique timeline FEN on startup.
- Impact: The app can initiate a very large engine download and CPU-heavy background analysis before the user asks for browser engine lines. That is especially costly on mobile and weak networks, and it conflicts with the README's current positioning as a front-end-only mock slice with verified packet data.
- Reproduction or experiment: `du -h public/stockfish/*` reported `108M` for `stockfish-18-single.wasm`. `gzip -c public/stockfish/stockfish-18-single.wasm | wc -c` reported `76867389` bytes. `bun run build` copied the asset into `dist/stockfish`. `curl -I http://127.0.0.1:4173/stockfish/stockfish-18-single.wasm` from `vite preview` reported `Content-Length: 112992459`.
- Recommended fix: Lazy-load Stockfish only after explicit user action or after the UI enters discovery mode, and keep verified/mock packet lines as the initial path. Consider a smaller browser engine build, a split engine asset, a remote analysis service, or a server-side cache for verified browser lines. Avoid startup pre-analysis until the engine asset is loaded and the user has signaled interest.
- Verification: Production build should not request `/stockfish/stockfish-18-single.wasm` on initial load. Add a browser/network test or Playwright route assertion for initial load, plus a test that the engine loads only after the chosen trigger.

### F-003: Move Sounds Preload Third-Party Chess.com Audio By Default

- Severity: Medium
- Category: security/privacy
- Confidence: High
- Status: Confirmed
- Evidence: `src/lib/use-chesscom-move-sound.ts:7-15` hard-codes six `https://images.chesscomfiles.com/...` MP3 URLs. `src/lib/use-chesscom-move-sound.ts:48-64` creates a pool of four `Audio` elements for every sound and sets `preload = "auto"` on mount. `src/hooks/useAnalysisBoard.ts:112-116` installs the sound hook for board feedback.
- Impact: App sessions can contact a third-party media host and may preload up to 24 audio elements without a user-visible setting or asset/license documentation. This can leak usage metadata, fail in offline or enterprise networks, and add avoidable startup work.
- Reproduction or experiment: Static inspection confirms the external URLs and automatic pool construction. The behavior does not depend on API configuration.
- Recommended fix: Host reviewed sound assets locally or disable preloading until after a user gesture. Add a mute/sound setting that defaults conservatively, document asset provenance/license, and avoid creating all sound pools until the first sound-enabled board interaction.
- Verification: A network test for initial page load should show no Chess.com audio requests. Unit or component tests should verify that sound pools are created only after the sound setting is enabled.

### F-004: Tests Now Exist, But Chess And Engine Parser Coverage Is Still Missing

- Severity: Medium
- Category: tests
- Confidence: High
- Status: Confirmed
- Evidence: `package.json:14` now defines `test: vitest run`, and `src/lib/api.test.ts` plus `src/lib/game-analysis-mapping.test.ts` were added during the audit. `bun run test` passes 2 files and 3 tests. No tests currently cover `src/lib/stockfish-uci.ts`, `src/lib/chess.ts`, `src/hooks/useStockfish.ts`, or `src/data/mock-analysis.ts`.
- Impact: The new tests are a useful start for the API import path, but the highest-risk chess-specific parsing, FEN/SAN/UCI conversion, Stockfish parsing, cache depth behavior, and generated mock consistency remain uncovered. The UCI depth bug is a concrete defect that current tests do not catch.
- Reproduction or experiment: `bun run test` passed. The targeted one-off UCI parser command still failed with expected depth 8 and actual depth 17.
- Recommended fix: Extend the Vitest suite to cover `stockfish-uci.ts`, `chess.ts`, `mock-analysis.ts`, and a small integration-style test around the engine state reducer/cache logic if it is extracted from the React hook. Include fixtures copied from real Stockfish output.
- Verification: `bun run test` should fail on the current UCI parser bug, pass after the parser fix, and run in CI alongside typecheck/lint/build.

### F-005: Legacy Visualization API UI Remains Beside The New Import-Game Path

- Severity: Cleanup
- Category: maintainability
- Confidence: High
- Status: Confirmed
- Evidence: `src/components/analysis/AnalysisWorkspace.tsx:357-363` now renders `AnalysisImportPanel`, and `src/lib/game-analysis-mapping.ts:24-50` maps `GameAnalysisSnapshot` into `AnalysisResponse`. Separately, import searches still found no active imports of `src/components/BoardPanel.tsx`, `src/components/ContextPanel.tsx`, `src/components/ExampleSidebar.tsx`, or `src/components/MoveStrip.tsx`.
- Impact: The codebase now has two API-era surfaces: the active full-game import path and the older visualization-example UI. Keeping both makes ownership unclear and increases the chance that future backend-contract changes update one path but not the other.
- Reproduction or experiment: Static import search confirmed the legacy visualization components are isolated from the active entry point, while `AnalysisWorkspace` imports and renders the new import-game path.
- Recommended fix: Remove the legacy visualization-example components if they are no longer planned, or place them behind an explicit route/demo boundary with tests. Keep the import-game path and legacy example path from sharing ambiguous names unless they truly share a backend contract.
- Verification: Import graph should show only intended active modules. If legacy UI remains, add route-level/component tests and contract fixtures for both API surfaces.

### F-006: Current Lint Gate Is Red On Newly Added Test Formatting

- Severity: Medium
- Category: maintainability
- Confidence: High
- Status: Confirmed
- Evidence: Final `bun run lint` failed on `src/lib/game-analysis-mapping.test.ts:1` for import ordering and on `src/lib/game-analysis-mapping.test.ts:247` for array formatting.
- Impact: If lint is enforced in CI or release gates, the current workspace cannot pass the documented checks even though typecheck, build, and tests pass. This also makes future audit/test signal noisy because formatting failures obscure behavioral findings.
- Reproduction or experiment: `bun run lint` failed with two Biome errors after the mapping test appeared. `bun run typecheck`, `bun run build`, and `bun run test` passed afterward.
- Recommended fix: Run the repo formatter or manually apply Biome's suggested import ordering and array formatting in `src/lib/game-analysis-mapping.test.ts`, then rerun `bun run lint`.
- Verification: `bun run lint` should pass with 44 checked files.

## Risks and Follow-Ups

- Absolute asset paths: `index.html:5`, `index.html:11`, `src/styles.css:5`, `src/styles.css:13`, and `src/hooks/useStockfish.ts:182` assume root deployment paths. If the app is served under a subpath, fonts, favicon, app script, and Stockfish can break. This is a deployment risk unless root hosting is guaranteed.
- Worker error handling: `useStockfish` has no surfaced error state for missing worker files, CSP failures, WASM MIME issues, memory failures, or blocked network. It silently falls back to mock/server lines in some views, but discovery mode can look empty or stale.
- Trial font licensing: `public/fonts/ABCDiatypeVariable-Trial.woff2` and `public/fonts/ABCOtto-Medium-Trial.woff2` are embedded in the production build. The repository does not include license notes. Confirm whether trial fonts are allowed in distributed builds.
- Runtime API shape validation: `src/lib/api.ts:37-43` casts JSON to TypeScript types without runtime validation. This is low risk while the API path is dormant, but it should be addressed before reviving backend integration.
- No Git metadata: the workspace is not a Git repository, which limits change attribution, branch hygiene, and audit reproducibility.

## Experiments And Checks

| Command or experiment | Purpose | Result | Notes |
| --- | --- | --- | --- |
| `git status --short` | Establish change baseline | Blocked | Workspace is not a Git repository. |
| `bun run typecheck` | TypeScript project references | Passed | `tsc -b` completed. |
| `bun run lint` | Biome lint/format gate | Failed final validation | Initial run passed with 39 files; final run failed with two errors in `game-analysis-mapping.test.ts`. |
| `bun run build` | Production build | Passed | Final build passed with 2175 transformed modules and JS gzip 155.75 kB. |
| `bun run test` | Vitest suite | Passed | 2 files and 3 tests passed. |
| `bun audit` | Dependency vulnerability audit | Passed | No vulnerabilities found. |
| Mock consistency `bun -e ...` | Validate move sequence, FEN chain, marker plies | Passed | 33 moves, 33 timeline rows, 6 markers, no failures. |
| Stockfish CLI depth 8 | Confirm score orientation | Passed | After `1. e4`, Black-to-move score was negative; code's black flip is directionally correct. |
| UCI parser depth fixture | Confirm parser handles `depth` and `seldepth` | Failed | Expected depth 8, got 17. Creates F-001. |
| `du -h public/stockfish/*` | Measure engine assets | Confirmed risk | WASM is 108 MB. |
| `gzip -c ... | wc -c` | Estimate compressed WASM size | Confirmed risk | Gzip size is 76,867,389 bytes. |
| `vite preview` + `curl -I /stockfish/...wasm` | Verify served asset size/MIME | Confirmed risk | `Content-Length: 112992459`, `Content-Type: application/wasm`. |
| `rg` test-file searches | Check test coverage presence | Confirmed gap | No test files/framework found. |

## Architectural Themes

- The current app is coherent as a single-screen React app, but engine work has crossed from enhancement into startup dependency.
- The import-game path is arriving in the active runtime, and tests are starting to arrive with it, but lint formatting is not yet caught up.
- Chess-specific logic deserves tests because bugs are semantic rather than syntactic.
- Contracts are split between an active mock-analysis model and a dormant API model. That is manageable now, but it should be resolved before backend integration resumes.
- Asset policy is implicit. Stockfish, third-party sounds, and trial fonts need explicit product/performance/license decisions.

## Remediation Roadmap

### Immediate

- Fix `parseUciInfo` with token-based parsing and add unit tests from real Stockfish output.
- Stop loading Stockfish on initial page load. Gate it behind an explicit trigger or discovery mode, and remove startup pre-analysis until the engine is intentionally enabled.
- Add minimal tests for Stockfish parsing, FEN/SAN/UCI helpers, and mock-analysis consistency.
- Format `src/lib/game-analysis-mapping.test.ts` so the documented lint gate passes again.

### Near-Term

- Replace third-party auto-preloaded sounds with local, licensed assets or lazy sound creation after a user setting/gesture.
- Add worker error state and UI fallback for missing or failed Stockfish assets.
- Decide whether legacy visualization API files are being kept. Remove them or reattach them behind a tested route and shared contract.

### Strategic

- Define an asset budget and deployment policy for engine, font, and audio assets.
- If browser Stockfish remains core, evaluate a smaller engine build, split loading, CDN caching strategy, and a progressive enhancement model.
- Generate or validate backend-facing types when API integration returns.

## Documentation Updates Needed

- Update `README.md` with the current asset/runtime behavior once Stockfish loading policy is decided.
- Document sound/font asset provenance and license status.
- Add a testing section after a test runner is introduced.
- If root-only deployment is required, document it. Otherwise switch assets to `import.meta.env.BASE_URL` or bundled URLs and document subpath support.

## Residual Risk

I did not perform full browser visual QA, accessibility testing, or a production CDN compression/cache audit. Live backend API behavior was not audited. The Stockfish runtime was checked through Node CLI and Vite preview headers, but not through an in-browser worker trace. The workspace changed during the audit, so final validation is authoritative for the current files: typecheck/build/test pass, lint fails on formatting/import ordering.
