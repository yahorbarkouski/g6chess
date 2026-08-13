# g6: Free Chess Analysis

[Try g6](https://g6chess.com)

https://github.com/user-attachments/assets/983c9ebf-1496-47e1-a61a-580f2b8c7dca

g6 reviews a real chess game one move at a time. Paste a Chess.com game,
Lichess game, Lichess study chapter, or PGN. g6 reconstructs the game, analyzes
each position, and turns the important moments into explanations you can use.

The point is not to make an LLM play chess. The point is to build a coach whose
words stay tied to chess evidence.

```text
Stockfish + Maia + deterministic rules + verifiers = truth and diagnosis
LLM or deterministic renderer = wording for verified explanations
```

## What you get

- A board-first review with move quality, critical moments, and evaluation.
- Verified engine lines that can be previewed directly on the board.
- Human move-likelihood evidence from Maia, kept separate from objective move
  quality.
- Coach-style explanations checked against the supplied chess evidence.
- Imports from Chess.com, Lichess, Lichess studies, and pasted PGN.
- Shareable game routes and progressive results while deeper analysis runs.

The review is built to answer one question:

> At this move in my game, what happened, how good was my move, and what should
> I understand?

## How it works

```text
Game URL or PGN
  -> canonical game and legal move reconstruction
  -> Redis-backed analysis job
  -> Stockfish evaluation and Maia move likelihoods
  -> deterministic move labels and evidence packets
  -> explanation generation
  -> deterministic explanation verification
  -> progressive results in the React client
```

Stockfish decides objective strength. Maia estimates how likely a human is to
find a move. Rules and verifiers decide which claims the explanation may make.
The language model only phrases those supported claims. If verification fails,
g6 rejects the explanation instead of returning plausible-sounding chess.

## Repository layout

| Path | What lives there |
| --- | --- |
| [`frontend/`](frontend/README.md) | React, Vite, UltraChess, the analysis workspace, and browser Stockfish |
| [`backend/`](backend/README.md) | FastAPI, Stockfish and Maia analysis, Redis jobs, imports, explanation generation, and verification |
| [`contracts/`](contracts/README.md) | Committed OpenAPI schema and generated frontend transport types |
| [`tools/`](tools) | Repository-wide release and contract checks |

The backend Pydantic models own the API contract. The repository exports them
as [`contracts/openapi.json`](contracts/openapi.json) and generates TypeScript
transport types for the frontend. UI-specific mapping remains handwritten at
the network boundary.

## Run g6 locally

You need:

- Bun 1.3
- Python 3.11 or newer and [uv](https://docs.astral.sh/uv/)
- Docker
- Stockfish available on `PATH`
- An OpenRouter API key for generated explanations

Install both applications and create the local backend environment:

```sh
(cd backend && uv sync --locked --dev --extra maia)
(cd frontend && bun install --frozen-lockfile)
cp backend/.env.example backend/.env
```

Add your key to `backend/.env`:

```text
OPENROUTER_API_KEY=...
```

Start the API in one terminal:

```sh
cd backend
./run.sh
```

`run.sh` starts the local Redis container and serves the API at
`http://127.0.0.1:8001`. The first real analysis downloads the Maia model.

Start the frontend in another terminal:

```sh
cd frontend
bun run dev
```

Open `http://127.0.0.1:5173`.

If Stockfish is not discoverable on `PATH`, set its absolute path in
`backend/.env`:

```text
G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_BINARY=/absolute/path/to/stockfish
```

## Verify a change

Run the complete deterministic release proof from the repository root:

```sh
./tools/prove.sh
```

This checks backend formatting, linting, static types, and tests. It also audits,
generates contracts, type-checks, lints, tests, and builds the frontend. These
checks use deterministic providers and do not spend OpenRouter credits.

Provider-facing backend changes also need the real Stockfish, Maia, Redis, and
OpenRouter gate described in the
[`backend testing playbook`](backend/docs/development/testing-playbook.md).

## Deployment

Frontend and backend releases have different safety rules.

- Vercel builds a preview when a branch is pushed. A merge or direct push to
  `main` deploys the frontend to production automatically.
- GitHub runs frontend and backend quality checks for pull requests and relevant
  changes on `main`.
- Publishing source does not deploy the backend. A reviewed commit must pass the
  protected, manually dispatched `Deploy Modal` workflow.

The root [`vercel.json`](vercel.json) builds `frontend/` for the existing Vercel
project. Backend infrastructure, required secrets, runtime settings, and smoke
tests are documented in the
[`Modal deployment guide`](backend/docs/development/modal-deployment.md).

## Related projects

- [`ultrachess`](https://github.com/yahorbarkouski/ultrachess) provides the
  Rust and WebAssembly chess library used for legal moves, FEN, SAN, PGN,
  perft, and hashing.
- [`ultrachess-react`](https://github.com/yahorbarkouski/ultrachess-react)
  provides the React chessboard, piece animation, and canvas arrows.

## Contributing

Start with [`AGENTS.md`](AGENTS.md) for repository rules. Backend product and
development documentation begins at
[`backend/docs/README.md`](backend/docs/README.md). Keep chess truth outside the
language model, regenerate the contract after schema changes, and run
`./tools/prove.sh` before opening a pull request.

## License and security

G6 is licensed under
[`GPL-3.0-or-later`](LICENSE). Third-party components retain their own terms;
see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Report vulnerabilities
privately according to [`SECURITY.md`](SECURITY.md).
