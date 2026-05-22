# EPIC-24 - Learning Outcomes Loop

Status: Done - implemented, deployed, and smoke validated

## Summary

EPIC-24 turns the EPIC-22 breakthrough foundation into a measurable learning
system. The goal is not to add more lesson formats. The goal is to prove
whether the core loops are improving the learner's English over time.

Delivery gate remains:

```text
development -> documentation -> tests -> commit -> deploy -> post-deploy smoke -> fix/repeat
```

Commit and deploy are still explicit user-approved gates.

## Validation Evidence

- Local gate: `pytest -q` -> `121 passed`; `ruff`, `secret_scan`,
  `python -m fluentloop --check`, and `git diff --check` were clean.
- Commit: `892188a EPIC-24: add learning outcomes loop`.
- Deploy date: May 22, 2026.
- Alembic on VPS: `0003_epic24 (head)`.
- Container: `fluentloop-bot` healthy after recreation.
- Schema verified on VPS: `evaluation_runs` and `learning_metric_snapshots`
  exist.
- Telegram smoke: Bot API reachable, outbound smoke message sent.
- Telegram workspace: command menu synced; fresh Help-topic guide pinned.
- Server handler smoke: `/baseline` prompt and `/outcomes full` render against
  the live schema inside a rollback transaction.

## Scope

### In v1

- `/baseline` shows the monthly writing/probe task.
- `/baseline <answer>` records a writing baseline and held-out item set.
- `/outcomes` shows a 30-day learning-quality report.
- `/outcomes full` shows sample sizes, top productive chunks, unused chunks,
  and data-quality notes.
- `evaluation_runs` stores baseline and Article Lab probe events.
- `learning_metric_snapshots` stores rendered outcome reports for the Coach
  Journal and trend history.
- Coach Journal includes the latest outcome summary after `/outcomes` has run.

### Not in v1

- Gamification, XP, streak leagues, lives.
- Voice/TTS/STT.
- Web UI or Telegram Mini App.
- Gmail/Calendar/OAuth personal corpus.
- New exercise types added only to increase count.
- Full 30-day Article Lab scheduling; `/article` remains text-first v1.

## Core Mechanisms

1. **Evaluation Harness**
   - Monthly baseline answer is persisted as an `EvaluationRun`.
   - A deterministic held-out item set is stored with that baseline.
   - `/outcomes` reports held-out retention from real `PracticeAttempt` results.
   - Reports say "insufficient data" when samples are too small.

2. **Productive Chunk Loop**
   - Counts `LearningItem(type="chunk")` phrases found in recent production
     answers.
   - Main metric: percent of active chunks used at least 3 times in 30 days.
   - Template/shared-library rows are excluded from per-user metrics.

3. **Notebook Loop**
   - `/practice notebook` remains the main free-production generator.
   - Writing metrics cover word count, lexical diversity, hedging density, and
     mean sentence length.
   - Notebook native-diff mined chunks continue to feed the learning-item loop.

4. **Diplomatic/L1 Loop**
   - Diplomatic Rewrite and Translation Lab remain the primary remediation
     surfaces for pragmatic English and RU->EN transfer.
   - `/outcomes` reports Russian L1 hit density per 100 production words.
   - Hedging density is surfaced as a proxy for softer professional tone.

5. **Mistake Extinction Loop**
   - Low-confidence mistake patterns are tracked against recent attempts.
   - A pattern is treated as nearly extinct after 3 recent correct hits and
     extinct after 5 recent correct hits.
   - The report shows the percent of trackable patterns reaching those states.

6. **Article/Critical Reading Loop**
   - `/article <text>` records a lightweight Article Lab probe event without
     storing the article text itself.
   - The measurable outputs remain: main claim, hedge marker, assumption
     challenge, and executive summary.
   - Critical Reading practice attempts and Article Lab probes count toward the
     reading section in `/outcomes`.

## Telegram Commands

```text
/baseline
/baseline <answer>
/outcomes
/outcomes full
```

`/stats` remains the operational progress view: attempts, due items, weak
items, favorites, and practice counts. `/outcomes` is the learning-quality view:
retention, production, chunk use, L1 density, writing metrics, mistake
extinction, and reading probes.

## Data Model

### evaluation_runs

- `user_id`
- `kind`
- `prompt`
- `answer_text`
- `source_reference`
- `metrics_json`
- `held_out_item_ids`
- `period_start`
- `period_end`

### learning_metric_snapshots

- `user_id`
- `period_start`
- `period_end`
- `metrics_json`
- `summary_text`

Sensitive free-production baseline answers are stored under the same private
runtime-data policy as practice attempts. Article source text is not stored in
the v1 probe event; only metrics and a source-length reference are stored.

## Acceptance Criteria

- `/baseline` returns a prompt and held-out count.
- `/baseline <answer>` stores an `evaluation_runs(kind="baseline")` row with
  writing metrics and held-out item IDs.
- `/outcomes` stores a `learning_metric_snapshots` row and reports insufficient
  data honestly when samples are missing.
- `/outcomes full` includes top productive chunks, unused chunks, L1 hit summary,
  and data-quality notes.
- `/article <text>` records an Article Lab probe event without storing source
  text.
- Coach Journal includes the latest outcome summary after `/outcomes` has run.
- Migration `0003_epic24` upgrades, downgrades, and upgrades again on a copied
  SQLite DB.
- Full local gate is green before commit/deploy.

## Verification

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests scripts
uv run python scripts/secret_scan.py
uv run python -m fluentloop --check
git diff --check
```

## Post-Deploy Smoke

1. Verify Alembic revision is `0003_epic24`.
2. Verify `evaluation_runs` and `learning_metric_snapshots` exist.
3. Run `/baseline`, then submit a short `/baseline <answer>`.
4. Run `/outcomes` and `/outcomes full`.
5. Run `/practice notebook`, `/practice diplomatic`, and `/article <short text>`.
6. Confirm container health and clean logs.
