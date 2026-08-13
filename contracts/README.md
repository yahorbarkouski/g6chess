# API contract

`openapi.json` is generated from the backend's Pydantic and FastAPI models. It
is committed so API changes are reviewable and frontend transport types can be
reproduced without starting Redis, Stockfish, Maia, or OpenRouter.

Regenerate from the repository root:

```sh
(cd backend && uv run python scripts/export_openapi.py)
(cd frontend && bun run contracts:generate)
```

Never edit the OpenAPI document or generated TypeScript by hand.
