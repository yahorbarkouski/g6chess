# Repository Guidance For Agents

This is the public Vite/React frontend for the G6 Explanation analysis board.
Start with `README.md` for the product boundary, local setup, API contract, and
project checks.

## Startup Path

Read these first:

1. `README.md`
2. `package.json`
3. `audit/README.md` only when you need dated audit context or feature plans

Do not treat every file in `audit/` as current instructions. Audit reports are
dated snapshots and plans; verify claims against the current source and checks
before acting on them.

## Active Areas

- App shell and routing: `src/App.tsx`, `src/lib/analysis-routing.ts`
- Import, polling, and persistence: `src/components/analysis/AnalysisWorkspace.tsx`,
  `src/components/analysis/AnalysisImportPanel.tsx`, `src/lib/api.ts`
- Backend response contracts: `src/types/api.ts`
- Frontend board model: `src/types/analysis.ts`
- Snapshot mapping: `src/lib/game-analysis-mapping.ts`
- Browser Stockfish runtime: `src/hooks/useStockfish.ts`,
  `src/components/analysis/StockfishAnalysisRuntime.tsx`
- UltraChess integration: `src/components/analysis/UltraAnalysisBoard.tsx`

## Checks

Run the relevant subset for your change, and prefer the full set before handing
off broad or release-facing work:

```bash
bun run typecheck
bun run lint
bun run test
bun run build
```

Use `bun audit` for dependency/security work. It may expose dev-dependency
advisories that are not covered by the default README checks.

## Documentation Update Rules

- API contract or mapping changes: update `src/types/api.ts`,
  `src/lib/game-analysis-mapping.ts`, tests, and any backend contract notes in
  `README.md` or active audit plans.
- Route/shareability changes: update `src/lib/analysis-routing.ts`, `vercel.json`
  when rewrites change, direct-load tests, and the README product boundary.
- Stockfish or UltraChess behavior changes: update focused tests around engine
  display, pre-analysis, and board mounting; check whether the performance audit
  index entry needs a new status note.
- New audit reports: add them to `audit/README.md` with a status label and the
  paired event log.

## Working Notes

The worktree may contain user edits. Do not revert unrelated changes. If an
audit file disagrees with the current source or command output, the current
source and fresh checks win.
