from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from fluentloop.db.models import User
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.workplace_roadmap import (
    CURRICULUM_PATH,
    SKILLS,
    default_plan,
    get_plan,
    load_curriculum,
    plan_outline,
    read_json,
    save_plan,
    update_plan,
    validate_curriculum,
    validate_plan,
)


@pytest.fixture
def catalog() -> dict:
    ids = ["general_reading", "general_writing", "work_client", "work_tech"]
    stages = {
        stage: "An independently produced sample."
        for stage in (
            "b2",
            "b2_plus",
            "c1_intro",
        )
    }
    return {
        "version": 1,
        "title_ru": "Учебный план",
        "assumptions_ru": ["План не подтверждает уровень."],
        "skills": {skill: skill for skill in SKILLS},
        "sources": [
            {
                "id": "cefr",
                "title": "CEFR",
                "url": "https://www.coe.int/",
                "publisher": "Council of Europe",
                "accessed": "2026-10-03",
            }
        ],
        "tracks": {
            "balanced": {"title_ru": "Общий", "module_ids": ids},
            "client_facing": {"title_ru": "Клиенты", "module_ids": ids[::-1]},
            "big_tech": {"title_ru": "Технологии", "module_ids": ids[1:] + ids[:1]},
        },
        "modules": [
            {
                "id": identifier,
                "title_ru": identifier,
                "area": "English",
                "strand": "general" if identifier.startswith("general") else "work",
                "skills": ["writing"],
                "language_focus": ["Cohesion"],
                "adaptive_topics": ["cohesion"],
                "library_slugs": [],
                "outcomes": deepcopy(stages),
                "tasks": deepcopy(stages),
                "evidence": ["Clear purpose and appropriate supporting detail."],
                "delivery": "mixed",
                "source_ids": ["cefr"],
            }
            for identifier in ids
        ],
        "language_map": [
            {
                "id": "cohesion",
                "title_ru": "Связность",
                "b2_focus": "Links",
                "c1_focus": "Flexible links",
                "module_ids": ids,
                "adaptive_topics": ["cohesion"],
                "coverage": "partial",
            }
        ],
    }


@pytest.fixture
def owner(db_session) -> User:
    user = User(
        telegram_user_id=123456789,
        preferences_json={
            "learning": {"mode": "simple", "adaptive_auto_expand": True},
            "vocab": {"paused": True},
            "unrelated": {"keep": [1, 2]},
        },
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_catalog_validates_and_returns_isolated_copy(catalog):
    validated = validate_curriculum(catalog)
    validated["modules"][0]["title_ru"] = "Edited"
    assert catalog["modules"][0]["title_ru"] != "Edited"


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(version=True),
        lambda c: c.update(extra="unexpected"),
        lambda c: c["modules"].append(deepcopy(c["modules"][0])),
        lambda c: c["modules"][0].update(skills=["unknown"]),
        lambda c: c["modules"][0].update(adaptive_topics=["unknown"]),
        lambda c: c["modules"][0].update(library_slugs=["unknown"]),
        lambda c: c["modules"][0].update(source_ids=["unknown"]),
        lambda c: c["modules"][0].update(strand="unknown"),
        lambda c: c["modules"][0].update(delivery="activate"),
        lambda c: c["modules"][0]["tasks"].pop("c1_intro"),
        lambda c: c["modules"][0]["outcomes"].update(c1_intro=""),
        lambda c: c["sources"][0].update(url="javascript:alert(1)"),
        lambda c: c["sources"][0].update(url="http://www.coe.int/"),
        lambda c: c["sources"][0].update(accessed="tomorrow"),
        lambda c: c["tracks"]["balanced"]["module_ids"].pop(),
        lambda c: c["tracks"]["balanced"]["module_ids"].append("general_reading"),
        lambda c: c["language_map"][0].update(module_ids=["unknown"]),
        lambda c: c["language_map"][0].update(coverage="complete"),
        lambda c: c["language_map"][0].update(adaptive_topics=[]),
    ],
)
def test_catalog_rejects_invalid_content(catalog, change):
    change(catalog)
    with pytest.raises(ValueError):
        validate_curriculum(catalog)


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(version=True),
        lambda p: p.update(version=2),
        lambda p: p.update(assessed_level="C1"),
        lambda p: p.pop("notes"),
        lambda p: p.update(track="unknown"),
        lambda p: p.update(track=[]),
        lambda p: p.update(weekly_minutes=True),
        lambda p: p.update(weekly_minutes=150.0),
        lambda p: p.update(weekly_minutes=29),
        lambda p: p.update(weekly_minutes=1201),
        lambda p: p.update(general_share=False),
        lambda p: p.update(general_share=19),
        lambda p: p.update(general_share=91),
        lambda p: p["order"].pop(),
        lambda p: p["order"].append("general_reading"),
        lambda p: p["order"].append("unknown"),
        lambda p: p.update(paused=["general_reading", "general_writing"]),
        lambda p: p.update(paused=["work_client", "work_tech"]),
        lambda p: p.update(paused=["general_reading", "general_reading"]),
        lambda p: p.update(paused=["unknown"]),
        lambda p: p.update(focus="unknown"),
        lambda p: p.update(focus=[]),
        lambda p: p.update(paused=["general_reading"], focus="general_reading"),
        lambda p: p.update(notes={"unknown": "Private note"}),
        lambda p: p.update(notes={"general_reading": "x" * 1001}),
        lambda p: p.update(notes={"general_reading": 1}),
        lambda p: p.update(notes={"general_reading": "\x00"}),
        lambda p: p.update(notes={"general_reading": "\ud800"}),
    ],
)
def test_plan_import_rejects_invalid_payload(catalog, change):
    plan = default_plan(catalog)
    change(plan)
    with pytest.raises(ValueError):
        validate_plan(plan, catalog)


