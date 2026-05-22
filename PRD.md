# PRD v0.2 — English Learning Companion Telegram Bot

## 0. Purpose of this document

This document describes the product requirements for a personal English-learning Telegram bot.

The document is intended to be used by an LLM/Codex as a product specification. It describes what the product must do, why it exists, what is included in MVP, what is excluded, and what acceptance criteria should be satisfied.

Architecture, deployment, Docker, VPS setup, database choice, framework choice, and infrastructure details should be described in a separate architecture document.

---

## 1. Product name

**English Learning Companion**

A Telegram bot that helps a B2+/C1- English learner consolidate school materials through short daily practice, active vocabulary usage, grammar/rules drills, immediate feedback, and mistake-based training.

Started as a personal single-user tool. The owner now curates a shared library of lesson plans so that other admitted Telegram users can subscribe to and practise the same content with fully isolated progress (see ADR-0008).

---

## 2. Context

The user attends an English school approximately 4 days per week. Lessons are mostly conversational and include business English, IT English, vocabulary, expressions, grammar rules, exercises, homework, and teacher feedback.

The user already has enough learning input. The main problem is not lack of materials, but lack of systematic consolidation between lessons.

The bot should help the user:

- repeat new words and expressions;
- activate phrases in business/IT contexts;
- practice grammar rules through short drills;
- receive immediate correction and explanation;
- convert recurring mistakes into separate training items;
- maintain regularity through daily Telegram reminders;
- track progress and weak points over time.

The bot is not intended to replace the English school. It should support the school process by converting lesson materials into structured personal practice.

---

## 3. Target user

The MVP can be designed for one primary user.

```text
Level: B2+/C1-
Main focus: business English, IT English, conversational English
Schedule: English school 4 days per week
Main goal: activate and retain lesson material
Preferred channel: Telegram
Preferred practice duration: approximately 15 minutes per day
MVP format: text-first
```

Multi-user SaaS behavior is not required for MVP.

---

## 4. Product concept

The core product loop:

```text
User uploads lesson material
→ Bot extracts words, expressions, grammar rules, and mistakes
→ Bot summarizes the lesson title, theme, focus, and knowledge areas
→ User approves what should be added to learning storage
→ Bot stores approved learning items
→ Bot builds a reusable lesson pool/lesson plan from the approved items
→ Bot automatically generates daily practice based on the lesson plan, progress, level, weak points, and due reviews
→ User answers text exercises in Telegram
→ Bot checks answers and explains mistakes
→ Mistakes update progress and may become mistake patterns
→ Mistake patterns are used in future practice
```

Important distinction:

```text
Adding new learning items from uploaded materials requires user confirmation.
Generating exercises from already approved items, progress data, user level, weak points, and mistake history does not require confirmation.
```

---

## 5. Product principles

### 5.1. Learn from the user's own materials

The bot should prioritize materials from the user's real English-learning process:

- lesson notes;
- word lists;
- expressions/chunks;
- homework;
- teacher corrections;
- grammar topics from school;
- business/IT texts;
- user mistakes.

The MVP should not focus on importing generic content from the internet.

### 5.2. Active production over passive recognition

At B2+/C1-, simple flashcards are not enough. The bot should train active usage:

- recall;
- translation into English;
- phrase production;
- cloze exercises;
- rewriting;
- grammar correction;
- business-style phrasing;
- follow-up questions;
- use of expressions in realistic IT/business situations.

### 5.3. Mistakes become training

A mistake should not end with a correction only. The bot should:

1. correct the answer;
2. explain the reason;
3. classify the mistake type;
4. connect the mistake to a grammar rule, expression, or concept;
5. update progress;
6. generate future practice based on this weak point.

### 5.4. Business/IT context by default

Examples and tasks should be relevant to the user's professional context:

- meetings;
- stakeholder communication;
- product discussions;
- architecture discussions;
- sprint planning;
- deadlines;
- delivery risks;
- incidents;
- prioritization;
- trade-offs;
- risk mitigation;
- status updates;
- feedback;
- negotiations.

### 5.5. Automatic exercise generation is allowed

The bot may automatically generate exercises without asking the user for confirmation before every exercise.

Automatic exercise generation should be based on:

- approved learning items;
- user level;
- business/IT focus;
- due review schedule;
- weak items;
- mistake patterns;
- favorite items;
- recent lesson materials;
- previous answer quality.

The bot should not automatically add arbitrary new words, expressions, or grammar concepts from uploaded materials without user approval.

---

## 6. MVP scope

MVP is a text-first Telegram bot.

### P0 — required for MVP

```text
1. Telegram bot basics.
2. User profile per admitted Telegram user (admission policy is a separate concern; see ADR-0009 once written).
3. Settings: level, focus areas, reminder time, practice duration.
4. Upload text lesson materials.
5. AI extraction of words, expressions, grammar rules, and mistake patterns.
6. User approval flow for adding extracted learning items.
7. Manual adding of words, expressions, rules, and mistakes.
8. Learning items storage.
9. Spaced repetition state for items.
10. Persistent lesson pools/plans from approved lesson materials.
11. Automatic daily practice generation from approved data.
12. Daily practice session in Telegram.
13. Exercise types:
    - guess word/expression;
    - translate phrase;
    - cloze;
    - grammar rewrite;
    - error correction;
    - follow-up question.
14. Immediate answer checking and feedback.
15. Mistake pattern tracking.
16. Grammar/rules as connected concepts.
17. Basic progress stats.
18. Favorites / important items.
```

