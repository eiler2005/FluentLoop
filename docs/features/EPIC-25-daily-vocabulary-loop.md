# EPIC-25 - Daily Vocabulary Loop

Status: Done - implemented, deployed, and validated in production

## Summary

EPIC-25 adds a lightweight daily delivery surface on top of the existing
learning engine. Instead of a single evening reminder that asks the learner to
open a 15-minute session, the bot reaches out three times a day with something
short and finishable: morning vocabulary cards, a midday micro-drill, and an
evening quiz.

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

- Local gate: `pytest -q` -> `312 passed`; `ruff check src tests scripts`,
  `python scripts/secret_scan.py`, and `git diff --check` clean.
- Migration `0004_epic25` verified idempotent and reversible against a fresh
  SQLite file, and applied on the VPS (`alembic_version = 0004_epic25`).
- **Native quiz poll confirmed end to end in production**: poll sent via
  MTProto (`poll_id=5195385113474506175`, `mode=poll`), the learner's vote
  arrived through the `events.Raw(UpdateMessagePollVote)` handler, and
  `ReviewState` recorded the result. This closes the one risk that could not
  be verified offline - `UpdateMessagePollVote` travels the `qts` update
  sequence, and Telethon does deliver it to bots.
- Midday drill delivered and answered in production; morning cards verified
  via `/today <n>`.
- Per-user timezone dispatch confirmed: the tick fired at the learner's local
  slot time, and users in other timezones were correctly skipped.
- Word bank: 164 entries, ids and texts unique, every topic / kind / fun set
  covered, every entry carrying a meaning, an example, and three distractors.
- Live LLM check against Qwen: `check_answer` returned the correct verdict and
  correction; `usage_log` attributed the call to `provider=qwen`,
  `model=qwen3.7-flash`.

## Scope

### In v1

- Three daily slots per user, in the user's own timezone, defaulting to
  08:00 / 13:00 / 19:00 and configurable via `/settings`.
- Morning: `words_per_day` cards, each with an example sentence and a short
  definition.
- Midday: one micro-drill from the existing exercise registry; every third day
  it is a "write your own sentence" task.
- Evening: a native Telegram quiz poll with one correct answer and three
  distractors, falling back to inline buttons.
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

### 1. Per-user slot dispatch

One `vocab_loop_tick` cron job runs every minute and resolves each user's local
time from `User.timezone`. A slot is due inside a 90-minute catch-up window, so
a restart does not lose the morning push.

A `vocab_deliveries` row is claimed before sending. Its unique constraint on
`(user_id, local_date, slot, seq)` is the lock that makes the tick idempotent
across restarts, overlapping ticks, and the repeated hour at the end of DST.

**The claim runs inside a SAVEPOINT.** A plain `session.rollback()` on the
duplicate-claim path would discard every delivery already recorded in the same
tick - see "Production defects found" below.

Accounts the command handlers would reject (seed and demo rows) are skipped, so
they do not generate a failed delivery and a Telegram traceback per slot.

See ADR-0012.

### 2. Graduation

`is_graduation_ready` in `srs.py` checks for a 120-day interval, a passing last
result, and at least four successes. `apply_review` wraps `record_result` and
flips `LearningItem.status` to `graduated`. Every existing query already filters
on `status == "active"`, so graduated items leave the rotation with no query
changes. `/learned <word>` forces graduation; `item:restore` undoes it.

### 3. Native quiz polls

Telethon raw `InputMediaPoll` with `quiz=True` and `public_voters=True`. The
poll id is stored on the delivery row, so an incoming `UpdateMessagePollVote`
maps back to the item and feeds `apply_review`. See ADR-0011.

### 4. Content and language

Distractors are pre-baked into the in-repo word bank, so the common path costs
nothing. For user-added words the bot first tries the learner's own items, then
falls back to the LLM once per item and caches the result.

**Prompts are English; Russian is revealed only after answering.** Items arrive
from several sources and some carry a Russian gloss in `meaning` with the
English one in `explanation`, or the reverse. `vocab_loop.english_definition`
picks the Cyrillic-free gloss for cards and quiz questions, and the evening slot
prefers a candidate it can ask in English before falling back. After the learner
answers, `russian_definition` supplies the translation - for the answer itself
and for each rejected option.

**Distractors must not be second correct answers.** Two guards, because ranking
that prefers similar items is exactly what produces synonyms:

- `select_distractors` ranks by *ascending* shared content-tag count. Candidates
  are already restricted to the learner's own items of the same type, so they
  are plausible without matching tags; matching tags means matching *function*.
  Provenance tags (`demo`, `wordbank`, `user_added`, `seed`) do not count.
- `is_near_synonym` compares stemmed content words of the two glosses and drops
  candidates above 1/3 overlap.

`seeds/wordbank_v1.jsonl` currently holds 164 entries. The wizard offers starter
sizes up to 500, so a large pick is capped by the bank and the completion
message says so. Growing the bank is additive: append lines, and
`scripts/seed_wordbank.py` imports the delta.

### 5. Own words first

`learning_items.priority` is `10` for user-added items and `0` otherwise. It is
the first `ORDER BY` term in `srs.get_due_items` and a scoring bonus in
`learning_engine.score_learning_items`.

## Data model

Three deltas, migration `0004_epic25`:

| Change | Why |
|---|---|
| `users.preferences_json` (JSON) | Slot times, pause flag, words/day, topics, kinds, sets, starter size, onboarding stamp. Read and written together, never queried individually, so one blob beats eight columns. |
| `learning_items.priority` (int, indexed) | Makes "own words first" a plain `ORDER BY` instead of a JSON path expression. |
| `vocab_deliveries` (table) | One row per delivered unit. Serves slot idempotency *and* the `poll_id -> item` lookup. |

