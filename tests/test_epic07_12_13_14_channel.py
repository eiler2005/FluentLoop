from __future__ import annotations

import asyncio

from fluentloop.bot.formatting import HTML_PARSE_MODE
from fluentloop.bot.handlers import (
    BotReply,
    InlineButton,
    handle_favorites,
    handle_rules,
)
from fluentloop.channel import (
    find_channel_from_updates,
    read_recorded_channel,
    record_channel_discovery,
)
from fluentloop.grammar import link_parent, parents_of, seed_concepts, unlink_parent
from fluentloop.learning import create_learning_item, set_item_status, toggle_favorite
from fluentloop.mistakes import archive_pattern, ingest_mistake_event
from fluentloop.practice import cache_session
from fluentloop.stats import collect_stats, render_stats, weekly_summary
from fluentloop.telegram_bot_api import inline_keyboard, send_bot_api_reply
from fluentloop.users import ensure_user


def test_generation_cache_stats_favorites_and_rules(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="expression", text="align on")
    toggle_favorite(db_session, item)
    cached = cache_session(
        db_session, user, target_date=__import__("datetime").date.today()
    )
    assert 15 <= len(cached.exercises) <= 20
    rendered = render_stats(collect_stats(db_session, user))
    assert "Favorites: 1" in rendered
    assert "Recommended focus next week" in weekly_summary(db_session, user)
    seed_concepts(db_session)
    from sqlalchemy import select

    from fluentloop.db.models import GrammarConcept

    hedging = db_session.scalar(
        select(GrammarConcept).where(GrammarConcept.title == "Hedging recommendations")
    )
    assert hedging is not None
    assert parents_of(db_session, hedging.id, depth=2)


def test_mistake_pattern_archive_blocks_recreation(db_session, settings) -> None:
    from sqlalchemy import func, select

    from fluentloop.db.models import MistakeEvent, MistakePattern

    user = ensure_user(db_session, 123456789, settings)
    pattern = None
    for index in range(3):
        event = MistakeEvent(
            user_id=user.id,
            wrong_answer=f"wrong {index}",
            corrected_answer="right",
            explanation="because",
            mistake_type="articles",
        )
        db_session.add(event)
        db_session.flush()
        pattern = ingest_mistake_event(db_session, event)
    assert pattern is not None
    archive_pattern(db_session, pattern)
    event = MistakeEvent(
        user_id=user.id,
        wrong_answer="wrong 4",
        corrected_answer="right",
        explanation="because",
        mistake_type="articles",
    )
    db_session.add(event)
    db_session.flush()
    ingest_mistake_event(db_session, event)
    assert db_session.scalar(select(func.count()).select_from(MistakePattern)) == 1
    assert pattern.status == "archived"


def test_grammar_unlink_rules_counts_and_favorites_limit(db_session, settings) -> None:
    from sqlalchemy import select

    from fluentloop.db.models import GrammarConcept, MistakePattern

    user = ensure_user(db_session, 123456789, settings)
    seed_concepts(db_session)
    hedging = db_session.scalar(
        select(GrammarConcept).where(GrammarConcept.title == "Hedging recommendations")
    )
    modal = db_session.scalar(
        select(GrammarConcept).where(
            GrammarConcept.title == "Modal verbs for recommendations"
        )
    )
    assert hedging is not None
    assert modal is not None
    unlink_parent(db_session, hedging, modal)
    assert modal.id not in hedging.parent_ids
    link_parent(db_session, hedging, modal)
    assert modal.id in hedging.parent_ids

    item = create_learning_item(
        db_session,
        user,
        type_="grammar_rule",
        text="Hedging recommendations",
    )
    item.linked_grammar_concept_id = hedging.id
    db_session.add(
        MistakePattern(
            user_id=user.id,
            description="Hedging issue",
            mistake_type="hedging",
            linked_grammar_concept_id=hedging.id,
            confidence="high",
            status="active",
            event_count=3,
        )
    )
    db_session.flush()
    assert "1 items, 1 patterns" in handle_rules(db_session).text

    for index in range(25):
        favorite = create_learning_item(
            db_session,
            user,
            type_="expression",
            text=f"favorite {index}",
        )
        toggle_favorite(db_session, favorite)
    archived = create_learning_item(
        db_session, user, type_="expression", text="archived favorite"
    )
    toggle_favorite(db_session, archived)
    set_item_status(db_session, archived, "archived")
    favorites = handle_favorites(db_session, user).text.splitlines()
    assert len([line for line in favorites if line.startswith("- #")]) == 20
    assert archived.is_favorite


def test_channel_discovery_from_updates() -> None:
    updates = [
        {
            "my_chat_member": {
                "chat": {
                    "id": -100123,
                    "type": "channel",
                    "title": "FluentLoop English",
                }
            }
        }
    ]
    assert find_channel_from_updates(updates, "FluentLoop English") == -100123


def test_channel_discovery_cache_round_trips(tmp_path) -> None:
    path = tmp_path / "channel_discovery.json"
    record_channel_discovery(
        path,
        title="FluentLoop English",
        channel_id=-100123,
    )
    assert read_recorded_channel(path, "FluentLoop English") == -100123
    assert read_recorded_channel(path, "Other") is None


def test_bot_api_inline_keyboard_payload() -> None:
    reply = BotReply(
        "Hi",
        "-1001",
        buttons=[[InlineButton("Start practice", "today:start")]],
        message_thread_id=42,
    )
    assert inline_keyboard(reply) == {
        "inline_keyboard": [
            [{"text": "Start practice", "callback_data": "today:start"}]
        ]
    }


def test_bot_api_reply_sends_html_parse_mode(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_call_bot_api(token: str, method: str, payload: dict) -> dict:
        captured.update({"token": token, "method": method, "payload": payload})
        return {"ok": True, "result": {"message_id": 42}}

    monkeypatch.setattr("fluentloop.telegram_bot_api.call_bot_api", fake_call_bot_api)
    reply = BotReply(
        "<b>Hi</b>",
        "-1001",
        message_thread_id=42,
        parse_mode=HTML_PARSE_MODE,
    )

    sent = asyncio.run(send_bot_api_reply("token", reply))

    assert sent.message_id == 42
    assert captured["payload"]["parse_mode"] == "HTML"
