import sys; from pathlib import Path
SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path: sys.path.insert(0, str(SIDECAR))
import watermark

import pytest


@pytest.fixture(autouse=True)
def _clean():
    """Each test starts with a cleared store."""
    watermark.reset()
    yield
    watermark.reset()


def test_get_default_is_zero():
    assert watermark.get("scratch:a") == 0


def test_first_delta_returns_all_and_advances():
    items = [(1, "p1"), (2, "p2"), (3, "p3")]
    assert watermark.delta("scratch:a", items) == ["p1", "p2", "p3"]
    assert watermark.get("scratch:a") == 3


def test_second_delta_returns_only_new_and_advances():
    watermark.delta("scratch:a", [(1, "p1"), (2, "p2"), (3, "p3")])
    items = [(1, "p1"), (2, "p2"), (3, "p3"), (4, "p4")]
    assert watermark.delta("scratch:a", items) == ["p4"]
    assert watermark.get("scratch:a") == 4


def test_redelta_with_same_items_returns_empty():
    items = [(1, "p1"), (2, "p2"), (3, "p3")]
    assert watermark.delta("scratch:a", items) == ["p1", "p2", "p3"]
    assert watermark.delta("scratch:a", items) == []
    assert watermark.get("scratch:a") == 3


def test_delta_advances_to_max_seq_not_just_returned():
    # Prime the watermark to 5 via set, then feed items whose max seq (4) is
    # below the watermark: nothing returned, but the watermark must advance to
    # the max seq present in items? No — spec: advance to max seq PRESENT in
    # items. Here max present is 4, which is < current 5. Advancing to a lower
    # value would be wrong; verify max() semantics don't regress the pointer.
    watermark.set("scratch:a", 5)
    assert watermark.delta("scratch:a", [(3, "p3"), (4, "p4")]) == []
    # Re-query same items still returns nothing.
    assert watermark.delta("scratch:a", [(3, "p3"), (4, "p4")]) == []


def test_delta_advances_to_max_seq_even_when_unordered():
    # Max seq present drives advancement, regardless of input order / gaps.
    items = [(2, "p2"), (5, "p5"), (3, "p3")]
    assert watermark.delta("scratch:a", items) == ["p2", "p5", "p3"]
    assert watermark.get("scratch:a") == 5


def test_delta_preserves_input_order():
    items = [(3, "p3"), (1, "p1"), (2, "p2")]
    assert watermark.delta("scratch:a", items) == ["p3", "p1", "p2"]


def test_delta_with_gaps():
    items = [(1, "p1"), (5, "p5"), (9, "p9")]
    assert watermark.delta("scratch:a", items) == ["p1", "p5", "p9"]
    assert watermark.get("scratch:a") == 9


def test_keys_are_independent():
    watermark.delta("scratch:a", [(1, "a1"), (2, "a2")])
    assert watermark.get("scratch:a") == 2
    assert watermark.get("shared:x:y") == 0
    assert watermark.delta("shared:x:y", [(1, "b1")]) == ["b1"]
    assert watermark.get("shared:x:y") == 1
    # a untouched by b's activity
    assert watermark.get("scratch:a") == 2


def test_peek_returns_new_without_advancing():
    items = [(1, "p1"), (2, "p2"), (3, "p3")]
    assert watermark.peek("scratch:a", items) == ["p1", "p2", "p3"]
    assert watermark.get("scratch:a") == 0
    # peek repeatable
    assert watermark.peek("scratch:a", items) == ["p1", "p2", "p3"]
    assert watermark.get("scratch:a") == 0


def test_peek_after_delta_shows_only_new():
    watermark.delta("scratch:a", [(1, "p1"), (2, "p2")])
    assert watermark.peek("scratch:a", [(1, "p1"), (2, "p2"), (3, "p3")]) == ["p3"]
    assert watermark.get("scratch:a") == 2


def test_empty_items_delta_is_noop():
    watermark.set("scratch:a", 7)
    assert watermark.delta("scratch:a", []) == []
    assert watermark.get("scratch:a") == 7


def test_empty_items_delta_noop_on_fresh_key():
    assert watermark.delta("scratch:a", []) == []
    assert watermark.get("scratch:a") == 0


def test_empty_items_peek_is_empty():
    watermark.set("scratch:a", 7)
    assert watermark.peek("scratch:a", []) == []
    assert watermark.get("scratch:a") == 7


def test_set_overrides():
    watermark.set("scratch:a", 10)
    assert watermark.get("scratch:a") == 10
    assert watermark.delta("scratch:a", [(5, "p5"), (10, "p10")]) == []
    watermark.set("scratch:a", 4)
    assert watermark.get("scratch:a") == 4
    assert watermark.delta("scratch:a", [(5, "p5"), (10, "p10")]) == ["p5", "p10"]


def test_reset_clears_all():
    watermark.delta("scratch:a", [(1, "p1")])
    watermark.set("shared:x:y", 99)
    watermark.reset()
    assert watermark.get("scratch:a") == 0
    assert watermark.get("shared:x:y") == 0


def test_payload_can_be_arbitrary_object():
    obj = {"nested": [1, 2]}
    items = [(1, obj), (2, None), (3, 42)]
    assert watermark.delta("scratch:a", items) == [obj, None, 42]
    assert watermark.get("scratch:a") == 3
