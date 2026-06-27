// ============================================================================
// Team Feed — Messages (focused agent's rendered stream) + Inbox (permissions)
// ----------------------------------------------------------------------------
// Scratch / Log tabs are ABSENT (net-new backend). The cross-agent merged
// Messages stream, the From/To filter, and the non-Permission Inbox sections
// (Error/Warning/Plan/Decision) all need the Phase-1 event-stream + detection
// that doesn't exist — so Messages is single-agent (the focused one) and the
// Inbox shows only Permission cards (the one request type the bridge detects).
// The Inbox tab badge is the fleet pending count.
// ============================================================================

import React, { useEffect, useRef, useState } from 'react'
import { C, MONO, deriveBadge } from './tokens'
import { Tabs, Btn, StatusBadge } from './ui'
import { AgentTile } from './AgentTile'
import { EventRenderer, hasRenderable } from './events'
import type { Session, SDKEvent } from './api'

function Messages({ session, events }: { session: Session | null; events: SDKEvent[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  useEffect(() => {
    if (autoScroll && ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [events, autoScroll])
  const onScroll = () => {
    const el = ref.current
    if (!el) return
    setAutoScroll(el.scrollHeight - el.scrollTop - el.clientHeight < 50)
  }
  const running = session?.status === 'running'

  return (
    <div ref={ref} onScroll={onScroll} style={{ flex: 1, overflow: 'auto', padding: 12, background: C.card }}>
      {!session ? (
        <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 40 }}>Select an agent to see its messages.</div>
      ) : (
        <>
          {events.map((e, i) => <EventRenderer key={i} event={e} />)}
          {running && (
            <div style={{ padding: '4px 0' }}>
              <span style={{ display: 'inline-block', width: 6, height: 14, background: C.border, borderRadius: 1, animation: 'awlblink 1s infinite' }} />
            </div>
          )}
          {!running && !hasRenderable(events) && (
            <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 40 }}>Agent ready. Send a prompt below.</div>
          )}
        </>
      )}
    </div>
  )
}

function PermissionCard({ session, onAnswer }: { session: Session; onAnswer: (approve: boolean) => void }) {
  const id = session.identity
  const det = session.permission_request
  return (
    <div style={{ background: C.card, border: `2px solid ${C.border}`, borderLeft: `4px solid ${C.inboxPermission}`, borderRadius: 5, boxShadow: C.shadowSm, padding: 10, marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
        <AgentTile icon={id?.icon} color={id?.color} size={24} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 8, fontWeight: 800, color: C.t3, textTransform: 'uppercase' }}>{id?.role || 'agent'}</div>
          <div style={{ fontSize: 11, fontWeight: 900, color: C.t1 }}>{String(id?.number ?? '').padStart(2, '0')} {id?.name || ''}</div>
        </div>
        <span style={{ fontSize: 8.5, fontWeight: 800, color: '#fff', background: C.inboxPermission, border: `2px solid ${C.border}`, borderRadius: 3, padding: '2px 7px' }}>PERMISSION</span>
      </div>
      <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.5, marginBottom: 8 }}>
        {det?.question || 'A tool/command needs your approval.'}
      </div>
      {det?.options && det.options.length > 0 && (
        <div style={{ fontSize: 10, color: C.t3, fontFamily: MONO, marginBottom: 8 }}>
          {det.options.map(o => <div key={o.index}>{o.index}. {o.label}</div>)}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8 }}>
        <Btn variant="primary" onClick={() => onAnswer(true)} style={{ flex: 1 }}>Approve</Btn>
        <Btn variant="danger" onClick={() => onAnswer(false)} style={{ flex: 1 }}>Deny</Btn>
      </div>
    </div>
  )
}

function Inbox({ sessions, onAnswer }: { sessions: Session[]; onAnswer: (id: string, approve: boolean) => void }) {
  const pending = sessions.filter(s => s.has_pending_permission)
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 12, background: C.card }}>
      <div style={{ fontSize: 9, fontWeight: 800, color: C.inboxPermission, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
        Permission {pending.length > 0 && `· ${pending.length}`}
      </div>
      {pending.length === 0 ? (
        <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 30 }}>No agents waiting on you.</div>
      ) : (
        pending.map(s => <PermissionCard key={s.session_id} session={s} onAnswer={(a) => onAnswer(s.session_id, a)} />)
      )}
      <div style={{ fontSize: 9, color: C.t5, marginTop: 14, lineHeight: 1.5, borderTop: `1.5px solid ${C.rule}`, paddingTop: 8 }}>
        Only tool-Permission requests are detectable on bridge. Error / Warning / Plan / Decision sections need net-new detection (not built).
      </div>
    </div>
  )
}

export function TeamFeed({ session, events, sessions, onAnswer }: {
  session: Session | null
  events: SDKEvent[]
  sessions: Session[]
  onAnswer: (id: string, approve: boolean) => void
}) {
  const [tab, setTab] = useState<'messages' | 'inbox'>('messages')
  const pendingCount = sessions.filter(s => s.has_pending_permission).length
  const badge = session ? deriveBadge(session.status, session.has_pending_permission) : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ height: 34, minHeight: 34, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 10px', gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Team Feed</span>
        <div style={{ flex: 1 }} />
        {tab === 'messages' && badge && <StatusBadge badge={badge} />}
        <Tabs tabs={[
          { value: 'messages', label: 'Messages' },
          { value: 'inbox', label: 'Inbox', badge: pendingCount, badgeColor: C.inboxPermission },
        ]} active={tab} onChange={(t) => setTab(t as any)} />
      </div>
      {tab === 'messages'
        ? <Messages session={session} events={events} />
        : <Inbox sessions={sessions} onAnswer={onAnswer} />}
    </div>
  )
}
