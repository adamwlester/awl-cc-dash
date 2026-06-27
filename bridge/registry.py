"""Read-only registry/config reads for the dashboard Settings surface.

Surfaces the real MCP / plugin / config state the bridge AGENTS see — read from
the WSL-side files and CLI the agents actually load (not the Windows copies that
this host's own Claude session uses). Every read goes through a ``runner`` that
exposes ``_run(cmd, ...)`` (the ``TmuxBridge``), reusing the same cat/CLI-over-WSL
mechanism ``mcp_sync`` already relies on.

Reads ONLY — enable/disable toggles and the gated global-edit writes are a later
run, intentionally not built here. Two of these (``read_mcp_registry`` and
``build_agent_mcp_config``) also back the per-agent MCP selection at launch.
"""

import json
import shlex

from .paths import (
    CLAUDE_BIN,
    WSL_CLAUDE_DIR,
    WSL_HOME,
    WSL_KNOWN_MARKETPLACES,
    WSL_SETTINGS_JSON,
    WSL_USER_CLAUDE_JSON,
    win_to_wsl,
)


def _cat(runner, path):
    """Return a WSL file's text, or '' if it is missing/unreadable."""
    return runner._run(f"cat {shlex.quote(path)} 2>/dev/null || true")


def _load_json(runner, path, default):
    raw = _cat(runner, path)
    if not raw.strip():
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _exists(runner, path):
    return runner._run(f"test -e {shlex.quote(path)} && echo 1 || echo 0").strip() == "1"


# ---------------------------------------------------------------------------
# MCP registry (also the source for per-agent --mcp-config selection)
# ---------------------------------------------------------------------------

def _server_entry(name, cfg, enabled, scope):
    cfg = cfg or {}
    env = cfg.get("env") or {}
    return {
        "name": name,
        "scope": scope,
        "enabled": enabled,
        "transport": cfg.get("type", "stdio"),
        "command": cfg.get("command"),
        "args": cfg.get("args") or [],
        "url": cfg.get("url"),
        # Names only — never surface secret values from env.
        "env_keys": sorted(env.keys()),
    }


def read_mcp_registry(runner, project_cwd=None):
    """MCP servers by scope (user / project), each with its enabled state.

    user scope = WSL ``~/.claude.json`` ``mcpServers`` (active when present).
    project scope = ``<cwd>/.mcp.json``, gated by the project settings'
    ``enableAllProjectMcpServers`` / ``enabled``/``disabledMcpjsonServers``.
    """
    user_cfg = _load_json(runner, WSL_USER_CLAUDE_JSON, {})
    user_servers = user_cfg.get("mcpServers") or {}

    project_servers = {}
    proj_settings = {}
    if project_cwd:
        cwd = win_to_wsl(project_cwd)
        project_servers = (_load_json(runner, f"{cwd}/.mcp.json", {}).get("mcpServers") or {})
        proj_settings = _load_json(runner, f"{cwd}/.claude/settings.json", {})

    enable_all = bool(proj_settings.get("enableAllProjectMcpServers"))
    enabled_list = set(proj_settings.get("enabledMcpjsonServers") or [])
    disabled_list = set(proj_settings.get("disabledMcpjsonServers") or [])

    def proj_enabled(n):
        if n in disabled_list:
            return False
        if n in enabled_list:
            return True
        return enable_all

    return {
        "user": [_server_entry(n, c, True, "user")
                 for n, c in sorted(user_servers.items())],
        "project": [_server_entry(n, c, proj_enabled(n), "project")
                    for n, c in sorted(project_servers.items())],
    }


def build_agent_mcp_config(runner, selected, project_cwd=None):
    """Build a per-agent ``{"mcpServers": {...}}`` for a chosen subset of servers.

    ``selected`` is a list of server names to scope the agent to (drawn from the
    user + project registries). Unknown names are skipped. The returned dict is
    what ``TmuxBridge.create(mcp_config=...)`` writes to the per-agent file and
    passes with ``--mcp-config``/``--strict-mcp-config``. An empty selection
    yields ``{"mcpServers": {}}`` — a valid "no servers" scope.
    """
    user_cfg = _load_json(runner, WSL_USER_CLAUDE_JSON, {})
    available = dict(user_cfg.get("mcpServers") or {})
    if project_cwd:
        cwd = win_to_wsl(project_cwd)
        available.update(_load_json(runner, f"{cwd}/.mcp.json", {}).get("mcpServers") or {})
    chosen = {name: available[name] for name in (selected or []) if name in available}
    return {"mcpServers": chosen}


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------

