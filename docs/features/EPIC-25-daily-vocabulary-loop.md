# EPIC-25 - Daily Vocabulary Loop

Status: In progress - all six stages implemented locally, not yet deployed

## Summary

EPIC-25 adds a lightweight daily delivery surface on top of the existing
learning engine. Instead of a single evening reminder that asks the learner to
open a 15-minute session, the bot reaches out three times a day with something
short and finishable: morning vocabulary cards, a midday micro-drill, and an
evening quiz poll.

This is a surface layer, not a second learning system. `LearningItem`,
`ReviewState`, the Pimsleur GIR ladder in `srs.py`, the 14 exercise types, and
the answer-checking path are reused unchanged. What EPIC-25 adds is the part
FluentLoop never had: per-user time slots, a card message format, multiple
choice quizzes, an explicit "graduated" end state for an item, an onboarding
wizard, and adding your own words by sending a plain message.

Delivery gate remains:

```text
development -> documentation -> tests -> commit -> deploy -> post-deploy smoke -> fix/repeat
```

Commit and deploy are still explicit user-approved gates.

## Validation Evidence

- Local gate: `pytest -q` -> `288 passed`; `ruff check src tests scripts`,
  `python scripts/secret_scan.py`, and `python -m fluentloop --check` clean.
- Migration `0004_epic25` verified idempotent and reversible against a fresh
  SQLite file, including a re-run of the head revision after a stamp.
- Poll construction verified against the installed Telethon 1.36.0 TL schema
  offline: `TextWithEntities` wrappers, `b"0"`..`b"3"` option ids,
  `quiz=True`, `public_voters=True`, `correct_answers=[b"2"]`.
- Word bank: 164 entries, ids and texts unique, every topic / kind / fun set
  covered, every entry carrying a meaning, an example, and three distractors.
- Commit: pending user approval.
- Deploy: pending.
- **Not yet verified:** that `UpdateMessagePollVote` actually reaches the
  `events.Raw` handler on the deployed Telegram layer. It travels the `qts`
  update sequence and can only be confirmed live. The inline-button fallback
  and `VOCAB_QUIZ_POLLS=0` exist for exactly this risk.

## Scope

### In v1

- Three daily slots per user, in the user's own timezone, defaulting to
  08:00 / 13:00 / 19:00 and configurable via `/settings`.
- Morning: `words_per_day` cards, each with an example sentence and a short
  definition.
- Midday: one micro-drill from the existing exercise registry; every third day
  it is a "write your own sentence" task.
- Evening: a native Telegram quiz poll with one correct answer and three
  distractors.
- Graduation: an item that reaches a 120-day interval with at least four
  successes leaves the review rotation as `status="graduated"`.
- `/pause` and `/resume` stop and restart the daily pushes.
- Sending a plain word list adds those items, with priority over bank content.
- An onboarding wizard picks topics, vocabulary kinds, starter list size, and
  words per day, then seeds a starter list from the in-repo word bank.
- Qwen joins DeepSeek and OpenAI as a selectable LLM provider.

### Not in v1

- Gamification, XP, streak leagues, lives.
- Voice, TTS, STT.
- Web UI or Telegram Mini App.
- Replacing the existing `/today` session flow. Bare `/today` keeps its current
  meaning; only `/today <n>` is new.
- Per-user cron jobs. Slot timing is resolved by a single minute tick.
- Sharing vocabulary between users. `LearningItem` stays per-user, per ADR-0008.

## Core Mechanisms

1. **Per-user slot dispatch**
   - One `vocab_loop_tick` cron job runs every minute and resolves each user's
     local time from `User.timezone`.
   - A slot is due inside a 90-minute catch-up window, so a restart does not
     lose the morning push.
   - A `vocab_deliveries` row is inserted before sending. Its unique constraint
     on `(user_id, local_date, slot, seq)` is the lock that makes the tick
     idempotent across restarts, overlapping ticks, and the repeated hour at the
     end of DST.
   - See ADR-0012.

2. **Graduation**
   - `is_graduation_ready` in `srs.py` checks for a 120-day interval, a passing
     last result, and at least four successes.
   - `apply_review` wraps `record_result` and flips `LearningItem.status` to
     `graduated`. Every existing query already filters on `status == "active"`,
     so graduated items leave the rotation with no query changes.
   - `/learned <word>` forces graduation; `item:restore` undoes it.

3. **Native quiz polls**
   - Telethon raw `InputMediaPoll` with `quiz=True` and `public_voters=True`.
   - The poll id is stored on the delivery row, so an incoming
     `UpdateMessagePollVote` maps back to the item and feeds `apply_review`.
   - See ADR-0011.

4. **Content**
   - Distractors are pre-baked into the in-repo word bank, so the common path
     costs nothing.
   - For user-added words the bot first tries the learner's own items, then
     falls back to the LLM once per item and caches the result.
   - `seeds/wordbank_v1.jsonl` currently holds 164 entries. The wizard offers
     starter sizes up to 500, so a large pick is capped by the bank and the
     completion message says so. Growing the bank is additive: append lines,
     and `scripts/seed_wordbank.py` imports the delta.

5. **Own words first**
   - `learning_items.priority` is `10` for user-added items and `0` otherwise.
   - It is the first `ORDER BY` term in `srs.get_due_items` and a scoring bonus
     in `learning_engine.score_learning_items`.

## Stages

| Stage | Content | Gate |
|---|---|---|
| 1 | Schema deltas, migration 0004, `vocab_prefs.py`, graduation, priority | `test_epic25_vocab_model.py`, `test_epic25_migration.py` |
| 2 | `vocab_loop.py` renderers, new commands, bulk add | `test_epic25_vocab_commands.py` |
| 3 | Minute-tick dispatcher, delivery rows, scheduler bug fixes | `test_epic25_vocab_scheduler.py` |
| 4 | Native quiz polls, distractors | `test_epic25_quiz_polls.py` |
| 5 | Word bank, onboarding wizard | `test_epic25_wordbank.py`, `test_epic25_onboarding.py` |
| 6 | Qwen provider, documentation sweep | `test_epic25_qwen_provider.py` |

Stage 2 is the minimum shippable slice: the whole loop is usable by hand before
any automatic push exists.

## Fixes carried by this epic

These are pre-existing defects found while planning EPIC-25. Each is a one-line
fix in code the epic already touches.

1. `send_reminders` computed the current day in UTC while
   `PracticeSession.target_date_local` is written in the user's timezone, so a
   non-UTC learner could be nudged during an active session.
2. `run_pre_generation` had the same UTC/local mismatch.
3. `User.reminder_time` was validated but never read; the reminder used the
   global default. The slot dispatcher makes the column meaningful again.
4. Scheduler jobs were registered as `lambda: asyncio.create_task(...)`. The
   task reference was never held, so the task could be garbage collected mid
   flight and exceptions were swallowed. `AsyncIOScheduler` takes coroutine
   functions directly.

## Related documents

- PRD.md sections 8, 12, 14, and 21.
- `docs/adr/0010-multi-provider-llm-gateway.md`
- `docs/adr/0011-native-telegram-quiz-polls.md`
- `docs/adr/0012-per-user-slot-dispatcher.md`
- `docs/architecture.md` sections 1, 3, and 5.
