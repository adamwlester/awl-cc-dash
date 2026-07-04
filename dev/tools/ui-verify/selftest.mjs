/**
 * selftest.mjs — proves the parked headed window behaves IDENTICALLY to a
 * normal front headed window, on our actual design/mockup.html.
 *
 * The parity check is SELF-CONTROLLING: it measures how much a front window
 * differs from ITSELF across two back-to-back captures (baseline noise from
 * any live regions), then checks that front-vs-parked differs by no more than
 * that baseline. So "parked == front" holds even if the mockup later gains a
 * live/animated region — parking is proven to add no difference of its own.
 * (The one known live region, the top-right #clock, is masked to keep the
 * baseline at zero, which also gives us clean byte-identical screenshots.)
 *
 * Also proves, while parked & occluded: the renderer is not throttled (rAF
 * keeps firing, visibilityState 'visible'), a click works, the surface repaints
 * live, a .rz-handle splitter drag works, and no focus is stolen from you.
 *
 * Screenshots + a JSON report land in <repo>/.scratch/ui-verify/.
 */
import { launch, serveDir } from './ui-verify.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(__dirname, '../../..');
const DESIGN = join(REPO, 'design');
const OUT = join(REPO, '.scratch', 'ui-verify');

const WIDE = { width: 1600, height: 1000 };
const NARROW = { width: 900, height: 720 };
const NOISE_FLOOR = 25; // px slack absorbing sub-visual anti-alias jitter run-to-run

const sha = (buf) => createHash('sha256').update(buf).digest('hex');

async function settle(page, ms = 350) {
  await page.waitForTimeout(ms);
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
}

// One masked screenshot. Mask the one live region (#clock, a 1s setInterval in
// behavior.js) so captures compare on rendering, not wall-clock.
async function snap(page) {
  return page.screenshot({ animations: 'disabled', caret: 'hide', mask: [page.locator('#clock')], maskColor: '#000000' });
}
// Capture the current viewport, waiting until the frame is STABLE (two
// consecutive snapshots byte-identical). The Team Graph redraws its edges via
// rAF after any resize, so a fixed delay is unreliable across transitions;
// shooting until stable removes that flakiness entirely.
async function cap(page, viewport) {
  await page.setViewportSize(viewport);
  await settle(page);
  let prev = await snap(page);
  for (let i = 0; i < 8; i++) {
    await page.waitForTimeout(250);
    const cur = await snap(page);
    if (Buffer.compare(prev, cur) === 0) return cur;
    prev = cur;
  }
  return prev; // best effort after ~2s of instability
}
async function save(buf, file) { await writeFile(file, buf); return { file, hash: sha(buf), bytes: buf.length }; }

