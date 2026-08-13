# Audit Event Log

Date: 2026-05-05
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Audit report: `./2026-05-05-codebase-audit.md`

## Resume State

- Current phase: Finalized audit artifacts.
- Artifact paths:
  - `audit/2026-05-05-codebase-audit.md`
  - `audit/2026-05-05-codebase-audit-event-log.md`
- Last completed dimension: Documentation/report consistency and final verification.
- Next planned checks: If continuing, implement remediations for F-001 through F-003 first.
- Known blockers: Backend service and deployed environment were not available; visual browser QA was not run.

## Timeline

### Step 001 - Initialize Audit

- Action: Read audit skill and templates, checked initial worktree, and located repo guidance.
- Reason: Establish required artifacts, constraints, and local instructions.
- Evidence inspected: `/Users/yahorbarkouski/.codex/skills/audit/SKILL.md`, report template, event-log template, `README.md`, `package.json`, `git status --short`.
- Observations: No `AGENTS.md` or docs directory was present. README describes Bun/Vite/React/TypeScript/Tailwind/UltraChess and the backend import boundary. Initial status showed modified product files.
- Outcome: Chose documentation-only output under `audit/`.

### Step 002 - Build Repository Map

- Action: Enumerated source files and read runtime entry points.
- Reason: Identify the main app flow before forming findings.
- Evidence inspected: `src/main.tsx`, `src/App.tsx`, `src/styles.css`, `vite.config.ts`, `tsconfig.json`, `README.md`, `package.json`.
- Observations: `App` renders `AnalysisWorkspace`; Vite uses React and Tailwind; Vitest uses jsdom; postinstall copies Stockfish assets into `public/stockfish`.
- Outcome: System map added to the report.

### Step 003 - Trace API and Type Contracts

- Action: Read API client, backend mirror types, frontend analysis types, mapping code, and API/mapping tests.
- Reason: Audit network boundaries, typed contracts, and snapshot conversion.
- Evidence inspected: `src/lib/api.ts`, `src/types/api.ts`, `src/types/analysis.ts`, `src/lib/game-analysis-mapping.ts`, `src/lib/api.test.ts`, `src/lib/game-analysis-mapping.test.ts`.
- Observations: Network JSON is cast directly to generic types. Snapshot mapping assumes nested fields after filtering moves with context. Tests cover expected payloads but not malformed payloads.
- Outcome: Created F-002.

### Step 004 - Trace Routing, Polling, and Persistence

- Action: Read route parsing and `AnalysisWorkspace` import/poll/share/localStorage logic.
- Reason: Verify how imported jobs are selected, stored, polled, and restored.
- Evidence inspected: `src/lib/analysis-routing.ts`, `src/components/analysis/AnalysisWorkspace.tsx`, `src/components/analysis/AnalysisWorkspace.test.tsx`.
- Observations: `status_url` comes from backend response or localStorage. Absolute HTTP(S) URLs are accepted by `apiUrl`. Stored jobs only validate `analysis_id` and `status_url` as strings.
- Outcome: Created F-002 and F-003.

### Step 005 - Trace Board State and Player Perspective

- Action: Read workspace board state, player metadata, engine-line display selection, move list, and position info.
- Reason: Audit correctness across board orientation, current ply, explanations, previews, and engine line coloring.
- Evidence inspected: `src/components/analysis/AnalysisWorkspace.tsx`, `src/components/analysis/MoveList.tsx`, `src/components/analysis/PositionInfo.tsx`, `src/components/analysis/EngineLinesView.tsx`, `src/components/analysis/preanalysis.test.ts`, `src/components/analysis/PositionInfo.test.tsx`.
- Observations: Imported `AnalysisResponse.player_side` is always `"white"`, but workspace uses it for orientation and perspective-sensitive behavior. Tests do not cover black-side import perspective.
- Outcome: Created F-004 and noted a follow-up on shared in-progress `?ply=` behavior.

### Step 006 - Trace Browser Stockfish Runtime

