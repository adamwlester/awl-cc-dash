// ============================================================================
// Prompt — Compose (send-timing + send-as-agent + templates + revise) + History
// ----------------------------------------------------------------------------
// Compose wires the send disposition (Now / Next / Queue / Hold), the
// send-as addressing (From = User or any agent → the focused agent), the
// templates store (insert / save), and the utility-LLM passes (Revise scope +
// Summarize). History lists the focused agent's own prompts from its transcript.
// ============================================================================

import React, { useEffect, useState } from 'react'
import { C, FONT, MONO } from './tokens'
import { Tabs, Btn, Segmented } from './ui'
import { AgentTile } from './AgentTile'
import { toBlocks } from './events'
import { api, type Session, type SDKEvent, type SendOpts, type Disposition, type Template, type SendResult } from './api'

const DISPOSITIONS: { value: Disposition; label: string }[] = [
  { value: 'now', label: 'Now' }, { value: 'next', label: 'Next' },
  { value: 'queue', label: 'Queue' }, { value: 'hold', label: 'Hold' },
]
const REVISE_SCOPES = [
  { value: 'grammar', label: 'Grammar' }, { value: 'language', label: 'Language' }, { value: 'refactor', label: 'Refactor' },
]

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

function FromToBar({ session, sessions, source, onSource }: {
  session: Session | null
  sessions: Session[]
  source: string
  onSource: (v: string) => void
}) {
  const inputStyle: React.CSSProperties = {
    background: C.card, border: `2px solid ${C.border}`, borderRadius: 5, padding: '3px 6px',
    fontSize: 10, fontWeight: 800, color: C.t1, fontFamily: FONT, outline: 'none',
  }
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', background: C.surface, borderBottom: `2px solid ${C.border}`, flexShrink: 0, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 9, fontWeight: 800, color: C.t3, textTransform: 'uppercase' }}>From</span>
      <select className="nb-in" style={inputStyle} value={source} onChange={e => onSource(e.target.value)}>
        <option value="user">User</option>
        {sessions.filter(s => s.session_id !== session?.session_id).map(s => (
          <option key={s.session_id} value={s.session_id}>
            {String(s.identity?.number ?? '').padStart(2, '0')} {s.identity?.name || s.identity?.role || s.session_id}
          </option>
        ))}
      </select>
      <span style={{ fontSize: 9, fontWeight: 800, color: C.t3, textTransform: 'uppercase' }}>To</span>
      <ToBadge session={session} />
    </div>
  )
}

