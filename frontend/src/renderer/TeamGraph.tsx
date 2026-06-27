// ============================================================================
// Team Graph — one card per agent, wired to real data
// ----------------------------------------------------------------------------
// Each card shows the derived 4-state status badge, the identity row (tile,
// role, number, name, model), the Ctx% health bar (GET /context|usage percent),
// the Turns count (GET /context work_steps — NOT /sessions total_turns, which is
// 0 on bridge), and the subagent strip (GET /subagents). Cards lay out in a
// scrolling grid; clicking one focuses that agent across the app.
//
// Honest fallbacks: the mode chip shows the launched permission_mode (real);
// effort/think have no readback on bridge, shown as "—". The Run strip is a
// barber-pole indeterminate when active (no real completion % exists) and a
// status-keyed flat color otherwise. The Marquee (no data source) is omitted.
// ============================================================================

import React from 'react'
import { C, MONO, deriveBadge, fmtCreated, timeAgo, healthColor } from './tokens'
import { StatusBadge } from './ui'
import { AgentTile } from './AgentTile'
import type { Session, Subagent } from './api'

function modeShort(mode: string): string {
  return ({
    acceptEdits: 'edit', bypassPermissions: 'bypass', plan: 'plan',
    default: 'default', dontAsk: 'dontask', auto: 'auto',
  } as Record<string, string>)[mode] || mode
}

const SUB_STATUS_COLOR: Record<string, string> = {
  running: C.success, done: C.mutedFill, error: C.danger,
}

