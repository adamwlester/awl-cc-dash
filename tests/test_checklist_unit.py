"""Hermetic unit tests for the OD-11 run-strip completion parser
(`sidecar/checklist.py`). Pure-logic: no live agents, no I/O.

OD-11 decision (authoritative): the agent publishes a short ordered checklist of
major operations up front and marks each done as it goes; the sidecar reads the
checklist from the agent's transcript text and renders done / total as a
segmented bar. The CURRENT in-progress item (first not-done) labels the bar.
FLOOR: any run that publishes NO checklist shows the honest barber-pole
indeterminate state — never a fabricated %.

Minimum-items rule (documented + tested below):
A "checklist" is a CONTIGUOUS run of >= 1 checklist-item line(s), BUT a single
lone item only counts when it stands alone as its own block (i.e. it is NOT
embedded in surrounding prose on adjacent lines). Concretely: a 1-item block is
accepted only if neither the line directly above nor directly below it is a
non-blank prose line. A run of >= 2 contiguous item lines is always a checklist.
This lets a deliberate single-step checklist render while a stray "[ ]" written
inside a paragraph does not false-fire. See test_single_stray_checkbox_in_prose
and test_single_item_standalone_checklist.
"""
import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import checklist  # noqa: E402


# --- the barber-pole floor -------------------------------------------------

def test_no_checklist_is_indeterminate():
    res = checklist.parse_checklist([
        "Just some prose with no checklist at all.",
        "Working on the thing now, almost there.",
    ])
    assert res == {
        "total": 0,
        "done": 0,
        "items": [],
        "current": None,
        "indeterminate": True,
        "fraction": 0.0,
    }


def test_empty_texts_is_indeterminate():
    assert checklist.parse_checklist([]) == checklist.barber_pole()


def test_barber_pole_sentinel_shape():
    bp = checklist.barber_pole()
    assert bp == {
        "total": 0,
        "done": 0,
        "items": [],
        "current": None,
        "indeterminate": True,
        "fraction": 0.0,
    }
    # must be a fresh dict each call (no shared mutable state)
    bp["items"].append("x")
    assert checklist.barber_pole()["items"] == []


# --- a fresh checklist, all undone -----------------------------------------

def test_fresh_checklist_all_undone():
    text = (
        "Here is my plan:\n"
        "- [ ] Read the config\n"
        "- [ ] Patch the module\n"
        "- [ ] Run the tests\n"
    )
    res = checklist.parse_checklist([text])
    assert res["indeterminate"] is False
    assert res["total"] == 3
    assert res["done"] == 0
    assert res["fraction"] == 0.0
    assert res["current"] == "Read the config"
    assert res["items"] == [
        {"text": "Read the config", "done": False},
        {"text": "Patch the module", "done": False},
        {"text": "Run the tests", "done": False},
    ]


# --- some done -------------------------------------------------------------

def test_some_done_current_is_first_undone():
    text = (
        "- [x] Read the config\n"
        "- [x] Patch the module\n"
        "- [ ] Run the tests\n"
        "- [ ] Ship it\n"
    )
    res = checklist.parse_checklist([text])
    assert res["total"] == 4
    assert res["done"] == 2
    assert res["fraction"] == pytest.approx(0.5)
    assert res["current"] == "Run the tests"
    assert res["indeterminate"] is False


# --- all done --------------------------------------------------------------

def test_all_done_current_none_fraction_one():
    text = (
        "- [x] Read the config\n"
        "- [x] Patch the module\n"
        "- [x] Run the tests\n"
    )
    res = checklist.parse_checklist([text])
    assert res["total"] == 3
    assert res["done"] == 3
    assert res["fraction"] == pytest.approx(1.0)
    assert res["current"] is None
    assert res["indeterminate"] is False


# --- numbered-list form ----------------------------------------------------

def test_numbered_list_form():
    text = (
        "1. [x] First step\n"
        "2. [ ] Second step\n"
        "3. [ ] Third step\n"
    )
    res = checklist.parse_checklist([text])
    assert res["total"] == 3
    assert res["done"] == 1
    assert res["current"] == "Second step"
    assert [i["text"] for i in res["items"]] == [
        "First step", "Second step", "Third step",
    ]


def test_star_bullet_form():
    text = (
        "* [ ] alpha\n"
        "* [x] beta\n"
    )
    res = checklist.parse_checklist([text])
    assert res["total"] == 2
    assert res["done"] == 1
    assert res["current"] == "alpha"