### P0.5 — optional MVP extension

```text
1. Lightweight web interface for managing learning content.
2. View/edit/delete learning items.
3. Approve extracted items in a web UI.
4. View due items and weak items.
5. View basic stats.
6. Manually add words, expressions, grammar rules, and mistake patterns.
```

The web interface is allowed in MVP if it helps development and content management. It is not required for the first usable Telegram-only version.

Telegram remains the primary interface for daily practice.

### P1 — after MVP

```text
1. PDF import.
2. Image/screenshot import.
3. Telegram Mini App or richer web dashboard.
4. Export to CSV/Anki.
5. More advanced FSRS implementation.
6. Lesson recap templates.
7. Text role-play scenarios.
8. More advanced weekly report.
9. Breakthrough roadmap: two-layer feedback, sub-day SRS, Russian L1 hit list,
   evaluation probe, reflection, and named lesson formats (EPIC-22).
10. Shared lesson library: owner-curated templates discoverable and subscribable by other admitted users, with cloned per-user progress (ADR-0008, EPIC-23).
11. Admission policy: allow-list vs invite-code vs open signup (ADR-0009 to write).
```

### P2 — future

```text
1. Voice messages.
2. Speech-to-text.
3. Pronunciation feedback.
4. Real-time voice dialogue.
5. Full AI tutor with voice.
6. Operational multi-tenancy (multiple bots, multiple owners, isolated tenants beyond shared content — content-level multi-user is P1, see ADR-0008).
7. Teacher/admin mode.
8. LMS or school integrations.
```

---

## 7. Non-goals for MVP

The MVP should not include:

```text
1. Voice practice.
2. Pronunciation scoring.
3. Real-time voice dialogue.
4. Full AI tutor with voice.
5. Generic internet import as the main content source.
6. Full English course from A1 to C1.
7. Multi-user SaaS features.
8. Complex admin panel.
9. School LMS integration.
10. Automatic activation of arbitrary newly extracted learning items without user approval.
```

Note: automatic exercise generation is not a non-goal. It is explicitly allowed when exercises are generated from approved learning items, approved lesson plans, material context, user progress, user level, and weak points.

---

## 8. User profile

The bot should store user settings.

### Profile fields

```text
id
telegram_user_id
level: default B2+/C1-
focus_areas: business, IT, conversational English, grammar, vocabulary
explanation_language: Russian / English / mixed
practice_duration_minutes: default 15
reminder_time
timezone
school_days
created_at
updated_at
```

### Acceptance criteria

```text
Given the user starts the bot for the first time
When the user sends /start
Then the bot creates a profile and offers basic settings

Given the user already has a profile
When the user sends /settings
Then the bot shows current settings and allows changing them
```

---

## 9. Material upload

The user should be able to send learning materials as text.

### Supported MVP formats

```text
1. Plain text message.
2. Word list.
3. Expression list.
4. Lesson notes.
5. Homework text.
6. Exercise text.
7. Teacher feedback copied as text.
```

PDF, image, screenshot, and audio upload are not required for MVP.

### Example flow

```text
User:
Today we covered:
- push back on
- align on priorities
- get buy-in
- trade-off
Grammar: hedging recommendations
Mistake: I used "must" too directly in business context

Bot:
Lesson:
Diplomatic stakeholder communication

Theme:
Explaining disagreement and recommendations at work.

Knowledge areas:
- Topics: stakeholder communication, business collocations
- Grammar: hedging recommendations
- Skills: polite disagreement, concise recommendations
- Mistake risks: over-direct "must" recommendations

Candidates:

Expressions:
1. push back on
2. align on priorities
3. get buy-in
4. trade-off

Grammar rules:
1. Hedging recommendations

Mistake patterns:
1. Too direct recommendations with "must"

Add these to learning?
[Add all] [Review one by one] [Skip]
```

### Acceptance criteria

```text
Given the user sends lesson material
When the bot processes it
Then the bot returns a lesson overview plus extracted words, expressions, grammar rules, and possible mistake patterns

Given extracted items are shown
When the user clicks Add all
Then all extracted items become active learning items

Given the user approves a lesson material
When active learning items are created
Then the bot creates or updates a reusable lesson pool that can rotate into /today

Given the user clicks Review one by one
Then each extracted item can be added, edited, or skipped
```

---

## 10. Learning items

The system should support four main learning item types.

```text
1. Word
2. Expression
3. Grammar Rule
4. Mistake Pattern
```

### 10.1. Word

Example:

```text
Text: mitigate
Meaning: смягчать, снижать риск
Context: We need to mitigate the risk before the release.
Tags: business, risk, IT
Level: B2/C1
```

