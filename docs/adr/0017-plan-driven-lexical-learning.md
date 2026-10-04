# ADR-0017 — Three-part Study allocation with lexical learning

**Status:** Accepted

**Date:** 2026-10-04

## Decision

- Add a reviewed, packaged sense-level lexical bank for words, collocations,
  phrasal verbs and frames. Public authored content is approved under the owner's
  request. It is selected as immutable Study snapshots, like module questions,
  without creating active LearningItems or changing the database schema.
- Use three disjoint allocation buckets: `general_share` default 30,
  `lexical_share` default 30, and work as the remainder (40 for new plans).
  A lexical question retains its truthful contextual strand, but counts only in
  the lexical bucket. Balance answered normal-mode questions,
  never screen time or optional writing. Record both shares; changed allocations
  begin a new cohort without resetting historical evidence or pending snapshots.
- Legacy version-1 plans lacking `lexical_share` validate and normalise to zero,
  preserving their behaviour. New defaults include it; explicit edits enable it.
  Update only the authorised owner pilot to 30 during release, preserving all
  existing preferences. Accept a bounded 0–60% lexical share with general plus
  lexical at most 90%, retaining at least 10% module/language work. The offline
  editor and Telegram use the same validation contract.
- Use stable sense and question IDs. A sense carries Russian/English glosses,
  an original example, grammar frame, register, plain alternative and source
  attribution. Curriculum stage labels place authored tasks in the programme;
  they are not calibrated CEFR ratings of expressions. B2/B2+ expressions remain teachable before
  C1; C1-only tasks require the existing ten-topic gate.
- Lexical slots include first exposure and due retrieval. Prefer a controlled
  mixture of unseen senses and due reviews when both exist, avoid recent cards,
  and enforce successful 24-hour review spacing and five-other-answer error
  retries. If the requested context or exercise pool is unavailable, annotate
  the actual fallback; never silently repeat early. Familiar mode selects only
  previously answered questions and cannot supply mastery or allocation credit.
- Reuse atomic per-user session claims and optional BONUS capture. Persist
  lexical provenance in attempts. Recognition does not grant module/adaptive
  mastery; genuine independent writing is tracked separately by sense. Exclude
  copied examples, reference choices, reused answers, model rewrites, unchecked
  fallback and familiar responses. Spaced independent use is a local milestone.
- Writing tasks name the expression but do not supply its definition again.
  Independent application means independently authored guided use in a new
  situation, not uncued lexical retrieval or spontaneous-fluency assessment.
- Progress and session summaries show lexical exposure/recognition/writing,
  new-versus-review counts and missing evidence. Content issue reports quarantine
  the disputed sense for that user; they do not mutate the public pack.

## Verification

Validate the bank, sense distinctions and examples. Exercise three-part allocation,
new/review balance, domain labels, plan compatibility, focus/pauses, C1 access,
empty-pool fallbacks, immutable resume, foreign/duplicate callbacks, independent
writing, local-day spacing and quarantine. Check export/editor parity, packaged
assets, docs, the full test gate and a rollback smoke on production.
