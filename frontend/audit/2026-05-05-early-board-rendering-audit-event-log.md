# Early Board Rendering Audit Event Log

Date: 2026-05-05
Repository: /Users/yahorbarkouski/g6explanation-frontend
Audit report: ./2026-05-05-early-board-rendering-audit.md

## Resume State

- Current phase: Complete.
- Artifact paths:
  - `audit/2026-05-05-early-board-rendering-audit.md`
  - `audit/2026-05-05-early-board-rendering-audit-event-log.md`
- Last completed dimension: Frontend/backend import-to-board timing and suggested contract fix.
- Next planned checks: Implement skeleton contract and add tests if requested.
- Known blockers: No live backend or Chess.com smoke was run. Backend repository had existing uncommitted changes.

## Timeline

### Step 001 - Initialize Audit

- Action: Read frontend repository guidance, README, package metadata, audit index, and audit skill templates; checked frontend git status.
- Reason: Establish instructions and scope before source tracing.
- Evidence inspected:
  - `README.md`
  - `package.json`
  - `audit/README.md`
  - `git status --short`
- Observations:
  - Frontend worktree was clean at audit start.
  - README documents `POST /api/game-analysis/import`, cached lookup, and polling through returned `status_url`.
- Outcome: Proceeded with frontend import/render trace.

### Step 002 - Trace Frontend Import And Polling

- Action: Read `AnalysisWorkspace`, import panel, API client, API types, snapshot mapper, route parsing, board wrapper, board hook, and workspace tests.
- Reason: Determine the exact state transition that mounts the board.
- Evidence inspected:
  - `src/components/analysis/AnalysisWorkspace.tsx`
  - `src/components/analysis/AnalysisImportPanel.tsx`
  - `src/lib/api.ts`
  - `src/types/api.ts`
  - `src/types/analysis.ts`
  - `src/lib/game-analysis-mapping.ts`
  - `src/lib/analysis-routing.ts`
  - `src/components/analysis/UltraAnalysisBoard.tsx`
  - `src/hooks/useAnalysisBoard.ts`
  - `src/components/analysis/AnalysisWorkspace.test.tsx`
- Observations:
  - `analysis` starts as null and is cleared on imports/routes.
  - Polling maps a snapshot only when at least one move has `context !== null`.
  - The app renders the import home while `analysis === null`.
  - The mapper filters to context-bearing moves and uses context FENs for board data.
- Outcome: Confirmed F-001 and F-004.

### Step 003 - Read Existing Audit Context

- Action: Searched existing audit files for import, snapshot, context, board, and Chess.com references.
- Reason: Check whether current source behavior had already been captured and whether backend path references existed.
- Evidence inspected:
  - `audit/2026-05-05-codebase-audit.md`
  - `audit/2026-05-05-routing-shareability-audit.md`
  - `audit/2026-05-05-book-lines-port-plan.md`
  - `audit/2026-05-05-g6explanation-modal-defense-plan.md`
- Observations:
  - Existing audits noted context-filtered frontend mapping.
  - Modal defense plan identified the sibling backend as the active `/api/game-analysis/import` implementation.
- Outcome: Expanded scope to the sibling backend for backend timing.

### Step 004 - Trace Backend Import And Job Start

- Action: Read sibling backend guidance, docs, git status, import service, import contracts, job service, game-analysis contracts, HTTP API, and import API tests.
- Reason: Determine what the backend has at Chess.com response time and what it returns to the frontend.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation/AGENTS.md`
  - `/Users/yahorbarkouski/g6explanation/README.md`
  - `/Users/yahorbarkouski/g6explanation/docs/product/game-analysis.md`
  - `/Users/yahorbarkouski/g6explanation/docs/development/game-analysis-integration.md`
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_imports/import_service.py`
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_imports/contracts.py`
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/job_service.py`
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/contracts.py`
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/visualization/http_api.py`
  - `/Users/yahorbarkouski/g6explanation/tests/g6explanation/game_imports/test_game_analysis_import_api.py`
- Observations:
  - Backend worktree had existing uncommitted files.
  - `GameImportService.start()` resolves the imported game and starts analysis, but the response includes only job pointer and source metadata.
  - `GameAnalysisService.start()` writes a pending snapshot with `total_plies` and no moves.
- Outcome: Confirmed the import response is too thin for immediate board render.

### Step 005 - Trace Backend Runner Snapshot Writes

