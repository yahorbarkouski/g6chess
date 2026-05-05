# Audit Index

This directory contains dated audits, plans, and event logs. Treat reports as
snapshots from the date in the filename. Verify important claims against the
current source and project checks before using them as implementation guidance.

Event logs are provenance for the paired report. Read the report first, then the
event log only when you need command history or detailed evidence.

## Active References

| Report | Status | Use For |
| --- | --- | --- |
| `2026-05-05-codebase-audit.md` | Current audit | Current code health, active risks, checks, and release concerns. |
| `2026-05-05-cloudflare-rate-limit-security-plan.md` | Current security plan | Cloudflare, rate limiting, Turnstile, origin protection, and frontend `429` behavior. |
| `2026-05-05-routing-shareability-audit.md` | Product/architecture plan | Shareable game URLs, direct-load routing, and backend route contract choices. |
| `2026-05-05-engine-line-preview-regression-audit.md` | Focused bug audit | Engine-line preview behavior and old-vs-current sidebar line selection. |
| `2026-05-05-book-lines-port-plan.md` | Feature plan | Opening-book metadata contract and book-line UI port. |

## Historical Context

| Report | Status | Use For |
| --- | --- | --- |
| `2026-05-04-codebase-audit.md` | Superseded by `2026-05-05-codebase-audit.md` | Earlier baseline and resolved or stale findings. |
| `2026-05-04-stockfish-performance-audit.md` | Historical performance audit | Original G6 Stockfish performance investigation. |
| `2026-05-04-stockfish-ultrachess-cross-repo-performance-audit.md` | Historical with implementation notes | Cross-repo G6/UltraChess performance context. Some blocker text is stale; verify with current tests. |

## Event Logs

- `2026-05-05-codebase-audit-event-log.md`
- `2026-05-05-cloudflare-rate-limit-security-plan-event-log.md`
- `2026-05-05-routing-shareability-audit-event-log.md`
- `2026-05-05-engine-line-preview-regression-audit-event-log.md`
- `2026-05-05-book-lines-port-plan-event-log.md`
- `2026-05-04-codebase-audit-event-log.md`
- `2026-05-04-stockfish-performance-audit-event-log.md`
- `2026-05-04-stockfish-ultrachess-cross-repo-performance-audit-event-log.md`

When adding a new report, add it to one of the tables above and list the paired
event log here.