@pytest.mark.parametrize("value", [None, [], "{}", True, 1])
def test_plan_requires_an_object(catalog, value):
    with pytest.raises(ValueError):
        validate_plan(value, catalog)


def test_save_preserves_other_preferences_and_other_profiles(
    db_session, owner, catalog
):
    library_owner = User(telegram_user_id=0, preferences_json={"unchanged": True})
    db_session.add(library_owner)
    before = deepcopy(owner.preferences_json)
    plan = default_plan(catalog)
    plan["notes"] = {"work_client": "Literal <script> and https://example.com/ text"}
    saved = save_plan(db_session, owner, plan, catalog)
    for key, value in before.items():
        assert owner.preferences_json[key] == value
    assert library_owner.preferences_json == {"unchanged": True}
    saved["notes"]["work_client"] = "Changed after saving"
    plan["order"].reverse()
    db_session.expire(owner)
    stored = get_plan(owner, catalog)
    assert stored["notes"]["work_client"].startswith("Literal")
    assert stored["order"] == catalog["tracks"]["client_facing"]["module_ids"]
    stored["paused"].append("work_client")
    assert get_plan(owner, catalog)["paused"] == []


def test_invalid_import_leaves_entire_preferences_unchanged(db_session, owner, catalog):
    save_plan(db_session, owner, default_plan(catalog), catalog)
    before = deepcopy(owner.preferences_json)
    plan = get_plan(owner, catalog)
    plan["notes"] = {"work_client": "Would be valid"}
    plan["paused"] = ["general_reading", "general_writing"]
    with pytest.raises(ValueError):
        save_plan(db_session, owner, plan, catalog)
    assert owner.preferences_json == before
    db_session.expire(owner)
    assert owner.preferences_json == before


def test_defaults_allocate_general_work_and_lexical(owner, catalog):
    first = get_plan(owner, catalog)
    first["notes"]["general_reading"] = "Only in returned copy"
    assert "workplace_plan" not in owner.preferences_json
    assert get_plan(owner, catalog)["notes"] == {}
    outline = plan_outline(first, catalog)
    assert outline["general_minutes"] == 45
    assert outline["work_minutes"] == 60
    assert outline["lexical_minutes"] == 45
    assert first["lexical_share"] == 30
    assert first["track"] == "client_facing"
    assert outline["general_focus"]["id"] == "general_writing"
    assert outline["work_focus"]["id"] == "work_tech"


def test_note_bound_counts_unicode_codepoints(catalog):
    plan = default_plan(catalog)
    plan["notes"] = {"general_reading": "📖" * 1000}
    assert validate_plan(plan, catalog)["notes"] == plan["notes"]


