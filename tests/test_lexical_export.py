from collections import Counter
from copy import deepcopy
from pathlib import Path

from fluentloop.lexical_export import html_bank, public_views
from fluentloop.lexical_learning import load_lexicon


def test_reviewed_bank_and_public_catalog_are_complete_and_current():
    bank = load_lexicon()
    assert len(bank["entries"]) == 240
    assert len(bank["functions"]) == 16
    assert Counter(e["strand"] for e in bank["entries"]) == {"work": 180, "general": 60}
    assert sum(e["stage"] == "c1_intro" for e in bank["entries"]) == 20
    assert sum(len(e["questions"]) for e in bank["entries"]) == 480
    assert sum(len(e["production_prompts"]) for e in bank["entries"]) == 480
    directory = Path(__file__).resolve().parents[1] / "docs" / "curriculum"
    for name, content in public_views(bank).items():
        assert (directory / name).read_text(encoding="utf-8") == content


def test_public_lexical_html_escapes_content_and_has_no_network_dependency():
    bank = deepcopy(load_lexicon())
    hostile = '<script>alert("unsafe")</script>'
    bank["entries"][0]["example"] = hostile
    html = html_bank(bank)
    assert hostile not in html
    assert "&lt;script&gt;" in html
    assert "fetch(" not in html
    assert "<script src=" not in html
    assert "innerHTML" not in html
