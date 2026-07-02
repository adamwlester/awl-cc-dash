// ============================================================================
// Team Feed — the merged Messages stream + the 5-type Inbox
// ----------------------------------------------------------------------------
// Messages renders the cross-agent merged /events bus (dedup + seq-ordered in
// App). A [Focused | All] toggle scopes it to the selected agent or the whole
// fleet, with per-agent grouping headers in All mode. Inbox is the "needs
// you" surface across all five typed sections (permission / error / warning /
// plan / decision) — permission cards Approve/Deny, the rest resolve.
// ============================================================================

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { C, MONO } from './tokens'
import { Tabs, Btn, Segmented } from './ui'
import { AgentTile } from './AgentTile'
import { EventRenderer, isRenderableEvent } from './events'
import type { Session, SDKEvent, InboxResponse, InboxItem } from './api'

// ---- Messages --------------------------------------------------------------

function agentLabel(s: Session | undefined): string {
  const id = s?.identity
  if (!id) return s?.session_id || '?'
  return `${String(id.number ?? '').padStart(2, '0')} ${id.name || id.role || ''}`.trim()
}

function AgentHeader({ session }: { session: Session | undefined }) {
  const id = session?.identity
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '10px 0 5px' }}>
      <AgentTile icon={id?.icon} color={id?.color} size={18} radius={3} />
      <span style={{ fontSize: 9.5, fontWeight: 800, color: C.t3, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {agentLabel(session)}
      </span>
      <div style={{ flex: 1, height: 2, background: C.rule }} />
    </div>
  )
}

function Messages({ focusedId, events, sessions, mode }: {
  focusedId: string | null
  events: SDKEvent[]
  sessions: Session[]
  mode: 'focused' | 'all'
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const byId = useMemo(() => Object.fromEntries(sessions.map(s => [s.session_id, s])), [sessions])

  const shown = useMemo(() => {
    const r = events.filter(isRenderableEvent)
    return mode === 'focused' && focusedId ? r.filter(e => e.agent_id === focusedId) : r
  }, [events, focusedId, mode])

  useEffect(() => {
    if (autoScroll && ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [shown, autoScroll])

  const onScroll = () => {
    const el = ref.current
    if (!el) return
    setAutoScroll(el.scrollHeight - el.scrollTop - el.clientHeight < 50)
  }

  let lastAgent: string | undefined
  return (
    <div ref={ref} onScroll={onScroll} style={{ flex: 1, overflow: 'auto', padding: 12, background: C.card }}>
      {mode === 'focused' && !focusedId ? (
        <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 40 }}>Select an agent to see its messages, or switch to All.</div>
      ) : shown.length === 0 ? (
        <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 40 }}>{mode === 'all' ? 'No messages yet across the fleet.' : 'Agent ready. Send a prompt below.'}</div>
      ) : (
        shown.map((e, i) => {
          const showHeader = mode === 'all' && e.agent_id !== lastAgent
          lastAgent = e.agent_id
          return (
            <React.Fragment key={e.id || i}>
              {showHeader && <AgentHeader session={byId[e.agent_id || '']} />}
              <EventRenderer event={e} />
            </React.Fragment>
          )
        })
      )}
    </div>
  )
}

// ---- Inbox (5 typed sections) ----------------------------------------------

const TYPE_META: Record<string, { accent: string; label: string }> = {
  permission: { accent: C.inboxPermission, label: 'Permission' },
  error: { accent: C.danger, label: 'Error' },
  warning: { accent: C.warning, label: 'Warning' },
  plan: { accent: C.secondary, label: 'Plan' },
  decision: { accent: C.railSection, label: 'Decision' },
}

function itemDetail(item: InboxItem): React.ReactNode {
  const d = item.data || {}
  if (item.type === 'permission') {
    return (
      <>
        <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.5 }}>{d.question || 'A tool/command needs your approval.'}</div>
        {Array.isArray(d.options) && d.options.length > 0 && (
          <div style={{ fontSize: 10, color: C.t3, fontFamily: MONO, marginTop: 5 }}>
            {d.options.map((o: any, i: number) => <div key={i}>{o.index}. {o.label}</div>)}
          </div>
        )}
      </>
    )
  }
  if (item.type === 'error' || item.type === 'warning') {
    return (
      <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.5 }}>
        <b>{d.subtype || item.type}</b>{d.message ? ` — ${d.message}` : ''}
        {d.cap != null ? ` (${d.value} ≥ cap ${d.cap})` : ''}
      </div>
    )
  }
  // plan / decision — surface the tool + its input
  const ti = d.tool_input || {}
  const text = ti.plan || ti.question || (Array.isArray(ti.questions) ? ti.questions.map((q: any) => q.question).join(' · ') : '') || JSON.stringify(ti).slice(0, 200)
  return (
    <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.5 }}>
      <span style={{ fontFamily: MONO, fontSize: 10, color: C.t3 }}>{d.tool || item.type}</span>
      <div style={{ marginTop: 3, whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 120, overflow: 'auto' }}>{text}</div>
    </div>
  )
}

