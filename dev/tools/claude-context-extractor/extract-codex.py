#!/usr/bin/env python3
"""extract-codex.py — export an OpenAI Codex CLI session to Markdown.

The Codex CLI (the `codex` coding agent) stores every session on disk as a JSONL "rollout"
file — one JSON record per line — under `~/.codex/sessions/YYYY/MM/DD/rollout-<time>-<uuid>.jsonl`
(archived chats move to `~/.codex/archived_sessions/`). Alongside them sits `session_index.jsonl`,
which maps each session's uuid to its human-readable **thread name** ("Review subagent messaging",
"Implement live bridge tests", …). That thread name is what --name matches against, so you can
pull a Codex session by the title you actually remember — no uuids, no network, no auth.

This is the third sibling of extract-web.py (claude.ai) and extract-desktop.py (Claude desktop
app); it reads local disk only. Exports land in `<repo>/transcripts/codex/` by default (override
with --out), named to match the claude-history-viewer extension's convention:
    codex-<session-start-date>-<title-slug>.md          rendered transcript
    codex-<session-start-date>-<title-slug>.summary.md  stats sidecar — only when --summary is passed

What renders (the readable conversation): real user prompts, assistant replies, and tool activity
(shell commands, apply_patch, their outputs). What's dropped as noise: the system prompt, the
synthetic `<environment_context>` / permission scaffolding messages, and Codex's redundant UI
event stream (which merely mirrors the canonical model records).

Three honest Codex-vs-Claude differences worth knowing:
  • Reasoning is usually ENCRYPTED on disk (`encrypted_content` blobs) — Codex doesn't keep
    readable thinking the way Claude does. A reasoning block renders only when a plaintext
    summary is present; otherwise it's silently skipped.
  • Token counts are EXACT and free — Codex logs real per-turn usage, so --summary reports the
    true total, not an estimate.
  • Codex records no model id (only `model_provider` + `cli_version`), so the header shows those.

By default --list and --name show your real chats and hide Codex's internal `guardian` subagent
sessions (approval-checkers with no thread name); pass --all to include them.

When done, the export opens as a tab in the running VS Code window (via the `code` CLI), the same
way the claude-history-viewer extension does — pass --no-open to skip that (batch/headless runs).

Usage (stdlib only — any Python 3.9+, no venv needed). Copy-paste these from the repo root:
    python dev/tools/claude-context-extractor/extract-codex.py --list
    python dev/tools/claude-context-extractor/extract-codex.py --name "Review subagent messaging"
    python dev/tools/claude-context-extractor/extract-codex.py --name "subagent" --summary
    python dev/tools/claude-context-extractor/extract-codex.py --session 019f2e37     # id, prefix, or suffix
    python dev/tools/claude-context-extractor/extract-codex.py --list --all           # incl. subagents
    python dev/tools/claude-context-extractor/extract-codex.py --name "..." --out C:\\somewhere\\else
(Or `cd dev/tools/claude-context-extractor` first and drop the path prefix: `python extract-codex.py --list`.)

Escape hatches:
    --all                 include Codex's internal guardian/subagent sessions in --list / --name
    --no-open             don't open the export in VS Code afterward (default: open it)
    --root <dir>          Codex home, if sessions live somewhere non-standard (else $CODEX_HOME, ~/.codex)
    --transcript <jsonl>  render one rollout .jsonl directly (skip discovery)
"""

from __future__ import annotations   # keep `X | None` annotations working on Python 3.9

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Codex home: $CODEX_HOME wins (Codex honors it too), else ~/.codex. Sessions live under
# sessions/ (live) and archived_sessions/ (archived); session_index.jsonl maps uuid -> thread name.
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))

# This file lives at <repo>/dev/tools/claude-context-extractor/, so the repo root is 3 up.
# If the script is copied somewhere shallower, fall back to CWD instead of crashing at import.
try:
    REPO_ROOT = Path(__file__).resolve().parents[3]
except IndexError:
    REPO_ROOT = Path.cwd()
DEFAULT_OUT = REPO_ROOT / "transcripts" / "codex"

TOOL_INPUT_CAP = 3000     # chars of tool-call input shown per call
TOOL_RESULT_CAP = 4000    # chars of tool output shown per result
TITLE_FALLBACK_CAP = 60   # chars of the first user message used as a title when unnamed

