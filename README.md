# G6 Chess

G6 is an open-source, evidence-grounded chess coach. It separates chess truth
from explanation wording:

```text
Stockfish + Maia + deterministic rules + verifiers = truth and diagnosis
LLM or deterministic renderer = wording for verified explanations
```

This monorepo contains two independently runnable projects:

- [`frontend/`](frontend/README.md): React, Vite, UltraChess, and browser
  Stockfish for the board-first analysis experience.
- [`backend/`](backend/README.md): FastAPI, Redis-backed asynchronous analysis,
  Stockfish, Maia human-likelihood evidence, verified explanation generation,
  and source-aware game imports.

The backend owns the API contract. It exports [`contracts/openapi.json`](contracts/openapi.json),
which generates the frontend transport types. UI-domain mapping remains
handwritten and defensive at the network boundary.

## Run locally

Requirements: Bun 1.3, Python 3.11+, uv, Docker, and a Stockfish executable on
`PATH`.

```sh
(cd backend && uv sync --locked --dev --extra maia)
(cd frontend && bun install --frozen-lockfile)
(cp backend/.env.example backend/.env)
# Add your OPENROUTER_API_KEY to backend/.env.
(cd backend && ./run.sh)
(cd frontend && bun run dev)
```

`backend/run.sh` starts Redis before the API. Maia downloads its model on the
first real analysis. Ordinary tests use deterministic providers and do not need
OpenRouter, Maia, or Stockfish. See
[`backend/docs/development/testing-playbook.md`](backend/docs/development/testing-playbook.md).

Run the complete local release proof with `./tools/prove.sh`.

The existing Vercel project uses the repository root. Root `vercel.json`
installs and builds `frontend/`, then publishes `frontend/dist`. Do not change
the Vercel project root to `frontend` unless the deployment config moves with it.

## License and security

G6 is GPL-3.0-or-later. Third-party components retain their own terms; see
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Report vulnerabilities using
[`SECURITY.md`](SECURITY.md), not a public issue.
