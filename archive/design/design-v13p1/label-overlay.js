/* ============================================================================
 * label-overlay.js — DEV-ONLY component-label overlay for mockup.html (Ctrl+L).
 *
 * Draws a small tag over the live mockup for every [data-comp] component root,
 * showing its canonical slug (one label per slug, anchored on the first
 * visible instance, with an "×N" count when several instances are visible;
 * hovering a label outlines every instance of that slug). Toggle with Ctrl+L;
 * a second Ctrl+L removes everything.
 *
 * DEV TOOLING, NOT DESIGN SYSTEM: like mockup-toolkit.js, this file sits
 * OUTSIDE the five-file design system (see design/DESIGN.md → Component
 * system → "Dev-only view tooling") — it is exempt from the propagation rule,
 * deliberately uses no tokens.css values (so it never reads as product UI),
 * and NEVER mutates the mockup's DOM (labels and hover-outlines are drawn in
 * its own fixed overlay layer appended to <body>, outside .app).
 *
 * It stores nothing per component: every draw re-queries [data-comp] and
 * recomputes positions from the live layout (getBoundingClientRect), so
 * renames, re-renders, and layout changes flow through automatically. It
 * redraws on window resize, any scroll (capture phase, so inner panels
 * count), pointer movement while a button is held (splitter drags), and DOM
 * mutations inside .app (a MutationObserver — the overlay's own layer lives
 * outside .app, so it can't observe itself).
 *
 * Keystroke note: Ctrl+L normally focuses the browser address bar; while the
 * mockup has focus this handler preventDefault()s it — the same class of
 * override mockup-toolkit.js already makes with Ctrl+G (browser find-next).
 * No collision in-repo: the toolkit owns Ctrl+G (+ Escape while active) and
 * behavior.js binds only Enter/Escape inside inputs.
 * ========================================================================== */
