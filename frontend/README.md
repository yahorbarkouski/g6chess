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

## Technology

| Technology | Purpose in the frontend |
| --- | --- |
| Bun 1.3 | Installs dependencies and runs development, contract, test, and build scripts. |
| React 19 and TypeScript 6 | Implement the analysis workspace with typed UI and API state. |
| Vite 8 | Provides the development server and production bundler. |
| Tailwind CSS 4 | Provides the styling system. |
| UltraChess and UltraChess React | Load the WebAssembly chess core, parse chess notation, enforce legal board state, and render the interactive board. |
| Stockfish.js 18 | Runs local position analysis in a browser Web Worker. |
| Framer Motion 12 | Handles interface transitions with reduced-motion support. |
| openapi-typescript 7 | Generates transport types from the backend OpenAPI document. |
| Vitest, Testing Library, and jsdom | Exercise mapping, state, interaction, performance, and component behavior. |
| Biome | Formats and lints TypeScript, TSX, and frontend configuration. |
| Vercel Analytics | Records frontend usage analytics in deployed builds. |

The production frontend is a static Vite build hosted by Vercel. It polls the
FastAPI backend for progressive snapshots while a game is being analyzed.

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

Enable Cloudflare Turnstile challenges for public imports:

```text
VITE_G6_TURNSTILE_SITE_KEY=...
```

## API contract

The backend owns the OpenAPI schema in `../contracts/openapi.json`. Frontend
transport types are generated into `src/generated/g6-api.ts`; UI mapping stays
in `src/lib/game-analysis-mapping.ts`.

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