function InboxCard({ item, session, onAnswer, onResolve }: {
  item: InboxItem
  session: Session | undefined
  onAnswer: (approve: boolean) => void
  onResolve: () => void
}) {
  const m = TYPE_META[item.type] || TYPE_META.error
  const id = session?.identity
  return (
    <div style={{ background: C.card, border: `2px solid ${C.border}`, borderLeft: `4px solid ${m.accent}`, borderRadius: 5, boxShadow: C.shadowSm, padding: 10, marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
        <AgentTile icon={id?.icon} color={id?.color} size={24} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 8, fontWeight: 800, color: C.t3, textTransform: 'uppercase' }}>{id?.role || 'agent'}</div>
          <div style={{ fontSize: 11, fontWeight: 900, color: C.t1 }}>{agentLabel(session)}</div>
        </div>
        <span style={{ fontSize: 8.5, fontWeight: 800, color: '#fff', background: m.accent, border: `2px solid ${C.border}`, borderRadius: 3, padding: '2px 7px', textTransform: 'uppercase' }}>{m.label}</span>
      </div>
      <div style={{ marginBottom: 8 }}>{itemDetail(item)}</div>
      {item.type === 'permission' ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn variant="primary" onClick={() => onAnswer(true)} style={{ flex: 1 }}>Approve</Btn>
          <Btn variant="danger" onClick={() => onAnswer(false)} style={{ flex: 1 }}>Deny</Btn>
        </div>
      ) : (
        <Btn variant="cream" onClick={onResolve} style={{ width: '100%' }}>
          {item.type === 'error' || item.type === 'warning' ? 'Dismiss' : 'Acknowledge'}
        </Btn>
      )}
    </div>
  )
}

function Inbox({ inbox, sessions, onAnswer, onResolveInbox }: {
  inbox: InboxResponse
  sessions: Session[]
  onAnswer: (id: string, approve: boolean) => void
  onResolveInbox: (agent: string, itemId: string, answer?: any) => void
}) {
  const byId = useMemo(() => Object.fromEntries(sessions.map(s => [s.session_id, s])), [sessions])
  const groups = Object.entries(inbox.inbox).filter(([, items]) => items.length > 0)
  const total = groups.reduce((a, [, items]) => a + items.length, 0)

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 12, background: C.card }}>
      <div style={{ fontSize: 9, fontWeight: 800, color: C.t3, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
        Needs you {total > 0 && `· ${total} across ${groups.length} agent${groups.length > 1 ? 's' : ''}`}
      </div>
      {total === 0 ? (
        <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 30 }}>Nothing waiting on you.</div>
      ) : (
        groups.flatMap(([agent, items]) =>
          items.map(item => (
            <InboxCard key={item.id} item={item} session={byId[agent]}
              onAnswer={(approve) => onAnswer(agent, approve)}
              onResolve={() => onResolveInbox(agent, item.id)} />
          ))
        )
      )}
    </div>
  )
}

// ---- Panel shell -----------------------------------------------------------

export function TeamFeed({ focusedId, events, sessions, inbox, onAnswer, onResolveInbox }: {
  focusedId: string | null
  events: SDKEvent[]
  sessions: Session[]
  inbox: InboxResponse
  onAnswer: (id: string, approve: boolean) => void
  onResolveInbox: (agent: string, itemId: string, answer?: any) => void
}) {
  const [tab, setTab] = useState<'messages' | 'inbox'>('messages')
  const [mode, setMode] = useState<'focused' | 'all'>('focused')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ height: 34, minHeight: 34, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 10px', gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Team Feed</span>
        <div style={{ flex: 1 }} />
        {tab === 'messages' && (
          <div style={{ width: 130 }}>
            <Segmented options={[{ value: 'focused', label: 'Focused' }, { value: 'all', label: 'All' }]} value={mode} onChange={(v) => setMode(v as any)} />
          </div>
        )}
        <Tabs tabs={[
          { value: 'messages', label: 'Messages' },
          { value: 'inbox', label: 'Inbox', badge: inbox.fleet_badge, badgeColor: C.inboxPermission },
        ]} active={tab} onChange={(t) => setTab(t as any)} />
      </div>
      {tab === 'messages'
        ? <Messages focusedId={focusedId} events={events} sessions={sessions} mode={mode} />
        : <Inbox inbox={inbox} sessions={sessions} onAnswer={onAnswer} onResolveInbox={onResolveInbox} />}
    </div>
  )
}