(function () {
  'use strict';

  let active = false;
  let layer = null;   // fixed, pointer-events:none host for labels + outlines
  let hud = null;     // tiny corner state pill
  let raf = 0;
  let observer = null;

  const MONO = '600 9.5px "JetBrains Mono", Consolas, monospace';

  function ensureLayer() {
    if (layer) return;
    layer = document.createElement('div');
    layer.id = 'lo-layer';
    layer.style.cssText = 'position:fixed;inset:0;z-index:99990;pointer-events:none;display:none;';
    document.body.appendChild(layer);
    hud = document.createElement('div');
    hud.id = 'lo-hud';
    hud.style.cssText = 'position:fixed;right:12px;bottom:12px;z-index:99991;display:none;pointer-events:none;' +
      'background:#14162b;color:#fff;border:2px solid #fff;border-radius:6px;padding:5px 10px;' +
      'font:' + MONO + ';box-shadow:0 4px 16px rgba(0,0,0,.5);';
    document.body.appendChild(hud);
  }

  /* Viewport-space rect of el, clipped by every overflow-clipping ancestor and
     the viewport; null when nothing of it is actually visible. */
  function clipRect(el) {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return null;
    let L = r.left, T = r.top, R = r.right, B = r.bottom;
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (/(auto|scroll|hidden|clip)/.test(cs.overflow + cs.overflowX + cs.overflowY)) {
        const ar = a.getBoundingClientRect();
        L = Math.max(L, ar.left); T = Math.max(T, ar.top);
        R = Math.min(R, ar.right); B = Math.min(B, ar.bottom);
        if (R - L <= 1 || B - T <= 1) return null;
      }
    }
    L = Math.max(L, 0); T = Math.max(T, 0);
    R = Math.min(R, window.innerWidth); B = Math.min(B, window.innerHeight);
    if (R - L <= 1 || B - T <= 1) return null;
    return { left: L, top: T, right: R, bottom: B };
  }

  /* Group visible [data-comp] roots by slug (document order → first visible
     instance anchors the label). Recomputed fresh on every draw. */
  function collect() {
    const groups = new Map();
    document.querySelectorAll('[data-comp]').forEach(el => {
      const slug = el.getAttribute('data-comp');
      if (!slug) return;
      const rect = clipRect(el);
      if (!rect) return;
      let g = groups.get(slug);
      if (!g) { g = { slug: slug, rects: [], anchor: rect }; groups.set(slug, g); }
      g.rects.push(rect);
    });
    return Array.from(groups.values());
  }

  /* Hover-to-expand: outline every visible instance of the hovered slug —
     drawn INSIDE the overlay layer, so the product DOM is never touched. */
  function clearHighlights() {
    layer.querySelectorAll('.lo-hl').forEach(n => n.remove());
  }
  function highlight(rects) {
    clearHighlights();
    rects.forEach(rc => {
      const hl = document.createElement('div');
      hl.className = 'lo-hl';
      hl.style.cssText = 'position:fixed;pointer-events:none;border:2px solid #ff2d78;border-radius:3px;' +
        'background:rgba(255,45,120,.08);box-shadow:0 0 0 1px rgba(255,255,255,.7) inset;' +
        'left:' + rc.left + 'px;top:' + rc.top + 'px;width:' + (rc.right - rc.left) + 'px;height:' + (rc.bottom - rc.top) + 'px;';
      layer.appendChild(hl);
    });
  }

  function draw() {
    if (!active) return;
    layer.textContent = '';
    const placed = [];
    const overlaps = (x, y, w, h) => placed.some(p =>
      x < p.x + p.w + 2 && x + w + 2 > p.x && y < p.y + p.h + 2 && y + h + 2 > p.y);
    collect().forEach(g => {
      const lab = document.createElement('div');
      lab.className = 'lo-label';
      lab.textContent = g.slug + (g.rects.length > 1 ? ' ×' + g.rects.length : '');
      lab.style.cssText = 'position:fixed;pointer-events:auto;cursor:default;background:#14162b;color:#fff;' +
        'border:1px solid rgba(255,255,255,.85);border-radius:3px;padding:1px 5px;white-space:nowrap;' +
        'font:' + MONO + ';line-height:1.5;box-shadow:0 1px 4px rgba(0,0,0,.45);opacity:.94;';
      layer.appendChild(lab);
      const w = lab.offsetWidth, h = lab.offsetHeight;
      /* seat the label on the instance's top-left corner, clamped on-screen */
      let x = Math.min(Math.max(g.anchor.left, 0), window.innerWidth - w - 2);
      let y = g.anchor.top - h + 4;                    // slight corner overlap
      if (y < 0) y = Math.min(g.anchor.top + 2, window.innerHeight - h - 2);
      /* collision nudging: stack downward until the slot is free */
      let tries = 0;
      while (overlaps(x, y, w, h) && tries++ < 30) y += h + 2;
      lab.style.left = x + 'px'; lab.style.top = y + 'px';
      placed.push({ x: x, y: y, w: w, h: h });
      lab.addEventListener('mouseenter', function () { highlight(g.rects); });
      lab.addEventListener('mouseleave', clearHighlights);
    });
    hud.textContent = 'data-comp labels ON · ' + placed.length + ' components · Ctrl+L to hide';
  }

  const schedule = () => {
    if (!active || raf) return;
    raf = requestAnimationFrame(() => { raf = 0; draw(); });
  };
  const onMove = e => { if (e.buttons & 1) schedule(); };   // splitter drags etc.

  function on() {
    active = true;
    ensureLayer();
    layer.style.display = 'block';
    hud.style.display = 'block';
    window.addEventListener('resize', schedule);
    document.addEventListener('scroll', schedule, true);    // capture: inner panels too
    document.addEventListener('mousemove', onMove);
    const app = document.querySelector('.app');
    if (app) {
      observer = new MutationObserver(schedule);
      observer.observe(app, { subtree: true, childList: true, attributes: true,
        attributeFilter: ['class', 'style', 'hidden', 'open', 'data-comp'] });
    }
    draw();
  }

  function off() {
    active = false;
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
    if (observer) { observer.disconnect(); observer = null; }
    window.removeEventListener('resize', schedule);
    document.removeEventListener('scroll', schedule, true);
    document.removeEventListener('mousemove', onMove);
    if (layer) { layer.textContent = ''; layer.style.display = 'none'; }
    if (hud) hud.style.display = 'none';
  }

  document.addEventListener('keydown', e => {
    if (e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey && (e.key === 'l' || e.key === 'L')) {
      e.preventDefault();
      active ? off() : on();
    }
  });
})();