# User-role messages that are synthetic scaffolding, not real prompts — dropped from the render.
SYNTHETIC_USER_PREFIXES = ("<environment_context", "<permissions", "<user_instructions")

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
FNAME_TS_RE = re.compile(r"rollout-(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})-(\d{2})")


def sessions_dirs(home: Path):
    """Live sessions first, then archived — first match wins on the rare uuid collision."""
    return [home / "sessions", home / "archived_sessions"]


def open_in_editor(paths, enabled: bool = True) -> None:
    """Best-effort: open the exported file(s) as tabs in the running VS Code window — the
    same convenience the claude-history-viewer extension gives. Uses the `code` CLI (installed
    globally on PATH, or provided by VS Code's integrated terminal). Quietly no-ops if `code`
    isn't found or the launch fails: an editor that won't open must never break an export."""
    paths = [p for p in (paths or []) if p]
    if not enabled or not paths:
        return
    code = shutil.which("code")
    if not code:
        print("  (skipped auto-open: VS Code 'code' command not on PATH)", file=sys.stderr)
        return
    # On Windows `code` resolves to a .cmd/.bat — route those through cmd.exe so the
    # launch is reliable across Python versions; run other platforms' `code` directly.
    launcher = (["cmd", "/c", code] if os.name == "nt" and code.lower().endswith((".cmd", ".bat"))
                else [code])
    try:
        subprocess.run([*launcher, "--reuse-window", *[str(p) for p in paths]], check=False)
        print(f"  (opened in VS Code: {', '.join(Path(p).name for p in paths)})")
    except Exception as e:
        print(f"  (skipped auto-open: {e})", file=sys.stderr)


# ----------------------------- discovery (by name) -----------------------------

def load_index(home: Path):
    """session_index.jsonl maps uuid -> thread name. It's append-only, so a renamed thread
    leaves stale duplicates; keep the newest `updated_at` per uuid."""
    idx, when = {}, {}
    f = home / "session_index.jsonl"
    if not f.exists():
        return idx
    for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except Exception:
            continue
        i, name, up = o.get("id"), o.get("thread_name"), o.get("updated_at") or ""
        if i and name and up >= when.get(i, ""):
            idx[i], when[i] = name, up
    return idx


def parse_uuid(name: str) -> str:
    m = UUID_RE.search(name)
    return m.group(0) if m else ""


def ts_from_filename(name: str):
    """The rollout filename stamps LOCAL start time (matches how you think of the session);
    session_meta.timestamp is UTC. We date exports by this local stamp."""
    m = FNAME_TS_RE.search(name)
    if not m:
        return None
    try:
        y, mo, d, h, mi, s = (int(x) for x in m.groups())
        return datetime(y, mo, d, h, mi, s)
    except Exception:
        return None


def iso_to_dt(s):
    if not s:
        return None
    try:
        s = s.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None


def _msg_text(payload: dict) -> str:
    """A message's content is a list of typed blocks (input_text for user, output_text for
    assistant) — both carry `text`. Occasionally content is a plain string."""
    c = payload.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join((b.get("text") or b.get("input_text") or "")
                         for b in c if isinstance(b, dict)).strip()
    return ""


def is_subagent(meta: dict) -> bool:
    """Guardian/subagent sessions record `source: {"subagent": {...}}`; real chats have a
    plain-string source (e.g. "vscode"). These internals have no thread name and clutter --list."""
    return isinstance(meta.get("source"), dict) and "subagent" in meta["source"]


def peek_session(path: Path, need_first_user: bool):
    """Read only the head of a rollout file (they can be tens of MB — a single tool-output line
    may be huge) to get session_meta and, when the session is unnamed, its first real user
    message for a fallback title. Stops as soon as it has what it needs."""
    meta, first_user = {}, None
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for i, ln in enumerate(fh):
                if i > 40:                       # deep enough for meta + first prompt; bail before giant lines
                    break
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                tt = o.get("type")
                pl = o.get("payload") if isinstance(o.get("payload"), dict) else {}
                if tt == "session_meta":
                    meta = pl
                    if not need_first_user:
                        break
                elif need_first_user and first_user is None:
                    if tt == "event_msg" and pl.get("type") == "user_message":
                        m = (pl.get("message") or "").strip()
                        if m and not m.startswith("<"):
                            first_user = m
                    elif tt == "response_item" and pl.get("type") == "message" and pl.get("role") == "user":
                        t = _msg_text(pl)
                        if t and not t.lstrip().startswith(SYNTHETIC_USER_PREFIXES):
                            first_user = t
                if meta and (first_user or not need_first_user):
                    break
    except Exception:
        pass
    return meta, first_user