function Chip({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div style={{ flex: 1, minWidth: 0, textAlign: 'center' }}>
      <div style={{ fontSize: 7.5, fontWeight: 800, color: C.t5, textTransform: 'uppercase', letterSpacing: '0.03em' }}>{label}</div>
      <div style={{ fontSize: 9.5, fontWeight: 800, color: muted ? C.t5 : C.t2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</div>
    </div>
  )
}

function RunStrip({ badge }: { badge: string }) {
  // active -> barber-pole (working, % unknown — the honest fallback); pending ->
  // warm flat; idle -> muted empty; error -> solid danger.
  if (badge === 'active') {
    return <div className="awl-barber" style={{ height: 6, border: `1.5px solid ${C.border}`, borderRadius: 3, overflow: 'hidden' }} />
  }
  const fill = badge === 'pending' ? C.warning : badge === 'error' ? C.danger : 'transparent'
  return (
    <div style={{ height: 6, border: `1.5px solid ${C.border}`, borderRadius: 3, overflow: 'hidden', background: badge === 'idle' ? C.surface : 'transparent' }}>
      <div style={{ width: '100%', height: '100%', background: fill }} />
    </div>
  )
}

function SubagentStrip({ subs }: { subs: Subagent[] }) {
  return (
    <div style={{ minHeight: 22, display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
      {subs.length === 0 ? (
        <span style={{ fontSize: 9, color: C.t5, fontStyle: 'italic' }}>no subagents</span>
      ) : (
        subs.map(s => (
          <span key={s.id} title={`${s.type || 'subagent'} · ${s.status}`} style={{
            fontSize: 8.5, fontWeight: 800, color: '#fff', background: SUB_STATUS_COLOR[s.status] || C.mutedFill,
            border: `1.5px solid ${C.border}`, borderRadius: 3, padding: '1px 5px',
          }}>{s.id}</span>
        ))
      )}
    </div>
  )
}

function AgentCard({ session, percent, workSteps, subs, selected, onSelect, nowMs }: {
  session: Session
  percent: number | null
  workSteps: number | null
  subs: Subagent[]
  selected: boolean
  onSelect: () => void
  nowMs: number
}) {
  const id = session.identity
  const badge = deriveBadge(session.status, session.has_pending_permission)
  const color = id?.color || C.mutedFill
  const pctVal = percent == null ? '—' : `${Math.round(percent)}%`

  return (
    <div onClick={onSelect} style={{
      display: 'flex', flexDirection: 'column', gap: 6, padding: 9,
      border: `2px solid ${C.border}`, borderRadius: 5,
      background: selected ? C.select : C.card,
      boxShadow: selected ? C.shadow : C.shadowSm,
      cursor: 'pointer', minHeight: 188,
    }}>
      {/* top meta strip: created stamp + status badge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
        <span style={{ fontSize: 8.5, color: C.t5, fontFamily: MONO, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {fmtCreated(session.created_at)} · {timeAgo(session.created_at, nowMs)}
        </span>
        <StatusBadge badge={badge} />
      </div>

      {/* identity row */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 7 }}>
        <AgentTile icon={id?.icon} color={color} size={30} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 8, fontWeight: 800, color: C.t3, textTransform: 'uppercase', letterSpacing: '0.04em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {id?.role || 'agent'}
          </div>
          <div style={{ fontSize: 11.5, fontWeight: 900, color: C.t1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {String(id?.number ?? '').padStart(2, '0')} {id?.name || ''}
          </div>
        </div>
        <div style={{ fontSize: 9, color: C.t3, fontFamily: MONO, textAlign: 'right', whiteSpace: 'nowrap', maxWidth: 70, overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {session.model || 'default'}
        </div>
      </div>

      <div style={{ borderTop: `2px solid ${C.border}`, margin: '1px 0' }} />

      {/* settings chips: mode (real) · effort (—) · think (—) */}
      <div style={{ display: 'flex', gap: 4 }}>
        <Chip label="mode" value={modeShort(session.permission_mode)} />
        <Chip label="effort" value="—" muted />
        <Chip label="think" value="—" muted />
      </div>

      {/* Ctx + Turns */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 9, fontWeight: 800, color: C.t3, width: 30, flexShrink: 0 }}>CTX</span>
        <div style={{ flex: 1, height: 7, background: C.surface, border: `1.5px solid ${C.border}`, borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ width: `${percent == null ? 0 : Math.max(0, Math.min(100, percent))}%`, height: '100%', background: healthColor(percent) }} />
        </div>
        <span style={{ fontSize: 9, fontWeight: 800, color: C.t2, width: 34, textAlign: 'right', flexShrink: 0, fontFamily: MONO }}>{pctVal}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }} title="Turns = agentic work-steps (no cap set)">
        <span style={{ fontSize: 9, fontWeight: 800, color: C.t3, width: 30, flexShrink: 0 }}>TURNS</span>
        <div style={{ flex: 1, fontSize: 8.5, color: C.t5 }}>—</div>
        <span style={{ fontSize: 9, fontWeight: 800, color: C.t2, width: 34, textAlign: 'right', flexShrink: 0, fontFamily: MONO }}>{workSteps ?? '—'}</span>
      </div>

      {/* run strip */}
      <RunStrip badge={badge} />

      <div style={{ flex: 1 }} />
      {/* subagents */}
      <SubagentStrip subs={subs} />
    </div>
  )
}

export function TeamGraph({ sessions, usageBy, subagentsBy, selectedId, onSelect, nowMs }: {
  sessions: Session[]
  usageBy: Record<string, { percent: number | null; work_steps: number | null }>
  subagentsBy: Record<string, Subagent[]>
  selectedId: string | null
  onSelect: (id: string) => void
  nowMs: number
}) {
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 10, background: C.bg }}>
      {sessions.length === 0 ? (
        <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 40, lineHeight: 1.6 }}>
          No agents yet.<br />Use the Agent panel → Create to start one.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(186px, 1fr))', gap: 10, alignContent: 'start' }}>
          {sessions.map(s => {
            const u = usageBy[s.session_id] || { percent: null, work_steps: null }
            return (
              <AgentCard key={s.session_id} session={s}
                percent={u.percent} workSteps={u.work_steps}
                subs={subagentsBy[s.session_id] || []}
                selected={s.session_id === selectedId}
                onSelect={() => onSelect(s.session_id)} nowMs={nowMs} />
            )
          })}
        </div>
      )}
    </div>
  )
}
