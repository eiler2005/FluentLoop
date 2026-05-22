# FluentLoop Material Upload Guide

FluentLoop лучше всего учится на реальных материалах: уроках, рабочих заметках,
фидбэке преподавателя, статьях, meeting notes и homework. Материал не обязан
быть идеальным, но в нем должны быть видны training targets: chunks, patterns,
mistakes, teacher feedback и твои собственные примеры.

## Быстрый формат

Правило: один upload = один урок, статья, встреча, homework или тема.

```text
Lesson: Diplomatic stakeholder communication
Context: We discussed how to disagree politely in product meetings.

Vocabulary / chunks:
- push back on
- align on priorities
- get buy-in
- it might be worth considering
- I see your point, but...

Grammar / patterns:
- hedging recommendations: might / could / would rather than must
- align on + topic
- depend on, not depend from

Mistakes / teacher feedback:
- I said: We must change this.
- Better: We might need to reconsider this.
- I often sound too direct in business context.

My examples:
- We need to align on the scope before Friday.
- It might be worth reducing the release scope.
```

After upload, review the candidates and approve only useful targets. Approval is
the quality gate; uploaded text does not automatically become active practice.

## 5 простых материалов для старта

Это не весь каталог уроков FluentLoop. Это 5 простых **типов входных
материалов** для `/upload`: то, что пользователь может принести сегодня из
урока или работы.

Отдельно в продукте есть:

- **20 shared seed lessons** в `/library` - готовые B2/B2+ business/IT lessons.
- **40 business/IT scenario cards** в `/scene` - roleplay/scene situations для
  переговоров, pushback, incidents, reviews, deadlines и других рабочих
  ситуаций.

Текущий public catalog с lesson types, seed lessons, English for Tech и
scenario cards: [lesson-catalog/index.md](lesson-catalog/index.md).

![What FluentLoop Can Train](assets/fluentloop-training-scope.png)

### 1. Lesson notes from teacher

Bad paste:

```text
lesson about meetings
push back
align
articles
```

Good paste:

```text
Lesson: Diplomatic meeting language
Context: I need to disagree with product managers without sounding aggressive.

Chunks:
- push back on a risky deadline
- align on the scope
- it might be worth considering

Teacher feedback:
- I said: We must change this.
- Better: We might need to reconsider this.
- Mistake: depend on, not depend from.

My example:
- We need to align on the scope before Friday.
```

What FluentLoop does: extracts chunks, L1 risks, teacher corrections, and
examples. Then it trains them in `/today`, `/practice diplomatic`, and SRS.

Next command: `/upload` -> `/approve <material_id>` -> `/today`.

### 2. Word/expression list

Bad paste:

```text
risk
scope
deadline
incident
```

Good paste:

```text
Topic: Incident updates
Use case: Slack updates during production issues.

Expressions:
- root cause - the underlying reason for the incident
- impact window - the time period affected
- current ETA - the best estimate we can give now
- mitigation plan - what we are doing to reduce the damage

Examples:
- We are still investigating the root cause.
- The current ETA is around 30 minutes, but that may change.
```

What FluentLoop does: turns isolated words into trainable chunks and realistic
workplace prompts.

Next command: `/upload` -> `/approve <material_id>` -> `/practice vocab`.

### 3. Slack/email draft

Bad paste:

```text
Your plan is unrealistic. We will break production.
```

Good paste:

```text
Context: I need to answer a product manager about an unrealistic deadline.

My draft:
Your plan is unrealistic. We will break production.

Goal:
Sound firm, clear, and professional. I want to push back without sounding rude.

Better direction:
- hedge the risk
- explain the trade-off
- propose a safer next step
```

What FluentLoop does: creates pragmatic rewrite practice, native alternatives,
and L1/directness checks.

Next command: `/upload` or `/practice diplomatic`.

### 4. Article or blog post

Bad paste:

```text
interesting article about platform teams
```

Good paste:

```text
Article: Platform ownership and reliability
Why I care: I need to summarize this for my team.

Text:
<paste the article or the useful excerpt>

Questions:
- What is the main claim?
- What assumption should I challenge?
- What would be a 3-sentence executive summary?
```

What FluentLoop does: creates critical-reading tasks: main claim, hedge marker,
assumption challenge, executive summary. `/article` also records a reading
probe for `/outcomes` without storing the pasted article text.

Next command: `/article <text>` for a quick lab, or `/upload` if you want it in
your lesson base.

