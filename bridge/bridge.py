"""
CC tmux Bridge — Core bridge class.

Programmatic control of Claude Code TUI sessions running in tmux inside WSL2.
All tmux commands are dispatched via `wsl -d Ubuntu -- bash -c '...'` when
running from Windows, or directly when running inside WSL.
"""

import json
import logging
import subprocess
import shutil
import time
import re
from .paths import is_windows, win_to_wsl, WSL_CLAUDE_DIR, CLAUDE_BIN

# Silent by default (no handler). Consumers — e.g. the pytest suite — can attach
# a handler to capture the exact WSL/tmux commands and their output at DEBUG.
log = logging.getLogger("bridge")


class TmuxBridgeError(Exception):
    """Raised when a tmux bridge operation fails."""
    pass


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

    def create(self, name, cwd=None, model=None, claude_args=""):
        """Spawn a named tmux session running the Claude Code TUI.

        Args:
            name: Session name (used as tmux session name).
            cwd: Working directory. Accepts Windows or WSL paths.
            model: Model to use (e.g. "sonnet", "opus"). Overrides default.
            claude_args: Additional CLI arguments for claude.

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
        cwd_flag = f" -c '{resolved_cwd}'" if resolved_cwd else ""

        # Build the claude launch command
        parts = [CLAUDE_BIN]
        use_model = model or self._default_model
        if use_model:
            parts.extend(["--model", use_model])
        if claude_args:
            parts.append(claude_args)

        claude_cmd = " ".join(parts)

        # Create detached tmux session
        self._run(
            f"tmux new-session -d -s '{name}'{cwd_flag} '{claude_cmd}'",
            timeout=15,
        )

        # Verify it started
        time.sleep(0.5)
        sessions = self._list_raw()
        if name not in sessions:
            raise TmuxBridgeError(f"Session '{name}' was not created. Check WSL/tmux state.")

        # Open a visible Windows Terminal tab
        self._open_wt_tab(name)

        return {
            "status": "created",
            "name": name,
            "cwd": resolved_cwd,
            "pid": sessions[name].get("pid"),
        }

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

        return {
            "status": "ok",
            "name": name,
            "state": state,
            "screen_tail": content[-500:] if content else "",
        }

    def _detect_state(self, content):
        """Heuristic state detection from screen content.

        Returns one of: "idle", "generating", "permission_prompt", "unknown".

        Screen layout (bottom of Claude Code TUI):
          ... content ...
          ────────────────  (top rule)
          ❯  <cursor>      (prompt line when idle)
          ────────────────  (bottom rule)
          ? for shortcuts   ◐ medium · /effort  (status bar)
        """
        if not content:
            return "unknown"

        lines = content.strip().split("\n")

        # The bottom 2 lines are the status bar (rule + shortcuts).
        # Content area is everything above that.
        content_lines = lines[:-2] if len(lines) > 2 else lines
        tail = "\n".join(content_lines[-8:])

        # Permission prompt patterns
        if re.search(r"(Allow|Deny|Yes.*No|approve|permission|Do you want)", tail, re.IGNORECASE):
            return "permission_prompt"

        # Claude Code idle prompt — ❯ followed by space/nbsp on its own line
        for line in content_lines[-4:]:
            stripped = line.strip()
            if re.match(r'^[❯>][\s\xa0]*$', stripped):
                return "idle"

        # Generating — braille spinner chars in the content area (not status bar)
        if re.search(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]', tail):
            return "generating"

        return "unknown"

    # --- Multi-Agent ---

    def batch_create(self, agents):
        """Spin up multiple sessions from a list of configs.

        Args:
            agents: List of dicts, each with at minimum 'name'.
                    Optional keys: 'cwd', 'model', 'claude_args'.

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
