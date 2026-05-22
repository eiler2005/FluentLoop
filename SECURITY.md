# SECURITY.md

FluentLoop is a Telegram bot for an owner-curated admitted-user audience. The
operational surface is still small: one bot, one VPS, one Docker container, and
one set of secrets. The sensitive part is the learning data, which may contain
real names of colleagues, clients, and projects. This file documents what is
protected, what is sent to third parties, and what to do when something goes
wrong.

## Protected assets

| Asset | Storage | Sensitivity | Notes |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `.env` (local), VPS env, gitignored | Critical | Compromise = full bot impersonation, ability to message the user as "the bot". |
| AI provider API key (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY`) | `.env` (local), VPS env, gitignored | Critical | Compromise = billing fraud + leak of any text sent through it. |
| User lesson data (notes, mistakes, answers) | `data/` directory, SQLite, gitignored | High | Contains real names, client info, internal project topics. |
| Bot session / state files | `data/`, `state/`, gitignored | Medium | Re-creatable but losing them resets progress. |
| `data/backups/` daily SQLite snapshot | Local, gitignored | High | Same sensitivity as the live DB. |

## Threat model

- **Admitted Telegram users, single VPS, single Docker container.** Low attack
  surface, but per-user lesson progress and private uploads must stay isolated.
- **No public web endpoint** in MVP (Telegram is the only interface).
- **Realistic risks:**
  - Accidental commit of `.env` or a leaked token in a log line.
  - AI provider data retention — anything sent to OpenAI / Anthropic / DeepSeek is
    governed by their terms.
  - VPS compromise via SSH (mitigated by key-only auth, fail2ban — handled in
    a deployment epic later).
- **Not in scope for MVP:** DDoS, advanced threat actors, sophisticated
  exfiltration. This is a personal tool.

## Third-party data flow disclosure

The bot sends user-generated text to the configured AI provider for three
purposes:

1. **Extraction** (PRD §25.1) — uploaded lesson notes, word lists, teacher
   feedback are sent verbatim to the AI to identify candidate learning items.
2. **Exercise generation** (PRD §25.2) — approved learning items, progress
   state, and weakness signals are sent so the AI can generate exercises.
3. **Answer checking** (PRD §25.3) — exercise prompts and the user's answers
   are sent so the AI can judge them and produce feedback.

What this means in practice:

- Lesson notes may contain colleague names, client names, internal project
  names, and informal commentary. All of that is transmitted to the chosen
  AI provider.
- Provider data retention follows the published terms for the configured AI
  provider.
- The user must consciously decide they accept this. There is no way to
  build the product without it.

**Optional mitigation — redaction list.** A simple regex-based redactor can
replace user-maintained sensitive tokens (real names, project codenames)
with placeholders like `[COLLEAGUE_1]`, `[PROJECT_X]` before sending text to
the AI. This is captured as a P1 enhancement, not MVP-blocking. See
`docs/architecture.md` (TODO section) when it is filled in.

## Secrets policy

- Real values live only in `.env` (local), in the VPS environment, or in a
  password manager. **Never** in git, commit messages, logs, or example files.
- `.env.example` is the only env file tracked. It contains placeholders only.
- Confidential deploy-only values may live in `secrets/deploy.env`
  (gitignored, mode 600). See `docs/runbooks/secrets-management.md`.
- Pre-commit checklist:
  - `python3 scripts/secret_scan.py` must return `secret-scan: ok`.
  - No real Telegram user IDs (numeric IDs are personally identifying).
  - No email addresses.
- If a secret leaks: rotate immediately (BotFather `/revoke`, AI provider
  dashboard), force-push a clean history (with explicit user permission),
  audit logs.

## Recovery boundaries

| Scenario | Recovery |
|---|---|
| Bot token rotated by user | Update `.env` on VPS, restart container. |
| AI key rotated by user | Update `.env` on VPS, restart container. |
| `data/fluentloop.sqlite` corrupted | Restore from latest `data/backups/db-YYYY-MM-DD.sqlite` (14-day rotation, see EPIC-08). |
| VPS lost / wiped | Re-deploy from git, re-add secrets, restore DB from off-VPS backup if you keep one. Off-VPS backup is a future enhancement. |
| Token leaked publicly | Rotate token, audit recent bot activity via Telegram update history, rebuild commit history if leaked through git. |

## Pre-push checklist

Before pushing to a remote (when there is one):

1. `git status` — no `.env`, no `data/`, no `secrets/`, no `*.session`.
2. `python3 scripts/secret_scan.py` returns `secret-scan: ok`.
3. No real numeric Telegram user IDs in tracked files.
4. PRD / epic / ADR docs reflect any behavior change in this commit.