### 10.2. Expression

Example:

```text
Text: push back on something
Meaning: мягко возражать, не соглашаться
Context: I’d like to push back on this proposal a bit.
Tags: meetings, stakeholder communication
Level: B2/C1
```

### 10.3. Grammar Rule

Example:

```text
Title: Hedging recommendations
Explanation:
In business communication, direct recommendations can sound too strong.
Use softer forms such as:
- might need to
- could consider
- I’d suggest
- it might be worth

Too direct: We must change the architecture.
Better: We might need to reconsider the architecture.
```

### 10.4. Mistake Pattern

Example:

```text
Title: Too direct recommendations
User mistake: We must change the architecture immediately.
Correction: We might need to reconsider the architecture soon.
Linked rule: Hedging recommendations
Training types: rewrite, translate phrase, choose better option, follow-up question
```

---

## 11. Grammar rules as a graph of concepts

Grammar/rules should be stored as connected concepts rather than a flat list.

Example:

```text
articles
→ abstract nouns
→ business collocations with zero article
```

Another example:

```text
modal verbs
→ recommendations
→ hedging in stakeholder communication
```

Another example:

```text
conditionals
→ discussing risks
→ discussing trade-offs with stakeholders
```

### Why this matters

If the user makes mistakes in a narrow topic, the bot can connect that mistake to broader parent concepts and occasionally review the foundation.

Example:

```text
Mistake:
We need to get approval from managements.

Linked concepts:
nouns
→ countable / uncountable nouns
→ collective nouns
→ business nouns
```

### Acceptance criteria

```text
Given a grammar rule exists
When it is stored
Then it can have parent concepts and child concepts

Given the user repeatedly fails a child concept
When the bot generates practice
Then it may include a short exercise from the parent concept
```

---

## 12. Spaced repetition

The bot should plan reviews for words, expressions, grammar rules, and mistake patterns.

### Reviewable item types

```text
1. Words
2. Expressions
3. Grammar rules
4. Mistake patterns
```

### Review result options

```text
Again
Hard
Good
Easy
```

For MVP, the implementation may use a simple interval-based algorithm. It should be possible to replace or upgrade it later with a more advanced FSRS-like algorithm.

### Example MVP intervals

```text
Again: same day / very soon
Hard: next day
Good: in 3 days
Easy: in 7 days
```

Intervals should grow over time when the user performs well.

### Acceptance criteria

```text
Given a learning item is added
When it becomes active
Then it receives a review state and next_review_at

Given the user answers correctly
When the result is Good or Easy
Then next_review_at is moved further into the future

Given the user answers incorrectly
When the result is Again or Hard
Then next_review_at is scheduled sooner and priority increases
```

---

## 13. Automatic practice generation

The bot should generate practice sessions automatically.

The user should not need to confirm every generated exercise.

### Input signals for generation

```text
1. User level.
2. Focus areas.
3. Due review items.
4. Weak items.
5. Favorite items.
6. Recent lesson materials.
7. Recent mistakes.
8. Active mistake patterns.
9. Active grammar rules.
10. Previous answer quality.
11. Active lesson plans from approved source materials.
12. Lesson knowledge areas such as topic, grammar rules, communication skills, and mistake risks.
```

### Item priority rules

When generating daily practice, the bot should prioritize:

```text
1. Due or overdue items.
2. Weak expressions and words.
3. Active mistake patterns.
4. Grammar rules connected to recent mistakes.
5. Recently added lesson items.
6. Active lesson-plan items with high teacher priority.
7. Favorite items.
8. Business/IT relevance.
9. Recent-session penalty, so the same pool can rotate over time.
```

### Exercise mix

A typical daily session should include a mix of:

```text
1. Word/expression review.
2. Translation into English.
3. Cloze exercise.
4. Grammar rewrite.
5. Error correction.
6. Business/IT follow-up question.
7. Mistake-based exercise.
```

### Safety rule

The bot may generate exercises freely from approved data, but it should not silently create new active learning items from hallucinated or unapproved content.

If the AI discovers a potentially useful new phrase during feedback, it can suggest it as a candidate:

```text
Suggested new expression:
"gently push back on"

Add to learning?
[Add] [Skip]
```

### Acceptance criteria

```text
Given the user has approved learning items and progress history
When /today is triggered
Then the bot automatically creates a practice session without asking for exercise-level confirmation

Given the user has weak items
When practice is generated
Then weak items receive higher priority

Given the user has recurring mistakes
When practice is generated
Then at least one mistake-based exercise should be included when appropriate

Given the AI suggests a new learning item not already approved
When it wants to add it to long-term storage
Then the user must be asked for approval
```

---

## 14. Daily practice

The daily session should take approximately 15 minutes.
The default session should contain about 15-20 short micro-drills, with fewer
items for writing-heavy sessions and more items for quick cloze/rewrite drills.

### Example daily session

