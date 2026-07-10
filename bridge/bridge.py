"""
CC tmux Bridge — Core bridge class.

Programmatic control of Claude Code TUI sessions running in tmux inside WSL2.
All tmux commands are dispatched via `wsl -d Ubuntu -- bash -c '...'` when
running from Windows, or directly when running inside WSL.
"""

import json
import logging
import shlex
import subprocess
import shutil
import time
import re
import uuid
from .paths import (
    is_windows, win_to_wsl, WSL_AWL_DIR, CLAUDE_BIN,
    parse_default_gateway, sidecar_base_url,
)

# Silent by default (no handler). Consumers — e.g. the pytest suite — can attach
# a handler to capture the exact WSL/tmux commands and their output at DEBUG.
log = logging.getLogger("bridge")


class TmuxBridgeError(Exception):
    """Raised when a tmux bridge operation fails."""
    pass


# Valid values for claude's `--permission-mode` launch flag (CC 2.1.x). An
# unrecognized value is dropped rather than passed through, so a bad/empty mode
# just launches the TUI in its default mode instead of erroring on startup.
VALID_PERMISSION_MODES = frozenset({
    "acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan",
})


# Status-line permission-mode indicators, live-verified on Claude Code 2.1.198
# (test_bypass_auto_preconditions_live). Plain-text substrings — `read()` uses
# `capture-pane -p -J`, which strips ANSI, so the words are matched. Order
# matters: most specific first. `default` shows NO indicator at all, so it is
# inferred (see parse_mode_indicator) rather than matched.
MODE_INDICATORS = (
    ("bypassPermissions", "bypass permissions on"),
    ("acceptEdits", "accept edits on"),
    ("plan", "plan mode on"),
    ("auto", "auto mode on"),
)

# The largest possible Shift+Tab mode ring (mode-control research + the live
# launch-matrix spike): default → acceptEdits → plan → [bypassPermissions] →
# [auto] → wrap. Optional segments are LAUNCH-ARMED; an un-armed segment is
# silently absent from the ring (no refusal, no indicator — it simply never
# appears). This bounds set_permission_mode's cycle attempts so an absent
# target yields an honest "unreachable", never an infinite loop.
MODE_RING_MAX = 5

# The `Meta+T` "Toggle thinking mode" modal (live-verified,
# test_thinking_toggle_live) and the `Meta+O` "↯ Fast mode (research preview)"
# panel (live-verified, test_fast_mode_toggle_live).
_THINKING_PANEL_MARKER = "toggle thinking mode"
_PANEL_CHECKMARKS = ("✔", "✓")  # the mark on the currently-active option
_FAST_PANEL_MARKER = "fast mode (research preview)"


def parse_mode_indicator(content):
    """Parse the CURRENT permission mode off a captured screen's status line.

    Pure function (no live session) so it is hermetically unit-testable. The
    status line shows a plain-text mode indicator for every non-default mode
    ("accept edits on", "plan mode on", "auto mode on", "bypass permissions
    on"); `default` shows no indicator, so it is reported only when the capture
    shows evidence of a rendered TUI screen (the input-box rule or the prompt
    marker) with none of the indicators present.

    Args:
        content: A captured screen block (as from ``read``/``status``).

    Returns:
        One of ``"default" / "acceptEdits" / "plan" / "auto" /
        "bypassPermissions"``, or ``None`` when the capture doesn't look like a
        rendered TUI screen.
    """
    if not content:
        return None
    low = content.lower()
    for label, needle in MODE_INDICATORS:
        if needle in low:
            return label
    if re.search(r"─{10,}", content) or "❯" in content:
        return "default"
    return None


def parse_thinking_panel(content):
    """Parse the open `Meta+T` "Toggle thinking mode" panel.

    Pure function. The panel is a numbered menu whose active option carries a
    check mark::

        ❯ 1. Enabled ✔  Claude will think before responding
          2. Disabled   Claude will respond without extended thinking

    Returns:
        ``"enabled"`` / ``"disabled"`` (whichever option line carries the mark),
        or ``None`` when the panel isn't open / can't be parsed.
    """
    if not content or _THINKING_PANEL_MARKER not in content.lower():
        return None
    state = None
    for line in content.splitlines():
        if not any(c in line for c in _PANEL_CHECKMARKS):
            continue
        low = line.lower()
        if "disabled" in low:
            state = "disabled"
        elif "enabled" in low:
            state = "enabled"
    return state


def parse_fast_panel(content):
    """Parse the open `Meta+O` "↯ Fast mode (research preview)" panel.

    Pure function. The state is the panel's ``Fast mode  OFF/ON  $…/Mtok`` line
    — the ``$/Mtok`` marker only exists in the OPEN panel, so a closed-state
    footer reading "Fast mode OFF" cannot be confused for it. A credit-gated
    account (no Fast usage credits) is reported distinctly: the panel says
    "requires usage credits" and no keystroke can turn Fast on.

    Returns:
        ``"on"`` / ``"off"`` / ``"credit-gated"``, or ``None`` when the panel
        isn't open / can't be parsed.
    """
    if not content:
        return None
    low = content.lower()
    if _FAST_PANEL_MARKER not in low:
        return None
    if "requires usage credits" in low or "usage-credits" in low:
        return "credit-gated"
    for line in content.splitlines():
        if "mtok" not in line.lower():
            continue
        norm = re.sub(r"\s+", " ", line.lower()).strip()
        if "fast mode on" in norm:
            return "on"
        if "fast mode off" in norm:
            return "off"
    return None


def _looks_like_optin_menu(content):
    """A numbered opt-in/enrollment menu (e.g. the auto-mode one-time opt-in)
    rendered instead of a clean mode line mid-cycle — the cycle helper backs out
    with Escape and keeps counting."""
    low = content.lower()
    return ("don't ask again" in low or "enable auto" in low
            or "opt in" in low or "do you want to enable" in low)


# Lines that look like a numbered menu option, e.g. "❯ 1. Yes" or "  3. No".
_MENU_OPTION_RE = re.compile(r"^\s*[❯>]?\s*(\d+)\.\s+(.*\S)\s*$")
# How close to the bottom of the capture the menu's last option must sit to count
# as the live prompt rather than an answered menu scrolled up into history. The
# live menu is followed by at most the "Esc to cancel · Tab to amend" hint line
# (trailing blank rows are stripped by ``read``), so a small slack is enough; a
# stale menu sits above the idle input box + status bar (several lines), so it is
# rejected.
_MENU_BOTTOM_SLACK = 3


