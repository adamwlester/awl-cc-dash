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


# ---------------------------------------------------------------------------
# blend_live — the §7.17 server-side blend of hook-registry records over the
# transcript-derived rows (supersedes the renderer's normalizeSubs repair).
# The decided contract: a RUNNING subagent must never arrive twice ({id: null}
# hook extra beside its own spawn row — hook records only carry the engine
# agentId the transcript mints at COMPLETION), and the engine's internal
# helper agents (hook records that never gain a transcript row) must not
# inflate the roster after they stop.
# ---------------------------------------------------------------------------

def _row(id_, *, agent_id=None, status="running", type_=None):
    return {"id": id_, "tool_use_id": f"tu-{id_}", "agent_id": agent_id,
            "type": type_, "description": None, "prompt": None,
            "status": status, "usage": None}


def _hook(agent_id, *, status="running", type_=None, transcript=None):
    return {"agent_id": agent_id, "type": type_, "status": status,
            "transcript_path": transcript, "started_at": 1.0,
            "stopped_at": None, "last_assistant_message": None}


def test_blend_running_hook_pairs_in_order_not_duplicated():
    # The live-caught duplicate: s1 running (no agentId yet) + its own hook
    # record — must merge into ONE row carrying the engine id + live status.
    rows = [_row("s1")]
    out = sn.blend_live(rows, [_hook("a09f42deadbeef", transcript="/t/sub.jsonl")])
    assert len(out) == 1
    assert out[0]["id"] == "s1"
    assert out[0]["agent_id"] == "a09f42deadbeef"
    assert out[0]["live_status"] == "running"
    assert out[0]["transcript_path"] == "/t/sub.jsonl"


def test_blend_exact_id_match_merges_finished_row():
    rows = [_row("s1", agent_id="agent-xyz", status="done")]
    out = sn.blend_live(rows, [_hook("agent-xyz", status="stopped")])
    assert len(out) == 1
    assert out[0]["live_status"] == "stopped"


def test_blend_prefix_id_match_merges():
    # A transcript result can carry a truncated form of the hook's id.
    rows = [_row("s1", agent_id="abcdef1234", status="done")]
    out = sn.blend_live(rows, [_hook("abcdef1234567890", status="stopped")])
    assert len(out) == 1 and out[0]["live_status"] == "stopped"


def test_blend_stopped_hook_only_records_are_dropped():
    # Internal helper agents: hook records with NO transcript row, already
    # stopped (verified live 2026-07-16: 4 such beside 2 real spawns).
    rows = [_row("s1", agent_id="real-1", status="done"),
            _row("s2", agent_id="real-2", status="done")]
    live = [_hook("real-1", status="stopped"), _hook("real-2", status="stopped"),
            _hook("helper-1", status="stopped"), _hook("helper-2", status="stopped"),
            _hook("helper-3", status="stopped"), _hook("helper-4", status="stopped")]
    out = sn.blend_live(rows, live)
    assert len(out) == 2
    assert {r["agent_id"] for r in out} == {"real-1", "real-2"}


def test_blend_running_leftover_kept_with_minted_id():
    # A still-running hook record the transcript hasn't caught up with is real
    # live activity — kept, with an honest display id off the engine id.
    out = sn.blend_live([], [_hook("a09f42deadbeef")])
    assert len(out) == 1
    assert out[0]["id"] == "a09f4"
    assert out[0]["status"] == "running" and out[0]["live_status"] == "running"


def test_blend_stopped_hook_pairs_with_finished_idless_row():
    # A result that never carried an agentId: the stopped hook record pairs
    # with the unclaimed finished spawn instead of appending.
    rows = [_row("s1", status="done")]
    out = sn.blend_live(rows, [_hook("eng-1", status="stopped")])
    assert len(out) == 1
    assert out[0]["agent_id"] == "eng-1" and out[0]["live_status"] == "stopped"


def test_blend_two_running_pair_in_spawn_order():
    rows = [_row("s1"), _row("s2")]
    out = sn.blend_live(rows, [_hook("first-eng"), _hook("second-eng")])
    assert [r["agent_id"] for r in out] == ["first-eng", "second-eng"]
    assert len(out) == 2


def test_blend_pure_inputs_untouched():
    rows = [_row("s1")]
    live = [_hook("eng-9")]
    rows_copy = [dict(r) for r in rows]
    sn.blend_live(rows, live)
    assert rows == rows_copy


def test_blend_no_hooks_is_identity():
    rows = [_row("s1", agent_id="x", status="done")]
    assert sn.blend_live(rows, []) == rows
