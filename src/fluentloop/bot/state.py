from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import BotState


class StateStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, chat_id: int, user_id: int) -> BotState | None:
        return self.session.scalar(
            select(BotState).where(
                BotState.chat_id == chat_id, BotState.user_id == user_id
            )
        )

    def set(
        self,
        chat_id: int,
        user_id: int,
        name: str,
        payload: dict | None = None,
    ) -> BotState:
        state = self.get(chat_id, user_id)
        if state is None:
            state = BotState(
                chat_id=chat_id,
                user_id=user_id,
                name=name,
                payload=payload or {},
            )
        else:
            state.name = name
            state.payload = payload or {}
        self.session.add(state)
        self.session.flush()
        return state

    def clear(self, chat_id: int, user_id: int) -> None:
        state = self.get(chat_id, user_id)
        if state is not None:
            self.session.delete(state)
            self.session.flush()
