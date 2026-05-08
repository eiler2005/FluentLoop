# EPIC-10 — Answer checking and feedback

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §16, §22.3, §25.3, §27
**Depends on:** EPIC-08 (calls into this), EPIC-09, ADR-0003
**Blocks:** EPIC-11 (consumes mistake events from here)

## Goal

When the user answers an exercise, the bot judges the answer, returns
structured feedback, updates the spaced-repetition state (EPIC-06), and
optionally logs a mistake event (EPIC-11). The user must be able to
override the AI verdict and dispute bad feedback — without that loop, the
bot can silently train mistake patterns from its own miscalls.

## In scope

- AI checking call per PRD §25.3 schema: `status` (correct / partial /
  incorrect), `corrected_answer`, `natural_answer`, `mistake_summary`,
  `why_wrong`, `rule`, `better_variants`, `micro_drill`, `teacher_note`,
  `detected_mistake_type`, `should_create_mistake_event`,
  `should_create_or_update_mistake_pattern`.
- Light tier (per ADR-0003) for cloze / exact-match types; heavy tier
  for grammar rewrite / follow-up / "more natural" suggestions.
- Format the feedback in chat as in PRD §16: status, corrected,
  natural, explanation, related rule, "I'll add this as a weak point"
  hint when applicable.
- **User override** of the AI verdict: every feedback message has inline
  buttons `[Got it]` and `[I disagree]`. `[I disagree]` opens a small
  flow: pick a reason (`AI was wrong`, `Stylistic, not an error`,
  `Mine was equally valid`, `Other`) and optionally type a note.
- **Dispute log:** every `[I disagree]` writes to
  `feedback_disputes/YYYY-MM-DD.jsonl` with the original prompt, the
  user's answer, the AI verdict, and the user's reason. This file is
  gitignored per `data/` policy.
- **Difficulty override:** the user may also tap `[Hard]` on a verdict
  the AI marked `correct` to indicate the answer cost effort. EPIC-06
  uses this to advance the schedule less aggressively.
- Trigger EPIC-06 `record_result(item_id, "Again"|"Hard"|"Good"|"Easy")`
  with the final (post-override) result.
- When `should_create_mistake_event=true`, write a `MistakeEvent` for
  EPIC-11 to consume.
- When the AI suggests a *new* candidate item ("gently push back on"),
  surface it as a candidate via the EPIC-04 approval flow — never
  auto-add.
- `/feedback explain <attempt_id>` and the `Teacher details` button render
  the full stored teacher breakdown. They should not call the model again
  unless stored feedback lacks the detailed fields.
- `/skip` and `Skip / show answer` record a skipped attempt and show the
  expected answer with a concise teacher explanation, without creating a
  mistake event.

## Out of scope

- Re-judging old answers after the AI is upgraded — defer.
- Showing the dispute log inside Telegram — log lives on disk for now.
- Per-user tunable strictness — defer.

## Acceptance criteria

- After every answer, the user sees a feedback message within ~3
  seconds (light tier) / ~6 seconds (heavy tier).
- The five-field structure from PRD §16 is present whenever applicable.
- Teacher feedback includes the layered fields from PRD §25.3 whenever the
  checker can produce them, and degrades gracefully when deterministic fallback
  only has a simpler explanation.
- `[Got it]` accepts the AI verdict; `[I disagree]` opens the reason
  picker and writes to the dispute log.
- `[Hard]` on a "correct" verdict downgrades to `Hard` for SRS purposes.
- A `MistakeEvent` is created exactly when the (post-override) result
  is `Again` or the AI's `should_create_mistake_event=true` AND the
  user did not dispute.
- Disputed answers do **not** trigger a `MistakeEvent` (avoid training
  on AI miscalls).
- Suggested-new-candidate flow goes through EPIC-04 — no silent auto-
  adds.
- Skipped exercises are stored as skipped attempts, reveal the correct answer,
  and do not create mistake events.

## Open questions

- Where to render the dispute reason picker — inline keyboard in the
  same message, or a follow-up message? Default: inline keyboard, edit
  the original message after pick.
- Should `[Hard]` also be available on `partial` / `incorrect` verdicts?
  Default: no; those are already non-Good. Only on `correct`.
- Time-bounded override: if the user moves on to the next exercise, can
  they still override the previous? Default: no — override window is
  the active feedback message only. Simpler.

## Verification plan

1. Answer "We must change the architecture immediately." to a hedging
   prompt; AI should suggest the more diplomatic rewrite.
2. Tap `[I disagree]` → "Stylistic, not an error" → confirm the
   `feedback_disputes/<today>.jsonl` row appears and SRS records
   `Good` (not `Again`).
3. Answer correctly to a cloze; tap `[Hard]`; confirm SRS records
   `Hard`, not `Good`.
4. Answer correctly to several exercises and verify no
   `MistakeEvent` rows are created.
5. Trigger an AI suggestion of a new expression; verify it appears in
   the EPIC-04 approval queue, not in `learning_items`.

## Notes from implementation

- Added stub AI checking, feedback-to-SRS mapping, mistake-event creation, and
  JSONL dispute logging.
- Feedback messages now include attempt ids, related rules when available, and
  a `/dispute <attempt_id> <reason>` fallback.
- `/dispute` writes the JSONL audit row, marks the attempt as disputed, and
  removes the latest matching mistake event so disputed answers do not train
  mistake patterns.
- Feedback now carries inline `Got it`, `I disagree`, `AI was wrong`, and
  `Style issue` buttons; each dispute callback writes the same JSONL audit row
  as `/dispute <attempt_id> <reason>`. The command fallback remains deployed.
- Correct-answer feedback now also carries `Hard`; tapping it converts the
  latest SRS `Good` result for the attempt's target items into `Hard` without
  double-counting the review.
- `AnswerFeedback.suggested_candidates` now queues AI-suggested new items as
  pending EPIC-04 candidates under a `teacher_feedback` source material; they
  are surfaced via `/candidates <material_id>` and are never auto-added.
- `AnswerFeedback` now carries layered teacher-feedback fields: mistake
  summary, why-wrong explanation, practical rule, better variants, micro-drill,
  and teacher note.
- Telegram feedback stays compact after each answer and offers
  `/feedback explain <attempt_id>` / `Teacher details` for the full stored
  teacher breakdown without another model call.
