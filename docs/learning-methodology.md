# FluentLoop Learning Methodology / Методология обучения FluentLoop

FluentLoop - это не каталог упражнений ради количества. Это учебная петля для
B2+/C1- business/IT English: взять реальный или curated материал, превратить
его в понятный тип урока, потренировать active recall, вернуть слабые места и
показать evidence прогресса.

![FluentLoop Learning Method](assets/fluentloop-learning-method.png)

## Простая практика

Пилот скрывает выбор lesson type и practice mode из ежедневного запуска:
`/study` → один вопрос → ответ кнопкой → короткое объяснение → следующий вопрос.
**Хватит** завершает занятие; короткое письмо (обычно 1–2 предложения) доступно после итога
по желанию. Автоматических учебных сообщений у простого профиля нет.

Лента смешивает одобренные фразы и грамматику, включая проверенный набор
lang-lessons. Правильное узнавание имеет суточную паузу перед следующим
обычным повтором; ошибка возвращается после пяти других ответов. Исчерпание
подходящего банка предлагает досрочное повторение явно.

Узнавание и самостоятельное использование — разные свидетельства:
`/progress` показывает их отдельно; кнопочные ответы не учитываются в
productive chunks, writing, productive held-out retention или extinction.
Для активного использования доступны необязательное письмо и полные уроки.
Если проверка письма недоступна, ответ сохраняется без оценки и не даёт
свидетельства освоения темы.

По каждой теме `/progress` показывает этап B2, B2+ или вводный C1 и отдельные
счётчики практики, переноса в новом контексте и самостоятельного письма.
`/plan` выбирает следующий шаг по сохранённым ответам и указывает пробелы.
Успех в знакомом вопросе сам по себе не означает перехода: нужен отложенный
повтор и свежий контекст, а на B2+/C1 — собственное предложение. Ошибки могут
вернуть тему к отработке. Вводный C1 открывается после устойчивого B2+ по всем
темам. Эти этапы направляют практику и не удостоверяют уровень CEFR.

Банк может пополняться новыми вариантами только в пределах уже одобренных
тем, с ограничениями на объём для профиля и исходного вопроса. Варианты
проходят независимую проверку и проверку структуры до включения; непрошедшие
остаются вне практики. Кнопка **Ошибка в вопросе** после ответа исключает
личный вопрос из подбора до проверки, сохраняя исходный материал и историю
ответов. Вариант из прежнего проверенного набора может быть заменён после
проверки без изменения исходного уровня или зачёта как доказательства B2.
Произвольные личные карточки автоматически не заменяются.

## Полный режим: короткая версия

Общая программа шире адаптивного банка: чтение, аудирование, письмо, речь,
взаимодействие и медиация в личных, общественных и рабочих ситуациях.
`/roadmap` и [редактор](curriculum/workplace-plan-guide.md) задают приоритеты
практики; `/progress` отражает только собранные свидетельства. Общая база
получает 60% исходного времени, бизнес и IT — дополнительные 40%.
Изменения плана не присваивают уровень и не перенастраивают очередь вопросов.
Методические основания и ограничения: [исследование](research/b2-c1-framework.md).

```text
input -> lesson type -> practice mode -> exercise type -> feedback ->
SRS/mistakes -> outcomes -> next focus
```

На практике это значит:

1. **Input.** Ты приносишь материал через `/upload` или берешь shared lesson
   через `/library` -> `/subscribe`.
2. **Lesson type.** Система понимает, что тренируется: vocabulary, chunks,
   grammar, mistakes, diplomatic tone, notebook, reading, writing, genre,
   scenario, review, mixed lesson или outcomes.
3. **Practice mode.** Ты тренируешься через `/today` или focused commands:
   `/practice notebook`, `/practice diplomatic`, `/practice vocab`,
   `/practice mistakes`, `/article`, `/scene`, `/translate_lab`.
4. **Exercise type.** Урок превращается в recall, cloze, rewrite, chunk builder,
   mini writing, register choice, active recall и другие конкретные задания.
5. **Feedback.** Ответ проверяется слоями: `Errors`, `Native`, `Why`.
6. **Memory and mistakes.** SRS, confidence, Russian L1 traps и mistake patterns
   решают, что должно вернуться.
7. **Outcomes.** `/baseline` и `/outcomes` показывают не активность, а учебные
   признаки: retention, productive chunks, L1 density, writing metrics,
   mistake extinction, reading probes.

## Что отличается от обычного бота с упражнениями

Обычный drill-бот часто делает одно: дает вопрос и проверяет правильность.
FluentLoop держит несколько учебных механизмов одновременно.

| Механизм | Зачем нужен | Команды |
|---|---|---|
| Approved input | Не тренировать мусор: новые targets попадают в практику только после approve | `/upload`, `/approve` |
| Daily retrieval | Доставать язык из памяти, а не перечитывать список | `/today`, `/review` |
| Layered feedback | Разделить ошибки, natural rewrite и объяснение причины | feedback buttons after answer |
| Sub-day SRS | Быстро вернуть слабое место, пока оно еще в рабочей памяти | `/today`, `/review` |
| Mistake/L1 loop | Превратить повторяющиеся русские transfer errors в targets | `/practice mistakes`, `/translate_lab` |
| Reflection | Понять, где английский реально мешал в работе | `/reflect`, `/mentor` |
| Outcomes | Еженедельно выбирать самый слабый учебный цикл | `/baseline`, `/outcomes full` |

