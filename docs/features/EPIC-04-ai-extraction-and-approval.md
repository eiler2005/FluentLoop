# EPIC-04 — AI extraction and candidate approval

**Status:** Planned
**PRD references:** §9, §22.1, §25.1 (AI extraction)
**Depends on:** EPIC-03, ADR-0003 (model tiering)
**Blocks:** EPIC-07 (which expects approved learning items as input)

## Goal

A `SourceMaterial` is sent to the AI heavy tier, which returns structured
candidates (words / expressions / grammar rules / mistake patterns). The
candidates are stored with `status=pending`, then surfaced to the user one
batch at a time for approval. Only **approved** candidates become
`LearningItem` rows.

This is the canonical "approval required" gate from PRD §5.5 and §13.

## In scope

- AI extraction call (heavy tier per ADR-0003) with the schema from
  PRD §25.1.
- `ExtractedCandidate` table per PRD §24: `id`, `source_material_id`,
  `type`, `text`, `meaning`, `explanation`, `examples`, `tags`,
  `confidence`, `status`, timestamps.
- Pydantic-validated AI response — if the model returns malformed JSON,
  retry once on heavy tier; on second failure, surface a graceful error
  to the user and keep the `SourceMaterial` for later retry.
- Approval UI in chat:
  - Compact summary message: "Found N words, M expressions, K rules,
    L mistake patterns. [Add all] [Review one by one] [Skip]".
  - "Add all" → all pending candidates become `LearningItem` rows.
  - "Review one by one" → bot iterates with [Add] [Edit] [Skip] buttons.
  - "Skip" → mark all as `status=skipped`.
- Edit flow: pick the candidate's `text` / `meaning` / `tags` via inline
  prompts; save; then continue iteration.
- All terminal `status` values (`approved`, `skipped`, `edited`) recorded
  with timestamp.

## Out of scope

- Auto-approval of high-confidence items — explicit PRD constraint, never.
- Bulk import from CSV / Anki — PRD §6 P1.
- Multi-language detection (the user is L1 Russian, target L2 English).

## Acceptance criteria

- After EPIC-03 stores a `SourceMaterial`, the bot calls the AI and stores
  candidates within ~10 seconds (heavy tier latency-dependent).
- The summary message reflects actual candidate counts.
- "Add all" promotes every pending candidate to a `LearningItem` row and
  marks them `approved`.
- "Review one by one" lets the user act on each candidate independently.
- Malformed AI responses don't crash the bot; the user sees a polite
  "couldn't extract — try again or rephrase".
- Re-running extraction on the same `SourceMaterial` (e.g. after an edit)
  does **not** duplicate already-approved candidates — there must be an
  idempotency check.

## Open questions

- Idempotency check: hash of `(source_material_id, candidate_text, type)`
  vs full text dedup? Default to the tuple hash.
- Should the bot suggest tags automatically and let the user edit them, or
  only show what the AI returned? Default: show AI tags, allow edit on
  "Review one by one" path.
- Where do prompts live? Default: `src/fluentloop/prompts/extract.py`
  with f-string templates and Pydantic output schemas.

## Verification plan

1. Upload the example from PRD §9 (push back on, align on, etc.).
2. Bot replies with extracted summary.
3. "Add all" → verify 4 expressions, 1 grammar rule, 1 mistake pattern in
   `LearningItem` table.
4. Re-run extraction on the same material → verify idempotency (no dupes).
5. Upload random Lorem Ipsum → verify graceful "nothing meaningful found"
   reply.