def test_new_recommendation_does_not_replace_saved_plan(db_session, owner, catalog):
    previous = default_plan(catalog)
    previous.update(
        track="balanced",
        general_share=60,
        lexical_share=0,
        weekly_minutes=200,
        order=list(catalog["tracks"]["balanced"]["module_ids"]),
        paused=["general_writing"],
        focus="work_client",
        notes={"work_client": "Keep my existing plan"},
    )
    save_plan(db_session, owner, previous, catalog)
    assert default_plan(catalog)["general_share"] == 30
    assert get_plan(owner, catalog) == previous
    changed = update_plan(db_session, owner, "general_share", 30, catalog)
    assert changed == {**previous, "general_share": 30}


def test_updates_keep_notes_pauses_focus_and_mode(db_session, owner, catalog):
    plan = default_plan(catalog)
    plan.update(paused=["general_reading"], focus="work_client")
    plan["notes"]["work_tech"] = "Read after the general foundation."
    save_plan(db_session, owner, plan, catalog)
    updated = update_plan(db_session, owner, "track", "big_tech", catalog)
    assert updated["order"] == catalog["tracks"]["big_tech"]["module_ids"]
    assert updated["notes"] == plan["notes"]
    assert updated["paused"] == plan["paused"]
    assert updated["focus"] == "work_client"
    update_plan(db_session, owner, "time", 120, catalog)
    update_plan(db_session, owner, "lexical_share", 0, catalog)
    updated = update_plan(db_session, owner, "general_share", 70, catalog)
    outline = plan_outline(updated, catalog)
    assert (outline["general_minutes"], outline["work_minutes"]) == (84, 36)
    assert owner.preferences_json["learning"]["mode"] == "simple"
    update_plan(db_session, owner, "pause", "work_client", catalog)
    assert get_plan(owner, catalog)["focus"] is None
    update_plan(db_session, owner, "resume", "work_client", catalog)
    assert get_plan(owner, catalog)["paused"] == ["general_reading"]
    update_plan(db_session, owner, "focus", "general_writing", catalog)
    assert get_plan(owner, catalog)["focus"] == "general_writing"


def test_outline_follows_order_and_focus_in_each_strand(catalog):
    plan = default_plan(catalog)
    plan["order"] = list(reversed(catalog["tracks"]["balanced"]["module_ids"]))
    plan["focus"] = "work_client"
    outline = plan_outline(plan, catalog)
    assert outline["general_focus"]["id"] == "general_writing"
    assert outline["work_focus"]["id"] == "work_client"
    assert [module["id"] for module in outline["next_work"]] == ["work_tech"]
    plan["paused"] = ["general_writing"]
    assert plan_outline(plan, catalog)["general_focus"]["id"] == "general_reading"


def test_invalid_update_is_atomic(db_session, owner, catalog):
    before = deepcopy(owner.preferences_json)
    for action, value in [("time", True), ("track", "invalid"), ("mastery", "C1")]:
        with pytest.raises(ValueError):
            update_plan(db_session, owner, action, value, catalog)
        assert owner.preferences_json == before


@pytest.mark.parametrize(
    "preferences", [False, [], "invalid", {"workplace_plan": None}]
)
def test_corrupt_stored_preferences_are_not_silently_replaced(
    owner, catalog, preferences
):
    owner.preferences_json = preferences
    with pytest.raises(ValueError):
        get_plan(owner, catalog)


@pytest.mark.parametrize(
    "content",
    [
        '{"version":1,"version":1}',
        '{"value":NaN}',
        '{"value":Infinity}',
    ],
)
def test_portable_json_rejects_duplicate_fields_and_nonfinite_values(tmp_path, content):
    path = tmp_path / "invalid.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        read_json(path)


