# tests/

Test suite. Empty until [EPIC-01](../docs/features/EPIC-01-bot-foundation.md) starts.

Conventions (when populated):

- `pytest -q` is the entrypoint.
- Unit tests live next to the module they cover: `tests/test_srs.py`,
  `tests/test_exercises/test_cloze.py`.
- AI calls are mocked in unit tests. Manual end-to-end against a real
  test bot is documented in each epic's "Verification plan".
- No real Telegram token, no real AI key in fixtures or recordings.
