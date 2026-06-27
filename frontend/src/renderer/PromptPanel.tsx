// ============================================================================
// Prompt — Compose (fire-now send + Stop) + History (focused agent's prompts)
// ----------------------------------------------------------------------------
// Single-agent for this run: From is User, To is the focused agent (the
// multi-target From/To selectors, send-timing beyond Now, templates, attach,
// and Revise all need Phase-1 backend — omitted, not faked). Compose sends
// fire-now (POST /send); Stop interrupts (POST /interrupt). History lists the
// focused agent's own prompts pulled from its transcript events.
// ============================================================================

import React, { useState } from 'react'
import { C, FONT, MONO } from './tokens'
import { Tabs, Btn } from './ui'
import { AgentTile } from './AgentTile'
import { toBlocks } from './events'
import type { Session, SDKEvent } from './api'

function ToBadge({ session }: { session: Session | null }) {
  if (!session) return <span style={{ fontSize: 10, color: C.t5 }}>—</span>
  const id = session.identity
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: `2px solid ${C.border}`, borderRadius: 5, padding: '3px 8px', background: C.card, boxShadow: C.shadowSm }}>
      <AgentTile icon={id?.icon} color={id?.color} size={18} radius={3} />
      <span style={{ fontSize: 10, fontWeight: 800, color: C.t1 }}>
        {String(id?.number ?? '').padStart(2, '0')} {id?.name || id?.role || session.session_id}
      </span>
    </div>
  )
}

function FromToBar({ session }: { session: Session | null }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', background: C.surface, borderBottom: `2px solid ${C.border}`, flexShrink: 0 }}>
      <span style={{ fontSize: 9, fontWeight: 800, color: C.t3, textTransform: 'uppercase' }}>From</span>
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: `2px solid ${C.border}`, borderRadius: 5, padding: '3px 8px', background: C.card }}>
        <div style={{ width: 18, height: 18, borderRadius: 3, background: C.agUser, border: `2px solid ${C.border}` }} />
        <span style={{ fontSize: 10, fontWeight: 800, color: C.t1 }}>User</span>
      </div>
      <span style={{ fontSize: 9, fontWeight: 800, color: C.t3, textTransform: 'uppercase' }}>To</span>
      <ToBadge session={session} />
    </div>
  )
}

function Compose({ session, onSend, onStop }: {
  session: Session | null
  onSend: (prompt: string) => void
  onStop: () => void
}) {
  const [prompt, setPrompt] = useState('')
  const running = session?.status === 'running'
  const canSend = !!session && !!prompt.trim() && !running

  const send = () => {
    if (!canSend) return
    onSend(prompt.trim())
    setPrompt('')
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <FromToBar session={session} />
      <div style={{ flex: 1, padding: 12, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div style={{ fontSize: 9, fontWeight: 800, color: C.t3, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 5 }}>Editor</div>
        <textarea
          className="nb-in"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder={session ? 'Type a prompt… (Enter to send · Shift+Enter for newline)' : 'Select an agent first'}
          disabled={!session}
          style={{
            flex: 1, minHeight: 60, resize: 'none', background: C.input, border: `2px solid ${C.border}`,
            borderRadius: 5, padding: '9px 11px', color: C.t1, fontSize: 12, fontFamily: MONO, outline: 'none',
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
          {running
            ? <Btn variant="danger" onClick={onStop}>■ Stop</Btn>
            : <Btn variant="primary" onClick={send} disabled={!canSend}>Send · Now</Btn>}
        </div>
        <div style={{ fontSize: 9, color: C.t5, marginTop: 6 }}>
          Send timing (Queue/Next/Inject), templates, attach &amp; Revise need the Phase-1 prompt queue — not built.
        </div>
      </div>
    </div>
  )
}

interface HistItem { text: string; ts: string }

function extractPrompts(events: SDKEvent[]): HistItem[] {
  const out: HistItem[] = []
  for (const e of events) {
    if (e.sdk_type !== 'UserMessage') continue
    const blocks = toBlocks(e.content ?? e.data?.message?.content)
    const text = blocks.filter((b: any) => b.type === 'text' && b.text?.trim()).map((b: any) => b.text).join('\n')
    if (text.trim()) out.push({ text, ts: e.timestamp || '' })
  }
  return out
}

function History({ session, events }: { session: Session | null; events: SDKEvent[] }) {
  const items = extractPrompts(events)
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 12, background: C.card }}>
      {!session ? (
        <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 40 }}>Select an agent to see its prompt history.</div>
      ) : items.length === 0 ? (
        <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 40 }}>No prompts sent yet.</div>
      ) : (
        items.map((it, i) => (
          <div key={i} style={{ background: C.card, border: `2px solid ${C.border}`, borderLeft: `4px solid ${C.main}`, borderRadius: 5, boxShadow: C.shadowSm, padding: '8px 11px', marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 3 }}>
              <span style={{ fontSize: 9, fontWeight: 800, color: C.t5, textTransform: 'uppercase' }}>You</span>
              <span style={{ fontSize: 9, color: C.t5, fontFamily: MONO }}>{it.ts ? new Date(it.ts).toLocaleTimeString() : ''}</span>
            </div>
            <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{it.text}</div>
          </div>
        ))
      )}
    </div>
  )
}

export function PromptPanel({ session, events, onSend, onStop }: {
  session: Session | null
  events: SDKEvent[]
  onSend: (prompt: string) => void
  onStop: () => void
}) {
  const [tab, setTab] = useState<'compose' | 'history'>('compose')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ height: 34, minHeight: 34, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 10px', gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Prompt</span>
        <div style={{ flex: 1 }} />
        <Tabs tabs={[{ value: 'compose', label: 'Compose' }, { value: 'history', label: 'History' }]} active={tab} onChange={(t) => setTab(t as any)} />
      </div>
      {tab === 'compose'
        ? <Compose session={session} onSend={onSend} onStop={onStop} />
        : <History session={session} events={events} />}
    </div>
  )
}