- Action: Read Stockfish hook, UCI parser, runtime store, board arrow integration, and related tests.
- Reason: Audit local engine lifecycle, performance, error handling, and UI fallback behavior.
- Evidence inspected: `src/hooks/useStockfish.ts`, `src/lib/stockfish-uci.ts`, `src/components/analysis/StockfishAnalysisRuntime.tsx`, `src/components/analysis/UltraAnalysisBoard.tsx`, `src/hooks/useStockfish.test.ts`, `src/components/analysis/AnalysisWorkspace.performance.test.tsx`.
- Observations: Worker construction and runtime messages have no error state. Browser engine snapshots are isolated through an external store and tests cover display throttling/performance paths.
- Outcome: Created F-006.

### Step 007 - Search for Risk Patterns

- Action: Searched for unsafe or high-risk constructs and environment/config files.
- Reason: Catch broad issues not found by source tracing.
- Evidence inspected: `rg` results for `fetch`, `new Worker`, `localStorage`, `catch`, `biome-ignore`, `dangerouslySetInnerHTML`, `eval`, `new Function`, `VITE_`, `status_url`; `.gitignore`, `.env.example`, `biome.json`.
- Observations: No `dangerouslySetInnerHTML`, `eval`, or `new Function` usage found. `.gitignore` excludes `.env`, build outputs, and Stockfish public assets. Biome ignores `public/stockfish`.
- Outcome: Confirmed boundary and engine findings; no XSS finding created.

### Step 008 - Run Typecheck, Lint, and Tests

- Action: Ran project verification commands.
- Reason: Establish baseline health and avoid reporting issues contradicted by tests.
- Evidence inspected: Command outputs for `bun run typecheck`, `bun run lint`, `bun run test`.
- Observations: Typecheck passed; Biome checked 61 files; Vitest passed 10 files and 44 tests.
- Outcome: Recorded positive verification baseline.

### Step 009 - Run Production Build and Asset Size Check

- Action: Ran `bun run build`, checked `dist` and Stockfish asset sizes.
- Reason: Validate production build and quantify deployment size risk.
- Evidence inspected: Vite build output and `du -sh dist dist/stockfish/stockfish-18-single.wasm dist/stockfish/stockfish-18-single.js`.
- Observations: Build passed, Vite warned that the main JS chunk is 520.67 kB minified, `dist` is 113 MB, and Stockfish wasm is 112 MB.
- Outcome: Created F-005.

### Step 010 - Run Dependency Audit

- Action: Ran `bun audit` and listed top-level installed dependencies.
- Reason: Cover security advisories and dependency state.
- Evidence inspected: `bun audit`, `bun pm ls --depth 0`, `du -sh node_modules`.
- Observations: `bun audit` failed with 3 `happy-dom <20.0.0` advisories through `vitest`: one critical and two high. Top-level installed versions include `vitest@4.1.5`, `jsdom@29.1.1`, `vite@8.0.10`, and `stockfish@18.0.7`.
- Outcome: Created F-001.

### Step 011 - Write Audit Artifacts

- Action: Created `audit/2026-05-05-codebase-audit.md` and this event log.
- Reason: Leave durable report and chronological inspection record.
- Evidence inspected: All prior notes and command results.
- Observations: Findings were grouped into confirmed findings plus risks/follow-ups, with remediation roadmap and verification guidance.
- Outcome: Required artifacts created.

### Step 012 - Final Artifact Verification

- Action: Re-read the new artifacts and reran repository lint after docs were created.
- Reason: Check consistency and ensure docs-only output did not break the available repo gate.
- Evidence inspected: `sed -n` reads of both audit files, `bun run lint`, final `git status --short`.
- Observations: Biome passed after artifact creation. Final status showed the two new codebase-audit docs plus two unrelated untracked Cloudflare rate-limit security-plan docs under `audit/`; those unrelated files were left untouched.
- Outcome: Audit complete.