## Lesson Types

Lesson Type - это единый learner-facing слой. Он отвечает на вопрос:
**что именно тренирует этот урок и куда идти дальше**.

Полная актуальная таблица генерируется из code registry:
[`lesson-catalog/lesson-types.md`](lesson-catalog/lesson-types.md).

Главные типы v1:

| Type | Что тренирует | Основные команды |
|---|---|---|
| Vocabulary | слова и термины, которые нужно recall | `/practice vocab`, `/review` |
| Chunks | collocations и reusable workplace phrases | `/practice vocab`, `/practice notebook` |
| Grammar | формы, tense, articles, prepositions, sentence shape | `/practice grammar`, `/practice mistakes` |
| Mistake Repair | повторяющиеся ошибки и L1 traps | `/practice mistakes`, `/translate_lab` |
| Diplomatic | pushback, disagreement, feedback, hedging, tone | `/practice diplomatic`, `/scene`, `/translate_lab` |
| Notebook | free writing для native diff, chunk mining, L1 checks | `/practice notebook`, `/reflect` |
| Reading | claim, assumption, hedge marker, executive summary | `/article`, `/practice reading` |
| Writing | workplace artifacts: email, report, update, review, resume | `/practice writing`, `/baseline` |
| Genre | структура рабочих документов | `/practice genre`, `/practice writing_workshop` |
| Scenario | roleplay и pre-meeting rehearsal | `/scene`, `/brief` |
| Review | SRS, retention, cold recall | `/today`, `/review` |
| Mixed | широкие уроки из seed/textbook/upload materials | `/lesson <id>`, `/today` |
| Outcomes | измерение прогресса и выбор следующего фокуса | `/baseline`, `/outcomes`, `/mentor` |

## Material Types vs Lessons vs Scenarios

![What FluentLoop Can Train](assets/fluentloop-training-scope.png)

Эти сущности похожи, но у них разная роль:

1. **Material types для `/upload`.** Это то, что ты приносишь сам: teacher
   notes, phrase list, Slack/email draft, article/blog post, meeting notes,
   homework. Они приватные и становятся practice targets только после approve.
2. **Shared lesson plans для `/library`.** Это public templates. После
   `/subscribe <template_id>` урок копируется в твою личную базу, а прогресс
   остается приватным.
3. **Scenario cards для `/scene`.** Это 40 code-defined business/IT roleplay
   ситуаций: design review, code review, incident postmortem, scope negotiation,
   customer escalation, deadline refusal и т.д.
4. **Focused modes для `/practice`.** Это режимы тренировки поверх твоей базы:
   notebook, diplomatic, vocab, mistakes, reading, genre, writing workshop.
5. **Outcome reports.** `/baseline` задает стартовую точку, `/outcomes` говорит,
   какой учебный loop слабее всего сейчас.

## Как выбрать режим

| Симптом | Что делать |
|---|---|
| Не знаешь, с чего начать | В пилоте `/study`; для полного пути `/library` -> `/subscribe`, потом `/baseline` и урок |
| Есть заметки с урока | `/upload` -> `/approve` -> `/today` |
| Много пассивных фраз, но мало active use | `/practice notebook`, `/practice vocab` |
| Звучишь слишком прямо или по-русски | `/practice diplomatic`, `/translate_lab` |
| Повторяются одни ошибки | `/practice mistakes`, `/review` |
| Нужно подготовиться к встрече | `/brief <agenda>`, `/scene <topic>` |
| Нужно читать и суммировать статьи | `/article <text>`, `/practice reading` |
| Хочешь понять прогресс | `/outcomes full` |

## Public catalog

Текущий публичный каталог генерируется автоматически и лежит здесь:

- [All public learning surfaces](lesson-catalog/index.md)
- [Lesson types](lesson-catalog/lesson-types.md)
- [B2/B2+ seed lessons](lesson-catalog/b2-b2plus-seed.md)
- [English for Tech](lesson-catalog/english-for-tech.md)
- [Business/IT scenarios](lesson-catalog/scenarios.md)

Source of truth: SQLite/code. Markdown/HTML файлы в `docs/lesson-catalog/` -
это export view. Их не нужно редактировать руками.

## Compact EN

FluentLoop uses a measurable learning loop, not random drills:

```text
approved input -> lesson type -> practice mode -> exercise -> feedback ->
SRS/mistakes -> outcomes -> next focus
```

Bring material with `/upload` or clone a shared lesson via `/library` and
`/subscribe`. Train with `/today` and focused practice modes. Check layered
feedback (`Errors`, `Native`, `Why`). Let SRS and mistake patterns return weak
items. Use `/baseline` and `/outcomes full` weekly to choose the next focus.
