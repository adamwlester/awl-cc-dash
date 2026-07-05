#!/usr/bin/env node
/* ============================================================================
 * variant-lint.mjs — the enforcement tier for the design system's data-variants
 * doctrine (design/DESIGN.md → Component system → Variant declarations).
 *
 * One runnable command:
 *     node dev/tools/variant-lint/variant-lint.mjs            # full run (needs ui-verify's playwright)
 *     node dev/tools/variant-lint/variant-lint.mjs --static   # source checks only, no browser
 *     node dev/tools/variant-lint/variant-lint.mjs --strict   # unrenderable states also fail the run
 *
 * WHAT IT FAILS ON (exit 1 — violations):
 *   V1 malformed declarations — empty value, duplicate state tokens, or a token
 *      that is not lowercase kebab-case.
 *   V2 adjacency — a data-variants that does not sit IMMEDIATELY after its
 *      data-comp (one space), in markup, template-literal builder emissions, and
 *      the setAttribute('data-comp',…) ; setAttribute('data-variants',…) pattern.
 *      The adjacency is what lets the Variant-check one-liner pair them.
 *   V3 interaction states — declared state names the DESIGN.md ladder forbids:
 *      hover · focus · focus-within · pressed · open · expanded · selected ·
 *      checked · on · sel. (See "WHAT IT CANNOT CATCH" for the `active` caveat.)
 *   V4 inconsistent duplicates — one slug carrying two DIFFERENT declarations
 *      (the doctrine homes each slug's declaration in one canonical place; an
 *      identical duplicate from a builder is fine, a diverging one is drift).
 *
 * WHAT IT REPORTS LOUDLY (exit 0 unless --strict):
 *   G1 unrenderable states — declared states the auto-generated states page
 *      (design/states.html) cannot render mechanically. The page itself is the
 *      single source of that truth: this lint boots it via ui-verify and reads
 *      window.__statesReport, so page and lint can never disagree. These are
 *      honest, legitimate declarations (child-composed or builder-content
 *      states); they are debt to burn down, not necessarily errors — hence
 *      loud-but-passing by default, failing under --strict.
 *
 * WHAT IT CANNOT CATCH (documented limits, mirroring the Variant-check's
 * blind-spots note):
 *   - States nobody has declared: a component whose hidden states were simply
 *     never written down is invisible to every declaration-driven check. The
 *     per-touch rule + review are the only guard.
 *   - The `active` ambiguity: run-state `active` (status ramp — legal) and
 *     pressed-`active` (interaction — forbidden) collide on the same name, so
 *     V3 deliberately does not flag `active`; review catches the pressed sense.
 *   - Correctness of a render: the states page proves a declared state produces
 *     a CSS-effective delta, not that the delta matches design intent — that is
 *     what looking at the page is for.
 *   - Declarations in files other than design/mockup.html + design/behavior.js
 *     (the only two homes the doctrine allows).
 * ========================================================================== */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const DESIGN = resolve(HERE, '../../../design');
const args = new Set(process.argv.slice(2));
const STATIC_ONLY = args.has('--static') || args.has('--no-browser');
const STRICT = args.has('--strict');

const FORBIDDEN = new Set(['hover', 'focus', 'focus-within', 'pressed', 'open', 'expanded', 'selected', 'checked', 'on', 'sel']);
const violations = [];
const files = {
  'design/mockup.html': readFileSync(resolve(DESIGN, 'mockup.html'), 'utf8'),
  'design/behavior.js': readFileSync(resolve(DESIGN, 'behavior.js'), 'utf8'),
};

/* ---- collect every declaration + its context ---- */
const decls = [];   // {file, line, slug, value, adjacent}
for (const [fname, text] of Object.entries(files)) {
  const lineOf = (idx) => text.slice(0, idx).split('\n').length;
  /* attribute-form declarations (markup + template-literal emissions) */
  for (const m of text.matchAll(/data-variants="([^"]*)"/g)) {
    const before = text.slice(Math.max(0, m.index - 400), m.index);
    const adj = /data-comp="[^"]*" $/.test(before);
    const comp = before.match(/^[^]*data-comp="([^"]*)"/);   // greedy prefix → the NEAREST preceding data-comp
    let slug = comp ? comp[1] : '(unknown)';
    if (slug.includes("'+")) slug = '(builder-computed: ' + slug + ')';
    decls.push({ file: fname, line: lineOf(m.index), slug, value: m[1], adjacent: adj });
  }
  /* setAttribute-form declarations (lazy singletons like toast); allow the
     receiver between the two calls: …('data-comp','x');t.setAttribute('data-variants'… */
  for (const m of text.matchAll(/setAttribute\('data-variants','([^']*)'\)/g)) {
    const before = text.slice(Math.max(0, m.index - 200), m.index);
    const adj = /setAttribute\('data-comp','[^']*'\);[\w$.]*$/.test(before);
    const comp = before.match(/^[^]*setAttribute\('data-comp','([^']*)'\)/);
    decls.push({ file: fname, line: lineOf(m.index), slug: comp ? comp[1] : '(unknown)', value: m[1], adjacent: adj });
  }
}