def _cli():
    path = Path(__file__).resolve().parents[1] / "scripts" / "workplace_plan.py"
    spec = importlib.util.spec_from_file_location("workplace_plan_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_default_and_exports_do_not_load_settings(tmp_path, catalog, monkeypatch):
    def forbid():
        raise AssertionError("Dry run must not load environment or DB settings")

    monkeypatch.setattr("fluentloop.config.get_settings", forbid)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    exported = tmp_path / "plan.json"
    cli = _cli()
    assert cli.main(["--catalog", str(path)]) == 0
    assert cli.main(["--catalog", str(path), "--export", str(exported)]) == 0
    assert read_json(exported) == default_plan(catalog)
    assert exported.stat().st_mode & 0o777 == 0o600
    assert (
        cli.main(
            [
                "--catalog",
                str(path),
                "--profile",
                str(exported),
                "--export",
                str(tmp_path / "second.json"),
            ]
        )
        == 0
    )


@pytest.mark.parametrize(
    "args",
    [
        ["--apply"],
        ["--apply", "--pilot"],
        ["--pilot"],
        ["--db-url", "sqlite:///:memory:"],
        ["--export-pilot", "plan.json", "--export", "other.json"],
    ],
)
def test_cli_rejects_ambiguous_db_intent(args):
    with pytest.raises(SystemExit) as exc:
        _cli().main(args)
    assert exc.value.code == 2


def test_cli_invalid_profile_rejected_before_config(tmp_path, catalog, monkeypatch):
    monkeypatch.setattr(
        "fluentloop.config.get_settings", lambda: pytest.fail("DB read")
    )
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    profile = tmp_path / "invalid.json"
    profile.write_text('{"version":1}', encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _cli().main(
            [
                "--catalog",
                str(path),
                "--profile",
                str(profile),
                "--apply",
                "--pilot",
            ]
        )
    assert exc.value.code == 2


def test_portable_json_size_and_depth_limits(tmp_path):
    path = tmp_path / "large.json"
    path.write_text('"' + "x" * 100 + '"', encoding="utf-8")
    with pytest.raises(ValueError, match="size"):
        read_json(path, max_bytes=50)
    path.write_text("[" * 2000 + "]" * 2000, encoding="utf-8")
    with pytest.raises(ValueError, match="depth"):
        read_json(path)


def test_cli_apply_and_pilot_export_preserve_unrelated_state(
    tmp_path, catalog, settings, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'pilot.sqlite'}"
    factory = make_session_factory(make_engine(database_url))
    before = {"learning": {"mode": "simple"}, "assessed": {"cohesion": "b2"}}
    with factory() as session, session.begin():
        session.add(User(telegram_user_id=123456789, preferences_json=before))
        session.add(User(telegram_user_id=0, preferences_json={"keep": True}))
    monkeypatch.setattr(
        "fluentloop.config.get_settings", lambda: replace(settings, db_url=database_url)
    )
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    profile = tmp_path / "profile.json"
    plan = default_plan(catalog)
    plan.update(track="client_facing", general_share=75, lexical_share=0)
    profile.write_text(json.dumps(plan), encoding="utf-8")
    cli = _cli()
    assert (
        cli.main(
            [
                "--catalog",
                str(path),
                "--profile",
                str(profile),
                "--apply",
                "--pilot",
            ]
        )
        == 0
    )
    with factory() as session:
        users = session.query(User).order_by(User.id).all()
        assert users[0].preferences_json == {**before, "workplace_plan": plan}
        assert users[1].preferences_json == {"keep": True}
    exported = tmp_path / "exported.json"
    assert (
        cli.main(
            [
                "--catalog",
                str(path),
                "--export-pilot",
                str(exported),
            ]
        )
        == 0
    )
    assert read_json(exported) == plan


def test_cli_public_render_and_freshness_use_no_settings(
    tmp_path, catalog, monkeypatch
):
    monkeypatch.setattr(
        "fluentloop.config.get_settings", lambda: pytest.fail("DB read")
    )
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    output = tmp_path / "rendered"
    cli = _cli()
    assert cli.main(["--catalog", str(path), "--render", str(output)]) == 0
    assert cli.main(["--catalog", str(path), "--check-render", str(output)]) == 0
    html = output / "workplace-planner.html"
    html.write_text(html.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        cli.main(["--catalog", str(path), "--check-render", str(output)])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        cli.main(
            ["--catalog", str(path), "--render", str(output), "--apply", "--pilot"]
        )
    assert exc.value.code == 2


def test_shipped_catalog_has_general_and_workplace_coverage():
    assert CURRICULUM_PATH.exists()
    catalog = load_curriculum()
    assert len(catalog["modules"]) == 48
    assert sum(module["strand"] == "general" for module in catalog["modules"]) == 16
    assert len(catalog["language_map"]) >= 10
    outline = plan_outline(default_plan(catalog), catalog)
    assert (
        outline["general_minutes"],
        outline["work_minutes"],
        outline["lexical_minutes"],
    ) == (45, 60, 45)


def test_cli_shipped_default_requires_no_profile_or_settings(monkeypatch, capsys):
    monkeypatch.setattr(
        "fluentloop.config.get_settings", lambda: pytest.fail("DB read")
    )
    assert _cli().main([]) == 0
    assert "modules=48 track=client_facing" in capsys.readouterr().out
