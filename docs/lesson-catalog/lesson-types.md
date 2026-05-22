# FluentLoop Lesson Types

> Generated from FluentLoop DB/code. Do not hand-edit; regenerate with `scripts/export_lesson_catalog.py`.

Lesson Type is the learner-facing layer that connects material, practice mode, exercises, feedback, SRS, and outcomes.

| Type | Goal | When to use | Commands | Metrics | Next modes |
|---|---|---|---|---|---|
| Vocabulary | Learn useful terms and convert them into recallable language. | Use when you meet new standalone words or tech terms. | `/practice vocab`, `/review` | active vocabulary, review accuracy | `/practice vocab`, `/today` |
| Chunks and Collocations | Turn phrases, collocations, and reusable workplace language into active production. | Use when you want to sound less translated and reuse ready-made English. | `/practice vocab`, `/practice notebook`, `/today` | productive chunks, reuse count | `/practice notebook`, `/practice vocab` |
| Grammar | Repair grammar patterns that block clear business/IT communication. | Use when the issue is form, tense, articles, prepositions, or sentence shape. | `/practice grammar`, `/practice mistakes` | grammar accuracy, repeat errors | `/practice grammar`, `/review` |
| Mistake Repair | Extinguish recurring mistakes and Russian-transfer traps. | Use when the same error keeps coming back or confidence is low. | `/practice mistakes`, `/review` | mistake extinction, L1 density | `/practice mistakes`, `/translate_lab` |
| Diplomatic Workplace English | Make pushback, disagreement, feedback, and risk language firm but natural. | Use for stakeholder communication, negotiation, feedback, and workplace tone. | `/practice diplomatic`, `/translate_lab`, `/scene` | hedging density, L1 density | `/practice diplomatic`, `/scene` |
| Notebook | Generate real free writing for native-diff, chunk mining, and L1 checks. | Use when the system needs fresh production data from you. | `/practice notebook`, `/reflect` | word count, lexical diversity, mined chunks | `/practice notebook`, `/outcomes full` |
| Critical Reading | Read articles or arguments and produce claim, assumption, and summary outputs. | Use for articles, blog posts, product docs, and executive summaries. | `/article <text>`, `/practice reading` | reading events, summary quality | `/article <text>`, `/practice reading` |
| Writing | Draft workplace artifacts with clear structure, tone, and reusable chunks. | Use for updates, emails, reports, reviews, resumes, and written answers. | `/practice writing`, `/practice discourse`, `/practice writing_workshop`, `/baseline` | writing metrics, hedging density | `/practice writing`, `/practice notebook` |
| Genre Curriculum | Practice the structure of recurring work artifacts. | Use when the hard part is not one phrase, but the whole document shape. | `/practice genre` | genre coverage, artifact completion | `/practice genre`, `/practice writing_workshop` |
| Scenario / Roleplay | Rehearse a realistic business/IT situation with tasks, roles, and target chunks. | Use before meetings, interviews, negotiation, or difficult conversations. | `/scene <topic or number>`, `/brief <agenda>` | scenario coverage, tone/L1 repair | `/scene`, `/practice diplomatic` |
| Review / SRS | Bring due and weak items back until they are easy to recall. | Use when retention is low or `/outcomes` says sample size is thin. | `/review`, `/today`, `/practice review` | held-out retention, review accuracy | `/today`, `/review` |
| Mixed Lesson | Combine vocabulary, chunks, grammar, writing, and recall in one lesson. | Use for textbook lessons, seed lessons, and broad workplace topics. | `/today`, `/lesson <id>`, `/practice mixed` | attempts, retention, productive chunks | `/today`, `/outcomes full` |
| Outcomes | Measure learning quality and choose the next training loop. | Use weekly or monthly to decide what to train next. | `/baseline`, `/outcomes`, `/outcomes full`, `/mentor` | retention, productive chunks, L1 density, mistake extinction | `/today`, `/practice notebook`, `/practice diplomatic` |
