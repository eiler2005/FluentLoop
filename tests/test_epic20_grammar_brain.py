from __future__ import annotations

from sqlalchemy import func, select

from fluentloop.db.models import GrammarConcept, MistakePattern
from fluentloop.grammar import parents_of, seed_concepts, select_focus_concept
from fluentloop.learning import create_learning_item
from fluentloop.learning_engine import compose_learning_session
from fluentloop.users import ensure_user


def test_seeded_business_grammar_concepts_exist(db_session) -> None:
    seed_concepts(db_session)

    titles = {
        row
        for row in db_session.scalars(select(GrammarConcept.title))
    }

    assert db_session.scalar(select(func.count()).select_from(GrammarConcept)) >= 12
    assert "Articles with specific project events" in titles
    assert "Business collocations with prepositions" in titles
    assert "Countable / uncountable business nouns" in titles
    assert "Register and tone in stakeholder communication" in titles


def test_seed_concepts_is_idempotent_and_adds_missing(db_session) -> None:
    db_session.add(
        GrammarConcept(
            title="Hedging recommendations",
            description="Old description",
            examples=[],
        )
    )
    db_session.flush()

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
    assert "stakeholder" in hedging.description
    assert modal.id in hedging.parent_ids
    assert parents_of(db_session, hedging.id, depth=2)


def test_select_focus_concept_uses_linked_mistake_pattern(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    seed_concepts(db_session)
    concept = db_session.scalar(
        select(GrammarConcept).where(
            GrammarConcept.title == "Articles with specific project events"
        )
    )
    assert concept is not None
    pattern = MistakePattern(
        user_id=user.id,
        description="Missing article before sprint",
        mistake_type="articles",
        linked_grammar_concept_id=concept.id,
        confidence="high",
        status="active",
        event_count=3,
    )

    selected = select_focus_concept(db_session, patterns=[pattern])

    assert selected is not None
    assert selected.id == concept.id


def test_grammar_focus_stage_uses_relevant_concept(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    seed_concepts(db_session)
    concept = db_session.scalar(
        select(GrammarConcept).where(
            GrammarConcept.title == "Business collocations with prepositions"
        )
    )
    assert concept is not None
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="align on priorities",
        tags=["prepositions"],
    )
    db_session.add(
        MistakePattern(
            user_id=user.id,
            description="Use align on + topic",
            mistake_type="preposition",
            linked_learning_item_id=item.id,
            linked_grammar_concept_id=concept.id,
            confidence="high",
            status="active",
            wrong_examples=["We need align priorities."],
            correct_examples=["We need to align on priorities."],
            event_count=3,
        )
    )
    db_session.flush()

    exercises = compose_learning_session(db_session, user)
    grammar_step = next(
        exercise
        for exercise in exercises
        if exercise["stage"] == "grammar_or_mistake_focus"
    )

    assert grammar_step["grammar_concept_id"] == concept.id
    assert "Business collocations with prepositions" in grammar_step["prompt"]
    assert "align on" in grammar_step["prompt"]