## Command Log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 001 | `sed -n '1,220p' /Users/yahorbarkouski/.codex/skills/audit/SKILL.md` | Read audit instructions | Passed | Required report and event log |
| 001 | `git status --short` | Initial dirty-worktree check | Passed | Initially showed modified product files |
| 001 | `rg --files -g 'AGENTS.md' -g 'README*' -g 'package.json' -g 'pnpm-lock.yaml' -g 'yarn.lock' -g 'package-lock.json' -g 'tsconfig*.json' -g 'vite.config.*' -g 'next.config.*' -g 'docs/**'` | Find guidance and metadata | Passed | Found README, package, Vite and TS configs; no docs directory |
| 001 | `find /Users/yahorbarkouski/.codex/skills/audit/references -maxdepth 1 -type f -print` | Locate templates | Passed | Found report and event-log templates |
| 002 | `sed -n '1,260p' README.md` | Read project docs | Passed | Import flow and checks documented |
| 002 | `sed -n '1,260p' package.json` | Read package metadata | Passed | Bun scripts and dependencies identified |
| 002 | `rg --files src test tests public .github | sed -n '1,240p'` | Inventory files | Partial | Missing `test`, `tests`, `.github`; listed `src` and `public` files |
| 003 | `nl -ba src/lib/api.ts | sed -n '1,260p'` | Read API boundary with line numbers | Passed | Supported F-002 and F-003 |
| 003 | `nl -ba src/types/api.ts | sed -n '1,620p'` | Read backend mirror types | Passed | Contract map |
| 003 | `nl -ba src/types/analysis.ts | sed -n '1,260p'` | Read frontend analysis model | Passed | Contract map |
| 003 | `nl -ba src/lib/game-analysis-mapping.ts | sed -n '1,520p'` | Read snapshot mapper | Passed | Supported F-002 and F-004 |
| 003 | `nl -ba src/lib/api.test.ts | sed -n '1,360p'` | Read API tests | Passed | Positive-path coverage |
| 004 | `nl -ba src/lib/analysis-routing.ts | sed -n '1,320p'` | Read route parsing | Passed | Share/canonical path behavior |
| 004 | `nl -ba src/components/analysis/AnalysisWorkspace.tsx | sed -n '1,1760p'` | Read workspace flow | Passed | Supported F-002, F-003, F-004 |
| 005 | `nl -ba src/components/analysis/AnalysisImportPanel.tsx | sed -n '1,620p'` | Read import UI | Passed | Request construction and validation |
| 005 | `nl -ba src/components/analysis/MoveList.tsx | sed -n '1,360p'` | Read move list | Passed | Marker/pairing behavior |
| 005 | `nl -ba src/components/analysis/PositionInfo.tsx | sed -n '1,860p'` | Read explanation UI | Passed | Preview and line-card behavior |
| 005 | `nl -ba src/components/analysis/EngineLinesView.tsx | sed -n '1,360p'` | Read engine/book line UI | Passed | Engine-line display behavior |
| 006 | `nl -ba src/hooks/useStockfish.ts | sed -n '1,620p'` | Read engine hook | Passed | Supported F-005 and F-006 |
| 006 | `nl -ba src/components/analysis/StockfishAnalysisRuntime.tsx | sed -n '1,260p'` | Read engine runtime store | Passed | Supported F-006 |
| 006 | `nl -ba src/lib/stockfish-uci.ts | sed -n '1,380p'` | Read UCI parser | Passed | Engine conversion behavior |
| 006 | `nl -ba src/components/analysis/UltraAnalysisBoard.tsx | sed -n '1,360p'` | Read board wrapper | Passed | Drag/drop and arrow behavior |
| 007 | `rg -n "TODO|FIXME|XXX|HACK|biome-ignore|eslint-disable|dangerouslySetInnerHTML|innerHTML|eval\\(|new Function|localStorage|sessionStorage|fetch\\(|new Worker|postMessage|setInterval|setTimeout|AbortController|catch \\{|as GameAnalysisSnapshot|as unknown|as any" src package.json README.md vite.config.ts` | Broad risk search | Passed | No dangerous HTML/eval use found |
| 007 | `rg -n "VITE_|import.meta.env|process.env|API_BASE_URL|stockfish|public/stockfish|status_url|source_url|rights_basis" src README.md package.json` | Env and integration search | Passed | Confirmed API and Stockfish boundaries |
| 007 | `rg -n "describe\\(|it\\(" src -g '*.test.ts' -g '*.test.tsx'` | Test inventory | Passed | 44 tests found |
| 007 | `find . -maxdepth 2 -type f \\( -name 'biome.json' -o -name 'biome.jsonc' -o -name '.env*' -o -name '.gitignore' -o -name 'bun.lock*' -o -name 'package-lock.json' -o -name 'yarn.lock' -o -name 'pnpm-lock.yaml' \\) -print` | Config inventory | Passed | Found `.env`, `.env.example`, `.gitignore`, `biome.json`, `bun.lock` |
| 008 | `bun run typecheck` | TypeScript gate | Passed | `tsc -b` completed |
| 008 | `bun run lint` | Biome gate | Passed | 61 files checked |
| 008 | `bun run test` | Vitest gate | Passed | 10 files, 44 tests |
| 009 | `bun run build` | Production build | Passed with warning | Main JS chunk over 500 kB |
| 009 | `du -sh dist dist/stockfish/stockfish-18-single.wasm dist/stockfish/stockfish-18-single.js 2>/dev/null` | Build output size | Passed | `dist` 113 MB, wasm 112 MB, worker JS 24 KB |
| 010 | `bun audit` | Dependency advisory scan | Failed | 3 `happy-dom` advisories via `vitest` |
| 010 | `bun pm ls --depth 0` | Top-level dependency versions | Passed | Listed installed versions |
| 010 | `du -sh node_modules 2>/dev/null` | Dependency footprint | Passed | `node_modules` 533 MB |
| 011 | `mkdir -p audit` | Create artifact directory | Passed | New docs-only directory |
| 012 | `sed -n '1,260p' audit/2026-05-05-codebase-audit.md` | Re-read report | Passed | Consistency check |
| 012 | `sed -n '1,340p' audit/2026-05-05-codebase-audit-event-log.md` | Re-read event log | Passed | Consistency check |
| 012 | `bun run lint` | Final docs-aware available gate | Passed | Biome passed after docs creation |
| 012 | `git status --short` | Final status | Passed | New codebase-audit docs plus unrelated untracked Cloudflare plan docs |

