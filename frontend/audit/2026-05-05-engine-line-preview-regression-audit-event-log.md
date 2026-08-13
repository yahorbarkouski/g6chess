# Engine Line Preview Regression Audit Event Log

Date: 2026-05-05
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Audit report: `./2026-05-05-engine-line-preview-regression-audit.md`

## Resume State

- Current phase: complete
- Artifact paths:
  - `audit/2026-05-05-engine-line-preview-regression-audit.md`
  - `audit/2026-05-05-engine-line-preview-regression-audit-event-log.md`
- Last completed dimension: source-level correctness comparison between current frontend and old `g6chess-frontend`
- Next planned checks: apply the one-branch fix and add a regression test if product changes are requested
- Known blockers: none for diagnosis

## Timeline

### Step 001 - Initialize Audit

- Action: Read audit skill instructions, listed repository files, and checked git status.
- Reason: User asked for a deep dive into a regression around engine-line previews.
- Evidence inspected: `README.md`, `package.json`, `git status --short`, `rg --files`.
- Observations: Current repo has a dirty worktree with unrelated UI/layout changes. Existing `audit/` artifacts are present.
- Outcome: Continued with source-only investigation and avoided product edits.

### Step 002 - Trace Current Preview Path

- Action: Read current `AnalysisWorkspace`, `EngineLinesView`, `DiscoveryLine`, `StockfishAnalysisRuntime`, and `useAnalysisBoard`.
- Reason: Identify where line-chip clicks become board state and where browser Stockfish output is displayed.
- Evidence inspected:
  - `src/components/analysis/EngineLinesView.tsx`
  - `src/hooks/useAnalysisBoard.ts`
  - `src/components/analysis/AnalysisWorkspace.tsx`
  - `src/components/analysis/StockfishAnalysisRuntime.tsx`
- Observations: Line chips call `onPreview`; preview changes `displayFen`; `analysisFen` becomes `displayFen`; runtime analyzes preview FEN; `EngineLinesSlot` prefers browser lines when `previewActive`.
- Outcome: Confirmed plausible current root cause.

### Step 003 - Compare Old G6 Frontend

- Action: Searched and read old `g6chess-frontend` workspace files.
- Reason: Validate the behavior the user described from the previous frontend.
- Evidence inspected:
  - `/Users/yahorbarkouski/g6chess-frontend/components/analysis/analysis-workspace-shell.tsx`
  - `/Users/yahorbarkouski/g6chess-frontend/components/analysis/analysis-workspace-layout.tsx`
  - `/Users/yahorbarkouski/g6chess-frontend/components/analysis/analysis-workspace-engine-panels.tsx`
  - `/Users/yahorbarkouski/g6chess-frontend/hooks/use-analysis-board.ts`
- Observations: Old `shouldAnalyzeBrowserLines` includes preview, but old `EngineLinesSection` only uses browser lines for discovery or as fallback when server lines are absent.
- Outcome: Confirmed old frontend separated preview analysis from visible line-list replacement.

### Step 004 - Verify Old Behavior Against HEAD

- Action: Used `git -C /Users/yahorbarkouski/g6chess-frontend show HEAD:...` on the key files.
- Reason: The old frontend worktree is dirty; HEAD avoids relying on unrelated local edits.
- Evidence inspected: old HEAD `analysis-workspace-engine-panels.tsx` and `analysis-workspace-shell.tsx`.
- Observations: HEAD matches the important behavior: preview analysis can run, but display line selection remains `serverEngineLines ?? browserEngineLines` unless discovery is active.
- Outcome: Strengthened confidence that the current frontend drifted from old behavior.

### Step 005 - Inspect Current Test Coverage

- Action: Read `AnalysisWorkspace.test.tsx` and `preanalysis.test.ts`.
- Reason: Check whether a test should have caught this.
- Evidence inspected:
  - `src/components/analysis/AnalysisWorkspace.test.tsx`
  - `src/components/analysis/preanalysis.test.ts`
- Observations: Tests assert browser analysis is triggered for preview mode, but they do not assert that visible server engine lines remain stable while preview is active.
- Outcome: Identified missing regression coverage.

## Command Log

