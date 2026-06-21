import React, { useState, useRef, useEffect, useCallback } from 'react'

// Sidecar URL — injected via preload or hardcoded for browser testing
const API = (window as any).awl?.sidecarUrl || 'http://127.0.0.1:7691'

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

const C = {
  bg: '#091318', surface: '#0c1820', card: '#112028', input: '#162a36',
  border: '#254050', borderH: '#30485a', dim: '#1c3444',
  t1: '#f0ebe0', t2: '#e8e0d4', t3: '#b8b0a4', t4: '#a0a8a4', t5: '#607078',
  gold: '#e8b058', coral: '#d0787a', teal: '#68b8c8', sage: '#68b890', blush: '#f3d2c1',
}

// Agent colors assigned round-robin
const AGENT_COLORS = [C.coral, C.teal, C.sage, C.gold, '#9b8ec4', '#c75d7e', '#5ba4cf', C.blush]

// ============================================================================
// Utility
// ============================================================================

function escapeHtml(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function formatCode(text: string): string {
  return escapeHtml(text).replace(/`([^`]+)`/g, `<code style="background:${C.input};color:${C.blush};padding:1px 4px;border-radius:3px;font-family:'JetBrains Mono',monospace;font-size:11px">$1</code>`)
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
    <div style={{ background: C.card, border: `2px solid ${C.border}`, borderLeft: `3px solid ${C.teal}`, borderRadius: 4, padding: '8px 12px', marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: C.teal, fontWeight: 700, fontSize: 11 }}>◆ {block.name}</span>
        {block.id && <span style={{ fontSize: 9, color: C.t5, fontFamily: 'monospace' }}>{block.id.slice(0, 8)}</span>}
      </div>
      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: C.t3, marginTop: 2, wordBreak: 'break-word' }}>{summary}</div>
      {full.length > 100 && (
        <>
          <div onClick={() => setExpanded(!expanded)} style={{ fontSize: 10, color: C.t5, cursor: 'pointer', marginTop: 4 }}>
            {expanded ? '▾ Collapse' : '▸ Full input'}
          </div>
          {expanded && (
            <pre style={{ fontSize: 9, color: C.t3, background: C.bg, padding: 8, borderRadius: 3, marginTop: 4, maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{full}</pre>
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
    <div style={{ background: C.surface, border: `2px solid ${C.border}`, borderRadius: 4, padding: '6px 12px', marginBottom: 6, fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: C.t3, maxHeight: expanded ? 300 : undefined, overflow: expanded ? 'auto' : undefined }}>
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
    <div style={{ background: C.card, border: `2px dashed ${C.border}`, borderRadius: 4, padding: '6px 12px', marginBottom: 6 }}>
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
    <div style={{ background: C.card, border: `2px dashed ${C.border}`, borderRadius: 4, padding: '8px 12px', marginBottom: 8 }}>
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
    <div style={{ background: C.surface, border: `2px solid ${C.border}`, borderRadius: 4, padding: '6px 12px', marginBottom: 6, fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: C.t3, display: 'flex', gap: 16 }}>
      <span style={{ color: C.gold, fontWeight: 700 }}>${cost.toFixed(4)}</span>
      <span>{turns} turns</span>
      <span>{(duration / 1000).toFixed(1)}s</span>
    </div>
  )
}

function RateLimitBanner() {
  return (
    <div style={{ background: `${C.gold}10`, border: `1px solid ${C.gold}30`, borderRadius: 4, padding: '6px 12px', marginBottom: 6, fontSize: 10, color: C.gold }}>
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
    const msg = event.data?.message || {}
    const content = msg.content || []
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
    const msg = event.data?.message || {}
    const content = msg.content || []
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
      <div style={{ height: 36, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 12px', justifyContent: 'space-between', flexShrink: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: C.t2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Sessions</span>
        <button onClick={onCreate} style={{ background: C.teal, color: C.t1, border: 'none', borderRadius: 4, padding: '4px 10px', fontSize: 10, fontWeight: 700, cursor: 'pointer' }}>+ New</button>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 6 }}>
        {sessions.map((s, i) => (
          <div key={s.session_id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', marginBottom: 3, borderRadius: 4, border: `2px solid ${s.session_id === activeId ? C.teal : C.border}`, background: s.session_id === activeId ? `${C.teal}10` : C.card, cursor: 'pointer' }}
            onClick={() => onSelect(s.session_id)}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: s.status === 'running' ? C.sage : s.status === 'error' ? C.coral : C.t5, flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: s.session_id === activeId ? C.teal : C.t2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {s.agent_type || 'session'}-{s.session_id}
              </div>
              <div style={{ fontSize: 9, color: C.t5, fontFamily: 'monospace' }}>
                {s.model || 'default'} · ${s.total_cost_usd.toFixed(3)}
              </div>
            </div>
            <button onClick={(e) => { e.stopPropagation(); onDelete(s.session_id) }}
              style={{ background: 'none', border: 'none', color: C.t5, fontSize: 12, cursor: 'pointer', padding: '0 2px' }}
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
      <div style={{ height: 36, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 12px', gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: C.t2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Event Feed</span>
        {sessionId && <span style={{ fontSize: 10, color: C.t5, fontFamily: 'monospace' }}>{sessionId}</span>}
        <div style={{ flex: 1 }} />
        <span style={{
          fontSize: 10, padding: '2px 8px', borderRadius: 99, fontWeight: 600,
          background: status === 'running' ? `${C.sage}20` : status === 'error' ? `${C.coral}20` : `${C.t5}15`,
          color: status === 'running' ? C.sage : status === 'error' ? C.coral : C.t5,
        }}>
          {status === 'running' ? '● Running' : status === 'error' ? '● Error' : '○ Idle'}
        </span>
      </div>
      <div ref={feedRef} onScroll={handleScroll} style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        {events.map((event, i) => <EventRenderer key={i} event={event} />)}
        {status === 'running' && (
          <div style={{ padding: '4px 0' }}>
            <span style={{ display: 'inline-block', width: 6, height: 14, background: C.teal, borderRadius: 1, animation: 'blink 1s infinite' }} />
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
        <div onClick={() => { setAutoScroll(true); feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' }) }}
          style={{ position: 'absolute', bottom: 80, right: 20, background: C.teal, color: C.t1, fontSize: 10, fontWeight: 700, padding: '4px 10px', borderRadius: 99, cursor: 'pointer', zIndex: 10 }}>
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
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
        placeholder={sessionId ? 'Type a prompt... (Enter to send, Shift+Enter for newline)' : 'Create a session first'}
        disabled={!sessionId}
        style={{
          flex: 1, background: C.input, border: `2px solid ${C.border}`, borderRadius: 4,
          padding: '8px 12px', color: C.t2, fontSize: 12, fontFamily: '"JetBrains Mono", monospace',
          resize: 'none', height: 56, outline: 'none',
        }}
      />
      {status === 'running' ? (
        <button onClick={onInterrupt} style={{
          background: 'transparent', color: C.coral, border: `2px solid ${C.coral}44`,
          borderRadius: 4, padding: '0 16px', fontSize: 11, fontWeight: 700, cursor: 'pointer', alignSelf: 'stretch',
        }}>Stop</button>
      ) : (
        <button onClick={handleSend} disabled={!sessionId || !prompt.trim()} style={{
          background: !sessionId || !prompt.trim() ? C.t5 : C.teal,
          color: C.t1, border: `2px solid ${!sessionId || !prompt.trim() ? C.t5 : C.teal}`,
          borderRadius: 4, padding: '0 20px', fontSize: 11, fontWeight: 700,
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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: C.bg, overflow: 'hidden' }}>
      {/* Title Bar */}
      <div style={{ height: 36, background: C.surface, borderBottom: `2px solid ${C.borderH}`, display: 'flex', alignItems: 'center', padding: '0 16px', gap: 12, flexShrink: 0, WebkitAppRegion: 'drag' as any }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: C.coral }} />
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: C.gold }} />
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: C.sage }} />
        </div>
        <span style={{ fontSize: 13, fontWeight: 800, color: C.t1 }}>AWL Dashboard</span>
        <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: `${C.teal}25`, color: C.teal, fontFamily: 'monospace', fontWeight: 700 }}>v0.2</span>
        <div style={{ flex: 1 }} />
        {!sidecarOk && (
          <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 99, background: `${C.coral}20`, color: C.coral, fontWeight: 600 }}>
            Sidecar offline
          </span>
        )}
        {sidecarOk && (
          <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 99, background: `${C.sage}15`, color: C.sage, fontWeight: 600 }}>
            Connected
          </span>
        )}
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left: Sessions */}
        <div style={{ width: 220, borderRight: `2px solid ${C.borderH}`, flexShrink: 0 }}>
          <SessionList sessions={sessions} activeId={activeId} onSelect={setActiveId} onCreate={createSession} onDelete={deleteSession} />
        </div>

        {/* Right: Event Feed + Prompt */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
          <EventFeed events={events} status={status} sessionId={activeId} />
          <PromptComposer sessionId={activeId} status={status} onSend={sendPrompt} onInterrupt={interrupt} />
        </div>
      </div>

      <style>{`
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        textarea::placeholder { color: ${C.t5}; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: ${C.surface}; }
        ::-webkit-scrollbar-thumb { background: ${C.borderH}; border-radius: 3px; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
      `}</style>
    </div>
  )
}