## Hypothesis Log

| ID | Hypothesis | Evidence For | Evidence Against | Status | Related Finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | The frontend has no runtime API validation at network/persistence boundaries. | Direct JSON casts in `api.ts`; partial stored-job validation; mapper assumes nested fields. | Strong TypeScript types and positive fixtures exist. | Confirmed | F-002 |
| H-002 | Polling can leave the API origin because `status_url` is trusted. | `apiUrl` passes absolute HTTP(S) through; response/localStorage supplies `status_url`. | Browser CORS limits response reads; no credentials configured. | Confirmed | F-003 |
| H-003 | Black-side imported games are shown from white perspective. | Mapper hardcodes `player_side: "white"`; workspace uses it for orientation and perspective. | No backend perspective field found in frontend metadata. | Confirmed | F-004 |
| H-004 | Browser Stockfish creates deployment and runtime reliability risk. | 112 MB wasm in build output; no worker error state. | Worker is created lazily only when browser analysis is needed. | Confirmed | F-005, F-006 |
| H-005 | Current tests fail or typecheck is broken. | None after running gates. | Typecheck, lint, and all tests pass. | Dismissed | None |
| H-006 | Dependency audit has actionable security findings. | `bun audit` reports critical/high `happy-dom` advisories via `vitest`. | Runtime app does not use `happy-dom` directly. | Confirmed | F-001 |
| H-007 | The UI uses obviously unsafe HTML injection. | Search included `dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function`. | No matching unsafe constructs found in source. | Dismissed | None |

## Files and Docs Inspected

### Repository Guidance and Config

