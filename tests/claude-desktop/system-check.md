# Claude Desktop toolchain smoke test

Run: 2026-06-14 (desktop app, filesystem + Playwright MCP). Re-run after full app restart with file:// enabled.

## Results

| Step | Result | Detail |
|------|--------|--------|
| 1. READ | PASS | Read CLAUDE.md; contents visible (workspace identity, folder map, Key files, cc_tmux_bridge, Testing). |
| 2. RENDER (file://) | PASS | Loaded with no "file: protocol blocked" error. Title "AWL Multi-Agent Dashboard". Console errors are one repeating fetch() failing under file://, not a styling problem (see Step 2 detail). |
| 3. SEE (screenshot) | PASS | Viewport 1600x1000; screenshot saved into the repo; the styled 3-pane layout rendered with design-tools.js applied. |
| 4. WRITE (gated) | PASS | This file and v6p3-render.png were written through the gated filesystem path; both exist on disk. |

## Step 2 detail
- Page title: AWL Multi-Agent Dashboard
- Warnings: 1. "cdn.tailwindcss.com should not be used in production." (Tailwind CDN-in-production notice.)
- Errors: a single repeating fetch() in the page (HTML line 1026) that fails under file://. The count grows on a timer (6 at load, then 78, 183, 185+ as it retries); all are the same root cause, not distinct failures.
- Verbatim error (representative pair, repeats):
  Access to fetch at 'file:///C:/Users/lester/MeDocuments/AppData/Anthropic/claude-code-sandbox/agent-dashboard/design/ui-concept-v6p3.html' from origin 'null' has been blocked by CORS policy: Cross origin requests are only supported for protocol schemes: chrome, chrome-extension, chrome-untrusted, data, http, https, isolated-app.
  Failed to load resource: net::ERR_FAILED
- Interpretation: classic script src assets like design-tools.js load fine over file://; only fetch/XHR is CORS-blocked when the origin is null (file://). This is a runtime data-poll, not an asset or styling failure, and would not occur if the page were served over http. It does not affect static render fidelity.

## Step 3 detail
- Screenshot path: C:\Users\lester\MeDocuments\AppData\Anthropic\claude-code-sandbox\tests\claude-desktop\v6p3-render.png
- Size: 226,713 bytes. Dimensions: 1600x1000 px (viewport capture, fullPage false, scale css).
- What rendered: the full styled 3-pane dashboard. Left pane is Team Graph (agent cards with context bars) and Team Feed (segmented filter controls). Middle pane is the Agent panel with Details/Create/Requests tabs and styled form fields. Right pane is the CLI transcript, the Prompts panel with Compose/Library/History tabs and Target/Source selectors, and the Revise/Send action strip. The Color Palette Reference renders below. Segmented controls, tabs, split buttons, and cards are all styled, confirming design-tools.js loaded. Not an unstyled HTML dump.

## Step 4 detail
- Paths written:
  - tests\claude-desktop\system-check.md (this file)
  - tests\claude-desktop\v6p3-render.png
- Approval: the write calls returned success. Whether the approval dialog appeared is visible on your side; from the tool side I can confirm only that the files were created.

## Verdict
ALL PASS. Read, file:// render, screenshot, and gated write are all functional. The only console noise is a repeating fetch() that cannot run under file://; it is expected and does not affect rendering.