- Action: Read runner, state store, Modal executor, Modal deployment entrypoint, and game-analysis API tests.
- Reason: Determine whether PGN-derived move data exists before context and whether Modal changes timing.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/analysis_runner.py`
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/state_store.py`
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/modal_job_executor.py`
  - `/Users/yahorbarkouski/g6explanation/deploy/modal_app.py`
  - `/Users/yahorbarkouski/g6explanation/tests/g6explanation/game_analysis/test_game_analysis_api.py`
  - `/Users/yahorbarkouski/g6explanation/tests/g6explanation/game_analysis/test_modal_job_executor.py`
- Observations:
  - `game_ply_requests()` derives FEN/SAN/UCI/clocks before context work.
  - Those derived fields are saved only after `_build_context()` completes.
  - Modal executor test asserts a spawned job leaves the snapshot pending.
- Outcome: Confirmed F-002.

### Step 006 - Check Public Context Guard

- Action: Read backend security admission code and public config.
- Reason: Verify whether the current frontend `include_context: true` dependency is compatible with production-shaped public API settings.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6explanation/src/g6explanation/security/admission.py`
  - `/Users/yahorbarkouski/g6explanation/deploy/modal_app.py`
  - `/Users/yahorbarkouski/g6explanation/tests/g6explanation/game_imports/test_game_analysis_import_api.py`
- Observations:
  - Modal API config disables public include-context requests.
  - Admission rejects `include_context: true` before Chess.com resolution.
  - Current frontend sends `include_context: true` for form and route imports.
- Outcome: Confirmed F-003.

### Step 007 - Inspect UI Tolerance For Skeleton-Only Moves

- Action: Read `MoveList`, `PositionInfo`, `StockfishAnalysisRuntime`, and missing-server-lines logic.
- Reason: Determine whether the existing workspace can tolerate moves without markers/timeline and identify secondary behavior.
- Evidence inspected:
  - `src/components/analysis/MoveList.tsx`
  - `src/components/analysis/PositionInfo.tsx`
  - `src/components/analysis/StockfishAnalysisRuntime.tsx`
  - `src/components/analysis/AnalysisWorkspace.tsx`
- Observations:
  - Move list can render moves without markers.
  - Position info can show current move with an empty/loading message when marker is missing.
  - Existing missing-server-lines logic would start browser Stockfish when no server lines are present unless gated.
- Outcome: Shaped frontend remediation guidance.

### Step 008 - Write Audit Artifacts

- Action: Created report and event log, then updated audit index.
- Reason: User requested a deep-dive report and suggested fix; repository guidance says new audit reports should be indexed.
- Evidence inspected:
  - `audit/README.md`
- Observations:
  - Existing audit index has an Active References table and Event Logs list.
- Outcome: Audit artifacts ready for handoff.

### Step 009 - Validate Documentation Edits

- Action: Checked status and ran the frontend lint gate.
- Reason: Validate documentation/index edits and identify unrelated worktree changes before handoff.
- Evidence inspected:
  - `git status --short`
  - `bun run lint`
- Observations:
  - Biome passed: 56 files checked, no fixes applied.
  - Current git status also showed modified product files under `src/` and `vercel.json` that were not touched by this audit patch. They were left alone.
- Outcome: Documentation artifacts validated; product checks beyond lint were not run because no product code was changed by this audit.

## Command Log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 001 | `git status --short` | Check frontend worktree | Passed | No frontend changes at start |
| 001 | `sed -n '1,260p' README.md` | Read frontend setup/product boundary | Passed | Import/poll contract documented |
| 001 | `sed -n '1,220p' package.json` | Read scripts/dependencies | Passed | Bun/Vite/React app |
| 001 | `sed -n '1,260p' audit/README.md` | Read audit index | Passed | New report should be indexed |
| 002 | `sed -n ... src/components/analysis/AnalysisWorkspace.tsx` | Trace import/poll/render | Passed | Main evidence for F-001 |
| 002 | `sed -n ... src/lib/game-analysis-mapping.ts` | Trace snapshot mapper | Passed | Main evidence for F-004 |
| 002 | `sed -n ... src/components/analysis/AnalysisWorkspace.test.tsx` | Check tests | Passed | Existing tests render after context fixture |
| 003 | `rg -n "total_plies|context_completed|moves|context" audit/*.md` | Search prior audits | Passed | Found relevant backend references |
| 004 | `git -C /Users/yahorbarkouski/g6explanation status --short` | Check backend worktree | Observed dirty | Existing backend changes left untouched |
| 004 | `nl -ba .../game_imports/import_service.py` | Trace import service | Passed | Import response lacks move skeleton |
| 004 | `nl -ba .../game_analysis/job_service.py` | Trace job start | Passed | Pending snapshot has no moves |
| 005 | `nl -ba .../game_analysis/analysis_runner.py` | Trace runner | Passed | PGN skeleton fields exist before context |
| 005 | `nl -ba .../game_analysis/modal_job_executor.py` | Trace Modal spawn | Passed | Spawned job returns pending |
| 006 | `nl -ba .../security/admission.py` | Trace public include-context guard | Passed | Confirmed include-context conflict |
| 007 | `nl -ba src/components/analysis/MoveList.tsx` | Check skeleton-only tolerance | Passed | Moves can render without markers |
| 009 | `bun run lint` | Validate documentation/index edits | Passed | Biome checked 56 files |