```text
Today’s English practice — 15 min
Lesson: Reported Speech: Introverts, Extroverts, and Workplace Opinions
Mode: lesson
Topic: Reported speech and workplace personality
Goal: Report opinions, recommendations, and conflicts naturally in workplace English.

Step 1/16 — Warm-up
In 1-2 sentences: do you prefer working with introverts or extroverts?

Step 2/16 — Input
Notice the pattern: suggest + gerund.
Example: She suggested having just one meeting a week.

Step 3/16 — Controlled practice
Rewrite using the correct reporting pattern:
"I think it would be a good idea to have fewer meetings."

Step 4/16 — Controlled practice
Complete the phrase:
People refused ___ take the idea seriously.

Step 16/16 — Recap
Recall three reporting verbs and one verb pattern without looking back.
```

### Acceptance criteria

```text
Given there are due items
When the reminder time comes
Then the bot sends a daily practice invitation

Given the user starts the session
When exercises are due
Then the bot sends exercises one by one

Given the user starts practice after midnight in their configured timezone
When /today is triggered
Then the bot treats it as the new local day, not UTC day

Given the user approves new lesson material while an old practice session is still active
When /today is triggered
Then the bot may supersede the stale old session and start the new lesson-plan session

Given the user does not know an answer
When they choose Skip / show answer or send /skip
Then the bot records the skipped attempt and shows the correct answer with a short explanation

Given the user wants metacognitive tracking
When they tap a 1-5 confidence rating before answering
Then the rating is stored with the exercise/attempt and overconfident mistakes receive higher priority

Given a session completes
When the summary is shown
Then the user is prompted to save a short reflection with /reflect

Given the user completes the session
When all exercises are finished
Then the bot shows a short summary and updates progress
```

---

## 15. Exercise types

### 15.1. Guess word/expression

```text
Bot:
Guess the expression:
"to politely disagree with a proposal or idea"

User:
push back on

Bot:
Correct.
Example:
I’d like to push back on this proposal a bit.
```

### 15.2. Translate phrase

```text
Bot:
Translate into English:
"Нам нужно согласовать приоритеты до демо."

User:
We need to align priorities before the demo.

Bot:
Good, but more natural:
We need to align on priorities before the demo.

Explanation:
"Align on something" is a common business collocation.
```

### 15.3. Cloze exercise

```text
Bot:
Fill in the gap:
We need to ___ the risk before the release.

User:
mitigate

Bot:
Correct.
```

### 15.4. Grammar rewrite

```text
Bot:
Rewrite this sentence in a more diplomatic business style:
"We must change the architecture immediately."

User:
I think we might need to reconsider the architecture soon.

Bot:
Great.
You softened the recommendation using "might need to".
```

### 15.5. Error correction

```text
Bot:
Correct the sentence:
"We need to get approval from managements."

User:
We need to get approval from management.

Bot:
Correct.
Explanation:
"Management" is usually used as an uncountable collective noun in this context.
```

### 15.6. Follow-up question

```text
Bot:
You are discussing a delayed feature with a product manager.
Explain the trade-off between speed and quality.
Use at least two expressions:
- push back on
- align on
- mitigate

User:
I’d push back on releasing it this week because we haven’t mitigated the main risks yet. We should align on the priorities first.

Bot:
Good answer.

More natural:
I’d gently push back on releasing it this week because we haven’t mitigated the main risks yet. We should align on priorities first.
```

### 15.7. Additional micro-drill templates

The bot may assemble lessons from these internal templates while exposing
simple user-facing practice modes such as vocabulary, grammar, mistakes,
writing, review, and mixed:

```text
noticing
collocation_drill
sentence_transform
word_family
register_choice
chunk_builder
active_recall
mini_writing
```

Each template should carry mode tags, stage tags, target item kinds,
difficulty, and writing weight so the lesson engine can balance 15-20
micro-drills inside a 15-minute session.

---

## 16. Immediate feedback

After each answer, the bot should give feedback.

### Feedback should include

```text
1. Status: correct / partially correct / incorrect.
2. Corrected version.
3. More natural version, if needed.
4. Short explanation.
5. Related expression or grammar rule.
6. Detected mistake type, if any.
7. Suggestion to add a new item, if useful.
```

### Example

```text
User:
We must change the architecture immediately.

Bot:
Grammatically correct, but too direct for a business meeting.

Better:
We might need to reconsider the architecture soon.

Why:
"Must" can sound too strong. In stakeholder communication, it is often better to hedge recommendations with:
- might need to
- could consider
- I’d suggest

Linked rule:
Hedging recommendations

I’ll add this as a weak point for future practice.
```

---

## 17. Mistake-based training

The bot should track mistakes and generate practice based on them.

### Mistake event

Every time the user makes a meaningful error, the bot may store a mistake event.

A mistake event can include:

```text
wrong_answer
corrected_answer
explanation
mistake_type
linked_learning_item_id
linked_grammar_concept_id
created_at
```

### Mistake pattern

If similar mistakes repeat, the bot should create or update a mistake pattern.

Example:

```text
Title: Too direct recommendations in business context

Detected examples:
- We must change the architecture immediately.
- You must fix it today.

Better alternatives:
- We might need to reconsider the architecture.
- It might be worth fixing this today.
- I’d suggest we look into this today.

Linked rule:
Hedging recommendations

Training types:
- rewrite;
- choose better option;
- translate phrase;
- follow-up question.
```

