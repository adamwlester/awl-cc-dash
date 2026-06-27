// ============================================================================
// Shared neobrutalism UI primitives
// ----------------------------------------------------------------------------
// Small building blocks reused across the panels: panel headers, buttons,
// the 4-state status badge, segmented controls, tab bars, labeled health bars,
// and config fields. All styled with inline tokens from tokens.ts.
// ============================================================================

import React from 'react'
import { C, FONT, MONO, BADGE_STYLE, healthColor, type Badge } from './tokens'

export const PANEL_HEADER_H = 34

// ---- Panel header strip (chrome) -------------------------------------------
export function PanelHeader({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div style={{
      height: PANEL_HEADER_H, minHeight: PANEL_HEADER_H, background: C.surface,
      borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center',
      padding: '0 10px', gap: 8, flexShrink: 0,
    }}>
      <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em', whiteSpace: 'nowrap' }}>{title}</span>
      <div style={{ flex: 1, minWidth: 0 }} />
      {right}
    </div>
  )
}

// ---- Button ----------------------------------------------------------------
type BtnVariant = 'primary' | 'secondary' | 'cream' | 'danger' | 'dangerSolid' | 'ghost'

export function Btn({ variant = 'cream', onClick, disabled, children, title, style }: {
  variant?: BtnVariant
  onClick?: () => void
  disabled?: boolean
  children: React.ReactNode
  title?: string
  style?: React.CSSProperties
}) {
  const base: React.CSSProperties = {
    border: `2px solid ${C.border}`, borderRadius: 5, boxShadow: C.shadowSm,
    padding: '4px 12px', fontSize: 11, fontWeight: 800, fontFamily: FONT,
    cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.45 : 1,
    whiteSpace: 'nowrap',
  }
  const variants: Record<BtnVariant, React.CSSProperties> = {
    primary: { background: C.main, color: C.mainFg },
    secondary: { background: C.secondary, color: C.mainFg },
    cream: { background: C.btn, color: C.t1 },
    danger: { background: C.btn, color: C.danger },
    dangerSolid: { background: C.danger, color: '#fff' },
    ghost: { background: 'transparent', color: C.t3, border: 'none', boxShadow: 'none' },
  }
  return (
    <button className={variant === 'ghost' ? undefined : 'nb-btn'} onClick={disabled ? undefined : onClick} disabled={disabled}
      title={title} style={{ ...base, ...variants[variant], ...style }}>
      {children}
    </button>
  )
}

// ---- Status badge (4-state) ------------------------------------------------
export function StatusBadge({ badge, onClick }: { badge: Badge; onClick?: () => void }) {
  const s = BADGE_STYLE[badge]
  return (
    <span onClick={onClick} style={{
      fontSize: 9, fontWeight: 800, letterSpacing: '0.04em', padding: '2px 7px',
      borderRadius: 3, border: `2px solid ${C.border}`, background: s.bg, color: '#fff',
      cursor: onClick ? 'pointer' : 'default', whiteSpace: 'nowrap',
    }}>{s.label}</span>
  )
}

// ---- Segmented control (single-select; active = teal) ----------------------
export function Segmented({ options, value, onChange, disabled, danger }: {
  options: { value: string; label: string }[]
  value: string | null
  onChange?: (v: string) => void
  disabled?: boolean
  danger?: string // a value rendered in the danger tone (e.g. Bypass)
}) {
  return (
    <div style={{
      display: 'flex', border: `2px solid ${C.border}`, borderRadius: 5,
      overflow: 'hidden', opacity: disabled ? 0.55 : 1,
    }}>
      {options.map((o, i) => {
        const active = o.value === value
        return (
          <button key={o.value}
            onClick={disabled || !onChange ? undefined : () => onChange(o.value)}
            disabled={disabled}
            style={{
              flex: 1, minWidth: 0, padding: '5px 2px', fontSize: 9.5, fontWeight: active ? 800 : 700,
              fontFamily: FONT, cursor: disabled ? 'default' : 'pointer',
              border: 'none', borderLeft: i ? `2px solid ${C.border}` : 'none',
              background: active ? C.secondary : C.btn,
              color: active ? C.mainFg : (o.value === danger ? C.danger : C.t3),
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}>
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

// ---- Tab bar (active = pink) -----------------------------------------------
export function Tabs({ tabs, active, onChange }: {
  tabs: { value: string; label: string; badge?: number; badgeColor?: string }[]
  active: string
  onChange: (v: string) => void
}) {
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      {tabs.map(t => {
        const on = t.value === active
        return (
          <button key={t.value} className="nb-btn" onClick={() => onChange(t.value)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px',
              fontSize: 10, fontWeight: 800, fontFamily: FONT, cursor: 'pointer',
              border: `2px solid ${on ? C.border : 'transparent'}`, borderRadius: 5,
              background: on ? C.main : 'transparent', color: on ? C.mainFg : C.t3,
              boxShadow: on ? C.shadowSm : 'none',
            }}>
            {t.label}
            {t.badge != null && t.badge > 0 && (
              <span style={{
                fontSize: 9, fontWeight: 800, color: '#fff', background: t.badgeColor || C.secondary,
                border: `1.5px solid ${C.border}`, borderRadius: 3, padding: '0 4px', minWidth: 14,
                textAlign: 'center',
              }}>{t.badge}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}

// ---- Labeled health bar (Ctx) ----------------------------------------------
export function LabeledBar({ label, pct, value }: { label: string; pct: number | null; value: string }) {
  const p = pct == null ? 0 : Math.max(0, Math.min(100, pct))
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ fontSize: 9, fontWeight: 800, color: C.t3, width: 30, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 7, background: C.surface, border: `1.5px solid ${C.border}`, borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${p}%`, height: '100%', background: healthColor(pct) }} />
      </div>
      <span style={{ fontSize: 9, fontWeight: 800, color: C.t2, width: 34, textAlign: 'right', flexShrink: 0, fontFamily: MONO }}>{value}</span>
    </div>
  )
}

// ---- Config field label ----------------------------------------------------
export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 9, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.t3, marginBottom: 4 }}>{label}</div>
      {children}
    </div>
  )
}

// ---- Read-only value box (greyed config display) ---------------------------
export function ReadOnly({ children, mono }: { children: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{
      background: C.surface, border: `2px solid ${C.rule}`, borderRadius: 5,
      padding: '6px 9px', fontSize: 11, color: C.t3, fontFamily: mono ? MONO : FONT,
      wordBreak: 'break-word', minHeight: 30,
    }}>{children}</div>
  )
}