def parse_permission_prompt(content):
    """Parse a captured Claude Code permission menu into structured detail.

    Pure function (no live session) so it is hermetically unit-testable, mirroring
    how ``_detect_state`` is tested. Anchors on the numbered menu at the BOTTOM of
    the capture — a numbered ``1. Yes`` option (the proven menu marker) — so a
    "Do you want …?" line or an already-answered menu left higher in older
    scrollback cannot false-fire.

    The real edit prompt renders a multi-line diff preview above the question, so
    the "Do you want …?" line can sit well above the menu; callers should capture
    comfortably more than the bottom 15 lines before parsing for detail.

    Args:
        content: A captured screen block (as from ``read``/``status``).

    Returns:
        ``{"question": str, "options": [{"index": int, "label": str}, ...],
        "raw": str}`` for a live menu, or ``None`` when no live menu is present.
    """
    if not content:
        return None

    lines = content.rstrip("\n").split("\n")
    option_idxs = [i for i, ln in enumerate(lines) if _MENU_OPTION_RE.match(ln)]
    if not option_idxs:
        return None

    # Take the trailing menu: the run of option lines ending at the last option
    # line (small gaps — e.g. a blank line between options — are tolerated).
    last = option_idxs[-1]
    block = [last]
    for i in reversed(option_idxs[:-1]):
        if 0 < block[-1] - i <= 2:
            block.append(i)
        else:
            break
    block.sort()

    # Anchor at the bottom: a live menu is at (or near) the end of the capture.
    # An answered menu scrolled up into history sits higher and is rejected.
    if last < len(lines) - 1 - _MENU_BOTTOM_SLACK:
        return None

    options = []
    for i in block:
        m = _MENU_OPTION_RE.match(lines[i])
        options.append({"index": int(m.group(1)), "label": m.group(2).strip()})

    # Proven marker: a "1. Yes" option must be present (loose keyword matching
    # false-fired on prompt text containing "permission"/"approve").
    if not any(o["index"] == 1 and o["label"].lower().startswith("yes")
               for o in options):
        return None

    # Question: prefer an explicit "Do you want …?" line above the menu; else the
    # nearest non-empty line above it.
    question = ""
    for i in range(block[0] - 1, -1, -1):
        text = lines[i].strip()
        if text:
            question = text
            break
    for i in range(block[0] - 1, -1, -1):
        if re.search(r"Do you want", lines[i], re.IGNORECASE):
            question = lines[i].strip()
            break

    raw = "\n".join(lines[max(0, block[0] - 8): last + 2])
    return {"question": question, "options": options, "raw": raw}


