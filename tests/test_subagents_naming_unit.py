import sys; from pathlib import Path
SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path: sys.path.insert(0, str(SIDECAR))
import subagents_naming as sn


# ---------------------------------------------------------------------------
# group_letter — bijective base-26 / spreadsheet-column style
# ---------------------------------------------------------------------------

def test_group_letter_single_letters():
    assert sn.group_letter(0) == "A"
    assert sn.group_letter(25) == "Z"


def test_group_letter_double_letters():
    assert sn.group_letter(26) == "AA"
    assert sn.group_letter(27) == "AB"


def test_group_letter_wrap_boundaries():
    # AZ is the 52nd label (index 51); BA is the 53rd (index 52).
    assert sn.group_letter(51) == "AZ"
    assert sn.group_letter(52) == "BA"


def test_group_letter_full_sequence_first_28():
    expected = (
        ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
         "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
        + ["AA", "AB"]
    )
    assert [sn.group_letter(i) for i in range(28)] == expected


# ---------------------------------------------------------------------------
# assign_names — group (letter) + member (1-based) + badge
# ---------------------------------------------------------------------------

def _spawn(name):
    return {"label": name}


def test_assign_names_two_runs_badges():
    runs = [
        [_spawn("a"), _spawn("b")],  # run 0 -> group A -> members 1,2
        [_spawn("c")],               # run 1 -> group B -> member 1
    ]
    out = sn.assign_names(runs)
    assert [d["badge"] for d in out] == ["A1", "A2", "B1"]
    assert [d["group"] for d in out] == ["A", "A", "B"]
    assert [d["member"] for d in out] == [1, 2, 1]
    # flat list length == total spawns
    assert len(out) == 3


def test_assign_names_member_resets_per_run():
    runs = [
        [_spawn("a"), _spawn("b"), _spawn("c")],  # A1,A2,A3
        [_spawn("d"), _spawn("e")],               # B1,B2
    ]
    out = sn.assign_names(runs)
    assert [d["badge"] for d in out] == ["A1", "A2", "A3", "B1", "B2"]
    assert [d["member"] for d in out] == [1, 2, 3, 1, 2]


def test_assign_names_does_not_mutate_input():
    original = {"label": "coder-01"}
    runs = [[original]]
    out = sn.assign_names(runs)
    # input dict untouched
    assert original == {"label": "coder-01"}
    assert "badge" not in original and "group" not in original and "member" not in original
    # output is an augmented copy carrying the original fields
    assert out[0] is not original
    assert out[0]["label"] == "coder-01"
    assert out[0]["badge"] == "A1"


def test_assign_names_empty_runs_get_no_letter():
    # Only runs that actually contain spawns consume a letter, in order.
    runs = [
        [],                          # no spawns -> consumes no letter
        [_spawn("a"), _spawn("b")],  # first run WITH spawns -> group A
        [],                          # no spawns -> consumes no letter
        [_spawn("c")],               # second run WITH spawns -> group B
    ]
    out = sn.assign_names(runs)
    assert [d["badge"] for d in out] == ["A1", "A2", "B1"]
    assert [d["group"] for d in out] == ["A", "A", "B"]


def test_assign_names_all_empty():
    assert sn.assign_names([[], [], []]) == []


def test_assign_names_no_runs():
    assert sn.assign_names([]) == []


def test_assign_names_27_groups_exercises_AA():
    # 27 runs, each with a single spawn -> groups A..Z then AA on the 27th.
    runs = [[_spawn(f"s{i}")] for i in range(27)]
    out = sn.assign_names(runs)
    assert out[0]["group"] == "A"
    assert out[25]["group"] == "Z"
    assert out[26]["group"] == "AA"
    assert out[26]["badge"] == "AA1"
    assert [d["member"] for d in out] == [1] * 27


# ---------------------------------------------------------------------------
# sender_form — parent_label › badge (U+203A single right-angle quote)
# ---------------------------------------------------------------------------

def test_sender_form_format():
    assert sn.sender_form("coder-01", "A2") == "coder-01 › A2"


def test_sender_form_uses_single_right_angle_quote():
    result = sn.sender_form("parent", "B1")
    assert "›" in result
    assert result == "parent › B1"