Everything else rides on existing JSON: MCQ distractors in
`LearningItem.metadata_json["mcq"]`, provenance in `metadata_json["source"]`,
wizard progress in `BotState.payload`, and `graduated` as a value of the
existing `LearningItem.status` column.

> `vocab_prefs.set_prefs` always reassigns the whole dict. SQLAlchemy's `JSON`
> type is not mutation-tracked, so in-place edits are silently lost.

## Commands

Extended and aliased, never duplicated.

| Command | Behaviour |
|---|---|
| `/today` | Unchanged: starts the full 15-minute session. |
| `/today <n>` | New: shows n vocabulary cards, clamped to 1-20. |
| `/words` | Counts by status including graduated, plus the 20 nearest-due items. |
| `/more <word>` | Meaning, synonyms, collocations, examples. |
| `/learned <word>` | Graduates the item, parks `due_at` 730 days out, offers Undo. |
| `/delete <word>` | Soft-deletes (archives), offers Undo. |
| `/pause`, `/resume` | Toggle the daily pushes. |
| `/setup` | Runs the onboarding wizard. |
| `/skip` | Skips an open daily drill first, else the existing practice skip. |
| `/settings` | Three new rows: slot times and words per day, under the existing `settings:` callback prefix. |
| `/help` | Extended with a "Your day" section covering the three slots, how to answer each, the language rule, graduation, and adding your own words. |

`telegram_bot_api.BOT_COMMANDS` and `handlers.command_catalog()` both grew by
the same eight entries and are asserted to stay in sync.

## Production defects found

Four defects surfaced only against live Telegram. Each has a regression test
that fails without its fix.

**1. Slot claim rolled back the whole tick.** `claim_slot` called
`session.rollback()` when the unique constraint rejected a duplicate. That
rolls back the entire session, so a later duplicate erased every delivery row
already recorded in the same tick - including ones whose message had already
been sent. Symptom: the evening quiz was re-sent every minute for the whole
90-minute catch-up window. Fixed with `session.begin_nested()`.

**2. Quiz polls were rejected at serialisation.** Telethon asserts that
`InputMediaPoll.solution` and `.solution_entities` are either both set or both
absent, and only checks in `_bytes()`. Passing a solution without entities made
every poll fail on send, so the loop silently fell back to inline buttons. The
test now serialises with `bytes()`; asserting on attributes could not reach the
check.

**3. Quizzes had two defensible answers.** Distractor ranking preferred
candidates sharing tags, which reliably pulled in synonyms - a real quiz offered
both "it may be worth" (*Useful hedge for recommendations*) and "I would lean
towards" (*A natural way to make a recommendation without overclaiming*). Fixed
by inverting the tag preference and adding `is_near_synonym`.

**4. Mixed-language prompts.** See "Content and language" above.

## Pre-existing defects fixed in passing

These were in code EPIC-25 touches.

1. `send_reminders` and `run_pre_generation` computed dates in UTC while
   `PracticeSession.target_date_local` is written in the user's timezone, so a
   non-UTC learner could be nudged during an active session.
2. Scheduler jobs were registered as `lambda: asyncio.create_task(...)`. The
   task reference was never held, so the task could be garbage collected mid
   flight and exceptions were swallowed.
3. `User.timezone` and `User.reminder_time` were validated but never read; the
   slot dispatcher makes them load-bearing.
4. `scripts/deploy.sh` created a `pre-migration-*.sqlite` snapshot on every
   deploy and never pruned it - `BACKUP_RETENTION_DAYS` only covers the
   scheduled `db-*.sqlite` files. Fifteen had accumulated on the VPS. It now
   keeps the newest `PRE_MIGRATION_KEEP` (default 5).

## Stages

| Stage | Content | Tests |
|---|---|---|
| 1 | Schema deltas, migration 0004, `vocab_prefs.py`, graduation, priority | `test_epic25_vocab_model.py`, `test_epic25_migration.py` |
| 2 | `vocab_loop.py` renderers, new commands, bulk add | `test_epic25_vocab_commands.py` |
| 3 | Minute-tick dispatcher, delivery rows, scheduler bug fixes | `test_epic25_vocab_scheduler.py` |
| 4 | Native quiz polls, distractors | `test_epic25_quiz.py`, `test_epic25_quiz_polls.py` |
| 5 | Word bank, onboarding wizard | `test_epic25_wordbank.py`, `test_epic25_onboarding.py` |
| 6 | Qwen provider, documentation | `test_epic25_qwen_provider.py` |

Stage 2 was the minimum shippable slice: the whole loop is usable by hand
before any automatic push exists.

## Operational notes

- The VPS is a shared Hetzner box. `scripts/deploy.sh` aborted twice at the
  Alembic step because the extra container pushed it over its memory budget and
  sshd dropped the connection. Those deploys were completed manually with
  `rsync` + `docker compose up -d --build`. A migration-bearing deploy needs
  headroom; consider swap.
- `VOCAB_QUIZ_POLLS=0` pins the evening slot to inline buttons. That is the
  rollback lever if the raw poll path ever regresses.

## Related documents

- PRD.md sections 8, 12, 14, and 21.
- `docs/adr/0010-multi-provider-llm-gateway.md`
- `docs/adr/0011-native-telegram-quiz-polls.md`
- `docs/adr/0012-per-user-slot-dispatcher.md`
- `docs/architecture.md` sections 1, 3, and 5.
- `docs/user-guide.md` section 3.5.
