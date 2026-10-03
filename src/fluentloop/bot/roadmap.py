"""Personal Study selection controls, separate from assessed adaptive progress."""

from __future__ import annotations

from html import escape

from sqlalchemy.orm import Session

from fluentloop.adaptive_learning import TOPIC_TITLES
from fluentloop.bot.handlers import BotReply, InlineButton
from fluentloop.curriculum_b2 import CURRICULUM_LESSONS
from fluentloop.db.models import User
from fluentloop.roadmap_export import DELIVERY as DELIVERY_LABELS
from fluentloop.workplace_roadmap import (
    get_plan,
    load_curriculum,
    plan_outline,
    update_plan,
)

STAGE_LABELS = {"b2": "B2", "b2_plus": "B2+", "c1_intro": "C1 intro"}
USAGE = (
    "/roadmap — общий план\n"
    "/roadmap activate — подключить план к «Учиться»\n"
    "/roadmap track balanced|client_facing|big_tech\n"
    "/roadmap time 150 — минут в неделю (30–1200)\n"
    "/roadmap general 60 — доля общего английского (20–90%)\n"
    "/roadmap list [general|work]\n"
    "/roadmap module ID [b2|b2_plus|c1_intro]\n"
    "/roadmap focus ID · /roadmap pause ID · /roadmap resume ID"
)


def _buttons(*rows: list[tuple[str, str]]) -> list[list[InlineButton]]:
    buttons = [
        [InlineButton(label, data) for label, data in row if len(data.encode()) <= 64]
        for row in rows
    ]
    return [row for row in buttons if row]


def _reply(
    text: str,
    channel_id: str | None,
    message_thread_id: int | None,
    buttons: list[list[InlineButton]] | None = None,
) -> BotReply:
    # Escape every public field, including URLs. Split before HTML entities can
    # be cut, keeping every continuation in the request's original destination.
    pages: list[str] = []
    page = ""
    page_size = 0
    for line in text.splitlines(keepends=True):
        encoded = escape(line)
        encoded_size = len(encoded.encode("utf-16-le")) // 2
        if page_size + encoded_size <= 3800:
            page += encoded
            page_size += encoded_size
            continue
        if page:
            pages.append(page.rstrip())
            page = ""
            page_size = 0
        for character in line:
            encoded_character = escape(character)
            character_size = len(encoded_character.encode("utf-16-le")) // 2
            if page_size + character_size > 3800:
                pages.append(page.rstrip())
                page = ""
                page_size = 0
            page += encoded_character
            page_size += character_size
    if page or not pages:
        pages.append(page.rstrip())
    extras = tuple(
        BotReply(
            part,
            channel_id,
            message_thread_id=message_thread_id,
            parse_mode="html",
        )
        for part in pages[1:]
    )
    return BotReply(
        pages[0],
        channel_id,
        buttons=buttons,
        message_thread_id=message_thread_id,
        extra_replies=extras,
        parse_mode="html",
    )


