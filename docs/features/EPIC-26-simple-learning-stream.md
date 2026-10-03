# EPIC-26 — Simple Learning Stream

**Status:** Done — implemented and locally validated; owner-only activation
**PRD references:** §5.2, §6 P1, §13, §14
**ADR:** [ADR-0013](../adr/0013-simple-learning-stream.md)

## Goal

Provide one manual entrance to an ongoing phrase/grammar stream for the owner's
profile, with concise feedback and optional writing after stopping. Full
lessons remain available through explicit commands and the additional menu.

## Behavior

- `/study` and bare `/today` start/resume the simple profile's pending question.
- Answers are buttons; an unknown answer reveals feedback and advances.
- "Enough" completes the run; an interrupted run resumes across date changes.
- Phrase and grammar categories alternate, prioritizing due/weak/unseen within
  each. Repeated success has a 24-hour floor; errors need five other answers.
- Prefer alternatives to the last five displayed fingerprints across runs;
  small banks may revisit them after the due and 24-hour success gates.
  If nothing normal is
  eligible, show the result and offer explicit familiar practice.
- Correct early familiar practice leaves SRS unchanged. Recognition does not
  graduate items or count as productive use.
- "Apply it" creates an optional one-sentence bonus linked to the finished run.
- Simple profiles receive no automated pushes or preparation; other profiles
  retain their existing settings and behavior.
- Reviewed `lang-lessons` bank: 86 records / 19 topics, original levels and
  provenance retained, contextual QA overrides applied to quiz payloads.
- Existing phrase cards are eligible only with English/Russian glosses and a
  usable example; the manual choice path performs no enrichment/model calls.

## Implementation

Reuse practice tables with dedicated simple states, a single pending JSON
snapshot, monotonic callback indices, and atomic owner/status/index claims.
Store recognition/production modality on attempts. Import through owner-curated
templates/personal copies; never select templates or another user's records.
Actual-sender authorization protects the owner's forum profile. Optional writing
capture is persisted for the originating chat/topic and current bonus run;
read-only menus preserve it, and switching to full practice closes the simple flow.

## Acceptance and verification

- Repeated starts and restarts return the same unanswered question.
- Parallel/duplicate, stale, and foreign callbacks record at most one answer.
- Stop completes; next start reselects; stopped snapshots remain in history.
- Both categories and all source levels remain reachable; no minimum-bank gate.
- Success cannot recycle a small due pool ahead of unseen questions every few
  seconds; normal/familiar cooldowns survive restarts and new runs.
- Unknown/error spacing, exhaustion, and deliberate familiar repetition work.
- Bonus ownership, retry/idempotency, optional skip, and production attribution
  are verified; full practice and scheduled behavior of other profiles pass.
- Run focused tests, then the standard local test/style/secret/check gates.

## Local validation

On 2026-10-03, the complete suite passed: 414 tests with eight existing Alembic
deprecation warnings. Ruff, application construction, secret scan, diff checks,
and the 19-topic/86-record dry run passed. Tests include separate-connection
answer races, forum sender isolation, topic-bound writing, stale bonus buttons,
reused curated cards, and committed-WAL backup verification. Packaging includes
the reviewed JSON bank in wheels.

## Deployment validation

On 2026-10-03, release `aa20a29` was pushed to `main` and passed
[CI](https://github.com/eiler2005/FluentLoop/actions/runs/37109237752).
The exact commit was deployed with the existing runtime environment preserved.
A consistent pre-release SQLite backup passed integrity verification, and the
container is healthy with Telegram connected and no startup errors.

The owner pilot has 19 subscribed plans and 86 personal question fingerprints,
retaining B1/B2 levels. Other profiles retain their mode. Reapplying the importer
created zero templates, items, or personal plans. Live-database handler smoke
verified resume, duplicate rejection, stop, optional bonus skip, progress, More,
Help, and private-chat routing in a rollback transaction; attempt counts stayed
unchanged. Telegram API reachability, command-menu updates, and delivery of the
owner's three-button keyboard were confirmed. Real learner button taps and typed
AI feedback remain learner actions; automated tests cover those handlers offline.
