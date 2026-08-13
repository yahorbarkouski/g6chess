# G6 Explanation Modal And Frontend Defense Plan

Date: 2026-05-05
Scope:
- `/Users/yahorbarkouski/g6explanation`
- `/Users/yahorbarkouski/g6explanation-frontend`

This plan intentionally excludes `g6chess-backend`.

## Executive Summary

The system to defend is:

```text
Browser
  -> G6 Explanation frontend
  -> Modal FastAPI web endpoint
  -> Redis pending snapshot / import index
  -> Modal worker spawn
  -> Stockfish + Maia + OpenRouter + Chess.com
  -> Redis partial snapshots
  -> frontend polling
```

The highest-risk operation is not serving the API itself. It is accepting an anonymous request that spawns a heavy Modal worker and fans out to Stockfish/Maia/OpenRouter. Cloudflare should absorb generic internet abuse, but Redis must make the final product-aware decision before any expensive work starts.

The key Modal-specific issue: adding a custom domain does **not** disable the generated `.modal.run` URL. If we only put `api.g6...` behind Cloudflare, attackers can still hit the `.modal.run` endpoint directly unless Modal proxy auth or an equivalent origin-secret gate is enabled.

The first real defense is:

1. Serve the API through a Cloudflare-proxied custom domain.
2. Enable Modal proxy auth on the web endpoint.
3. Have Cloudflare inject the Modal proxy auth headers only on origin requests.
4. Add Redis admission control inside the app before import resolution, job creation, and worker spawn.
5. Add Turnstile to anonymous import starts.
6. Teach the frontend to respect `429` and `Retry-After`.

## Current Source-Grounded Map

### Frontend

- `README.md:5-8` says the UI submits a Chess.com URL to `POST /api/game-analysis/import`, then polls the returned `status_url`.
- `src/lib/api.ts:10-13` configures the backend base URL with `VITE_G6_API_BASE_URL`.
- `src/lib/api.ts:40-61` exposes the active backend calls:
  - `POST /api/game-analysis/import`
  - `GET /api/game-analysis/import/chess-com/live/{external_game_id}`
  - `GET {status_url}`
- `src/components/analysis/AnalysisWorkspace.tsx:168-188` polls every 1.2 seconds until a terminal snapshot.
- `src/components/analysis/AnalysisWorkspace.tsx:260-295` starts a route import after cached lookup returns `404`.

### Modal API

- `deploy/modal_app.py:103-134` exposes the FastAPI app with `@modal.asgi_app()`.
- `deploy/modal_app.py:70-80` allows up to 10 worker containers by default.
- `deploy/modal_app.py:30-39` sets worker defaults: Stockfish depth 16, MultiPV 5, context workers 8, OpenRouter concurrency 30.
- `docs/development/modal-deployment.md:9-14` documents the production flow: API request, Redis pending snapshot, Modal worker spawn, Redis snapshots, frontend polling.
- `docs/development/modal-deployment.md:172-176` says the deployment does not yet add durable distributed queue semantics, cancellation, user ownership, or cost accounting.

### FastAPI Routes

`src/g6explanation/visualization/http_api.py:80-126` registers:

- `GET /api/visualization/health`
- `GET /api/visualization/examples`
- `GET /api/visualization/examples/{example_id}`
- `GET /api/visualization/examples/{example_id}/contexts/{ply}`
- `POST /api/game-analysis`
- `POST /api/game-analysis/import`
- `GET /api/game-analysis/import/chess-com/live/{external_game_id}`
- `GET /api/game-analysis/{analysis_id}`

The app has CORS in `http_api.py:73-79`, but no auth, no Turnstile validation, and no rate limiter.

### Expensive Work Boundary

- `GameImportService.start()` checks cached Chess.com responses, then resolves/imports and starts analysis in `src/g6explanation/game_imports/import_service.py:145-160`.
- `ChessComLiveGameResolver.resolve()` calls Chess.com callback/archive endpoints if Redis import cache misses in `src/g6explanation/game_imports/chess_com_live_games.py:218-241`.
- `GameAnalysisService.start()` counts plies, writes a pending snapshot, then submits the runner in `src/g6explanation/game_analysis/job_service.py:63-92`.
- Redis is used for snapshots and import caches, but not admission control.

