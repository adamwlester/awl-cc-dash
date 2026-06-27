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
from .paths import is_windows, win_to_wsl, WSL_AWL_DIR, CLAUDE_BIN

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
               settings=None, mcp_config=None):
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
            dict with session info: name, cwd, pid.

        Raises:
            TmuxBridgeError: If the session already exists or creation fails.
        """
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
        }

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

    def resume(self, name, cwd=None, model=None):
        """Reconnect to an existing session, or create if it doesn't exist.

        If the session exists in tmux, returns its info.
        If not, creates a new session with that name.

        Args:
            name: Session name.
            cwd: Working directory (only used if creating).
            model: Model flag (only used if creating).

        Returns:
            dict with session info and whether it was resumed or created.
        """
        existing = self._list_raw()
        if name in existing:
            return {
                "status": "resumed",
                "name": name,
                "pid": existing[name].get("pid"),
            }
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