### Confirmation behavior

For MVP, the bot may automatically log mistake events.

The bot may automatically create or update a mistake pattern when:

```text
1. Similar mistakes occur repeatedly.
2. The confidence is high.
3. The pattern is linked to a known grammar rule or expression.
```

If confidence is low, the bot should ask the user before adding a new active mistake pattern.

### Acceptance criteria

```text
Given the user makes a mistake
When the bot detects it
Then the bot stores a mistake event and gives feedback

Given similar mistakes repeat
When the bot identifies a recurring pattern
Then it creates or updates a mistake pattern

Given a mistake pattern is active
When daily practice is generated
Then the bot can include exercises targeting that mistake pattern
```

---

## 18. Rules practice

The bot should train precise rules relevant to B2+/C1- business and IT English.

### Priority rule examples

```text
1. Articles in abstract business language.
2. Zero article in business collocations.
3. Hedging in stakeholder communication.
4. Conditionals for discussing risks.
5. Reported speech in meetings.
6. Modal verbs for recommendations.
7. Phrasal verbs in business context.
8. Countable / uncountable business nouns.
9. More diplomatic phrasing.
10. Natural collocations in IT discussions.
```

### Example rule

```text
Rule:
Hedging in stakeholder communication

Short explanation:
In business English, direct statements can sound too strong.
Use softer structures when giving recommendations.

Patterns:
- We must... → We might need to...
- You should... → It might be worth...
- This is wrong... → One concern is...

Exercise:
Rewrite:
"You should change the deadline."
```

---

## 19. Progress memory

The bot should track progress over time.

### Metrics

```text
1. Total words added.
2. Total expressions added.
3. Active words.
4. Active expressions.
5. Grammar rules in progress.
6. Active mistake patterns.
7. Completed sessions.
8. Skipped sessions.
9. Weak items.
10. Due items.
11. Favorite items.
12. Last practiced date.
```

### Weekly report

The bot should send a weekly report.

Example:

```text
Weekly English Summary

This week:
- New expressions: 18
- Practiced items: 64
- Weak expressions: 5
- Grammar focus: hedging, articles, conditionals
- Recurring mistake: too direct recommendations

Recommended focus next week:
1. Hedging in meetings
2. Articles with abstract business nouns
3. Expressions for pushing back politely
```

---

## 20. Favorites / important items

The user should be able to mark items as important.

Examples:

```text
- get buy-in
- align on priorities
- push back on
- single source of truth
- trade-off
- mitigate risk
- follow up with
- keep stakeholders in the loop
```

### Acceptance criteria

```text
Given a learning item exists
When the user marks it as Favorite
Then the item receives an is_favorite flag

Given an item is favorite
When practice is generated
Then the item may receive higher priority
```

---

## 21. Telegram commands

### Required commands

```text
/start
Create or load user profile.

/today
Start today’s practice session.

/review
Review due items.

/practice vocab|grammar|mistakes|writing|review|mixed|diplomatic|notebook|discourse|reading|genre|writing_workshop
Start standalone practice by mode.

/topics
Browse active lesson topics and knowledge areas.

/lessons [query]
List active lesson plans, optionally filtered by topic/title/focus/tags.

/lesson <id>
Show a lesson card with title, topic, goal, focus, target chunks, and pool size.

/lesson random
Start a random active lesson.

/lesson topic <query>
Start the best matching active lesson for a topic.

/skip
Skip the current exercise and reveal the correct answer with a short explanation.

/feedback explain <attempt_id>
Show the stored detailed teacher breakdown for an answer.

/reflect <text>
Save a short reflective practice note for weekly review.

/scene <topic>
Build a business/IT roleplay scene card.

/brief <agenda>
Prepare just-in-time meeting language.

/mentor
Show the weekly Socratic English prompt.

/article <text>
Start text-first Article Lab v1.

/debate <topic>
Start Debate Mode.

/translate_lab <topic>
Practice RU-to-EN transfer and L1 traps.

/fluency432 <topic>
Practice 4-3-2 fluency compression.

/add
Manually add a word, expression, grammar rule, or mistake.

/upload
Upload lesson material for extraction.

/mistakes
Show active mistake patterns.

/rules
Show grammar rules and weak rules.

/stats
Show progress.

/settings
Change settings.

/help
Show the learner guide: how to start practice, browse lessons, upload material,
answer, skip, and read feedback.

/howto
Alias for /help.
```

The Help guide should also be pinned in the Telegram Help topic. The Telegram
command menu should list the current core commands so the user can discover
`/today`, `/topics`, `/lessons`, `/lesson`, `/practice`, `/upload`, `/skip`,
`/feedback`, `/reflect`, `/brief`, `/scene`, `/help`, and `/howto` without
reading repository docs.

---

## 22. Main user scenarios

### 22.1. After lesson

