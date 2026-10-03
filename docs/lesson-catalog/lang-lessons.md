# Reviewed lang-lessons question pack

This pack supports the [manual simple stream](../user-guide.md). It contains all
86 original question records across 19 topics: 48 grammar and 38 phrase
questions. Original source levels are retained: 45 B1 and 41 B2 questions.

| Level | Grammar | Phrases | Total |
|---|---:|---:|---:|
| B1 | 40 | 5 | 45 |
| B2 | 8 | 33 | 41 |

Source: `lang-lessons/errors_bank.json`. Source SHA-256:
`376961255dce533c5bd3c597cdb4575f5968de3b9457027eba37de42595eb243`.
The shipped [pack](../../src/fluentloop/seeds/lang_lessons_v1.json) stores each
source topic/index and level, original wrong/right/why fields, a stable fingerprint,
and a reviewed contextual question overlay. Local source files and private
lesson data are not required at runtime.

The original bank contains pairs that are both grammatical in different
situations. Contextual prompts resolve these, including perfect/past tense,
future plans, gerund/infinitive meaning, and discourse linkers. Choices test a
specific meaning or construction; concise Russian feedback explains it.
Phrase cards also carry a Russian gloss, English gloss, and usable example.
Final semantic review checked all 86 questions. Context distinguishes permanent
habits from temporary routines, a learner taking a course from a creator making
one, and a requested phrasal verb from an equally valid single-word verb.
Explanations avoid universal claims about state verbs or adverbs.

This is a finite B1/B2 practice bank, not a CEFR assessment or unlimited content
generator. The stream mixes it with existing approved personal cards. Eligible
questions alternate between grammar and phrases; successful normal answers
wait at least 24 hours and for SRS, while errors need other answers before
returning. When the eligible pool ends, deliberate familiar practice is offered.

The [activation runbook](../runbooks/simple-learning.md) documents validation,
publication, owner subscription, smoke checks, and rollback. Publication and
subscription are idempotent; each user gets isolated progress.
