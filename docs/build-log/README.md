# Build log

This directory holds the verbatim artifacts of the autonomous overnight build
session that took FluentLoop from an empty scaffold to a deployed bot. It is
preserved as history, not as living documentation — for current product
requirements see [`../../PRD.md`](../../PRD.md), and for current architecture
see [`../architecture.md`](../architecture.md).

## What's here

| File | What it is |
|---|---|
| [`NIGHT_RUN.md`](NIGHT_RUN.md) | The self-contained brief Codex executed on 2026-05-06: mission, allowed actions, reference projects, epic execution order, stuck protocol, cost telemetry, and the morning-report format. |
| [`MORNING_REPORT.md`](MORNING_REPORT.md) | The session's delivery manifest: 14 MVP epics + 6 learning-engine epics shipped, 18+ deploys to the VPS, all gates green, cost telemetry, and surprises. |
| [`NIGHT_QUESTIONS.md`](NIGHT_QUESTIONS.md) | Questions that were deferred mid-session, each with the default the agent would have used if forced. All resolved at morning review. |

## Why keep them

Three reasons:

1. **Reproducibility.** Anyone (including future-me) can read `NIGHT_RUN.md`
   and understand the exact constraints, permissions, and stop-rules that
   shaped the codebase that exists today.
2. **Honest provenance.** The repository did not appear by accident. The
   journal makes the autonomous-build origin explicit so reviewers can
   evaluate code quality with full context.
3. **Learning.** What an unattended agent could and could not do well in
   2026 is itself useful evidence — for hiring, for retros, for "what would
   I change next time."

## Caveats for readers

- Operational specifics (VPS host, deploy paths, channel IDs) are
  intentionally omitted or generic in these files; real values live in the
  ignored `secrets/` catalog.
- These documents are **frozen**. They describe state as of 2026-05-07.
  Anything written here that contradicts current code, ADRs, or epic files
  is superseded by those — not the other way around.
