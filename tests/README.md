# Workspace tests

Workspace-level tests — things that exercise tooling shared across the whole
sandbox (not tied to a single project). Project-specific tests live in that
project's own `tests/` directory (e.g. `projects/fb-group-search/tests/`).

## Layout

| Path | Purpose |
|------|---------|
| `test_tmux_bridge.py` | Integration suite for the `cc_tmux_bridge` library (real WSL2/tmux + live TUI). |
| `conftest.py` | Shared fixtures (`bridge`, `live_session`) and per-run log-file setup. |
| `run.ps1` | Convenience runner — resolves the shared venv and invokes pytest. |
| `log/` | Timestamped DEBUG logs, one file per run. Gitignored. |

## Running

```powershell
tests\run.ps1                 # everything
tests\run.ps1 -k mcp_sync     # one test by keyword
tests\run.ps1 -m integration  # by marker
```

Or directly with the venv python:

```powershell
.\claude-code-sandbox-env\Scripts\python.exe -m pytest tests/
```

## Where to look when something fails

Console output is intentionally concise. The full story — exact WSL/tmux
commands, raw screen captures, detected states, and tracebacks — is in the
newest file under `tests/log/`.

## Conventions (apply to all new tests)

- **Framework:** pytest. Put tests in a `tests/` dir at the relevant scope.
- **Logging:** use `logging.getLogger(__name__)`; DEBUG goes to the per-run log
  file automatically. Log the raw inputs/outputs you'd want when debugging a
  failure (screens, commands, payloads) at DEBUG.
- **Markers:** tag non-hermetic tests `@pytest.mark.integration` and slow ones
  `@pytest.mark.slow` (see `pyproject.toml`).
- **Fixtures over implicit order:** share expensive setup (like a live session)
  via session-scoped fixtures rather than cross-test side effects.
