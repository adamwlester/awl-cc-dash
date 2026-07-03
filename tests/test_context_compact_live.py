r"""Live spike — Context breakdown (`/context`) & Compact-boundary marking (`/compact`).

§10 item #9 ("Context breakdown & Compact controls" — 🧪 needs-spike). Probes TWO
independent levers, each with its own machine-read-back, WITHOUT re-testing the
already-unit-proven total-usage + turn derivation (`derive_context_usage`).

LIVE FINDINGS (Claude Code 2.1.198, this run — both levers came back WORKS, stronger
than the research's "dead-end" prediction):

  * Lever A — per-category breakdown via `/context`. WORKS. At an idle boundary,
    `send("/context")` renders the per-category split to the screen AND records it into
    the JSONL transcript. The screen rows parse cleanly into stable labeled values, e.g.
        System prompt: 9k tokens (0.9%)   System tools: 21.9k (2.3%)   Skills: 2.1k (0.2%)
        Messages: 4.4k (0.5%)   Free space: 896.6k (92.7%)   Autocompact buffer: 33k (3.4%)
    Bonus discovery: `/context`'s output is ALSO written into the transcript as a clean
    markdown table (a local-command `user` entry — "## Context Usage … | System prompt |
    9k | 0.9% |"), a steadier read-back than raw screen-scrape. Caveat (matches research
    Q4 items 3-4): it is a point-in-time, idle-gated snapshot triggered by `/context`,
    NOT a passive live feed — so it is an on-demand pull, not a continuous signal.

  * Lever B — compaction marking via `compact_boundary`. WORKS. A real `/compact` writes a
    `type:"system" subtype:"compact_boundary"` entry (`content:"Conversation compacted"`)
    carrying rich `compactMetadata`:
        trigger("manual"|"auto") · preTokens · postTokens · durationMs ·
        cumulativeDroppedTokens · preservedSegment · preservedMessages
    plus a companion `user` entry flagged `isCompactSummary:true`. So the DESIGN
    compaction history (count = #boundaries, type = trigger, when = timestamp, + pre/post
    tokens) IS derivable from JSONL. Threshold gotcha: `/compact` refuses a near-empty
    context ("Not enough messages to compact.") — it needs ~3 conversational rounds; the
    fixture primes enough, and Lever B retries with extra rounds if it is ever refused.

Read-back is the crux: sending the slash command is trivial; proving the RESULT is
machine-readable is the whole test. The already-proven total-usage number is the
*fallback*, never a substitute for either observable here.

Run (ONLY this file, in isolation — never the whole live tier)::

    .\.venv\Scripts\python.exe -m pytest tests\test_context_compact_live.py -m integration

=============================================================================
ISOLATION RULES (parallel-safe — CRITICAL; reproduced from the build prompt):
  * ONE new file only — tests/test_context_compact_live.py. Do not add/modify any
    other test file.
  * Uniquely-named tmux session — prefix with the slug: `ctxcompact-<uuid8>`. Never a
    fixed/shared name.
  * NEVER call `tmux kill-server` in teardown (it kills sibling agents' sessions).
  * Do NOT depend on conftest's session-scoped `bridge` fixture — its setup AND
    teardown both call `_kill_all_tmux()` (= `tmux kill-server`), which would kill
    sibling agents' live sessions. This module instantiates its OWN `TmuxBridge()`
    and, in teardown, removes ONLY its own uniquely-named session (`close(name)`) and
    its own throwaway dir (`rm -rf`). Never a broadcast kill.
  * Do NOT edit tests/conftest.py, pyproject.toml, or tests/README.md.
  * Bridge sessions stay TAB-LESS — `show=False` (the default); never `show=True`.
=============================================================================
"""

import asyncio
import logging
import re
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

import pytest

# `bridge` is a top-level package from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

SLUG = "ctxcompact"

