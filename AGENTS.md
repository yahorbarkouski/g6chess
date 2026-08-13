# G6 repository guide

Read `backend/AGENTS.md` before backend, contract, provider, chess-truth, or
cross-stack work. Read `frontend/AGENTS.md` before React/TypeScript work.

The backend Pydantic/FastAPI schema is authoritative. Regenerate committed
OpenAPI and TypeScript transport types after contract changes. Keep UI-domain
mapping handwritten in the frontend.

Never make source publication deploy production. Modal releases remain manual
and protected. Never commit secrets, user games, provider outputs, model weights,
or licensed font binaries.

Write public README prose with direct affirmative sentences. Avoid contrastive
negation templates and manifesto-style product framing. The repository prose
check enforces common forms of this pattern.
