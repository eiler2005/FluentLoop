from datetime import UTC, datetime

from fluentloop.db.models import LearningItem, LessonPlan, ReviewState
from fluentloop.evaluation import select_held_out_items
from fluentloop.learning import active_items
from fluentloop.learning_engine import score_learning_items
from fluentloop.lesson_plans import available_lesson_plan, random_lesson_plan
from fluentloop.quiz import select_distractors
from fluentloop.srs import get_due_items
from fluentloop.users import ensure_user
from fluentloop.vocab_loop import select_cards


def test_generic_learning_paths_cannot_expose_curriculum_questions(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    ordinary = LearningItem(
        user_id=user.id,
        type="expression",
        text="push back on",
        meaning="challenge a proposal",
        examples=["We pushed back on the scope."],
    )
    protected = LearningItem(
        user_id=user.id,
        type="expression",
        text="RESERVED_TRANSFER_ANSWER",
        meaning="a reserved answer",
        metadata_json={
            "simple_question": {
                "adaptive": {
                    "version": 1,
                    "topic_id": "aspect",
                    "stage": "b2",
                    "role": "transfer",
                    "variant_id": "heldout",
                }
            }
        },
    )
    db_session.add_all([ordinary, protected])
    db_session.flush()
    now = datetime.now(UTC)
    db_session.add_all(
        [
            ReviewState(learning_item_id=item.id, due_at=now)
            for item in (ordinary, protected)
        ]
    )
    db_session.flush()
    for items in (
        active_items(db_session, user.id),
        get_due_items(db_session, user.id, now=now),
        [entry.item for entry in score_learning_items(db_session, user, now=now)],
        select_cards(db_session, user, count=10, now=now),
        select_held_out_items(db_session, user),
    ):
        assert ordinary.id in {item.id for item in items}
        assert protected.id not in {item.id for item in items}
    assert protected.text not in select_distractors(db_session, user, ordinary)


def test_automatic_full_lessons_do_not_choose_adaptive_plans(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    plan = LessonPlan(
        user_id=user.id,
        title="Adaptive topic",
        status="active",
        tags_json=["adaptive_curriculum:v1"],
    )
    db_session.add(plan)
    db_session.flush()
    assert available_lesson_plan(db_session, user) is None
    assert random_lesson_plan(db_session, user) is None