# --- done-marker variants --------------------------------------------------

def test_capital_x_and_lowercase_x_both_count_done():
    text = (
        "- [X] upper marks done\n"
        "- [x] lower marks done\n"
        "- [ ] this one isn't\n"
    )
    res = checklist.parse_checklist([text])
    assert res["done"] == 2
    assert res["total"] == 3
    assert [i["done"] for i in res["items"]] == [True, True, False]
    assert res["current"] == "this one isn't"


def test_checkmark_glyph_counts_done():
    text = (
        "- [✓] done via checkmark\n"
        "- [ ] not done\n"
    )
    res = checklist.parse_checklist([text])
    assert res["items"][0]["done"] is True
    assert res["done"] == 1
    assert res["current"] == "not done"


# --- re-publish: latest block wins, denominator can grow -------------------

def test_republished_checklist_uses_latest_done_advances():
    first = (
        "- [ ] step one\n"
        "- [ ] step two\n"
        "- [ ] step three\n"
    )
    later = (
        "- [x] step one\n"
        "- [x] step two\n"
        "- [ ] step three\n"
    )
    res = checklist.parse_checklist([first, later])
    assert res["total"] == 3
    assert res["done"] == 2
    assert res["current"] == "step three"


def test_republished_denominator_can_grow():
    first = (
        "- [x] step one\n"
        "- [x] step two\n"
        "- [ ] step three\n"
    )
    later = (
        "- [x] step one\n"
        "- [x] step two\n"
        "- [x] step three\n"
        "- [ ] step four (added mid-run)\n"
        "- [ ] step five (added mid-run)\n"
    )
    res = checklist.parse_checklist([first, later])
    assert res["total"] == 5            # denominator grew 3 -> 5
    assert res["done"] == 3
    assert res["current"] == "step four (added mid-run)"
    assert res["fraction"] == pytest.approx(3 / 5)


def test_latest_block_within_a_single_text_wins():
    # Two separate checklist blocks in ONE text -> the LATEST (lowest) wins.
    text = (
        "Old plan:\n"
        "- [x] a\n"
        "- [x] b\n"
        "\n"
        "Revised plan:\n"
        "- [ ] x\n"
        "- [ ] y\n"
        "- [ ] z\n"
    )
    res = checklist.parse_checklist([text])
    assert res["total"] == 3
    assert res["done"] == 0
    assert res["current"] == "x"


# --- minimum-items rule ----------------------------------------------------

def test_single_stray_checkbox_in_prose_does_not_fire():
    # A lone "[ ]" embedded in a paragraph (prose directly above AND below)
    # must NOT be read as a checklist -> barber-pole floor.
    text = (
        "I considered whether to mark this as - [ ] pending in the doc,\n"
        "but decided the wording should stay as a normal sentence here.\n"
    )
    res = checklist.parse_checklist([text])
    assert res["indeterminate"] is True
    assert res["total"] == 0


def test_single_item_standalone_checklist_fires():
    # A single item that stands alone as its own block (blank lines / nothing
    # adjacent) IS a one-step checklist.
    text = (
        "Plan:\n"
        "\n"
        "- [ ] do the one big thing\n"
        "\n"
        "I'll report back when it's done.\n"
    )
    res = checklist.parse_checklist([text])
    assert res["indeterminate"] is False
    assert res["total"] == 1
    assert res["done"] == 0
    assert res["current"] == "do the one big thing"


def test_two_contiguous_items_always_fire_even_amid_prose():
    text = (
        "blah blah blah\n"
        "- [ ] one\n"
        "- [x] two\n"
        "more prose follows\n"
    )
    res = checklist.parse_checklist([text])
    assert res["indeterminate"] is False
    assert res["total"] == 2
    assert res["done"] == 1


# --- misc robustness -------------------------------------------------------

def test_leading_whitespace_indented_items():
    text = (
        "Plan:\n"
        "    - [ ] indented one\n"
        "    - [x] indented two\n"
    )
    res = checklist.parse_checklist([text])
    assert res["total"] == 2
    assert res["done"] == 1
    assert res["current"] == "indented one"


def test_item_text_is_stripped():
    text = (
        "- [ ]    spaced out text   \n"
        "- [ ] tidy\n"
    )
    res = checklist.parse_checklist([text])
    assert res["items"][0]["text"] == "spaced out text"


def test_fraction_zero_when_total_zero():
    res = checklist.parse_checklist(["nothing here"])
    assert res["fraction"] == 0.0