| Step | Command | Purpose | Result | Notes |
| --- | --- | --- | --- | --- |
| 001 | `sed -n '1,220p' /Users/yahorbarkouski/.codex/skills/audit/SKILL.md` | Load audit workflow | Passed | Followed source-grounded audit path. |
| 001 | `pwd && rg --files` | Map repo files | Passed | Found analysis components and prior audits. |
| 001 | `git status --short` | Identify dirty worktree | Passed | Current repo has unrelated modified files. |
| 002 | `nl -ba src/components/analysis/AnalysisWorkspace.tsx` | Trace current workspace | Passed | Found `analysisFen` and `EngineLinesSlot` behavior. |
| 002 | `nl -ba src/hooks/useAnalysisBoard.ts` | Trace preview state | Passed | Found `handlePreview` and `displayFen`. |
| 002 | `nl -ba src/components/analysis/StockfishAnalysisRuntime.tsx` | Trace browser engine store | Passed | Found snapshot publication and selector use. |
| 003 | `rg -n "EngineLinesView|preview|analysisFen|Stockfish" /Users/yahorbarkouski/g6chess-frontend/...` | Locate old implementation | Passed | Found old workspace and engine panel files. |
| 003 | `nl -ba /Users/yahorbarkouski/g6chess-frontend/components/analysis/analysis-workspace-engine-panels.tsx` | Inspect old line-source logic | Passed | Confirmed no preview branch in display selection. |
| 004 | `git -C /Users/yahorbarkouski/g6chess-frontend show HEAD:components/analysis/analysis-workspace-engine-panels.tsx` | Verify old HEAD behavior | Passed | Confirmed working-copy dirtiness does not affect conclusion. |
| 005 | `rg -n "previewActive|browserEngineLines|EngineLinesSlot|browserAnalysisReasonForPosition"` | Inspect current coverage and references | Passed | Found test only covers analysis reason, not display line stability. |

## Hypothesis Log

| ID | Hypothesis | Evidence For | Evidence Against | Status | Related Finding |
| --- | --- | --- | --- | --- | --- |
| H-001 | Current click handler mutates selected mainline ply. | User sees UI change after click. | `handlePreview` only sets preview; `currentPly` is unchanged. | Dismissed |  |
| H-002 | Current preview FEN intentionally starts browser Stockfish and the sidebar displays its lines. | `analysisFen` uses preview `displayFen`; `browserAnalysisReasonForPosition` returns `"preview"`; `EngineLinesSlot` prefers browser lines during preview. | None. | Confirmed | F-001 |
| H-003 | Old frontend did not analyze preview positions at all. | Could explain stable line list. | Old `shouldAnalyzeBrowserLines` includes `board.preview`. | Dismissed |  |
| H-004 | Old frontend analyzed preview positions but did not replace visible server lines during preview. | Old `EngineLinesSection` uses browser lines only for discovery or server fallback. | None. | Confirmed | F-001 |

## Files and Docs Inspected

Current frontend:

- `README.md`: repo setup and stack.
- `package.json`: scripts and dependencies.
- `src/components/analysis/AnalysisWorkspace.tsx`: selected ply, `analysisFen`, Stockfish runtime, line-source selection.
- `src/components/analysis/EngineLinesView.tsx`: line chip click handler.
- `src/components/analysis/DiscoveryLine.tsx`: discovery display behavior.
- `src/components/analysis/StockfishAnalysisRuntime.tsx`: browser Stockfish store and selector.
- `src/hooks/useAnalysisBoard.ts`: preview/discovery state.
- `src/components/analysis/AnalysisWorkspace.test.tsx`: workspace import tests.
- `src/components/analysis/preanalysis.test.ts`: browser-analysis reason tests.

Old G6 frontend:

- `/Users/yahorbarkouski/g6chess-frontend/components/analysis/analysis-workspace-shell.tsx`: old `analysisFen` and `shouldAnalyzeBrowserLines`.
- `/Users/yahorbarkouski/g6chess-frontend/components/analysis/analysis-workspace-layout.tsx`: old sidebar composition.
- `/Users/yahorbarkouski/g6chess-frontend/components/analysis/analysis-workspace-engine-panels.tsx`: old `EngineLinesSection`.
- `/Users/yahorbarkouski/g6chess-frontend/hooks/use-analysis-board.ts`: old preview/discovery hook behavior.

## Blockers and Deferred Checks

- No browser QA was run. The source trace is sufficient for diagnosis, but a UI test or browser reproduction should be run after applying the fix.
