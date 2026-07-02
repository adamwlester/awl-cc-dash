"""Hermetic unit tests for ``sidecar/templates_store.py`` (Templates).

The store persists to the templates JSON inside the **dashboard runtime store**
(reusable / project-agnostic). These tests redirect that store to a
``tmp_path`` via ``AWL_SIDECAR_RUNTIME`` so they never touch the real dashboard
store, and exercise the public API end-to-end through a real JSON file on disk.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import templates_store  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the dashboard runtime store at a fresh tmp dir for each test.

    The module must resolve the store path at call-time so this override
    applies; we set the env var before any store call is made.
    """
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path))
    # Sanity: the file should not exist yet (clean slate per test).
    templates_store.reset()
    return tmp_path


# ---------------------------------------------------------------------------
# add / list / get round-trips through a real JSON file
# ---------------------------------------------------------------------------

def test_add_then_list_and_get_round_trip(store):
    created = templates_store.add_template("Greeting", "Hello {{name}}!")

    assert created["name"] == "Greeting"
    assert created["body"] == "Hello {{name}}!"
    assert created["placeholders"] == ["name"]
    assert created["id"]
    assert created["created_at"]

    listed = templates_store.list_templates()
    assert listed == [created]

    fetched = templates_store.get_template(created["id"])
    assert fetched == created


def test_add_persists_to_real_json_file(store):
    created = templates_store.add_template("Persisted", "Body {{x}}")

    path = store / "templates.json"
    assert path.exists(), "add_template must write the templates JSON to disk"

    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["id"] == created["id"]
    assert data[0]["name"] == "Persisted"


def test_ids_are_unique_across_adds(store):
    a = templates_store.add_template("A", "alpha")
    b = templates_store.add_template("B", "beta")
    assert a["id"] != b["id"]
    ids = {t["id"] for t in templates_store.list_templates()}
    assert ids == {a["id"], b["id"]}


# ---------------------------------------------------------------------------
# placeholder auto-extraction
# ---------------------------------------------------------------------------

def test_placeholder_auto_extraction_unique_and_ordered(store):
    created = templates_store.add_template(
        "Extract", "{{a}} ... {{b}} ... {{a}}"
    )
    assert created["placeholders"] == ["a", "b"]


def test_placeholders_explicit_override_skips_extraction(store):
    created = templates_store.add_template(
        "Explicit", "{{a}} {{b}}", placeholders=["custom"]
    )
    assert created["placeholders"] == ["custom"]


def test_placeholder_extraction_empty_when_none(store):
    created = templates_store.add_template("Plain", "no tokens here")
    assert created["placeholders"] == []


# ---------------------------------------------------------------------------
# update — partial merge + re-extraction on body change
# ---------------------------------------------------------------------------

def test_update_merges_name_only(store):
    created = templates_store.add_template("Old", "Body {{x}}")
    updated = templates_store.update_template(created["id"], name="New")

    assert updated is not None
    assert updated["name"] == "New"
    assert updated["body"] == "Body {{x}}"
    assert updated["placeholders"] == ["x"]
    assert updated["id"] == created["id"]

    # Persisted, not just returned.
    assert templates_store.get_template(created["id"]) == updated


def test_update_reextracts_placeholders_on_body_change(store):
    created = templates_store.add_template("T", "Hello {{name}}")
    updated = templates_store.update_template(
        created["id"], body="Hi {{first}} {{last}}"
    )
    assert updated is not None
    assert updated["body"] == "Hi {{first}} {{last}}"
    assert updated["placeholders"] == ["first", "last"]


def test_update_body_with_explicit_placeholders_does_not_reextract(store):
    created = templates_store.add_template("T", "Hello {{name}}")
    updated = templates_store.update_template(
        created["id"], body="Hi {{a}} {{b}}", placeholders=["only"]
    )
    assert updated is not None
    assert updated["placeholders"] == ["only"]


def test_update_missing_returns_none(store):
    assert templates_store.update_template("does-not-exist", name="x") is None


# ---------------------------------------------------------------------------
# render — fills provided values, leaves unfilled tokens intact
# ---------------------------------------------------------------------------

def test_render_fills_and_leaves_unfilled_intact(store):
    created = templates_store.add_template(
        "R", "Hi {{name}}, your code is {{code}}."
    )
    rendered = templates_store.render_template(created["id"], {"name": "Sam"})
    assert rendered == "Hi Sam, your code is {{code}}."


def test_render_fills_all_when_all_provided(store):
    created = templates_store.add_template("R", "{{a}}-{{b}}")
    rendered = templates_store.render_template(
        created["id"], {"a": "1", "b": "2"}
    )
    assert rendered == "1-2"


def test_render_missing_template_returns_none(store):
    assert templates_store.render_template("nope", {"a": "1"}) is None


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

def test_remove_existing_returns_true_and_drops_it(store):
    created = templates_store.add_template("Doomed", "bye")
    assert templates_store.remove_template(created["id"]) is True
    assert templates_store.get_template(created["id"]) is None
    assert templates_store.list_templates() == []


def test_remove_missing_returns_false(store):
    assert templates_store.remove_template("ghost") is False


# ---------------------------------------------------------------------------
# missing file / reset
# ---------------------------------------------------------------------------

def test_list_on_missing_file_returns_empty(store):
    # reset() in the fixture removed any file; nothing has been written.
    assert not (store / "templates.json").exists()
    assert templates_store.list_templates() == []


def test_reset_clears_the_store(store):
    templates_store.add_template("A", "alpha")
    templates_store.add_template("B", "beta")
    assert (store / "templates.json").exists()

    templates_store.reset()

    assert not (store / "templates.json").exists()
    assert templates_store.list_templates() == []
