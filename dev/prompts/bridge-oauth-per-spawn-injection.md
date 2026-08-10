# Bridge OAuth token: per-spawn injection (stop the VS Code login hijack)

Implement, verify, and migrate — in one sprint — the change that stops the bridge's fleet credential from hijacking the operator's interactive Claude Code login, while keeping the bridge (and the whole dashboard) fully working. Deliver working code and a completed migration, not a proposal. You are running in ultracode on the real laptop with full repo + system access (real WSL2/tmux, the installed Claude build, the running sidecar); use it. The diagnosis below is settled — do not spend effort re-deriving it; spend it on a clean implementation, a rigorous verification, and a safe migration.

## The one step you cannot do — say it in your final report

The symptom the operator sees ("Auth method: Anthropic Console", "Plan limits aren't available") only clears when the VS Code **extension host restarts and re-reads its environment**. You cannot reload the operator's live IDE for them. So the single manual step at the end is theirs: **reload VS Code (or restart the extension host) and confirm `/status` shows Max (20x)**. Everything else — code, docs, token-file setup, headless verification, and the env-var/`WSLENV` removal — you do. Put this step, plainly, at the top of your final report.

## Confirmed diagnosis (settled — do not re-diagnose)

The Windows **user** environment variable `CLAUDE_CODE_OAUTH_TOKEN` (an `sk-ant-oat01-…` token minted by `claude setup-token`) is inherited by every process the operator launches — VS Code included — and Claude Code's credential precedence uses it *above* the interactive keychain login in `~/.claude/.credentials.json`. That keychain login is a healthy full-scope Max subscription; the env-var token is a `setup-token` that carries **only `user:inference` scope** (no `user:profile`). With only `user:inference`, the session cannot fetch subscription/plan/profile metadata, so the extension renders it as a degraded, non-subscription login: "Anthropic Console", "Plan limits aren't available", Max features off, Claude-in-Chrome disabled, profile-scoped MCP calls 403, and Fable asking for credits.

Proven by a non-persistent A/B on `claude auth status` (a child process with the var set vs unset — nothing persisted): var **absent** → `authMethod: "claude.ai"`, `subscriptionType: "max"`, full account; var **present** → `authMethod: "oauth_token"`, no `subscriptionType`, no plan info. The extension's own resolver classifies an OAuth token by scope (`scopes.includes("user:inference") ? "claudeai" : "console"`) and the webview maps `"console"` → "Anthropic Console"; the env-var setup-token loads without the scope metadata the keychain token carries, so it falls to the "console" label. The extension log corroborates: "env-var and setup-token sessions default to user:inference only" and "[Bootstrap] Skipped: 403 for OAuth token without profile scope".

The catch: the **bridge legitimately needs this exact token** to authenticate its headless WSL/tmux agents (they run through a non-login `wsl -- bash -c` that inherits nothing else). So the fix is not "delete the token" — it is "stop delivering it by ambient inheritance, deliver it deliberately per spawn, and remove it from the operator's inherited environment."

## What to build (intent, not line-by-line — you own the mechanics)

Today the token reaches agents by **pure ambient inheritance**: the bridge injects no auth env at all. The only env it injects is the four `GIT_*` attribution vars, prepended onto the launched `claude` command right before `tmux new-session`. Confirm the seam against current code — around `bridge/bridge.py` where `claude_cmd` is assembled (~807–869), the `GIT_*` prefix (~881–888), and the `tmux new-session -d -s …` dispatch (~894–897); the wsl wrapper `_run()` (~531–546) calls `subprocess.run` with no `env=`. `git_run`'s `env_prefix` (~2535–2538) is the existing `VAR=value`-prefix primitive to mirror. Grep `bridge/` for `CLAUDE_CODE_OAUTH_TOKEN` / `WSLENV` / `os.environ` to confirm it is injected nowhere today. (Line numbers are anchors from an earlier pass — verify against the current file; don't trust them blindly.)

