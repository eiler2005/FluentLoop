# ADR-0015 — Editable workplace roadmap beside assessed progress

**Status:** Accepted  
**Date:** 2026-10-03

## Context

The ten-topic adaptive bank covers selected language targets. The requested
business/IT B2–introductory C1 programme also needs workplace functions, reading,
listening, interaction, mediation and productive deliverables. A larger syllabus
must not silently reinterpret existing evidence or expose reserved transfer tests.

## Decision

- General English remains the foundation; client-facing and large-technology
  workplace modules supplement it. The default time split is 60% general and
  40% specialisation, editable while retaining both strands.
- Ship a versioned, validated public JSON curriculum with source references,
  task ladders, coverage tags, links to existing topics/lessons and explicit
  delivery limits. Render readable Markdown and an offline HTML planner from it.
- Keep the editable personal plan separate: track, weekly minutes, ordered and
  paused module IDs, focus and notes. A portable versioned JSON file carries
  preferences only, never answer history, assessment results or transfer keys.
- Store runtime personal plans in a dedicated user preference namespace; do not
  add a database migration. Imports validate completely before changing that
  namespace, preserve unrelated preferences and affect only the selected user.
- Telegram exposes the roadmap and common edits. The offline editor exports a
  portable plan; a validated administrative CLI applies it to the admitted pilot.
  No browser upload, account, external script or network request is required.
- Plan ordering is advisory and separate from the adaptive question selector.
  Existing ten-topic mastery and C1 gates remain unchanged. New public roadmap
  modules are authored practice briefs, not silently activated question banks.
- Weekly time is a configurable allocation, not a promised completion date.
  Speaking/listening use linked external practice because the bot is text-only.

## Consequences

The learner can customise a practical programme without editing Python or
confusing planned coverage with assessed ability. New quiz targets require their
own content/import review. Personal notes belong in preferences or local exports,
not tracked repository files. Validation and render freshness checks keep the
public catalogue, generated views and packaged runtime data aligned.
