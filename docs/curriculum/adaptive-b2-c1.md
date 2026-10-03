# Adaptive workplace curriculum — B2 to introductory C1

The reviewed pack adds **270 distinct contextual questions** to the original
86-question `lang-lessons` bank. Its ten topics each contain three stages,
with six practice questions and three reserved transfer questions per stage:
180 practice questions and 90 transfer questions. Each question also provides
a construction or phrase target and an original workplace writing task.

Stage names are editorial curriculum labels informed by the CEFR's emphasis
on range, accuracy, coherence and appropriate register. They are not a formal
CEFR assessment or a certification of the learner's level. See the Council of
Europe's [descriptor collection](https://www.coe.int/en/web/common-european-framework-reference-languages/cefr-descriptors)
and [2020 Companion Volume](https://rm.coe.int/cefr-companion-volume-with-new-descriptors-2020/16809ea0d4).

## Topic plans

Every topic is published as one owner-curated lesson template with three
syllabus steps. Subscriptions create personal copies and isolated progress.
The syllabus describes goals and writing tasks; it does not reveal transfer
prompts or answer keys. The gated simple stream delivers the questions.

| Topic | B2 foundation | Strong B2 / B2+ | Introductory C1 |
| --- | --- | --- | --- |
| Time, aspect and progress | Finished events, present results, ongoing work | Past sequences, duration, result versus process | Narrative viewpoint, provisional assessments, future in the past |
| Forecasts, milestones and commitments | Intentions, arrangements, deadline completion | Future progress, dependencies, timetables | Qualified forecasts, formal contingencies, bounded commitments |
| Conditions, alternatives and counterfactuals | Real dependencies and unreal alternatives | Mixed conditionals, precautions, strict conditions | Inverted conditionals and nuanced counterfactual reasoning |
| Evidence, obligation and certainty | Permission, rules, advice, present deductions | Past deductions, unnecessary versus omitted actions | Evidential scope, cautious expectations, diplomatic criticism |
| Reporting and process changes | Reported statements/questions and passive processes | Reporting patterns, causatives, attributed claims | Formal recommendations, prior-process attribution, claims versus facts |
| Focus and specification | Defining/non-defining clauses and precise references | Reduced clauses, shared subjects, cleft focus | Inversion, concessive and absolute clauses, contrastive emphasis |
| Cause, contrast and argument | Cause, purpose, consequence and contrast | Connector syntax, concessions, bounded claims | Corrective reformulation, argument ranking, evidence limitations |
| Diplomatic communication | Courteous requests, clarification and constructive disagreement | Hedging, negotiating priorities, conditional support | Sensitive reservations, mandates, substantive disagreement |
| Delivery and accountability | Natural deadline, decision and ownership collocations | Constraints, scope creep, measurable success criteria | Opportunity cost, contingent advantages, outputs versus outcomes |
| Incidents and operational handovers | Impact, investigation, recovery, next actions | Symptoms versus causes, mitigation, prevention | Causal attribution, interacting factors, proportionate assurance |

Practice uses business and IT settings. Reserved transfer questions also use
different situations, including procurement, research, transport, museums,
manufacturing and service administration. They test applying a construction
or distinction beyond a memorised sentence; names are not substituted to
inflate the bank.

## Progression and evidence

Each topic begins at B2. Advancement needs five distinct practice successes,
at least 80% accuracy in the last ten relevant practice attempts, successes on
at least two local dates and a span of at least 24 hours. Transfer becomes
eligible after a further delay; its first unseen presentation is the only
presentation that can supply transfer evidence.

One successful B2 transfer opens that topic's B2+ stage. Strong B2 evidence
requires B2+ practice, two unseen transfer successes and a successful original
written application. All ten topics need that evidence before introductory
C1 opens. Familiar repetition cannot supply advancement evidence. Errors
bring back practice; optional writing stays optional, but a topic cannot be
reported as productively strong without it. These are local learning rules,
not standardised exam cutoffs.

Approved background expansion can add contextual practice and replacement
transfer variants to an existing personal learning item. It preserves the
topic, stage and practice/transfer role, validates the payload and avoids
already known variants. Generation does not add new active learning targets
or expose the held-out keys in lesson previews. An already available personal
card cannot be relabelled as a reserved unseen transfer card.

## Publishing and pilot subscription

The bundled source is
[`adaptive_curriculum_v1.json`](../../src/fluentloop/seeds/adaptive_curriculum_v1.json).
The loader checks the pack checksum, question fingerprints, unique contexts,
per-stage coverage, English quiz prompts/options, card fields and targets.
It runs before publishing any database rows.

Validate without opening the runtime database or loading runtime settings:

```bash
python scripts/import_adaptive_curriculum.py
```

Explicitly publish templates and subscribe the configured admitted pilot:

```bash
python scripts/import_adaptive_curriculum.py --apply --subscribe-pilot --enable-simple
```

`--apply` alone publishes the library templates. `--subscribe-pilot` clones
the ten plans and enables `learning.adaptive_auto_expand` for that profile.
`--enable-simple` additionally changes its learning entrance. Other users'
preferences remain unchanged. Reapplying creates no duplicate templates,
items, steps or personal plans; curated personal fields and review state are
preserved. Conflicting question provenance fails instead of overwriting it.
The existing 86-question pack and its source B1/B2 labels remain intact.

The importer is an explicit database mutation; local validation does not
deploy it or run it against the VPS. For the architecture and verification
contract, see [ADR-0014](../adr/0014-adaptive-topic-progression.md),
[EPIC-27](../features/EPIC-27-adaptive-topic-progression.md),
[the activation runbook](../runbooks/adaptive-learning.md) and
[the content tests](../../tests/test_adaptive_curriculum.py).
