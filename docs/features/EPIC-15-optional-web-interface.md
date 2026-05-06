# EPIC-15 — Optional lightweight web interface

**Status:** Deferred — re-evaluate after 4–6 weeks of real bot usage.
**PRD references:** §6 (P0.5), §22.5, §23
**Depends on:** EPIC-04, EPIC-05, EPIC-13 (data model must be stable
first)
**Blocks:** —

## Why deferred

The PRD allows a lightweight web UI in MVP. It is intentionally **not**
on the critical path because:

- A web UI is effectively a second project inside the first: hosting,
  framework, auth, CSP, session, deployment, browser testing.
- In-Telegram editing via inline keyboards covers ~90% of the
  management needs (approve candidates, toggle favorites, view
  patterns). The remaining 10% — bulk edits, multi-item filtering — is
  rare and survivable via direct SQL during MVP.
- Building a UI before real bot usage produces the wrong UI. After
  4–6 weeks, the actual pain points will be obvious.

## Goal (when un-deferred)

A small read-mostly web UI for content management: list items, filter,
edit, approve candidates, view stats. Telegram remains the primary
interface for daily practice; the web UI is for the operations
Telegram does poorly.

## In scope (when un-deferred)

- List learning items with filters (type, tag, status, due, weak,
  favorite).
- Edit / archive / delete items.
- Approve extracted candidates with a richer UI than chat allows.
- View `/stats`-equivalent metrics in a dashboard.
- Manually add items.
- Single-user auth: a long shared secret in env (`WEB_UI_TOKEN`),
  passed as a cookie or header. No user accounts.

## Out of scope

- Multi-user accounts.
- Real-time chat (use Telegram).
- Complex analytics, plotting libraries.
- Teacher / admin mode.
- Mobile-app-grade polish.

## Acceptance criteria (when un-deferred)

- The web UI is reachable on a configurable port (default 8080) when
  `WEB_UI_ENABLED=true` is set.
- Without `WEB_UI_TOKEN` in the request, all requests return 401.
- Editing an item in the web UI is reflected on the next Telegram
  practice session.
- The same Docker container hosts both the bot and the web UI; no
  second service.

## Open questions

- Framework: FastAPI + minimal HTMX vs Flask + Jinja vs Telegram Mini
  App. Default working assumption: FastAPI + HTMX.
- Hosting strategy: same domain as some future landing page or just
  `https://<vps-ip>:<port>` behind basic auth? Default: VPS port +
  token; reverse proxy is an infra decision for later.
- Read-only by default with explicit "edit mode" toggle, or always
  editable? Default: always editable (single user).

## Verification plan (when un-deferred)

1. `WEB_UI_ENABLED=true WEB_UI_TOKEN=<secret>`; restart container.
2. Open `https://<vps-ip>:<port>`; assert 401 without token.
3. With token in header, list view loads with current items.
4. Edit an item; restart bot; verify the change persists in Telegram.
5. `WEB_UI_ENABLED=false`; restart; the port is closed.