def title_for(uuid: str, idx: dict, first_user, meta: dict) -> str:
    """thread name (the good one) → first real user message → working-folder name → placeholder."""
    if idx.get(uuid):
        return idx[uuid]
    if first_user:
        one = " ".join(first_user.split())
        return (one[:TITLE_FALLBACK_CAP] + "…") if len(one) > TITLE_FALLBACK_CAP else one
    cwd = meta.get("cwd")
    if cwd:
        return Path(cwd).name or cwd
    return "(untitled)"


def discover_sessions(home: Path, include_subagent: bool):
    idx = load_index(home)
    sessions, seen = [], set()
    for d in sessions_dirs(home):
        if not d.exists():
            continue
        for f in d.rglob("rollout-*.jsonl"):
            uuid = parse_uuid(f.name)
            if uuid and uuid in seen:            # live copy already claimed this session
                continue
            named = bool(idx.get(uuid))
            meta, first_user = peek_session(f, need_first_user=not named)
            if is_subagent(meta) and not include_subagent:
                continue
            if uuid:
                seen.add(uuid)
            sessions.append({
                "title": title_for(uuid, idx, first_user, meta),
                "session_id": uuid or f.stem,
                "started": ts_from_filename(f.name) or iso_to_dt(meta.get("timestamp")),
                "cwd": meta.get("cwd") or "",
                "subagent": is_subagent(meta),
                "archived": d.name == "archived_sessions",
                "path": f,
            })
    sessions.sort(key=lambda s: s["started"] or datetime.min, reverse=True)
    return sessions


def pick_by_name(sessions, needle: str):
    n = needle.lower().strip()
    matches = [s for s in sessions if n in s["title"].lower()]
    if not matches:
        sys.exit(f'No session title matching "{needle}". Run --list to see titles '
                 '(add --all to include internal subagent sessions).')
    if len(matches) > 1:
        exact = [s for s in matches if s["title"].lower() == n]
        if len(exact) == 1:
            return exact[0]
        print(f'"{needle}" is ambiguous — {len(matches)} matches:', file=sys.stderr)
        for s in matches:
            when = s["started"].strftime("%Y-%m-%d %H:%M") if s["started"] else "?"
            print(f"   {when}  {s['title']}", file=sys.stderr)
        sys.exit("Refine --name (exact title wins ties) or use --session <id>.")
    return matches[0]


# ----------------------------- rendering -----------------------------

def slugify(title: str) -> str:
    """Mirror the claude-history-viewer extension's filename slug:
    lowercase, non-alphanumeric runs -> '-', trim '-', max 50 chars."""
    return re.sub(r"[^a-z0-9]+", "-", (title or "session").lower()).strip("-")[:50] or "session"


def export_basename(title: str, started) -> str:
    """`codex-<session-start-date>-<title-slug>` — the extension's convention, codex-flavored."""
    d = started or datetime.now()
    return f"codex-{d:%Y-%m-%d}-{slugify(title)}"


def disambiguate(out_dir: Path, base: str, owner_marker: str) -> str:
    """Keep the extension's naming, but never clobber a DIFFERENT session's export.
    Re-exporting the same session reuses its filename (refresh); a different session that
    happens to share the title+date gets `-2`, `-3`, ... appended."""
    candidate, n = base, 2
    while True:
        existing = out_dir / f"{candidate}.md"
        if not existing.exists():
            return candidate
        try:
            head = existing.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception:
            head = ""
        if owner_marker in head:                 # same session — safe to overwrite
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def load_records(path: Path):
    recs = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if ln:
            try:
                recs.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return recs


