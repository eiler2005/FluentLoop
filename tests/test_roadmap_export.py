"""Publication checks for the offline plan and its public task map."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from fluentloop.roadmap_export import render_roadmap_html, render_roadmap_markdown
from fluentloop.workplace_roadmap import default_plan, load_curriculum, validate_plan

ROOT = Path(__file__).resolve().parents[1]


def _embedded(html, name):
    match = re.search(
        rf'<script id="{name}" type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert match
    return json.loads(match.group(1))


def test_committed_views_match_validated_source_and_renderer():
    catalog = load_curriculum()
    directory = ROOT / "docs" / "curriculum"
    assert (directory / "workplace-roadmap.md").read_text() == (
        render_roadmap_markdown(catalog)
    )
    assert (directory / "workplace-planner.html").read_text() == (
        render_roadmap_html(catalog)
    )
    published_plan = json.loads((directory / "client-work-plan.json").read_text())
    assert validate_plan(published_plan, catalog) == default_plan(catalog)
    assert published_plan["notes"] == {}


def test_editor_embeds_portable_default_without_network_or_answer_keys():
    catalog = load_curriculum()
    html = render_roadmap_html(catalog)
    embedded = _embedded(html, "catalog-data")
    plan = _embedded(html, "default-data")
    assert embedded == catalog
    assert validate_plan(plan, embedded) == default_plan(catalog)
    assert plan["general_share"] == 30
    assert plan["track"] == "client_facing"
    assert "<script src=" not in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "correct_index" not in html
    assert "transfer_eligible" not in html
    assert "innerHTML" not in html


def test_embedded_source_cannot_break_out_of_json_script_element():
    catalog = deepcopy(load_curriculum())
    hostile = '</script><script>alert("unsafe")</script> & <img src=x>'
    catalog["title_ru"] = hostile
    catalog["modules"][0]["tasks"]["b2"] = hostile
    html = render_roadmap_html(catalog)
    assert hostile not in html
    assert _embedded(html, "catalog-data")["modules"][0]["tasks"]["b2"] == hostile
    assert html.count("<script") == 3


def test_every_module_stage_and_coverage_gap_is_published():
    catalog = load_curriculum()
    markdown = render_roadmap_markdown(catalog)
    for module in catalog["modules"]:
        assert f'<a id="{module["id"]}"></a>' in markdown
        for task in module["tasks"].values():
            assert task in markdown
    for row in catalog["language_map"]:
        assert row["title_ru"] in markdown
        assert row["b2_focus"] in markdown
    assert "управляет подбором /study" in markdown
    assert "Общий английский — основа" in markdown