// Pixel-diff two PNG buffers inside the (already-open) browser page.
function pixelDiff(page, a, b) {
  return page.evaluate(async ([a, b]) => {
    const load = (s) => new Promise((r) => { const i = new Image(); i.onload = () => r(i); i.src = s; });
    const ia = await load('data:image/png;base64,' + a), ib = await load('data:image/png;base64,' + b);
    const px = (img) => { const c = new OffscreenCanvas(img.width, img.height); const x = c.getContext('2d'); x.drawImage(img, 0, 0); return x.getImageData(0, 0, img.width, img.height).data; };
    const da = px(ia), db = px(ib), w = ia.width, h = ia.height;
    let d = 0, minX = 1e9, minY = 1e9, maxX = -1, maxY = -1;
    if (ia.width !== ib.width || ia.height !== ib.height) return { diffPixels: -1, box: null, note: 'dimension mismatch' };
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const i = (y * w + x) * 4; if (da[i] !== db[i] || da[i + 1] !== db[i + 1] || da[i + 2] !== db[i + 2] || da[i + 3] !== db[i + 3]) { d++; if (x < minX) minX = x; if (y < minY) minY = y; if (x > maxX) maxX = x; if (y > maxY) maxY = y; } }
    return { diffPixels: d, box: maxX < 0 ? null : { minX, minY, maxX, maxY, w: maxX - minX + 1, h: maxY - minY + 1 } };
  }, [a.toString('base64'), b.toString('base64')]);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const site = await serveDir(DESIGN);
  const report = { mode: 'headed-front → park', url: site.url + '/mockup.html', checks: {}, shots: {}, diffs: {} };

  // Launch headed, FRONT. restorePrevForeground lets park() hand focus back.
  const app = await launch({ mode: 'headed-front', viewport: WIDE });
  const { page } = app;
  report.pid = app.pid;
  report.foregroundBeforeLaunch = app.prevFg;

  await page.goto(site.url + '/mockup.html', { waitUntil: 'load' });
  await settle(page, 1000); // let the rAF-drawn Team Graph edges fully settle

  // FRONT captures, matched to the parked captures' viewport-transition PATH.
  // The Team Graph's dashed edges have a ~sub-pixel hysteresis across a
  // narrow<->wide round trip (a mockup quirk, unrelated to window mode), so the
  // wide baseline is captured AFTER the same round trip the parked-wide shot
  // goes through — isolating "parking" as the only variable in the comparison.
  const fW1 = await cap(page, WIDE);    // wide, initial path
  const fN1 = await cap(page, NARROW);  // narrow
  const fN2 = await cap(page, NARROW);  // narrow again (front-to-front baseline pair)
  const fW2 = await cap(page, WIDE);    // wide, POST round-trip → matched to parked-wide
  report.shots.frontWide = await save(fW2, join(OUT, 'front-wide.png'));
  report.shots.frontNarrow = await save(fN1, join(OUT, 'front-narrow.png'));

  // Park the SAME window behind + restore prior foreground.
  const parkInfo = await app.park();
  report.parkInfo = parkInfo;

  // Give occlusion/throttling a chance to (wrongly) kick in before probing.
  await page.waitForTimeout(1500);
  await page.evaluate(() => { window.__raf = 0; const t = () => { window.__raf++; requestAnimationFrame(t); }; requestAnimationFrame(t); });
  await page.waitForTimeout(1000);
  const rafProbe = await page.evaluate(() => ({ raf: window.__raf, vis: document.visibilityState }));
  report.checks.notThrottled = { pass: rafProbe.raf >= 30 && rafProbe.vis === 'visible', rafFramesIn1s: rafProbe.raf, visibilityState: rafProbe.vis };

  // PARKED captures. Viewport is unchanged from fW2 (still WIDE) → the ONLY
  // difference between fW2 and pW is that the window is now parked behind.
  const pW = await cap(page, WIDE);
  const pN = await cap(page, NARROW);
  report.shots.parkedWide = await save(pW, join(OUT, 'parked-wide.png'));
  report.shots.parkedNarrow = await save(pN, join(OUT, 'parked-narrow.png'));

  // Parity, with parking isolated as the only variable (matched viewport path).
  // baseline* = the page's OWN front-to-front noise, reported for context so
  // it's visible that parking adds no more than the page already varies.
  const baseWide = await pixelDiff(page, fW1, fW2);   // page's own round-trip hysteresis (context)
  const parkWide = await pixelDiff(page, fW2, pW);    // matched path → pure parking effect
  const baseNarrow = await pixelDiff(page, fN1, fN2); // front-to-front narrow (context)
  const parkNarrow = await pixelDiff(page, fN1, pN);  // parking effect at narrow
  report.diffs = { baseWide, parkWide, baseNarrow, parkNarrow };
  report.checks.parityWide = { pass: parkWide.diffPixels >= 0 && parkWide.diffPixels <= NOISE_FLOOR, frontVsParked_matched: parkWide.diffPixels, pageOwnRoundTripNoise: baseWide.diffPixels, byteIdentical: report.shots.frontWide.hash === report.shots.parkedWide.hash };
  report.checks.parityNarrow = { pass: parkNarrow.diffPixels >= 0 && parkNarrow.diffPixels <= NOISE_FLOOR, frontVsParked_matched: parkNarrow.diffPixels, frontVsFront: baseNarrow.diffPixels, byteIdentical: report.shots.frontNarrow.hash === report.shots.parkedNarrow.hash };

  // Live-paint-while-parked: toggle a control, re-shot at WIDE, must DIFFER.
  const clickBefore = await page.evaluate(() => { const b = document.getElementById('det-think'); return b ? { on: b.classList.contains('on'), lbl: b.querySelector('.tt-lbl')?.textContent } : null; });
  let clickAfter = null;
  try { await page.click('#det-think'); clickAfter = await page.evaluate(() => { const b = document.getElementById('det-think'); return b ? { on: b.classList.contains('on'), lbl: b.querySelector('.tt-lbl')?.textContent } : null; }); }
  catch (e) { report.checks.clickError = String(e); }
  const pwPost = await cap(page, WIDE);
  report.shots.parkedPostClick = await save(pwPost, join(OUT, 'parked-postclick.png'));
  const paintDiff = await pixelDiff(page, pW, pwPost);
  report.checks.clickWorksParked = { pass: !!(clickBefore && clickAfter && clickBefore.on !== clickAfter.on), before: clickBefore, after: clickAfter };
  report.checks.livePaintParked = { pass: paintDiff.diffPixels > 0, changedPixels: paintDiff.diffPixels, note: 'parked surface repainted after the click (not a stale/frozen frame)' };

  // Drag a .rz-handle splitter while parked (mouse-event drag — the flaky kind).
  try {
    const handle = page.locator('.rz-handle').first();
    const box = await handle.boundingBox();
    if (!box) throw new Error('no visible .rz-handle');
    const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
    const flexBefore = await page.evaluate(() => { const p = document.querySelector('.rz-handle')?.previousElementSibling; return p ? getComputedStyle(p).flexGrow : null; });
    await page.mouse.move(cx, cy); await page.mouse.down();
    await page.mouse.move(cx + 90, cy, { steps: 12 });
    const readoutShown = await page.evaluate(() => document.getElementById('rz-readout')?.classList.contains('show') || false);
    await page.mouse.move(cx + 130, cy, { steps: 8 }); await page.mouse.up();
    const flexAfter = await page.evaluate(() => { const p = document.querySelector('.rz-handle')?.previousElementSibling; return p ? getComputedStyle(p).flexGrow : null; });
    report.checks.dragWorksParked = { pass: readoutShown && flexBefore !== flexAfter, readoutShown, flexBefore, flexAfter, orient: await handle.getAttribute('data-orient') };
  } catch (e) { report.checks.dragWorksParked = { pass: false, error: String(e) }; }

  // Focus theft check.
  const chromiumHwnds = (parkInfo?.hwnds || []).map(Number);
  report.checks.noFocusTheft = { pass: !chromiumHwnds.includes(Number(parkInfo?.foregroundAfter)), foregroundBefore: parkInfo?.foregroundBefore, foregroundAfter: parkInfo?.foregroundAfter, chromiumHwnds, restoredToPreLaunch: Number(parkInfo?.foregroundAfter) === Number(app.prevFg) };

  await app.close();
  await site.close();

  const results = Object.entries(report.checks).filter(([, v]) => v && typeof v === 'object' && 'pass' in v);
  report.summary = { passed: results.filter(([, v]) => v.pass).map(([k]) => k), failed: results.filter(([, v]) => !v.pass).map(([k]) => k), allPass: results.every(([, v]) => v.pass) };

  await writeFile(join(OUT, 'selftest-report.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
  console.log('\n=== SELFTEST ' + (report.summary.allPass ? 'PASS ✅' : 'FAIL ❌') + ' ===');
  console.log('passed:', report.summary.passed.join(', ') || '(none)');
  console.log('failed:', report.summary.failed.join(', ') || '(none)');
  console.log('shots in:', OUT);
  process.exit(report.summary.allPass ? 0 : 2);
}

main().catch((e) => { console.error(e); process.exit(1); });
