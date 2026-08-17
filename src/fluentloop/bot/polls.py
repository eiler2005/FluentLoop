"""Native Telegram quiz polls over Telethon's raw API (EPIC-25, ADR-0011).

Two constraints drive this module:

* The Bot API HTTP path in ``telegram_bot_api`` can send a poll but can never
  receive the votes, because Telethon owns the update stream and there is no
  ``getUpdates`` loop. Polls therefore go through MTProto.
* ``public_voters`` must be true. Telegram delivers no
  ``UpdateMessagePollVote`` at all for an anonymous poll, which would silently
  kill the SRS feedback path.

``resolve_vote`` is pure database work, so the whole vote path is testable
without a Telegram connection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import LearningItem, VocabDelivery
from fluentloop.vocab_loop import QuizSpec

LOG = logging.getLogger(__name__)

MAX_SOLUTION_CHARS = 200

# Slots that carry a multi-question quiz sequence. The scheduled evening slot
# and the on-demand /quiz slot share the same continuation machinery.
QUIZ_SLOTS = ("evening", "quiz")


def quiz_deliveries_for(
    session: Session, delivery: VocabDelivery
) -> list[VocabDelivery]:
    """All questions of the quiz this delivery belongs to, in order."""

    return list(
        session.scalars(
            select(VocabDelivery)
            .where(
                VocabDelivery.user_id == delivery.user_id,
                VocabDelivery.local_date == delivery.local_date,
                VocabDelivery.slot == delivery.slot,
            )
            .order_by(VocabDelivery.seq)
        ).all()
    )


def next_quiz_delivery(
    session: Session, delivery: VocabDelivery
) -> VocabDelivery | None:
    """The next unanswered question of the same quiz, if any."""

    if delivery.slot not in QUIZ_SLOTS:
        return None
    return session.scalar(
        select(VocabDelivery).where(
            VocabDelivery.user_id == delivery.user_id,
            VocabDelivery.local_date == delivery.local_date,
            VocabDelivery.slot == delivery.slot,
            VocabDelivery.seq == delivery.seq + 1,
            VocabDelivery.status == "claimed",
        )
    )


def quiz_progress(session: Session, delivery: VocabDelivery) -> tuple[int, int]:
    rows = quiz_deliveries_for(session, delivery)
    return delivery.seq + 1, len(rows)


def quiz_summary_line(
    session: Session, delivery: VocabDelivery
) -> str | None:
    """Wrap-up for a finished quiz, or None while questions remain."""

    if delivery.slot not in QUIZ_SLOTS:
        return None
    rows = quiz_deliveries_for(session, delivery)
    if any(row.status == "claimed" for row in rows):
        return None
    answered = [row for row in rows if row.status == "answered"]
    if not answered:
        return None
    correct = 0
    for row in answered:
        payload = row.payload_json or {}
        if payload.get("chosen_index") == payload.get("correct_index"):
            correct += 1
    return (
        f"🏁 Quiz done — {correct}/{len(rows)} right. "
        "Missed words come back sooner."
    )


def quiz_minutes(count: int) -> int:
    if count <= 4:
        return 1
    if count <= 8:
        return 2
    if count <= 14:
        return 3
    return 5


def quiz_intro(count: int, *, resume_at: int | None = None) -> str:
    """The announcement that opens a quiz: size, duration, what happens next."""

    from fluentloop.bot.formatting import bold

    if resume_at is not None:
        return (
            f"🎯 {bold('Quiz')} — picking up at question {resume_at}/{count}. "
            "Answer each one; the next follows right after."
        )
    return (
        f"🎯 {bold('Quiz')} — {count} questions, about {quiz_minutes(count)} "
        "minutes. Answer each one; the next follows right after."
    )


@dataclass(frozen=True)
class VoteOutcome:
    delivery_id: int
    telegram_user_id: int
    item_text: str
    correct: bool
    graduated: bool
    solution: str = ""
    options: tuple[str, ...] = ()
    correct_index: int = -1
    user_id: int = 0
    item: LearningItem | None = None


def option_bytes(index: int) -> bytes:
    """Option ids travel as bytes; ASCII indices survive the round trip."""

    return str(index).encode("ascii")


def option_index(raw: bytes) -> int | None:
    try:
        return int(bytes(raw).decode("ascii"))
    except (ValueError, UnicodeDecodeError):
        return None


def build_input_media_poll(spec: QuizSpec):  # type: ignore[no-untyped-def]
    from telethon.tl.types import (
        InputMediaPoll,
        Poll,
        PollAnswer,
        TextWithEntities,
    )

    # Telethon asserts that solution and solution_entities are both set or
    # both absent, and it only checks at serialisation time.
    solution = (spec.solution or "")[:MAX_SOLUTION_CHARS]
    return InputMediaPoll(
        poll=Poll(
            id=0,  # the server assigns the real id
            question=TextWithEntities(text=spec.question, entities=[]),
            answers=[
                PollAnswer(
                    text=TextWithEntities(text=option, entities=[]),
                    option=option_bytes(index),
                )
                for index, option in enumerate(spec.options)
            ],
            quiz=True,
            public_voters=True,  # required, or no votes are delivered
            multiple_choice=False,
        ),
        correct_answers=[option_bytes(spec.correct_index)],
        solution=solution or None,
        solution_entities=[] if solution else None,
    )


async def send_quiz_poll(client: Any, chat_id: Any, spec: QuizSpec) -> tuple[int, int]:
    """Send the quiz and return (poll_id, message_id)."""

    message = await client.send_file(chat_id, build_input_media_poll(spec))
    poll_id = int(message.media.poll.id)
    return poll_id, int(message.id)


def spec_from_payload(payload: dict, item_id: int) -> QuizSpec | None:
    options = [str(option) for option in (payload.get("options") or [])]
    if not options:
        return None
    try:
        correct_index = int(payload.get("correct_index", -1))
    except (TypeError, ValueError):
        return None
    if not 0 <= correct_index < len(options):
        return None
    return QuizSpec(
        item_id=item_id,
        question=str(payload.get("question", "")),
        options=options,
        correct_index=correct_index,
        solution=str(payload.get("solution", "")),
    )


def resolve_vote(
    session: Session, poll_id: int, options: list[bytes]
) -> VoteOutcome | None:
    """Map an incoming poll vote back to the item and record the review.

    Returns None for a poll this bot does not know about, which happens
    routinely for polls that predate a database reset.
    """

    from fluentloop.db.models import User
    from fluentloop.srs import apply_review

    delivery = session.scalar(
        select(VocabDelivery).where(VocabDelivery.poll_id == poll_id)
    )
    if delivery is None:
        return None
    if delivery.status == "answered":
        return None
    if not options:
        return None
    chosen = option_index(options[0])
    if chosen is None:
        return None

    payload = delivery.payload_json or {}
    try:
        correct_index = int(payload.get("correct_index", -1))
    except (TypeError, ValueError):
        return None
    correct = chosen == correct_index

    item_ids = delivery.learning_item_ids or []
    item = session.get(LearningItem, item_ids[0]) if item_ids else None
    graduated = False
    if item is not None:
        _, graduated = apply_review(session, item, "Good" if correct else "Again")

    delivery.status = "answered"
    delivery.payload_json = {**payload, "chosen_index": chosen}
    session.add(delivery)
    session.flush()

    user = session.get(User, delivery.user_id)
    stored_options = [str(option) for option in (payload.get("options") or [])]
    answer = (
        stored_options[correct_index]
        if 0 <= correct_index < len(stored_options)
        else ""
    )
    return VoteOutcome(
        delivery_id=delivery.id,
        telegram_user_id=user.telegram_user_id if user is not None else 0,
        item_text=item.text if item is not None else answer,
        correct=correct,
        graduated=graduated,
        solution=str(payload.get("solution", "")),
        options=tuple(stored_options),
        correct_index=correct_index,
        user_id=delivery.user_id,
        item=item,
    )


async def send_quiz_question(
    client: Any, session: Session, settings: Any, delivery_id: int
) -> bool:
    """Deliver one pre-claimed quiz question as a poll or inline buttons.

    The question and options already live on the delivery row; this only
    picks the transport and records the poll id so votes map back. Button
    mode is the fallback when the poll path is disabled or fails.
    """

    from fluentloop.bot.formatting import HTML_PARSE_MODE, bold, html_escape
    from fluentloop.db.models import User

    delivery = session.get(VocabDelivery, delivery_id)
    if delivery is None or delivery.status != "claimed":
        return False
    spec = spec_from_payload(
        delivery.payload_json or {},
        delivery.learning_item_ids[0] if delivery.learning_item_ids else 0,
    )
    if spec is None:
        return False
    user = session.get(User, delivery.user_id)
    if user is None:
        return False
    index, total = quiz_progress(session, delivery)
    if settings.vocab_quiz_polls:
        poll_spec = QuizSpec(
            item_id=spec.item_id,
            question=f"{index}/{total} · {spec.question}",
            options=list(spec.options),
            correct_index=spec.correct_index,
            solution=spec.solution,
        )
        try:
            poll_id, message_id = await send_quiz_poll(
                client, user.telegram_user_id, poll_spec
            )
        except Exception:
            LOG.exception("Native quiz poll failed; falling back to buttons")
        else:
            delivery.poll_id = poll_id
            delivery.message_id = message_id
            delivery.payload_json = {
                **(delivery.payload_json or {}),
                "mode": "poll",
            }
            session.add(delivery)
            session.flush()
            return True
    from fluentloop.bot.app import send_reply
    from fluentloop.bot.handlers import BotReply, quiz_buttons

    reply = BotReply(
        f"🎯 {bold(f'Question {index}/{total}')}\n\n{html_escape(spec.question)}",
        user.telegram_user_id,
        buttons=quiz_buttons(delivery.id, spec.options),
        parse_mode=HTML_PARSE_MODE,
    )
    await send_reply(client, user.telegram_user_id, reply, settings)
    return True
