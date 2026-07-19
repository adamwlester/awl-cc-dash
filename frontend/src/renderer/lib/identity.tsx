// ============================================================================
// Identity — one shared roster vocabulary for every surface.
// ----------------------------------------------------------------------------
// Wraps the sidecar Session.identity {role, number, name, color, icon} into the
// display identity the design system renders everywhere (tile · role ·
// "NN name"), plus the two reserved pseudo-identities (User, System) and the
// Scratch target row. Mirrors agtileHTML/badgeHTML/badgeXsHTML/agrowHTML in
// design/behavior.js.
// ============================================================================

import React from 'react'
import type { Session } from '../api'
import { AgGlyph, Ic } from './icons'

export interface Ident {
  key: string           // session_id | 'user' | 'system' | 'scratch'
  role: string
  name: string          // display: "01 sandy" (padded number + short name)
  short: string         // "sandy"
  color: string         // hex (identity token value)
  icon: string          // icon file name (assets/icons/agents)
  user?: boolean
  system?: boolean
  scratch?: boolean
}

export const USER_IDENT: Ident = { key: 'user', role: 'human', name: 'User', short: 'User', color: 'var(--ag-user)', icon: '', user: true }
export const SYSTEM_IDENT: Ident = { key: 'system', role: 'app', name: 'System', short: 'System', color: 'var(--ag-system)', icon: '', system: true }
export const SCRATCH_IDENT: Ident = { key: 'scratch', role: 'scratchpad', name: 'Scratch', short: 'Scratch', color: 'var(--ag-azure)', icon: '', scratch: true }

export function identOf(s: Session): Ident {
  const id = s.identity
  if (!id) {
    const short = s.session_id.replace(/^awl-/, '').slice(0, 12)
    return { key: s.session_id, role: s.agent_type || 'agent', name: short, short, color: 'var(--ag-cobalt)', icon: '' }
  }
  const num = String(id.number ?? 1).padStart(2, '0')
  // A backend-assigned identity can carry an empty name (today: a handoff
  // fork's — backend gap): fall back to the session id rather than a blank.
  const nm = id.name || s.session_id.replace(/^awl-/, '').slice(0, 8)
  return { key: s.session_id, role: id.role || 'agent', name: `${num} ${nm}`, short: nm, color: id.color || 'var(--ag-cobalt)', icon: id.icon || '' }
}

// ---- run-state (the 4-state badge model: active / idle / pending / error) --
export type RunStateKind = 'active' | 'idle' | 'pending' | 'error'
export function runStateOf(s: Session): RunStateKind {
  if (s.has_pending_permission) return 'pending'
  if (s.status === 'error') return 'error'
  if (s.status === 'running') return 'active'
  return 'idle'
}
export const NB_CLASS: Record<RunStateKind, string> = { active: 'nb-active', idle: 'nb-idle', pending: 'nb-pending', error: 'nb-error' }
export const NB_LABEL: Record<RunStateKind, string> = { active: 'Active', idle: 'Idle', pending: 'Pending', error: 'Error' }

// ---- the 25-colour Jewel ring (mirrors tokens.css --ag-*) -------------------
export const JEWELS: { name: string; hex: string }[] = [
  { name: 'crimson', hex: '#aa3a61' }, { name: 'scarlet', hex: '#ae3a4f' }, { name: 'vermilion', hex: '#af3c3a' },
  { name: 'amber', hex: '#aa4600' }, { name: 'gold', hex: '#9d5400' }, { name: 'topaz', hex: '#915c00' },
  { name: 'citron', hex: '#876300' }, { name: 'chartreuse', hex: '#786900' }, { name: 'lime', hex: '#687100' },
  { name: 'peridot', hex: '#557600' }, { name: 'fern', hex: '#387b12' }, { name: 'emerald', hex: '#008149' },
  { name: 'teal', hex: '#008370' }, { name: 'turquoise', hex: '#007879' }, { name: 'cyan', hex: '#007f91' },
  { name: 'cerulean', hex: '#007494' }, { name: 'azure', hex: '#0076ab' }, { name: 'cobalt', hex: '#006bbb' },
  { name: 'sapphire', hex: '#3565be' }, { name: 'indigo', hex: '#4d5ebe' }, { name: 'violet', hex: '#7152b5' },
  { name: 'orchid', hex: '#8b48a0' }, { name: 'fuchsia', hex: '#954393' }, { name: 'magenta', hex: '#9e3f84' },
  { name: 'rose', hex: '#a53c73' },
]
export function jewelName(hex: string): string {
  const j = JEWELS.find(j => j.hex.toLowerCase() === (hex || '').toLowerCase())
  return j ? j.name : hex || '—'
}

