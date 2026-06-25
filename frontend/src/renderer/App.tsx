import React, { useState, useRef, useEffect, useCallback } from 'react'

// Sidecar URL — injected via preload or hardcoded for browser testing
const API = (window as any).awl?.sidecarUrl || 'http://127.0.0.1:7690'

// ============================================================================
// Types
// ============================================================================

interface Session {
  session_id: string
  status: string
  model: string | null
  agent_type: string | null
  permission_mode: string
  total_cost_usd: number
  total_turns: number
  event_count: number
  created_at: string
}

interface SDKEvent {
  type: string
  subtype?: string
  sdk_type?: string
  timestamp?: string
  data?: any
  [key: string]: any
}

// ============================================================================
// Colors
// ============================================================================

// Neobrutalism light-theme palette — values mirror design/tokens.css (the single
// source of truth). Existing keys are remapped onto design tokens; a few keys are
// added (main/select/btn/rule/codeBg/shadows + soft status tints) so the same
// component styles can speak the design language. See design/DESIGN.md.
const C = {
  // Surfaces — three warm surfaces + a button tint + a hairline
  bg: '#fef6e4',        // --background  canvas / panel bodies / scroll wells
  surface: '#f5ecd9',   // --surface-3  chrome: panel headers, footers, toolbars
  card: '#ffffff',      // --secondary-background  cards
  input: '#ffffff',     // form inputs (white, like cards)
  btn: '#fbf5e8',       // --surface-btn  low-emphasis action buttons
  codeBg: '#f5ecd9',    // inline code / code blocks (--surface-3)
  rule: '#d8cfb8',      // --rule  hairline between rows
  // Border + ink (2px navy everywhere)
  border: '#001858',    // --border
  borderH: '#001858',   // --border (kept for column / title-bar dividers)
  dim: '#a9dde7',       // --select  light-teal selection fill
  // Text ramp
  t1: '#001858', t2: '#001858',          // --foreground  primary ink / headings / body
  t3: '#5b5f86', t4: '#5b5f86',          // --muted
  t5: '#9a93b4',                          // --muted-2  faint (timestamps, placeholders)
  // Accents — pink=primary · teal=secondary · cream=low-emphasis · red=danger
  main: '#f582ae',      // --main  PRIMARY (Send · New · badges · title bar)
  mainFg: '#001858',    // --main-foreground / --secondary-foreground  ink on accents
  select: '#a9dde7',    // --select  selection fill (light teal)
  teal: '#8bd3dd',      // --secondary  secondary / active / selected ring
  gold: '#d98a2b',      // --warning  attention / cost
  coral: '#d23b6a',     // --danger  stop / error / offline
  sage: '#2f9e6f',      // --success  running / connected
  blush: '#f582ae',     // accent slot → pink
  // Soft status containers (Material-3 "container" roles) for connectivity pills
  successSoft: '#e7f5ee', successText: '#1f6f4d',
  dangerSoft: '#fbe7ee',
  warnSoft: '#f6e6cf', warnText: '#9a6710',
  // Hard offset shadows (no blur) — raised / interactive elements only
  shadow: '4px 4px 0 0 #001858', shadowSm: '2px 2px 0 0 #001858',
}

// Agent colors assigned round-robin — the design "Jewel" family (--ag-* in tokens.css)
const AGENT_COLORS = ['#aa3a61', '#008370', '#008149', '#9d5400', '#7152b5', '#9e3f84', '#0076ab', '#aa4600']

// ============================================================================
// Utility
// ============================================================================

