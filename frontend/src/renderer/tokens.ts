// ============================================================================
// Design tokens + small style helpers
// ----------------------------------------------------------------------------
// Values mirror design/tokens.css (the single source of truth). The dashboard
// speaks neobrutalism: 2px navy borders, hard offset shadows (no blur), flat
// fills, one tight radius, Archivo (heading 800 / body 500) + JetBrains Mono for
// metrics. Do not hardcode values here that diverge from tokens.css.
// ============================================================================

export const C = {
  // Surfaces — three warm surfaces + a button tint + a hairline
  bg: '#fef6e4',        // --background      canvas / panel bodies / scroll wells
  surface: '#f5ecd9',   // --surface-3       chrome: headers, footers, toolbars
  card: '#ffffff',      // --secondary-background  cards / inputs / tab wells
  input: '#ffffff',     // form inputs (white)
  btn: '#fbf5e8',       // --surface-btn     low-emphasis action buttons
  codeBg: '#f5ecd9',    // inline code (--surface-3)
  rule: '#d8cfb8',      // --rule            hairline inside inline atoms
  // Border + ink (2px navy everywhere)
  border: '#001858',    // --border / --foreground
  borderH: '#001858',
  // Text ramp
  t1: '#001858', t2: '#001858',   // --foreground  ink / headings / body
  t3: '#5b5f86', t4: '#5b5f86',   // --muted
  t5: '#9a93b4',                  // --muted-2  faint (timestamps, placeholders)
  // Accents — pink=primary · teal=secondary · cream=low-emphasis · red=danger
  main: '#f582ae', mainFg: '#001858', mainDim: '#f9b9d2',
  secondary: '#8bd3dd', secondaryDim: '#bfe6ec',
  select: '#a9dde7',    // --select  selection FILL (light teal)
  teal: '#8bd3dd',
  railSection: '#2f97a6',
  gold: '#d98a2b', warning: '#d98a2b',     // --warning  attention / pending
  coral: '#d23b6a', danger: '#d23b6a',     // --danger
  sage: '#2f9e6f', success: '#2f9e6f',     // --success
  inboxPermission: '#a9710f',              // --inbox-permission
  iconFg: '#ffffff',                       // --icon-fg  glyph knockout on tiles
  agUser: '#7b7fa6',                       // --ag-user
  mutedFill: '#5b5f86',                    // idle status badge fill (slate)
  // Soft status containers
  successSoft: '#e7f5ee', successText: '#1f6f4d',
  dangerSoft: '#fbe7ee',
  warnSoft: '#f6e6cf', warnText: '#9a6710',
  // Hard offset shadows (no blur) — raised / interactive only
  shadow: '4px 4px 0 0 #001858', shadowSm: '2px 2px 0 0 #001858',
}

export const FONT = "'Archivo', sans-serif"
export const MONO = "'JetBrains Mono', monospace"

// The 16 --ag-* Jewel colors keyed by name (for any name->hex lookups the UI
// needs; identity.color already carries the resolved hex from the backend).
export const AG_COLORS: Record<string, string> = {
  crimson: '#aa3a61', vermilion: '#af3c3a', amber: '#aa4600', gold: '#9d5400',
  citron: '#876300', lime: '#687100', fern: '#387b12', emerald: '#008149',
  teal: '#008370', cyan: '#007f91', azure: '#0076ab', cobalt: '#006bbb',
  indigo: '#4d5ebe', violet: '#7152b5', orchid: '#8b48a0', magenta: '#9e3f84',
}

// ---- Status badge (the derived 4-state) ------------------------------------
// active/idle/pending/error all use the solid-fill + white-text family so they
// read as one badge family (per the design system). Pending reads off the
// session's has_pending_permission flag, not a status value.
export type Badge = 'active' | 'idle' | 'pending' | 'error'

export function deriveBadge(status: string, hasPendingPermission: boolean): Badge {
  if (hasPendingPermission) return 'pending'
  if (status === 'running') return 'active'
  if (status === 'error') return 'error'
  return 'idle' // idle / connecting / closed all read as idle
}

export const BADGE_STYLE: Record<Badge, { bg: string; label: string }> = {
  active: { bg: C.success, label: 'ACTIVE' },
  idle: { bg: C.mutedFill, label: 'IDLE' },
  pending: { bg: C.warning, label: 'PENDING' },
  error: { bg: C.danger, label: 'ERROR' },
}

// ---- Health ramp (context %, turns) — green -> amber -> red -----------------
export function healthColor(pct: number | null | undefined): string {
  if (pct == null) return C.t5
  if (pct >= 85) return C.danger
  if (pct >= 65) return C.warning
  return C.success
}

// ---- Time helpers ----------------------------------------------------------
// Auto-scaling "ago" duration, e.g. 45s · 12m · 2h12m · 3d · 2w.
export function timeAgo(iso: string | null | undefined, nowMs?: number): string {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ''
  let s = Math.max(0, Math.floor(((nowMs ?? Date.now()) - t) / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) { const rm = m % 60; return rm ? `${h}h${rm}m` : `${h}h` }
  const d = Math.floor(h / 24)
  if (d < 7) return `${d}d`
  return `${Math.floor(d / 7)}w`
}

// Compact created stamp "MM-DD HH:MM" in local time.
export function fmtCreated(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