class TmuxBridge:
    """Programmatic control of Claude Code TUI sessions in WSL2/tmux.

    Each session is a named tmux session running a Claude Code TUI.
    Sessions are always live and interactive — programmatic control
    and manual typing coexist without mode switching.
    """

    def __init__(self, distro="Ubuntu", default_cwd=None, default_model=None):
        """Initialize the bridge.

        Args:
            distro: WSL distribution name (default: Ubuntu).
            default_cwd: Default working directory for new sessions.
                         Accepts Windows or WSL paths.
            default_model: Default model flag for new sessions (e.g. "sonnet").
        """
        self._distro = distro
        self._default_cwd = default_cwd
        self._default_model = default_model
        self._on_windows = is_windows()
        # tmux session name -> the claude `--session-id` (uuid) we launched it
        # with. The transcript file is named `<session-id>.jsonl`, so this is how
        # `find_transcript` resolves a session's OWN transcript even when several
        # agents share a cwd (and thus a project dir). See create()/transcript.py.
        self._session_uuids: dict[str, str] = {}
        # Cached Windows-host IP reachable from inside WSL (the default gateway).
        # "" = resolved-but-none; None = not yet resolved. Stable within a WSL
        # boot, so resolved once and reused for every agent's hook URL.
        self._host_ip: str | None = None

    # --- Low-level execution ---

    def _run(self, bash_cmd, timeout=30, stdin_data=None):
        """Run a bash command inside WSL and return stdout.

        Args:
            bash_cmd: The bash command string to execute.
            timeout: Seconds before the command is killed.
            stdin_data: If given, this string is piped to the command's stdin.
                Use this for large payloads (e.g. writing a config file via
                ``cat > file``) instead of embedding them in ``bash_cmd`` —
                Windows caps a command line at ~32 KB and raises WinError 206
                beyond that.

        Returns:
            stdout as a string (stripped).

        Raises:
            TmuxBridgeError: If the command fails.
        """
        if self._on_windows:
            cmd = ["wsl", "-d", self._distro, "--", "bash", "-c", bash_cmd]
        else:
            cmd = ["bash", "-c", bash_cmd]

        log.debug("run (stdin=%dB): %s", len(stdin_data or ""), bash_cmd[:200])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                input=stdin_data,
            )
        except subprocess.TimeoutExpired:
            raise TmuxBridgeError(f"Command timed out after {timeout}s: {bash_cmd[:80]}")

        log.debug("  -> rc=%s out=%r err=%r", result.returncode,
                  result.stdout[:200], result.stderr[:200])
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise TmuxBridgeError(stderr or f"Command failed (exit {result.returncode})")

        return result.stdout.strip()

    def _tmux(self, tmux_args, timeout=10):
        """Run a tmux command inside WSL.

        Args:
            tmux_args: The tmux subcommand and arguments as a string.
            timeout: Seconds before the command is killed.

        Returns:
            stdout as a string (stripped).
        """
        return self._run(f"tmux {tmux_args}", timeout=timeout)

    def _resolve_cwd(self, cwd):
        """Resolve a working directory path for use inside WSL."""
        path = cwd or self._default_cwd
        if not path:
            return None
        if self._on_windows:
            return win_to_wsl(path)
        return path

    def _write_agent_config(self, name, filename, data):
        """Materialize a per-agent launch-config file to a WSL-reachable path.

        Used for the ``--settings`` / ``--mcp-config`` files built at create
        time. The JSON is piped via stdin (``cat > file``) rather than embedded
        in the command, so a large payload (many MCP servers / permission rules)
        cannot blow past Windows' ~32 KB command-line limit — the same pattern
        ``mcp_sync`` uses.

        Args:
            name: Session name (one config subdir per session).
            filename: e.g. ``settings.json`` or ``mcp.json``.
            data: A JSON-serializable dict.

        Returns:
            The WSL path the file was written to (suitable for a launch flag).
        """
        agent_dir = f"{WSL_AWL_DIR}/{name}"
        path = f"{agent_dir}/{filename}"
        self._run(f"mkdir -p {shlex.quote(agent_dir)}")
        self._run(
            f"cat > {shlex.quote(path)}",
            stdin_data=json.dumps(data, indent=2),
        )
        return path

    def _open_wt_tab(self, name):
        """Open a Windows Terminal tab attached to a tmux session.

        Uses `wt -w 0 new-tab` to add a tab to the existing WT window,
        or opens a new WT window if none exists. The tab runs
        `wsl -d <distro> -- tmux attach -t <name>` and its title is
        set to the session name.

        Args:
            name: The tmux session name to attach to.
        """
        if not self._on_windows:
            return  # WT only available on Windows

        wt_path = shutil.which("wt") or shutil.which("wt.exe")
        if not wt_path:
            return  # WT not installed, skip silently

        cmd = [
            wt_path, "-w", "0", "new-tab",
            "--title", name,
            "--", "wsl.exe", "-d", self._distro,
            "--", "tmux", "attach", "-t", name,
        ]
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass  # WT launch failed, non-fatal

    # --- Core Operations ---

    def create(self, name, cwd=None, model=None, claude_args="", show=False,
               permission_mode=None, allowed_tools=None, disallowed_tools=None,
               settings=None, mcp_config=None, session_id=None,
               resume_session_id=None):
        """Spawn a named tmux session running the Claude Code TUI.

        Per-agent permissions, plugins, and MCP scoping are applied AT LAUNCH
        (the only point a claude process reads them) via native flags, exactly
        like ``permission_mode`` — the bridge cannot change any of them on a
        running TUI.

        Args:
            name: Session name (used as tmux session name).
            cwd: Working directory. Accepts Windows or WSL paths.
            model: Model to use (e.g. "sonnet", "opus"). Overrides default.
            claude_args: Additional CLI arguments for claude (raw passthrough).
            session_id: The claude ``--session-id`` (a uuid) to launch with. When
                omitted a fresh uuid is generated. Claude names the session's
                transcript ``<session-id>.jsonl``, so pinning the id is what lets
                ``find_transcript`` resolve THIS agent's own transcript even when
                several agents share a cwd (same project dir). This replaces the
                old "newest .jsonl in the project dir" heuristic, which silently
                cross-read co-located agents. (The research doc's PID→
                ``~/.claude/sessions/{PID}.json`` mapping was verified DEAD on
                this build — 2.1.195 no longer writes those files — so the
                native ``--session-id`` flag is used instead.)
            resume_session_id: Cold-restore (§9.9): launch with
                ``--resume <resume_session_id>`` (and NO ``--session-id``) so the
                new process RESUMES that prior conversation instead of starting a
                fresh one. Mutually exclusive with ``session_id``. Plain
                ``--resume`` (without ``--fork-session``) reuses the SAME session
                id and keeps appending to the same ``<id>.jsonl`` — live-verified
                on Claude Code 2.1.202 (``tests/test_cold_restore_live.py``) — so
                the given id is registered as-is and transcript resolution
                continues on the same file. All other launch config (model,
                permission_mode, tools, settings, mcp_config) applies as normal,
                and startup gates are cleared as usual.
            permission_mode: Initial permission mode for the session, passed as
                claude's ``--permission-mode`` flag (one of
                ``VALID_PERMISSION_MODES``). An unrecognized/empty value is
                ignored so the TUI launches in its default mode. The
                ``bypassPermissions`` warning gate that this triggers is cleared
                by ``_clear_startup_gates`` like any other startup gate.
            allowed_tools: Optional list of tool specs to allow, passed as
                ``--allowedTools`` (comma-joined). NOTE: live-verified that the
                allow-list is IGNORED under ``bypassPermissions`` (a known claude
                bug) — use ``disallowed_tools`` for a hard block in every mode.
            disallowed_tools: Optional list of tool specs to deny, passed as
                ``--disallowedTools`` (comma-joined). This is the RELIABLE
                hard-block: the named tools are removed from the agent's toolset
                in all modes, bypass included (live-verified on 2.1.195).
            settings: Optional settings dict (e.g. ``{"permissions": {...},
                "enabledPlugins": {...}}``) materialized to a per-agent WSL file
                and passed as ``--settings``. ``permissions.deny`` hard-blocks;
                ``enabledPlugins`` enables/disables installed plugins per-agent.
            mcp_config: Optional MCP config dict (``{"mcpServers": {...}}``)
                materialized to a per-agent WSL file and passed as
                ``--mcp-config`` together with ``--strict-mcp-config`` (the agent
                sees ONLY these servers). Pass ``{"mcpServers": {}}`` for none;
                pass ``None`` (the default) to inherit the global MCP registry.
            show: When True, open a visible Windows Terminal tab attached to the
                new session. Defaults to False: the tmux session runs detached and
                is fully drivable via capture-pane/send-keys without a window, so
                callers (tests, the sidecar) get no tab and never steal desktop
                focus. Opening a tab is opt-in — pass show=True (or use show()
                later) only for explicit human attach.

        Returns:
            dict with session info: name, cwd, pid, session_id, and
            resumed_conversation (True only on a ``resume_session_id`` launch).

        Raises:
            TmuxBridgeError: If the session already exists, both ``session_id``
                and ``resume_session_id`` are given, or creation fails.
        """
        if session_id and resume_session_id:
            raise TmuxBridgeError(
                "Pass either session_id (pin a NEW conversation's id) or "
                "resume_session_id (cold-restore a prior conversation), not both."
            )

        # Check for duplicate
        existing = self._list_raw()
        if name in existing:
            raise TmuxBridgeError(
                f"Session '{name}' already exists. Use close() first or choose a different name."
            )

        resolved_cwd = self._resolve_cwd(cwd)

        # Build the claude launch argv. Each token is shell-quoted, then the whole
        # command is quoted once more for the tmux `new-session '<cmd>'` slot, so
        # tool specs / file paths containing spaces, parens, or globs survive the
        # bash -> tmux -> sh layering intact.
        argv = [CLAUDE_BIN]
        if resume_session_id:
            # Cold-restore (§9.9): resume the prior conversation. No --session-id
            # — plain --resume reuses the SAME id and appends to the same
            # `<id>.jsonl` (live-proven on CC 2.1.202; a fork would need the
            # explicit --fork-session flag), so registering the given id keeps
            # find_transcript resolving the same file.
            claude_session_id = resume_session_id
            argv += ["--resume", resume_session_id]
        else:
            # Pin a known session id so this agent's transcript is `<id>.jsonl`,
            # resolvable by find_transcript even when co-located agents share a dir.
            claude_session_id = session_id or str(uuid.uuid4())
            argv += ["--session-id", claude_session_id]
        use_model = model or self._default_model
        if use_model:
            argv += ["--model", use_model]
        if permission_mode in VALID_PERMISSION_MODES:
            argv += ["--permission-mode", permission_mode]
        elif permission_mode:
            log.warning(
                "Ignoring unknown permission_mode %r for session '%s' "
                "(launching in default mode).", permission_mode, name,
            )
        if allowed_tools:
            argv += ["--allowedTools", ",".join(allowed_tools)]
        if disallowed_tools:
            argv += ["--disallowedTools", ",".join(disallowed_tools)]
        # Per-agent settings + MCP selection are written to WSL files and passed
        # by path (dodges the ~32KB Windows command-line limit; same stdin/cat>
        # pattern as mcp_sync). Files are written BEFORE the session launches.
        if settings:
            settings_path = self._write_agent_config(name, "settings.json", settings)
            argv += ["--settings", settings_path]
        if mcp_config is not None:
            mcp_path = self._write_agent_config(name, "mcp.json", mcp_config)
            argv += ["--mcp-config", mcp_path, "--strict-mcp-config"]

        claude_cmd = " ".join(shlex.quote(a) for a in argv)
        if claude_args:
            claude_cmd += " " + claude_args  # raw passthrough (legacy)

        # Create detached tmux session
        cwd_part = f" -c {shlex.quote(resolved_cwd)}" if resolved_cwd else ""
        self._run(
            f"tmux new-session -d -s {shlex.quote(name)}{cwd_part} {shlex.quote(claude_cmd)}",
            timeout=15,
        )

        # Verify it started
        time.sleep(0.5)
        sessions = self._list_raw()
        if name not in sessions:
            raise TmuxBridgeError(f"Session '{name}' was not created. Check WSL/tmux state.")

        # Remember the session id so find_transcript can resolve this agent's own
        # transcript directly (it is `<session-id>.jsonl`).
        self._session_uuids[name] = claude_session_id

        # Open a visible Windows Terminal tab only when explicitly requested.
        # Auto-opening steals desktop focus and routes the user's keystrokes into
        # the session mid-task, so the tab is opt-in (see the `show` arg).
        if show:
            self._open_wt_tab(name)

        # Clear any startup gates (folder-trust on a fresh/untrusted dir;
        # bypass-mode when launched with --dangerously-skip-permissions) and
        # wait for the genuine idle prompt before reporting ready. No flag skips
        # these gates, and pressing Enter blindly on the bypass gate selects
        # "No, exit" and kills the session.
        self._clear_startup_gates(name)

        return {
            "status": "created",
            "name": name,
            "cwd": resolved_cwd,
            "pid": sessions[name].get("pid"),
            "session_id": claude_session_id,
            "resumed_conversation": bool(resume_session_id),
        }

    def session_id_for(self, name):
        """The claude ``--session-id`` this bridge launched ``name`` with, or None.

        Populated by ``create()`` (and by ``register_session_id`` on resume).
        """
        return self._session_uuids.get(name)

    def register_session_id(self, name, session_id):
        """Re-register a session's claude id on a fresh bridge after a resume.

        A bridge that merely *resumed* a still-alive tmux session (e.g. after a
        sidecar restart) never ran ``create()`` and so has no in-memory id. The
        sidecar persists the id in its runtime record and calls this on reconnect
        so ``find_transcript`` resolves the session's own ``<id>.jsonl`` again.
        """
        if session_id:
            self._session_uuids[name] = session_id

    def _clear_startup_gates(self, name, timeout=45, interval=0.5):
        """Clear the folder-trust and bypass-mode gates, then wait for idle.

        Both gates appear before the first turn and no CLI flag skips them:

          * Folder-trust ("… trust this folder / No, exit") — Enter accepts the
            default highlighted option 1 ("Yes, I trust this folder").
          * Bypass-mode ("WARNING: … Bypass Permissions mode") — the default
            highlight is "1. No, exit", so pressing Enter blindly kills the
            session; accept with ``keys("2")`` then ``keys("Enter")``.

        Polls the screen and clears whichever gate appears (in either order,
        each at most once) until the genuine idle prompt is reached. Returns
        best-effort on timeout rather than raising, so the caller can still
        probe state via ``status()``.
        """
        deadline = time.time() + timeout
        bypass_cleared = False
        trust_cleared = False
        while time.time() < deadline:
            content = self.read(name, lines=20)["content"]

            if not bypass_cleared and \
               re.search(r"Bypass Permissions mode", content, re.IGNORECASE):
                self.keys(name, "2")
                self.keys(name, "Enter")
                bypass_cleared = True
                time.sleep(1.0)
                continue

            if not trust_cleared and re.search(
                r"trust this folder|trust the files in this folder|"
                r"Is this a project you created or one you trust",
                content, re.IGNORECASE,
            ):
                self.keys(name, "Enter")
                trust_cleared = True
                time.sleep(1.0)
                continue

            if self._detect_state(content) == "idle":
                return

            time.sleep(interval)

        log.warning(
            "Session '%s' did not reach idle within %ss while clearing startup gates "
            "(bypass_cleared=%s, trust_cleared=%s).",
            name, timeout, bypass_cleared, trust_cleared,
        )

    def send(self, name, text, press_enter=True):
        """Type text into a session's prompt.

        Args:
            name: Session name.
            text: The text to type.
            press_enter: Whether to press Enter after typing (default True).

        Returns:
            dict with status and text length.
        """
        self._require_session(name)
        # Use literal mode (-l) so special chars are typed as-is
        # Escape single quotes in the text for the shell
        escaped = text.replace("'", "'\\''")
        self._tmux(f"send-keys -t '{name}' -l -- '{escaped}'")
        if press_enter:
            self._tmux(f"send-keys -t '{name}' Enter")
        return {"status": "sent", "name": name, "textLength": len(text)}

    def keys(self, name, *key_names):
        """Send special keys to a session.

        Args:
            name: Session name.
            *key_names: Key names like "Enter", "Escape", "C-c", "C-d".

        Returns:
            dict with status and keys sent.
        """
        self._require_session(name)
        if not key_names:
            raise TmuxBridgeError("No keys specified. Provide at least one key name.")
        for key in key_names:
            self._tmux(f"send-keys -t '{name}' {key}")
        return {"status": "sent", "name": name, "keys": list(key_names)}

    def read(self, name, lines=50):
        """Capture current screen content from a session.

        Args:
            name: Session name.
            lines: Number of lines to capture (from bottom). Default 50.

        Returns:
            dict with captured text and line count.
        """
        self._require_session(name)
        output = self._tmux(f"capture-pane -t '{name}' -p -J -S -{lines}", timeout=10)
        # Strip trailing blank lines
        content_lines = output.rstrip("\n").split("\n") if output.strip() else []
        return {
            "status": "ok",
            "name": name,
            "lines": len(content_lines),
            "content": output,
        }

    def list(self):
        """List all active tmux sessions with metadata.

        Returns:
            list of dicts, each with: name, created, attached, pid, status.
        """
        sessions = self._list_raw()
        result = []
        for name, info in sessions.items():
            result.append({
                "name": name,
                "created": info.get("created", ""),
                "attached": info.get("attached", False),
                "pid": info.get("pid", ""),
                "windows": info.get("windows", 1),
            })
        return result

    def show(self, name):
        """Open a Windows Terminal tab for an existing session.

        Useful for sessions that were created before WT was available,
        or if a WT tab was closed and you want it back.

        Args:
            name: Session name.

        Returns:
            dict with status.
        """
        self._require_session(name)
        self._open_wt_tab(name)
        return {"status": "shown", "name": name}

    def close(self, name):
        """Kill a tmux session.

        The WT tab (if any) closes automatically when the session dies.

        Args:
            name: Session name to kill.

        Returns:
            dict with status.
        """
        self._require_session(name)
        self._tmux(f"kill-session -t '{name}'")
        self._session_uuids.pop(name, None)
        # Best-effort: remove any per-agent launch config materialized for this
        # session (no-op when none was written).
        try:
            self._run(f"rm -rf {shlex.quote(f'{WSL_AWL_DIR}/{name}')}")
        except TmuxBridgeError:
            pass
        return {"status": "closed", "name": name}

    def shutdown(self):
        """Kill all tmux sessions and clean up.

        WT tabs close automatically when their tmux sessions die.

        Returns:
            dict with status and list of closed session names.
        """
        sessions = self._list_raw()
        names = list(sessions.keys())
        if names:
            self._run("tmux kill-server", timeout=10)
        return {"status": "shutdown", "closed": names}

    # --- Session Management ---

    def rename(self, old_name, new_name):
        """Rename an existing session.

        Args:
            old_name: Current session name.
            new_name: New session name.

        Returns:
            dict with old and new names.
        """
        self._require_session(old_name)
        existing = self._list_raw()
        if new_name in existing:
            raise TmuxBridgeError(f"Session '{new_name}' already exists.")
        self._tmux(f"rename-session -t '{old_name}' '{new_name}'")
        return {"status": "renamed", "old": old_name, "new": new_name}

    def resume(self, name, cwd=None, model=None, resume_session_id=None):
        """Reconnect to an existing session, or create if it doesn't exist.

        If the session is alive in tmux, rebind to it (and, when
        ``resume_session_id`` is given, re-register the claude id so
        ``find_transcript`` resolves the session's own ``<id>.jsonl`` again —
        the warm-restore of §9.9). If the tmux session is DEAD and
        ``resume_session_id`` is given, cold-restore it: relaunch via
        ``create(..., resume_session_id=...)`` — ``claude --resume <id>``, the
        SAME conversation rebuilt from its transcript. Dead with no id keeps the
        legacy behavior: a fresh ``create()`` (a brand-new conversation).

        Args:
            name: Session name.
            cwd: Working directory (only used if creating).
            model: Model flag (only used if creating).
            resume_session_id: The claude session id of the prior conversation.
                Alive session → re-registered; dead session → cold-restored.

        Returns:
            dict with session info and whether it was resumed or created.
        """
        existing = self._list_raw()
        if name in existing:
            if resume_session_id:
                self.register_session_id(name, resume_session_id)
            return {
                "status": "resumed",
                "name": name,
                "pid": existing[name].get("pid"),
            }
        if resume_session_id:
            return self.create(name, cwd=cwd, model=model,
                               resume_session_id=resume_session_id)
        return self.create(name, cwd=cwd, model=model)

    def status(self, name):
        """Get the current state of a session.

        Attempts to determine if the agent is idle, generating, or
        waiting for input by inspecting the screen content.

        Args:
            name: Session name.

        Returns:
            dict with name, state, and raw screen excerpt.
        """
        self._require_session(name)
        screen = self.read(name, lines=15)
        content = screen["content"]

        state = self._detect_state(content)

        result = {
            "status": "ok",
            "name": name,
            "state": state,
            "screen_tail": content[-500:] if content else "",
        }

        if state == "permission_prompt":
            # The "Do you want …?" question can sit above a multi-line diff
            # preview, outside the 15-line state window, so re-read a larger
            # slice for the structured detail (the menu still anchors detection).
            detail = self.read(name, lines=40)
            parsed = parse_permission_prompt(detail["content"])
            if parsed:
                result["permission"] = parsed

        return result

    def _detect_state(self, content):
        """Detect run-state from the bottom status bar of the Claude Code TUI.

        Returns one of: "idle", "generating", "permission_prompt", "unknown".

        A running turn renders an animated spinner status line — a sparkle
        glyph followed by a gerund and an ELLIPSIS (e.g. "✻ Percolating…",
        "✶ Flibbertigibbeting…") — usually with an "esc to interrupt" hint to
        its right. The hint's wording varies ("· thinking", "· esc to
        interrupt") and is clipped at the right edge in normal (non-bypass)
        mode, so we key off the sparkle-glyph line; we match either it or the
        hint. Crucially the line must contain the ellipsis: once the turn
        finishes, Claude Code leaves a same-glyph SUMMARY line ("✻ Cooked for
        1s") with no ellipsis — that is a completed turn, NOT generation, so
        requiring "…" keeps it from false-firing as generating.

        The empty ``❯`` prompt line is present whether idle OR generating — and
        Claude Code 2.x fills it with ghost-suggestion text — so a lone ❯ line
        cannot be trusted as idle. Idle is therefore "input box rendered (a
        horizontal rule plus the ❯ marker) AND not generating", never the ❯
        line alone.

        We deliberately do NOT key idle off the "? for shortcuts" hint: that
        hint rotates with other hints ("← for agents", "● high · /effort") and
        is dropped at narrow widths, so it is frequently absent on a genuinely
        idle screen.

        A genuine tool-permission prompt is confirmed by the menu marker — a
        "Do you want …?" question together with a numbered "1. Yes" option —
        rather than loose keyword matching, which false-fired on prompt text
        containing "permission"/"approve" and on the "fewer-permission-prompts"
        skill name on an idle screen.

        Screen layout (bottom of Claude Code TUI):
          ... content ...
          ────────────────  (top rule)
          ❯  <cursor>      (prompt line — present whether idle or generating)
          ────────────────  (bottom rule)
          ← for agents      ● high · /effort   (status bar — varies by width)
        """
        if not content:
            return "unknown"

        # Genuine tool-permission menu: anchored on the numbered menu at the
        # bottom of the capture (see ``parse_permission_prompt``), not loose
        # keyword matching. Checked first because a paused permission prompt is a
        # specific stop-state, distinct from idle/generating. Keying off the
        # bottom menu (rather than the "Do you want" line) means a long diff
        # preview pushing the question off a short window cannot hide the prompt.
        if parse_permission_prompt(content) is not None:
            return "permission_prompt"

        # A running turn shows the animated spinner status line — a sparkle glyph
        # at line start followed by a gerund and an ellipsis — and/or the "esc to
        # interrupt" hint. The ellipsis requirement excludes the completed-turn
        # summary line ("✻ Cooked for 1s"), which reuses the glyph but is idle.
        if re.search(r"esc to interrupt", content, re.IGNORECASE) or \
           re.search(r"(?m)^\s*[✶✷✸✹✺✻✼✽✢✣✤✥✦✧❋❉].*(?:…|\.\.\.)", content):
            return "generating"

        # Input prompt box rendered (horizontal rule + ❯) and not generating →
        # the TUI is ready and waiting for input.
        if re.search(r"─{10,}", content) and "❯" in content:
            return "idle"

        return "unknown"

    # --- Live mode / thinking / fast controls (§11 #12) ---
    #
    # The three levers proven live on the real TUI (see the three spikes:
    # tests/test_permission_mode_cycle_live.py, tests/test_thinking_toggle_live.py,
    # tests/test_fast_mode_toggle_live.py). All are tab-less keys()/read()
    # sequences; every one is gated on a verified-idle screen (keys landing
    # mid-turn are lost, misfire, or answer a pending permission menu), and every
    # result is a READ-BACK of the resulting screen state — never an echo of the
    # value sent.

    def _idle_gate(self, name, timeout=5.0, interval=0.5):
        """Poll until the screen is idle; True when safe to send control keys.

        Checks at least once even with ``timeout=0`` (so a fake/pre-idle screen
        gates in one read). Only "idle" is safe — "permission_prompt" is a menu
        that a control key would answer.
        """
        deadline = time.time() + timeout
        while True:
            if self.status(name).get("state") == "idle":
                return True
            if time.time() >= deadline:
                return False
            time.sleep(interval)

    def _open_panel_and_parse(self, name, key, parser, tries=14, interval=0.5):
        """Send a panel-opening keybinding, poll until the panel parses.

        Returns ``(state, content)`` — state is the parser's result, or ``None``
        when the panel never became parseable within ``tries`` reads.
        """
        self.keys(name, key)
        content = ""
        for _ in range(tries):
            content = self.read(name, lines=45)["content"]
            state = parser(content)
            if state is not None:
                return state, content
            time.sleep(interval)
        return None, content

    def permission_mode(self, name):
        """Read the CURRENT permission mode off the live status line.

        Read-only and safe in any run state (the mode indicator stays on the
        status bar while generating). Returns one of ``"default" /
        "acceptEdits" / "plan" / "auto" / "bypassPermissions"``, or ``None``
        when the capture doesn't look like a rendered TUI screen.
        """
        return parse_mode_indicator(self.read(name, lines=20)["content"])

    def set_permission_mode(self, name, target_mode, step_delay=1.2,
                            idle_timeout=5.0):
        """Set the permission mode on a RUNNING session — the proven cycle lever.

        No absolute set exists on the TUI (mode-control research; confirmed at
        every layer), so this cycles ``Shift+Tab`` (tmux ``BTab``) at a
        known-idle screen, reading the resulting mode back from the status line
        after each step until it equals ``target_mode``. The cycle is BOUNDED at
        the ring size + 1: an un-armed Bypass/Auto segment is SILENTLY ABSENT
        from the ring (§7.11 — no refusal, no indicator), so a target that never
        appears yields an honest ``unreachable``, never an infinite loop. The
        auto segment's one-time opt-in menu, if it interposes, is backed out of
        with Escape and the cycle continues.

        Returns:
            ``{"ok": True, "mode": <read-back>}`` on success;
            ``{"ok": False, "mode": <current>, "reason": "busy"}`` when the
            screen never went idle; ``{"ok": False, "mode": <current>,
            "reason": "unreachable"}`` when the target is not in this session's
            armed ring (the launch pre-arm — ``--permission-mode`` /
            ``--allow-dangerously-skip-permissions`` — is a create()-time
            choice).
        """
        if not self._idle_gate(name, timeout=idle_timeout):
            return {"ok": False, "mode": self.permission_mode(name),
                    "reason": "busy"}
        current = self.permission_mode(name)
        if current == target_mode:
            return {"ok": True, "mode": current}
        for _ in range(MODE_RING_MAX + 1):
            if not self._idle_gate(name, timeout=idle_timeout):
                return {"ok": False, "mode": self.permission_mode(name),
                        "reason": "busy"}
            self.keys(name, "BTab")
            time.sleep(step_delay)
            content = self.read(name, lines=20)["content"]
            mode = parse_mode_indicator(content)
            if mode == "default" and _looks_like_optin_menu(content):
                self.keys(name, "Escape")
                time.sleep(step_delay)
                continue
            log.debug("set_permission_mode(%s): BTab -> %s (want %s)",
                      name, mode, target_mode)
            if mode == target_mode:
                return {"ok": True, "mode": mode}
        return {"ok": False, "mode": self.permission_mode(name),
                "reason": "unreachable"}

    def thinking_state(self, name, idle_timeout=5.0, poll_interval=0.5):
        """Read the extended-thinking state via the `Meta+T` modal.

        Opens the modal, reads which option carries the check mark, closes with
        Escape. Returns ``{"ok": True, "on": bool}``, or ``{"ok": False,
        "on": None, "reason": "busy" | "unreadable"}``.
        """
        if not self._idle_gate(name, timeout=idle_timeout):
            return {"ok": False, "on": None, "reason": "busy"}
        state, _ = self._open_panel_and_parse(
            name, "M-t", parse_thinking_panel, interval=poll_interval)
        self.keys(name, "Escape")  # leave the modal closed regardless
        if state is None:
            return {"ok": False, "on": None, "reason": "unreadable"}
        return {"ok": True, "on": state == "enabled"}

    def set_thinking(self, name, on, idle_timeout=5.0, poll_interval=0.5,
                     step_delay=1.2):
        """Set extended thinking ABSOLUTELY via the `Meta+T` modal.

        Open the modal, READ the current state first, toggle only if needed
        (numbered-menu digit + Enter — Enter both confirms and closes), then
        re-open to read the result back. The read-back is the returned state —
        never the value sent.

        Returns:
            ``{"ok": True, "on": bool}`` on success; ``{"ok": False, "on": None,
            "reason": "busy" | "unreadable"}`` on the honest failures.
        """
        if not self._idle_gate(name, timeout=idle_timeout):
            return {"ok": False, "on": None, "reason": "busy"}
        target = "enabled" if on else "disabled"
        state, _ = self._open_panel_and_parse(
            name, "M-t", parse_thinking_panel, interval=poll_interval)
        if state is None:
            self.keys(name, "Escape")
            return {"ok": False, "on": None, "reason": "unreadable"}
        if state == target:
            self.keys(name, "Escape")
            return {"ok": True, "on": on}
        # Numbered-menu selection by digit (1=Enabled, 2=Disabled) + Enter —
        # the proven pattern (the startup bypass gate selects "2" the same way).
        self.keys(name, "1" if on else "2")
        time.sleep(step_delay / 3)
        self.keys(name, "Enter")
        time.sleep(step_delay)
        state2, _ = self._open_panel_and_parse(
            name, "M-t", parse_thinking_panel, interval=poll_interval)
        self.keys(name, "Escape")
        if state2 is None:
            return {"ok": False, "on": None, "reason": "unreadable"}
        return {"ok": state2 == target, "on": state2 == "enabled"}

    def fast_state(self, name, idle_timeout=5.0, poll_interval=0.6):
        """Read the Fast-mode state via the `Meta+O` panel.

        Opens the panel, reads the ``Fast mode OFF/ON`` line, closes with
        Escape. Returns ``{"ok": True, "on": bool}``, or ``{"ok": False,
        "on": None, "reason": "busy" | "credit_gated" | "unreadable"}`` —
        ``credit_gated`` is the honest degrade for an account without Fast
        usage credits (the panel reports "requires usage credits" and no
        keystroke can turn Fast on).
        """
        if not self._idle_gate(name, timeout=idle_timeout):
            return {"ok": False, "on": None, "reason": "busy"}
        state, _ = self._open_panel_and_parse(
            name, "M-o", parse_fast_panel, interval=poll_interval)
        self.keys(name, "Escape")
        if state == "credit-gated":
            return {"ok": False, "on": None, "reason": "credit_gated"}
        if state is None:
            return {"ok": False, "on": None, "reason": "unreadable"}
        return {"ok": True, "on": state == "on"}

    def set_fast(self, name, on, idle_timeout=5.0, poll_interval=0.6):
        """Set Fast mode via the `Meta+O` panel — `Space` is the toggle lever.

        Open the panel, READ the current state first, `Space`-toggle only if
        needed (Enter/Escape merely CLOSE the panel), read the flipped line
        back, close. A credit-gated account degrades honestly (see
        ``fast_state``) — the toggle is never faked.

        Returns:
            ``{"ok": True, "on": bool}`` on success; ``{"ok": False, "on": None,
            "reason": "busy" | "credit_gated" | "unreadable"}`` otherwise.
        """
        if not self._idle_gate(name, timeout=idle_timeout):
            return {"ok": False, "on": None, "reason": "busy"}
        target = "on" if on else "off"
        state, _ = self._open_panel_and_parse(
            name, "M-o", parse_fast_panel, interval=poll_interval)
        if state == "credit-gated":
            self.keys(name, "Escape")
            return {"ok": False, "on": None, "reason": "credit_gated"}
        if state is None:
            self.keys(name, "Escape")
            return {"ok": False, "on": None, "reason": "unreadable"}
        if state == target:
            self.keys(name, "Escape")
            return {"ok": True, "on": on}
        self.keys(name, "Space")
        state2 = None
        for _ in range(14):
            time.sleep(poll_interval)
            state2 = parse_fast_panel(self.read(name, lines=45)["content"])
            if state2 is not None:
                break
        self.keys(name, "Escape")
        if state2 == "credit-gated":
            return {"ok": False, "on": None, "reason": "credit_gated"}
        if state2 is None:
            return {"ok": False, "on": None, "reason": "unreadable"}
        return {"ok": state2 == target, "on": state2 == "on"}

    # --- Multi-Agent ---

    def batch_create(self, agents):
        """Spin up multiple sessions from a list of configs.

        Args:
            agents: List of dicts, each with at minimum 'name'.
                    Optional keys: 'cwd', 'model', 'claude_args', 'show'.
                    'show' defaults to False (no Windows Terminal tab), matching
                    create()'s opt-in tab behavior; set it per agent to attach.

        Returns:
            list of results from create(), one per agent.
        """
        results = []
        for agent in agents:
            name = agent["name"]
            try:
                result = self.create(
                    name,
                    cwd=agent.get("cwd"),
                    model=agent.get("model"),
                    claude_args=agent.get("claude_args", ""),
                    show=agent.get("show", False),
                )
                results.append(result)
            except TmuxBridgeError as e:
                results.append({"status": "error", "name": name, "error": str(e)})
            time.sleep(1)  # stagger to avoid resource contention
        return results

    def broadcast(self, names, text, press_enter=True):
        """Send the same prompt to multiple sessions.

        Args:
            names: List of session names.
            text: The text to send.
            press_enter: Whether to press Enter after typing.

        Returns:
            list of results from send(), one per session.
        """
        results = []
        for name in names:
            try:
                result = self.send(name, text, press_enter=press_enter)
                results.append(result)
            except TmuxBridgeError as e:
                results.append({"status": "error", "name": name, "error": str(e)})
        return results

    def interrupt(self, name):
        """Send Ctrl+C to stop a running response.

        Args:
            name: Session name.

        Returns:
            dict with status.
        """
        return self.keys(name, "C-c")

    # --- Output & Monitoring ---

    def scrollback(self, name, max_lines=10000):
        """Capture full scrollback history from a session.

        Args:
            name: Session name.
            max_lines: Maximum lines to capture (default 10000).

        Returns:
            dict with full scrollback content.
        """
        self._require_session(name)
        output = self._tmux(
            f"capture-pane -t '{name}' -p -J -S -{max_lines}",
            timeout=15,
        )
        content_lines = output.rstrip("\n").split("\n") if output.strip() else []
        return {
            "status": "ok",
            "name": name,
            "lines": len(content_lines),
            "content": output,
        }

    def watch(self, name, pattern, timeout=60, interval=0.5):
        """Poll a session until output matches a regex pattern.

        Args:
            name: Session name.
            pattern: Regex pattern to match against screen content.
            timeout: Seconds before giving up (default 60).
            interval: Seconds between polls (default 0.5).

        Returns:
            dict with matched status, the match, and screen content.

        Raises:
            TmuxBridgeError: If timeout is reached without a match.
        """
        self._require_session(name)
        deadline = time.time() + timeout
        compiled = re.compile(pattern)

        while time.time() < deadline:
            screen = self.read(name, lines=50)
            content = screen["content"]
            match = compiled.search(content)
            if match:
                return {
                    "status": "matched",
                    "name": name,
                    "match": match.group(0),
                    "content": content,
                }
            time.sleep(interval)

        raise TmuxBridgeError(
            f"Timed out after {timeout}s waiting for pattern '{pattern}' in session '{name}'."
        )

    def wait_idle(self, name, timeout=120, interval=1.0):
        """Block until the agent finishes responding.

        Uses screen heuristics to detect the idle prompt.

        Args:
            name: Session name.
            timeout: Seconds before giving up (default 120).
            interval: Seconds between polls (default 1.0).

        Returns:
            dict with status and final screen content.

        Raises:
            TmuxBridgeError: If timeout is reached.
        """
        self._require_session(name)
        deadline = time.time() + timeout

        while time.time() < deadline:
            st = self.status(name)
            if st["state"] == "idle":
                return {
                    "status": "idle",
                    "name": name,
                    "content": st["screen_tail"],
                }
            if st["state"] == "permission_prompt":
                return {
                    "status": "permission_prompt",
                    "name": name,
                    "content": st["screen_tail"],
                }
            time.sleep(interval)

        raise TmuxBridgeError(
            f"Timed out after {timeout}s waiting for session '{name}' to become idle."
        )

    def export(self, name, filepath, mode="scrollback"):
        """Dump session content to a file.

        Args:
            name: Session name.
            filepath: Path to write the export to.
            mode: "scrollback" for raw screen history,
                  "log" for structured JSONL transcript.

        Returns:
            dict with status and filepath.
        """
        if mode == "scrollback":
            data = self.scrollback(name)
            content = data["content"]
        elif mode == "log":
            entries = self.read_log(name)
            content = json.dumps(entries, indent=2)
        else:
            raise TmuxBridgeError(f"Unknown export mode: '{mode}'. Use 'scrollback' or 'log'.")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return {"status": "exported", "name": name, "filepath": filepath, "mode": mode}

    # --- JSONL Transcript ---

    def read_log(self, name, last_n=None, types=None):
        """Read structured entries from the JSONL session transcript.

        Args:
            name: Session name (used to find the transcript file).
            last_n: If set, only return the last N entries.
            types: If set, filter to these message types
                   (e.g. ["user", "assistant"]).

        Returns:
            list of parsed JSONL entries (dicts).
        """
        from .transcript import find_transcript, parse_transcript
        transcript_path = find_transcript(self, name)
        if not transcript_path:
            raise TmuxBridgeError(
                f"No transcript found for session '{name}'. "
                "The session may not have processed any messages yet."
            )
        return parse_transcript(self, transcript_path, last_n=last_n, types=types)

    # --- Configuration ---

    def set_cwd(self, cwd):
        """Set the default working directory for new sessions.

        Accepts Windows or WSL paths — automatically translated.

        Args:
            cwd: The working directory path.
        """
        self._default_cwd = cwd

    def set_model(self, model):
        """Set the default model for new sessions.

        Args:
            model: Model name (e.g. "sonnet", "opus", "haiku").
        """
        self._default_model = model

    def wsl_host_ip(self):
        """The Windows-host IP reachable from inside WSL2 (the default gateway).

        In WSL2's default NAT networking the in-WSL ``localhost`` does NOT reach
        the host and ``host.docker.internal`` lands on the LAN IP (firewall-blocked
        from WSL) — both live-verified in the idle-detection hook spike — so an agent's
        HTTP hook must POST to this gateway address. Resolved once per WSL boot
        and cached. Returns the dotted-quad, or ``None`` if it can't resolve.
        """
        if self._host_ip is not None:
            return self._host_ip or None
        try:
            out = self._run("ip route show default", timeout=10)
        except Exception:
            out = ""
        self._host_ip = parse_default_gateway(out) or ""
        return self._host_ip or None

    def sidecar_hook_base_url(self, port=None):
        """The WSL-reachable sidecar base URL (``http://<host>:<port>``) the
        per-agent hooks POST to, or ``None`` if the host gateway can't be
        resolved (hooks are then omitted and launch still succeeds)."""
        ip = self.wsl_host_ip()
        if port is None:
            return sidecar_base_url(ip)
        return sidecar_base_url(ip, port=port)

    def mcp_sync(self):
        """Sync MCP server config from Windows .claude.json into WSL.

        Reads the Windows config at /mnt/c/Users/lester/.claude.json,
        extracts MCP server definitions and API keys, filters out
        Windows-only servers, and writes the config into WSL's
        ~/.claude.json.

        Returns:
            dict with status, servers synced, and servers skipped.
        """
        from .mcp import sync_mcp_config
        return sync_mcp_config(self)

    # --- Internal Helpers ---

    def _list_raw(self):
        """Get raw session data as a dict keyed by session name."""
        try:
            output = self._tmux(
                "list-sessions -F '#{session_name}|#{session_created}|#{session_attached}|#{pane_pid}|#{session_windows}'"
            )
        except TmuxBridgeError:
            # No sessions exist
            return {}

        sessions = {}
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 5:
                sessions[parts[0]] = {
                    "created": parts[1],
                    "attached": parts[2] != "0",
                    "pid": parts[3],
                    "windows": int(parts[4]) if parts[4].isdigit() else 1,
                }
        return sessions

    def _require_session(self, name):
        """Raise if the named session doesn't exist."""
        sessions = self._list_raw()
        if name not in sessions:
            available = ", ".join(sessions.keys()) if sessions else "(none)"
            raise TmuxBridgeError(
                f"Session '{name}' not found. Active sessions: {available}"
            )
