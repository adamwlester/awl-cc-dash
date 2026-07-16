// ============================================================================
// Team Feed — Transcript · Scratch · Log · Inbox over the shared From/To
// filter accordion (right column, top). Mockup DOM + live data.
// ============================================================================

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api, type InboxItem } from '../api'
import { useDash } from '../store'
import { Ic } from '../lib/icons'
import {
  identOf, IdentBadge, RecipientBadge, AgTile, USER_IDENT, SYSTEM_IDENT, SCRATCH_IDENT,
  clockTime, type Ident,
} from '../lib/identity'
import { deriveTranscript, deriveLog, type TxCard } from '../lib/transcript'
import { MultiAgAccordion, useRoster } from './selectors'
import { ExportControl } from './ExportControl'
import { toast } from '../lib/toast'

const RAIL_ICON: Record<string, string> = {
  text: 'message-square', think: 'brain', read: 'file-text', write: 'file-text', edit: 'file-text',
  file: 'file-text', diff: 'file-text', bash: 'terminal', shell: 'terminal', search: 'search', workflow: 'workflow', meta: 'info',
}
const KIND_FILTER: Record<string, string> = {
  text: 'messages', think: 'thinking', read: 'files', write: 'files', edit: 'files', file: 'files', diff: 'files',
  bash: 'shell', shell: 'shell', search: 'search', workflow: 'workflow',
}

// Typed sections (§7.8; ND 16): ONE Review section covers plan/doc hand-offs
// (type "plan") AND the §11 #23 workflow approvals (type "review" — the
// PreToolUse(Workflow) HELD gate's card).
const SECTIONS: { key: string; types: string[]; lab: string }[] = [
  { key: 'error', types: ['error'], lab: 'Error' },
  { key: 'warning', types: ['warning'], lab: 'Warning' },
  { key: 'permission', types: ['permission'], lab: 'Permission' },
  { key: 'plan', types: ['plan', 'review'], lab: 'Review' },
  { key: 'decision', types: ['decision'], lab: 'Decision' },
  { key: 'response', types: ['response'], lab: 'Response' },
]

function identForKey(key: string, d: ReturnType<typeof useDash>): Ident {
  if (key === 'user') return USER_IDENT
  if (key === 'system') return SYSTEM_IDENT
  if (key === 'scratch') return SCRATCH_IDENT
  const s = d.sessions.find(x => x.session_id === key)
  if (s) return identOf(s)
  return { key, role: 'agent', name: key.replace(/^awl-/, '').slice(0, 14), short: key, color: 'var(--muted)', icon: '' }
}

