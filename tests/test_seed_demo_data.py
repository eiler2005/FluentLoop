from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import func, select

from fluentloop.db.models import (
    LearningItem,
    MistakePattern,
    PracticeSession,
    PracticeSessionCached,
    SourceMaterial,
)
from fluentloop.db.session import make_engine, make_session_factory


def load_seed_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "seed_demo_data.py"
    spec = importlib.util.spec_from_file_location("seed_demo_data", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_seed_demo_data_is_idempotent_and_covers_core_entities(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "123456789")
    db_url = f"sqlite:///{tmp_path / 'seed.sqlite'}"
    module = load_seed_module()

    first = module.seed_demo_data(db_url)
    second = module.seed_demo_data(db_url)

    assert first["items"] == second["items"]
    assert second["approved_now"] == 0

    engine = make_engine(db_url)
    factory = make_session_factory(engine)
    with factory() as session:
        assert first["lesson_count"] == 3
        assert session.scalar(select(func.count()).select_from(LearningItem)) >= 16
        assert session.scalar(select(func.count()).select_from(SourceMaterial)) == 4
        assert session.scalar(select(func.count()).select_from(MistakePattern)) == 1
        assert (
            session.scalar(select(func.count()).select_from(PracticeSessionCached))
            == 1
        )
        completed = session.scalar(
            select(PracticeSession).where(PracticeSession.status == "completed")
        )
        assert completed is not None