```text
1. User sends /upload.
2. Bot asks for lesson materials.
3. User sends text.
4. Bot extracts words, expressions, grammar rules, and possible mistake patterns.
5. Bot shows lesson title, theme, focus, knowledge areas, and candidates.
6. User approves, edits, or skips candidates.
7. Bot stores approved items.
8. Bot creates a reusable lesson pool/lesson plan.
9. Bot schedules the approved items for future practice.
```

### 22.2. Daily practice

```text
1. At reminder time, the bot sends a practice invitation.
2. User starts the session.
3. Bot automatically generates exercises from approved data and progress history.
4. Bot shows the lesson title, mode, topic, goal, focus, and dynamic Step X/N.
5. User answers in text.
6. Bot checks answers.
7. Bot explains mistakes.
8. User may skip an exercise to reveal the correct answer.
9. Bot updates review states and progress.
10. Bot shows a session summary.
```

### 22.3. Mistake becomes training

```text
1. User makes a mistake.
2. Bot corrects the answer.
3. Bot explains the rule.
4. Bot logs a mistake event.
5. Similar mistakes repeat.
6. Bot creates or updates a mistake pattern.
7. Future sessions include exercises for this mistake pattern.
```

### 22.4. Grammar concept practice

```text
1. Bot sees repeated mistakes with hedging.
2. Bot selects the rule: Hedging recommendations.
3. Bot gives a short explanation.
4. Bot generates rewrite exercises.
5. User answers.
6. Bot updates rule review state.
```

### 22.5. Web interface usage, optional MVP extension

```text
1. User opens web interface.
2. User sees learning items, due items, weak items, and stats.
3. User edits or deletes items.
4. User approves extracted items more comfortably than in Telegram chat.
5. User returns to Telegram for daily practice.
```

---

## 23. Lightweight web interface — optional MVP extension

A lightweight web interface may be included in MVP if it improves usability.

The web interface is not a replacement for Telegram practice. Its purpose is content management and visibility.

### Web UI MVP features

```text
1. List learning items.
2. Filter by type: word, expression, grammar rule, mistake pattern.
3. Filter by tag, status, due, weak, favorite.
4. View item details.
5. Edit item.
6. Delete or archive item.
7. Mark item as favorite.
8. Approve extracted candidate items.
9. View basic stats.
10. Manually create items.
```

### Web UI non-goals for MVP

```text
1. Complex design system.
2. Multi-user admin panel.
3. Teacher mode.
4. Complex analytics.
5. Real-time chat in web UI.
```

### Acceptance criteria

```text
Given the web UI is enabled
When the user opens it
Then the user can view existing learning items

Given the user edits an item in web UI
When the change is saved
Then Telegram practice uses the updated item data

Given extracted candidate items exist
When the user opens the approval page
Then the user can approve, edit, or skip them
```

---

## 24. High-level data entities

This is not a final database schema. It describes product-level entities.

### User

```text
id
telegram_user_id
level
focus_areas
timezone
reminder_time
practice_duration_minutes
created_at
updated_at
```

### SourceMaterial

```text
id
user_id
type
raw_text
summary
title
topic
lesson_goal
knowledge_areas
created_at
```

### MaterialChunk

```text
id
source_material_id
chunk_index
text
tags
created_at
```

### ExtractedCandidate

```text
id
source_material_id
type: word | expression | grammar_rule | mistake_pattern
text
meaning
explanation
examples
tags
confidence
status: pending | approved | skipped | edited
created_at
updated_at
```

### LearningItem

```text
id
user_id
type: word | expression | grammar_rule | mistake_pattern | chunk
text
meaning_ru
explanation
examples
tags
metadata_json
level
source_material_id
is_favorite
status: active | archived | suspended
created_at
updated_at
```

### LessonPlan

```text
id
user_id
source_material_id
title
topic
goal
format
status: active | archived
created_at
updated_at
```

### LessonStep

```text
id
lesson_plan_id
position
stage: warmup | input | controlled_practice | grammar_or_mistake_focus | free_production | recap
prompt
target_skill
metadata
created_at
updated_at
```

### LessonPlanItem

```text
id
lesson_plan_id
learning_item_id
teacher_priority
created_at
```

### GrammarConcept

```text
id
title
description
parent_ids
child_ids
examples
created_at
updated_at
```

### MistakeEvent

```text
id
user_id
wrong_answer
corrected_answer
explanation
mistake_type
linked_learning_item_id
linked_grammar_concept_id
created_at
```

### MistakePattern

```text
id
user_id
title
description
wrong_examples
correct_examples
linked_grammar_concept_id
linked_learning_item_ids
status
created_at
updated_at
```

### ReviewState

```text
id
learning_item_id
due_at
last_reviewed_at
review_count
success_count
fail_count
difficulty
stability
last_result: again | hard | good | easy
created_at
updated_at
```

### PracticeSession

```text
id
user_id
type: daily | review | grammar | mistake_based
mode: review | lesson | mixed | mistake_focus
target_date_local
lesson_plan_id
topic
lesson_goal
started_at
completed_at
status: in_progress | completed | abandoned | superseded
exercises
summary
created_at
updated_at
```

