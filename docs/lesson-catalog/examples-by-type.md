# FluentLoop Examples by Lesson Type

> Generated from FluentLoop DB/code. Do not hand-edit; regenerate with `scripts/export_lesson_catalog.py`.

Этот guide показывает, как разные Lesson Types выглядят для пользователя: зачем нужен урок, в чем идея тренировки, какие targets он поднимает и какой ответ считается сильным.

## Executive map

| Type | Examples | What the type proves |
|---|---|---|
| Vocabulary | [Data Trends and Business Reports](#data-trends-and-business-reports), [Performance, Latency, and Reliability](#performance-latency-and-reliability) | Learn useful terms and convert them into recallable language. |
| Chunks and Collocations | [English for Tech 02: How to Build a Startup](#english-for-tech-02-how-to-build-a-startup), [English for Tech 03: Trending Technology](#english-for-tech-03-trending-technology) | Turn phrases, collocations, and reusable workplace language into active production. |
| Grammar | [Architecture Trade-offs and Recommendations](#architecture-trade-offs-and-recommendations), [Risk Mitigation and Conditionals](#risk-mitigation-and-conditionals) | Repair grammar patterns that block clear business/IT communication. |
| Mistake Repair | [Cross-team Dependencies and Ownership](#cross-team-dependencies-and-ownership), [Article/preposition cleanup](#articlepreposition-cleanup) | Extinguish recurring mistakes and Russian-transfer traps. |
| Diplomatic Workplace English | [Deadline Negotiation and Pushback](#deadline-negotiation-and-pushback), [Customer Feedback and Feature Prioritisation](#customer-feedback-and-feature-prioritisation) | Make pushback, disagreement, feedback, and risk language firm but natural. |
| Notebook | [Technical conversation native diff](#technical-conversation-native-diff), [Weekly work reflection](#weekly-work-reflection) | Generate real free writing for native-diff, chunk mining, and L1 checks. |
| Critical Reading | [Executive Summaries and Concise Recommendations](#executive-summaries-and-concise-recommendations), [Incident Updates and ETA Caveats](#incident-updates-and-eta-caveats) | Read articles or arguments and produce claim, assumption, and summary outputs. |
| Writing | [Async Slack and Email Updates](#async-slack-and-email-updates), [English for Tech 12: Job Interview](#english-for-tech-12-job-interview) | Draft workplace artifacts with clear structure, tone, and reusable chunks. |
| Genre Curriculum | [Incident post-mortem](#incident-post-mortem), [RFC decision memo](#rfc-decision-memo) | Practice the structure of recurring work artifacts. |
| Scenario / Roleplay | [Design review - defend choice A vs B](#design-review-defend-choice-a-vs-b), [Customer escalation absorb and de-escalate](#customer-escalation-absorb-and-de-escalate) | Rehearse a realistic business/IT situation with tasks, roles, and target chunks. |
| Review / SRS | [Due chunk recall](#due-chunk-recall), [Weak mistake return](#weak-mistake-return) | Bring due and weak items back until they are easy to recall. |
| Mixed Lesson | [Balanced daily lesson](#balanced-daily-lesson), [Tech textbook mixed loop](#tech-textbook-mixed-loop) | Combine vocabulary, chunks, grammar, writing, and recall in one lesson. |
| Outcomes | [Monthly baseline](#monthly-baseline), [30-day outcomes report](#30-day-outcomes-report) | Measure learning quality and choose the next training loop. |

## Compact examples

### Vocabulary

- What it trains: Learn useful terms and convert them into recallable language.
- When to use: Use when you meet new standalone words or tech terms.
- Commands: `/practice vocab`, `/review`

#### Data Trends and Business Reports

- Source: [public template: B2/B2+ Seed Lessons: Data Trends and Business Reports](b2-b2plus-seed.md#data-trends-and-business-reports)
- Telegram path: `/subscribe 33`
- Why this lesson exists: Пользователь часто знает слово trend пассивно, но не умеет быстро сказать, что именно изменилось и почему это важно для бизнеса.
- Core idea: Превратить data vocabulary в короткое business impact statement.
- When to use: Когда нужно объяснить метрики, отчет или dashboard без длинного технического описания.
- Targets: a slight increase, a downward trend, compared with
- Practice sample:
  - Name the direction of the metric.
  - Add one comparison point.
  - Finish with the business impact.
- Good answer:

```text
Revenue showed a slight increase compared with last quarter, but activation is still on a downward trend. The main risk is that growth looks healthy while the onboarding funnel is getting weaker.
```

#### Performance, Latency, and Reliability

- Source: [public template: B2/B2+ Seed Lessons: Performance, Latency, and Reliability](b2-b2plus-seed.md#performance-latency-and-reliability)
- Telegram path: `/subscribe 36`
- Why this lesson exists: Tech terms вроде latency и reliability легко узнавать, но сложнее использовать в спокойном объяснении trade-off.
- Core idea: Связать performance word с причиной, эффектом и next step.
- When to use: Когда надо объяснить проблему сервиса менеджеру, команде или клиенту.
- Targets: latency spike, reliability concern, under load
- Practice sample:
  - Describe the symptom in one sentence.
  - Explain the likely cause.
  - Add one mitigation.
- Good answer:

```text
We saw a latency spike under load after the release. It is a reliability concern because retries can amplify the issue. I suggest we roll back the cache change first and then test the queue separately.
```

### Chunks and Collocations

- What it trains: Turn phrases, collocations, and reusable workplace language into active production.
- When to use: Use when you want to sound less translated and reuse ready-made English.
- Commands: `/practice vocab`, `/practice notebook`, `/today`

#### English for Tech 02: How to Build a Startup

- Source: [public template: English for Tech: English for Tech 02: How to Build a Startup](english-for-tech.md#english-for-tech-02-how-to-build-a-startup)
- Telegram path: `/subscribe 14`
- Why this lesson exists: Startup vocabulary часто звучит как набор buzzwords. Урок делает его производительным: идея, problem, market, pitch.
- Core idea: Собрать reusable chunks в короткий startup pitch.
- When to use: Когда нужно объяснить продуктовую идею, MVP или customer pain point.
- Targets: customer pain point, gap in the market, scalable solution
- Practice sample:
  - State the customer pain point.
  - Name the market gap.
  - Pitch the solution in one sentence.
- Good answer:

```text
The main customer pain point is that small teams cannot track compliance work without extra admin. We see a gap in the market for a lightweight tool, so our MVP is a scalable solution for recurring checks.
```

#### English for Tech 03: Trending Technology

- Source: [public template: English for Tech: English for Tech 03: Trending Technology](english-for-tech.md#english-for-tech-03-trending-technology)
- Telegram path: `/subscribe 15`
- Why this lesson exists: Пользователь может читать про trends, но не всегда умеет описать, что компания планирует делать с новой технологией.
- Core idea: Тренировать chunks для trend explanation and future plans.
- When to use: Когда обсуждаешь AI, cloud, automation или новую tooling strategy.
- Targets: gain traction, adopt a tool, roll it out gradually
- Practice sample:
  - Name the technology trend.
  - Explain why it matters now.
  - Say how the team should adopt it.
- Good answer:

```text
The new testing tool is gaining traction because it reduces manual QA work. I would not roll it out to every team yet; we should adopt it in one pilot project and expand gradually if the signal is strong.
```

### Grammar

- What it trains: Repair grammar patterns that block clear business/IT communication.
- When to use: Use when the issue is form, tense, articles, prepositions, or sentence shape.
- Commands: `/practice grammar`, `/practice mistakes`

#### Architecture Trade-offs and Recommendations

- Source: [public template: B2/B2+ Seed Lessons: Architecture Trade-offs and Recommendations](b2-b2plus-seed.md#architecture-trade-offs-and-recommendations)
- Telegram path: `/subscribe 27`
- Why this lesson exists: Без точной grammar recommendation легко звучит слишком уверенно или слишком расплывчато.
- Core idea: Использовать conditionals и comparatives, чтобы честно сравнить options.
- When to use: Когда надо рекомендовать архитектурное решение без overselling.
- Targets: trade-off, from a reliability perspective, I would lean towards
- Practice sample:
  - Compare two options.
  - State the main trade-off.
  - Recommend one option with a hedge.
- Good answer:

```text
From a reliability perspective, I would lean towards the async workflow. The main trade-off is higher operational complexity, but if traffic spikes again, this option gives us a safer failure mode.
```

#### Risk Mitigation and Conditionals

- Source: [public template: B2/B2+ Seed Lessons: Risk Mitigation and Conditionals](b2-b2plus-seed.md#risk-mitigation-and-conditionals)
- Telegram path: `/subscribe 29`
- Why this lesson exists: Risk language needs precise conditions: what happens if we do X, unless Y, provided that Z.
- Core idea: Make mitigation sound specific instead of vague.
- When to use: When writing risk updates, launch plans, or technical recommendations.
- Targets: mitigate the risk, provided that, unless we
- Practice sample:
  - Name one risk.
  - Add a condition with provided that or unless.
  - Close with a mitigation.
- Good answer:

```text
We can mitigate the rollout risk provided that we keep the old endpoint available for one release. Unless we do that, rollback will be slower and customer support will have fewer options.
```

### Mistake Repair

- What it trains: Extinguish recurring mistakes and Russian-transfer traps.
- When to use: Use when the same error keeps coming back or confidence is low.
- Commands: `/practice mistakes`, `/review`

#### Cross-team Dependencies and Ownership

- Source: [public template: B2/B2+ Seed Lessons: Cross-team Dependencies and Ownership](b2-b2plus-seed.md#cross-team-dependencies-and-ownership)
- Telegram path: `/subscribe 35`
- Why this lesson exists: Repeated preposition errors make dependency updates sound translated even when the message is understandable.
- Core idea: Repair dependency + preposition patterns in realistic status language.
- When to use: When blockers, ownership, and follow-ups are spread across teams.
- Targets: depend on, dependency on, own the follow-up
- Practice sample:
  - Find the wrong preposition.
  - Rewrite the dependency sentence.
  - Add who owns the next step.
- Good answer:

```text
The release depends on the data team finishing the migration. We have a dependency on their validation script, and I will own the follow-up with their tech lead today.
```

#### Article/preposition cleanup

- Source: demo card: Demo: Article/preposition cleanup
- Telegram path: `/practice mistakes`
- Why this lesson exists: Некоторые ошибки не заслуживают отдельного урока, но возвращаются каждую неделю: missing articles, wrong prepositions, RU transfer.
- Core idea: Показать пользователю один repeat pattern и сразу закрепить correct form.
- When to use: Когда `/outcomes` или feedback показывает повторяющуюся low-confidence ошибку.
- Targets: in production, the rollout, responsible for
- Practice sample:
  - Correct: We found issue on production.
  - Explain why the article/preposition changes.
  - Use the corrected pattern in a new sentence.
- Good answer:

```text
We found the issue in production during the rollout. The platform team is responsible for the fix, and support will update customers after validation.
```

### Diplomatic Workplace English

- What it trains: Make pushback, disagreement, feedback, and risk language firm but natural.
- When to use: Use for stakeholder communication, negotiation, feedback, and workplace tone.
- Commands: `/practice diplomatic`, `/translate_lab`, `/scene`

#### Deadline Negotiation and Pushback

- Source: [public template: B2/B2+ Seed Lessons: Deadline Negotiation and Pushback](b2-b2plus-seed.md#deadline-negotiation-and-pushback)
- Telegram path: `/subscribe 42`
- Why this lesson exists: Deadline pushback часто звучит либо резко, либо слишком извиняюще.
- Core idea: Дать firm but calm structure: risk, option A, option B.
- When to use: When a deadline is risky and you need to protect quality.
- Targets: move the deadline, protect quality, reduce scope
- Practice sample:
  - State the delivery risk calmly.
  - Offer to move the deadline.
  - Offer to reduce scope if the date is fixed.
- Good answer:

```text
I am concerned that Friday may be too tight because the API schema is still changing. If the date is fixed, we can reduce scope and ship the core flow only. Otherwise, I would suggest moving the deadline to Wednesday so we can protect quality.
```

#### Customer Feedback and Feature Prioritisation

- Source: [public template: B2/B2+ Seed Lessons: Customer Feedback and Feature Prioritisation](b2-b2plus-seed.md#customer-feedback-and-feature-prioritisation)
- Telegram path: `/subscribe 34`
- Why this lesson exists: Feature discussions need diplomatic prioritisation, not just louder opinions.
- Core idea: Turn customer feedback into a ranked recommendation with evidence.
- When to use: When product, support, and engineering disagree about what to build next.
- Targets: recurring feedback, prioritise, high-impact
- Practice sample:
  - Summarise the feedback pattern.
  - Rank one feature as high-impact.
  - Acknowledge one trade-off.
- Good answer:

```text
The recurring feedback is about onboarding friction, so I would prioritise the checklist flow. It looks high-impact because it affects new accounts early, although it means delaying lower-volume reporting requests.
```

### Notebook

- What it trains: Generate real free writing for native-diff, chunk mining, and L1 checks.
- When to use: Use when the system needs fresh production data from you.
- Commands: `/practice notebook`, `/reflect`

#### Technical conversation native diff

- Source: demo card: Demo: Technical conversation native diff
- Telegram path: `/practice notebook`
- Why this lesson exists: Notebook нужен, чтобы получить живой текст пользователя, а не только ответы на закрытые drills.
- Core idea: Free writing -> native rewrite -> mined chunks -> next practice.
- When to use: When the system needs fresh production data from a real work situation.
- Targets: real stakeholder, constraint, native rewrite
- Practice sample:
  - Write 4-5 sentences about a technical conversation.
  - Mention one stakeholder and one constraint.
  - Compare your answer with a native rewrite.
- Good answer:

```text
Yesterday I explained the migration risk to our product manager. The main constraint is that the billing service still depends on the old schema. I suggested a smaller release first, so we can validate the flow before moving all customers.
```

#### Weekly work reflection

- Source: demo card: Demo: Weekly work reflection
- Telegram path: `/reflect`
- Why this lesson exists: Reflection превращает рабочие события в language data: что было трудно сказать, где не хватило chunks, где появился L1 transfer.
- Core idea: Use a short weekly note to feed future lessons.
- When to use: When you want FluentLoop to learn from your actual work week.
- Targets: reflection, missing chunk, next focus
- Practice sample:
  - Describe one moment where English slowed you down.
  - Name the phrase you wished you had.
  - Pick the next practice focus.
- Good answer:

```text
This week I struggled to push back on a vague request. I wanted to say that the scope was unclear without sounding negative. Next week I want to practise diplomatic clarification and requirement questions.
```

### Critical Reading

- What it trains: Read articles or arguments and produce claim, assumption, and summary outputs.
- When to use: Use for articles, blog posts, product docs, and executive summaries.
- Commands: `/article <text>`, `/practice reading`

#### Executive Summaries and Concise Recommendations

- Source: [public template: B2/B2+ Seed Lessons: Executive Summaries and Concise Recommendations](b2-b2plus-seed.md#executive-summaries-and-concise-recommendations)
- Telegram path: `/subscribe 43`
- Why this lesson exists: Reading practice should end in a decision-ready output, not only comprehension.
- Core idea: Extract the bottom line, key risk, and recommended option.
- When to use: When you need to brief a manager after reading a long article or memo.
- Targets: bottom line, recommended option, key risk
- Practice sample:
  - Find the main claim.
  - Name one assumption or risk.
  - Write a three-sentence executive summary.
- Good answer:

```text
Bottom line: the async option is safer for reliability. The key risk is additional operational complexity during rollout. My recommended option is to pilot it with one workflow before expanding.
```

#### Incident Updates and ETA Caveats

- Source: [public template: B2/B2+ Seed Lessons: Incident Updates and ETA Caveats](b2-b2plus-seed.md#incident-updates-and-eta-caveats)
- Telegram path: `/subscribe 26`
- Why this lesson exists: Incident reading/writing needs uncertainty: what we know, what we do not know, and what happens next.
- Core idea: Train concise updates with caveats instead of overpromising.
- When to use: When summarising production issues for stakeholders.
- Targets: root cause, impact window, ETA caveat
- Practice sample:
  - State the current known impact.
  - Add one caveat about ETA.
  - Close with the next update time.
- Good answer:

```text
Current impact is limited to checkout retries between 09:10 and 09:24 UTC. We have narrowed the root cause down to cache invalidation, but the ETA has a caveat around validation. We will send the next update in 30 minutes.
```

### Writing

- What it trains: Draft workplace artifacts with clear structure, tone, and reusable chunks.
- When to use: Use for updates, emails, reports, reviews, resumes, and written answers.
- Commands: `/practice writing`, `/practice discourse`, `/practice writing_workshop`, `/baseline`

#### Async Slack and Email Updates

- Source: [public template: B2/B2+ Seed Lessons: Async Slack and Email Updates](b2-b2plus-seed.md#async-slack-and-email-updates)
- Telegram path: `/subscribe 41`
- Why this lesson exists: Async updates fail when context, status, and next step are mixed together.
- Core idea: Use a compact structure: context, current status, next step.
- When to use: When writing Slack/email updates for distributed teams.
- Targets: for context, current status, next step
- Practice sample:
  - Write one sentence of context.
  - Add current status.
  - Finish with the owner and next step.
- Good answer:

```text
For context, the migration is blocked by one failing validation check. Current status: backend has a fix ready, but QA needs one more run. Next step: I will post the result by 16:00 and confirm whether we can ship today.
```

#### English for Tech 12: Job Interview

- Source: [public template: English for Tech: English for Tech 12: Job Interview](english-for-tech.md#english-for-tech-12-job-interview)
- Telegram path: `/subscribe 24`
- Why this lesson exists: Interview answers need structure and evidence, not memorised phrases.
- Core idea: Turn experience into a concise STAR-style workplace answer.
- When to use: When preparing for recruiter screens or technical interviews.
- Targets: responsible for, worked on, resulted in
- Practice sample:
  - Choose one project.
  - Explain your responsibility.
  - End with a measurable result.
- Good answer:

```text
I was responsible for improving the billing retry flow. I worked on the API changes and coordinated testing with QA. The change resulted in fewer failed renewals and a clearer support playbook.
```

### Genre Curriculum

- What it trains: Practice the structure of recurring work artifacts.
- When to use: Use when the hard part is not one phrase, but the whole document shape.
- Commands: `/practice genre`

#### Incident post-mortem

- Source: demo card: Demo: Incident post-mortem
- Telegram path: `/practice genre`
- Why this lesson exists: Genre lessons train the shape of a work artifact, not only individual phrases.
- Core idea: Use the expected sections: timeline, impact, root cause, remediation, prevention.
- When to use: When you need to write a post-mortem that is clear and blameless.
- Targets: timeline, root cause, prevention
- Practice sample:
  - Place each note into the correct section.
  - Rewrite one blame-heavy sentence neutrally.
  - Draft the prevention section.
- Good answer:

```text
Prevention: we will add a pre-release cache validation check and a rollback owner for checkout changes. This should reduce detection time and make the response path clearer during future incidents.
```

#### RFC decision memo

- Source: demo card: Demo: RFC decision memo
- Telegram path: `/practice genre`
- Why this lesson exists: RFCs become easier to review when the structure separates problem, constraints, options, trade-offs, and recommendation.
- Core idea: Practice the document schema before writing the full proposal.
- When to use: When proposing an architecture or process decision.
- Targets: problem, trade-offs, recommendation
- Practice sample:
  - Draft the five RFC section headings.
  - Put one note under each heading.
  - Write the recommendation with a hedge.
- Good answer:

```text
Recommendation: I would lean towards the async option because it gives us better failure isolation. The trade-off is extra operational complexity, so I suggest piloting it with one workflow first.
```

### Scenario / Roleplay

- What it trains: Rehearse a realistic business/IT situation with tasks, roles, and target chunks.
- When to use: Use before meetings, interviews, negotiation, or difficult conversations.
- Commands: `/scene <topic or number>`, `/brief <agenda>`

#### Design review - defend choice A vs B

- Source: [public scenario card: Business/IT Scenarios: Design review - defend choice A vs B](scenarios.md#design-review-defend-choice-a-vs-b)
- Telegram path: `/scene 1`
- Why this lesson exists: Roleplay is for pressure: you need language while another person is challenging the decision.
- Core idea: Rehearse defending a design with constraints and trade-offs.
- When to use: Before architecture reviews, design reviews, or senior stakeholder Q&A.
- Targets: constraint, trade-off, recommendation
- Practice sample:
  - State your recommendation.
  - Acknowledge one downside.
  - Ask for alignment on the next step.
- Good answer:

```text
I recommend option A because it gives us better failure isolation. The trade-off is a slightly longer migration, but it lowers rollback risk. If we agree on that priority, I can draft the migration plan today.
```

#### Customer escalation absorb and de-escalate

- Source: [public scenario card: Business/IT Scenarios: Customer escalation absorb and de-escalate](scenarios.md#customer-escalation-absorb-and-de-escalate)
- Telegram path: `/scene 12`
- Why this lesson exists: Escalations require tone control: acknowledge, clarify, and move toward a concrete next step.
- Core idea: Practise calm customer language under stress.
- When to use: Before customer calls, incident follow-ups, or support escalations.
- Targets: I understand the concern, what I can confirm, next update
- Practice sample:
  - Acknowledge the customer's frustration.
  - Separate confirmed facts from investigation.
  - Promise a specific next update.
- Good answer:

```text
I understand the concern, and I agree the delay is frustrating. What I can confirm is that the fix is deployed and validation is running now. I will send the next update by 15:30 with either confirmation or a new ETA.
```

### Review / SRS

- What it trains: Bring due and weak items back until they are easy to recall.
- When to use: Use when retention is low or `/outcomes` says sample size is thin.
- Commands: `/review`, `/today`, `/practice review`

#### Due chunk recall

- Source: demo card: Demo: Due chunk recall
- Telegram path: `/review`
- Why this lesson exists: Review lessons protect memory: useful chunks return before they become passive again.
- Core idea: Cold recall first, explanation second.
- When to use: When `/today` or `/review` brings back due items.
- Targets: active recall, cloze, confidence
- Practice sample:
  - Fill the missing chunk without looking.
  - Rate confidence.
  - Use the chunk in a new work sentence.
- Good answer:

```text
Could we move the deadline to Wednesday? This would help us protect quality and still keep the core release on track.
```

#### Weak mistake return

- Source: demo card: Demo: Weak mistake return
- Telegram path: `/practice review`
- Why this lesson exists: Weak items need to reappear in a different form, otherwise the user only memorises one answer.
- Core idea: Return the same mistake pattern as rewrite, cloze, and production.
- When to use: When confidence is low or the same error repeats.
- Targets: error correction, same pattern, new sentence
- Practice sample:
  - Correct the old mistake.
  - Explain the pattern in one line.
  - Write a new sentence with the corrected form.
- Good answer:

```text
The system depends on the billing service, not depends from it. We also have a dependency on the data export before we can finish validation.
```

### Mixed Lesson

- What it trains: Combine vocabulary, chunks, grammar, writing, and recall in one lesson.
- When to use: Use for textbook lessons, seed lessons, and broad workplace topics.
- Commands: `/today`, `/lesson <id>`, `/practice mixed`

#### Balanced daily lesson

- Source: demo card: Demo: Balanced daily lesson
- Telegram path: `/today`
- Why this lesson exists: A daily lesson should not overfit one skill; it should mix recall, accuracy, production, and feedback.
- Core idea: Combine vocabulary, grammar, writing, and SRS in one short loop.
- When to use: When the user opens `/today` and needs the next best training mix.
- Targets: recall, grammar repair, mini writing
- Practice sample:
  - Recall one due chunk.
  - Repair one sentence.
  - Write a short realistic update.
- Good answer:

```text
For context, the rollout is delayed because validation found one edge case. If the date is fixed, we can reduce scope; otherwise I recommend moving the deadline to protect quality.
```

#### Tech textbook mixed loop

- Source: demo card: Demo: Tech textbook mixed loop
- Telegram path: `/lesson <id>`
- Why this lesson exists: Textbook-like lessons usually contain vocabulary, grammar, speaking, and writing together.
- Core idea: Turn broad material into a sequence of small production tasks.
- When to use: When a public or uploaded lesson covers a whole topic, not one pattern.
- Targets: topic vocabulary, grammar focus, free production
- Practice sample:
  - Notice the topic vocabulary.
  - Practise the grammar focus.
  - Produce a short workplace answer.
- Good answer:

```text
I usually work on backend APIs, but this week I am helping the DevOps team with deployment checks. It is a good chance to keep up with our cloud tooling and understand the release process better.
```

### Outcomes

- What it trains: Measure learning quality and choose the next training loop.
- When to use: Use weekly or monthly to decide what to train next.
- Commands: `/baseline`, `/outcomes`, `/outcomes full`, `/mentor`

#### Monthly baseline

- Source: demo card: Demo: Monthly baseline
- Telegram path: `/baseline`
- Why this lesson exists: Outcomes need a stable starting point; otherwise progress is just a feeling.
- Core idea: Capture a monthly writing sample and reserve held-out items.
- When to use: When starting a new month or checking whether practice transfers to production.
- Targets: baseline, held-out items, writing metrics
- Practice sample:
  - Write 120-180 words about a real work situation.
  - Include one risk, one trade-off, and one recommendation.
  - Use the result as the comparison point for the month.
- Good answer:

```text
The main trade-off is speed versus reliability. I recommend delaying the full rollout by two days, because the current validation gap could create support load if we ship to all customers at once.
```

#### 30-day outcomes report

- Source: demo card: Demo: 30-day outcomes report
- Telegram path: `/outcomes full`
- Why this lesson exists: The user needs evidence: retention, productive chunks, L1 density, and mistake extinction, not just number of exercises.
- Core idea: Summarise learning quality and choose the next loop.
- When to use: Weekly or monthly, after enough practice attempts.
- Targets: retention, productive chunks, L1 density
- Practice sample:
  - Read the sample size first.
  - Find the weakest metric.
  - Choose the next practice loop.
- Good answer:

```text
Next best loop: use `/practice notebook` for production volume and `/practice diplomatic` for L1 transfer. Retention is acceptable, but productive chunk use is still thin, so the next week should generate more free writing.
```