Build these three pieces (you decide the exact structure, the quoting across the wsl/bash/tmux layers, the helper shape, and the file ACLs):

1. **Per-spawn token injection at the single bridge seam.** Read the token from a file and prepend `CLAUDE_CODE_OAUTH_TOKEN=<value>` onto the launched `claude` command exactly the way the `GIT_*` prefix is already done. Read it **per spawn** (spawns are infrequent; per-read means a rotated token is picked up on the next agent with no `tmux kill-server` — this also retires the documented "token change needs kill-server/reboot" wart). Every launch path funnels through `create()` — `fork()` (~2130), `batch_create()` (~2173), `resume()` (~1267), the CLI (`bridge/cli.py` ~145), and the sidecar driver (`sidecar/drivers/bridge.py` ~869) — so injecting once at the seam covers them all. `tmux new-session -e VAR=VALUE` is an acceptable equivalent; the command-prefix is the recommended default because it matches the current code and the launch-string unit tests.

2. **Token file, outside the repo.** Default `%LOCALAPPDATA%\awl-cc-dash\oauth-token`, ACL-restricted to the user, overridable via an `AWL_OAUTH_TOKEN_FILE` env var. Resolve the path in `bridge/paths.py` (the natural home, alongside `CLAUDE_BIN`). Never place it inside the repo. The bridge Python runs on Windows and reads this Windows file directly, then injects the value into the WSL command — no path translation needed. **Transitional fallback:** if the file is absent, inject nothing and let today's ambient inheritance stand. This lets the code land and be verified *before* the machine-state migration, so there is no flag-day. Fail loudly and diagnosably (a clear one-line log) if the file is present but empty/unreadable, so an auth gap never shows up only as a downstream 401.

3. **Sidecar startup token-load, for the opt-in in-process `sdk` driver.** At sidecar init (`sidecar/main.py`), read the same file and set `CLAUDE_CODE_OAUTH_TOKEN` in the **sidecar's own process env** if unset, so `sidecar/drivers/sdk.py` keeps authenticating headless. This is process-scoped, not a global var: VS Code (a sibling of the sidecar, not a child) never inherits it, and with `WSLENV` gone the sidecar's env won't cross into WSL either — so the bridge still relies on its explicit per-spawn injection, and this load only serves the in-process SDK. Keep this piece cleanly separable in case the operator later wants bridge-only.

## Migration — full hands-off, strict ordering, with rollback

Do the whole migration, but in this order, and never delete the global var before the file path is proven:

1. Land the code + docs (above).
2. **Seed the token file** from the current value of the Windows user `CLAUDE_CODE_OAUTH_TOKEN`, and ACL-lock it. This same captured value is your backup.
3. **Verify headlessly and conclusively, simulating the post-migration world** — i.e. with the ambient var *removed from the test's own environment* so you are proving the file path, not the inherited one: (a) `claude auth status` / a real bridge spawn shows an agent authenticating with **no ambient token present**, purely via the file injection; (b) a real spawned agent returns an actual model reply (not a dry run). Only a green here unlocks step 4.
4. **Back up** the old `CLAUDE_CODE_OAUTH_TOKEN` and `WSLENV` values to a saved file outside the repo, then **remove** the Windows user `CLAUDE_CODE_OAUTH_TOKEN` and its `WSLENV` entry. `WSLENV` currently holds only `CLAUDE_CODE_OAUTH_TOKEN/u`, so removing that entry means deleting `WSLENV` entirely — confirm it has no other entries first, and remove only the one entry if it does.
5. **`tmux kill-server` is optional cleanup, not required** — because injection is now explicit on the command, new spawns carry the token regardless of the server's frozen env. If you do it, do it only when no bridge agents are running; otherwise note that the stale inherited value lingers harmlessly in the old server env until the next kill/reboot.
6. Write **rollback instructions** (re-add the user var + `WSLENV`) into your report and alongside the backup.

## Testing & verification (per CLAUDE.md — required, and the real quality gate)

