# ADR-0014 — Adaptive topic progression and transfer evidence

**Status:** Accepted
**Date:** 2026-10-03
**Deciders:** Denis Ermilov
**Amends:** [ADR-0013](0013-simple-learning-stream.md)

## Context

The manual stream has correct cooldowns but a finite recognition bank does not
establish transfer or strong B2 ability. The owner requests rising difficulty,
topic progress, introductory C1 gating, and automatic bank improvement.

## Decision

Keep the existing practice tables and atomic answer claims. Question snapshots
carry `adaptive = {version: 1, topic_id, stage, role, variant_id}`. Stages are
`b2`, `b2_plus`, and `c1_intro`; roles are `practice` and `transfer`. A dedicated
reviewed curriculum defines the complete topic coverage, independent of which
items happen to be subscribed. Select approved, active, personal copies only.

Compute per-profile topic evidence from immutable attempt feedback. Five
distinct correct normal practice variants across at least two local dates and
24 hours, with at least 80% accuracy on the last up to ten eligible practice
answers, establish practice readiness. A correct unseen transfer at least
24 hours after readiness unlocks B2+ from B2. At B2+, the same practice threshold,
two correct first-exposure transfers, and correct independent written production
after readiness establish strong B2. Every curriculum topic must meet that threshold before
introductory C1 becomes eligible. Recognition never graduates a learning item.
Older attempts without the versioned evidence contract count only as history.

Transfer questions are held out until practice is ready. A displayed question,
including a stopped unanswered snapshot, is no longer unseen. Familiar mode
cannot reveal held-out questions or contribute mastery. Save first-exposure and
selection-mode evidence before displaying; grading and next selection remain
inside the answer transaction. Repeat successful practice retains due/cooldown
rules. Two errors on distinct normal variants in a 14-day window invalidate the
affected stage's evidence and trigger repair; isolated errors retain progress.
Derived evidence is replayed chronologically, so restarts cannot erase repair.

Writing snapshots copy topic/stage provenance from the chosen parent question.
Correct feedback counts only for independent production, excluding a verbatim
copy, a model sentence with filler, or a near-copy. Provider-set provenance must
confirm a successful real model evaluation; substring-only stub/fallback checks
are saved as unchecked and cannot advance SRS or establish curriculum mastery.
Skips and unchecked responses create no failures.

Generated questions live in `LearningItem.metadata_json.simple_question_variants`
on an already approved item. They require structural/content validation,
independent review, unique content, and versioned provenance. Bounded generation
fills shortages for the current topic/stage/role through hourly background checks
or an operator CLI, sharing an opted-in daily budget (at most two candidates
per profile/day, twelve variants/item, 120/profile). This maintenance does not
send reminders or prepare full lessons. Learner-reported or review-rejected
questions are quarantined; their history cannot establish mastery. High error
rates trigger review, never an automatic answer-key rewrite. Transfer content
and the rest of the adaptive bank are excluded from generic advanced flows;
the adaptive stream owns their stage-aware exposure.

## Consequences

- No schema migration or shared progress state is required.
- Honest progress can show recognition ready while writing is still missing.
- The complete curriculum gate cannot be bypassed by subscribing to one topic.
- Small banks may exhaust while fresh variants are prepared; transfer is never
  silently converted into familiar recognition.
- Existing source labels and SRS history remain intact.
