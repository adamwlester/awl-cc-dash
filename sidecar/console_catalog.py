"""Console slash-command runner catalog (OD-20).

Pure-logic catalog of Claude Code TUI slash-commands for the dashboard's
**Console** runner tab, plus the classification the runner needs to drive them.
No server, tmux, WSL2, bridge, or driver is touched here — this module only
owns the *data* (which commands exist, how they group, what each does) and the
*classification* (which commands open a sub-prompt). The live send/route
wiring — actually pushing ``/model`` into a session and handling the follow-on
picker — lives elsewhere; this module tells that wiring which commands need
follow-on handling.

Design (from the OD-20 tracker Decision, authoritative):

* A COMPLETE catalog grouped into **six clusters**, in a fixed display order:
  ``Session & context``, ``Model & behavior``, ``Info & status``,
  ``Tools & integrations``, ``Project & custom``, ``System``. Every cluster is
  non-empty.
* Each entry is a dict:
  ``{"command", "description", "cluster", "interactive", "also_in"}``.
* Commands that already have a first-class home elsewhere in the dashboard
  (e.g. ``/model`` in the Details panel, ``/mcp`` and ``/config`` in Settings)
  are still LISTED here, tagged via ``also_in`` with that panel's name — the
  Console is the complete index; the tag just points at the primary home.
* A filter box: :func:`filter_commands` does a case-insensitive substring match
  over command + description.

**Interactive commands.** Some slash-commands drop the agent into a sub-prompt
or interactive picker instead of returning a one-shot result. When the runner
sends one of these, it must handle the follow-on interaction (select a model,
confirm a clear, type a compact instruction, pick a session) rather than
blind-send-and-forget. The set we classify as interactive
(``interactive=True``) is every command that opens a picker / panel / sub-prompt
or asks for confirmation:

    /model /clear /compact /resume /config /permissions /agents /hooks
    /memory /theme /effort /export /rewind /plan /login /rename /add-dir
    /mcp /plugin /doctor /ide /statusline /review /security-review /init
    /terminal-setup /keybindings

Everything else — pure info / status / immediate toggles that render a result
without waiting on the user (``/help``, ``/status``, ``/cost``, ``/context``,
``/stats``, ``/usage``, ``/release-notes``, ``/vim``, ``/exit``, ``/diff``,
``/copy``, ``/cost`` …) — is ``interactive=False``.

Membership and descriptions are drawn from the Claude Code CLI reference
(TUI slash-commands table). This is a curated, representative set covering all
six clusters, not an exhaustive dump of every hidden/internal stub.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Optional

__all__ = [
    "CATALOG",
    "clusters",
    "by_cluster",
    "filter_commands",
    "is_interactive",
    "get",
]

# --------------------------------------------------------------------------- #
# Cluster display order (authoritative).
# --------------------------------------------------------------------------- #

_CLUSTERS: list[str] = [
    "Session & context",
    "Model & behavior",
    "Info & status",
    "Tools & integrations",
    "Project & custom",
    "System",
]


def _entry(
    command: str,
    description: str,
    cluster: str,
    *,
    interactive: bool = False,
    also_in: Optional[str] = None,
) -> dict:
    return {
        "command": command,
        "description": description,
        "cluster": cluster,
        "interactive": interactive,
        "also_in": also_in,
    }


# --------------------------------------------------------------------------- #
# The catalog. Grouped by cluster (order within a cluster is display order too).
# --------------------------------------------------------------------------- #

CATALOG: list[dict] = [
    # ----- Session & context ------------------------------------------------
    _entry("/clear", "Clear conversation history and free up context",
           "Session & context", interactive=True),
    _entry("/compact", "Clear history but keep a summary in context",
           "Session & context", interactive=True),
    _entry("/context", "Visualize current context usage as a colored grid",
           "Session & context", interactive=False),
    _entry("/resume", "Resume a previous conversation from a picker",
           "Session & context", interactive=True),
    _entry("/rewind", "Restore code and/or conversation to a previous checkpoint",
           "Session & context", interactive=True),
    _entry("/rename", "Rename the current conversation",
           "Session & context", interactive=True),
    _entry("/export", "Export the conversation to a file or clipboard",
           "Session & context", interactive=True),
    _entry("/copy", "Copy Claude's last response to the clipboard",
           "Session & context", interactive=False),
    _entry("/plan", "Enable plan mode or view the current session plan",
           "Session & context", interactive=True),
    _entry("/memory", "Edit Claude memory files (CLAUDE.md)",
           "Session & context", interactive=True),

    # ----- Model & behavior -------------------------------------------------
    _entry("/model", "Set the AI model for Claude Code",
           "Model & behavior", interactive=True, also_in="Details"),
    _entry("/effort", "Set the effort level for model usage",
           "Model & behavior", interactive=True, also_in="Details"),
    _entry("/config", "Open the interactive config / settings panel",
           "Model & behavior", interactive=True, also_in="Settings"),
    _entry("/permissions", "Manage allow & deny tool permission rules",
           "Model & behavior", interactive=True, also_in="Settings"),
    _entry("/theme", "Change the visual theme of the TUI",
           "Model & behavior", interactive=True),
    _entry("/vim", "Toggle between Vim and Normal editing modes",
           "Model & behavior", interactive=False),
    _entry("/output-style", "Change the output style (via config)",
           "Model & behavior", interactive=True, also_in="Settings"),

    # ----- Info & status ----------------------------------------------------
    _entry("/help", "Show help and available commands",
           "Info & status", interactive=False),
    _entry("/status", "Show version, model, account, API, and tool statuses",
           "Info & status", interactive=False),
    _entry("/cost", "Show total cost and duration of the current session",
           "Info & status", interactive=False),
    _entry("/stats", "Show your Claude Code usage statistics and activity",
           "Info & status", interactive=False),
    _entry("/usage", "Show plan usage limits and reset timing",
           "Info & status", interactive=False),
    _entry("/release-notes", "View release notes for the current version",
           "Info & status", interactive=False),
    _entry("/doctor", "Diagnose and verify installation and settings",
           "Info & status", interactive=True),
    _entry("/diff", "View uncommitted changes and per-turn diffs",
           "Info & status", interactive=False),

    # ----- Tools & integrations --------------------------------------------
    _entry("/mcp", "Manage MCP servers",
           "Tools & integrations", interactive=True, also_in="Settings"),
    _entry("/agents", "Manage agent configurations",
           "Tools & integrations", interactive=True, also_in="Settings"),
    _entry("/hooks", "View hook configurations for tool events",
           "Tools & integrations", interactive=True, also_in="Settings"),
    _entry("/skills", "List available skills",
           "Tools & integrations", interactive=False),
    _entry("/plugin", "Manage Claude Code plugins",
           "Tools & integrations", interactive=True),
    _entry("/ide", "Manage IDE integrations and show status",
           "Tools & integrations", interactive=True),
    _entry("/install-github-app", "Set up Claude GitHub Actions for a repository",
           "Tools & integrations", interactive=True),

    # ----- Project & custom -------------------------------------------------
    _entry("/init", "Initialize CLAUDE.md with codebase documentation",
           "Project & custom", interactive=True),
    _entry("/add-dir", "Add a new working directory for file access",
           "Project & custom", interactive=True),
    _entry("/commit", "Create a git commit from the current changes",
           "Project & custom", interactive=False),
    _entry("/review", "Review a pull request",
           "Project & custom", interactive=True),
    _entry("/security-review", "Complete a security review of pending changes",
           "Project & custom", interactive=True),
    _entry("/statusline", "Set up Claude Code's status line UI",
           "Project & custom", interactive=True),
    _entry("/tasks", "List and manage background tasks",
           "Project & custom", interactive=False),

    # ----- System -----------------------------------------------------------
    _entry("/login", "Sign in with your Anthropic account",
           "System", interactive=True),
    _entry("/logout", "Sign out from your Anthropic account",
           "System", interactive=False),
    _entry("/keybindings", "Open or create the keybindings configuration file",
           "System", interactive=True),
    _entry("/terminal-setup", "Install the Shift+Enter key binding for newlines",
           "System", interactive=True),
    _entry("/feedback", "Submit feedback about Claude Code",
           "System", interactive=False),
    _entry("/exit", "Exit the REPL",
           "System", interactive=False),
]


# --------------------------------------------------------------------------- #
# Public API.
# --------------------------------------------------------------------------- #

def clusters() -> list[str]:
    """The six cluster names, in display order (a fresh copy each call)."""
    return list(_CLUSTERS)


def by_cluster() -> dict[str, list[dict]]:
    """The catalog grouped by cluster, keyed in display order.

    Every cluster key is present (even if it were empty). Entries are deep
    copies, so callers can't mutate the module-level catalog.
    """
    grouped: dict[str, list[dict]] = {name: [] for name in _CLUSTERS}
    for entry in CATALOG:
        grouped[entry["cluster"]].append(deepcopy(entry))
    return grouped


def filter_commands(query: str) -> list[dict]:
    """Case-insensitive substring match over command + description.

    An empty / whitespace-only query returns the whole catalog (copies).
    """
    q = (query or "").strip().lower()
    if not q:
        return [deepcopy(e) for e in CATALOG]
    out: list[dict] = []
    for e in CATALOG:
        haystack = f"{e['command']} {e['description']}".lower()
        if q in haystack:
            out.append(deepcopy(e))
    return out


def is_interactive(command: str) -> bool:
    """True if ``command`` opens a sub-prompt / picker / confirmation.

    The runner must handle the follow-on interaction for these rather than
    blind-sending. Unknown commands return False (nothing to follow on).
    """
    entry = get(command)
    return bool(entry and entry["interactive"])


def get(command: str) -> Optional[dict]:
    """Return the catalog entry for ``command``, or None if not present."""
    for e in CATALOG:
        if e["command"] == command:
            return deepcopy(e)
    return None
