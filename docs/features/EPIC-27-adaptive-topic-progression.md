# EPIC-27 — Adaptive topic progression

**Status:** Done — implementation and local validation complete
**PRD references:** §6 P1, §14 Adaptive topic progression
**ADR:** [ADR-0014](../adr/0014-adaptive-topic-progression.md)

## Goal

Make the simple stream develop topic-specific B2 ability, verify transfer and
written use, and open introductory C1 after complete strong B2 coverage.

## Implementation

- Reviewed B2/B2+/introductory C1 variants for all ten supported topics.
- Versioned topic/stage/role/variant metadata in questions and attempts.
- Derived per-user evidence with spaced distinct practice, unseen transfer,
  written-use requirements, and repair after repeated difficulty.
- Selection respects stage gates, transfer holdout, cooldowns, and source labels.
- Topic progress explains evidence and the next step without claiming CEFR
  certification.
- Automatic validated variants attach to approved items; they preserve
  provenance and avoid adding unapproved concepts.

## Acceptance and verification

- Repeated same-day/familiar/legacy answers cannot unlock harder stages.
- Distinct spaced evidence unlocks only its topic; all topics gate C1.
- Transfer exposure, stopped snapshots, failures, and restarts are respected.
- Recognition alone cannot establish strong B2; optional skips are harmless.
- Production belongs to the originating topic/profile and rejects copied text.
- Repeated errors trigger repair without single-error regression.
- Duplicate/foreign answers preserve atomicity and user isolation.
- Content/importer/generation tests and standard local gates pass.

## Validation

On 2026-10-03, the full suite passed: 481 tests, with eight existing Alembic
deprecation warnings. Ruff, application construction, both bank dry runs and
diff checks passed. The new bank contains 270 questions, 180 practice and 90
reserved transfer, with thirty topic-stage plans. Independent semantic review
covered all questions and rechecked the revised C1 content, contextual keys,
explanations and production tasks; the pack has no literal answer leaks or exact
duplicate prompts/correct answers.

Tests cover real-bank progression across three days, delayed transfer, the
all-topic C1 gate, repeated-error repair, source quarantine, genuine production
provenance, near-copy rejection, withheld content across generic flows, daily
maintenance concurrency, provider failures and preserved personal data. An
isolated check against the configured model generated and independently reviewed
one accepted variant; two independent authored writing samples (grammar and
phrase use) received genuine model evaluations. Those checks changed no live
learner history.

Activation and rollback: [adaptive-learning runbook](../runbooks/adaptive-learning.md).
The curriculum stage labels are editorial learning targets, not validated CEFR
certification.
