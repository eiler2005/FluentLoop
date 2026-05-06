from __future__ import annotations

from fluentloop.channel import find_channel_from_updates
from fluentloop.grammar import parents_of, seed_concepts
from fluentloop.learning import create_learning_item, toggle_favorite
from fluentloop.practice import cache_session
from fluentloop.stats import collect_stats, render_stats, weekly_summary
from fluentloop.users import ensure_user


def test_generation_cache_stats_favorites_and_rules(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="expression", text="align on")
    toggle_favorite(db_session, item)
    cached = cache_session(
        db_session, user, target_date=__import__("datetime").date.today()
    )
    assert len(cached.exercises) == 7
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