### PracticeAttempt

```text
id
practice_session_id
learning_item_id
exercise_index
exercise_type
prompt
user_answer
correct_answer
feedback
score
status: correct | partial | incorrect | skipped | disputed | unchecked
target_learning_item_ids
created_at
```

---

## 25. AI requirements

The bot may use AI for extraction, exercise generation, and answer checking.

### 25.1. AI extraction from materials

Input:

```text
raw lesson material
user level
focus areas
```

Expected output:

```json
{
  "lesson_overview": {
    "title": "",
    "theme": "",
    "communicative_goal": "",
    "focus": "",
    "knowledge_areas": {
      "topics": [],
      "grammar": [],
      "skills": [],
      "mistake_risks": []
    }
  },
  "candidates": [
    {
      "type": "word | expression | grammar_rule | mistake_pattern",
      "text": "",
      "meaning": "",
      "explanation": "",
      "examples": [],
      "teacher_priority": 1,
      "why_selected": ""
    }
  ],
  "suggested_tags": []
}
```

The extracted items should become candidates. They should not become active learning items until approved by the user. The bot should show the full candidate list when Telegram message limits allow it, so the user can see what will enter the lesson pool before approval.

### 25.2. AI exercise generation

Input:

```text
learning item
item type
user level
focus areas
progress state
weakness state
exercise type
business/IT context
lesson plan context
material chunks
```

Expected output:

```json
{
  "exercise_type": "",
  "stage": "",
  "mode": "",
  "topic": "",
  "lesson_goal": "",
  "prompt": "",
  "expected_answer": "",
  "hint": "",
  "explanation": "",
  "target_learning_item_ids": []
}
```

Exercise generation can be automatic and does not require user confirmation. Generated exercises should fit a 15-minute session of 15-20 micro-drills and should remain short enough for Telegram.

### 25.3. AI answer checking

Input:

```text
exercise prompt
expected answer or target item
user answer
user level
business/IT context
```

Expected output:

```json
{
  "status": "correct | partially_correct | incorrect",
  "corrected_answer": "",
  "natural_answer": "",
  "mistake_summary": "",
  "why_wrong": "",
  "rule": "",
  "error_layer": "",
  "native_rewrite": "",
  "native_rewrite_reason": "",
  "why_layer": "",
  "l1_hits": [],
  "confidence_rating": 5,
  "format_feedback": {},
  "better_variants": [],
  "micro_drill": "",
  "teacher_note": "",
  "detected_mistake_type": "",
  "should_create_mistake_event": true,
  "should_create_or_update_mistake_pattern": false
}
```

Immediate feedback should be compact: verdict, correction, what was wrong, why,
one practical rule, one better variant, and Russian L1 hits when deterministic
rules apply. Detailed layers are stored with the attempt and can be shown later
using `/feedback explain <attempt_id>` or the Errors / Native / Why buttons
without requiring another AI call.

Named EPIC-22 lesson formats may add structured `format_feedback` to the stored
attempt: Notebook native-diff mined chunks, Discourse Builder cohesion metadata,
Critical Reading task metadata, and Mistake Drill extinction-state metadata.
The owner can also seed a static 10-genre business/IT writing curriculum; each
seeded plan uses `LessonPlan.format="genre"` and normal per-user progress.
The teacher layer may choose the next lesson mode through a structured Lesson
Director decision, write a private markdown Coach Journal, and show a Hint
Ladder for confirmed recurring mistake patterns.
Operational utility commands provide structured just-in-time practice cards for
meeting prep, article analysis, debate, RU→EN transfer, and 4-3-2 fluency.

---

## 26. MVP success criteria

MVP is successful if:

```text
1. User can upload text materials after a lesson.
2. Bot extracts useful words, expressions, rules, and mistakes.
3. Bot explains the lesson title, theme, focus, knowledge areas, and why candidates were selected.
4. User can approve extracted learning items.
5. Bot stores approved items and links them to a reusable lesson pool.
6. Bot automatically generates daily practice based on progress, level, weak points, due items, active lesson plans, and material context.
7. User can complete a 15-minute practice session with 15-20 Telegram-friendly micro-drills.
8. User can skip an exercise and immediately see the correct answer with a short explanation.
9. Bot checks answers and explains mistakes in a teacher-like way.
10. Detailed feedback is available from stored attempt feedback.
11. Mistakes are logged.
12. Recurring mistakes become mistake patterns.
13. Mistake patterns appear in future exercises.
14. Words and expressions are reviewed according to schedule.
15. User can view basic progress.
16. Optional: user can manage items through a lightweight web interface.
```

---

## 27. Example ideal MVP UX

### Example 1 — expression review

```text
Bot:
Today’s English practice — 15 min
Mode: lesson
Lesson: Reported Speech: Introverts, Extroverts, and Workplace Opinions
Goal: Report workplace opinions accurately and diplomatically.

Step 1/16
Guess the expression:
"to politely disagree with an idea or proposal"

User:
push back

Bot:
Almost.
Better:
push back on something

Example:
I’d like to push back on this proposal a bit.

Result: Good
Next review: in 3 days
```