### 5. Meeting transcript / meeting notes

Bad paste:

```text
meeting about roadmap
I need better English
```

Good paste:

```text
Meeting: Roadmap review
Goal: Explain why the team should reduce scope.

Useful phrases I heard:
- reduce the blast radius
- align on the riskiest assumption
- defer the non-critical work

Things I wanted to say:
- Нам нужно срезать объем, иначе релиз будет рискованным.
- Давайте сначала проверим самое рискованное предположение.

Weak spots:
- I sound too direct when I disagree.
- I forget articles in "a risk", "an incident", "the scope".
```

What FluentLoop does: extracts real chunks, L1 transfer risks, articles issues,
and diplomatic rewrite targets.

Next command: `/upload` -> `/approve <material_id>` -> `/practice notebook` or
`/practice diplomatic`.

## Шаблоны

### Lesson Notes

```text
Lesson: <lesson title>
Context: <what the lesson was about and where you need this English>

Vocabulary / chunks:
- <chunk or collocation>
- <phrase with meaning if useful>

Grammar / patterns:
- <grammar pattern>
- <verb/preposition pattern>

Mistakes / teacher feedback:
- I said: <wrong or too-simple version>
- Better: <teacher/native version>

My examples:
- <your realistic sentence>
```

### Word Or Expression List

```text
Topic: <topic>
Use case: <meeting, email, design review, incident update, etc.>

Expressions:
- <expression> — <meaning/context>
- <expression> — <meaning/context>

Example sentences:
- <realistic sentence>
- <realistic sentence>
```

### Teacher Feedback

```text
Source: Teacher feedback from <date/topic>

What I tried to say:
<your original answer>

Teacher/native correction:
<corrected version>

Rules or comments:
- <teacher explanation>
- <register/tone note>

Patterns to train:
- <recurring grammar or collocation>
```

### Article Or Reading

```text
Article: <title or URL if useful>
Main topic: <topic>
Why I care: <work/learning reason>

Key claims:
- <claim>
- <claim>

Useful language:
- <chunk from the article>
- <discourse marker>

Questions / critical reading:
- <assumption to challenge>
- <claim to summarize>
```

### Meeting Transcript Or Notes

```text
Meeting: <meeting name>
Goal: <what you needed to communicate>

Useful phrases I heard:
- <phrase>
- <phrase>

Things I wanted to say but could not:
- <Russian/rough English idea>
- <Russian/rough English idea>

Mistakes or weak spots:
- <too direct / too vague / wrong preposition / missing article>
```

### Homework

```text
Homework topic: <topic>
Task: <what the assignment asked for>

My draft:
<your answer>

Teacher/model answer:
<better answer if available>

Targets:
- <phrase/pattern to reuse>
- <mistake to fix>
```

## Good vs Bad Upload

Good:

```text
Lesson: Incident update
Context: writing a production issue update.
Chunks: root cause, impact window, current ETA, mitigation plan.
Mistake: I wrote "we have incident"; better "we have an incident".
Example: We are still investigating the root cause.
```

Bad:

```text
English lesson
some words:
risk
plan
good
```

The bad version hides the context and gives the bot little signal. The good
version shows where the language is used, what the useful chunks are, and what
mistake should come back in practice.

## LLM Prompt For Preparing Notes

Use this with ChatGPT or another LLM when your raw notes are messy:

```text
Turn my raw English lesson/work notes into FluentLoop upload-ready material.

Goal: preserve only information present in my notes, but organize it so a
Telegram English-learning bot can extract trainable targets.

Output format:
Lesson:
Context:
Vocabulary / chunks:
Grammar / patterns:
Mistakes / teacher feedback:
My examples:

Rules:
- Do not invent new vocabulary that is not supported by the notes.
- Prefer reusable B2+/C1 business/IT chunks and collocations over standalone words.
- Keep teacher corrections and my original mistakes if present.
- Add short labels for register, tone, or use case when obvious.
- Keep the result under 12,000 characters.

Raw notes:
<paste notes here>
```

## Lesson Base And Shared Library

- `/upload` creates candidates from your own material. After approval, the
  material becomes part of **your lesson base**.
- `/library` shows shared B2/B2+ seed lessons.
- `/subscribe <template_id>` copies a shared lesson into your lesson base.
- `/lessons`, `/lesson`, `/topics`, and `/today` operate on your own lesson
  base, including subscribed copies.