# The per-category rows DESIGN's context dropdown wants off `/context`. Aliases map
# the various rendered labels onto one stable key each (parse target for Lever A).
_CATEGORY_ALIASES = {
    "system prompt": "system_prompt",
    "system tools": "system_tools",
    "mcp tools": "mcp_tools",
    "custom agents": "custom_agents",
    "memory files": "memory",
    "skills": "skills",
    "messages": "messages",
    "free space": "free_space",
    "autocompact buffer": "autocompact_buffer",
}

# WORKS bar for Lever A: at least this many distinct category rows parsed into stable
# keys, each with a numeric token or percent value — plus the two most stable rows
# (system_prompt, free_space) must be among them.
_MIN_CATEGORIES = 4
_REQUIRED_CATEGORIES = {"system_prompt", "free_space"}

# Priming rounds — enough real conversation that BOTH `/context` renders non-trivial
# rows AND `/compact` actually compacts (it refuses a near-empty context).
_PRIME_ROUNDS = 4


# -----------------------------------------------------------------------------
# Driving helpers
# -----------------------------------------------------------------------------

def _assistant_count(br, name):
    try:
        return sum(1 for e in br.read_log(name) if e.get("type") == "assistant")
    except Exception:
        return 0


def _drive_round(br, name, prompt, timeout=120):
    """Send one prompt; block until a NEW assistant entry lands in the transcript."""
    before = _assistant_count(br, name)
    br.send(name, prompt)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _assistant_count(br, name) > before:
            return True
        time.sleep(1.0)
    return False


def _prime_conversation(br, name, rounds=_PRIME_ROUNDS):
    """Build a real multi-round conversation so both levers have something to act on."""
    ok = 0
    for i in range(1, rounds + 1):
        if _drive_round(br, name, f"In one short sentence, give me interesting fact #{i}."):
            ok += 1
    return ok


# -----------------------------------------------------------------------------
# Parsing / scanning helpers (the read-back)
# -----------------------------------------------------------------------------

def parse_context_screen(text):
    """Best-effort parse of a `/context` screen into {stable_key: {tokens, percent, raw}}.

    Scans each line for a known category label and pulls a token count (e.g. `12.3k`,
    `1,234`, `1234 tokens`) and/or a percent (`(6.2%)` / `6.2%`) off the same line. A
    category counts as parsed only if it yielded a numeric token OR percent value.
    """
    parsed = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower()
        for label, key in _CATEGORY_ALIASES.items():
            if label not in low:
                continue
            pct_m = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
            tok_m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*([kKmM])?\s*(?:tokens?\b)?", line)
            percent = float(pct_m.group(1)) if pct_m else None
            tokens = None
            if tok_m and tok_m.group(1):
                num = float(tok_m.group(1).replace(",", ""))
                suffix = (tok_m.group(2) or "").lower()
                if suffix == "k":
                    num *= 1_000
                elif suffix == "m":
                    num *= 1_000_000
                tokens = int(num)
            if percent is None and tokens is None:
                continue
            parsed.setdefault(key, {"tokens": tokens, "percent": percent, "raw": line})
            break
    return parsed


def find_context_markdown(entries):
    """The `/context` output also lands in the JSONL as a local-command `user` entry
    rendered as a markdown table. Return its text if present (secondary read-back)."""
    for e in reversed(entries):
        if e.get("type") != "user":
            continue
        content = (e.get("message") or {}).get("content")
        text = content if isinstance(content, str) else str(content)
        if "Context Usage" in text and "| System prompt" in text:
            return text
    return None


def scan_compaction_markers(entries):
    """Scan transcript entries for compaction markers; return hits with their shape.

    Matches broadly (the field name is what the spike ESTABLISHES): any `type`/`subtype`
    containing "compact", `isCompactSummary`, or any key containing "compact" (e.g.
    `compactMetadata`). Each hit records the marks, the entry's key set, and — for a
    `compact_boundary` — its `content` and `compactMetadata` so the test can assert shape.
    """
    hits = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        t = str(e.get("type") or "")
        sub = str(e.get("subtype") or "")
        marks = []
        if "compact" in t.lower():
            marks.append(f"type={t}")
        if "compact" in sub.lower():
            marks.append(f"subtype={sub}")
        if e.get("isCompactSummary"):
            marks.append("isCompactSummary=true")
        for k in e.keys():
            if "compact" in str(k).lower():
                marks.append(f"key:{k}")
        if marks:
            hits.append({
                "marks": marks,
                "type": t,
                "subtype": sub,
                "content": e.get("content"),
                "compactMetadata": e.get("compactMetadata"),
                "entry_keys": sorted(e.keys()),
            })
    return hits