- `README.md`: Local run/check commands and product flow.
- `package.json`: Scripts, dependencies, Stockfish postinstall.
- `bun.lock`: Dependency lock present.
- `vite.config.ts`: Vite, React, Tailwind, Vitest jsdom setup.
- `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`: TypeScript project references.
- `biome.json`: Lint/format config and ignored generated assets.
- `.gitignore`, `.env.example`: Local env and generated asset ignore policy.

### Runtime Entry and Styling

- `src/main.tsx`: React root mount.
- `src/App.tsx`: Application shell.
- `src/styles.css`: Tailwind, fonts, board wrapper styles, reduced motion.

### API, Routing, and Contracts

- `src/lib/api.ts`: Fetch helpers, API base URL, error handling.
- `src/lib/analysis-routing.ts`: URL parsing and canonical share paths.
- `src/types/api.ts`: Backend response/request mirror types.
- `src/types/analysis.ts`: Frontend board/workspace model.
- `src/lib/game-analysis-mapping.ts`: Snapshot-to-analysis conversion.
- `src/lib/document-title.ts`: Source metadata title formatting.

### Analysis Workspace and UI

- `src/components/analysis/AnalysisWorkspace.tsx`: Import, polling, board state, engine-line selection, storage.
- `src/components/analysis/AnalysisImportPanel.tsx`: URL/PGN import form and request construction.
- `src/components/analysis/MoveList.tsx`: Move pairing and marker display.
- `src/components/analysis/PositionInfo.tsx`: Explanation rendering, line-card previews.
- `src/components/analysis/EngineLinesView.tsx`: Engine and book lines.
- `src/components/analysis/UltraAnalysisBoard.tsx`: UltraChess wrapper.
- `src/components/analysis/AnalysisNavigationBar.tsx`: Move navigation controls.
- `src/components/analysis/AnalysisSettingsPopover.tsx`: Board settings controls.
- `src/components/analysis/BoardSidebar.tsx`, `PlayerBar.tsx`, `WorkspaceFooter.tsx`, `DiscoveryLine.tsx`, `EvalBar.tsx`: Supporting workspace UI.

### Chess and Engine

- `src/lib/chess.ts`: FEN/move helpers, material, eval formatting.
- `src/lib/stockfish-uci.ts`: UCI info parsing and line conversion.
- `src/hooks/useStockfish.ts`: Worker lifecycle, cache, pre-analysis queue.
- `src/components/analysis/StockfishAnalysisRuntime.tsx`: External store and selectors.
- `public/stockfish/stockfish-18-single.js`, `public/stockfish/stockfish-18-single.wasm`: Generated engine assets were size-checked.

### Tests and Fixtures

- `src/lib/api.test.ts`: API request tests.
- `src/lib/game-analysis-mapping.test.ts`: Mapper tests.
- `src/lib/document-title.test.ts`: Title tests.
- `src/hooks/useStockfish.test.ts`: Engine display gate tests.
- `src/components/analysis/AnalysisWorkspace.test.tsx`: Import/routing/workspace tests.
- `src/components/analysis/AnalysisWorkspace.performance.test.tsx`: Board render/performance baseline.
- `src/components/analysis/preanalysis.test.ts`: Browser engine selection/pre-analysis tests.
- `src/components/analysis/AnalysisImportPanel.test.tsx`: Import panel tests.
- `src/components/analysis/PositionInfo.test.tsx`: Explanation line-card tests.
- `src/components/analysis/EngineLinesView.test.tsx`: Book lines tests.
- `src/data/mock-analysis.ts`: Workspace fixture data.
- `src/test/setup.ts`: Test environment setup.

## Blockers and Deferred Checks

- Backend integration was not run. Exact malformed payload behavior should be verified with backend contract tests once the API is available.
- Browser visual QA was not run. Layout, board rendering, and engine fallback UX should be checked in a real browser after any remediation.
- No docs-specific lint command exists. `bun run lint` was used as the available repository gate after docs were added.
- `bun audit` failed on dependency advisories. This is recorded as F-001 and remains unresolved by this audit.
