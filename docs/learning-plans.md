# FluentLoop Learning Plans / Учебные планы

Этот документ отвечает на практический вопрос: что делать каждый день, чтобы
FluentLoop реально помогал в рабочем английском.

Методология целиком описана в [learning-methodology.md](learning-methodology.md).
Текущие lesson types и публичные уроки лежат в
[lesson-catalog/index.md](lesson-catalog/index.md).

Основная логика:

```text
start simple -> produce English -> get feedback -> repeat weak points ->
measure outcomes -> choose next focus
```

![FluentLoop 30-Day Starter Plan](assets/fluentloop-30-day-plan.png)

## 1. 15-Minute Daily Plan

Для занятых дней. Цель - не потерять loop.

1. `/today`.
2. Ответь сам, не смотри сразу model answer.
3. Если уверен/не уверен - нажми confidence `1-5`.
4. Посмотри compact feedback.
5. Открой `Errors`, `Native` или `Why` только если ответ важный.
6. В конце: `/reflect <one hard thing today>`.

Результат: SRS и mistake loop получают свежие данные, даже если у тебя всего
15 минут.

## 2. 30-Minute Serious Plan

Для дней, когда хочешь заметный прогресс.

1. `/today`.
2. Один focused mode:
   - `/practice notebook` - free writing and chunks;
   - `/practice diplomatic` - softer workplace tone;
   - `/translate_lab <topic>` - RU->EN transfer repair;
   - `/article <text>` или `/practice reading` - critical reading.
3. `/reflect <what I could not express + next action>`.
4. Раз в неделю: `/outcomes full`.

Результат: система видит не только recognition, но и production.

## 3. First Week / Первая неделя

В первый день можно стартовать тремя способами:

- `/upload` - если есть свои материалы;
- `/library` + `/subscribe` - если хочешь готовый seed lesson;
- `/scene <topic or number>` - если нужен быстрый business scenario для
  rehearsal перед разговором.

### Day 1 - создать материал

Если материалов нет:

```text
/library
/subscribe <template_id>
```

Если материал есть:

```text
/upload
/approve <material_id>
```

Цель дня: создать личную базу уроков.

### Day 2 - baseline

```text
/baseline
/baseline <your 120-180 word answer>
```

Цель дня: зафиксировать стартовую точку и held-out set.

### Day 3 - daily practice

```text
/today
```

Цель дня: начать retrieval. Не полируй ответ слишком сильно: системе нужен
реальный английский.

### Day 4 - free production

```text
/practice notebook
```

Цель дня: дать системе writing sample, native diff, mined chunks и L1 hits.

### Day 5 - tone or L1

Выбери одно:

```text
/practice diplomatic
/translate_lab planning
```

Цель дня: сделать английский менее буквальным и менее резким.

### Weekend - выбрать следующий фокус

```text
/outcomes full
/review
/mistakes
/stats
```

Цель weekend: понять, что тренировать на второй неделе.

## 4. 30-Day Outcome Plan

### Week 1 - Start + Measure

Команды:

```text
/library or /upload
/subscribe or /approve
/baseline
/today
```

Цель: создать стартовую точку и собрать первые attempts.

Good sign: `/outcomes` уже открывается, даже если пишет `insufficient data`.

### Week 2 - Write + Reuse Chunks

Команды:

```text
/today
/practice notebook
/practice vocab
```

Цель: выбрать 3-5 chunks и сознательно использовать их в ответах.

Good sign: `/outcomes full` начинает показывать top productive chunks.

### Week 3 - Diplomatic + L1 Repair

Команды:

```text
/practice diplomatic
/translate_lab <work topic>
/today
```

Цель: снижать literal Russian transfer и делать tone профессиональнее.

Good sign: меньше повторных L1 hits на 100 words.

### Week 4 - Review + Prove Progress

Команды:

```text
/review
/practice mistakes
/article <short text>
/outcomes full
```

Цель: увидеть, что стало лучше, и выбрать следующий loop.

Good sign: хотя бы один pattern становится nearly extinct, или отчет честно
показывает, каких данных не хватает.

## 5. 12-Week Outcome Plan

### Month 1 - Measurement loop

Фокус: собрать честные данные.

- `/baseline` один раз.
- `/today` 4-5 раз в неделю.
- `/practice notebook` каждую неделю.
- Один operational drill перед реальной встречей или текстом.

Смотреть в `/outcomes`: word count, sample size, L1 hits, productive chunks,
insufficient-data notes.

### Month 2 - Active production

Фокус: перевести passive vocabulary в active English.

- Делать `/today`.
- Переиспользовать chunks в Notebook.
- Каждую неделю делать Diplomatic/L1 repair.
- Добавить `/article` или `/practice reading`.

Смотреть в `/outcomes`: chunks used >=3 times, hedging density, L1 density,
reading events.

### Month 3 - Extinction and transfer

Фокус: доказать, что старые ошибки уходят, а язык помогает в работе.

- `/practice mistakes` и `/review`.
- `/reflect` после реальных рабочих ситуаций.
- `/mentor` после `/outcomes`, чтобы Coach Journal видел latest summary.

Смотреть в `/outcomes`: held-out retention, mistake extinction rate, L1 density
trend, real-work usefulness.

## 6. Если `/outcomes` пишет insufficient data

Это не ошибка. Это значит, что FluentLoop не рисует fake progress.

Что делать:

- Нет baseline -> `/baseline`.
- Мало attempts -> `/today` 4-5 раз за неделю.
- Мало production words -> `/practice notebook`.
- Нет chunk usage -> выбери 3 chunks и используй их в ответах.
- Нет reading events -> `/article <text>` или `/practice reading`.
- Нет mistake extinction data -> `/practice mistakes` и `/review`.

## 7. Как выбрать следующий режим

| Что показывает `/outcomes` | Следующий режим |
|---|---|
| L1 hits high | `/practice diplomatic`, `/translate_lab` |
| Chunks low | `/practice notebook`, `/practice vocab` |
| Retention low | `/review`, `/today` |
| Reading missing | `/article`, `/practice reading` |
| Mistakes persist | `/practice mistakes` |
| Мало real production | `/practice notebook` |
| Нужно перед встречей | `/brief`, `/scene` |

## Compact EN Version

1. Start with `/library` + `/subscribe` or `/upload` + `/approve`.
2. Record `/baseline`.
3. Train with `/today`.
4. Use `/practice notebook` for free production.
5. Use `/practice diplomatic` and `/translate_lab` for tone/L1 repair.
6. Use `/article` or `/practice reading` for reading and summaries.
7. Run `/outcomes full` weekly and train the weakest loop next.
