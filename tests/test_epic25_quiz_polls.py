"""Native quiz polls. No network: Telethon TL objects construct offline."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fluentloop.bot.handlers import handle_poll_vote, render_daily_slot
from fluentloop.bot.polls import (
    build_input_media_poll,
    option_bytes,
    option_index,
    resolve_vote,
    send_quiz_poll,
    spec_from_payload,
)
from fluentloop.db.models import ReviewState, VocabDelivery
from fluentloop.learning import create_learning_item
from fluentloop.quiz import build_quiz_spec
from fluentloop.users import ensure_user
from fluentloop.vocab_loop import QuizSpec

NOW = datetime(2026, 8, 17, 16, 0, tzinfo=UTC)
SPEC = QuizSpec(
    item_id=7,
    question='Which word or phrase means: "a chain of build steps"?',
    options=["alpha", "beta", "pipeline", "gamma"],
    correct_index=2,
    solution="a chain of build steps",
)


class FakePollMessage:
    def __init__(self, poll_id: int) -> None:
        self.id = 4321
        self.media = type(
            "Media", (), {"poll": type("Poll", (), {"id": poll_id})()}
        )()


class FakePollClient:
    def __init__(self, poll_id: int = 999) -> None:
        self.poll_id = poll_id
        self.media = None

    async def send_file(self, chat_id, media):
        self.media = media
        return FakePollMessage(self.poll_id)


def _prepared_delivery(session, user, *, settings, poll_id: int | None = None):
    for index in range(5):
        create_learning_item(
            session, user, type_="word", text=f"filler-{index}", meaning="a meaning"
        )
    create_learning_item(
        session, user, type_="word", text="pipeline", meaning="a chain of build steps"
    )
    delivery = VocabDelivery(
        user_id=user.id, local_date=NOW.date(), slot="evening", seq=0, status="claimed"
    )
    session.add(delivery)
    session.flush()
    render_daily_slot(
        session, user, "evening", delivery, now=NOW, settings=settings
    )
    if poll_id is not None:
        delivery.poll_id = poll_id
        session.add(delivery)
        session.flush()
    return delivery


# --- building the poll -----------------------------------------------------


def test_option_ids_round_trip() -> None:
    assert option_bytes(2) == b"2"
    assert option_index(b"2") == 2
    assert option_index(b"not-a-number") is None


def test_poll_media_has_the_required_shape() -> None:
    media = build_input_media_poll(SPEC)

    assert media.poll.question.text == SPEC.question
    assert [answer.option for answer in media.poll.answers] == [
        b"0",
        b"1",
        b"2",
        b"3",
    ]
    assert [answer.text.text for answer in media.poll.answers] == SPEC.options
    assert media.poll.quiz is True
    # Without public_voters Telegram delivers no vote updates at all.
    assert media.poll.public_voters is True
    assert media.poll.multiple_choice is False
    assert media.correct_answers == [b"2"]
    assert media.solution == SPEC.solution


def test_poll_solution_is_truncated() -> None:
    spec = QuizSpec(1, "q?", ["a", "b", "c", "d"], 0, solution="x" * 500)

    assert len(build_input_media_poll(spec).solution) == 200


def test_poll_without_solution_sends_none() -> None:
    spec = QuizSpec(1, "q?", ["a", "b", "c", "d"], 0, solution="")

    media = build_input_media_poll(spec)

    assert media.solution is None
    assert media.solution_entities is None


@pytest.mark.parametrize("solution", ["a definition", "", "x" * 500])
def test_poll_media_serialises(solution) -> None:
    """Telethon validates solution/solution_entities only in _bytes().

    Asserting on attributes alone missed a production failure where a poll
    with a solution but no solution_entities blew up on send.
    """

    spec = QuizSpec(1, "q?", ["a", "b", "c", "d"], 2, solution=solution)

    assert bytes(build_input_media_poll(spec))


@pytest.mark.asyncio
async def test_send_quiz_poll_returns_ids() -> None:
    client = FakePollClient(poll_id=555)

    poll_id, message_id = await send_quiz_poll(client, 42, SPEC)

    assert (poll_id, message_id) == (555, 4321)
    assert client.media.poll.quiz is True


def test_spec_from_payload_rebuilds_the_question() -> None:
    payload = {
        "question": "q?",
        "options": ["a", "b", "c", "d"],
        "correct_index": 1,
        "solution": "s",
    }

    spec = spec_from_payload(payload, item_id=3)

    assert spec.correct_index == 1
    assert spec.item_id == 3


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"options": []},
        {"options": ["a", "b"], "correct_index": 9},
        {"options": ["a", "b"], "correct_index": "x"},
    ],
)
def test_spec_from_payload_rejects_broken_payloads(payload) -> None:
    assert spec_from_payload(payload, item_id=1) is None


# --- receiving the vote ----------------------------------------------------


def test_resolve_vote_records_a_correct_answer(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    delivery = _prepared_delivery(db_session, user, settings=settings, poll_id=777)
    correct = delivery.payload_json["correct_index"]

    outcome = resolve_vote(db_session, 777, [option_bytes(correct)])

    assert outcome is not None
    assert outcome.correct is True
    assert outcome.telegram_user_id == 123456789
    assert delivery.status == "answered"
    item_id = delivery.learning_item_ids[0]
    state = db_session.query(ReviewState).filter_by(learning_item_id=item_id).one()
    assert state.success_count == 1


def test_resolve_vote_records_a_wrong_answer(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    delivery = _prepared_delivery(db_session, user, settings=settings, poll_id=778)
    wrong = (delivery.payload_json["correct_index"] + 1) % 4

    outcome = resolve_vote(db_session, 778, [option_bytes(wrong)])

    assert outcome.correct is False
    item_id = delivery.learning_item_ids[0]
    state = db_session.query(ReviewState).filter_by(learning_item_id=item_id).one()
    assert state.fail_count == 1


def test_resolve_vote_on_unknown_poll_is_silent(db_session, settings) -> None:
    ensure_user(db_session, 123456789, settings)

    assert resolve_vote(db_session, 424242, [b"0"]) is None


def test_resolve_vote_ignores_a_second_vote(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _prepared_delivery(db_session, user, settings=settings, poll_id=779)

    assert resolve_vote(db_session, 779, [b"0"]) is not None
    assert resolve_vote(db_session, 779, [b"1"]) is None


def test_resolve_vote_ignores_empty_and_broken_options(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _prepared_delivery(db_session, user, settings=settings, poll_id=780)

    assert resolve_vote(db_session, 780, []) is None
    assert resolve_vote(db_session, 780, [b"zzz"]) is None


def test_poll_vote_reply_is_addressed_to_the_learner(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    delivery = _prepared_delivery(db_session, user, settings=settings, poll_id=781)
    correct = delivery.payload_json["correct_index"]

    reply = handle_poll_vote(db_session, 781, [option_bytes(correct)])

    assert reply is not None
    assert reply.target_chat_id == 123456789
    assert "✅ Right" in reply.text


def test_poll_vote_on_unknown_poll_returns_no_reply(db_session, settings) -> None:
    ensure_user(db_session, 123456789, settings)

    assert handle_poll_vote(db_session, 4242, [b"0"]) is None


def test_poll_vote_announces_graduation(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    delivery = _prepared_delivery(db_session, user, settings=settings, poll_id=782)
    item_id = delivery.learning_item_ids[0]
    state = db_session.query(ReviewState).filter_by(learning_item_id=item_id).one()
    state.last_interval_days = 120.0
    state.success_count = 4
    db_session.flush()
    correct = delivery.payload_json["correct_index"]

    reply = handle_poll_vote(db_session, 782, [option_bytes(correct)])

    assert "🎓 Graduated!" in reply.text


# --- the scheduler falls back when the raw path fails ----------------------


@pytest.mark.asyncio
async def test_tick_falls_back_to_buttons_when_poll_fails(
    tmp_path, settings
) -> None:
    from dataclasses import replace

    from fluentloop.db.session import make_engine, make_session_factory
    from fluentloop.scheduler import run_vocab_tick

    engine = make_engine(f"sqlite:///{tmp_path / 'polls.sqlite'}")
    factory = make_session_factory(engine)
    with factory() as session:
        user = ensure_user(session, 123456789, settings)
        user.timezone = "Europe/Moscow"
        for index in range(6):
            create_learning_item(
                session,
                session.get(type(user), user.id),
                type_="word",
                text=f"word-{index}",
                meaning="a meaning",
            )
        session.commit()

    class BrokenPollClient:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send_file(self, chat_id, media):
            raise RuntimeError("raw API rejected the poll")

        async def send_message(self, chat_id, text, buttons=None, parse_mode=None):
            self.sent.append(text)
            return type("Msg", (), {"id": 1})()

    client = BrokenPollClient()
    evening = datetime(2026, 8, 17, 16, 0, tzinfo=UTC)

    sent = await run_vocab_tick(
        client, factory, replace(settings, vocab_quiz_polls=True), now=evening
    )

    assert sent == 1
    assert "Evening quiz" in client.sent[0]
    with factory() as session:
        delivery = session.query(VocabDelivery).one()
        assert delivery.status == "sent"
        assert delivery.poll_id is None


@pytest.mark.asyncio
async def test_tick_stores_poll_id_on_success(tmp_path, settings) -> None:
    from dataclasses import replace

    from fluentloop.db.session import make_engine, make_session_factory
    from fluentloop.scheduler import run_vocab_tick

    engine = make_engine(f"sqlite:///{tmp_path / 'polls-ok.sqlite'}")
    factory = make_session_factory(engine)
    with factory() as session:
        user = ensure_user(session, 123456789, settings)
        user.timezone = "Europe/Moscow"
        for index in range(6):
            create_learning_item(
                session, user, type_="word", text=f"word-{index}", meaning="a meaning"
            )
        session.commit()

    client = FakePollClient(poll_id=31337)
    evening = datetime(2026, 8, 17, 16, 0, tzinfo=UTC)

    sent = await run_vocab_tick(
        client, factory, replace(settings, vocab_quiz_polls=True), now=evening
    )

    assert sent == 1
    with factory() as session:
        delivery = session.query(VocabDelivery).one()
        assert delivery.poll_id == 31337
        assert delivery.payload_json["mode"] == "poll"


def test_quiz_spec_is_reproducible(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    for index in range(5):
        create_learning_item(
            db_session, user, type_="word", text=f"filler-{index}", meaning="m"
        )
    target = create_learning_item(
        db_session, user, type_="word", text="pipeline", meaning="build steps"
    )

    first = build_quiz_spec(db_session, user, target, settings=settings)
    second = build_quiz_spec(db_session, user, target, settings=settings)

    assert first == second
