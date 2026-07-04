/**
 * ui-verify.mjs — the reusable substrate for UI verification of the design/ mockups.
 *
 * Launches a REAL headed Chromium, then parks it at the bottom of the Windows
 * z-order with a no-activate flag so it never steals your foreground and never
 * covers your work — while anti-throttle flags keep the renderer painting at
 * full rate even when occluded. Screenshots / clicks / drags travel over the
 * DevTools protocol (renderer surface), so window position cannot change what
 * an agent sees or does: parked renders identically to a normal front window.
 *
 * Exports: serveDir(), runPs(), launch().  Also a small CLI (see bottom).
 */
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname, normalize, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PS1 = join(__dirname, 'win-window.ps1');

/**
 * Chromium flags that keep an occluded/backgrounded window rendering at full
 * rate. Without --disable-features=CalculateNativeWinOcclusion in particular,
 * a window covered by yours can have its compositor paused on Windows — which
 * would make a "hidden headed" window secretly stop painting (worse than
 * headless). These make parking safe.
 */
export const ANTI_THROTTLE = [
  '--disable-backgrounding-occluded-windows',
  '--disable-renderer-backgrounding',
  '--disable-background-timer-throttling',
  '--disable-features=CalculateNativeWinOcclusion',
];

/** Spawn the Win32 PowerShell helper and parse its single JSON line. */
export function runPs(command, { targetPid = 0, restoreHwnd = 0, timeoutMs = 4000 } = {}) {
  return new Promise((res, rej) => {
    const args = [
      '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
      '-File', PS1,
      '-Command', command,
      '-TargetPid', String(targetPid),
      '-RestoreHwnd', String(restoreHwnd),
      '-TimeoutMs', String(timeoutMs),
    ];
    const p = spawn('powershell.exe', args, { windowsHide: true });
    let out = '', err = '';
    p.stdout.on('data', d => (out += d));
    p.stderr.on('data', d => (err += d));
    p.on('error', rej);
    p.on('close', (code) => {
      const line = out.split(/\r?\n/).map(s => s.trim()).filter(Boolean).reverse().find(s => s.startsWith('{'));
      if (!line) return rej(new Error(`win-window.ps1 ${command} produced no JSON (exit ${code}). stderr: ${err.trim()}`));
      try {
        const obj = JSON.parse(line);
        // PS5.1 unwraps single-element arrays — normalise hwnds back to an array.
        if (obj.hwnds != null && !Array.isArray(obj.hwnds)) obj.hwnds = [obj.hwnds];
        if (obj.hwnds == null) obj.hwnds = [];
        res(obj);
      } catch (e) { rej(new Error(`bad JSON from win-window.ps1: ${line} :: ${e.message}`)); }
    });
  });
}

const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
  '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf',
  '.map': 'application/json',
};

/** Serve a directory over http://127.0.0.1 (file: is blocked for module scripts). */
export async function serveDir(rootDir, { host = '127.0.0.1', port = 0, indexFile = 'mockup.html' } = {}) {
  const root = resolve(rootDir);
  const server = createServer(async (req, res) => {
    try {
      let p = decodeURIComponent((req.url || '/').split('?')[0]);
      if (p === '/' || p === '') p = '/' + indexFile;
      const fp = normalize(join(root, p));
      if (!fp.startsWith(root)) { res.writeHead(403); return res.end('forbidden'); }
      const body = await readFile(fp);
      res.writeHead(200, { 'content-type': MIME[extname(fp).toLowerCase()] || 'application/octet-stream' });
      res.end(body);
    } catch { res.writeHead(404); res.end('not found'); }
  });
  await new Promise((r) => server.listen(port, host, r));
  const addr = server.address();
  return { url: `http://${host}:${addr.port}`, port: addr.port, close: () => new Promise((r) => server.close(r)) };
}

/**
 * Launch Chromium in one of three modes:
 *   'headed-parked'  headed, immediately parked behind (the default product mode)
 *   'headed-front'   headed, left in front (the "normal headed" reference)
 *   'headless'       new-headless (invisible; for comparison only)
 *
 * Returns { browser, context, page, pid, prevFg, park(), toFront(), parkInfo }.
 * park()/toFront() are no-ops in headless mode.
 */
export async function launch({
  mode = 'headed-parked',
  viewport = { width: 1440, height: 960 },
  deviceScaleFactor = 1,
  restorePrevForeground = true,
} = {}) {
  const headless = mode === 'headless';
  const headed = !headless;

  // Capture the caller's foreground BEFORE launch so park() can hand it back.
  let prevFg = 0;
  if (headed && restorePrevForeground) {
    try { prevFg = (await runPs('foreground')).foreground || 0; } catch { /* non-fatal */ }
  }

  // launchServer + connect so we can read the browser process PID (used to find
  // its OS window). chromium.launch() gives no process handle in Playwright.
  const server = await chromium.launchServer({
    headless,
    args: headed
      ? [...ANTI_THROTTLE, '--window-position=40,40', `--window-size=${viewport.width + 80},${viewport.height + 160}`]
      : [],
  });
  const pid = server.process()?.pid || 0;
  const browser = await chromium.connect(server.wsEndpoint());
  const context = await browser.newContext({ viewport, deviceScaleFactor });
  const page = await context.newPage();

  let parkInfo = null;
  async function park() {
    if (!headed) return null;
    parkInfo = await runPs('park', { targetPid: pid, restoreHwnd: restorePrevForeground ? prevFg : 0 });
    return parkInfo;
  }
  async function toFront() {
    if (!headed) return null;
    return runPs('front', { targetPid: pid });
  }
  async function close() {
    try { await browser.close(); } catch { /* ignore */ }
    try { await server.close(); } catch { /* ignore */ }
  }

  if (mode === 'headed-parked') await park();

  return {
    browser, server, context, page, pid, prevFg, park, toFront, close,
    get parkInfo() { return parkInfo; },
  };
}

/* ------------------------------- tiny CLI -------------------------------- */
const isMain = (() => {
  try { return process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url)); }
  catch { return false; }
})();

if (isMain) {
  const argv = process.argv.slice(2);
  const opt = (name, def) => { const i = argv.indexOf(name); return i >= 0 && argv[i + 1] ? argv[i + 1] : def; };
  const serveArg = opt('--serve', resolve(__dirname, '../../../design'));
  const urlPath = opt('--url', '/mockup.html');
  const mode = opt('--mode', 'headed-parked');

  (async () => {
    const site = await serveDir(serveArg);
    const app = await launch({ mode });
    const full = site.url + (urlPath.startsWith('/') ? urlPath : '/' + urlPath);
    await app.page.goto(full, { waitUntil: 'load' });
    console.log(JSON.stringify({ serving: serveArg, url: full, mode, pid: app.pid, parkInfo: app.parkInfo }, null, 2));
    console.log('\nWindow is live (parked behind your work if headed-parked). Press Ctrl+C to close.');
    const shutdown = async () => { try { await app.close(); } catch {} try { await site.close(); } catch {} process.exit(0); };
    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
  })().catch((e) => { console.error(e); process.exit(1); });
}
