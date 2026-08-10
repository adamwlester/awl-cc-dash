# Fix: stop the bridge's fleet OAuth token from hijacking interactive Claude Code sessions

> **Status: IMPLEMENTED + MIGRATED 2026-08-10** (per `dev/prompts/bridge-oauth-per-spawn-injection.md`). Per-spawn injection landed at the `create()` seam, the token file is seeded at `%LOCALAPPDATA%\awl-cc-dash\oauth-token`, and the Windows user env var + `WSLENV` entry were removed after the headless no-ambient-token verification passed. See DEVLOG 2026-08-10 and ARCHITECTURE §6.4.

## Context (root cause CONFIRMED 2026-08-10 — scope-based mechanism)

The bridge's fleet credential is silently overriding the operator's own interactive Claude Code login. `CLAUDE_CODE_OAUTH_TOKEN` is stored as a Windows **user** environment variable (`HKEY_CURRENT_USER\Environment`) plus `WSLENV=CLAUDE_CODE_OAUTH_TOKEN/u`. A user-scoped env var is inherited by *every* process the operator launches — including VS Code — and Claude Code's credential precedence puts that env-var token above the interactive keychain login in `~/.claude/.credentials.json`. **The confirmed mechanism is scope, not just precedence:** the env-var token is a `claude setup-token` product carrying **only `user:inference` scope** (no `user:profile`), while the overridden keychain login is a healthy full-scope Max subscription. With only `user:inference`, the session cannot fetch subscription/plan/profile metadata, so the extension renders a degraded non-subscription login: "Anthropic Console", "Plan limits aren't available", Max features off, Claude-in-Chrome disabled, profile-scoped MCP calls 403, Fable asking for credits. Proven by a non-persistent A/B on `claude auth status` (a child process with the var set vs unset — nothing persisted): var **absent** → `authMethod: "claude.ai"`, `subscriptionType: "max"`, full account; var **present** → `authMethod: "oauth_token"`, no `subscriptionType`, no plan info. The extension's own resolver classifies an OAuth token by scope (`scopes.includes("user:inference") ? "claudeai" : "console"`) and the webview maps `"console"` → "Anthropic Console"; the env-var setup-token loads without the scope metadata the keychain token carries, so it falls to the "console" label. The extension log corroborates: "env-var and setup-token sessions default to user:inference only" and "[Bootstrap] Skipped: 403 for OAuth token without profile scope". The claude.ai web app is unaffected because it never sees this env var.

