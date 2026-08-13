# [g6](https://g6chess.com): Free Chess Analysis

https://github.com/user-attachments/assets/983c9ebf-1496-47e1-a61a-580f2b8c7dca

Paste a Chess.com game, Lichess game, Lichess study chapter, or PGN. g6 opens
the board and builds a move-by-move review with engine lines, move labels,
opening information, and plain-English explanations.

[Try g6](https://g6chess.com)

## Game review

- Follow every move on an interactive board.
- Jump between critical moments from the move list.
- Preview Stockfish lines directly on the board.
- Compare the played move with stronger alternatives.
- See opening names, book moves, evaluation, and clock context.
- Read explanations written for the player's level.
- Share Chess.com, Lichess, study, and analysis routes.

The board appears as soon as the game imports. Labels and explanations arrive
as the backend finishes each part of the analysis.

## How analysis runs

1. The backend imports the game and reconstructs every legal position.
2. Stockfish evaluates the played move and its alternatives.
3. Maia estimates which moves players at a similar rating tend to choose.
4. Deterministic rules assign quality, significance, and beauty labels.
5. GPT-5.6 Terra writes explanations for selected moves.
6. The explanation verifier checks move references and chess claims.
7. Redis stores partial results while the frontend polls for updates.

## Repository

| Path | Contents |
| --- | --- |
| [`frontend/`](frontend/README.md) | React, Vite, UltraChess, the analysis workspace, and browser Stockfish |
| [`backend/`](backend/README.md) | FastAPI, Stockfish, Maia, Redis snapshots, imports, explanations, and verification |
| [`contracts/`](contracts/README.md) | OpenAPI schema and generated frontend transport types |
| [`tools/`](tools) | Repository-wide checks |

Backend Pydantic models define the API contract. The repository exports them to
[`contracts/openapi.json`](contracts/openapi.json) and generates matching
TypeScript types for the frontend.

## Technology

| Technology | Purpose in g6 |
| --- | --- |
| Bun 1.3 | Installs frontend dependencies and runs repository scripts. |
| React 19 and TypeScript 6 | Build the analysis workspace and keep UI state, API data, and chess data typed. |
| Vite 8 | Serves the frontend during development and creates the production bundle. |
| Tailwind CSS 4 and Framer Motion 12 | Style the interface and provide focused, reduced-motion-aware transitions. |
| UltraChess and UltraChess React | Provide WebAssembly chess rules, PGN/FEN/SAN handling, the board, piece animation, and arrows. |
| Stockfish.js 18 | Runs in a browser Web Worker for interactive analysis of the position being viewed. |
| Python 3.11+, FastAPI, and Pydantic 2 | Serve the HTTP API, validate requests and responses, and define the OpenAPI contract. |
| python-chess and native Stockfish | Reconstruct legal positions and produce the objective engine evidence used by the backend review. |
| Maia2 0.9 | Estimates move likelihoods for a player rating and time control. |
| OpenRouter and GPT-5.6 Terra | Generate structured explanations from the verified evidence selected for each move. |
| Redis | Stores progressive analysis snapshots, resolved-import caches, import-to-analysis indexes, and rate-limit counters. |
| OpenAPI and openapi-typescript | Generate the frontend transport types from backend Pydantic schemas. |
| Vercel | Builds and hosts the frontend from `main`. |
| Modal | Runs the FastAPI service and separate CPU-heavy analysis workers. |
| Cloudflare | Proxies the public API hostname to Modal and supplies Turnstile protection for public imports. |

Backend Stockfish produces the review evidence. Stockfish.js responds to board
navigation in the browser and can analyze positions outside the stored server
snapshot.

## Run locally

You need:

- Bun 1.3
- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker
- Stockfish on `PATH`
- An OpenRouter API key

Install the backend and frontend:

```sh
(cd backend && uv sync --locked --dev --extra maia)
(cd frontend && bun install --frozen-lockfile)
cp backend/.env.example backend/.env
```

Add the OpenRouter key to `backend/.env`:

```text
OPENROUTER_API_KEY=...
```

Start the API:

```sh
cd backend
./run.sh
```

`run.sh` starts Redis and serves the API at `http://127.0.0.1:8001`. The first
real analysis downloads the Maia model.

Start the frontend in another terminal:

```sh
cd frontend
bun run dev
```

Open `http://127.0.0.1:5173`.

Set the Stockfish path in `backend/.env` when the executable is outside
`PATH`:

```text
G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_BINARY=/absolute/path/to/stockfish
```

## Run the checks

```sh
./tools/prove.sh
```

This command checks backend formatting, lint, types, and tests. It also audits,
generates contracts, type-checks, lints, tests, and builds the frontend. The
deterministic test suite does not spend OpenRouter credits.

Changes to providers, prompts, or model behavior also require the real
Stockfish, Maia, Redis, and OpenRouter checks in the
[`backend testing playbook`](backend/docs/development/testing-playbook.md).

## Deployment

Vercel deploys the frontend from `main`. GitHub runs frontend, backend, contract,
and secret checks on each relevant push.

Modal backend releases use the protected `Deploy Modal` workflow. The
[`Modal deployment guide`](backend/docs/development/modal-deployment.md) covers
secrets, runtime settings, Cloudflare routing, and production smoke tests.

## Related projects

- [`ultrachess`](https://github.com/yahorbarkouski/ultrachess) provides legal
  move generation, FEN, SAN, PGN, perft, and hashing through Rust and WebAssembly.
- [`ultrachess-react`](https://github.com/yahorbarkouski/ultrachess-react)
  provides the React chessboard, piece animation, and canvas arrows.

## Contributing

Read [`AGENTS.md`](AGENTS.md) and the relevant application guide before making
changes. Backend product and development documentation starts at
[`backend/docs/README.md`](backend/docs/README.md).

Run `./tools/prove.sh` before opening a pull request.

## License and security

g6 uses the [`GPL-3.0-or-later`](LICENSE) license. Third-party components keep
their original terms in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
Report security issues through [`SECURITY.md`](SECURITY.md).
