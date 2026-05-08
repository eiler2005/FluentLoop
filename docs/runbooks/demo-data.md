# Demo Data Seeding

Use this during audit and post-deploy smoke testing to ensure the bot has
enough realistic data to exercise all MVP paths. The script is idempotent and
uses the stub AI provider internally, so it does not spend external AI credit.

## Local

```bash
uv run --python 3.11 python scripts/seed_demo_data.py
```

For an isolated audit database:

```bash
TELEGRAM_ALLOWED_USER_ID=<telegram-allowed-user-id> \
  uv run --python 3.11 python scripts/seed_demo_data.py \
  --db-url sqlite:////tmp/fluentloop-audit.sqlite
```

## VPS

After deploy:

```bash
ssh <ssh-user>@<vps-host> \
  'cd /opt/fluentloop-bot && docker compose exec -T fluentloop python scripts/seed_demo_data.py'
```

## What It Creates

- One user from `TELEGRAM_ALLOWED_USER_ID`.
- Demo learning items across expressions, words, grammar rules, and mistake
  patterns.
- Three 15-minute B2+/C1- demo lessons:
  stakeholder alignment and polite pushback, incident update and risk
  mitigation, and product/architecture trade-offs for London/New York
  collaboration.
- A lesson-material upload with stub-extracted candidates and approval into
  learning items.
- A promoted high-confidence mistake pattern.
- A cached/current practice session shape for today. In the current Learning
  Engine, live `/today` should produce a dynamic 15-20 micro-drill session when
  enough material exists.
- One completed practice session with attempts for `/stats` coverage.

The seeded rows use `demo` tags or fixed demo text so repeated runs do not keep
growing the database.