def read_plugins(runner):
    """Installed plugins (authoritative enabled state) + known marketplaces.

    ``claude plugin list --json`` is the resolver of record for enabled state
    (the settings files don't persist it in a single readable place); each entry
    carries id/version/scope/enabled/installPath. Marketplaces come from
    ``known_marketplaces.json``.
    """
    try:
        raw = runner._run(f"{shlex.quote(CLAUDE_BIN)} plugin list --json 2>/dev/null || true")
        installed = json.loads(raw) if raw.strip() else []
    except Exception:
        installed = []

    plugins = []
    for p in installed if isinstance(installed, list) else []:
        pid = p.get("id", "")
        name, _, marketplace = pid.partition("@")
        plugins.append({
            "id": pid,
            "name": name,
            "marketplace": marketplace,
            "version": p.get("version"),
            "scope": p.get("scope"),
            "enabled": bool(p.get("enabled")),
            "installPath": p.get("installPath"),
            "installedAt": p.get("installedAt"),
        })

    mkts = _load_json(runner, WSL_KNOWN_MARKETPLACES, {})
    marketplaces = []
    for n, m in sorted((mkts or {}).items()):
        src = m.get("source") or {}
        marketplaces.append({
            "name": n,
            "source": src.get("source"),
            "repo": src.get("repo"),
            "installLocation": m.get("installLocation"),
            "lastUpdated": m.get("lastUpdated"),
        })
    return {"installed": plugins, "marketplaces": marketplaces}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Per the DESIGN Config table + the permission research: model/effort reach a
# running session live (/model, /effort); permission-mode/sandbox/env/plans are
# read at startup (New session); hooks + CLAUDE.md are read-only/re-read live.
_CONFIG_TENOR = {
    "model": "Live",
    "effort": "Live",
    "permissionMode": "New session",
    "sandbox": "New session",
    "env": "New session",
    "hooks": "Live",
    "claudeMd": "Live",
    "plansDirectory": "New session",
}


def read_config(runner, project_cwd=None):
    """Config-tab readouts from the global + project settings files.

    Global = WSL ``~/.claude/settings.json`` (user-scope, what agents load).
    Project = ``<cwd>/.claude/settings.json``. Each field carries a Live vs
    New-session tag (``tenor``) per the DESIGN Config contract.
    """
    g = _load_json(runner, WSL_SETTINGS_JSON, {})
    g_perms = g.get("permissions") or {}
    glob = {
        "model": g.get("model"),
        "effort": g.get("effortLevel") or g.get("effort"),
        "permissionMode": g_perms.get("defaultMode") or g.get("permissionMode"),
        "sandbox": g.get("sandbox"),
        "env": g.get("env") or {},
        "hooks": sorted((g.get("hooks") or {}).keys()),
        "tui": g.get("tui"),
        "theme": g.get("theme"),
        "permissions": {
            "allow": g_perms.get("allow") or [],
            "deny": g_perms.get("deny") or [],
            "ask": g_perms.get("ask") or [],
        },
        "raw_keys": sorted(g.keys()),
    }

    project = None
    claude_md = [{
        "scope": "user",
        "path": f"{WSL_CLAUDE_DIR}/CLAUDE.md",
        "exists": _exists(runner, f"{WSL_CLAUDE_DIR}/CLAUDE.md"),
    }, {
        "scope": "home",
        "path": f"{WSL_HOME}/CLAUDE.md",
        "exists": _exists(runner, f"{WSL_HOME}/CLAUDE.md"),
    }]
    if project_cwd:
        cwd = win_to_wsl(project_cwd)
        p = _load_json(runner, f"{cwd}/.claude/settings.json", {})
        perms = p.get("permissions") or {}
        project = {
            "model": p.get("model"),
            "permissionMode": perms.get("defaultMode") or p.get("permissionMode"),
            "permissions": {
                "allow": perms.get("allow") or [],
                "deny": perms.get("deny") or [],
                "ask": perms.get("ask") or [],
                "additionalDirectories": perms.get("additionalDirectories") or [],
            },
            "sandbox": p.get("sandbox"),
            "env": p.get("env") or {},
            "hooks": sorted((p.get("hooks") or {}).keys()),
            "enableAllProjectMcpServers": p.get("enableAllProjectMcpServers"),
            "plansDirectory": p.get("plansDirectory"),
            "agent": p.get("agent"),
            "raw_keys": sorted(p.keys()),
        }
        claude_md.append({
            "scope": "project",
            "path": f"{cwd}/CLAUDE.md",
            "exists": _exists(runner, f"{cwd}/CLAUDE.md"),
        })

    return {
        "global": glob,
        "project": project,
        "claudeMd": claude_md,
        "tenor": _CONFIG_TENOR,
    }
