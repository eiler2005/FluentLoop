"""Validated learning preferences, separate from assessed evidence."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from fluentloop.adaptive_curriculum import ADAPTIVE_TOPICS, STAGES
from fluentloop.db.models import User, utc_now

CURRICULUM_PATH = Path(__file__).parent / "seeds" / "workplace_curriculum_v1.json"
PLAN_NAMESPACE = "workplace_plan"
TRACKS = ("balanced", "client_facing", "big_tech")
SKILLS = (
    "reading",
    "listening",
    "writing",
    "speaking",
    "interaction",
    "mediation",
    "language",
    "register",
)
PLAN_FIELDS = {
    "version",
    "track",
    "weekly_minutes",
    "general_share",
    "order",
    "paused",
    "focus",
    "notes",
}


def _object(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{name}: missing or unknown fields")
    return value


def _text(value: Any, name: str, maximum: int = 5000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name}: nonempty text required")
    if any(ord(char) < 32 and char not in "\n\t\r" for char in value):
        raise ValueError(f"{name}: control characters are not supported")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError(f"{name}: invalid Unicode character")
    return value


def _strings(value: Any, name: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{name}: list required")
    for entry in value:
        _text(entry, name)
    if len(set(value)) != len(value):
        raise ValueError(f"{name}: duplicate entries")
    return value


def _references(
    value: Any, allowed: set[str], name: str, *, nonempty: bool = False
) -> list[str]:
    entries = _strings(value, name, nonempty=nonempty)
    if set(entries) - allowed:
        raise ValueError(f"{name}: unknown reference")
    return entries


def _version(value: Any, name: str) -> None:
    if type(value) is not int or value != 1:
        raise ValueError(f"{name}: unsupported version")


def _unique_objects(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name}: nonempty list required")
    ids: set[str] = set()
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError(f"{name}: object required")
        identifier = entry.get("id")
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", identifier)
            or identifier in ids
        ):
            raise ValueError(f"{name}: invalid or duplicate id")
        ids.add(identifier)
    return value


def validate_curriculum(data: Any) -> dict[str, Any]:
    """Validate the public syllabus and all internal references without writes."""
    catalog = _object(
        data,
        {
            "version",
            "title_ru",
            "assumptions_ru",
            "skills",
            "sources",
            "tracks",
            "modules",
            "language_map",
        },
        "Curriculum",
    )
    _version(catalog["version"], "Curriculum")
    _text(catalog["title_ru"], "Curriculum title")
    _strings(catalog["assumptions_ru"], "Assumptions", nonempty=True)
    skills = _object(catalog["skills"], set(SKILLS), "Skills")
    for label in skills.values():
        _text(label, "Skill label")
    sources = _unique_objects(catalog["sources"], "Sources")
    for source in sources:
        _object(source, {"id", "title", "url", "publisher", "accessed"}, "Source")
        for field in ("title", "publisher", "url", "accessed"):
            _text(source[field], f"Source {field}")
        try:
            url = urlsplit(source["url"])
            valid_url = (
                url.scheme == "https"
                and url.hostname
                and not url.username
                and not url.password
                and not any(c.isspace() for c in source["url"])
            )
            accessed = date.fromisoformat(source["accessed"])
        except ValueError as exc:
            raise ValueError("Invalid source URL or access date") from exc
        if not valid_url or accessed.isoformat() != source["accessed"]:
            raise ValueError("Sources require an HTTPS URL and ISO access date")
    source_ids = {source["id"] for source in sources}
    modules = _unique_objects(catalog["modules"], "Modules")
    module_ids = {module["id"] for module in modules}
    # These are links to shipped public lessons, never a request to activate them.
    from fluentloop.curriculum_b2 import CURRICULUM_LESSONS

    library_slugs = {lesson.slug for lesson in CURRICULUM_LESSONS}
    for module in modules:
        _object(
            module,
            {
                "id",
                "title_ru",
                "area",
                "strand",
                "skills",
                "language_focus",
                "adaptive_topics",
                "library_slugs",
                "outcomes",
                "tasks",
                "evidence",
                "delivery",
                "source_ids",
            },
            "Module",
        )
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", module["id"]):
            raise ValueError("Module ids must use snake_case")
        for field in ("title_ru", "area"):
            _text(module[field], f"Module {field}")
        if module["strand"] not in ("general", "work"):
            raise ValueError("Module strand must be general or work")
        if module["delivery"] not in ("mixed", "external", "brief"):
            raise ValueError("Unknown module delivery")
        _references(module["skills"], set(SKILLS), "Module skills", nonempty=True)
        _strings(module["language_focus"], "Language focus", nonempty=True)
        _references(module["adaptive_topics"], set(ADAPTIVE_TOPICS), "Adaptive topics")
        _references(module["library_slugs"], library_slugs, "Library slugs")
        _references(module["source_ids"], source_ids, "Module sources", nonempty=True)
        _strings(module["evidence"], "Evidence", nonempty=True)
        for field in ("outcomes", "tasks"):
            stages = _object(module[field], set(STAGES), f"Module {field}")
            for content in stages.values():
                _text(content, f"Module {field} stage")
    if {module["strand"] for module in modules} != {"general", "work"}:
        raise ValueError("Curriculum must retain general and workplace strands")
    tracks = _object(catalog["tracks"], set(TRACKS), "Tracks")
    for track in tracks.values():
        _object(track, {"title_ru", "module_ids"}, "Track")
        _text(track["title_ru"], "Track title")
        ids = _references(track["module_ids"], module_ids, "Track modules")
        if set(ids) != module_ids:
            raise ValueError("Every track must contain every module exactly once")
    for row in _unique_objects(catalog["language_map"], "Language map"):
        _object(
            row,
            {
                "id",
                "title_ru",
                "b2_focus",
                "c1_focus",
                "module_ids",
                "adaptive_topics",
                "coverage",
            },
            "Language map row",
        )
        for field in ("title_ru", "b2_focus", "c1_focus"):
            _text(row[field], f"Language map {field}")
        _references(
            row["module_ids"], module_ids, "Language map modules", nonempty=True
        )
        topics = _references(
            row["adaptive_topics"], set(ADAPTIVE_TOPICS), "Language map adaptive topics"
        )
        if row["coverage"] not in ("partial", "planned"):
            raise ValueError("Unknown language coverage")
        if row["coverage"] == "partial" and not topics:
            raise ValueError("Partial coverage requires existing adaptive topics")
    return deepcopy(catalog)


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def read_json(path: str | Path, *, max_bytes: int = 2 * 1024 * 1024) -> Any:
    """Read portable JSON without accepting duplicate fields or nonfinite values."""

    def reject_constant(value: str) -> None:
        raise ValueError("Nonfinite JSON number")

    with Path(path).open("rb") as handle:
        content = handle.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ValueError("JSON file exceeds the supported size")
    try:
        return json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=reject_constant,
        )
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds the supported depth") from exc


def load_curriculum(path: str | Path | None = None) -> dict[str, Any]:
    return validate_curriculum(read_json(path or CURRICULUM_PATH))


def _catalog(catalog: dict[str, Any] | None) -> dict[str, Any]:
    return load_curriculum() if catalog is None else validate_curriculum(catalog)


def default_plan(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    pack = _catalog(catalog)
    return {
        "version": 1,
        "track": "balanced",
        "weekly_minutes": 150,
        "general_share": 60,
        "order": list(pack["tracks"]["balanced"]["module_ids"]),
        "paused": [],
        "focus": None,
        "notes": {},
    }


def validate_plan(data: Any, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reject incomplete/foreign state before replacing any user's preferences."""
    pack = _catalog(catalog)
    plan = _object(data, PLAN_FIELDS, "Plan")
    _version(plan["version"], "Plan")
    if not isinstance(plan["track"], str) or plan["track"] not in TRACKS:
        raise ValueError("Unknown plan track")
    for field, low, high in (("weekly_minutes", 30, 1200), ("general_share", 20, 90)):
        if type(plan[field]) is not int or not low <= plan[field] <= high:
            raise ValueError(f"{field} must be an integer between {low} and {high}")
    module_ids = {module["id"] for module in pack["modules"]}
    order = _references(plan["order"], module_ids, "Plan order")
    if set(order) != module_ids:
        raise ValueError("Plan order must contain every module exactly once")
    paused = _references(plan["paused"], module_ids, "Paused modules")
    for strand in ("general", "work"):
        if not any(
            module["strand"] == strand and module["id"] not in paused
            for module in pack["modules"]
        ):
            raise ValueError(f"Keep at least one active {strand} module")
    focus = plan["focus"]
    if focus is not None and (
        not isinstance(focus, str) or focus not in module_ids or focus in paused
    ):
        raise ValueError("Focus must be an active module or null")
    notes = plan["notes"]
    if not isinstance(notes, dict) or set(notes) - module_ids:
        raise ValueError("Notes require known module IDs")
    for note in notes.values():
        if not isinstance(note, str) or len(note) > 1000:
            raise ValueError("Module notes must be text of at most 1000 characters")
        if any(ord(char) < 32 and char not in "\n\t\r" for char in note):
            raise ValueError("Notes contain unsupported control characters")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in note):
            raise ValueError("Notes contain invalid Unicode characters")
    return deepcopy(plan)


