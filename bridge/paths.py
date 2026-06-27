"""
Path translation between Windows and WSL2.
"""

import platform
import re


def is_windows():
    """Check if we're running on Windows."""
    return platform.system() == "Windows"


def is_wsl():
    """Check if we're running inside WSL."""
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except FileNotFoundError:
        return False


def win_to_wsl(path):
    """Convert a Windows path to its WSL mount equivalent.

    C:\\Users\\lester\\foo  →  /mnt/c/Users/lester/foo
    C:/Users/lester/foo   →  /mnt/c/Users/lester/foo
    Already a Unix path   →  returned as-is
    """
    if not path:
        return path
    # Already a unix path
    if path.startswith("/"):
        return path
    # Normalize backslashes
    path = path.replace("\\", "/")
    # Match drive letter
    match = re.match(r"^([A-Za-z]):/(.*)$", path)
    if match:
        drive = match.group(1).lower()
        rest = match.group(2)
        return f"/mnt/{drive}/{rest}"
    return path


def wsl_to_win(path):
    """Convert a WSL mount path to Windows equivalent.

    /mnt/c/Users/lester/foo  →  C:\\Users\\lester\\foo
    Non-mount path           →  returned as-is
    """
    if not path:
        return path
    match = re.match(r"^/mnt/([a-z])/(.*)$", path)
    if match:
        drive = match.group(1).upper()
        rest = match.group(2).replace("/", "\\")
        return f"{drive}:\\{rest}"
    return path


# WSL home directory for the default user
WSL_HOME = "/home/lester"

# Claude Code config paths
WSL_CLAUDE_DIR = f"{WSL_HOME}/.claude"
WSL_CLAUDE_PROJECTS = f"{WSL_CLAUDE_DIR}/projects"
WSL_CLAUDE_SESSIONS = f"{WSL_CLAUDE_DIR}/sessions"

# The WSL-side user config the bridge AGENTS actually read (user-scope MCP
# servers live here, distinct from the Windows file `mcp_sync` copies FROM).
WSL_USER_CLAUDE_JSON = f"{WSL_HOME}/.claude.json"
# Global (user-scope) settings the WSL agents read.
WSL_SETTINGS_JSON = f"{WSL_CLAUDE_DIR}/settings.json"
# Plugin registry files (user/project/local plugins + marketplaces).
WSL_PLUGINS_DIR = f"{WSL_CLAUDE_DIR}/plugins"
WSL_INSTALLED_PLUGINS = f"{WSL_PLUGINS_DIR}/installed_plugins.json"
WSL_KNOWN_MARKETPLACES = f"{WSL_PLUGINS_DIR}/known_marketplaces.json"

# Where per-agent launch config (settings.json / mcp.json) is materialized, one
# subdir per tmux session name. WSL-reachable so claude's --settings/--mcp-config
# launch flags resolve it; kept out of ~/.claude so it never pollutes real config.
WSL_AWL_DIR = f"{WSL_HOME}/.awl-agents"

# Windows Claude config accessible from WSL
WIN_CLAUDE_JSON = "/mnt/c/Users/lester/.claude.json"

# Claude Code native binary path inside WSL
CLAUDE_BIN = f"{WSL_HOME}/.local/bin/claude"

