# EPIC-03 — Material upload

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §9 (material upload), §22.1 (after-lesson scenario)
**Depends on:** EPIC-02
**Blocks:** EPIC-04

## Goal

The user can dump lesson notes / word lists / teacher feedback into the bot
as plain text and the bot stores them as a `SourceMaterial` row, ready to
be processed by EPIC-04 (AI extraction).

## In scope

- `/upload` command: bot prompts for material, then accepts the next text
  message (FSM state) as a source.
- Free-form text messages (without `/upload` first) — also accepted; the
  bot offers buttons "Treat as lesson material" / "Cancel".
- `SourceMaterial` table per PRD §24: `id`, `user_id`, `type`, `raw_text`,
  optional `summary`, `created_at`.
- `type` enum: `lesson_notes`, `word_list`, `expression_list`, `homework`,
  `exercise`, `teacher_feedback`, `other`. Bot asks; default to `other`.
- Upload size cap (e.g. 10 KB / ~2000 words). If exceeded, suggest the
  user paste in chunks.
- Acknowledge with "Got it. Processing…" before handing off to EPIC-04.

## Out of scope

- PDF upload — PRD §9 lists this as P1.
- Image / screenshot upload — PRD §9 P1.
- Voice messages — PRD §6 P2.
- Auto-classification of `type` — defer; user picks for MVP.
- Teacher-feedback templates / structured forms — PRD §29 / future.

## Acceptance criteria

- `/upload` prompts for material; the next user message is stored as a
  `SourceMaterial` row.
- A free-text message offers "Treat as lesson material" inline button; on
  accept, stored same way.
- Material >10 KB triggers a friendly "please paste in chunks" reply and
  is **not** stored.
- The stored row has `raw_text` exactly equal to the user's message and
  `created_at` set.
- After storage, the bot replies "Got it. Extracting…" and EPIC-04 takes
  over (until EPIC-04 lands, just say "Stored. Extraction not yet
  implemented.").

## Open questions

- FSM library choice depends on ADR-0002 (`aiogram` has FSM built in;
  `python-telegram-bot` uses `ConversationHandler`).
- Should we de-duplicate near-identical uploads (cosine similarity over
  recent `SourceMaterial`)? Defer — premature optimization for one user.

## Verification plan

1. `/upload` and paste 10 lines of mixed expressions and grammar notes.
2. Confirm `SourceMaterial` row exists in DB with the exact text.
3. Send a free-text message; pick "Treat as lesson material"; confirm
   another row.
4. Send a 50 KB blob; confirm refusal and no row created.

## Notes from implementation

- Added `SourceMaterial` storage with the 10 KB cap and an extraction handoff.
- Added `/upload` FSM behavior: the next free-text message is stored and
  passed to extraction.
- Oversized upload errors are returned as friendly Telegram replies rather
  than bubbling exceptions.
