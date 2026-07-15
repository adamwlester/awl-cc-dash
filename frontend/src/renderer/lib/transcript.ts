// ============================================================================
// Transcript derivation — merged-bus events → the Transcript/Log card models.
// One assistant/user event = one transcript card; content blocks map onto the
// design system's rail kinds (text · think · read/write/edit · bash · search ·
// workflow). Log rows come from the non-turn system events.
// ============================================================================

import type { SDKEvent, Session } from '../api'
import { clockTime } from './identity'

export interface TxBlock { k: string; t: string }
export interface TxCard {
  key: string
  agent: string             // ident key: session_id | 'user'
  dir: 'in' | 'out'         // anchored to the operator: out = you sent it
  recipients: string[]      // 'user' | session_id | 'scratch'
  body: string
  blocks: TxBlock[]         // typed rail rows AFTER the primary text row
  text: string              // the primary reply text (the 'text' rail row)
  status: 'active' | 'complete' | 'error'
  time: string
  turn: number | null
  seq: number
}

export interface LogRow {
  key: string
  agent: string             // ident key: session_id | 'user' | 'system'
  text: string
  warn?: boolean
  time: string
  seq: number
}

function toBlocks(content: any): any[] {
  if (Array.isArray(content)) return content
  if (typeof content === 'string') return content.trim() ? [{ type: 'text', text: content }] : []
  return []
}

const TOOL_KIND: [RegExp, string][] = [
  [/^(bash|powershell|shell)/i, 'bash'],
  [/^read/i, 'read'], [/^write/i, 'write'], [/^(edit|notebookedit|multiedit)/i, 'edit'],
  [/^(grep|glob)/i, 'search'], [/^web/i, 'search'],
]
function toolKind(name: string): string {
  for (const [re, k] of TOOL_KIND) if (re.test(name || '')) return k
  return 'workflow'
}
function toolSummary(block: any): string {
  const input = block.input || {}
  const bit = input.command || input.file_path || input.pattern || input.query || input.prompt || input.description
  return `${block.name}(${typeof bit === 'string' ? bit.slice(0, 160) : JSON.stringify(input).slice(0, 120)})`
}

const preview = (s: string, n = 110) => { const t = s.replace(/\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n - 1) + '…' : t }

/** CLI-internal echoes the bridge replays as user turns (<local-command-*>,
    <command-name>…) — transport noise, never shown as messages. */
export const isCliNoise = (t: string) => /^\s*<(local-command|command-name|command-message|system-reminder)/.test(t)

export function deriveTranscript(events: SDKEvent[], sessions: Session[]): TxCard[] {
  const cards: TxCard[] = []
  const turnBy: Record<string, number> = {}
  const running = new Set(sessions.filter(s => s.status === 'running').map(s => s.session_id))
  for (const e of events) {
    const sdk = e.sdk_type || ''
    const t = e.type
    if (sdk === 'AssistantMessage' || t === 'assistant') {
      const agent = e.agent_id || '?'
      const content = toBlocks(e.content ?? e.data?.message?.content)
      let text = ''
      const blocks: TxBlock[] = []
      for (const b of content) {
        if (b.type === 'text' && b.text?.trim()) { if (!text) text = b.text; else blocks.push({ k: 'text', t: b.text }) }
        else if (b.type === 'thinking' && b.thinking) blocks.push({ k: 'think', t: b.thinking })
        else if (b.type === 'tool_use') blocks.push({ k: toolKind(b.name), t: toolSummary(b) })
      }
      if (!text && !blocks.length) continue
      turnBy[agent] = (turnBy[agent] || 0) + 1
      cards.push({
        key: e.id || `a:${agent}:${e.seq}`,
        agent, dir: 'in',
        recipients: (e.recipients && e.recipients.length) ? e.recipients : ['user'],
        body: preview(text || blocks[0]?.t || ''),
        text: text || '',
        blocks,
        status: 'complete',
        time: clockTime(e.ts || e.timestamp),
        turn: turnBy[agent],
        seq: e.seq ?? 0,
      })
    } else if (sdk === 'UserMessage' || t === 'user') {
      const content = toBlocks(e.content ?? e.data?.message?.content)
      const texts = content.filter((b: any) => b.type === 'text' && b.text?.trim() && !isCliNoise(b.text)).map((b: any) => b.text)
      if (!texts.length) continue   // tool_result-only / CLI-echo user events are transport noise
      // the bridge stamps replayed user turns with source = the session id — a
      // user event whose source is the session itself is YOUR prompt to it
      const from = (e.source && e.source !== 'user' && e.source !== e.agent_id) ? e.source : 'user'
      cards.push({
        key: e.id || `u:${e.agent_id}:${e.seq}`,
        agent: from, dir: from === 'user' ? 'out' : 'in',
        recipients: (e.recipients && e.recipients.length && !(e.recipients.length === 1 && e.recipients[0] === 'user' && from === 'user'))
          ? e.recipients : (e.agent_id ? [e.agent_id] : ['user']),
        body: preview(texts[0]),
        text: texts.join('\n\n'),
        blocks: [],
        status: 'complete',
        time: clockTime(e.ts || e.timestamp),
        turn: null,
        seq: e.seq ?? 0,
      })
    }
  }
  // the newest assistant card of a still-running agent reads Active
  for (let i = cards.length - 1; i >= 0; i--) {
    const c = cards[i]
    if (c.dir === 'in' && running.has(c.agent)) { c.status = 'active'; running.delete(c.agent) }
  }
  return cards
}

export function deriveLog(events: SDKEvent[]): LogRow[] {
  const rows: LogRow[] = []
  const pv = (s: any, n = 120) => preview(String(s ?? ''), n)
  for (const e of events) {
    const t = e.type
    const time = clockTime(e.ts || e.timestamp)
    const agent = e.agent_id || 'system'
    const push = (text: string, warn = false, sys = false) =>
      rows.push({ key: e.id || `${t}:${e.seq}`, agent: sys ? 'system' : agent, text, warn, time, seq: e.seq ?? 0 })
    if (t === 'status_change') push(`status → ${e.status || e.data?.status || '?'}`)
    else if (t === 'link_fire') push(`link fired · ${pv(e.text)}`)
    else if (t === 'inject' || t === 'inject_delivered') push(`${e.kind === 'context' ? 'context inject' : 'inject'} · ${pv(e.text)}`)
    else if (t === 'scratch_delivered') push(`scratch delta · ${e.count ?? ''} new post(s)`)
    else if (t === 'warning') push(`warning · ${e.subtype ?? ''}${e.cap != null ? ` — ${e.value} ≥ cap ${e.cap}` : ''}`, true)
    else if (t === 'plan') push(`plan proposed · ${pv(e.data?.tool_input?.plan)}`)
    else if (t === 'decision') push(`decision needed · ${pv(e.data?.tool_input?.question ?? e.data?.tool_input?.questions?.[0]?.question)}`, true)
    else if (t === 'error') push(`error · ${pv(e.error ?? e.message)}`, true)
    else if (t === 'permission_request') push(`permission requested · ${pv(e.data?.question ?? '')}`, true)
    else if (t === 'permission_answered') push(`permission answered`)
    else if (e.subtype === 'init') push(`session started · ${e.data?.model || ''}`)
  }
  return rows
}