The token is doing its intended job (subscription auth for bridge-launched agents, deliberately static to dodge the OAuth refresh-token rotation race that wiped WSL credentials on 2026-07-14 — [docs/ARCHITECTURE.md:388](../../docs/ARCHITECTURE.md#L388), [DEVLOG.md:31](../../DEVLOG.md#L31)). The problem is purely the **storage scope**: a global env var instead of a scoped, deliberate injection.

**Root cause in code:** the token reaches agents by 100% ambient inheritance. The bridge reads *no* environment variables — a repo-wide search found zero code references to `CLAUDE_CODE_OAUTH_TOKEN`/`WSLENV` (only docs and one message string at [sidecar/system_check.py:154](../../sidecar/system_check.py#L154)). The chain is: Windows user env var → VS Code/shell → Electron → sidecar ([frontend/src/main/sidecar.ts:138-143](../../frontend/src/main/sidecar.ts#L138-L143), inherits full `process.env`) → `wsl.exe` (spawned with **no** `env=` at [bridge/bridge.py:531-546](../../bridge/bridge.py#L531-L546)) → tmux server env → agent.

**Intended outcome:** the bridge injects the token *deliberately, per spawn*, from a file outside the repo, so the global env var + `WSLENV` can be deleted — which un-overrides the operator's interactive Max login while keeping every bridge agent authenticated.

## Feasibility summary (answers to the five questions)

1. **Per-spawn injection — yes.** One spawn seam: the bridge builds `claude_cmd` and prepends git-identity env vars at [bridge/bridge.py:881-888](../../bridge/bridge.py#L881-L888), feeding `tmux new-session` at [bridge/bridge.py:894-897](../../bridge/bridge.py#L894-L897). A `CLAUDE_CODE_OAUTH_TOKEN=<val>` prefix added the same way is sufficient. Reusable precedent: `git_run`'s `env_prefix` at [bridge/bridge.py:2535-2538](../../bridge/bridge.py#L2535-L2538).
2. **Delete the global var + WSLENV — yes.** No code reads them; once injection is explicit they are dead, and removing them stops VS Code (and every interactive process) from inheriting the token.
3. **Rotation-race protection preserved — yes.** Same static, non-refreshing token; only its storage location and delivery change. The anti-race property is intact.
4. **Removes the `tmux kill-server`/reboot wart — yes.** The wart exists because delivery flows through the frozen tmux **server** env. Per-spawn injection reads the current file value each `create()`, so a rotated token takes effect on the next spawned agent with no server restart.
5. **Blast radius — small:** one code file ([bridge/bridge.py](../../bridge/bridge.py)) for the core fix, a few launch-string unit tests, three docs, and an operator migration step. Remaining ambient-dependent paths: the opt-in in-process `sdk` driver (addressed by the optional sidecar step below) and manual `claude` run directly in an interactive WSL shell (falls back to WSL-side login — expected).

## Recommended approach (decisions locked)

- **Store:** token in a file **outside the repo** — default `%LOCALAPPDATA%\awl-cc-dash\oauth-token`, overridable via an `AWL_OAUTH_TOKEN_FILE` env var. ACL-restricted to the user, never in git.
- **Inject:** **command-prefix**, mirroring the existing `GIT_*` prefix — minimal refactor, matches current code and unit-test shape.
- **sdk driver:** small skippable add-on — sidecar reads the same file into *its own* process env at startup (process-scoped, not global) so the in-process SDK path also authenticates.
- **Safe rollout ordering** (each step reversible, no flag-day): land code first with a **transitional fallback** (if the file is absent, inject nothing → existing ambient inheritance still works) → verify agents still auth → place the file → verify → delete the global var + `WSLENV` → verify VS Code shows Max → one-time `tmux kill-server` to clear the stale server env.

## Implementation

### 1. Token read helper (bridge)
- Add a path resolver to [bridge/paths.py](../../bridge/paths.py) (which already centralizes `CLAUDE_BIN` etc.): resolve `AWL_OAUTH_TOKEN_FILE` else default `%LOCALAPPDATA%\awl-cc-dash\oauth-token`.
- Add `_read_oauth_token()` to [bridge/bridge.py](../../bridge/bridge.py): read + strip the file, return `None` if missing/empty. Read **per spawn** (spawns are infrequent; per-read gives immediate rotation pickup). On missing file, log a clear one-line warning so an auth gap is diagnosable rather than a silent 401.

### 2. Inject at the spawn seam (bridge)
- At the `claude_cmd` build site [bridge/bridge.py:881-890](../../bridge/bridge.py#L881-L890), after the `GIT_*` prefix, prepend `CLAUDE_CODE_OAUTH_TOKEN={shlex.quote(token)} ` **only when** `_read_oauth_token()` returns a value. When it returns `None`, inject nothing (transitional fallback → ambient inheritance still works until migration completes). All launch paths (`create`, and the `fork`/`batch_create`/`resume`/CLI wrappers) route through this one site, so no per-caller changes.

### 3. sdk-driver coverage (sidecar — small, skippable)
- At sidecar startup ([sidecar/main.py](../../sidecar/main.py) app-init), read the same token file and, if present and not already set, load it into the sidecar's own `os.environ` so the in-process `sdk` driver ([sidecar/drivers/](../../sidecar/drivers/)) authenticates without the global var. Process-scoped only — nothing global, VS Code unaffected.

### 4. Tests
- Update the launch-string unit tests that assert command shape to expect the token prefix when a token file is present, and its absence when not — using a monkeypatched path / temp file, never a real credential. Representative files: [tests/test_git_identity_unit.py:166-189](../../tests/test_git_identity_unit.py#L166-L189), [tests/test_bridge_unit.py](../../tests/test_bridge_unit.py). Mirror the existing `GIT_*`-prefix assertions.
- Live tests ([tests/conftest.py:219-229](../../tests/conftest.py#L219-L229) `live_session` and the `*_live.py` suite) already spawn real agents; after migration they authenticate via the same file — ensure the file exists in the run environment.

### 5. Docs (propagate the design change)
- [docs/ARCHITECTURE.md:388](../../docs/ARCHITECTURE.md#L388) (§6.4 auth bullet) — rewrite from "Windows user env var + WSLENV inheritance" to "gitignored file outside the repo + explicit per-spawn injection"; note the wart is removed. Adjust the spawn-command note at [docs/ARCHITECTURE.md:371](../../docs/ARCHITECTURE.md#L371) to show the token prefix.
- [CLAUDE.md:51](../../CLAUDE.md#L51) — update the bridge auth sentence to match.
- Update the message string at [sidecar/system_check.py:154](../../sidecar/system_check.py#L154) to reference the file path rather than "the CLAUDE_CODE_OAUTH_TOKEN env path."
- New append-only [DEVLOG.md](../../DEVLOG.md) entry recording the change.

### 6. Operator migration (documented — run/approved by operator, NOT done by code)
Not executed as part of the code change; the code's transitional fallback means it can land first, and these steps flip the source afterward:
1. Capture current value: `[Environment]::GetEnvironmentVariable("CLAUDE_CODE_OAUTH_TOKEN","User")`.
2. Write it to `%LOCALAPPDATA%\awl-cc-dash\oauth-token` (create dir; restrict ACL to the user).
3. Verify a bridge spawn authenticates (one agent / a live test) — should still pass.
4. Delete the global var: `[Environment]::SetEnvironmentVariable("CLAUDE_CODE_OAUTH_TOKEN",$null,"User")`; remove `CLAUDE_CODE_OAUTH_TOKEN` from `WSLENV` (delete `WSLENV` entirely if it holds only that).
5. Restart VS Code / open a fresh shell so it no longer inherits the var.
6. One-time `tmux kill-server` to clear the stale server env carrying the old token (afterward never needed for token changes).

## Files to modify

- **Code:** [bridge/bridge.py](../../bridge/bridge.py) (helper + injection), [bridge/paths.py](../../bridge/paths.py) (path resolver), [sidecar/main.py](../../sidecar/main.py) (optional sdk coverage), [sidecar/system_check.py](../../sidecar/system_check.py) (message string).
- **Tests:** [tests/test_git_identity_unit.py](../../tests/test_git_identity_unit.py), [tests/test_bridge_unit.py](../../tests/test_bridge_unit.py) (and any sibling launch-string unit tests asserting the `new-session` command).
- **Docs:** [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) (§6.4 + spawn-command note), [CLAUDE.md](../../CLAUDE.md), [DEVLOG.md](../../DEVLOG.md).
- **Not repo:** the token file at `%LOCALAPPDATA%\awl-cc-dash\oauth-token`, and the operator's env-var/WSLENV deletion.

## Verification (end to end)

1. **Unit:** `tests\run.ps1` (or targeted pytest) — launch-string tests assert the token prefix appears given a temp token file and is absent without one.
2. **Live auth (pre-migration, fallback path):** with the code landed and the global var still present, spawn one bridge agent and confirm a real model reply, not `401 Invalid bearer token` — same check as the 2026-07-15 verification.
3. **Live auth (post-migration, file path):** with the file placed and the global var deleted, spawn a bridge agent (`python -m bridge create ...` or a `*_live.py` test) → real model reply.
4. **Interactive hijack resolved:** in a fresh VS Code terminal, `Get-ChildItem Env:CLAUDE_CODE_OAUTH_TOKEN` returns nothing; the Claude Code extension reports **Max (20x)** (not "Anthropic Console"), and Fable stops prompting for credits.
5. **Wart removed / rotation:** change the token file value, spawn a *new* agent → it picks up the new value with **no** `tmux kill-server`. Already-running agents keep the old token (expected).
6. **sdk path (if covered):** select the `sdk` driver and confirm it authenticates with the global var gone.

## Risks / notes

- **Local same-user token visibility:** the command-prefix puts the token literal in the tmux pane start-command, readable via `tmux display -p '#{pane_start_command}'` by the same user. This is no worse than today (`tmux show-environment` already exposes the inherited var) and is local/same-user only. If ever a concern, the `-e` variant or WSL-side command-substitution reduces it.
- **Manual interactive WSL `claude`:** after the global var is gone, a `claude` you run by hand in a WSL shell no longer gets the token ambiently — it uses its own WSL-side login. Expected and correct; the bridge path is unaffected.
- **Adopted sidecar:** if a sidecar was started manually before the code change (adopt-vs-spawn at [frontend/src/main/sidecar.ts](../../frontend/src/main/sidecar.ts)), restart it so it picks up the new injection / optional token-file load.
