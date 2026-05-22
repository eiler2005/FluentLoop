from __future__ import annotations

from fluentloop.config import get_settings
from fluentloop.db.session import make_engine, make_session_factory, session_scope
from fluentloop.evaluation import build_monthly_probe
from fluentloop.users import ensure_user


def main() -> None:
    settings = get_settings()
    if settings.telegram_allowed_user_id is None:
        raise SystemExit("TELEGRAM_ALLOWED_USER_ID is required for evaluation.")
    engine = make_engine(settings.db_url)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        user = ensure_user(session, settings.telegram_allowed_user_id, settings)
        probe = build_monthly_probe(session, user)
        print(probe.title)
        print(f"Held-out item ids: {probe.held_out_item_ids}")
        print(probe.prompt)


if __name__ == "__main__":
    main()
