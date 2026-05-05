# G6 Explanation Front-end

Analysis board for the G6 Explanation product slice.

The first screen starts at game import. Submitting a Chess.com live-game URL
starts `POST /api/game-analysis/import` against the Python API, polls the
returned `status_url`, and maps completed `GameAnalysisSnapshot` moves into the
board UI. If URL import fails, the panel exposes a PGN paste fallback that uses
the same backend import boundary.

## Stack

- Bun
- Vite
- React
- TypeScript
- Tailwind CSS
- UltraChess React

## Run

```bash
bun install
bun run dev
```

The app runs at `http://127.0.0.1:5173/` by default.

The local `.env` sets the backend base URL to the default backend:

```bash
VITE_G6_API_BASE_URL=http://127.0.0.1:8001
```

## Checks

```bash
bun run typecheck
bun run lint
bun run test
bun run build
```
