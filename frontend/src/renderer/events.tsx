// ============================================================================
// Event render components — the message stream (assistant/user blocks)
// ----------------------------------------------------------------------------
// Extracted from the original App.tsx stub; these are the proven renderers for
// the bridge transcript's Anthropic-format content blocks. (The SDK-era
// ResultBar — which showed a $cost the bridge never supplies — was dropped: the
// bridge emits no `result` events, so it was dead code.)
// ============================================================================

import React, { useState } from 'react'
import { C, MONO } from './tokens'
import type { SDKEvent } from './api'

function escapeHtml(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function formatCode(text: string): string {
  return escapeHtml(text).replace(
    /`([^`]+)`/g,
    `<code style="background:${C.codeBg};color:${C.t1};border:1.5px solid ${C.rule};padding:1px 4px;border-radius:3px;font-family:${MONO};font-size:11px">$1</code>`
  )
}

// Message content can be a list of typed blocks (the SDK shape) OR a bare string:
// the bridge replays a user's own prompt as `content: "<prompt text>"`. Normalize
// to blocks so EventRenderer can always .map over it.
export function toBlocks(content: any): any[] {
  if (Array.isArray(content)) return content
  if (typeof content === 'string') return content.trim() ? [{ type: 'text', text: content }] : []
  return []
}

function ToolCallCard({ block }: { block: any }) {
  const [expanded, setExpanded] = useState(false)
  const input = block.input || {}
  const summary = input.command || input.file_path || input.pattern || input.query || JSON.stringify(input).slice(0, 100)
  const full = JSON.stringify(input, null, 2)
  return (
    <div style={{ background: C.card, border: `2px solid ${C.border}`, borderLeft: `4px solid ${C.teal}`, borderRadius: 5, boxShadow: C.shadowSm, padding: '8px 12px', marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: C.t1, fontWeight: 800, fontSize: 11 }}>◆ {block.name}</span>
        {block.id && <span style={{ fontSize: 9, color: C.t5, fontFamily: MONO }}>{block.id.slice(0, 8)}</span>}
      </div>
      <div style={{ fontFamily: MONO, fontSize: 10, color: C.t3, marginTop: 2, wordBreak: 'break-word' }}>{summary}</div>
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
    <div style={{ background: C.card, border: `2px solid ${C.border}`, borderRadius: 5, boxShadow: C.shadowSm, padding: '6px 12px', marginBottom: 8, fontFamily: MONO, fontSize: 10, color: C.t3, maxHeight: expanded ? 300 : undefined, overflow: expanded ? 'auto' : undefined }}>
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

// The user's own prompt, echoed into the feed (bridge replays it as a bare
// string -> one text block). Pink left accent + "You" label.
function UserPromptBlock({ text }: { text: string }) {
  return (
    <div style={{ background: C.card, border: `2px solid ${C.border}`, borderLeft: `4px solid ${C.main}`, borderRadius: 5, boxShadow: C.shadowSm, padding: '6px 12px', marginBottom: 8 }}>
      <div style={{ fontSize: 9, fontWeight: 800, color: C.t5, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>You</div>
      <div style={{ fontSize: 12, lineHeight: 1.6, color: C.t2, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{text}</div>
    </div>
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

function RateLimitBanner() {
  return (
    <div style={{ background: C.warnSoft, border: `2px solid ${C.border}`, borderRadius: 5, padding: '6px 12px', marginBottom: 8, fontSize: 10, fontWeight: 700, color: C.warnText }}>
      ⏳ Rate limit — Claude is waiting before retrying
    </div>
  )
}

// A compact one-line "system" note for the merged-bus events that aren't
// assistant/user turns — link fires, injects, scratch deltas, warnings,
// plan/decision raises, errors. Colored left accent keys the kind.
function SystemLine({ accent, icon, label, detail }: { accent: string; icon: string; label: string; detail?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, background: C.card, border: `2px solid ${C.border}`, borderLeft: `4px solid ${accent}`, borderRadius: 5, padding: '5px 10px', marginBottom: 8 }}>
      <span style={{ fontSize: 11 }}>{icon}</span>
      <span style={{ fontSize: 9.5, fontWeight: 800, color: C.t2, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>{label}</span>
      {detail ? <span style={{ fontSize: 10.5, color: C.t3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, minWidth: 0 }}>{detail}</span> : null}
    </div>
  )
}

export function EventRenderer({ event }: { event: SDKEvent }) {
  const sdk = event.sdk_type || ''
  const sub = event.subtype || ''
  const t = event.type

  if (sub === 'hook_started' || sub === 'hook_response') return null
  if (t === 'status_change') return null
  if (sub === 'init') return <SystemInitCard data={event.data || {}} />

  if (sdk === 'AssistantMessage' || t === 'assistant') {
    const content = toBlocks(event.content ?? event.data?.message?.content)
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

  if (sdk === 'UserMessage' || t === 'user') {
    const content = toBlocks(event.content ?? event.data?.message?.content)
    return (
      <>
        {content.map((block: any, i: number) => {
          if (block.type === 'text' && block.text?.trim()) return <UserPromptBlock key={i} text={block.text} />
          if (block.type === 'tool_result') return <ToolResultCard key={i} content={block.content ?? ''} />
          return null
        })}
      </>
    )
  }

  if (sdk === 'RateLimitEvent' || t === 'rate_limit') return <RateLimitBanner />

  // ---- merged-bus system events (OD-01/02/04/09/17) ----
  const preview = (s: any, n = 90) => { const str = String(s ?? ''); return str.length > n ? str.slice(0, n - 1) + '…' : str }
  if (t === 'link_fire') return <SystemLine accent={C.teal} icon="🔗" label="Linked reply" detail={preview(event.text)} />
  if (t === 'inject' || t === 'inject_delivered') return <SystemLine accent={C.secondary} icon="⇢" label={event.kind === 'context' ? 'Context inject' : 'Inject'} detail={preview(event.text)} />
  if (t === 'scratch_delivered') return <SystemLine accent={C.railSection} icon="📋" label="Scratch delta" detail={`${event.count ?? ''} new post(s)`} />
  if (t === 'warning') return <SystemLine accent={C.warning} icon="⚠" label={`Warning · ${event.subtype ?? ''}`} detail={event.cap != null ? `${event.value} ≥ cap ${event.cap}` : undefined} />
  if (t === 'plan') return <SystemLine accent={C.inboxPermission} icon="◷" label="Plan proposed" detail={preview(event.data?.tool_input?.plan)} />
  if (t === 'decision') return <SystemLine accent={C.inboxPermission} icon="?" label="Decision needed" detail={preview(event.data?.tool_input?.question ?? event.data?.tool_input?.questions?.[0]?.question)} />
  if (t === 'error') return <SystemLine accent={C.danger} icon="✕" label="Error" detail={preview(event.error ?? event.message)} />
  return null
}

const RENDERABLE_TYPES = new Set([
  'assistant', 'user', 'rate_limit',
  'link_fire', 'inject', 'inject_delivered', 'scratch_delivered', 'warning', 'plan', 'decision', 'error',
])

// Will EventRenderer draw anything for this event? (status/permission_* events
// are stored but render nothing.)
export function isRenderableEvent(e: SDKEvent): boolean {
  if (e.sdk_type === 'AssistantMessage' || e.sdk_type === 'UserMessage' || e.sdk_type === 'RateLimitEvent') return true
  if (e.subtype === 'init') return true
  return RENDERABLE_TYPES.has(e.type)
}

// Does the event list contain anything that actually renders? (status/permission
// events are stored but render nothing, so events.length overcounts.)
export function hasRenderable(events: SDKEvent[]): boolean {
  return events.some(isRenderableEvent)
}
