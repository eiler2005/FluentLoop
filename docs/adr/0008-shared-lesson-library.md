# 0008. Shared lesson library — exit single-user MVP for content

- **Status:** Accepted
- **Date:** 2026-05-20
- **Deciders:** Denis Ermilov

## Decision

Promote lesson plans from per-user private records to a **shared library**
that any registered Telegram user can browse and subscribe to. Subscription
follows a **clone-on-subscribe** model: when a user picks a template, the
bot copies the lesson plan, its steps, and all linked learning items into
records owned by that user, so SRS state and practice progress stay
fully isolated.

This officially ends the strict single-user MVP stance for content
distribution. The bot remains single-tenant from an *operational* point of
view (one container, one Telegram bot, one set of secrets), but the data
layer is now multi-tenant for content access.

## Context

- The product was scoped as single-user (PRD §6 P0 item 2, AGENTS.md
  "Architectural invariants").
- The production database (`/opt/fluentloop-bot/data/fluentloop.sqlite`)
  already contains 21 curated lesson plans built from 34 uploaded
  source materials, owned by `user_id=2` (the project owner).
- The owner wants every Telegram user that the bot admits to be able to
  discover and practise these lessons, not just the owner.
- `TELEGRAM_ALLOWED_USER_ID` is no longer a meaningful gate once
  multiple real users are expected; admission becomes an explicit
  product question (allow-list, signup flow, or open).
- The data model already carries `user_id` on every row, which AGENTS.md
  flagged as "forward-compat only — do not build multi-tenant
  infrastructure." That guard is being removed.

## Alternatives considered

1. **Shared scope via nullable `user_id`.** A new `scope='shared'`
   column lets one row be visible to many. Light schema change, but
   `learning_items` (151 rows) are user-scoped and feed user-scoped
   `review_states`; making them shareable forces either denormalising
   the join key or accepting that every user mutates the same items.
   Rejected — too many cascading invariants to revisit.
2. **System-user pattern.** A reserved `user_id=0` owns all templates,
   queries become `WHERE user_id IN (current_user, 0)`. Simpler than
   nullable scope, but still requires updating every query that filters
   by `user_id` and complicates SRS state.
3. **Clone-on-subscribe (chosen).** Existing per-user queries keep
   working unchanged. Template records get a flag (`is_template=true`)
   and live alongside cloned records. On subscribe, the clone path
   duplicates `lesson_plans`, `lesson_plan_items`, and the underlying
   `learning_items`. `review_states` and `practice_sessions` remain
   strictly per-user as today.

## Consequences

- **Positive**
  - No invasive change to existing queries in
    `src/fluentloop/lesson_plans.py`. `available_lesson_plan`,
    `active_lesson_plans`, `lesson_plan_by_id`, `find_lesson_plan`,
    `random_lesson_plan` keep filtering by `user_id`.
  - SRS / mistake events / progress stats stay isolated per user with
    zero risk of cross-tenant leakage.
  - The shared library becomes a curation surface: the owner can
    iterate on the 21 templates, and improvements propagate via
    re-subscribe rather than mutating active users' plans behind their
    backs.
- **Negative**
  - Data duplication: cloning learning items per subscriber is
    write-heavy. 100 users × 21 plans × ~7 items = ~15k rows. Cheap on
    SQLite for the foreseeable horizon, but worth budgeting.
  - Template edits do not auto-propagate to existing subscribers.
    Subscribers can be offered an opt-in "refresh from template" path
    later — out of scope here.
  - `TELEGRAM_ALLOWED_USER_ID` no longer protects the bot. Admission
    policy becomes a separate concern (see follow-ups).
- **Follow-ups**
  - **ADR-0009 (admission policy):** allow-list vs open signup vs
    invite codes. Required before public discovery.
  - **EPIC-23 (Shared Lesson Library):** schema migration (add
    `is_template`, `template_of`, `subscribed_at` where appropriate),
    `/library` and `/subscribe` commands, clone path.
  - PRD §6 P0 invariant "Single-user profile" is reframed in §1 / §6;
    multi-user moves from P2 to P1 (content access only — operational
    multi-tenancy stays P2).
  - AGENTS.md "Single-user. … data model carries `user_id` for
    forward-compat only" is updated.
  - The 13 source materials currently lacking a draft plan (failed
    `_draft_lesson_plan` runs) are out of scope for this ADR and will
    be re-attempted in a separate pass before being promoted to
    templates.

## References

- PRD §1, §6 P0, §6 P2, §24 (User, LessonPlan), §28 (backlog)
- `docs/features/EPIC-17-persistent-lesson-plans.md`
- `docs/features/EPIC-23-shared-lesson-library.md`
- `src/fluentloop/lesson_plans.py`
- AGENTS.md → Architectural invariants