def _boundary_count(entries):
    return sum(
        1 for e in entries
        if e.get("type") == "system" and e.get("subtype") == "compact_boundary"
    )


# -----------------------------------------------------------------------------
# Fixture — our OWN bridge, one primed tab-less session, shared by both levers.
# Teardown removes ONLY this session + its own dir. Never kill-server.
# -----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def primed_session():
    br = TmuxBridge()
    name = f"{SLUG}-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-{SLUG}-{uuid.uuid4().hex[:8]}"
    br._run(f"mkdir -p {diag}")
    created = False
    try:
        br.create(name, cwd=diag)  # show=False (default) — TAB-LESS. Never show=True.
        created = True
        br.wait_idle(name, timeout=60)
        primed = _prime_conversation(br, name)
        if primed < 2:
            pytest.skip(f"could not prime a conversation (only {primed} rounds landed)")
        log.debug("primed session %s in %s with %d rounds", name, diag, primed)
        yield br, name
    finally:
        if created:
            try:
                br.close(name)
            except Exception as e:  # pragma: no cover - best effort
                log.debug("close(%s) failed: %s", name, e)
        try:
            br._run(f"rm -rf {diag}")
        except Exception as e:  # pragma: no cover - best effort
            log.debug("rm -rf %s failed: %s", diag, e)


# -----------------------------------------------------------------------------
# Lever A — per-category breakdown via `/context`
# -----------------------------------------------------------------------------

def test_lever_a_context_breakdown(primed_session):
    """`/context` at an idle boundary renders the per-category split; the rows parse into
    stable labeled values (screen-scrape), and the same table is recoverable from the
    JSONL transcript as markdown. WORKS = a clean parse of >= _MIN_CATEGORIES rows incl.
    the stable core; an unparseable screen would be the predicted xfail FINDING."""
    br, name = primed_session

    async def flow():
        br.send(name, "/context")
        # `/context` renders to screen (not a generating turn); poll scrollback until
        # the category rows appear.
        screen = ""
        parsed = {}
        for _ in range(12):
            await asyncio.sleep(1.5)
            screen = br.scrollback(name, max_lines=200)["content"]
            parsed = parse_context_screen(screen)
            if len(parsed) >= _MIN_CATEGORIES and _REQUIRED_CATEGORIES <= set(parsed):
                break

        log.debug("=== /context raw scrollback (tail 4000) ===\n%s", screen[-4000:])
        log.debug("=== parsed categories: %s", parsed)

        # Every parsed category must carry a numeric value (labels alone are not a
        # machine-readable breakdown).
        for key, vals in parsed.items():
            assert vals.get("tokens") is not None or vals.get("percent") is not None, (
                f"category {key!r} parsed no numeric value: {vals}"
            )

        if not (len(parsed) >= _MIN_CATEGORIES and _REQUIRED_CATEGORIES <= set(parsed)):
            # Predicted honest NEGATIVE — screen-scrape-only, unparseable. Not a fake green.
            pytest.xfail(
                "FINDING (Lever A): `/context` did not parse into >= "
                f"{_MIN_CATEGORIES} stable category rows incl. {_REQUIRED_CATEGORIES} "
                f"(got {sorted(parsed)}). Per-category breakdown is a screen-scrape-only "
                "snapshot; settle for total usage + turn count (derive_context_usage). "
                f"Screen head:\n{screen[:1200]}"
            )

        # WORKS — the per-category rows parsed into stable keys with numeric values.
        log.info("Lever A WORKS: parsed %d categories: %s", len(parsed), sorted(parsed))

        # Secondary read-back: the same breakdown is recorded in the JSONL as a markdown
        # table (steadier than raw screen-scrape). Best-effort — assert it only if present.
        entries = br.read_log(name)
        md = find_context_markdown(entries)
        if md:
            log.debug("=== /context markdown table (from transcript) ===\n%s", md[:1200])
            assert "| System prompt" in md and "Percentage" in md, (
                "context markdown table present but missing expected columns"
            )
        else:
            log.info("Lever A: no transcript markdown table found (screen-scrape only)")

    asyncio.run(flow())


