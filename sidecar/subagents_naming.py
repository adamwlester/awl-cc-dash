"""Subagent GROUP+MEMBER naming (pure logic).

Replaces the flat monotonic ``s1..sN`` scheme with a group+member naming:

* A **GROUP** is a parent RUN that spawned subagents. Groups are lettered in
  occurrence order — A, B, C, … past Z into AA, AB, … (bijective base-26 /
  spreadsheet-column style).
* A **MEMBER** is the spawn order *within* that run — 1, 2, 3, …

The badge shown in the UI is ``f"{group}{member}"`` (e.g. ``"A2"``) — there is
NO ``s`` prefix anywhere. The full sender form is ``"coder-01 › A2"`` using a
U+203A single right-angle quote as the separator.

This module is intentionally **pure**: it takes runs that have ALREADY been
segmented (by the caller, at parent-transcript user-prompt / turn boundaries)
and assigns names. It performs no I/O and touches no servers, tmux, or bridge.

It also owns :func:`blend_live` — the §7.17 blend of the hook-fed subagent
registry over the transcript-derived rows (running-pair matching, hook-only
leftover policy) that ``GET /sessions/{id}/subagents`` serves.
"""

from __future__ import annotations

# U+203A SINGLE RIGHT-POINTING ANGLE QUOTATION MARK — the sender-form separator.
SENDER_SEP = "›"


def group_letter(index: int) -> str:
    """Return the spreadsheet-column-style letter for a 0-based ``index``.

    0 -> "A", 25 -> "Z", 26 -> "AA", 27 -> "AB", 51 -> "AZ", 52 -> "BA", …

    This is a *bijective* base-26 numbering: there is no zero digit, so "Z" is
    followed by "AA" (not "BA").
    """
    if index < 0:
        raise ValueError(f"group index must be non-negative, got {index}")
    letters = []
    n = index + 1  # shift to 1-based for bijective base-26
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(ord("A") + rem))
    return "".join(reversed(letters))


def assign_names(runs: list[list[dict]]) -> list[dict]:
    """Assign group letters + member numbers to already-segmented ``runs``.

    ``runs`` is a list of runs in occurrence order; each run is a list of
    subagent-spawn dicts in spawn order.

    Returns a FLAT list of the spawns (occurrence order across runs, spawn
    order within each run). Each returned dict is a shallow **copy** of the
    input augmented with:

    * ``"group"``  — the letter for its run
    * ``"member"`` — 1-based position within its run
    * ``"badge"``  — ``f"{group}{member}"`` (e.g. ``"A2"``)

    Input dicts are never mutated. Only runs that actually contain spawns
    consume a letter: a run's letter is its index *among runs that have
    spawns*, in order (empty runs are skipped and consume no letter).
    """
    result: list[dict] = []
    group_index = 0  # advances only for runs that contain spawns
    for run in runs:
        if not run:
            continue
        letter = group_letter(group_index)
        for member, spawn in enumerate(run, start=1):
            augmented = dict(spawn)  # copy — never mutate the input
            augmented["group"] = letter
            augmented["member"] = member
            augmented["badge"] = f"{letter}{member}"
            result.append(augmented)
        group_index += 1
    return result


def sender_form(parent_label: str, badge: str) -> str:
    """Return the full sender form, e.g. ``"coder-01 › A2"``.

    The separator is a U+203A single right-angle quote.
    """
    return f"{parent_label} {SENDER_SEP} {badge}"


# ---------------------------------------------------------------------------
# The §7.17 blend — transcript spawn rows × hook-registry records (pure)
# ---------------------------------------------------------------------------

def _same_engine_id(a, b) -> bool:
    """Exact or prefix match between two engine agent ids (a transcript result
    can carry a truncated form of the hook payload's id, or vice versa)."""
    if not a or not b:
        return False
    a, b = str(a), str(b)
    return a == b or (len(a) >= 8 and b.startswith(a)) \
        or (len(b) >= 8 and a.startswith(b))


def blend_live(subagents: list[dict], live: list[dict]) -> list[dict]:
    """Blend hook-registry records over the transcript-derived subagent rows.

    The §7.17 server-side blend (supersedes the renderer's ``normalizeSubs``
    client repair). The transcript records a spawn immediately but only mints
    the subagent's engine ``agentId`` when its RESULT lands — so matching by
    id alone double-counts every RUNNING subagent ({id: null} hook extra
    beside its own spawn row), and the engine's internal helper agents fire
    the same SubagentStart/Stop hooks without ever gaining a transcript row.
    Rules, in order, per hook record:

    1. **Exact/prefix engine-id match** to an unclaimed row → merge (the
       hook's ``live_status``/``transcript_path`` are authoritative; ``type``
       fills only a missing value).
    2. A **running** hook record with no id-match belongs to a transcript
       spawn whose result hasn't landed yet → pair IN ORDER with the first
       unclaimed *running* row that has no engine id (adopting the hook's
       ``agent_id``).
    3. A **stopped** hook record whose result never carried an agentId →
       pair with the first unclaimed *finished* id-less row.
    4. **Leftovers**: still-``running`` hook records are real live activity
       the transcript hasn't caught up with — appended with an honest display
       id minted from the engine id; **stopped** leftovers never gained a
       transcript row (internal helper agents, verified live 2026-07-16) and
       are dropped — keeping them would inflate the roster forever.

    Pure — inputs are never mutated; returns a new list.
    """
    out = [dict(s) for s in subagents]
    claimed: set[int] = set()

    def _claim(idx: int, rec: dict) -> None:
        claimed.add(idx)
        row = out[idx]
        row["agent_id"] = row.get("agent_id") or rec.get("agent_id")
        if rec.get("type") and not row.get("type"):
            row["type"] = rec["type"]
        row["live_status"] = rec.get("status")
        if rec.get("transcript_path"):
            row["transcript_path"] = rec["transcript_path"]

    leftovers: list[dict] = []
    for rec in live:
        idx = next((i for i, s in enumerate(out)
                    if i not in claimed
                    and _same_engine_id(s.get("agent_id"), rec.get("agent_id"))),
                   -1)
        if idx < 0 and rec.get("status") == "running":
            idx = next((i for i, s in enumerate(out)
                        if i not in claimed and not s.get("agent_id")
                        and s.get("status") == "running"), -1)
        elif idx < 0:
            idx = next((i for i, s in enumerate(out)
                        if i not in claimed and not s.get("agent_id")
                        and s.get("status") != "running"), -1)
        if idx >= 0:
            _claim(idx, rec)
        else:
            leftovers.append(rec)

    n = 0
    for rec in leftovers:
        if rec.get("status") != "running":
            continue  # hook-only + already stopped = internal helper — drop
        n += 1
        aid = rec.get("agent_id")
        out.append({
            "id": str(aid)[:5] if aid else f"h{n}",
            "tool_use_id": None,
            "agent_id": aid,
            "type": rec.get("type"),
            "description": None,
            "prompt": None,
            "status": "running",
            "live_status": rec.get("status"),
            "transcript_path": rec.get("transcript_path"),
            "usage": None,
        })
    return out