/* ---- V1 malformed ---- */
for (const d of decls) {
  const toks = d.value.trim().split(/\s+/).filter(Boolean);
  if (!d.value.trim()) violations.push(`V1 malformed  ${d.file}:${d.line}  ${d.slug} — empty data-variants`);
  const seen = new Set();
  for (const t of toks) {
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(t)) violations.push(`V1 malformed  ${d.file}:${d.line}  ${d.slug} — state "${t}" is not lowercase kebab-case`);
    if (seen.has(t)) violations.push(`V1 malformed  ${d.file}:${d.line}  ${d.slug} — duplicate state "${t}"`);
    seen.add(t);
  }
}
/* ---- V2 adjacency ---- */
for (const d of decls) if (!d.adjacent) violations.push(`V2 adjacency  ${d.file}:${d.line}  ${d.slug} — data-variants is not immediately after data-comp`);
/* ---- V3 interaction states ---- */
for (const d of decls) for (const t of d.value.trim().split(/\s+/).filter(Boolean)) {
  if (FORBIDDEN.has(t)) violations.push(`V3 interaction  ${d.file}:${d.line}  ${d.slug} — "${t}" is an interaction state (never declared; see the DESIGN.md ladder)`);
}
/* ---- V4 inconsistent duplicates ---- */
const bySlug = new Map();
for (const d of decls) {
  if (d.slug.startsWith('(')) continue;
  const norm = d.value.trim().split(/\s+/).sort().join(' ');
  const prev = bySlug.get(d.slug);
  if (prev && prev.norm !== norm) violations.push(`V4 duplicate  ${d.file}:${d.line}  ${d.slug} — declaration "${d.value}" diverges from ${prev.file}:${prev.line} "${prev.value}"`);
  else bySlug.set(d.slug, { norm, file: d.file, line: d.line, value: d.value });
}

console.log(`variant-lint: ${decls.length} declaration sites scanned in design/mockup.html + design/behavior.js`);

/* ---- G1 unrenderable states (via the states page's own report) ---- */
let gaps = null;
if (!STATIC_ONLY) {
  const { launch, serveDir } = await import(resolve(HERE, '../ui-verify/ui-verify.mjs').replace(/\\/g, '/').replace(/^([A-Za-z]:)/, 'file:///$1'));
  const site = await serveDir(DESIGN);
  const app = await launch({ mode: 'headless' });   // a data read, not a visual verification — headless is deliberate
  try {
    await app.page.goto(site.url + '/states.html', { waitUntil: 'load' });
    await app.page.waitForFunction(() => window.__statesReport !== null, { timeout: 45000 });
    const report = await app.page.evaluate(() => window.__statesReport);
    gaps = report.gaps;
    console.log(`states page: ${report.counts.declaredSlugs} declared slugs · ${report.counts.states} states → ${report.counts.rendered} rendered · ${report.counts.approximate} approximate · ${report.counts.unrendered} unrendered`);
  } finally { await app.close(); await site.close(); }
} else {
  console.log('states-page renderability check SKIPPED (--static)');
}

/* ---- report ---- */
let exit = 0;
if (violations.length) {
  exit = 1;
  console.error(`\nVIOLATIONS (${violations.length}) — these fail the lint:`);
  for (const v of violations) console.error('  ✗ ' + v);
} else {
  console.log('violations: none');
}
if (gaps) {
  if (gaps.length) {
    console.log(`\nGAPS (${gaps.length}) — declared states the states page cannot render mechanically (honest debt${STRICT ? '; failing under --strict' : '; pass --strict to fail on these'}):`);
    for (const g of gaps) console.log('  ! ' + g.slug + ':' + g.state + ' — ' + g.why);
    if (STRICT) exit = 1;
  } else {
    console.log('gaps: none — every declared state renders on the states page');
  }
}
process.exit(exit);
