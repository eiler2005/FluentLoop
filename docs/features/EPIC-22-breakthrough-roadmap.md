# EPIC-22 — Breakthrough Roadmap (idea catalog)

**Status:** Done — Phase 1-2 implemented, deployed, and validated
**Owner:** FluentLoop owner
**Created:** 2026-05-16
**Purpose:** каталог прорывных идей по урокам и продукту плюс execution roadmap. После фиксации решений этот файл стал рабочей спецификацией EPIC-22: Sprint 1 foundation реализуется первым, следующие lesson formats идут по sequencing ниже.

---

## 0. Context — что мы имеем и что в индустрии существует

**FluentLoop сегодня:** 16-step staged session, 15+ exercise templates, naive SRS, mistake events → patterns, lesson plans from uploaded materials, grammar concept graph (EPIC-20), material chunks (EPIC-21), pre-gen lesson cache, weekly summary.

**Что найдено в реальных продуктах (синтез research'а):**

| Продукт | Что они делают круто |
|---------|----------------------|
| **Duolingo Max** | (a) Explain My Answer — pull-not-push объяснения по тапу, (b) Adventures — in-character repair: персонаж в сценарии "не понимает" и просит уточнить, не корректирует напрямую |
| **Speak** | (a) Roleplay с **3-мя явными задачами** и автозакрытием при их выполнении, (b) Proficiency Graph — отслеживает, какие конкретные структуры показал ученик, и калибрует **свой** output под "1 stretch / 1 review" на ход |
| **Praktika** | **Multi-agent**: один LLM ведёт диалог в роли (не корректирует), второй отдельно анализирует transcript и пишет отчёт |
| **Loora** | **"Culturally awkward but grammatically correct" flagging** — ошибки = одно, native-rewrite = другое. Разные каналы фидбэка |
| **Khanmigo** | (a) Socratic refusal — не даёт ответ, ведёт вопросами, (b) Writing Coach — outline → draft → revision, ни одной строчки за ученика |
| **Falou** | **Cold-recall closer** — каждый урок заканчивается продуктивным recall без подсказок |
| **TalkPal** | **Debate mode** — бот аргументирует противоположную позицию жёстко |
| **Quazel/Univerbal** | **Scene Builder** — ученик авторит сценарий: тема / партнёр / задачи |
| **Pimsleur** | **Graduated Interval Recall**: sub-day интервалы 5s → 25s → 2min → 10min → 1hr → 5hr → 1d → 5d → 25d → 4mo → 2yr. **Никто из FSRS/SM-2 это не делает.** |
| **Glossika** | Reverse-translation drill (русский → английский эквивалент) + FSRS на отдельных предложениях, не словах |
| **LingQ** | **Auto-promote** слова в "known" при пассивном встрече ×3 без lookup |
| **Migaku / Refold (MIA)** | **1T rule** — добавляем sentence в SRS только если ровно одно неизвестное в нём для этого ученика. + **sentence cards, не word cards** |
| **Clozemaster** | **5–7 typed retrievals** — эмпирический порог для productive automatization |
| **Memrise "Learn with Locals"** | 3-5-секундные клипы носителей по теме — text-only заменяется на **screenshots native discourse** (Slack-тред / email скрин / Reddit-цитата) |
| **BreakingNewsEnglish** | **40+ модулей упражнений из одной статьи** — единый pipeline "статья → урок" |
| **ESL Brains C1** | **5 lesson formats** на одном контенте: Standard / Speaking / Critical Reading Club / Flipped / Vocabulary Lab |
| **Cambridge CAE Writing Part 2** | 5-genre menu: **essay / proposal / report / review / letter** — clean taxonomy |
| **Business English Pod** | Episode = dialogue → commentary → practice. Группировка по 2–5 эпизодов на skill arc |
| **italki Notebook** | Ученик пишет свободный текст → native правит inline. (Продукт убрали в 2020 — механика жива) |
| **Lingoda Sprint** | 30 уроков за 60 дней с **cashback за консистентность** — повышение через жёсткую дисциплину |
| **Market Leader Advanced (Pearson)** | Unit = 8 секций: Discussion → Vocab → Reading → Listening → Language Review → Skills → Case Study → Cross-cultural |

**SLA-научный фундамент:** Lexical Approach (Lewis), TBLT (Ellis/Long/Willis), Genre-based (Halliday/Martin), ZPD/Dynamic Assessment (Vygotsky/Lantolf), Skill Acquisition (DeKeyser), Noticing (Schmidt), Output (Swain), Focus on Form (Long), Politeness (Brown & Levinson). Главное — **Russian L1 interference inventory** (списки калек, артиклей с абстрактными существительными, conditional with `would have`, prepositional collocations).

---

## 1. Тезис: что значит "прорыв" для FluentLoop

> Хороший советский тренер по фигурному катанию выигрывает не потому, что **сложнее прыжки**, а потому, что **тренировка спроектирована**. Все Tier-1 пункты ниже — это **дизайн тренировки**, а не "ещё одна механика".

Конкретно прорыв в трёх измерениях:

1. **Каталог уроков как у настоящего курса** — 15+ именованных типов уроков с явной целью, длиной, скелетом, критерием успеха. Не "сегодня 16 шагов микродрила" — а "сегодня Critical Reading Club по этой статье".
2. **Два слоя обратной связи** — отдельно ошибки, отдельно native-rewrite. Грамматика ≠ зрелость речи.
3. **Sub-day consolidation + sentence-level SRS + chunk-curriculum** — память работает иначе, чем "due_at = +3d".

---

## 2. Конкретные форматы уроков (catalog of 15 lesson types)

Каждый формат — **отдельная команда** в боте + tag в `LessonPlan.format`. Bot offers them via `/today` selection или Lesson Director выбирает.

### F1. Article Lab (BreakingNewsEnglish pattern + LingQ + Refold 1T)

**Input:** пользователь шлёт URL/PDF/текст статьи в боте.
**Pipeline:** статья прогоняется через **17-модульный pipeline** (украдено у BNE):

- **Pre-read:** topic chat (open question), word-association на главное понятие
- **Vocab pre-teach:** 8 ключевых chunks из статьи (выбираются по 1T-rule + collocation novelty)
- **Listening:** TTS-озвучка статьи в 3 скоростях → пока не для voice-mode, можно отложить
- **Reading:** разметка незнакомых слов (LingQ-стиль) — синие, жёлтые, белые
- **Comprehension:** 8 MCQ + 4 open questions
- **Gap-fill / cloze:** 12 пропусков на ключевые collocations (не на грамматику — пропускаются именно chunks)
- **Synonym match:** 10 пар
- **Phrase match:** 10 пар collocations
- **Multi-choice cloze:** 12 пунктов
- **Word-order reconstruction:** 3 сложных предложения из статьи
- **Sentence-jumble:** реконструкция параграфа
- **Article noticing:** "найди в статье 3 hedging device, 2 places where author signals doubt"
- **Critical question:** "С каким утверждением автора ты не согласен и почему?"
- **Writing prompt** (10 min free write): "Объясни коллеге главную мысль статьи в 5 предложениях"
- **Survey question** генерируется автоматически
- **Discussion question** для следующего session
- **Internet research follow-up**

**Spread over 30 days** (Yabla "one source, many surfaces"):
- Day 1: vocab pre-teach + reading + 1T cloze (5–8 items по Pimsleur cap)
- Day 1 in-session re-prompt: cloze re-firing на ~30s, ~2min, ~10min (Pimsleur GIR)
- Day 2: comprehension MCQ + re-cloze в **парафразированных** предложениях (transfer test)
- Day 3, 7: typed cloze → reverse-translation (Glossika) → writing prompt с обязательным использованием 3 mined chunks
- Day 14: пользователь summary'ит статью, bot скорит активное использование chunks
- Day 30: те же items resurface внутри **другой** загруженной статьи (cross-source reinforcement)

**Per-item state machine:** `seen → recognised → recalled → produced → mastered`. Gated на конкретные действия (см. Skill Acquisition Theory).

**Impact:** ⭐⭐⭐⭐⭐ — это **flagship product**. **Cost:** L (pipeline + 30-day cron). Самая дорогая фича в плане. Можно начать с 5-модульной версии и наращивать.

---

### F2. Diplomatic Rewrite Drill (Linguahouse + Brown & Levinson)

**Цель:** Pragmatic Competence — закрыть главный гэп Russian L1 на C1+.

**Skeleton:**
- Bot даёт 5–7 "blunt" Russian-stylized английских предложений
- Ученик переписывает в 3 регистрах: very polite / professional / direct-but-not-rude
- Bot скорит **по hedging-density** (модальные глаголы вероятности, ослабляющие наречия, indirect speech acts)
- Surface "more native" rewrite каждого (Loora-style)
- Cold-recall closer (Falou): новая ситуация — производит ответ без подсказки

**Пример сессии:**
> Bot: "Перепиши: 'Your code is bad and won't work in production.'"
> User: "I'm worried this might run into issues in production — could we walk through the edge cases together?"
> Bot: ✅ Hedging density 0.4 (target ≥0.3). Native alternative: "I might be missing something, but I'm a bit concerned about how this will hold up in production — mind if we trace through a few edge cases?"

**Bank:** ~200 blunt situations, тегированных по P/D/I (Power/Distance/Imposition — Brown & Levinson). Auto-generated via LLM + curation за один вечер.

**Impact:** ⭐⭐⭐⭐⭐ — самая прямая атака на C1→C1+. **Cost:** S.

---

### F3. Critical Reading Club (ESL Brains)

**Skeleton (15 min):**
- 1 long-form статья (не короткая news)
- Up-front noticing focus: "обрати внимание на способы автора **поставить под сомнение** мейнстрим-позицию"
- Reading (~5 min) with click-translation (Readlang-style — пришлёшь chunk → bot объясняет inline + сохранит в active deck)
- 4 critical questions (не comprehension; argumentation analysis): "найди в тексте hedging / signposting / register shifts / counter-argument"
- Discussion turn (Dogme-style): "С каким аргументом ты бы поспорил? Как бы ты его опроверг?" — bot отвечает контр-аргументом в **debate mode** (TalkPal)
- Recap: 3 chunks из статьи → cold recall

**Impact:** ⭐⭐⭐⭐⭐ — это **самый недотрогенный навык на C1**. **Cost:** S.

---

### F4. Writing Workshop — 5 жанров CAE rotation (Cambridge Writing Part 2 + Khanmigo Writing Coach)

**5 genres:**
- **Essay** (220–260 слов) — argument with 2 prompts
- **Proposal** — recommendation memo for stakeholders
- **Report** — формальный, с графиком/числами
- **Review** — критический обзор (tool/book/event)
- **Formal letter / professional email** — escalation, polite refusal, complaint, request

**Skeleton по Khanmigo Writing Coach (никогда не пишет за ученика):**
- Bot предлагает 3 типа задания на выбор для текущего жанра
- Stage 1 — **Outline**: ученик пишет outline (3–5 points). Bot скорит по structural completeness (через genre schema)
- Stage 2 — **Draft**: ученик пишет полный текст. Bot даёт **diff** с two-layer feedback (errors / native-rewrite). Подсвечивает структурные дыры: "missing Impact stage in post-mortem"
- Stage 3 — **Revision**: ученик переписывает. Bot сравнивает draft vs revision, считает MTLD / hedging density / sentence complexity
- Bot **никогда не пишет за ученика**, только Socratic prompts (Khanmigo)

**Spaced:** один жанр в неделю rotation. Месячный артефакт по каждому жанру (Coursera capstone-pattern).

**Impact:** ⭐⭐⭐⭐⭐ — **писать длинные тексты на C1** — это **главное** для IT/business. **Cost:** M.

---

### F5. Business-Scenario Roleplay (Speak Live Roleplays + Quazel Scene Builder)

**Skeleton (10–15 min):**
- Сценарий (один из 40+ pre-built, см. Section 3) или **Scene Builder** (Quazel): пользователь авторит за 30 сек — топик, роль контрагента, своя роль, **3 explicit tasks**
- Bot **в роли** (не корректирует mid-flow) — Praktika split agent
- Pushed output по Swain: каждый ход bot предъявляет stretch element 1 уровень выше пользователя (Speak Proficiency Graph)
- In-character repair (Duolingo Max Adventures): если ученик сказал лажу, контрагент в роли удивляется и просит уточнить ("Sorry, I didn't catch that — you wanted to *postpone* the meeting?") — это **noticing prompt**, не correction
- Auto-closure: bot tracks task completion в state; сессия закрывается, когда 3 задачи выполнены или диалог естественно сворачивается
- **Post-session report** (Praktika split — отдельный LLM-call): two-layer feedback на весь transcript

**Пример Scene Builder:**
```
/scene topic="negotiating Q3 scope reduction"
       their_role="impatient PM, prefers to add features"
       my_role="tech lead, capacity-constrained"
       tasks="(1) acknowledge their priorities (2) propose specific cut (3) get to written agreement"
```

**Impact:** ⭐⭐⭐⭐⭐ **Cost:** M.

---

### F6. Debate Mode (TalkPal)

**Skeleton:**
- Ученик заявляет позицию (по работе / технологии / индустрии)
- Bot аргументирует **противоположную** позицию **жёстко**, без поблажек
- 5–7 ходов диалога
- После: post-session report по hedging / concession / counter-arguing language (это **C1+ навык**, который не качается friendly роlepleay'ями)

**Impact:** ⭐⭐⭐⭐ **Cost:** S.

---

### F7. Notebook (italki) — Daily Free Write + Annotated Diff

**Skeleton (5–10 min):**
- Bot предъявляет один открытый prompt из real-work-context ("describe yesterday's most painful technical conversation in 4–5 sentences")
- Ученик пишет free text
- Bot возвращает **annotated diff** в 3 слоя (Loora):
  - **errors** (grammar, articles, prepositions, calques) с пометкой priority (high — explicit rule, med — collocation, low — stylistic)
  - **native-rewrite** одной фразы с объяснением "почему так звучит лучше"
  - **collocation upgrades** (Lexical Approach) — 1–3 "do a mistake → make a mistake"
- All mined items → fed into SRS как `LearningItem` с source `notebook_YYYY-MM-DD`
- Errors → mistake events (existing EPIC-11)

**Impact:** ⭐⭐⭐⭐⭐ — это **самый дешёвый источник production data**. **Cost:** S.

---

### F8. Vocabulary Lab (ESL Brains + Lexical Approach)

**Skeleton (15 min) — sequential micro-rounds:**
- Тема: одно концептуальное поле (UNCERTAINTY / DISAGREEMENT / DECISION / INFLUENCE / CRITIQUE / SUPPORT / TIME-MANAGEMENT)
- 6–8 native chunks из выбранного поля
- Round 1: **collocation box** — verb→noun matching ("an underlying ___" → assumption/principle/cause)
- Round 2: **paraphrase ladder** — same content в 3 регистрах (formal / collegial / casual)
- Round 3: **cloze in context** — 6 натуральных предложений с пропусками
- Round 4: **reverse-translation** (Glossika) — Russian gloss → English target, typed
- Round 5: **cold-recall closer** (Falou) — новая ситуация, выбрать правильный chunk
- All chunks → SRS с tag `field=<field_name>`

**Bank:** "Frame Semantics Map" — 8–10 концептуальных полей × 30 chunks = ~300 chunks. Curated за пару вечеров.

**Impact:** ⭐⭐⭐⭐⭐ — **Lexical Approach в чистом виде**. **Cost:** M.

---

### F9. Listening Transcript Study (text-only сейчас; voice TTS позже)

**Skeleton:**
- Сейчас в текстовом виде: transcript study без аудио — ученик читает stenogram of authentic speech (Stripe engineering podcast, Lex Fridman, founder interviews) → noticing → chunk harvest
- Когда воткнём voice TTS: аудио в 3 скоростях, dictation, comprehension MCQ

**Impact:** ⭐⭐⭐⭐ **Cost:** S (без voice); M (с voice позже).

---

### F10. Translation Lab — RU→EN с corpus comparison (Glossika)

**Skeleton:**
- 5–7 русских business-предложений уровня complexity
- Ученик переводит каждое
- Bot сравнивает с **native idiomatic** version (не дословным переводом)
- Detect калек, прямых L1 transfers (см. Russian L1 hit list ниже)
- Surface 1 best native alternative per sentence

**Impact:** ⭐⭐⭐⭐ — прямая атака на L1 interference. **Cost:** S.

---

### F11. Discourse Builder (Genre-based + ESL Brains Speaking Class)

**Skeleton (15 min) — sentence-level → discourse-level:**
- **Argumentation build:** 1 topic sentence → ученик строит 4-sentence argument (topic + 2 supporting + counter)
- **Cohesion repair:** даётся параграф без connectives → восстанови переходы
- **Signposting drill:** даётся текст-flat → вставь macro и micro signposts
- **Register shift:** одна мысль в 3 регистрах (formal report / colleague Slack / casual chat)
- Bot скорит **дискурсивно**: connective accuracy, paragraph structure, topic progression

**Impact:** ⭐⭐⭐⭐⭐ — это **главный навык B2+ → C1**, который sentence-level упражнения не качают. **Cost:** M.

---

### F12. Mistake Drill — твои ошибки = твой curriculum (Error-as-Material)

**Skeleton:**
- 5–7 упражнений, **сгенерированных из последних mistake patterns** ученика
- Для каждой ошибки — **причинная диагностика** (L1-transfer / grammar gap / register mismatch / pragmatic transfer)
- **Minimal pairs**: 6–8 контрастных native examples
- Drill в 2 модах: recognition → production
- **Extinction tracking:** 10 правильных подряд → demote pattern

**Impact:** ⭐⭐⭐⭐ **Cost:** S (надстройка над EPIC-11).

---

### F13. Boss Mode / 4-3-2 Fluency (DeKeyser)

**Skeleton:**
- Ученик пишет короткий текст (3–4 предложения) на заданную тему
- Bot задаёт переписать **то же самое** за 3 минуты → за 2 минуты → за 1 минуту
- Метрики: word count delta, lexical diversity drop/preserve, error rate under pressure
- Это **automaticity training** — то, что отличает B2+ от C1

**Impact:** ⭐⭐⭐⭐ **Cost:** S.

---

### F14. Pre-Meeting Brief (Just-In-Time)

**Skeleton:**
- Ученик шлёт agenda встречи / название проекта / название клиента
- Bot за 30 сек делает **mini-brief**:
  - 5–7 ключевых chunks для этой темы
  - 2 typical phrasings для типичных moves встречи (open / pushback / clarify / close)
  - 1 likely Russian-L1 trap для этой темы
  - 3 hedging templates на случай неопределённости
- All chunks → flagged with `source=brief_<date>` для следующей сессии review

**Impact:** ⭐⭐⭐⭐ — **операционная польза в моменте**, единственное реально внедряющееся в рабочий день. **Cost:** S.

---

### F15. Mentor's Question — Weekly Socratic Conversation

**Skeleton (5–10 min, раз в неделю):**
- Bot не даёт упражнений
- Сократическая беседа в open chat: "что было самым трудным на английском за неделю?", "если бы тебе сейчас нужно было объяснить ваш текущий incident senior engineer'у с нуля — с чего бы начал?", "что новое заметил в речи коллег?"
- Свободный output
- Bot **harvests** language за разговор → пополняет SRS
- Метакогнитивно: bot summарит **что ученик не смог выразить** (по hesitation markers, simplifications) → план на след. неделю

**Impact:** ⭐⭐⭐⭐ — **stretched authentic output + диагностика того, что ещё не освоено**. **Cost:** S.

---

## 3. Сценарная библиотека — 40 business-IT situations

Pre-built bank для F5 (Roleplay) и F2 (Diplomatic Rewrite). Каждый сценарий — **YAML-карточка**: setting, my_role, partner_role, 3 tasks, P/D/I parameters, target functional language, target chunks, common L1 traps.

**Категории:**

**Project / Engineering communication (10):**
1. Design review — defend choice А vs Б
2. Code review feedback — receive criticism gracefully
3. Code review feedback — give criticism diplomatically
4. RFC discussion в Slack threading
5. Incident post-mortem facilitation
6. Architecture migration proposal
7. Tech-debt prioritization debate
8. Scope renegotiation with PM
9. Estimation pushback ("realistically it's 3 weeks not 1")
10. Cross-team dependency negotiation

**Customer / vendor (8):**
11. Customer demo opening + Q&A handling
12. Customer escalation absorb + de-escalate
13. Vendor pricing pushback
14. Vendor SLA negotiation
15. Discovery call — listening, paraphrasing, clarifying
16. Bad news to customer (delay, defect, deprecation)
17. Sales hand-off conversation
18. Reference call (give a reference for ex-coworker)

**People / management (8):**
19. 1:1 mentoring conversation
20. Performance review — giving
21. Performance review — receiving
22. Salary negotiation
23. Promotion case presentation
24. Resignation conversation
25. Hiring interview — interviewer (senior IC)
26. Hiring interview — candidate (going for staff/principal)

**Leadership / executive (6):**
27. Standup update (clear, concise, no rambling)
28. Quarterly all-hands speech
29. Board update on engineering velocity
30. Tech blog post draft for company
31. Investor demo (technical founder)
32. Conference talk Q&A handling

**Conflict / face-risk (8):**
33. Disagree with senior architect publicly
34. Tell teammate they're underperforming
35. Push back on micromanagement gently
36. Decline scope creep ("no, but here's what we can do")
37. Apologize for production outage (no blame externalize)
38. Diplomatic refusal of impossible deadline
39. Asking for help when you should know
40. Admitting "I don't know" without losing face

Каждый сценарий ~5 минут авторинга + LLM-расширение. **Один вечер курации.**

---

## 4. Two-Layer Feedback Model

**Главная идея, украденная у Loora:** разделить **errors** и **native rewrite**.

После каждого user-output (любой формат):

```
✅ / ⚠️ / ❌ — короткий verdict (1 строка)

[tappable] Errors → 1-2 предложений: что неправильно по правилу
[tappable] Native rewrite → "more idiomatic / more business-register" + 1 строка почему
[tappable] Why? → deep explanation (pull-not-push, Duolingo Max)
```

- **Errors** — для B2 базы (articles, prepositions, tenses). **Никогда** не дублируется в native-rewrite.
- **Native-rewrite** — для C1 ceiling. Только когда есть **реальный idiomatic upgrade**, не косметика.
- **Why?** — выгружается только на тап, не drown'ит сессию.

**Реализация:** существующий `_render_feedback` рефакторится в 3-layer output. Two separate LLM-calls (Praktika split): один на error detection (структурный), второй на idiomatic-rewrite (стилистический).

**Impact:** ⭐⭐⭐⭐⭐ **Cost:** S.

---

## 5. Pimsleur Sub-day SRS — закрытие самого большого slip'а в современных SRS

**Что украл у Pimsleur:** Graduated Interval Recall с **sub-day** интервалами:

```
5s → 25s → 2min → 10min → 1hr → 5hr → 1d → 5d → 25d → 4mo → 2yr
```

**Что есть сейчас:** SRS работает в днях. Item видится впервые → следующее повторение через 0–7 дней. **6 ранних retrievals в Pimsleur полностью пропускаются современными SRS.**

**Что делаем:**
- Внутри **одной сессии** новый item должен прозвенеть 3–4 раза (на ~30s, ~2min, ~10min)
- Followup в **той же сессии** или сразу после — на 1hr (если сессия длиннее) или на следующий sync (push после ~5hr)
- Только после 6 in-session retrievals → передача в FSRS-5 daily scheduler

**Реализация:** новый `InSessionScheduler` поверх FSRS. Не заменяет FSRS, а **дополняет его слева** (короткие интервалы).

**Impact:** ⭐⭐⭐⭐⭐ — это **самое большое улучшение retention**, которое современные spaced-repetition приложения **не делают**. **Cost:** S-M.

---

## 6. Lexical Chunks Curriculum — 3000 chunks под IT/business

**Что украл из Lexical Approach + Glossika + Frame Semantics:** учим **chunks**, не слова. Системно.

**Структура:**
- **9 концептуальных полей** (frame semantics): UNCERTAINTY / DISAGREEMENT / DECISION / INFLUENCE / CRITIQUE / SUPPORT / TIME / RESPONSIBILITY / NEGOTIATION
- **5 регистров на каждое поле:** very formal / professional / collegial / casual / blunt-direct
- **3 коммуникативные функции на каждое:** hedging / signposting / softening
- ~3000 chunks total, тегированных по полю/регистру/функции/жанру

**Примеры chunks по полю UNCERTAINTY:**
- *very formal:* "it remains an open question whether..."
- *professional:* "I'm not yet convinced that..."
- *collegial:* "I'm in two minds about this"
- *casual:* "I'm honestly not sure"
- *blunt:* "I don't know"

**Acquisition pipeline (5–7 typed retrievals per chunk, Clozemaster):**
```
seen (passive)
  → recognised (correct MCQ ×2)
  → recalled (cloze ×2)
  → produced (used in free output ×1)
  → mastered (used in 3 different contexts)
```

**Bank generation:** один Pro DeepSeek-call на 100 chunks за раз × 30 раз → seed bank. Curation за один вечер (~3 часа).

**Impact:** ⭐⭐⭐⭐⭐ **Cost:** M.

---

## 7. Russian L1 Interference Hit List — deterministic targeting

**Что украл из RILEC + study.ru + Heather Hughes corpus:** 30 высокочастотных Russian-transfer ошибок, для которых **детерминированный regex/rule + LLM verify** даёт точность ≥95%.

**Categories:**

**Verb-noun calques:**
- `do a mistake` → make
- `open a business` → start/launch
- `make a research` → do/conduct + mass noun
- `take a decision` (БрЕнгл OK, амер. нет) → make
- `put a question` → ask/raise

**Adjective-noun collocations:**
- `strong rain` → heavy
- `strong pain` → severe/acute
- `big price` → high
- `cheap quality` → poor/low

**Prepositional collocations:**
- `depend from` → depend on
- `consist from` → consist of
- `discuss about` → discuss (no prep)
- `participate at` → participate in
- `influence on` (only as noun, not verb)

**Lexical false friends:**
- `actual` (RU = current) → English **real** ≠ intended
- `normal` (RU = acceptable) → English colder
- `technic` → technique/technology/equipment
- `economy` vs `economics`
- `politics` vs `policy`

**Aspect/tense:**
- `I have seen him yesterday` → past simple
- `if I would have known` → if I had known
- under-use of past perfect in narrative

**Articles:**
- zero article with abstract nouns at sentence start
- generic plurals vs `the X`
- the institutions

**Pragmatic:**
- bare imperatives in email
- insufficient hedging
- over-use of "of course"
- over-use of "in my opinion"

**Implementation:** `russian_l1_filter.py` — модуль с 30 rules. Запускается перед LLM-based error detection. Хиты автоматически → mistake events с pre-filled causal hypothesis.

**Impact:** ⭐⭐⭐⭐⭐ **Cost:** S.

---

## 8. Lesson Director — agentic teacher

**Что украл из Praktika multi-agent + Khanmigo + Lesson Plans EPIC-17:**

Заменить детерминированную ротацию стадий на **LLM-агент**:
- Tools: `get_due_items()`, `get_journal_last_n_entries()`, `get_genre_progress()`, `get_skill_tree_state()`, `get_recent_mistake_patterns()`, `pick_lesson_format()`, `pick_scenario()`, `build_session_blueprint()`
- System prompt: SLA principles (Krashen, Swain, Schmidt, ZPD, FonF, Pawley-Syder formulaicity)
- Authority: **выбрать сегодняшний lesson format** (F1–F15) + content + объяснить ученику цель: "сегодня делаем Diplomatic Rewrite — на прошлой неделе ты на трёх pushback'ах падал в директивный регистр. Цель — освоить 5 hedging chunks для disagreement"

**Multi-agent split (Praktika):**
- **Conversation Agent** — ведёт сессию, в роли (если roleplay), no mid-flow corrections
- **Grading Agent** — отдельный pass, скорит transcript, пишет feedback, проставляет SRS
- **Coach Agent** — в конце недели пишет narrative observation в Coach's Journal

**Impact:** ⭐⭐⭐⭐⭐ **Cost:** M.

---

## 9. Coach's Journal — narrative observations, не статистика

**Что украл из реального педагогического практикума:** хороший тутор ведёт **журнал наблюдений**, а не таблицу.

После каждой сессии — Pro-call → narrative ≤300 слов в `data/journal/YYYY-MM-DD.md`:

> 2026-05-16, session #142. Денис уверенно использует `the underlying assumption is that...`, активно вошло за 2 недели. **Замечено:** 4 попытки построить Conditional Type 3 → в 3 fall-back на `would have been + Simple`. Избегает `should have / could have`. **Гипотеза:** модальные перфекты воспринимаются как избыточная вежливость в техническом контексте. **Гипотеза 2:** возможно подсознательное избегание retrospective blame, поэтому уход в безличные формы. **Стоит проверить:** через F5 roleplay incident retrospective, где явно требуется retrospective regret expression.

Журнал → input для следующего Lesson Director call.

**Impact:** ⭐⭐⭐⭐⭐ — это **то, чего нет ни у одного language-app**. **Cost:** S.

---

## 10. Evaluation Harness — петля обратной связи на обучении

**4 mechanism:**

1. **Held-out test set** (10% новых items hidden) → cold quiz через 30/60/90 дней
2. **Longitudinal writing baseline** — один и тот же prompt раз в месяц ("Describe your team's biggest engineering challenge this quarter"). NLP-метрики: MTLD, mean clause length, hedging density (counting modal verbs of probability, "may/might/could/seem/tend/appear"), chunk usage rate, error density
3. **Skill-tree mastery probes** — раз в месяц 15-min adaptive test (IRT-driven), CEFR Reading & Use of English style: 8 grammatical transformations, 10 vocab-in-context MCQ, 12 cloze, 1 short writing
4. **A/B на типах упражнений** — для одного chunk случайно выбирать F-формат, через 30 дней мерить retention

**Impact:** ⭐⭐⭐⭐⭐ **Cost:** S-M.

---

## 11. Genre-Aware Curriculum (Halliday/Martin sydney school)

**Что украл из Sydney School + Cambridge CAE Part 2:**

Куррикулум организован не по грамматике, а по **жанрам производимых артефактов**:

| Genre | Schema (stages) | Target lexicogrammar |
|-------|----------------|----------------------|
| Incident post-mortem | Timeline → Impact → Root cause → Remediation → Prevention | passive voice for blameless, past perfect for sequence, hedged conclusions |
| RFC / decision memo | Problem → Constraints → Options → Trade-offs → Recommendation | comparative, modals of probability, signposting |
| Status update (standup) | What I did → What I'm doing → Blockers | present simple, present continuous, conditional |
| Architecture proposal | Context → Proposal → Alternatives considered → Risks → Migration plan | hedging, future perfect, conditionals |
| Performance review (give) | Strengths → Growth areas → Specific examples → Goals | indirect feedback, mitigated negatives |
| Performance review (receive) | Acknowledge → Clarify → Reflect → Commit | active listening markers, hedging response |
| Customer escalation response | Acknowledge → Investigate → Action → Prevent | empathy markers, future-perfect commitments |
| Cold outreach email | Context → Reason → Ask → Soft close | softened modal questions |
| Technical blog post | Hook → Problem → Solution → Trade-offs → Conclusion | discourse markers, hedging, formal connectives |
| Conference talk Q&A | Acknowledge → Rephrase → Answer → Bridge | thinking-time fillers, polite hedge, brief commit |

**Каждый жанр** = ~50 signature chunks + schema scorer + 5 example artifacts + 3 critique-target traps.

**Implementation:** новая таблица `Genre`, привязанная к `LessonPlan`. `/practice genre <name>`.

**Impact:** ⭐⭐⭐⭐⭐ **Cost:** M (10 жанров — один вечер каждого).

---

## 12. Sprint Mode (Lingoda + James Clear)

**Sprint configuration:**
- 30 sessions в 30 дней (1 ежедневно) или 60 sessions в 60 дней
- Defined start/end date
- **Streak as commitment**, не gamification: пропуск дня → sprint reset
- "Cashback" заменяется на **самонаграду**: ученик задаёт reward себе в начале sprint'а ("если выполню — куплю N")
- Прогресс-bar и явная цель (например: "к концу sprint'а — Diplomatic Rewrite mastered, F7 Notebook 30/30 entries written")

**Бот:**
- `/sprint start 30days goal="diplomatic_competence"`
- Daily reminder в Sprint time
- Daily mini-summary "Day 12/30, 4 chunks promoted to mastered"

**Impact:** ⭐⭐⭐ **Cost:** S.

---

## 13. Hint Ladder + Socratic Correction (Vygotsky/Lantolf + Khanmigo)

**Что украл из Dynamic Assessment + Khanmigo Socratic refusal:**

При ошибке — **не давать сразу ответ**. Ladder:

```
Level 0 (silent): "Try again."
Level 1 (implicit): "There's something off in the second clause."
Level 2 (category): "It's about the preposition."
Level 3 (contrast): "Do we say 'depend ON' or 'depend FROM'?"
Level 4 (give): "It's 'depend on'."
```

Bot фиксирует, на каком уровне ученик восстановил. Время → ladder сдвигается выше (т.е. меньше scaffolding). Это **dynamic assessment** + **fading scaffolding** = ZPD operationalized.

Применяется **только** на mistake patterns с `confidence=high` (известные ученику ошибки). Для нового материала — прямая подача правила.

**Impact:** ⭐⭐⭐⭐ **Cost:** S.

---

## 14. Прочие "стащенные" мелочи (XS-S effort, заметный эффект)

- **Cold-recall closer** (Falou) — каждая сессия заканчивается **одним** productive recall без подсказки. Никаких "you finished!" на multiple choice.
- **Auto-promote known words** (LingQ) — chunk встречен в reading ×3 без lookup → promoted to "known".
- **Calibrated confidence** (research) — pre-submit 1-tap rating (1–5); tracking calibration; overconfident wrong → priority.
- **Reflective Practice Loop** — в конце сессии 1 открытый вопрос ("что было самым трудным?"), ответ → в журнал. Weekly summary показывает паттерны рефлексии. +20–40% retention (research consensus).
- **Rolling Native Comparison** — bot ведёт corpus твоих writing samples; каждые 2 недели показывает: версия от 6 недель назад vs вчера. Visible progress = motivation.
- **The "Why" Layer** — каждый chunk → mini-story (etymology / metaphor / cultural). Elaborative encoding effect.

---

## Сводная таблица: импакт × затраты

| # | Формат / механика | Источник | Impact | Cost |
|---|---|---|---|---|
| F1 | **Article Lab** (30-day pipeline) | BNE + Yabla + Refold | ⭐⭐⭐⭐⭐ | L |
| F4 | **Writing Workshop** (5 CAE genres) | Cambridge + Khanmigo | ⭐⭐⭐⭐⭐ | M |
| F5 | **Roleplay** (3-tasks + Scene Builder + split agent) | Speak + Quazel + Praktika | ⭐⭐⭐⭐⭐ | M |
| F11 | **Discourse Builder** | Genre-based / ESL Brains | ⭐⭐⭐⭐⭐ | M |
| F2 | **Diplomatic Rewrite** | Linguahouse + B&L | ⭐⭐⭐⭐⭐ | S |
| F3 | **Critical Reading Club** | ESL Brains | ⭐⭐⭐⭐⭐ | S |
| F7 | **Notebook** (daily free write) | italki | ⭐⭐⭐⭐⭐ | S |
| F8 | **Vocabulary Lab** + Frame Semantics | Lexical Approach + ESL Brains | ⭐⭐⭐⭐⭐ | M |
| #4 | **Two-layer feedback** (errors / native-rewrite) | Loora | ⭐⭐⭐⭐⭐ | S |
| #5 | **Pimsleur sub-day SRS** | Pimsleur GIR | ⭐⭐⭐⭐⭐ | S-M |
| #6 | **Chunks Curriculum** (3000 items) | Lexical Approach + Glossika | ⭐⭐⭐⭐⭐ | M |
| #7 | **Russian L1 hit list** | RILEC + corpus | ⭐⭐⭐⭐⭐ | S |
| #8 | **Lesson Director** (agentic + split) | Praktika + Khanmigo | ⭐⭐⭐⭐⭐ | M |
| #9 | **Coach's Journal** | педагогический практикум | ⭐⭐⭐⭐⭐ | S |
| #10 | **Evaluation Harness** | research | ⭐⭐⭐⭐⭐ | S-M |
| #11 | **Genre Curriculum** + schemas | Sydney School | ⭐⭐⭐⭐⭐ | M |
| F6 | **Debate Mode** | TalkPal | ⭐⭐⭐⭐ | S |
| F10 | **Translation Lab** | Glossika + L1 hit list | ⭐⭐⭐⭐ | S |
| F12 | **Mistake Drill 2.0** | extension EPIC-11 | ⭐⭐⭐⭐ | S |
| F13 | **4-3-2 Fluency** | DeKeyser | ⭐⭐⭐⭐ | S |
| F14 | **Pre-Meeting Brief** | own idea | ⭐⭐⭐⭐ | S |
| F15 | **Mentor's Question** (weekly) | Dogme | ⭐⭐⭐⭐ | S |
| #13 | **Hint Ladder** | Vygotsky + Khanmigo | ⭐⭐⭐⭐ | S |
| #12 | **Sprint Mode** | Lingoda | ⭐⭐⭐ | S |
| #3 | **40-scenario library** | own + Engoo | ⭐⭐⭐⭐ | M (1 evening) |
| — | Cold recall closer | Falou | ⭐⭐⭐ | XS |
| — | Auto-promote known | LingQ | ⭐⭐⭐ | XS |
| — | Calibrated confidence | research | ⭐⭐⭐⭐ | XS |
| — | Reflective Practice | research | ⭐⭐⭐⭐ | XS |
| — | Rolling Native Comparison | own | ⭐⭐⭐ | S |
| — | Why Layer | research | ⭐⭐⭐ | XS |
| F9 | Listening Transcript Study (text-only пока) | own | ⭐⭐⭐ | S |

---

## Sequencing по спринтам (примерный, 3 месяца)

### Sprint 1 (2 недели) — "Two layers and sub-day"
Foundation для всех остальных.
- #4 Two-layer feedback (errors / native-rewrite)
- #5 Pimsleur sub-day SRS
- #7 Russian L1 hit list (30 rules)
- #10 Evaluation Harness (longitudinal baseline + held-out 10%)
- Cold-recall closer, Calibrated confidence, Reflective Practice (XS-tier)

### Sprint 2 (2 недели) — "Lesson formats core"
4 формата уроков, которые меняют ощущение продукта. **F2 идёт первым** (highest leverage против Russian L1 pragmatic gap), F7 — параллельно как daily habit.
- **F2 Diplomatic Rewrite Drill** — landed as named `/practice diplomatic` format with layered/native feedback.
- F7 Notebook (daily free write) — landed with native-diff mining into pending candidate chunks.
- F11 Discourse Builder — landed with deterministic discourse metadata scoring.
- F3 Critical Reading Club — landed for `/practice reading` and pasted text via Article Lab v1 critical-reading tasks.
- F12 Mistake Drill 2.0 — landed with causal prompt and extinction-state metadata.

### Sprint 3 (3 недели) — "Curriculum"
- Импорт пользовательского `data/curriculum/chunks_v1.jsonl` (~3000 chunks) → landed via `scripts/import_chunks.py`, Pydantic validation/dedupe, `LearningItem(type="chunk")`, and alembic migration.
- F8 Vocabulary Lab format — landed over chunk `field/register/function` metadata.
- #11 Genre Curriculum — landed as static 10-genre seed via `scripts/seed_genre_curriculum.py`.
- F4 Writing Workshop — landed as outline → draft → revision staged prompts.

### Sprint 4 (3 недели) — "The Teacher"
- #8 Lesson Director — landed as structured `LessonDirectorDecision` with deterministic fallback and provider route.
- #9 Coach's Journal — landed as markdown output under `data/coach_journal/` via `/mentor`.
- F5 Roleplay — landed over the 40-scenario library with numeric Scene Builder selection.
- #13 Hint Ladder — landed for `confidence=high` mistake patterns.

### Sprint 5 (2 недели) — "Operational utility"
- F14 Pre-Meeting Brief — landed as structured `/brief` card.
- F15 Mentor's Question (weekly) — landed via `/mentor` with Coach Journal output.
- F1 Article Lab — landed as 5-module text-first `/article` v1.
- F6 Debate, F10 Translation Lab, F13 4-3-2 — landed as structured `/debate`, `/translate_lab`, `/fluency432` cards.

### Sprint 6+ — Полировка
- F1 Article Lab full 30-day pipeline — landed as 6-checkpoint text pipeline in Article Lab v1.
- #12 Sprint Mode — landed as `/practice sprint` 14-day consistency contract.
- Rolling Native Comparison — landed in Coach Journal.
- "Why" Layer — enriched with rule pressure, L1 mechanism, and transfer context.
- Voice-mode (TTS) — still deferred; re-evaluate after text-first telemetry.

---

## Метрики прорыва (что мерим)

1. **30-day retention** на held-out items → baseline ≈ 50–65% → таргет **≥ 85%** после #5 + #6
2. **Productive chunks** (#6) — % из 3000 chunks, использованных активно (≥3 раза в free production за 30 дней) → старт ~0%, таргет **≥ 25%** к концу квартала
3. **MTLD / hedging density / sentence complexity** на ежемесячном writing baseline → рост **≥ 15%** за квартал
4. **Mistake pattern extinction rate** (F12) — % low-confidence patterns, дошедших до extinction за 30 дней → таргет **≥ 40%**
5. **L1-trap density** (#7) — частота 30 deterministic ошибок на 100 слов free production → снижение **≥ 50%** за квартал
6. **CEFR Reading & Use of English mock** (#10) → измеренный score growth (Pearson Test-style adaptive probe) — таргет **+10 points** за квартал на 100-балльной шкале
7. **Subjective**: 5-min self-assessment раз в 4 недели — "был ли реальный момент, где FluentLoop помог в рабочей коммуникации?" Целевая частота **≥ 1× в неделю** к 3-му месяцу.

---

## Что НЕ делаем (явные ловушки)

- **Gamification** (XP, leagues, lives) — шум для C1-aiming professional.
- **Voice mode сейчас** — confirm'нули, P2. Text-first → доказываем педагогику → потом voice.
- **Personal Corpus (Gmail/Calendar OAuth)** — не делаем; Pre-Meeting Brief (F14) покрывает 80% эффекта через paste.
- **Public SaaS / open signup** — нет. Это owner/admitted-user бот; repo может
  быть публичным, но продукт не становится self-serve платформой.
- **Web UI / Telegram Mini App** — потом, после педагогической петли.
- **Скейлить exercise types ради количества** — только новые **классы** (discourse / pragmatic / genre / chunks).

---

## Зафиксированные решения

После планирования зафиксированы следующие решения (см. план в `.claude/plans/fluentloop-eager-eich.md`):

1. **Chunks Curriculum (#6)** — пользователь сгенерирует bank сам через Claude Code / Codex по спецификации ниже. Файл `data/curriculum/chunks_v1.jsonl` загружается готовым; ничего LLM-bulk внутри основного приложения не делаем.
2. **40-scenario library (#3)** — берём **Engoo Business / Cambly Topics catalog** как открытый seed, LLM-адаптация под уровень C1+ и под IT/business reality пользователя.
3. **Evaluation probe (#10.3)** — **CAE-style LLM-generated probe** (8 transformations + 10 vocab MCQ + 12 cloze + 1 short writing). Принимаем риск validity, фиксируем seed для воспроизводимости между месяцами.
4. **Sprint 2 first format** — **F2 Diplomatic Rewrite Drill** идёт первым (highest leverage против Russian L1 pragmatic gap). F7 Notebook следует параллельно как daily habit.
5. **Sequencing** — спринты выше следуем как есть: foundation → lesson formats → curriculum → teacher → ops. Lesson Director (#8) сознательно отложен в Sprint 4: даёт плечо, но без foundation (two-layer feedback, sub-day SRS) ему нечем оперировать.

---

## Execution gate

GSD используется только как reference: `discuss → plan → execute → verify → ship → repeat`. В репо не добавляем GSD runtime или `.planning`-артефакты.

Для каждого EPIC-22 slice:

1. Разработка — минимальный вертикальный инкремент без соседних refactor'ов.
2. Документация — PRD + этот epic + index/runbook/help text, если меняется UX.
3. Тесты — focused tests, затем `pytest -q`, `ruff`, `secret_scan`, `git diff --check`.
4. Коммит и деплой — только после явного разрешения owner'а; schema changes требуют SQLite backup и Alembic migration.
5. Post-deploy smoke — upload/approve, `/today`, answer/skip, layered feedback, EPIC-22 command smoke, logs; любой fail начинает новый fix slice.

Sprint 1 implementation v1 включает: layered feedback schema/buttons, deterministic Russian L1 hits, Pimsleur-style sub-day intervals, confidence rating callbacks, reflection logging, monthly evaluation probe, chunk import schema, and scaffolded EPIC-22 practice commands.

## Phase 2 validation gate

EPIC-22 возвращён в `Done` после закрытия review findings:

- in-session GIR re-fire inside a single active practice session;
- negative-path tests for L1 false positives, native-rewrite fallback,
  malformed chunk JSONL, migration roundtrip, and GIR re-fire cap;
- schema verification for `learning_items.metadata_json`, `lesson_plans.format`,
  and Alembic revision;
- deploy runbook smoke for `/scene`, `/brief`, `/mentor`, `/article`,
  `/debate`, `/translate_lab`, `/fluency432`, `/practice sprint`, confidence
  rating, feedback layers, and `/reflect`.

Validation evidence:

- Local gate: `pytest -q` → 113 passed; `ruff check src tests scripts` clean;
  `secret_scan` ok; `git diff --check` clean.
- Migration verification: copied SQLite roundtrip test covers
  upgrade → inspect columns/index → downgrade → upgrade.
- VPS deployment: batched runtime deploy completed with backup/migration,
  container `healthy`, bot connected, scheduler started, and Telegram outbound
  smoke delivered.

---

## Спецификация: формат для self-генерации Chunks Curriculum

> Это техзадание для отдельной сессии Claude Code / Codex, которую запустит пользователь. Цель — сгенерировать ~3000 lexical chunks в едином JSONL-формате, готовых к импорту в FluentLoop.

### Файл: `data/curriculum/chunks_v1.jsonl`

Один chunk = одна JSON-строка. Поля:

```json
{
  "id": "chunk_0001",
  "text": "the underlying assumption is that",
  "type": "collocation",
  "field": "UNCERTAINTY",
  "register": "professional",
  "function": "hedging",
  "genres": ["rfc", "architecture_proposal", "post_mortem"],
  "cefr_target": "C1",
  "russian_gloss": "лежащее в основе предположение",
  "l1_trap": null,
  "example_sentences": [
    "The underlying assumption is that traffic will grow linearly.",
    "Their underlying assumption is that the API will remain stable for two years."
  ],
  "anti_examples": [
    "underlying assumption is that ..."
  ],
  "etymology_or_why": "underlying = 'lying beneath' — metaphor for foundational beliefs in argument."
}
```

### Допустимые значения полей

- **`type`** (8 классов): `collocation` | `fixed_expression` | `semi_fixed_expression` | `discourse_marker` | `phrasal_verb` | `idiom` | `signposting` | `hedge`
- **`field`** (9 концептуальных полей frame semantics): `UNCERTAINTY` | `DISAGREEMENT` | `DECISION` | `INFLUENCE` | `CRITIQUE` | `SUPPORT` | `TIME` | `RESPONSIBILITY` | `NEGOTIATION`
- **`register`** (5 регистров): `very_formal` | `professional` | `collegial` | `casual` | `blunt_direct`
- **`function`** (3 коммуникативные функции): `hedging` | `signposting` | `softening`
- **`genres`** (массив, 0–N из списка): `rfc` | `post_mortem` | `architecture_proposal` | `standup_update` | `perf_review_give` | `perf_review_receive` | `customer_escalation` | `cold_outreach` | `tech_blog` | `talk_qa`
- **`cefr_target`**: `B2` | `B2+` | `C1` | `C1+`
- **`l1_trap`** (опционально): null или строка с типичным русским неправильным эквивалентом (например `"make a research"` для chunk `"do a research"`)

### Распределение

- **3000 chunks total** (~330 на field × 9 полей)
- Внутри field: **примерно равномерно по 5 регистрам** (~66 chunks × 5 = 330)
- Покрытие функций: ≥30% всех chunks помечены `hedging` (C1+ priority), остальные распределяются между signposting и softening
- **L1-trap density**: 200–300 chunks должны иметь непустой `l1_trap` (10%)
- **Genre coverage**: каждый из 10 жанров получает ≥150 chunks через теги в `genres`

### Качество

- **example_sentences** — реальный business/IT контекст, не "John buys an apple"
- **anti_examples** — типичные ошибки L2 (article drop, неправильная collocation)
- **etymology_or_why** ≤ 200 символов, опционально; только когда есть реальная метафора/история, не просто перефразирование

### Промпт-шаблон для генератора

```
You are generating a lexical chunks dataset for a C1+ English learner
(Russian L1, IT/business professional). Generate {N} chunks for field
"{FIELD}" in register "{REGISTER}". Each chunk must be in JSON format
matching this schema: {SCHEMA_ABOVE}. Constraints:
- chunks must be authentic business/IT collocations (verifiable in COCA
  or BNC corpus mental model)
- example_sentences must be from realistic engineering/business contexts
- l1_trap field is filled when there is a known Russian-transfer mistake
- output one JSON per line, no markdown, no commentary
```

### Импорт в FluentLoop

После генерации файла — отдельный sprint-task в Sprint 3 (Curriculum):
1. `scripts/import_chunks.py` парсит JSONL, валидирует через pydantic schema
2. Создаёт `LearningItem` records с `kind="chunk"` и метаданными в JSON-поле
3. Опционально дедуплицирует по `text` + `field`
4. Alembic migration добавляет JSON metadata column в `learning_items`

Это не блокирует Sprint 1.

---

## Источники / референсы

**Продукты (исследовано через open web):**
- Duolingo Max — Adventures, Explain My Answer
- Speak (speak.com, OpenAI Startup Fund) — Live Roleplays, Proficiency Graph
- Praktika.ai — multi-agent lesson architecture (OpenAI case study)
- Loora.ai — culturally-awkward flagging, two-layer feedback
- Quazel / Univerbal — Scene Builder
- Khanmigo (Khan Academy) — Socratic refusal, Writing Coach
- Falou — cold-recall closer
- TalkPal — debate mode
- Pimsleur — Graduated Interval Recall (1967)
- Glossika — reverse-translation, per-sentence FSRS
- LingQ (Steve Kaufmann) — auto-promote known words
- Migaku / Refold (MIA) — 1T rule, sentence cards
- Clozemaster — typed cloze 5–7 retrievals threshold
- Memrise — Learn with Locals native clips
- BreakingNewsEnglish — 40-module pipeline from arbitrary article
- ESL Brains — 5 lesson formats (Standard / Speaking / Critical Reading / Flipped / Vocab Lab)
- Cambridge CAE Writing Part 2 — essay/proposal/report/review/letter taxonomy
- Business English Pod — dialogue → commentary → practice format
- italki — Notebook free-write + annotated diff
- Lingoda Sprint — 30-in-60 cashback commitment device
- Market Leader Advanced (Pearson) — 8-section business unit template
- Engoo / Cambly — 25-min 1:1 lesson catalogue
- Coursera Business English (ASU) — module = one functional output deliverable
- Linguahouse — Diplomatic Language lesson plan as template

**SLA / Applied Linguistics:**
- Lewis (1993, 1997) — Lexical Approach
- Willis (1996), Ellis (2003), Long (2015) — Task-Based Language Teaching
- Howatt (1984), Canale & Swain (1980) — Communicative Language Teaching weak/strong
- Marsh, Coyle — CLIL (Content and Language Integrated Learning)
- Thornbury & Meddings — Dogme ELT (Teaching Unplugged)
- Halliday, Martin, Rothery — Genre-based Pedagogy (Sydney School)
- Vygotsky, Lantolf — Sociocultural Theory, Dynamic Assessment, ZPD
- DeKeyser (1998, 2007, 2025) — Skill Acquisition Theory
- Schmidt (1990, 2010) — Noticing Hypothesis
- Swain (1985, 1995, 2005) — Output Hypothesis, languaging
- Krashen (1985) — Input Hypothesis (+ critiques: Gregg 1984)
- Long (1991, 1998) — Focus on Form
- Brown & Levinson (1987), Grice (1975), Kasper & Rose (2002) — Politeness, Implicature, Pragmatics
- Pawley & Syder (1983), Wray (2002), Nick Ellis (2008, 2012) — formulaic sequences, nativelike selection
- Erman & Warren (2000) — ~50% formulaic ratio in native speech
- Norris & Ortega (2000) — meta-analysis of L2 instruction
- Lyster (2004) — recasts vs prompts
- RILEC (arXiv) — Russian L1 interference in English learner texts
- Russian L1 error inventories: study.ru, italki, TALK Schools, Heather Hughes corpus

**Algorithms / SRS:**
- FSRS-5 (Anki default, RemNote, py-fsrs MIT)
- Pimsleur Graduated Interval Recall (1967 original paper, intervals 5s…2yr)
- Settles & Meeder (Duolingo, 2016) — half-life regression trainable SRS
- Bayesian Knowledge Tracing (pyBKT) — probabilistic mastery modeling
- Item Response Theory (IRT) — for adaptive testing
