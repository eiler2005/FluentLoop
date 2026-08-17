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