export function TeamFeed() {
  const d = useDash()
  const roster = useRoster()

  // ---- shared From/To filter (default: everything on; new agents join on) ----
  const [offSet, setOffSet] = useState<Set<string>>(new Set())
  const allKeys = useMemo(() => {
    const keys = ['user', 'system', ...d.sessions.map(s => s.session_id)]
    for (const s of d.sessions) for (const su of d.subagentsBy[s.session_id] || []) keys.push(`${s.session_id}:${su.id}`)
    return keys
  }, [d.sessions, d.subagentsBy])
  const sel = useMemo(() => new Set(allKeys.filter(k => !offSet.has(k))), [allKeys, offSet])
  const setSel = (next: Set<string>) => setOffSet(new Set(allKeys.filter(k => !next.has(k))))
  const agentOn = (k: string) => sel.has(k)

  // ---- content filters (mockup defaults) --------------------------------------
  const [flt, setFlt] = useState<Record<string, boolean>>({
    sent: true, received: true, messages: true, thinking: true, files: false, shell: false, search: false, workflow: false, subagent: true,
  })
  const tog = (k: string) => setFlt(p => ({ ...p, [k]: !p[k] }))

  // ---- selection / expansion ---------------------------------------------------
  const [selCards, setSelCards] = useState<Set<string>>(new Set())
  const [openCards, setOpenCards] = useState<Set<string>>(new Set())
  const [blockSel, setBlockSel] = useState<{ card: string; rows: Set<number> } | null>(null)
  const [flashKey, setFlashKey] = useState<string | null>(null)
  const [summaryOpen, setSummaryOpen] = useState(false)
  const [summaryText, setSummaryText] = useState('')
  const [subScope, setSubScope] = useState<{ agent: string; sub: string } | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const toggleCard = (key: string) => setSelCards(p => { const n = new Set(p); n.has(key) ? n.delete(key) : n.add(key); return n })
  const toggleOpen = (key: string) => setOpenCards(p => { const n = new Set(p); n.has(key) ? n.delete(key) : n.add(key); return n })

  // ---- data --------------------------------------------------------------------
  const txAll = useMemo(() => deriveTranscript(d.events, d.sessions), [d.events, d.sessions])
  const logAll = useMemo(() => deriveLog(d.events), [d.events])
  const tx = txAll.filter(c => {
    if (!(c.dir === 'out' ? flt.sent : flt.received)) return false
    const scoped = subScope ? c.agent === subScope.agent : true
    if (!scoped) return false
    return agentOn(c.agent) || c.recipients.some(r => agentOn(r))
  })
  const log = logAll.filter(r => r.agent === 'system' ? agentOn('system') : agentOn(r.agent))
  // §11 #23 — resolved review cards are HELD in place for the read beat: the
  // store's own 2s inbox poll drops a resolved item from /inbox almost
  // immediately (GET /inbox excludes resolved), so without this hold the
  // approved/rejected banner's visibility would depend on poll phase.
  const [heldReviews, setHeldReviews] = useState<(InboxItem & { _agent: string })[]>([])
  const inboxByAgent = d.inbox.inbox
  const inboxItems: (InboxItem & { _agent: string })[] = Object.entries(inboxByAgent)
    .flatMap(([agent, items]) => items.filter(i => !i.resolved).map(i => ({ ...i, _agent: agent })))
    .filter(i => i._agent === 'system' ? agentOn('system') : agentOn(i._agent))
  for (const h of heldReviews) if (!inboxItems.some(i => i.id === h.id)) inboxItems.push(h)
  const openCount = inboxItems.length

  // ---- cross-panel jumps ---------------------------------------------------------
  useEffect(() => {
    const j = d.jump
    if (j.target === 'inbox' && j.agent) {
      const item = inboxItems.find(i => i._agent === j.agent && (!j.type || i.type === j.type)) || inboxItems.find(i => i._agent === j.agent)
      if (item) {
        setOpenCards(p => new Set(p).add(item.id))
        setSelCards(p => new Set(p).add(item.id))
        setFlashKey(item.id)
        setTimeout(() => document.querySelector(`[data-inbox-id="${CSS.escape(item.id)}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 60)
        setTimeout(() => setFlashKey(null), 1400)
      }
    }
    if (j.target === 'subagents' && j.agent && j.type) setSubScope({ agent: j.agent, sub: j.type })
    if (j.target === 'transcript' && j.agent) {
      const last = [...tx].reverse().find(c => c.agent === j.agent && c.dir === 'in')
      if (last) {
        setOpenCards(p => new Set(p).add(last.key))
        setFlashKey(last.key)
        setTimeout(() => document.querySelector(`[data-tx-key="${CSS.escape(last.key)}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 60)
        setTimeout(() => setFlashKey(null), 1400)
      }
    }
  }, [d.jump.seq])

  // ---- selection → export helpers -------------------------------------------------
  const selectionText = (): { text: string; source: string } | null => {
    if (d.feedTab === 'transcript') {
      if (blockSel) {
        const card = tx.find(c => c.key === blockSel.card)
        if (card) {
          const rows = [card.text, ...card.blocks.map(b => b.t)]
          const picked = [...blockSel.rows].sort().map(i => rows[i]).filter(Boolean)
          if (picked.length) return { text: picked.join('\n\n'), source: identForKey(card.agent, d).name }
        }
      }
      const cards = tx.filter(c => selCards.has(c.key))
      if (cards.length) return { text: cards.map(c => `${identForKey(c.agent, d).name}: ${c.text}\n${c.blocks.map(b => b.t).join('\n')}`).join('\n\n'), source: 'Transcript' }
      return null
    }
    if (d.feedTab === 'scratch') {
      const posts = d.scratch.filter(p => selCards.has(`sc:${p.seq}`))
      if (posts.length) return { text: posts.map(p => `${p.author}: ${p.text}`).join('\n\n'), source: 'Scratch' }
      return null
    }
    if (d.feedTab === 'log') {
      const rows = log.filter(r => selCards.has(r.key))
      if (rows.length) return { text: rows.map(r => `${r.time} ${identForKey(r.agent, d).name} · ${r.text}`).join('\n'), source: 'Log' }
      return null
    }
    const items = inboxItems.filter(i => selCards.has(i.id))
    if (items.length) return { text: items.map(i => `${i.type}: ${inboxTitle(i)}\n${inboxBody(i)}`).join('\n\n'), source: 'Inbox' }
    return null
  }

  const selInfo = selectionText()
  const expCopy = () => { if (!selInfo) return; navigator.clipboard?.writeText(selInfo.text); toast('Copied selection') }
  const expFile = async () => {
    if (!selInfo || !d.projectCwd) { toast(d.projectCwd ? 'Nothing selected' : 'No project open'); return }
    const name = `feed-export-${Date.now()}.md`
    const r = await api.createDocument({ cwd: d.projectCwd, filename: name, content: selInfo.text, subdir: 'docs' })
    toast(r ? `Exported → Library → Documents (${name})` : 'Export failed')
  }
  const expEmbed = () => {
    if (!selInfo) return
    d.replyTo(d.selectedId || '', { source: selInfo.source, text: selInfo.text })
  }
  const doSummarize = async () => {
    const src = selInfo?.text || tx.slice(-12).map(c => `${identForKey(c.agent, d).name}: ${c.text}`).join('\n')
    if (!src.trim()) { toast('Nothing to summarize'); return }
    setSummaryOpen(true)
    setSummaryText('Summarizing…')
    const r = await api.summarize(src)
    setSummaryText(r?.result || 'Summarize failed (utility endpoint unavailable)')
  }
  const doStop = async () => {
    const targets = new Set<string>()
    tx.filter(c => selCards.has(c.key)).forEach(c => { if (c.agent !== 'user') targets.add(c.agent) })
    if (!targets.size && d.selectedId) targets.add(d.selectedId)
    for (const id of targets) await api.interrupt(id)
    toast(targets.size ? `Stop sent to ${targets.size} agent(s)` : 'No agent to stop')
  }
  const selectAll = () => {
    const keys = d.feedTab === 'transcript' ? tx.map(c => c.key)
      : d.feedTab === 'scratch' ? d.scratch.map(p => `sc:${p.seq}`)
      : d.feedTab === 'log' ? log.map(r => r.key)
      : inboxItems.map(i => i.id)
    setSelCards(p => p.size === keys.length ? new Set() : new Set(keys))
  }

  // ---- inbox actions ----------------------------------------------------------------
  // A review (workflow) verdict keeps its resolved state IN PLACE for a beat:
  // the item is HELD in the local list for 1.2s (see heldReviews above) so the
  // success/danger banner reads before the card completes and leaves (the ND 16
  // round-trip) — a delayed refresh alone can't guarantee it, because the
  // store's independent 2s inbox poll drops the resolved item on its own phase.
  const resolve = async (it: InboxItem & { _agent: string }, answer?: any) => {
    if (it.type === 'review') {
      setHeldReviews(prev => prev.some(h => h.id === it.id) ? prev : [...prev, it])
      setTimeout(() => setHeldReviews(prev => prev.filter(h => h.id !== it.id)), 1200)
    }
    if (it.id.startsWith('perm:')) {
      await api.answerPermission(it._agent, answer === 'approved')
    } else {
      await api.resolveInbox(it._agent, it.id, answer)
    }
    if (it.type === 'review') setTimeout(() => d.refreshInbox(), 1200)
    else d.refreshInbox()
  }
  const replyToItem = (it: InboxItem & { _agent: string }) => {
    d.replyTo(it._agent, { source: `Inbox · ${SECTIONS.find(s => s.types.includes(it.type))?.lab || it.type}`, text: `${inboxTitle(it)}\n${inboxBody(it)}` })
  }

  return (
    <section className="rz-panel" id="pFeed" style={{ flex: '1 1 52%', minHeight: 'var(--pane-feed-min-h)', maxHeight: 'var(--pane-feed-max-h)' }}>
      <div className="pcard-head">
        <h3>Team Feed</h3>
        <div data-comp="tab-bar" className="tabset">
          {(['transcript', 'scratch', 'log', 'inbox'] as const).map(t => (
            <button key={t} className={`tab-btn${d.feedTab === t ? ' active' : ''}`} onClick={() => { d.setFeedTab(t); setSelCards(new Set()); setBlockSel(null) }}>
              {t[0].toUpperCase() + t.slice(1)}
              {t === 'inbox' && openCount > 0 && <span data-comp="count-square" className="req-badge ml-1">{openCount}</span>}
            </button>
          ))}
        </div>
      </div>
      <div className="pcard-body flex flex-col overflow-hidden" style={{ background: 'var(--background)' }}>
        <div className="subbar">
          <MultiAgAccordion id="feed-filter" header="From/To" rows={roster.agents} lead={[USER_IDENT, SYSTEM_IDENT]} sel={sel} onSel={setSel} tree />
        </div>

        <div className="flex-1 min-w-0 flex flex-col overflow-hidden feed-body-wrap" style={{ position: 'relative' }}>
          {/* TRANSCRIPT */}
          {d.feedTab === 'transcript' && (
            <div className="flex-1 overflow-y-auto px-3 pt-1 pb-3" style={{ background: 'var(--background)' }} ref={listRef}>
              <div className="minibar sticky top-0 z-10" style={{ background: 'var(--background)', borderBottom: 'var(--border-width) solid var(--border)' }}>
                <button data-comp="mini-toggle" className={`minitog${flt.sent ? ' on' : ''}`} onClick={() => tog('sent')} title="Messages you sent to the team"><Ic name="arrow-up-right" />Sent</button>
                <button data-comp="mini-toggle" className={`minitog${flt.received ? ' on' : ''}`} onClick={() => tog('received')} title="Messages received from agents"><Ic name="arrow-down-left" />Received</button>
                <span className="mini-div" />
                <button data-comp="mini-toggle" className={`minitog${flt.messages ? ' on' : ''}`} onClick={() => tog('messages')} title="The reply text"><Ic name="message-square" />Messages</button>
                <button data-comp="mini-toggle" className={`minitog${flt.thinking ? ' on' : ''}`} onClick={() => tog('thinking')} title="Extended-thinking blocks"><Ic name="brain" />Thinking</button>
                <button data-comp="mini-toggle" className={`minitog${flt.files ? ' on' : ''}`} onClick={() => tog('files')} title="File activity — Read / Write / Edit"><Ic name="file-text" />Files</button>
                <button data-comp="mini-toggle" className={`minitog${flt.shell ? ' on' : ''}`} onClick={() => tog('shell')} title="Shell activity — Bash / PowerShell"><Ic name="terminal" />Shell</button>
                <button data-comp="mini-toggle" className={`minitog${flt.search ? ' on' : ''}`} onClick={() => tog('search')} title="Search activity — Grep"><Ic name="search" />Search</button>
                <button data-comp="mini-toggle" className={`minitog${flt.workflow ? ' on' : ''}`} onClick={() => tog('workflow')} title="Workflow runs"><Ic name="workflow" />Workflow</button>
                <span className="mini-div" />
                <button data-comp="mini-toggle" className={`minitog${flt.subagent ? ' on' : ''}`} onClick={() => tog('subagent')} title="Show / hide nested subagent entries"><Ic name="git-branch" />Subagent</button>
              </div>
              {subScope && (
                <div className="text-[9px] text-muted font-mono mt-2 flex items-center gap-2">
                  scoped to subagent <span className="sbadge sb-active sub-fbadge">{subScope.sub}</span> of {identForKey(subScope.agent, d).name}
                  <button className="mini-link" onClick={() => setSubScope(null)}>clear</button>
                </div>
              )}
              <div id="tx-list" className="flex flex-col gap-2 mt-2">
                {tx.map(c => (
                  <TxCardView key={c.key} c={c} d={d}
                    sel={selCards.has(c.key)} open={openCards.has(c.key)} flash={flashKey === c.key}
                    flt={flt} blockSel={blockSel?.card === c.key ? blockSel.rows : null}
                    onSel={() => { toggleCard(c.key); setBlockSel(null) }}
                    onOpen={() => toggleOpen(c.key)}
                    onBlock={(i) => setBlockSel(p => {
                      const rows = p && p.card === c.key ? new Set(p.rows) : new Set<number>()
                      rows.has(i) ? rows.delete(i) : rows.add(i)
                      setSelCards(new Set())
                      return rows.size ? { card: c.key, rows } : null
                    })} />
                ))}
                {!tx.length && <div className="awl-empty">No traffic yet — send a prompt from Compose to see the stream.</div>}
              </div>
            </div>
          )}

          {/* SCRATCH */}
          {d.feedTab === 'scratch' && (
            <div className="flex-1 overflow-y-auto px-3 py-3" style={{ background: 'var(--background)' }}>
              <div className="text-[9px] text-muted font-mono mb-2">{d.projectCwd ? `${d.projectCwd}/.awl/scratchpad.md — live posts` : 'no project open'}</div>
              <div className="flex flex-col gap-2">
                {d.scratch.filter(p => agentOn(p.author) || p.author === 'user' || !d.sessions.some(s => s.session_id === p.author)).map(p => {
                  const key = `sc:${p.seq}`
                  const a = identForKey(p.author, d)
                  return (
                    <div data-comp="scratch-post" className={`fcard${selCards.has(key) ? ' sel' : ''}${openCards.has(key) ? ' open' : ''}`} key={key}>
                      <div className="fcard-head">
                        <button className="fcard-exp msel-head" onClick={() => toggleCard(key)} title="Select this card (Attach)">
                          <IdentBadge a={a} />
                          <span className="fcard-prev">{p.text}</span><span className="fcard-time">{clockTime(p.ts)}</span>
                        </button>
                        <button className="fcard-chevbtn" onClick={() => toggleOpen(key)} title="Expand / collapse"><Ic name="chevron-right" className="fcard-chev" /></button>
                      </div>
                      <div className="fcard-body"><div className="fcard-full">{p.text}</div></div>
                    </div>
                  )
                })}
                {!d.scratch.length && <div className="awl-empty">The shared scratchpad is empty — post to it from Compose → To → Scratch.</div>}
              </div>
            </div>
          )}

          {/* LOG */}
          {d.feedTab === 'log' && (
            <div className="flex-1 overflow-y-auto px-3 py-3" style={{ background: 'var(--background)' }}>
              <div className="flex flex-col gap-1.5">
                {log.map(r => {
                  const a = identForKey(r.agent, d)
                  return (
                    <div data-comp="log-line" className={`fcard${selCards.has(r.key) ? ' sel' : ''}${openCards.has(r.key) ? ' open' : ''}`} key={r.key}>
                      <div className="fcard-head">
                        <button className="fcard-exp msel-head" onClick={() => toggleCard(r.key)} title="Select this card (Attach)">
                          <IdentBadge a={a} />
                          <span className="fcard-prev fcard-log" style={r.warn ? { color: 'var(--warning)' } : undefined}>{r.text}</span>
                          <span className="fcard-time">{r.time}</span>
                        </button>
                        <button className="fcard-chevbtn" onClick={() => toggleOpen(r.key)} title="Expand / collapse"><Ic name="chevron-right" className="fcard-chev" /></button>
                      </div>
                      <div className="fcard-body"><div className="fcard-full fcard-log">{a.name} · {r.text}</div></div>
                    </div>
                  )
                })}
                {!log.length && <div className="awl-empty">No system events yet.</div>}
              </div>
            </div>
          )}

          {/* INBOX */}
          {d.feedTab === 'inbox' && (
            <div className="flex-1 overflow-y-auto px-3 py-3" style={{ background: 'var(--background)' }}>
              <div className="text-[9px] text-muted font-mono mb-2">
                {openCount ? `${openCount} open item${openCount === 1 ? '' : 's'} — blocking requests first, the non-blocking Response section last` : 'Inbox clear — nothing needs you'}
              </div>
              <div className="flex flex-col gap-2.5">
                {SECTIONS.map(sec => {
                  const items = inboxItems.filter(i => sec.types.includes(i.type))
                  if (!items.length) return null
                  return (
                    <InboxSection key={sec.key} sec={sec} items={items} d={d}
                      selCards={selCards} openCards={openCards} flashKey={flashKey}
                      onSel={toggleCard} onOpen={toggleOpen}
                      resolve={resolve} replyToItem={replyToItem} />
                  )
                })}
              </div>
            </div>
          )}

          {/* Summarize slide-over */}
          <div data-comp="summarize-slideover" className={`feed-overlay${summaryOpen ? ' open' : ''}`}>
            <div className="fo-head">
              <div className="fo-title"><Ic name="sparkles" />Conversation summary</div>
              <span className="fo-sub">{selCards.size ? `${selCards.size} selected` : 'recent traffic'}</span>
              <span className="flex-1" />
              <button data-comp="ghost-icon-button" className="ghost-ic" title="Copy summary" onClick={() => { navigator.clipboard?.writeText(summaryText); toast('Summary copied') }}><Ic name="copy" /></button>
              <button data-comp="button" className="btn btn-sm" onClick={() => setSummaryOpen(false)}><Ic name="x" className="w-3.5 h-3.5" />Close</button>
            </div>
            <div className="fo-body" style={{ whiteSpace: 'pre-wrap' }}>{summaryText}</div>
          </div>
        </div>
      </div>

      {/* shared feed action strip */}
      <div className="pcard-foot px-2 py-2.5" id="feed-actions">
        <div className="flex items-center gap-2 flex-wrap">
          <button data-comp="icon-button" className="icon-btn" title="Select / deselect all cards in this tab" onClick={selectAll}><Ic name="list-checks" /></button>
          <ExportControl a={{
            enabled: !!selInfo,
            fileDisabled: !d.projectCwd,
            onCopy: expCopy,
            onFile: expFile,
            onEmbed: expEmbed,
            // Materialized content (§7.14): the selection lands in the project
            // store as a real asset and is chipped on Compose by id.
            onAttach: async () => {
              if (!selInfo || !d.projectCwd) { toast(d.projectCwd ? 'Nothing selected' : 'No project open'); return }
              const b64 = btoa(unescape(encodeURIComponent(selInfo.text)))
              const r = await api.ingestAsset({ cwd: d.projectCwd, filename: `feed-${Date.now() % 100000}.md`, content_base64: b64, created_by: 'user' })
              if (r.ok && r.data?.asset?.id) { d.attachToCompose([{ id: r.data.asset.id, filename: r.data.asset.filename, kind: 'doc' }]); toast(`Attached ${r.data.asset.filename}`) }
              else toast(`Attach failed: ${r.detail || 'sidecar error'}`)
            },
          }} />
          {d.feedTab !== 'inbox' && (
            <button data-comp="button" className="btn" title="Summarize the conversation" onClick={doSummarize}><Ic name="sparkles" className="w-3.5 h-3.5" />Summarize</button>
          )}
          <div className="flex-1" />
          {d.feedTab === 'transcript' && (
            <button data-comp="icon-button" className="icon-btn icon-btn--danger-solid" title="Stop this run" onClick={doStop}><Ic name="square" /></button>
          )}
        </div>
      </div>
    </section>
  )
}

// ---- transcript card ------------------------------------------------------------
function TxCardView({ c, d, sel, open, flash, flt, blockSel, onSel, onOpen, onBlock }: {
  c: TxCard; d: ReturnType<typeof useDash>; sel: boolean; open: boolean; flash: boolean
  flt: Record<string, boolean>; blockSel: Set<number> | null
  onSel: () => void; onOpen: () => void; onBlock: (rowIdx: number) => void
}) {
  const a = identForKey(c.agent, d)
  const CAP = 2
  const recips = c.recipients.slice(0, CAP)
  const more = c.recipients.length - recips.length
  // rows: 0 = primary text; 1.. = blocks
  const rows: { k: string; t: string; idx: number }[] = [{ k: 'text', t: c.text, idx: 0 }, ...c.blocks.map((b, i) => ({ ...b, idx: i + 1 }))]
  const visRows = rows.filter(r => flt[KIND_FILTER[r.k] || 'messages'] !== false)
  return (
    <div data-comp="message-card" data-tx-key={c.key} className={`fcard txcard${sel ? ' sel' : ''}${open ? ' open' : ''}${flash ? ' reply-flash' : ''}`}>
      <div className="fcard-head">
        <button className="fcard-exp msel-head" onClick={onSel} title="Select this whole message (Attach)">
          <IdentBadge a={a} />
          <span className="rcpt-to" title="addressed to"><Ic name="arrow-right" /></span>
          {recips.map(r => <RecipientBadge key={r} a={identForKey(r, d)} />)}
          {more > 0 && <span className="rcpt-more">+{more}</span>}
          <span className="fcard-prev">{c.body}</span>
          <span data-comp="lifecycle-badge" className={`dbadge db-${c.status}`}>{{ active: 'Active', complete: 'Complete', error: 'Error' }[c.status]}</span>
          <span className="fcard-time">{c.time}</span>
        </button>
        <button className="fcard-chevbtn" onClick={e => { e.stopPropagation(); onOpen() }} title="Expand / collapse"><Ic name="chevron-right" className="fcard-chev" /></button>
      </div>
      <div className="fcard-body">
        <div className="mrail-wrap">
          <div data-comp="message-rail-row" className="mrow mrow--title">
            <button className="mrail mrail--title" onClick={onSel} title="Select the whole message" />
            <div className="mrow-c"><div className="fcard-full"><span className="msg-turn">Turn {c.turn ?? ''}</span></div></div>
          </div>
          {visRows.map(r => (
            <div data-comp="message-rail-row" className={`mrow${blockSel?.has(r.idx) || sel ? ' bsel' : ''}`} key={r.idx} data-blk={r.k}>
              <button className="mrail" onClick={e => { e.stopPropagation(); onBlock(r.idx) }} title="Select this block (multi)">
                <span className="rail-tag" title={r.k}><Ic name={RAIL_ICON[r.k] || 'file-text'} /></span>
              </button>
              <div className="mrow-c">
                {r.idx === 0
                  ? <div className="fcard-full">{r.t || <span className="text-muted-2 italic">no reply text</span>}</div>
                  : <div data-comp="msg-block" className={`msg-blk blk-${r.k}`}>{r.t}</div>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ---- inbox section + cards ---------------------------------------------------------
export function inboxTitle(it: InboxItem): string {
  const dt = it.data || {}
  if (it.type === 'review') return `Run workflow: ${dt.preview?.name || dt.tool_input?.name || dt.tool || 'Workflow'}`
  if (dt.title) return dt.title
  if (dt.question) return dt.question
  if (it.type === 'response') return 'Run ended — final reply not yet reviewed'
  if (it.type === 'permission') return dt.tool_name ? `Run ${dt.tool_name}` : 'Permission requested'
  if (it.type === 'plan') return dt.plan_title || 'Plan ready for review'
  if (it.type === 'warning') return dt.subtype ? `${dt.subtype} — attention needed` : 'Warning'
  if (dt.message) return String(dt.message).slice(0, 90)
  return dt.command || dt.tool_name || it.type
}
export function inboxBody(it: InboxItem): string {
  const dt = it.data || {}
  if (it.type === 'response') {
    const n = dt.runs || 1
    return `${n === 1 ? 'A run' : `${n} runs`} ended with output you haven't reviewed. View jumps to the run's final reply in the Transcript and completes this item; Reply quotes it in the Editor (also completes). It clears only when completed — never on a glance.`
  }
  return dt.message || dt.body || dt.plan || dt.detail || dt.raw || dt.command || ''
}

function InboxSection({ sec, items, d, selCards, openCards, flashKey, onSel, onOpen, resolve, replyToItem }: {
  sec: { key: string; types: string[]; lab: string }
  items: (InboxItem & { _agent: string })[]
  d: ReturnType<typeof useDash>
  selCards: Set<string>; openCards: Set<string>; flashKey: string | null
  onSel: (k: string) => void; onOpen: (k: string) => void
  resolve: (it: InboxItem & { _agent: string }, answer?: any) => Promise<void>
  replyToItem: (it: InboxItem & { _agent: string }) => void
}) {
  const [open, setOpen] = useState(true)
  return (
    <div data-comp="inbox-section" className={`inbox-sec inbox-sec--${sec.key}${open ? ' open' : ''}`}>
      <button className="inbox-sec-head" onClick={() => setOpen(o => !o)} title="Collapse / expand this section">
        <Ic name="chevron-down" className="inbox-sec-chev" /><span className="inbox-sec-lab">{sec.lab}</span>
        <span data-comp="count-square" className="inbox-sec-n">{items.length}</span>
      </button>
      <div className="inbox-sec-cards">
        {items.map(it => <InboxCard key={it.id} it={it} d={d}
          sel={selCards.has(it.id)} isOpen={openCards.has(it.id)} flash={flashKey === it.id}
          onSel={() => onSel(it.id)} onOpen={() => onOpen(it.id)} resolve={resolve} replyToItem={replyToItem} />)}
      </div>
    </div>
  )
}

function InboxCard({ it, d, sel, isOpen, flash, onSel, onOpen, resolve, replyToItem }: {
  it: InboxItem & { _agent: string }
  d: ReturnType<typeof useDash>
  sel: boolean; isOpen: boolean; flash: boolean
  onSel: () => void; onOpen: () => void
  resolve: (it: InboxItem & { _agent: string }, answer?: any) => Promise<void>
  replyToItem: (it: InboxItem & { _agent: string }) => void
}) {
  const a = identForKey(it._agent, d)
  const dt = it.data || {}
  const [decision, setDecision] = useState<string | null>(null)
  // §11 #23 — the workflow round-trip's resolved-in-place beat: the verdict
  // class shows the success/danger edge + banner (styles.css) until the next
  // inbox poll drops the completed card.
  const [wfState, setWfState] = useState<null | 'approved' | 'rejected'>(null)
  const isSystem = it._agent === 'system'
  const subtype = dt.subtype ? String(dt.subtype) : null
  const reply = (
    <button data-comp="button" className="btn-secondary btn-sm ml-auto" disabled={isSystem}
      title={isSystem ? "Reply is unavailable — System isn't addressable" : 'Reply via the Editor (quotes the request as a reference block)'}
      onClick={() => replyToItem(it)}><Ic name="send-horizontal" className="w-3 h-3" />Reply</button>
  )
  let detail: React.ReactNode = <div className="rc-body">{inboxBody(it) || inboxTitle(it)}</div>
  let acts: React.ReactNode = null
  if (it.type === 'permission') {
    detail = <div className="rc-body" style={{ fontFamily: 'var(--font-mono)' }}>{dt.question || dt.raw || dt.command || inboxTitle(it)}</div>
    acts = (<>
      <button data-comp="button" className="btn-main btn-sm" onClick={() => resolve(it, 'approved')}>Approve</button>
      <button data-comp="button" className="btn-danger btn-sm" onClick={() => resolve(it, 'denied')}>Deny</button>
      {reply}
    </>)
  } else if (it.type === 'plan') {
    const isDoc = String(dt.plan_id || dt.id || '').startsWith('doc-')
    acts = (<>
      <button data-comp="button" className="btn btn-sm" title={isDoc ? 'Review the full doc in Library → Documents' : 'Review the full plan in Library → Plans'}
        onClick={() => { d.setLibTab(isDoc ? 'documents' : 'plan'); }}><Ic name="file-text" className="w-3 h-3" />Review</button>
      {reply}
    </>)
  } else if (it.type === 'review') {
    // §11 #23 — a /workflows approval held at the PreToolUse gate: the parsed
    // script preview (name / description / phase chips / the full scrolling
    // script) renders in the card; Approve = the hook ALLOWS the call (the
    // workflow launches) · Reject = DENIES it (aborts before launch). A lapsed
    // hold (data.timed_out) reads honestly: the gate already fell back to the
    // agent's on-pane dialog, so resolving now only clears the card.
    const pv = dt.preview || {}
    const scriptText: string = dt.tool_input?.script || ''
    const timedOut = !!dt.timed_out
    const wfVerdict = async (ok: boolean) => {
      setWfState(ok ? 'approved' : 'rejected')
      await resolve(it, { verdict: ok ? 'approve' : 'reject' })
    }
    detail = (
      <div className="wf-prev">
        <div className="rc-body"><b>{pv.name || dt.tool || 'Workflow'}</b></div>
        {pv.description && <div className="wf-desc">{pv.description}</div>}
        {(pv.phase_titles || []).length > 0 && (
          <div className="wf-phases">{(pv.phase_titles as string[]).map((p, i) => <span data-comp="workflow-phase-chip" className="wf-phase" key={i}>{p}</span>)}</div>
        )}
        {pv.script_path && <div className="wf-desc" title={pv.script_path}>script: <span style={{ fontFamily: 'var(--font-mono)' }}>{pv.script_path}</span></div>}
        {scriptText
          ? <pre className="wf-script">{scriptText}</pre>
          : <div className="wf-desc">{pv.script_path ? 'script preview read from the file (best-effort) — see the path above' : 'no inline script carried on the tool call'}</div>}
        {timedOut && (
          <div className="wf-desc" style={{ color: 'var(--warning-text)' }}>
            Hold lapsed — the approval fell back to the agent&#8217;s on-pane dialog; answering here only clears this card.
          </div>
        )}
        <div className="wf-resolved wf-resolved--ok"><Ic name="circle-check" />Approved — workflow launched</div>
        <div className="wf-resolved wf-resolved--no"><Ic name="circle-x" />Rejected — workflow aborted before launch</div>
      </div>
    )
    acts = (<>
      <button data-comp="button" className="btn-main btn-sm" onClick={() => wfVerdict(true)}
        title={timedOut ? 'The hold already lapsed — this only clears the card' : 'Approve — allow the Workflow tool call; the workflow launches'}>Approve</button>
      <button data-comp="button" className="btn-danger btn-sm" onClick={() => wfVerdict(false)}
        title={timedOut ? 'The hold already lapsed — this only clears the card' : 'Reject — deny the tool call; the workflow never launches'}>Reject</button>
      {reply}
    </>)
  } else if (it.type === 'decision') {
    const q = dt.tool_input?.questions?.[0] || dt
    const options: { nm: string; desc: string }[] = (q.options || dt.options || []).map((o: any) =>
      typeof o === 'string' ? { nm: o, desc: '' } : { nm: o.label || o.nm || String(o), desc: o.description || o.desc || '' })
    detail = (
      <div className="space-y-1.5">
        {options.map(op => (
          <button data-comp="option-card" key={op.nm} className={`opt${decision === op.nm ? ' on' : ''}`} onClick={() => setDecision(op.nm)}>
            <span className="opt-nm">{op.nm}</span><span className="opt-desc">{op.desc}</span>
          </button>
        ))}
        {!options.length && <div className="rc-body">{q.question || inboxBody(it)}</div>}
      </div>
    )
    acts = (<>
      <button data-comp="button" className="btn-main btn-sm dec-approve" disabled={!decision} title={decision ? undefined : 'Select an option first'}
        onClick={() => resolve(it, decision)}>Approve</button>
      {reply}
    </>)
  } else if (it.type === 'warning') {
    acts = (<>
      <button data-comp="button" className="btn-main btn-sm" title="Dismiss this warning (clears it from the Inbox)" onClick={() => resolve(it, 'dismissed')}>Dismiss</button>
      {reply}
    </>)
  } else if (it.type === 'response') {
    acts = (<>
      <button data-comp="button" className="btn-main btn-sm" title="View — jump to the run's final reply (completes this item)"
        onClick={async () => { await resolve(it, 'viewed'); d.setFeedTab('transcript'); d.statusJump('active', it._agent) }}><Ic name="eye" className="w-3 h-3" />View</button>
      {reply}
    </>)
  } else { // error
    detail = <div className="rc-body inbox-err">{inboxBody(it) || inboxTitle(it)}</div>
    acts = (<>
      <button data-comp="button" className="btn-main btn-sm" title="Retry — load the last command into the Editor"
        onClick={() => d.replyTo(it._agent, undefined, dt.command || dt.cmd || inboxBody(it))}><Ic name="rotate-ccw" className="w-3 h-3" />Retry</button>
      <button data-comp="button" className="btn-danger btn-sm" onClick={() => resolve(it, 'dismissed')}>Dismiss</button>
      {reply}
    </>)
  }
  return (
    <div data-comp={it.type === 'review' ? 'workflow-inbox-card' : `${it.type}-inbox-card`} data-inbox-id={it.id}
      className={`fcard inbox-card inbox-card--${it.type === 'review' ? 'plan' : it.type}${sel ? ' sel' : ''}${isOpen ? ' open' : ''}${flash ? ' reply-flash' : ''}${wfState ? ` ${wfState}` : ''}`} data-agent={it._agent}>
      <div className="fcard-head">
        <button className="fcard-exp msel-head" onClick={onSel} title="Select this request (Attach)">
          <IdentBadge a={a} />
          {subtype && <span data-comp="inbox-subtype-badge" className={`inbox-subtype${it.type === 'warning' ? ' inbox-subtype--warning' : ''}`}>{subtype}</span>}
          {it.type === 'response' && (dt.runs || 1) > 1 && <span data-comp="inbox-runs-chip" className="inbox-runs" title={`${dt.runs} unseen runs coalesced — a new unseen run updates this card, never stacks`}>×{dt.runs} runs</span>}
          <span className="inbox-title">{inboxTitle(it)}</span>
          <span className="fcard-time">{clockTime(it.created_at)}</span>
        </button>
        <button className="fcard-chevbtn" onClick={onOpen} title="Expand / collapse"><Ic name="chevron-right" className="fcard-chev" /></button>
      </div>
      <div className="fcard-body">
        <div className="inbox-detail">{detail}</div>
        <div className="inbox-acts">{acts}</div>
      </div>
    </div>
  )
}