// ---- helpers ---------------------------------------------------------------
export function ctxColor(p: number): string {
  return p < 50 ? 'var(--success)' : p <= 75 ? 'var(--warning)' : 'var(--danger)'
}
export function fmtTokens(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`
  return String(n)
}
/** "06-26 14:30 · 2h12m" — created stamp + auto-scaling ago (the node-age form). */
export function createdStamp(iso: string | null | undefined, nowMs: number): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())} · ${timeAgo(iso, nowMs)}`
}
export function timeAgo(iso: string | null | undefined, nowMs: number): string {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (isNaN(t)) return ''
  const s = Math.max(0, Math.floor((nowMs - t) / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return m % 60 && h < 10 ? `${h}h${m % 60}m` : `${h}h`
  return `${Math.floor(h / 24)}d`
}
/** "14:43" clock time for feed cards. */
export function clockTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
/** Canonical permission-mode label (Plan · Ask · Edit · Auto · Bypass). */
export function modeLabel(mode: string | null | undefined): string {
  const m = (mode || '').toLowerCase()
  if (m.includes('plan')) return 'Plan'
  if (m.includes('bypass')) return 'Bypass'
  if (m.includes('acceptedits') || m === 'edit') return 'Edit'
  if (m === 'auto' || m === 'dontask' || m.includes('acceptall')) return 'Auto'
  return 'Ask'
}
/** UI label → the CLI permission-mode value the sidecar accepts. `auto` is
 * the Auto segment's canonical spelling — the launch flag, the live set-mode
 * endpoint, and the status-line indicator all use it (the old `dontAsk`
 * alias made the live switch 400 "unreachable" even with Auto in the ring). */
export const MODE_VALUE: Record<string, string> = {
  Plan: 'plan', Ask: 'default', Edit: 'acceptEdits', Auto: 'auto', Bypass: 'bypassPermissions',
}

/** Short model label ("opus 4.8" from "claude-opus-4-8" etc.). A null/absent
 * model reads an honest '—' — the Claude-Code-default "inherit" path is
 * retired (NU-7: the app pins its own default, Opus); legacy null-model
 * records simply show no model. */
export function modelLabel(model: string | null | undefined): string {
  if (!model) return '—'
  const m = model.match(/(opus|sonnet|haiku|fable)[-_ ]?(\d+)(?:[-._](\d+))?/i)
  if (m) return `${m[1].toLowerCase()}${m[2] ? ` ${m[2]}${m[3] ? '.' + m[3] : ''}` : ''}`
  return model.replace(/^claude-/, '')
}

// ---- shared identity atoms (mirror behavior.js builders 1:1) ---------------

export function AgTile({ a, style, className }: { a: Ident; style?: React.CSSProperties; className?: string }) {
  if (a.user) return <span className={`agtile agtile--user agtile--me ${className || ''}`} style={style}><Ic name="user" className="agtile-luc" /></span>
  if (a.system) return <span className={`agtile agtile--system ${className || ''}`} style={style}><Ic name="settings" className="agtile-luc" /></span>
  if (a.scratch) return <span className={`agtile agtile--user ${className || ''}`} style={{ background: 'var(--ag-azure)', ...style }}><Ic name="file-text" className="agtile-luc" /></span>
  return <span className={`agtile ${className || ''}`} style={{ color: a.color, ...style }}><AgGlyph icon={a.icon} color={a.color} /></span>
}

/** Dense-default two-line identity badge (.badge badge-c). */
export function IdentBadge({ a }: { a: Ident }) {
  return (
    <span data-comp="identity-badge" className={`badge badge-c${a.user ? ' ag-user-badge' : ''}`}>
      <AgTile a={a} />
      <span className="b-lab"><span className="b-role">{a.role}</span><span className="b-name">{a.name}</span></span>
    </span>
  )
}

/** Small tier (.badge-xs) — tile + bare name. */
export function BadgeXs({ a }: { a: Ident }) {
  return (
    <span data-comp="identity-badge" className="badge-xs" title={`${a.role} ${a.name}`}>
      <AgTile a={a} /><span className="bx-nm">{a.name.replace(/^\d+\s*/, '')}</span>
    </span>
  )
}

/** Transcript-header recipient mini badge (.rcpt). */
export function RecipientBadge({ a }: { a: Ident }) {
  if (a.user) return <span data-comp="recipient-badge" className="rcpt" title="addressed to User"><span className="agtile agtile--user agtile--me"><Ic name="user" className="agtile-luc" /></span><span className="rcpt-nm">User</span></span>
  if (a.scratch) return <span data-comp="recipient-badge" className="rcpt" title="addressed to the shared Scratchpad"><span className="agtile rcpt-scratch"><Ic name="notebook-pen" className="agtile-luc" /></span><span className="rcpt-nm">Scratch</span></span>
  return (
    <span data-comp="recipient-badge" className="rcpt" title={`addressed to ${a.role} ${a.name}`}>
      <AgTile a={a} /><span className="rcpt-nm">{a.name.replace(/^\d+\s*/, '')}</span>
    </span>
  )
}

/** Selector list row (.agrow) — used by every From/To/Filter drawer. */
export function AgRow({ a, on, onClick, sub }: { a: Ident; on: boolean; onClick: () => void; sub?: React.ReactNode }) {
  return (
    <button className={`agrow${on ? ' on' : ''}`} type="button" onClick={onClick} data-ag={a.key}>
      <AgTile a={a} />
      <span className="ag-lab"><span className="ag-role">{a.role}</span><span className="ag-name">{a.name}</span></span>
      {sub}
      <Ic name="check" className="ag-ck" />
    </button>
  )
}
