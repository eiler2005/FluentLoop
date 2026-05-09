# Contributing to FluentLoop

FluentLoop is a personal-use Telegram bot, but the repository is public and
PRs are welcome — bug fixes, doc clarifications, small features that fit the
"single user, single Docker container" shape. Anything bigger, please open
an issue first so we can talk about scope.

## Before you start

- Read [`AGENTS.md`](AGENTS.md) — the durable workflow rules apply to humans
  too: smallest useful change, surgical edits, verifiable goals, doc updates
  before commit.
- Read the relevant epic in [`docs/features/`](docs/features/) so you know
  what is in scope and what is intentionally not.
- For architectural decisions, write an
  [ADR](docs/adr/) **before** the code. Don't refactor a system into a new
  shape and document it after.

## Dev setup

Python 3.11+, [`uv`](https://github.com/astral-sh/uv) recommended.

```bash
git clone https://github.com/eiler2005/FluentLoop.git
cd FluentLoop
uv sync --extra dev
cp .env.example .env   # fill in your own values, never commit real ones
```

Optional but recommended:

```bash
pre-commit install     # runs secret-scan + ruff on each commit
```

## Day-to-day commands

```bash
# Tests
uv run --extra dev pytest -q
uv run --extra dev pytest -v -k <epic-or-keyword>
uv run --extra dev pytest --lf          # rerun the last failures

# Lint
uv run --extra dev ruff check src tests scripts
uv run --extra dev ruff format src tests scripts

# Secret scan (also a pre-commit hook)
python scripts/secret_scan.py

# Local config sanity
uv run python -m fluentloop --check
uv run python scripts/check_env.py
```

The standard pre-commit gate is documented in
[`docs/testing.md`](docs/testing.md).

## Pull request checklist

- [ ] PR description explains *why* (problem) and *what* (chosen solution).
- [ ] Updated the relevant epic file (status, "Notes from implementation"
      section if behavior changed).
- [ ] Added or updated an ADR if an architectural choice was made.
- [ ] Added or updated tests; `pytest -q` is green.
- [ ] `ruff check src tests scripts` is clean.
- [ ] `python scripts/secret_scan.py` is clean.
- [ ] No real credentials in the diff (`.env`, tokens, API keys, real user IDs).
- [ ] Docs touched if user-visible behavior changed (README, runbooks).

## Commit style

Short imperative subject (under ~70 chars), then a blank line, then 1–3
bullet points of "why and what." Example:

```
EPIC-08: pin channel help

- Maintain one fresh #help message in the forum Help topic.
- Safely delete only bot-authored stale help/smoke messages.
- Idempotent on re-runs of telegram_workspace_maintenance.
```

Do **not** include real bot tokens, API keys, user IDs, or VPS hostnames in
commit messages. The CI secret scan will catch obvious leaks; subtler ones
(real names of people, clients, projects) are on us.

## Reporting issues

GitHub Issues. Please include:

1. What you were trying to do.
2. What you expected to happen.
3. What actually happened (include the relevant log slice with secrets
   redacted).
4. Environment: local Docker, VPS, Python version.

## Out of scope

These are intentionally **not** goals — please don't open PRs for them
without prior discussion:

- Multi-tenancy or multi-user auth (FluentLoop is single-user by design).
- Voice support (text-only MVP).
- Public web UI (see [`docs/features/EPIC-15-optional-web-interface.md`](docs/features/EPIC-15-optional-web-interface.md)
  — `Status: Deferred`).
- Generic content import beyond the user's own lesson notes.

If you have a use case that genuinely doesn't fit any of the above
exclusions, open an issue and tag it `proposal` so we can talk about whether
it deserves a P1/P2 entry in PRD §6.

## License

By contributing you agree that your contributions are licensed under the
[MIT License](LICENSE).