def get_plan(user: User, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    preferences = user.preferences_json if user.preferences_json is not None else {}
    if not isinstance(preferences, dict):
        raise ValueError("User preferences must be an object")
    if PLAN_NAMESPACE not in preferences:
        return default_plan(catalog)
    return validate_plan(preferences[PLAN_NAMESPACE], catalog)


def save_plan(
    session: Session, user: User, data: Any, catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    plan = validate_plan(data, catalog)
    preferences = deepcopy(
        user.preferences_json if user.preferences_json is not None else {}
    )
    if not isinstance(preferences, dict):
        raise ValueError("User preferences must be an object")
    preferences[PLAN_NAMESPACE] = deepcopy(plan)
    user.preferences_json = preferences
    user.updated_at = utc_now()
    session.add(user)
    session.flush()
    return plan


def update_plan(
    session: Session,
    user: User,
    action: str,
    value: Any,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pack = _catalog(catalog)
    plan = get_plan(user, pack)
    if action == "track":
        if not isinstance(value, str) or value not in TRACKS:
            raise ValueError("Unknown plan track")
        plan["track"] = value
        plan["order"] = list(pack["tracks"][value]["module_ids"])
    elif action in ("time", "general_share"):
        plan["weekly_minutes" if action == "time" else action] = value
    elif action == "focus":
        plan["focus"] = value
    elif action in ("pause", "resume"):
        if not isinstance(value, str) or value not in plan["order"]:
            raise ValueError("Unknown module")
        if action == "pause" and value not in plan["paused"]:
            plan["paused"].append(value)
            if plan["focus"] == value:
                plan["focus"] = None
        elif action == "resume" and value in plan["paused"]:
            plan["paused"].remove(value)
    else:
        raise ValueError("Unknown plan action")
    return save_plan(session, user, plan, pack)


def plan_outline(
    plan: dict[str, Any], catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Show suggested time and priorities; this read does not change evidence."""
    pack = _catalog(catalog)
    valid = validate_plan(plan, pack)
    modules = {module["id"]: module for module in pack["modules"]}
    result: dict[str, Any] = {}
    general_minutes = valid["weekly_minutes"] * valid["general_share"] // 100
    result["general_minutes"] = general_minutes
    result["work_minutes"] = valid["weekly_minutes"] - general_minutes
    for strand in ("general", "work"):
        active = [
            modules[identifier]
            for identifier in valid["order"]
            if identifier not in valid["paused"]
            and modules[identifier]["strand"] == strand
        ]
        focus = next(
            (module for module in active if module["id"] == valid["focus"]), active[0]
        )
        result[f"{strand}_focus"] = deepcopy(focus)
        result[f"next_{strand}"] = deepcopy(
            [module for module in active if module["id"] != focus["id"]][:3]
        )
    return result
