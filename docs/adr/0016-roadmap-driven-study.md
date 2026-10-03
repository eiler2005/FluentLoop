# ADR-0016 — Execute the personal roadmap in Study

**Status:** Accepted

**Date:** 2026-10-03

**Supersedes:** ADR-0015's advisory-only selection decision. Its isolation,
portable-plan validation and separation from assessed language progress remain.

## Decision

- `/study` keeps one persisted, resumable simple stream and adds real authored
  module choice questions for all 48 modules and three stages. General scenarios
  remain genuinely general; grammar overlap never relabels a work question.
  Full options appear in the message with compact A/B/C buttons so Telegram
  cannot truncate the distinctions in long choices.
- The latest validated personal plan drives eligible module order, focus, pauses
  and general/work allocation. Balancing uses explicit practice units, not claimed
  measured learning time. Weekly minutes remain a suggested workload, not a cap.
  Snapshots tag their allocation share; changing it does not impose catch-up debt
  from questions answered under a different ratio.
- Existing adaptive questions continue as language practice within the work
  allocation, with bounded interleaving so neither language nor modules starve.
  Existing unseen transfer, SRS and genuine-production rules remain intact.
- Store module identity, stage and immutable content snapshots in exercises and
  attempt feedback. Use existing per-user sessions and atomic claims; no schema
  migration. A plan edit affects subsequent selection, never rewrites history.
- Module progression derives from recognition and genuine independently checked
  written applications: one correct choice plus two distinct writing situations
  spaced across local dates and at least 24 hours per stage. It is distinct from
  the ten-topic adaptive curriculum evidence.
  C1 delivery requires the existing language gate in addition to module readiness.
- Optional application and external activity have distinct controls and metrics.
  Skips and external self-reports are not model-checked mastery. Text cannot
  demonstrate pronunciation, live interaction or unaided listening.
- Public authored module questions are approved curricular material under the
  user's explicit instruction. Personal imports/notes cannot inject answer keys,
  bypass stage gates or approve arbitrary uploaded learning items.

## Programme amendment — 2026-10-03

- New or missing plans recommend the client-facing track with 70% workplace and
  30% general practice (`general_share=30`). General English remains part of the
  programme; the existing language bank is counted in workplace practice units.
  Saved plans retain their chosen track, allocation and other preferences. The
  explicitly requested owner deployment updates that owner's ratio only,
  preserving module order, focus, notes, pauses and weekly time. No schema change
  is needed.
- B2 and B2+ keep exactly two authored writing situations (`a`, `b`). Selected
  introductory C1 modules may carry four (`a`, `b`, `c`, `d`) to offer additional
  client and technology contexts. The original identifiers and texts remain
  stable. Packs must contain exactly the two- or four-variant set at C1; duplicate,
  unknown or partial variant sets fail validation.
- Additional situations increase practice breadth; the evidence requirement
  remains recognition plus any two distinct independently checked applications
  on different local dates at least 24 hours apart. They do not require four
  successful responses or weaken the ten-topic C1 language gate. Writing chooses
  the next uncredited situation before revisiting one for spacing.
- Existing immutable two-situation question and writing snapshots remain valid
  and resume with their saved content. Extra variants become available through
  future question snapshots; neither pending questions nor prior evidence change.

## Verification

Test weighted selection, order/focus/pauses, all modules/stages, source isolation,
resume and duplicate/foreign callback rejection, skip/stop, genuine writing,
spaced stage advancement, external reports, preserved old C1 gate and Telegram
origin routing. Document how the editor changes real Study selection.