function escapeHtml(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function formatCode(text: string): string {
  return escapeHtml(text).replace(/`([^`]+)`/g, `<code style="background:${C.codeBg};color:${C.t1};border:1.5px solid ${C.rule};padding:1px 4px;border-radius:3px;font-family:'JetBrains Mono',monospace;font-size:11px">$1</code>`)
}

// ============================================================================
// Event Components
// ============================================================================

function ToolCallCard({ block }: { block: any }) {
  const [expanded, setExpanded] = useState(false)
  const input = block.input || {}
  const summary = input.command || input.file_path || input.pattern || input.query || JSON.stringify(input).slice(0, 100)
  const full = JSON.stringify(input, null, 2)

  return (
    <div style={{ background: C.card, border: `2px solid ${C.border}`, borderLeft: `4px solid ${C.teal}`, borderRadius: 5, boxShadow: C.shadowSm, padding: '8px 12px', marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: C.t1, fontWeight: 800, fontSize: 11 }}>◆ {block.name}</span>
        {block.id && <span style={{ fontSize: 9, color: C.t5, fontFamily: 'monospace' }}>{block.id.slice(0, 8)}</span>}
      </div>
      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: C.t3, marginTop: 2, wordBreak: 'break-word' }}>{summary}</div>
      {full.length > 100 && (
        <>
          <div onClick={() => setExpanded(!expanded)} style={{ fontSize: 10, color: C.t5, cursor: 'pointer', marginTop: 4 }}>
            {expanded ? '▾ Collapse' : '▸ Full input'}
          </div>
          {expanded && (
            <pre style={{ fontSize: 9, color: C.t3, background: C.codeBg, border: `1.5px solid ${C.rule}`, padding: 8, borderRadius: 3, marginTop: 4, maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{full}</pre>
          )}
        </>
      )}
    </div>
  )
}

function ToolResultCard({ content }: { content: any }) {
  const [expanded, setExpanded] = useState(false)
  let text = ''
  if (typeof content === 'string') text = content
  else if (Array.isArray(content)) text = content.map((c: any) => c.text || c.content || '').join('\n')
  else text = JSON.stringify(content, null, 2)

  const lines = text.split('\n')
  const preview = lines.slice(0, 6).join('\n')

  return (
    <div style={{ background: C.card, border: `2px solid ${C.border}`, borderRadius: 5, boxShadow: C.shadowSm, padding: '6px 12px', marginBottom: 8, fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: C.t3, maxHeight: expanded ? 300 : undefined, overflow: expanded ? 'auto' : undefined }}>
      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }}>{expanded ? text : preview}</pre>
      {lines.length > 6 && (
        <div onClick={() => setExpanded(!expanded)} style={{ fontSize: 10, color: C.t5, cursor: 'pointer', marginTop: 4 }}>
          {expanded ? '▾ Collapse' : `▸ Show all (${lines.length} lines)`}
        </div>
      )}
    </div>
  )
}

function TextBlock({ text }: { text: string }) {
  return (
    <div style={{ padding: '4px 0', marginBottom: 6, fontSize: 12, lineHeight: 1.65, color: C.t2 }}
      dangerouslySetInnerHTML={{ __html: formatCode(text).replace(/\n/g, '<br>') }}
    />
  )
}

function ThinkingBlock({ thinking }: { thinking: string }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div style={{ background: C.card, border: `2px dashed ${C.border}`, borderRadius: 5, padding: '6px 12px', marginBottom: 8 }}>
      <div onClick={() => setExpanded(!expanded)} style={{ fontSize: 10, color: C.t5, cursor: 'pointer' }}>
        {expanded ? '▾' : '▸'} Thinking ({thinking.length} chars)
      </div>
      {expanded && (
        <div style={{ fontSize: 10, color: C.t4, fontStyle: 'italic', marginTop: 4, maxHeight: 200, overflow: 'auto', lineHeight: 1.5 }}>{thinking}</div>
      )}
    </div>
  )
}

function SystemInitCard({ data }: { data: any }) {
  const [expanded, setExpanded] = useState(false)
  const model = data?.model || '?'
  const mode = data?.permissionMode || '?'
  const tools = Array.isArray(data?.tools) ? data.tools.length : '?'

  return (
    <div style={{ background: C.card, border: `2px dashed ${C.border}`, borderRadius: 5, padding: '8px 12px', marginBottom: 8 }}>
      <div onClick={() => setExpanded(!expanded)} style={{ cursor: 'pointer', fontSize: 10, color: C.t5 }}>
        {expanded ? '▾' : '▸'} Session init — {model} · {mode} · {tools} tools
      </div>
      {expanded && (
        <pre style={{ fontSize: 9, color: C.t3, marginTop: 6, maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
          {JSON.stringify(data, null, 2).slice(0, 3000)}
        </pre>
      )}
    </div>
  )
}

function ResultBar({ event }: { event: SDKEvent }) {
  const d = event.data || event
  const cost = d.total_cost_usd || 0
  const turns = d.num_turns || 0
  const duration = d.duration_ms || 0
  return (
    <div style={{ background: C.card, border: `2px solid ${C.border}`, borderRadius: 5, padding: '6px 12px', marginBottom: 8, fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: C.t3, display: 'flex', gap: 16 }}>
      <span style={{ color: C.gold, fontWeight: 800 }}>${cost.toFixed(4)}</span>
      <span>{turns} turns</span>
      <span>{(duration / 1000).toFixed(1)}s</span>
    </div>
  )
}

function RateLimitBanner() {
  return (
    <div style={{ background: C.warnSoft, border: `2px solid ${C.border}`, borderRadius: 5, padding: '6px 12px', marginBottom: 8, fontSize: 10, fontWeight: 700, color: C.warnText }}>
      ⏳ Rate limit — Claude is waiting before retrying
    </div>
  )
}

function EventRenderer({ event }: { event: SDKEvent }) {
  const sdk = event.sdk_type || ''
  const sub = event.subtype || ''

  // Skip hook noise
  if (sub === 'hook_started' || sub === 'hook_response') return null
  if (event.type === 'status_change') return null

  // System init
  if (sub === 'init') return <SystemInitCard data={event.data || {}} />

  // Assistant message
  if (sdk === 'AssistantMessage') {
    // Sidecar flattens message attrs to the top level (event.content); keep the
    // older data.message.content shape as a fallback.
    const content = event.content || event.data?.message?.content || []
    return (
      <>
        {content.map((block: any, i: number) => {
          if (block.type === 'tool_use') return <ToolCallCard key={i} block={block} />
          if (block.type === 'text' && block.text?.trim()) return <TextBlock key={i} text={block.text} />
          if (block.type === 'thinking' && block.thinking) return <ThinkingBlock key={i} thinking={block.thinking} />
          return null
        })}
      </>
    )
  }

  // User message (tool results)
  if (sdk === 'UserMessage') {
    // Sidecar flattens message attrs to the top level (event.content); keep the
    // older data.message.content shape as a fallback.
    const content = event.content || event.data?.message?.content || []
    return (
      <>
        {content.map((block: any, i: number) => {
          if (block.type === 'tool_result' && block.content) {
            return <ToolResultCard key={i} content={block.content} />
          }
          return null
        })}
      </>
    )
  }

  // Result
  if (event.type === 'result') return <ResultBar event={event} />

  // Rate limit
  if (sdk === 'RateLimitEvent') return <RateLimitBanner />

  return null
}

// ============================================================================
// Session List (Left Panel)
// ============================================================================

function SessionList({ sessions, activeId, onSelect, onCreate, onDelete }: {
  sessions: Session[]
  activeId: string | null
  onSelect: (id: string) => void
  onCreate: () => void
  onDelete: (id: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ height: 36, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 10px', justifyContent: 'space-between', flexShrink: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Sessions</span>
        <button className="nb-btn" onClick={onCreate} style={{ background: C.main, color: C.mainFg, border: `2px solid ${C.border}`, borderRadius: 5, boxShadow: C.shadowSm, padding: '3px 10px', fontSize: 10, fontWeight: 800, cursor: 'pointer' }}>+ New</button>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 6 }}>
        {sessions.map((s, i) => (
          <div key={s.session_id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', marginBottom: 6, borderRadius: 5, border: `2px solid ${C.border}`, background: s.session_id === activeId ? C.select : C.card, boxShadow: s.session_id === activeId ? C.shadow : C.shadowSm, cursor: 'pointer' }}
            onClick={() => onSelect(s.session_id)}>
            <div style={{ width: 9, height: 9, borderRadius: '50%', border: `2px solid ${C.border}`, background: s.status === 'running' ? C.sage : s.status === 'error' ? C.coral : C.t5, flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 11, fontWeight: 800, color: C.t1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {s.agent_type || 'session'}-{s.session_id}
              </div>
              <div style={{ fontSize: 9, color: C.t3, fontFamily: 'monospace' }}>
                {s.model || 'default'} · ${s.total_cost_usd.toFixed(3)}
              </div>
            </div>
            <button onClick={(e) => { e.stopPropagation(); onDelete(s.session_id) }}
              style={{ background: 'none', border: 'none', color: C.t5, fontSize: 13, fontWeight: 700, cursor: 'pointer', padding: '0 2px' }}
              title="Close session">×</button>
          </div>
        ))}
        {sessions.length === 0 && (
          <div style={{ fontSize: 10, color: C.t5, textAlign: 'center', marginTop: 24, lineHeight: 1.6 }}>
            No sessions.<br />Click "+ New" to start.
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// Event Feed (Right Panel)
// ============================================================================

function EventFeed({ events, status, sessionId }: { events: SDKEvent[], status: string, sessionId: string | null }) {
  const feedRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [events, autoScroll])

  const handleScroll = useCallback(() => {
    if (!feedRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = feedRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ height: 36, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 10px', gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Event Feed</span>
        {sessionId && <span style={{ fontSize: 10, color: C.t3, fontFamily: 'monospace' }}>{sessionId}</span>}
        <div style={{ flex: 1 }} />
        <span style={{
          fontSize: 9.5, padding: '2px 8px', borderRadius: 5, fontWeight: 800, border: `2px solid ${C.border}`,
          background: status === 'running' ? C.successSoft : status === 'error' ? C.dangerSoft : C.surface,
          color: status === 'running' ? C.successText : status === 'error' ? C.coral : C.t3,
        }}>
          {status === 'running' ? '● Running' : status === 'error' ? '● Error' : '○ Idle'}
        </span>
      </div>
      <div ref={feedRef} onScroll={handleScroll} style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        {events.map((event, i) => <EventRenderer key={i} event={event} />)}
        {status === 'running' && (
          <div style={{ padding: '4px 0' }}>
            <span style={{ display: 'inline-block', width: 6, height: 14, background: C.border, borderRadius: 1, animation: 'blink 1s infinite' }} />
          </div>
        )}
        {!sessionId && (
          <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 60 }}>
            Select or create a session to begin.
          </div>
        )}
        {sessionId && events.length === 0 && status !== 'running' && (
          <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 60 }}>
            Session ready. Send a prompt below.
          </div>
        )}
      </div>
      {!autoScroll && events.length > 0 && (
        <div className="nb-btn" onClick={() => { setAutoScroll(true); feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' }) }}
          style={{ position: 'absolute', bottom: 80, right: 20, background: C.teal, color: C.mainFg, fontSize: 10, fontWeight: 800, padding: '4px 10px', border: `2px solid ${C.border}`, borderRadius: 5, boxShadow: C.shadowSm, cursor: 'pointer', zIndex: 10 }}>
          ↓ New events
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Prompt Composer
// ============================================================================

function PromptComposer({ sessionId, status, onSend, onInterrupt }: {
  sessionId: string | null, status: string, onSend: (prompt: string) => void, onInterrupt: () => void
}) {
  const [prompt, setPrompt] = useState('')

  const handleSend = () => {
    if (!prompt.trim() || !sessionId || status === 'running') return
    onSend(prompt.trim())
    setPrompt('')
  }

  return (
    <div style={{ borderTop: `2px solid ${C.border}`, padding: 12, background: C.surface, display: 'flex', gap: 8, flexShrink: 0 }}>
      <textarea
        className="nb-in"
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
        placeholder={sessionId ? 'Type a prompt... (Enter to send, Shift+Enter for newline)' : 'Create a session first'}
        disabled={!sessionId}
        style={{
          flex: 1, background: C.input, border: `2px solid ${C.border}`, borderRadius: 5,
          padding: '8px 12px', color: C.t2, fontSize: 12, fontFamily: '"JetBrains Mono", monospace',
          resize: 'none', height: 56, outline: 'none',
        }}
      />
      {status === 'running' ? (
        <button className="nb-btn" onClick={onInterrupt} style={{
          background: C.btn, color: C.coral, border: `2px solid ${C.border}`, boxShadow: C.shadowSm,
          borderRadius: 5, padding: '0 16px', fontSize: 11, fontWeight: 800, cursor: 'pointer', alignSelf: 'stretch',
        }}>Stop</button>
      ) : (
        <button className="nb-btn" onClick={handleSend} disabled={!sessionId || !prompt.trim()} style={{
          background: !sessionId || !prompt.trim() ? C.btn : C.main,
          color: C.mainFg, border: `2px solid ${C.border}`, boxShadow: C.shadowSm,
          borderRadius: 5, padding: '0 20px', fontSize: 11, fontWeight: 800,
          cursor: !sessionId || !prompt.trim() ? 'default' : 'pointer', alignSelf: 'stretch', opacity: !sessionId || !prompt.trim() ? 0.4 : 1,
        }}>Send</button>
      )}
    </div>
  )
}

// ============================================================================
// Main App
// ============================================================================

export function App() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [events, setEvents] = useState<SDKEvent[]>([])
  const [status, setStatus] = useState('idle')
  const [sidecarOk, setSidecarOk] = useState(false)

  // Health check
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API}/health`)
        setSidecarOk(res.ok)
      } catch { setSidecarOk(false) }
    }
    check()
    const i = setInterval(check, 5000)
    return () => clearInterval(i)
  }, [])

  // Poll for session list
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API}/sessions`)
        if (res.ok) setSessions(await res.json())
      } catch { /* sidecar down */ }
    }
    poll()
    const i = setInterval(poll, 2000)
    return () => clearInterval(i)
  }, [])

  // Poll for events when a session is active
  useEffect(() => {
    if (!activeId) { setEvents([]); setStatus('idle'); return }
    let cancelled = false
    const poll = async () => {
      while (!cancelled) {
        try {
          const [evRes, sRes] = await Promise.all([
            fetch(`${API}/sessions/${activeId}/history`),
            fetch(`${API}/sessions/${activeId}`),
          ])
          if (evRes.ok) setEvents(await evRes.json())
          if (sRes.ok) {
            const s = await sRes.json()
            setStatus(s.status)
          }
        } catch { /* sidecar down */ }
        await new Promise(r => setTimeout(r, 800))
      }
    }
    poll()
    return () => { cancelled = true }
  }, [activeId])

  const createSession = async () => {
    try {
      const res = await fetch(`${API}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ permission_mode: 'acceptEdits' }),
      })
      const session = await res.json()
      setActiveId(session.session_id)
      setEvents([])
    } catch (e) {
      console.error('Failed to create session:', e)
    }
  }

  const deleteSession = async (id: string) => {
    try {
      await fetch(`${API}/sessions/${id}`, { method: 'DELETE' })
      if (activeId === id) { setActiveId(null); setEvents([]) }
    } catch { /* ignore */ }
  }

  const sendPrompt = async (prompt: string) => {
    if (!activeId) return
    try {
      await fetch(`${API}/sessions/${activeId}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      })
    } catch (e) {
      console.error('Failed to send:', e)
    }
  }

  const interrupt = async () => {
    if (!activeId) return
    try {
      await fetch(`${API}/sessions/${activeId}/interrupt`, { method: 'POST' })
    } catch { /* ignore */ }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: C.bg, color: C.t1, fontFamily: "'Archivo', sans-serif", overflow: 'hidden' }}>
      {/* Title Bar */}
      <div style={{ height: 36, background: C.main, borderBottom: `2px solid ${C.borderH}`, display: 'flex', alignItems: 'center', padding: '0 16px', gap: 12, flexShrink: 0, WebkitAppRegion: 'drag' as any }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', border: `2px solid ${C.border}`, background: C.coral }} />
          <div style={{ width: 10, height: 10, borderRadius: '50%', border: `2px solid ${C.border}`, background: C.gold }} />
          <div style={{ width: 10, height: 10, borderRadius: '50%', border: `2px solid ${C.border}`, background: C.sage }} />
        </div>
        <span style={{ fontSize: 13, fontWeight: 800, color: C.mainFg }}>AWL Dashboard</span>
        <span style={{ fontSize: 9, padding: '2px 7px', borderRadius: 5, background: C.card, color: C.t1, border: `2px solid ${C.border}`, fontFamily: 'monospace', fontWeight: 800 }}>v0.2</span>
        <div style={{ flex: 1 }} />
        {!sidecarOk && (
          <span style={{ fontSize: 9.5, padding: '2px 8px', borderRadius: 5, background: C.dangerSoft, color: C.coral, border: `2px solid ${C.border}`, fontWeight: 800 }}>
            Sidecar offline
          </span>
        )}
        {sidecarOk && (
          <span style={{ fontSize: 9.5, padding: '2px 8px', borderRadius: 5, background: C.successSoft, color: C.successText, border: `2px solid ${C.border}`, fontWeight: 800 }}>
            Connected
          </span>
        )}
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left: Sessions */}
        <div style={{ width: 220, borderRight: `2px solid ${C.borderH}`, background: C.bg, flexShrink: 0 }}>
          <SessionList sessions={sessions} activeId={activeId} onSelect={setActiveId} onCreate={createSession} onDelete={deleteSession} />
        </div>

        {/* Right: Event Feed + Prompt */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
          <EventFeed events={events} status={status} sessionId={activeId} />
          <PromptComposer sessionId={activeId} status={status} onSend={sendPrompt} onInterrupt={interrupt} />
        </div>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        textarea::placeholder { color: ${C.t5}; }
        /* Neobrutalism press: raised at rest, slides into its hard shadow on hover/active */
        .nb-btn { transition: transform .07s ease, box-shadow .07s ease; }
        .nb-btn:hover:not(:disabled), .nb-btn:active:not(:disabled) { transform: translate(2px, 2px); box-shadow: none !important; }
        .nb-in:focus { box-shadow: ${C.shadowSm}; }
        /* Palette-matched scrollbars (mirrors design tokens) */
        ::-webkit-scrollbar { width: 9px; height: 9px; }
        ::-webkit-scrollbar-track { background: ${C.surface}; border-left: 2px solid ${C.border}; }
        ::-webkit-scrollbar-thumb { background: ${C.t3}; border: 2px solid ${C.border}; }
        ::-webkit-scrollbar-thumb:hover { background: ${C.teal}; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
      `}</style>
    </div>
  )
}