## Threat Model

Attacker goals:

- Spawn many Modal workers and burn compute.
- Force many OpenRouter calls.
- Hit Chess.com repeatedly and cause upstream throttling.
- Poll many job IDs and increase Redis/API cost.
- Abuse visualization/context endpoints if they remain public.
- Bypass Cloudflare by calling the `.modal.run` endpoint directly.
- Cache-bust frontend assets, including large Stockfish files if publicly served.

Trust boundaries:

- Browser input is untrusted.
- CORS is not a security boundary.
- Cloudflare request metadata is trusted only after Modal proxy auth proves the request came through our Cloudflare path.
- Analysis IDs are bearer secrets. They are hard to guess but should not authorize mutation or expensive work.
- Redis is the shared enforcement point for all Modal API containers and workers.

## Defense Architecture

```text
Cloudflare zone
  - DNS proxy for frontend and API
  - WAF managed rules
  - coarse rate limits
  - request-size/method/path blocks
  - Worker or request-header transform that injects Modal proxy auth

Modal API endpoint
  - custom domain on API hostname
  - requires_proxy_auth=True
  - rejects direct .modal.run requests without Modal-Key / Modal-Secret

FastAPI app
  - route classification
  - Turnstile validation for anonymous expensive starts
  - Redis rate limits and idempotency locks
  - job/source/provider budgets before expensive work

Frontend
  - Cloudflare-cached static assets
  - Turnstile on import
  - 429 / Retry-After handling
  - adaptive polling
```

## Immediate Cloudflare And Modal Setup

### 1. Put The API Behind A Custom Domain, But Do Not Trust That Alone

Configure the Modal app with a custom API hostname and proxy auth:

```python
@modal.asgi_app(
    custom_domains=["api.g6chess.com"],
    requires_proxy_auth=True,
)
def fastapi_app() -> object:
    ...
```

Modal custom domains do not disable the generated `.modal.run` URL. `requires_proxy_auth=True` is the critical bypass defense.

### 2. Inject Modal Proxy Auth Only From Cloudflare

Use one of these:

- Preferred: Cloudflare Worker route for `api.g6chess.com/*`.
  - Worker reads `MODAL_KEY` and `MODAL_SECRET` from Worker secrets.
  - Worker forwards to the Modal custom-domain or `.modal.run` URL with `Modal-Key` and `Modal-Secret`.
  - Browser never sees those headers.
- Acceptable: Cloudflare Request Header Transform Rules.
  - Set `Modal-Key` and `Modal-Secret` as origin request headers for the API hostname.
  - Use Cloudflare Trace to confirm headers are added only on the intended API route.

Never put `Modal-Key` or `Modal-Secret` into frontend JavaScript.

### 3. Verify Bypass Resistance

After enabling proxy auth:

```bash
curl https://<workspace>--g6explanation-fastapi-app.modal.run/api/visualization/health
# expected: unauthorized / rejected by Modal

curl https://api.g6chess.com/api/visualization/health
# expected: 200 through Cloudflare
```

If direct `.modal.run` still returns `200`, the system is not actually protected by Cloudflare.

## Cloudflare Rules

### Baseline WAF

Enable:

- Cloudflare Managed Ruleset.
- Cloudflare OWASP Core Ruleset if the plan allows it.
- Browser Integrity Check.
- Security Events visibility.

Start managed rules in log/simulate mode for the PGN endpoint, then block after checking false positives. PGN text may look unusual to generic WAF rules, so exceptions should be narrow and route-specific.

### Route Policy

| Route | Public? | Policy |
| --- | --- | --- |
| `GET /api/visualization/health` | Yes | Cheap health, low rate limit |
| `GET /api/visualization/examples` | Prefer no | Block unless frontend still needs it |
| `GET /api/visualization/examples/{id}` | Prefer no | Block unless explicit public demo |
| `GET /api/visualization/examples/{id}/contexts/{ply}` | No | Block publicly; this can build real context |
| `POST /api/game-analysis` | Prefer no | Internal/admin only or same protection as import |
| `POST /api/game-analysis/import` | Yes | Turnstile + Redis limiter + source idempotency |
| `GET /api/game-analysis/import/chess-com/live/{id}` | Yes | Cheap lookup limiter |
| `GET /api/game-analysis/{analysis_id}` | Yes | Poll limiter and adaptive frontend polling |

