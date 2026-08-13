# [g6](https://g6chess.com): frontend

https://github.com/user-attachments/assets/983c9ebf-1496-47e1-a61a-580f2b8c7dca

This directory contains the React analysis board for g6. Players can paste a
Chess.com game, Lichess game, Lichess study chapter, or PGN and follow the
review as the backend completes each move.

## Features

- Chess.com, Lichess, Lichess study, and PGN import.
- Shareable routes with selected-move state.
- Move list, evaluation bar, player clocks, and opening information.
- Stockfish line previews drawn on the board.
- Progressive move labels and explanations from the analysis API.
- UltraChess React board with animated pieces and canvas arrows.
- Browser Stockfish for exploring additional positions.

The board renders from the PGN-derived game skeleton immediately after import.
Deeper analysis fills the same workspace without replacing the game state.

## Stack

- Bun
- Vite
- React
- TypeScript
- Tailwind CSS
- UltraChess React

## Run

```sh
bun install --frozen-lockfile
bun run dev
```

Open `http://127.0.0.1:5173`.

## Configuration

Point the frontend at a local backend:

```text
VITE_G6_API_BASE_URL=http://127.0.0.1:8001
```

Enable Cloudflare Turnstile for public imports:

```text
VITE_G6_TURNSTILE_SITE_KEY=...
```

## API contract

The backend owns the OpenAPI schema in `../contracts/openapi.json`. Frontend
transport types are generated into `src/generated/g6-api.ts`; UI mapping stays
in `src/lib/analysis-mapping.ts`.

The main frontend flow uses:

- `POST /api/game-analysis/import`
- `GET /api/game-analysis/import/chess-com/live/{externalGameId}`
- `GET /api/game-analysis/import/lichess/{externalGameId}`
- `GET /api/game-analysis/import/lichess/study/{studyId}/{chapterId}`
- the `status_url` returned by an import request

Normal requests use compact snapshots with `include_context=false`. Browser
Stockfish can analyze positions beyond the server snapshot.

## Checks

```sh
bun run typecheck
bun run lint
bun run test
bun run build
```

`bun install` copies the Stockfish worker files into `public/stockfish/`.
