# ui-verify — headed-but-parked Playwright launcher

The single, reliable way to drive the `design/` mockups in a **real headed Chromium** for UI verification — one that opens **behind** your windows, **never steals foreground**, and **never gets throttled**. Every agent and every session invokes it the same way, so verification is consistent across runs instead of depending on whatever the shared Playwright MCP happens to be configured as.

## Why headed, and why parked

Headless (new-headless) renders our static CSS/layout essentially identically to headed, so for *pixels* it wouldn't matter. Headed earns its keep on **interaction**: mouse-event splitter drags (our `.rz-handle` resizers) script more reliably, native drag/DnD works, and — not trivially — an agent (or you) can actually *watch* what happened when something is flaky. The catch is that a headed window normally grabs focus on launch and, once covered, Chromium may pause its compositor. This tool removes both problems:

- **Parked, not minimized** — the window is pushed to the bottom of the z-order with a *no-activate* flag (`SetWindowPos(HWND_BOTTOM, SWP_NOACTIVATE)` + `ShowWindowAsync(SW_SHOWNOACTIVATE)`), and the caller's previous foreground window is restored. A window that is merely *covered* is still `visible` to the page, so nothing visibility-gated changes.
- **Anti-throttle flags** — `--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding`, `--disable-background-timer-throttling`, `--disable-features=CalculateNativeWinOcclusion` keep the renderer painting at full rate no matter what is on top of it.
- **Protocol-level I/O** — screenshots, clicks and drags travel over the DevTools protocol (the renderer surface), so window position/occlusion cannot change what an agent sees or does.

**Proven:** `npm run selftest` drives the actual `design/mockup.html` and confirms a parked window is **pixel-identical** (byte-identical) to a normal front window, that it keeps painting while occluded, that clicks and `.rz-handle` drags work parked, and that foreground is never stolen. See "Self-test" below.

## Requirements

- Windows (the park step uses Win32 via PowerShell — `win-window.ps1`).
- Node (tested on v24) and this folder's local `playwright` (pinned to **1.61.1**, whose bundled Chromium **1228** is already in the shared `ms-playwright` cache — installing reuses it, no browser download).

Install / reinstall (from this folder):

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-audit --no-fund
./node_modules/.bin/playwright install chromium   # reuses cached chromium-1228
```

`node_modules/` is gitignored; the committed tool is the four source files below.

## Usage

Self-test (the parity + behavior proof; briefly shows a window, parked):

```bash
npm run selftest
```

CLI — serve a directory and open a page parked behind your work, held until Ctrl+C:

```bash
node ui-verify.mjs --serve ../../../design --url /mockup.html --mode headed-parked
```

Programmatic (build your own verification drive):

```js
import { launch, serveDir } from './ui-verify.mjs';

const site = await serveDir('../../../design');           // http on 127.0.0.1
const app = await launch({ mode: 'headed-parked', viewport: { width: 1600, height: 1000 } });
await app.page.goto(site.url + '/mockup.html', { waitUntil: 'load' });
// ... resize to narrow/wide extremes, click every control you touched,
//     app.page.screenshot(...) each state into .scratch/ ...
await app.close();
await site.close();
```

Modes: `headed-parked` (default — headed, parked behind), `headed-front` (headed, left in front — the "normal headed" reference), `headless` (invisible; comparison only). `park()` / `toFront()` are exposed for mid-session control; both are no-ops in headless.

## Files

| File | Role |
|------|------|
| `ui-verify.mjs` | Reusable core: `serveDir()`, `launch()`, `runPs()`, plus the CLI. |
| `win-window.ps1` | Win32 helper — find the Chromium window by PID, park it (bottom + no-activate), restore prior foreground, or raise it. |
| `selftest.mjs` | Proves parked == front on the real mockup, plus not-throttled / click / drag / no-focus-theft. Writes shots + `selftest-report.json` to `<repo>/.scratch/ui-verify/`. |
| `package.json` | Pins `playwright@1.61.1`; `npm run selftest`. |

## Notes for anyone extending the self-test

- The mockup has exactly one periodic live region — the top-right `#clock` ([`design/behavior.js`](../../../design/behavior.js) `setInterval`, 1 s). It is **masked** during captures so comparisons are about rendering, not wall-clock.
- The Team Graph draws its dashed edges via `requestAnimationFrame`, and those edges have a ~sub-pixel **hysteresis** across a narrow↔wide round trip — a mockup quirk, not a window-mode effect. The self-test captures via **capture-until-stable** (shoot until two consecutive frames are byte-identical) and matches the front baseline to the parked capture's viewport-transition **path**, so parking is isolated as the only variable. The report prints the page's own front-to-front noise next to the parked delta to make that explicit.
- Screenshots and any transient output go to `<repo>/.scratch/ui-verify/` (gitignored), never the repo tree.

_Intended to be the tool referenced by the "Verifying UI changes" rule in the repo root `CLAUDE.md`._