def as_text(content) -> str:
    """A tool output may be a plain string or a list/dict of typed blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict):
                out.append(b.get("text") or json.dumps(b, ensure_ascii=False)[:400])
            else:
                out.append(str(b))
        return "\n".join(out)
    if isinstance(content, dict):
        return content.get("output") or content.get("text") or json.dumps(content, ensure_ascii=False)
    return json.dumps(content, ensure_ascii=False) if content is not None else ""


def cap(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + f"\n… [truncated, {len(s) - n} more chars]"


def render_tool_call(pl: dict) -> str:
    name = pl.get("name", "tool")
    raw = pl.get("arguments")
    if raw is None:
        raw = pl.get("input", "")
    body = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    try:                                          # pretty-print JSON args (shell_command etc.); patches stay raw
        body = json.dumps(json.loads(body), ensure_ascii=False, indent=2)
    except Exception:
        pass
    return f"\n**[tool → {name}]**\n```\n{cap(body, TOOL_INPUT_CAP)}\n```\n"


def render_tool_result(pl: dict) -> str:
    body = cap(as_text(pl.get("output")), TOOL_RESULT_CAP)
    return f"\n**[tool result]**\n```\n{body}\n```\n"


def render_reasoning(pl: dict) -> str:
    """Codex reasoning is usually encrypted (no plaintext); render only when a summary exists."""
    summ = pl.get("summary")
    if isinstance(summ, list):
        parts = [b.get("text", "") for b in summ if isinstance(b, dict)]
        txt = "\n".join(p for p in parts if p).strip()
        if txt:
            return "\n> **[reasoning]**\n> " + txt.replace("\n", "\n> ") + "\n"
    return ""


def render(path: Path, title: str, out_dir: Path, want_summary: bool, open_editor: bool = True):
    recs = load_records(path)
    meta = next((r.get("payload") for r in recs
                 if r.get("type") == "session_meta" and isinstance(r.get("payload"), dict)), {})
    sid = meta.get("id") or parse_uuid(path.name) or path.stem
    started = ts_from_filename(path.name) or iso_to_dt(meta.get("timestamp"))

    n_user = n_asst = n_reason = 0
    tools = Counter()
    tokens_total = 0
    body_lines = []
    for r in recs:
        tt = r.get("type")
        pl = r.get("payload") if isinstance(r.get("payload"), dict) else {}
        pt = pl.get("type")
        if tt == "event_msg" and pt == "token_count":
            tu = (pl.get("info") or {}).get("total_token_usage") or {}
            tokens_total = max(tokens_total, tu.get("total_tokens") or 0)
            continue
        if tt != "response_item":                 # session_meta, turn_context, redundant event_msg stream
            continue
        if pt == "message":
            role = pl.get("role")
            if role == "developer":               # permission scaffolding — noise
                continue
            text = _msg_text(pl)
            if role == "user":
                if not text or text.lstrip().startswith(SYNTHETIC_USER_PREFIXES):
                    continue
                n_user += 1
                body_lines += [f"## user", text, ""]
            elif role == "assistant":
                n_asst += 1
                body_lines += [f"## assistant", text, ""]
        elif pt in ("function_call", "custom_tool_call"):
            tools[pl.get("name", "tool")] += 1
            body_lines.append(render_tool_call(pl))
        elif pt in ("function_call_output", "custom_tool_call_output"):
            body_lines.append(render_tool_result(pl))
        elif pt == "reasoning":
            block = render_reasoning(pl)
            if block:
                n_reason += 1
                body_lines.append(block)

    out_dir.mkdir(parents=True, exist_ok=True)
    base = disambiguate(out_dir, export_basename(title, started), f"- session: {sid}")
    tpath = out_dir / f"{base}.md"

    model = meta.get("model") or meta.get("model_provider") or "n/a"
    if meta.get("cli_version"):
        model = f"{model} (codex-cli {meta['cli_version']})"
    header = [f"# {title}", "",
              f"- session: {sid}",
              f"- model: {model}",
              f"- originator: {meta.get('originator', 'n/a')}",
              f"- working folder: {meta.get('cwd', 'n/a')}",
              f"- started: {meta.get('timestamp') or (started.isoformat() if started else 'n/a')}",
              f"- records: {len(recs)} ({n_user} user, {n_asst} assistant, {sum(tools.values())} tool calls)",
              f"- exact tokens: {tokens_total:,}" if tokens_total else "- exact tokens: n/a",
              f"- source: {path}",
              f"- exported: {datetime.now():%Y-%m-%d %H:%M}", "", "---", ""]
    # errors="replace" on write: rollouts can carry lone surrogates from mid-string truncation.
    tpath.write_text("\n".join(header + body_lines), encoding="utf-8", errors="replace")
    written = [tpath]

    if want_summary:
        S = [f"# Summary — {title}", "",
             f"- session id: {sid}",
             f"- model: {model}",
             f"- working folder: {meta.get('cwd', 'n/a')}",
             f"- started: {meta.get('timestamp') or 'n/a'}", "",
             "## Activity",
             f"- conversation messages: {n_user + n_asst} ({n_user} user, {n_asst} assistant)",
             f"- reasoning blocks (plaintext): {n_reason}",
             f"- tool calls: {sum(tools.values())}"]
        S += [f"    - {nm}: {c}" for nm, c in tools.most_common()]
        S += ["", "## Tokens",
              f"- exact total tokens: {tokens_total:,}" if tokens_total else "- exact total tokens: n/a",
              "  (Codex logs true usage on disk — this is the real number, not an estimate)", "",
              "## Source", f"- records in file: {len(recs)}", f"- file: {path}"]
        spath = out_dir / f"{base}.summary.md"
        spath.write_text("\n".join(S), encoding="utf-8", errors="replace")
        written.append(spath)

    print("Wrote:")
    for p in written:
        print(f"  {p}")
    print(f"\n{title}")
    print(f"{n_user + n_asst} messages ({n_user} user / {n_asst} assistant) · "
          f"{sum(tools.values())} tool calls · {tokens_total:,} tokens")
    open_in_editor(written, open_editor)


# ----------------------------- CLI -----------------------------

def main():
    try:  # Windows consoles default to cp1252; errors="replace" also survives lone surrogates
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        description="Export an OpenAI Codex CLI session to Markdown.")
    ap.add_argument("--list", action="store_true", help="list Codex sessions by thread name")
    ap.add_argument("--name", help="export by thread name (substring, case-insensitive; exact wins ties)")
    ap.add_argument("--session", help="export by session uuid (full, or a unique prefix/suffix)")
    ap.add_argument("--all", action="store_true",
                    help="include Codex's internal guardian/subagent sessions (default: hide them)")
    ap.add_argument("--summary", action="store_true",
                    help="also write a <name>.summary.md stats sidecar (default: transcript only)")
    ap.add_argument("--out", help=f"output directory (default: {DEFAULT_OUT})")
    ap.add_argument("--no-open", action="store_true",
                    help="don't open the export in VS Code afterward (default: open it)")
    ap.add_argument("--root", help="Codex home (default: $CODEX_HOME, else ~/.codex)")
    ap.add_argument("--transcript", help="render one rollout .jsonl directly (skip discovery)")
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else DEFAULT_OUT

    if args.transcript:                           # explicit-path mode, no discovery
        f = Path(args.transcript)
        if not f.exists():
            sys.exit(f"--transcript not found: {f}")
        meta, first_user = peek_session(f, need_first_user=True)
        title = title_for(parse_uuid(f.name), {}, first_user, meta)
        render(f, title, out_dir, args.summary, not args.no_open)
        return

    home = Path(args.root) if args.root else CODEX_HOME
    if not home.exists():
        sys.exit(f"No Codex home found at {home} (is the Codex CLI installed?). "
                 "Pass --root <dir> or set $CODEX_HOME if it lives somewhere non-standard.")
    sessions = discover_sessions(home, include_subagent=args.all)

    if args.list or (not args.name and not args.session):
        label = "Codex sessions" + (" (incl. subagents)" if args.all else "")
        print(f"{len(sessions)} {label}:\n")
        for s in sessions:
            when = s["started"].strftime("%Y-%m-%d %H:%M") if s["started"] else "?"
            tag = " [subagent]" if s["subagent"] else (" [archived]" if s["archived"] else "")
            print(f"  {when:16}  {s['title']}{tag}")
        if not args.list:
            print('\nExport one with:  python extract-codex.py --name "<title>"')
        return

    if args.session:
        # session lookup reaches everything (incl. subagents), since it's explicit.
        pool = sessions if args.all else discover_sessions(home, include_subagent=True)
        # Codex ids are time-ordered UUIDv7 — naturally referenced by their front (prefix);
        # accept a full id, a prefix, or a suffix.
        hits = [s for s in pool if s["session_id"] == args.session
                or s["session_id"].startswith(args.session)
                or s["session_id"].endswith(args.session)]
        if not hits:
            sys.exit(f"No session with id {args.session}. Run --list to see sessions.")
        if len(hits) > 1:                         # suffix matched several — never guess silently
            print(f"--session {args.session} is ambiguous — {len(hits)} matches:", file=sys.stderr)
            for s in hits:
                print(f"   {s['session_id']}  ({s['title']})", file=sys.stderr)
            sys.exit("Use a longer suffix or the full session id.")
        match = hits[0]
    else:
        match = pick_by_name(sessions, args.name)

    render(match["path"], match["title"], out_dir, args.summary, not args.no_open)


if __name__ == "__main__":
    main()