### Edge Rate Limits

These are starting values. Redis limits below are authoritative.

| Surface | Cloudflare match | Starting edge limit | Action |
| --- | --- | --- | --- |
| Global API | host is API and path starts `/api/` | 300/min/IP | block or 429 for 10 min |
| Analysis start | `POST /api/game-analysis/import` and `POST /api/game-analysis` | 3/min/IP and 10/hour/IP | block/429 |
| Polling | `GET /api/game-analysis/{analysis_id}` | 180/min/IP | 429 for 1-5 min |
| Cached lookup | `GET /api/game-analysis/import/chess-com/live/*` | 60/min/IP | 429 |
| Health | `/api/visualization/health` | 60/min/IP | 429 |
| Visualization context | `/api/visualization/examples/*/contexts/*` | 0 public | block |
| Unknown API paths | `starts_with(path, "/api/")` and not allowlisted | 0 public | block |

Cloudflare rate limits are not exact origin guarantees. Backend Redis limits must still run before expensive work starts.

### Method And Body Guards

Cloudflare custom rules:

- Allow `GET`, `POST`, and `OPTIONS` only.
- Require `Content-Type: application/json` for `POST /api/game-analysis*`.
- Block request bodies above product maximums:
  - Chess.com URL import: 8 KB.
  - PGN import: 128 KB.
  - Direct `/api/game-analysis`: 128 KB.
- Block `/docs`, `/redoc`, and `/openapi.json` in production unless intentionally protected.

### Bot Controls

Do not blanket-challenge `/api/*` JSON requests. Browser challenges often break `fetch()` clients.

Use:

- Turnstile inside the import UI.
- WAF/rate-limit blocks for API abuse.
- Bot Fight/Super Bot Fight primarily for frontend page and static routes, with explicit API skips unless tested.

## Redis Admission Control

Add a backend module before expensive work, for example:

```text
src/g6explanation/security/
  __init__.py
  client_identity.py
  rate_limiter.py
  turnstile.py
  admission.py
```

Or keep it close to the product boundary:

```text
src/g6explanation/game_analysis/admission_control.py
```

The route should call admission control before:

1. Chess.com resolver network calls.
2. PGN parsing beyond cheap size/shape validation.
3. `GameAnalysisService.start()`.
4. Redis snapshot writes.
5. Modal worker spawn.

### Required Primitives

- `client_identity(request)`: normalized client IP, country, user agent hash, `CF-Ray`, and whether request arrived through the Cloudflare/Modal-auth path.
- `RateLimiter.check_many(...)`: atomically evaluates multiple Redis buckets and returns allow/deny plus retry time.
- `source_key`: stable key for idempotency.
  - Chess.com: `chess_com_live:{external_game_id}`.
  - PGN: `pgn:{sha256(normalized_pgn + options)}`.
- `inflight lock`: `SET lock:{source_key} NX EX 300`.
- `job pointer`: `source:{source_key} -> GameAnalysisImportResponse`, TTL 24 hours.
- `worker lease`: `worker:{analysis_id}` with TTL, renewed by worker or cleared at terminal status.
- Deny response: `429` with `Retry-After`, JSON error code, and no worker spawn.

### Starting Redis Limits

| Key | Limit | Why |
| --- | --- | --- |
| `ip:{ip}:api` | 300/min | General API pressure valve |
| `ip:{ip}:analysis_start` | 3/10 min, 12/day | Anonymous cost control |
| `ip:{ip}:pgn_start` | 2/10 min, 8/day | Pasted PGNs can bypass Chess.com cache |
| `ip:{ip}:chesscom_start` | 5/hour, 20/day | Chess.com imports are cacheable but still upstream work |
| `source:{source_key}:start` | 1 in-flight | Duplicate submit/refresh returns existing job |
| `global:analysis_start` | 20/min | Protect Modal from distributed bursts |
| `global:analysis_inflight` | cap equal to public worker cap | Prevent overspawn |
| `global:chesscom_egress` | 30/min | Protect Chess.com and avoid upstream 429s |
| `global:openrouter_generation` | provider-plan dependent | Protect model spend |
| `analysis:{id}:poll:{ip}` | 90/min | Covers normal UI; blocks tight loops |
| `analysis:{id}:poll:global` | 600/min | Protect one shared viral job URL |