# -----------------------------------------------------------------------------
# Lever B — compaction marking via `compact_boundary`
# -----------------------------------------------------------------------------

def test_lever_b_compact_boundary(primed_session):
    """Force a REAL `/compact` (retrying with extra rounds if refused for too little
    context), then read_log() and assert a `compact_boundary` marker with its
    `compactMetadata` shape appears. WORKS = the marker reliably marks the compaction and
    yields count/type/when + pre/post tokens; no marker would be the xfail FINDING."""
    br, name = primed_session

    async def flow():
        before = br.read_log(name)
        before_n = _boundary_count(before)
        log.debug("pre-/compact: %d entries, %d existing boundaries", len(before), before_n)

        entries = before
        compacted = False
        # Up to 3 attempts; drive extra rounds between refusals so a too-small context
        # can't produce a false negative.
        for attempt in range(3):
            br.send(name, "/compact")
            try:
                br.wait_idle(name, timeout=180)
            except Exception as e:  # pragma: no cover - environment dependent
                log.debug("wait_idle after /compact raised (continuing): %s", e)
            # Poll the transcript for a new boundary (compaction ~15s; be patient).
            for _ in range(30):
                await asyncio.sleep(2)
                try:
                    entries = br.read_log(name)
                except Exception as e:
                    log.debug("read_log after /compact raised: %s", e)
                    continue
                if _boundary_count(entries) > before_n:
                    compacted = True
                    break
            if compacted:
                break
            log.debug("attempt %d: no new boundary yet; driving extra rounds", attempt + 1)
            for j in range(3):
                _drive_round(br, name, f"One more short fact, please (extra {attempt}-{j}).")

        after_types = Counter(str(e.get("type")) for e in entries)
        hits = scan_compaction_markers(entries)
        boundaries = [h for h in hits if h["subtype"] == "compact_boundary"]
        log.debug("post-/compact: %d entries types=%s", len(entries), dict(after_types))
        log.debug("=== compaction marker hits: %s", hits)

        if not boundaries:
            tail = [
                {"type": e.get("type"), "subtype": e.get("subtype"), "keys": sorted(e.keys())}
                for e in entries[-8:]
            ]
            pytest.xfail(
                "FINDING (Lever B): no `compact_boundary` entry appeared after /compact "
                f"(compacted={compacted}, types={dict(after_types)}). Richer compaction "
                f"history is not derivable from JSONL alone. tail={tail}"
            )

        # WORKS — assert the reliable marker + its machine-readable metadata shape.
        newest = boundaries[-1]
        log.info("Lever B WORKS: %d compact_boundary marker(s); newest=%s",
                 len(boundaries), newest)
        assert newest["content"] == "Conversation compacted", newest["content"]
        meta = newest["compactMetadata"] or {}
        assert isinstance(meta, dict) and meta, "compact_boundary carried no compactMetadata"
        assert meta.get("trigger") in ("manual", "auto"), meta.get("trigger")
        # Compaction-history richness the DESIGN dropdown wants: type/when + token deltas.
        for field in ("preTokens", "postTokens", "durationMs"):
            assert meta.get(field) is not None, f"compactMetadata missing {field}: {meta}"
        # A companion summary user entry is flagged isCompactSummary.
        assert any(e.get("isCompactSummary") for e in entries), \
            "no isCompactSummary summary entry accompanied the compaction"

    asyncio.run(flow())