Use the repo `.venv` and pytest via `tests\run.ps1`; follow the existing fixtures (`bridge` / `live_session` in `tests/conftest.py` ~208–229) and marks.

- **Unit:** update the launch-string unit tests that assert the `tmux new-session` command shape / the `GIT_*` prefix (around `tests/test_git_identity_unit.py` ~166–189 and `tests/test_bridge_unit.py`) to assert the token prefix is present when a token file exists and absent when it doesn't — using a **temp file / monkeypatched path, never a real credential**.
- **Live + dashboard-functional:** prove the dashboard still works end to end — sidecar up on `:7690`, a bridge agent spawns, **authenticates**, and returns a real reply — and prove it does so via the **file path with no ambient token** (the post-migration condition). This is the gate that must be green before you remove the global var.
- Full DEBUG to `tests/log/`; keep console output concise.

## Docs to update (the repo's "update all related docs" rule — code that lands without its docs is unfinished)

- `docs/ARCHITECTURE.md` §6.4 — rewrite the "Agent authentication" bullet (~388) from "Windows user env var + `WSLENV` inheritance through the tmux server" to "gitignored file outside the repo + explicit per-spawn injection," and note the `kill-server`/reboot wart is gone. Update the spawn-command note earlier in §6.4 (~371) if you add the prefix/`-e` there.
- `CLAUDE.md` — the bridge auth sentence (~51).
- `sidecar/system_check.py` — the message string that references the `CLAUDE_CODE_OAUTH_TOKEN` env path (~154).
- The plan file `.claude/plans/context-claude-code-oauth-token-is-hijac-buzzing-bubble.md` — refresh its Context/root-cause to the **confirmed scope-based mechanism** above (it predates the confirmation).
- A **new** `DEVLOG.md` entry per the append-only rule (re-read the file from disk first; oldest→newest; include a `Files:` line).

## Guardrails / do-not

- **Never print or commit the live token value.** The token file lives outside the repo; the backup lives outside the repo; neither is ever staged.
- **Don't break the dashboard.** The bridge must be proven to authenticate from the file before the global var is removed — that ordering is not optional.
- **Same token, relocated — not a new one.** You are changing storage and delivery of the same static subscription token; the rotation-race protection that motivated a static token in the first place is preserved. Do not re-mint or switch to interactive OAuth for the bridge.
- **Follow the repo git rules** (work on `main`; branch/worktree only if isolation earns it; merge and delete branches when done; close with a one-line git check-in).
- **Bridge sessions stay tab-less** — programmatic creation never opens a terminal tab.
- Be conservative on the irreversible-feeling out-of-project step (the env-var/`WSLENV` removal): it is reversible via your backup, but only take it after the headless gate is green.

## Read first

- `CLAUDE.md` — the bridge (Custom Tooling) section, the Testing section, the DEVLOG rule, and the git rules.
- `docs/ARCHITECTURE.md` §6.4 (the current auth model you are replacing) and the §5–§6 driver/bridge map.
- `bridge/bridge.py` (the seam + `create`/`fork`/`batch_create`/`resume`/`_run`), `bridge/paths.py`, `bridge/cli.py`, `sidecar/drivers/bridge.py`, `sidecar/drivers/sdk.py`, `sidecar/main.py`, and `frontend/src/main/sidecar.ts` (how Electron spawns the sidecar with `env: {...process.env}`).
- The plan file above (the candidate approach and the full evidence) and `tests/conftest.py` (fixtures).

## Finish

Append one `DEVLOG.md` entry (re-read from disk first): what landed, the observable outcome, and a `Files:` line — before you report done. Then report back with: the manual step (VS Code reload + `/status`) at the very top; what you built and where; the headless verification result (the auth-from-file proof + the live spawn); confirmation the migration completed (var + `WSLENV` removed, backup + rollback location); whether you ran `tmux kill-server`; the test status (unit green + which live round-trips passed); and the docs updated.