## Hypothesis Log

| ID | Hypothesis | Evidence For | Evidence Against | Status | Related Finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | The board starts rendering immediately after the Chess.com import response. | Import response has source metadata and route is updated. | `analysis` remains null until a poll has `context !== null`. | Dismissed | F-001 |
| H-002 | The frontend waits for backend full-game completion before rendering board. | Board waits for a polled snapshot. | It renders after first context-bearing move, not necessarily terminal completion. | Dismissed | F-001 |
| H-003 | The backend already has enough non-analysis data to render the board before context. | Chess.com resolver returns PGN; `game_ply_requests()` derives FEN/SAN/UCI/clocks. | That data is not exposed in import response or initial snapshot. | Confirmed | F-002 |
| H-004 | Public frontend can keep using full context for board hydration. | Local tests use `include_context: true`. | Public Modal config and admission guard reject public include-context requests. | Dismissed | F-003 |
| H-005 | Existing UI components can tolerate skeleton-only moves. | MoveList supports empty markers; PositionInfo supports missing marker. | Workspace gate and mapper prevent skeleton-only state today. | Confirmed | F-004 |

## Files And Docs Inspected

Frontend:

- `README.md`: product/import boundary and local setup.
- `package.json`: project checks and dependencies.
- `audit/README.md`: report indexing rules.
- `src/components/analysis/AnalysisWorkspace.tsx`: import, polling, board mount gate, workspace state.
- `src/components/analysis/AnalysisImportPanel.tsx`: import request construction.
- `src/lib/api.ts`: API calls.
- `src/types/api.ts`: import/snapshot contracts.
- `src/types/analysis.ts`: frontend board model.
- `src/lib/game-analysis-mapping.ts`: context-dependent mapper.
- `src/lib/analysis-routing.ts`: route and status URL helpers.
- `src/components/analysis/MoveList.tsx`: move-only render tolerance.
- `src/components/analysis/PositionInfo.tsx`: marker-missing render tolerance.
- `src/components/analysis/StockfishAnalysisRuntime.tsx`: browser Stockfish runtime trigger.
- `src/components/analysis/AnalysisWorkspace.test.tsx`: current import/render expectations.

Backend:

- `/Users/yahorbarkouski/g6explanation/AGENTS.md`: backend instructions.
- `/Users/yahorbarkouski/g6explanation/README.md`: backend product/API overview.
- `/Users/yahorbarkouski/g6explanation/docs/product/game-analysis.md`: async game-analysis API contract.
- `/Users/yahorbarkouski/g6explanation/docs/development/game-analysis-integration.md`: frontend polling guidance.
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_imports/import_service.py`: import orchestration.
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_imports/contracts.py`: import request/response metadata.
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_imports/chess_com_live_games.py`: Chess.com callback/archive resolver.
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/job_service.py`: initial snapshot and job start.
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/contracts.py`: snapshot and move contracts.
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/analysis_runner.py`: PGN traversal and snapshot updates.
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/modal_job_executor.py`: Modal spawn executor.
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/state_store.py`: Redis/in-memory snapshot persistence.
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/visualization/http_api.py`: API routes.
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/security/admission.py`: public include-context guard.
- `/Users/yahorbarkouski/g6explanation/deploy/modal_app.py`: public API and worker config.
- `/Users/yahorbarkouski/g6explanation/tests/g6explanation/game_imports/test_game_analysis_import_api.py`: import and admission tests.
- `/Users/yahorbarkouski/g6explanation/tests/g6explanation/game_analysis/test_game_analysis_api.py`: snapshot progression tests.
- `/Users/yahorbarkouski/g6explanation/tests/g6explanation/game_analysis/test_modal_job_executor.py`: pending Modal spawn behavior.

## Blockers And Deferred Checks

- No live Chess.com import smoke was run.
- No frontend browser visual QA was run.
- No typecheck/test/build gates were run because this audit only added documentation artifacts and did not change product behavior.
- Backend deployment state was not verified against production; the local backend worktree has existing uncommitted changes.