function Compose({ session, sessions, onSend, onStop }: {
  session: Session | null
  sessions: Session[]
  onSend: (prompt: string, opts?: SendOpts) => Promise<SendResult | null>
  onStop: () => void
}) {
  const [prompt, setPrompt] = useState('')
  const [source, setSource] = useState('user')
  const [disp, setDisp] = useState<Disposition>('queue')
  const [scope, setScope] = useState('grammar')
  const [busy, setBusy] = useState<null | 'revise' | 'summarize' | 'send'>(null)
  const [result, setResult] = useState<string>('')
  const [templates, setTemplates] = useState<Template[]>([])
  const [saveName, setSaveName] = useState('')
  const [showSave, setShowSave] = useState(false)

  const running = session?.status === 'running'
  const hasText = !!prompt.trim()
  const canSend = !!session && hasText && busy === null

  const loadTemplates = () => api.templates().then(t => setTemplates(t || []))
  useEffect(() => { loadTemplates() }, [])

  const send = async () => {
    if (!canSend || !session) return
    setBusy('send')
    const r = await onSend(prompt.trim(), { source, recipients: [session.session_id], disposition: disp })
    setBusy(null)
    if (r) {
      setResult(r.status === 'queued' ? `queued @${r.position ?? '?'}` : r.status)
      if (disp !== 'hold') setPrompt('')
    } else {
      setResult('send failed')
    }
  }

  const revise = async () => {
    if (!hasText) return
    setBusy('revise')
    const r = await api.revise(prompt, scope as any)
    setBusy(null)
    if (r?.result) { setPrompt(r.result); setResult(`revised · ${scope}`) } else setResult('revise failed')
  }
  const summarize = async () => {
    if (!hasText) return
    setBusy('summarize')
    const r = await api.summarize(prompt)
    setBusy(null)
    if (r?.result) { setPrompt(r.result); setResult('summarized') } else setResult('summarize failed')
  }

  const insertTemplate = (id: string) => {
    const t = templates.find(x => x.id === id)
    if (!t) return
    setPrompt(prev => (prev.trim() ? `${prev}\n${t.body}` : t.body))
  }
  const saveTemplate = async () => {
    const name = saveName.trim()
    if (!name || !hasText) return
    await api.addTemplate({ name, body: prompt })
    setSaveName(''); setShowSave(false)
    loadTemplates()
    setResult(`saved template "${name}"`)
  }

  const smallBtn: React.CSSProperties = { padding: '3px 8px', fontSize: 10 }
  const inputStyle: React.CSSProperties = {
    background: C.card, border: `2px solid ${C.border}`, borderRadius: 5, padding: '4px 7px',
    fontSize: 10, color: C.t1, fontFamily: FONT, outline: 'none',
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <FromToBar session={session} sessions={sessions} source={source} onSource={setSource} />
      <div style={{ flex: 1, padding: 12, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {/* toolbar: templates + revise/summarize */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 7, flexWrap: 'wrap' }}>
          <select className="nb-in" style={{ ...inputStyle, fontFamily: MONO, maxWidth: 130 }} value="" disabled={!templates.length}
            onChange={e => { if (e.target.value) insertTemplate(e.target.value); e.currentTarget.value = '' }}>
            <option value="">{templates.length ? 'Insert template…' : 'No templates'}</option>
            {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <Btn variant="cream" onClick={() => setShowSave(s => !s)} disabled={!hasText} style={smallBtn}>＋ Save</Btn>
          <div style={{ flex: 1 }} />
          <select className="nb-in" style={inputStyle} value={scope} onChange={e => setScope(e.target.value)}>
            {REVISE_SCOPES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          <Btn variant="secondary" onClick={revise} disabled={!hasText || busy !== null} style={smallBtn}>{busy === 'revise' ? '…' : 'Revise'}</Btn>
          <Btn variant="cream" onClick={summarize} disabled={!hasText || busy !== null} style={smallBtn}>{busy === 'summarize' ? '…' : 'Summarize'}</Btn>
        </div>
        {showSave && (
          <div style={{ display: 'flex', gap: 6, marginBottom: 7 }}>
            <input className="nb-in" style={{ ...inputStyle, flex: 1 }} value={saveName} placeholder="template name" onChange={e => setSaveName(e.target.value)} />
            <Btn variant="primary" onClick={saveTemplate} disabled={!saveName.trim() || !hasText} style={smallBtn}>Save template</Btn>
          </div>
        )}

        <div style={{ fontSize: 9, fontWeight: 800, color: C.t3, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 5 }}>Editor</div>
        <textarea
          className="nb-in"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send() } }}
          placeholder={session ? 'Type a prompt… (Ctrl/⌘+Enter to send)' : 'Select an agent first'}
          disabled={!session}
          style={{
            flex: 1, minHeight: 56, resize: 'none', background: C.input, border: `2px solid ${C.border}`,
            borderRadius: 5, padding: '9px 11px', color: C.t1, fontSize: 12, fontFamily: MONO, outline: 'none',
          }}
        />

        {/* send-timing + send */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
          <div style={{ flex: 1 }}>
            <Segmented options={DISPOSITIONS} value={disp} onChange={(v) => setDisp(v as Disposition)} />
          </div>
          {running && <Btn variant="danger" onClick={onStop}>■ Stop</Btn>}
          <Btn variant="primary" onClick={send} disabled={!canSend}>{busy === 'send' ? 'Sending…' : `Send · ${DISPOSITIONS.find(d => d.value === disp)?.label}`}</Btn>
        </div>
        <div style={{ fontSize: 9, color: C.t5, marginTop: 6, display: 'flex', gap: 8 }}>
          <span>Now interrupts · Next jumps the queue · Queue waits · Hold stages (manual release).</span>
          {result && <span style={{ color: C.t3, fontWeight: 800 }}>· {result}</span>}
        </div>
      </div>
    </div>
  )
}

interface HistItem { text: string; ts: string }

function extractPrompts(events: SDKEvent[]): HistItem[] {
  const out: HistItem[] = []
  for (const e of events) {
    if (e.sdk_type !== 'UserMessage' && e.type !== 'user') continue
    const blocks = toBlocks(e.content ?? e.data?.message?.content)
    const text = blocks.filter((b: any) => b.type === 'text' && b.text?.trim()).map((b: any) => b.text).join('\n')
    if (text.trim()) out.push({ text, ts: e.timestamp || e.ts || '' })
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
              <span style={{ fontSize: 9, fontWeight: 800, color: C.t5, textTransform: 'uppercase' }}>Prompt</span>
              <span style={{ fontSize: 9, color: C.t5, fontFamily: MONO }}>{it.ts ? new Date(it.ts).toLocaleTimeString() : ''}</span>
            </div>
            <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{it.text}</div>
          </div>
        ))
      )}
    </div>
  )
}

export function PromptPanel({ session, sessions, events, onSend, onStop }: {
  session: Session | null
  sessions: Session[]
  events: SDKEvent[]
  onSend: (prompt: string, opts?: SendOpts) => Promise<SendResult | null>
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
        ? <Compose session={session} sessions={sessions} onSend={onSend} onStop={onStop} />
        : <History session={session} events={events} />}
    </div>
  )
}