### Example 2 — translation and natural collocation

```text
Bot:
Step 6/16
Translate into English:
"Нам нужно согласовать приоритеты до начала спринта."

User:
We need to align priorities before sprint starts.

Bot:
Good meaning, but more natural:
We need to align on priorities before the sprint starts.

Notes:
1. "align on priorities" is the natural collocation.
2. Use "the sprint" if you mean a specific sprint.

Weak points updated:
- align on something
- articles with specific project events
```

### Example 3 — hedging

```text
Bot:
Step 10/16
Rewrite this sentence in a more diplomatic business style:
"We must change the architecture immediately."

User:
We might need to reconsider the architecture soon.

Bot:
Great.

Why it works:
"might need to" softens the recommendation.
This is useful in stakeholder communication.

Linked rule:
Hedging recommendations
```

### Example 4 — skip and reveal

```text
Bot:
Step 11/16
Choose the more natural reported-speech pattern:
"She suggested ___ the rollout until Monday."

User:
/skip

Bot:
Skipped.
Correct answer:
She suggested delaying the rollout until Monday.

Why:
After "suggest", use a gerund or a that-clause, not an infinitive.

Mini pattern:
suggest doing something
suggest that someone do something
```

---

## 28. Product backlog

```text
EPIC 1: Telegram Bot Foundation
EPIC 2: User Profile and Settings
EPIC 3: Material Upload
EPIC 4: AI Extraction and Candidate Approval
EPIC 5: Learning Items
EPIC 6: Spaced Repetition
EPIC 7: Automatic Practice Generation
EPIC 8: Daily Practice in Telegram
EPIC 9: Exercise Types
EPIC 10: Answer Checking and Feedback
EPIC 11: Mistake Events and Mistake Patterns
EPIC 12: Grammar Rules Graph
EPIC 13: Stats and Weekly Summary
EPIC 14: Favorites
EPIC 15: Optional Lightweight Web Interface
EPIC 16: Staged Learning Engine
EPIC 17: Persistent Lesson Plans
EPIC 18: Structured LLM Gateway
EPIC 19: AI Exercise Generation
EPIC 20: Grammar Brain
EPIC 21: Light Material Context Search
EPIC 22: Breakthrough Roadmap (in progress; pedagogy upgrades, see docs/features/EPIC-22-breakthrough-roadmap.md)
EPIC 23: Shared Lesson Library (planned; content access for multiple users, see ADR-0008)
```

---

## 29. What should be moved to a separate architecture document

Do not decide these details in the PRD. They belong to the architecture document:

```text
1. Docker container on VPS.
2. Backend framework.
3. Telegram Bot API library.
4. Database choice.
5. Background scheduler.
6. AI provider and model choice.
7. Prompt structure.
8. Secrets management.
9. Backups.
10. Logging.
11. Deployment process.
12. Monitoring.
13. Web UI framework.
14. Authentication for web UI.
```

The expected MVP architecture direction can be summarized separately as:

```text
One small personal app deployed as one Docker container on the user's VPS.
Telegram is the main interface.
A lightweight web interface may be added later or as an optional MVP extension.
```

---

## 30. Short instruction for Codex / implementation LLM

```text
Build a personal text-first Telegram bot for English learning.

The bot helps a B2+/C1- user practice business and IT English using the user's own lesson materials.

Do not implement voice features in MVP.

Core MVP flow:
1. User uploads lesson notes or word/expression lists.
2. Bot extracts a lesson overview, knowledge areas, words, expressions, grammar rules, and mistake risks.
3. Extracted items are shown as candidates with the lesson title, theme, focus, and why the items were selected.
4. User approves what should become active learning items.
5. Bot stores approved items and links them to reusable lesson plans.
6. Bot indexes material chunks for lightweight local context search.
7. Bot schedules items for spaced repetition.
8. Bot automatically generates a daily 15-minute practice session based on user level, progress, weak points, due items, active lesson plans, material context, favorite items, and mistake patterns.
9. Daily practice contains 15-20 micro-drills across warmup, input/noticing, controlled practice, grammar or mistake focus, free production, and recap.
10. Exercise generation from approved data does not require confirmation.
11. Adding new active learning items from uploaded materials requires confirmation.
12. Practice includes guess word/expression, translate phrase, cloze, grammar rewrite, error correction, and business/IT follow-up questions.
13. User can skip an exercise to see the correct answer and a short teacher explanation.
14. Bot checks answers, gives corrections, explains mistakes, and updates review state.
15. Detailed teacher feedback can be shown from stored attempt feedback.
16. Mistakes are logged as mistake events.
17. Recurring mistakes become mistake patterns and appear in future practice.
18. Grammar rules can be connected as a graph of concepts.
19. Bot tracks progress, weak items, favorites, due reviews, and basic stats.
20. Optional MVP extension: lightweight web interface for managing items, approving candidates, and viewing stats.

Focus all examples on business English, IT English, meetings, stakeholder communication, architecture discussions, product discussions, risks, trade-offs, prioritization, and delivery.
```