def handle_roadmap(
    session: Session,
    user: User,
    argument: str = "",
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
    catalog: dict | None = None,
) -> BotReply:
    """Inspect or edit only this user's Study plan, never start practice."""

    from fluentloop.roadmap_study import enabled, module_progress

    try:
        pack = load_curriculum() if catalog is None else catalog
        plan = get_plan(user, pack)
        parts = argument.split()
        action = parts[0] if parts else ""
        if action == "activate":
            if len(parts) != 1:
                raise ValueError("unexpected value")
            plan = update_plan(session, user, "time", plan["weekly_minutes"], pack)
        elif action in {"track", "time", "general", "focus", "pause", "resume"}:
            if len(parts) != 2:
                raise ValueError("missing value")
            value = int(parts[1]) if action in {"time", "general"} else parts[1]
            plan = update_plan(
                session,
                user,
                "general_share" if action == "general" else action,
                value,
                pack,
            )
        elif action == "module":
            if len(parts) not in {2, 3}:
                raise ValueError("module id and optional stage required")
            stage = parts[2] if len(parts) == 3 else "b2"
            if stage not in STAGE_LABELS:
                raise ValueError("unknown stage")
            module = next(
                (row for row in pack["modules"] if row["id"] == parts[1]), None
            )
            if module is None:
                raise ValueError("unknown module")
            module_id = module["id"]
            sources = {source["id"]: source for source in pack["sources"]}
            skills = ", ".join(pack["skills"][skill] for skill in module["skills"])
            lines = [
                f"{module['title_ru']} · {STAGE_LABELS[stage]}",
                "Общий английский"
                if module["strand"] == "general"
                else "Дополнение для работы",
                f"Навыки: {skills}",
                f"Язык: {', '.join(module['language_focus'])}",
                "",
                f"Результат: {module['outcomes'][stage]}",
                f"Задание: {module['tasks'][stage]}",
                "Свидетельства результата:",
                *(f"• {criterion}" for criterion in module["evidence"]),
                "",
                f"Практика: {DELIVERY_LABELS[module['delivery']]}",
            ]
            if module["adaptive_topics"]:
                lines.append(
                    "Связанные темы /plan: "
                    + ", ".join(TOPIC_TITLES[key] for key in module["adaptive_topics"])
                )
            if module["library_slugs"]:
                titles = {lesson.slug: lesson.title for lesson in CURRICULUM_LESSONS}
                lines.append(
                    "Искать в /library: "
                    + ", ".join(titles[key] for key in module["library_slugs"])
                )
            lines.extend(
                [
                    "Ресурсы:",
                    *(
                        f"• {sources[source_id]['title']}: {sources[source_id]['url']}"
                        for source_id in module["source_ids"]
                    ),
                ]
            )
            lines.append(
                "Бриф C1 можно изучать; задания C1 открываются после B2+ модуля "
                "и устойчивого B2+ по всем десяти языковым темам /plan."
            )
            if enabled(user):
                progress = next(
                    row
                    for row in module_progress(session, user)
                    if row["module_id"] == module_id
                )
                lines.extend(
                    [
                        "",
                        f"Текущая ступень: {STAGE_LABELS[progress['stage']]}. "
                        f"Узнавание: {progress['recognition_correct']}; "
                        "самостоятельное письмо: "
                        f"{len(progress['writing_variants'])}/2.",
                        f"Внешних отметок: {progress['external_reports']} "
                        "(со слов пользователя).",
                        "Рост ступени: верный вопрос + два самостоятельных письменных "
                        "задания в разных ситуациях на разных днях с интервалом ≥24 ч.",
                    ]
                )
            paused = module_id in plan["paused"]
            buttons = _buttons(
                [
                    (label, f"simple:roadmap:module:{module_id}:{stage_id}")
                    for stage_id, label in STAGE_LABELS.items()
                ],
                [
                    ("В фокус", f"simple:roadmap:focus:{module_id}"),
                    (
                        "Возобновить" if paused else "На паузу",
                        f"simple:roadmap:{'resume' if paused else 'pause'}:{module_id}",
                    ),
                ],
                [("Общий план", "simple:roadmap")],
            )
            return _reply("\n".join(lines), channel_id, message_thread_id, buttons)
        elif action == "list":
            if len(parts) > 2 or (
                len(parts) == 2 and parts[1] not in {"general", "work"}
            ):
                raise ValueError("unknown strand")
            strand = parts[1] if len(parts) == 2 else None
            modules = {module["id"]: module for module in pack["modules"]}
            lines = [
                "Модули общего английского и дополнений",
                "Порядок — учебный план, не оценка освоения.",
                "",
            ]
            for module_id in plan["order"]:
                module = modules[module_id]
                if strand and module["strand"] != strand:
                    continue
                status = " · пауза" if module_id in plan["paused"] else ""
                label = "общий" if module["strand"] == "general" else "работа"
                lines.extend(
                    [
                        f"{module['title_ru']} ({label}){status}",
                        f"/roadmap module {module_id}",
                    ]
                )
            return _reply("\n".join(lines), channel_id, message_thread_id)
        elif parts:
            raise ValueError("unknown action")
        outline = plan_outline(plan, pack)
    except ValueError:
        return _reply(
            "Не удалось прочитать или изменить план. Проверь команду и настройки.\n\n"
            + USAGE,
            channel_id,
            message_thread_id,
        )

    general = outline["general_focus"]
    work = outline["work_focus"]
    text = "\n".join(
        [
            "🗺 Общий план · B2 → B2+ → C1 intro",
            f"Направление: {pack['tracks'][plan['track']]['title_ru']}",
            f"В неделю: {plan['weekly_minutes']} мин. "
            f"Общий английский: {plan['general_share']}%.",
            f"Основа: {outline['general_minutes']} мин — {general['title_ru']}",
            f"Дополнения: {outline['work_minutes']} мин — {work['title_ru']}",
            "",
            "Общий английский остаётся основой; работа с клиентами и IT дополняют его.",
            "Чтение, письмо, аудирование, разговор и медиация входят в план.",
            "Аудирование и живой разговор требуют внешней практики.",
            (
                "План подключён к «Учиться»: доля общего английского, порядок, "
                "фокус и паузы влияют на следующий вопрос. "
                "Уже открытый вопрос сохраняется."
                if enabled(user)
                else "Нажмите «Подключить план» или измените настройку, "
                "чтобы «Учиться» "
                "подбирало вопросы по этому плану."
            ),
            "Проценты распределяют вопросы; минуты — ориентир нагрузки, "
            "не измеренное время.",
            "Это план занятий, а не оценка уровня CEFR. "
            "/plan показывает текущие свидетельства; его правила C1 сохранены.",
            "",
            f"Основа: /roadmap module {general['id']}",
            f"Дополнение: /roadmap module {work['id']}",
            f"На паузе: {len(plan['paused'])} модулей.",
            "Порядок и личные заметки можно изменить в офлайн-планировщике.",
            "",
            USAGE,
        ]
    )
    buttons = _buttons(
        [
            ("Баланс", "simple:roadmap:track:balanced"),
            ("Клиенты", "simple:roadmap:track:client_facing"),
            ("Big Tech", "simple:roadmap:track:big_tech"),
        ],
        [
            ("90 мин/нед", "simple:roadmap:time:90"),
            ("150 мин/нед", "simple:roadmap:time:150"),
            ("300 мин/нед", "simple:roadmap:time:300"),
        ],
        [
            ("Основа", f"simple:roadmap:module:{general['id']}"),
            ("Дополнение", f"simple:roadmap:module:{work['id']}"),
        ],
        [
            ("Общие модули", "simple:roadmap:list:general"),
            ("Рабочие модули", "simple:roadmap:list:work"),
        ],
        [("Текущий прогресс", "simple:plan")],
        [("Учиться", "simple:study")]
        if enabled(user)
        else [("Подключить план", "simple:roadmap:activate")],
    )
    return _reply(text, channel_id, message_thread_id, buttons)


def handle_roadmap_callback(
    session: Session,
    user: User,
    data: str,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    prefix = "simple:roadmap"
    argument = ""
    if data.startswith(prefix + ":"):
        parts = data[len(prefix) + 1 :].split(":")
        argument = " ".join(parts)
        if any(not part or any(char.isspace() for char in part) for part in parts):
            argument = "invalid"
    elif data != prefix:
        argument = "invalid"
    return handle_roadmap(
        session,
        user,
        argument,
        channel_id=channel_id,
        message_thread_id=message_thread_id,
    )
