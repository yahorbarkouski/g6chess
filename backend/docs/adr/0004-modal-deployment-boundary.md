# ADR 0004: Modal Deployment Boundary

Date: 2026-05-05
Status: Accepted

## Decision

The first public deployment runs the FastAPI game-analysis API and analysis
workers inside one Modal App.

The API container handles request validation, import resolution, pending Redis
snapshots, and polling. It must not run full-game analysis in-process in the
Modal deployment. Instead, job start uses a Modal spawn executor that serializes
the `GameAnalysisStartRequest` and starts a worker function.

The worker container runs the existing `GameAnalysisRunner` with real
Stockfish, Maia2, OpenRouter, and Redis snapshot persistence.

## Rules

- Keep the local `ThreadPoolExecutor` service path for local development and
  deterministic tests.
- Keep Redis as the shared snapshot contract between API, worker, and frontend.
- Keep Maia model files on a Modal Volume, not in repository source.
- Keep runtime secrets in the Modal `g6explanation-runtime` secret.
- Keep CI responsible for required local quality gates before deployment.
- Limit Modal worker concurrency with `G6EXPLANATION_MODAL_WORKER_MAX_CONTAINERS`
  and product request limits before public traffic.
- This deployment boundary does not change chess truth, explanation policy,
  schema contracts, or source-rights policy.

## Validation

A deploy is acceptable when the required local checks pass, Modal deploys
`deploy/modal_app.py`, the health endpoint responds, and a no-mock
game-analysis smoke can complete with Stockfish depth 16 or deeper.