Tune after telemetry. Start conservative because this system currently has no account-level quotas, billing model, or cancellation.

### Fail-Open / Fail-Closed

- Job starts: fail closed if Redis limiter is unavailable.
- Chess.com import resolution: fail closed if Redis limiter is unavailable.
- Polling: fail open or degraded if Redis is unavailable, because polling is a read and user may already have paid the job cost.
- Health: fail open.

## Turnstile Plan

Add Cloudflare Turnstile to anonymous expensive starts:

- Chess.com URL import.
- PGN paste import.
- Direct `/api/game-analysis` if left public.

Backend:

- Add `turnstile_token` to the import request or a sibling security envelope.
- Validate with Cloudflare Siteverify before admission succeeds.
- Include `remoteip` from `client_identity`.
- Use an idempotency key for validation retries.
- Treat tokens as five-minute, single-use tokens.
- Deny missing/invalid token before Chess.com or worker work.

Frontend:

- Render Turnstile in the import panel.
- Disable submit while solving or while an import request is in flight.
- Reset the widget after a failed/expired token.
- Do not hide Turnstile behind retry loops.

## Modal Runtime Caps

Before public exposure, lower public defaults:

| Setting | Current code default | Safer first public value |
| --- | --- | --- |
| `G6EXPLANATION_MODAL_API_MAX_CONTAINERS` | 20 | 5-10 |
| `G6EXPLANATION_MODAL_WORKER_MAX_CONTAINERS` | 10 | 3-5 |
| `G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS` | 8 | 3-4 |
| `G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY` | 30 | 5-10 |
| `G6EXPLANATION_MODAL_WORKER_MIN_CONTAINERS` | 0 | 0 except demo windows |

These caps are not a security solution. They are the blast-radius limit while Cloudflare and Redis limits are being verified.

## Frontend Defense Plan

### Static Frontend

Put the frontend hostname behind Cloudflare too.

Cache policy:

- `/assets/*`: cache everything, long TTL, immutable.
- `/stockfish/*`: cache everything, long TTL. This asset is expensive to serve repeatedly.
- `/index.html`: short TTL or no-store, so deployments roll out normally.
- Unknown route fallback: cache carefully because the app has SPA rewrites.

Security headers:

- `Strict-Transport-Security` after HTTPS is stable.
- `X-Content-Type-Options: nosniff`.
- `Referrer-Policy: strict-origin-when-cross-origin`.
- `Permissions-Policy` with only required browser capabilities.
- CSP after testing Stockfish worker/WASM loading.

### API Client Behavior

Update `src/lib/api.ts`:

- Preserve `Retry-After` in `ApiError`.
- Preserve a stable `code` field from backend error JSON.
- Treat `429` as a cooldown, not a generic failure.

Update polling:

- Keep quick feedback initially, then back off:
  - 1.2 seconds for first 15-20 seconds.
  - 3 seconds until 2 minutes.
  - 5-10 seconds after that.
- Always respect `Retry-After`.
- Stop duplicate polling from multiple overlapping timers.
- Do not immediately start a new import when a cached lookup is rate-limited. Only fall back to new import on clean `404`.

Update submit behavior:

- One in-flight import per tab.
- Disable the submit button while request is pending.
- Reset Turnstile only after a failed/expired token.
- Do not send `include_context=true` from public UI.

## Implementation Roadmap

### Phase 0: No-Code Safety Switches

