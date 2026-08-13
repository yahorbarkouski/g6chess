# Engine Line Preview Regression Audit

Date: 2026-05-05
Repository: `/Users/yahorbarkouski/g6explanation-frontend`
Auditor: Codex
Related event log: `./2026-05-05-engine-line-preview-regression-audit-event-log.md`

## Executive Summary

The current frontend replaces the selected move's engine-line panel with fresh browser Stockfish lines whenever an engine-line chip is previewed. That is why clicking into the middle of a displayed line changes the visible line list after the browser engine catches up.

The older `g6chess-frontend` did not do that. It still analyzed the previewed FEN for eval/discovery support, but its engine-lines panel stayed anchored to `serverEngineLines ?? browserEngineLines` unless discovery mode was active. The current port added an explicit `previewActive` branch that prefers browser lines, which breaks the stable "look inside this line without changing the line list" behavior.

## Scope

- Included: current `AnalysisWorkspace` line-preview flow, current `useAnalysisBoard`, current Stockfish runtime selector, old `g6chess-frontend` workspace/engine-panel implementation, and targeted tests around browser-analysis reasons.
- Excluded: visual browser reproduction, backend engine-line payload generation, and unrelated mobile/layout changes already present in the dirty worktree.
- Repository instructions followed: no product code was changed during this audit.
- Constraints or blockers: both this repo and `/Users/yahorbarkouski/g6chess-frontend` have unrelated dirty worktrees, so old behavior was checked against `g6chess-frontend` HEAD as well as the working copy.

## System Map

- `src/hooks/useAnalysisBoard.ts` owns transient board states:
  - `preview`: click a SAN chip inside an engine/book/explanation line.
  - `discovery`: user continues from a preview or plays a custom board move.
  - `displayFen`: preview/discovery FEN if active, otherwise selected mainline move FEN.
- `src/components/analysis/AnalysisWorkspace.tsx` owns selected mainline ply, computes `analysisFen`, chooses server/browser engine lines, and renders `EngineLinesView`.
- `src/components/analysis/StockfishAnalysisRuntime.tsx` runs browser Stockfish for `analysisFen` when enabled and publishes snapshots through an external store.
- `EngineLinesView` renders line chips and calls `onPreview(rootFen, moves, step)` when a chip is clicked.

## Findings Overview

| ID | Severity | Category | Confidence | Title | Fix Priority |
| --- | --- | --- | --- | --- | --- |
| F-001 | High | correctness | High | Previewed engine-line positions replace the selected move's engine lines | Immediate |

## Confirmed Findings

### F-001: Previewed Engine-Line Positions Replace The Selected Move's Engine Lines

- Severity: High
- Category: correctness
- Confidence: High
- Status: Confirmed
- Evidence:
  - Current `AnalysisWorkspace` sets `analysisFen = board.discovery || board.preview ? displayFen : currentFen`.
  - Current `browserAnalysisReasonForPosition` returns `"preview"` whenever `previewActive` is true.
  - Current `EngineLinesSlot` chooses `previewActive ? (browserEngineLines ?? serverEngineLines) : ...`.
  - Current `useBrowserEngineLines` returns browser lines when the Stockfish snapshot FEN matches `analysisFen`.
  - Old `g6chess-frontend` HEAD chooses `if (discovery) return browserEngineLines; return serverEngineLines ?? browserEngineLines`, with no preview branch.
- Impact: clicking a move in the middle of an engine line initially previews the position, then the sidebar line list morphs to the best lines from that previewed FEN. This removes the line the user was inspecting and changes the surrounding UI without an explicit navigation or discovery action.
- Reproduction or experiment: source trace confirms the state transition:
  1. Click line chip in `EngineLinesView`.
  2. `useAnalysisBoard.handlePreview` sets `preview`.
  3. `AnalysisWorkspace` changes `analysisFen` to `displayFen`.
  4. `StockfishAnalysisRuntime` analyzes the previewed FEN.
  5. `EngineLinesSlot` prefers `browserEngineLines` because `previewActive` is true.
- Recommended fix: keep preview analysis available for board/eval, but do not let preview mode replace the engine-lines panel while server lines exist. Mirror the old selection rule:

```ts
const engineLines = discoveryActive
  ? browserEngineLines
  : (serverEngineLines ?? browserEngineLines);
```

Optional clarity improvement: rename `previewActive` usage around line selection or extract a helper, because "analyze preview FEN" and "display preview FEN's best lines" are separate product decisions.
- Verification:
  - Add a regression test where a selected move has server engine lines, a preview is active, and browser lines exist for the preview FEN; assert the rendered engine lines remain the server lines.
  - Keep the existing behavior for discovery and missing server-line positions.

## Risks and Follow-Ups

- The current unit tests only assert that browser Stockfish runs for preview mode. They do not assert what the sidebar should display once browser lines arrive.
- Current `playerSideForLines` also treats preview as a display-line context. That is less likely to cause the reported line replacement, but should be revisited after the line-source rule is fixed.

## Experiments and Checks

| Command or experiment | Purpose | Result | Notes |
| --- | --- | --- | --- |
| `rg -n "previewActive|browserEngineLines|EngineLinesSlot" src/components/analysis/AnalysisWorkspace.tsx` | Locate current line-source logic | Passed | Found preview branch that prefers browser lines. |
| `git -C /Users/yahorbarkouski/g6chess-frontend show HEAD:components/analysis/analysis-workspace-engine-panels.tsx` | Verify old behavior independent of dirty worktree | Passed | Old HEAD has no preview branch in display engine-line selection. |
| Source trace through `useAnalysisBoard`, `AnalysisWorkspace`, and `StockfishAnalysisRuntime` | Confirm event/state path | Passed | Click preview changes `analysisFen`, runtime analyzes it, slot swaps to browser lines. |

## Remediation Roadmap

### Immediate

Change `EngineLinesSlot` line-source selection so preview mode does not prefer browser lines over server lines.

### Near-Term

Add a targeted regression test for "preview with server lines keeps selected move's visible engine lines stable."

### Strategic

Make the line-source policy explicit, for example a helper named `selectDisplayedEngineLines`, so preview/discovery behavior cannot drift accidentally.

## Residual Risk

I did not run a browser-level visual reproduction during this audit. The bug is source-confirmed, and the old/current behavior difference is isolated to the line-source selection policy.
