# ADR-0011 — Native Telegram quiz polls over Telethon raw API

**Status:** Accepted
**Date:** 2026-08-17
**Deciders:** Denis Ermilov

## Context

EPIC-25 delivers an evening vocabulary quiz. The target experience is
Telegram's native quiz poll: four options, a marked correct answer, and result
bars in the message itself.

FluentLoop has two outbound Telegram paths (ADR-0002, ADR-0005):

1. Telethon in bot mode over MTProto, which owns the update stream.
2. A raw HTTP Bot API helper in `telegram_bot_api.py`, used for forum topics,
   pinning, and `setMyCommands`.

The Bot API path can call `sendPoll`. It cannot receive the answer: votes
arrive as updates, there is no `getUpdates` loop in the process, and adding one
would fight Telethon for the update sequence. A poll sent that way would render
correctly and silently discard every answer, which would quietly disable the
SRS feedback the quiz exists to produce.

## Decision

Send quiz polls through Telethon's raw API and receive votes with a fourth
Telethon handler.

- Build `InputMediaPoll(poll=Poll(..., quiz=True, public_voters=True), ...)` in
  `src/fluentloop/bot/polls.py` and send it with `client.send_file`, which
  accepts a bare `InputMedia` and returns a parsed `Message` carrying the
  server-assigned `poll.id`.
- **`public_voters=True` is mandatory.** Telegram delivers no
  `UpdateMessagePollVote` at all for an anonymous poll. This is the single
  constraint the whole design rests on.
- Option ids travel as `bytes`. Use ASCII index strings (`b"0"`..`b"3"`) so the
  vote handler recovers the index with `int(raw.decode())`.
- Wrap the poll question and each option in `TextWithEntities` — required by the
  Telethon 1.36 TL schema.
- `solution` and `solution_entities` must be **both set or both absent**.
  Telethon only asserts this while serialising the request, so a poll built
  with a solution and no entities looks valid until it is sent. Tests must
  call `bytes()` on the media to reach that check.
- Persist `(poll_id, message_id)` on the `vocab_deliveries` row. An incoming
  vote is resolved by an indexed lookup on `poll_id`.
- `resolve_vote` is pure database work with no Telethon import, so the entire
  vote path is testable offline.
- Do **not** add `sendPoll` to `telegram_bot_api.py`.

## Consequences

**Positive**

- The learner gets the native quiz UI, and every answer feeds `srs.apply_review`.
- A vote for a poll the database does not know about (for example after a
  restore) resolves to `None` and is ignored rather than raising.

**Negative**

- `public_voters=True` means the bot can see who voted. In a one-to-one chat
  this is information the bot already has, but the flag would be a privacy
  consideration if polls were ever posted to a group.
- `UpdateMessagePollVote` travels the `qts` update sequence. **Confirmed in
  production on 2026-08-17**: a poll sent over MTProto received the learner's
  vote through the `events.Raw` handler and updated `ReviewState`. Telethon
  does deliver qts updates to bots.

**Neutral**

- The scheduler always prepares the inline-button quiz first and only then
  attempts the poll, so the fallback costs one extra render.

### Amendment, 2026-08-17: a quiz is a sequence, not one question

The evening slot delivers a whole quiz rather than a single poll. Each
question is its own `vocab_deliveries` row (`seq` 0..N-1) carrying its own
`poll_id`, so vote resolution is unchanged — the lookup is still one indexed
read on `poll_id`.

What the sequence adds:

- The `seq=0` claim is the idempotency lock for the entire set, so a tick
  that fires twice inside the catch-up window does not restart the quiz.
- Rows stay `claimed` until answered. That is deliberate: it is what lets
  `/quiz` resume at the first unanswered question, and what `/stop` counts
  when it reports paused questions.
- On-demand quizzes use the slot name `"quiz"` rather than `"evening"`, so a
  `/quiz` earlier in the day cannot consume the scheduled evening delivery.
- The answer to the last question carries the wrap-up score instead of a
  bare verdict.

Question count is a per-user preference (`quiz_size`, one of 5/10/15/20,
default 10), not a constant.

## Fallback

`send_quiz_poll` is wrapped in `try/except`. On any failure the tick sends the
inline-button quiz instead (`vocab:ans:<delivery_id>:<index>`, routed through
the existing callback dispatcher) and records `payload_json["mode"] = "buttons"`.

`VOCAB_QUIZ_POLLS=0` disables the raw path entirely and pins the bot to
buttons, which is the rollback lever if the qts assumption turns out to be
wrong on the deployed layer.

## Alternatives considered

- **Bot API `sendPoll`.** Rejected: cannot receive votes, as above.
- **Inline buttons only.** Workable, and retained as the fallback, but it does
  not match the requested experience and loses the poll result bars.
- **Raw `messages.SendMediaRequest`.** Equivalent on the wire, but returns an
  `Updates` container that must be parsed by hand to find the poll id.
  `client.send_file` does that already.