1. Put frontend and API hostnames behind Cloudflare DNS proxy.
2. Lower Modal worker/API max containers to conservative values.
3. Add Cloudflare WAF managed rules in log mode.
4. Add Cloudflare block rules for visualization context routes and unknown API paths.
5. Confirm `VITE_G6_API_BASE_URL` points to the Cloudflare API hostname, not `.modal.run`.

### Phase 1: Enforce Cloudflare As The Gateway

1. Configure Modal API custom domain.
2. Enable `requires_proxy_auth=True` on `@modal.asgi_app`.
3. Add Cloudflare Worker or request-header transform to inject Modal proxy auth.
4. Verify direct `.modal.run` requests fail.
5. Log `CF-Ray`, normalized IP, and route policy in FastAPI.

### Phase 2: Backend Admission Control

1. Add `Request` to FastAPI route functions where needed.
2. Implement `client_identity`.
3. Implement Redis atomic limiter.
4. Add source-key idempotency locks and cached job pointer returns.
5. Add limits before `GameImportService.start()` and before `GameAnalysisService.start()`.
6. Add poll limits to `game_analysis_state`.
7. Add tests with fake Redis/time plus a real Redis integration gate.

### Phase 3: Turnstile And Frontend Backoff

1. Add Turnstile widget to the import panel.
2. Validate Turnstile server-side.
3. Extend API errors with `Retry-After`.
4. Add adaptive polling and cooldown UI.
5. Add tests for duplicate submit, `429`, and `Retry-After`.

### Phase 4: Observability And Drills

1. Dashboard:
   - Cloudflare 4xx/5xx/rate-limit events.
   - Modal API invocations.
   - Modal worker spawns.
   - Redis limiter allow/deny counts.
   - OpenRouter calls and failures.
   - Chess.com outbound status codes.
2. Run staging burst tests:
   - 100 users loading frontend.
   - 20 repeated import attempts from one IP.
   - 50 clients polling one analysis.
   - repeated direct `.modal.run` calls.
3. Verify no worker spawns after denied requests.

## Verification Checklist

- Direct `.modal.run` API URL rejects without Modal proxy auth.
- Cloudflare API hostname succeeds.
- `/api/visualization/examples/*/contexts/*` is blocked publicly.
- `POST /api/game-analysis/import` without Turnstile is denied before Chess.com/worker work.
- Repeated identical Chess.com URL returns the same in-flight/cached `analysis_id`.
- Repeated identical PGN returns the same in-flight/cached `analysis_id`.
- Redis down fails closed for starts and does not spawn workers.
- Polling returns `429` with `Retry-After` when abused.
- Frontend respects `Retry-After`.
- Modal worker count never exceeds the configured public cap in burst tests.
- Logs include `CF-Ray`, normalized IP, limiter key, route, decision, and retry time.

## What Not To Do

- Do not rely on CORS as an abuse defense.
- Do not rely on Cloudflare DNS/rate limits while `.modal.run` remains publicly usable.
- Do not put Modal proxy auth secrets in frontend code.
- Do not run generic Cloudflare browser challenges on JSON API routes without testing.
- Do not treat Cloudflare limits as the only cost-control layer.
- Do not leave `include_context=true` available from public UI.

## External References Checked

- Modal Web Endpoints: https://modal.com/docs/guide/webhooks
- Modal Proxy Auth: https://modal.com/docs/guide/webhook-proxy-auth
- Modal Web Endpoint URLs and custom domains: https://modal.com/docs/guide/webhook-urls
- Cloudflare Rate Limiting Rules: https://developers.cloudflare.com/waf/rate-limiting-rules/
- Cloudflare Request Header Transform Rules: https://developers.cloudflare.com/rules/transform/request-header-modification/
- Cloudflare WAF Managed Rules: https://developers.cloudflare.com/waf/managed-rules/
- Cloudflare Turnstile server-side validation: https://developers.cloudflare.com/turnstile/get-started/server-side-validation/

## Open Decisions

- Exact public domain names for frontend and API.
- Whether `/api/game-analysis` should be public at all, or only `/api/game-analysis/import`.
- Whether visualization example metadata is still needed by the public frontend.
- Whether Cloudflare Worker or request-header transform will inject Modal proxy auth.
- Initial anonymous daily quota once real traffic expectations are known.
