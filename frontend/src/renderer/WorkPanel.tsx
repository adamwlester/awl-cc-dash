// ============================================================================
// Work panel (middle-bottom) — Library · Links · Scratch
// ----------------------------------------------------------------------------
// Library: read + render the focused project's markdown Plans/Documents
// (+ any plan-review verdicts). Links: list / create / delete
// agent-to-agent links and kick off a reply-to conversation. Scratch:
// read the shared board for the focused project and post to it. All wired to the
// live sidecar; minimal styling on the shared primitives.
// ============================================================================

import React, { useEffect, useState } from 'react'
import { C, FONT, MONO, timeAgo } from './tokens'
import { Tabs, Btn, Segmented } from './ui'
import { AgentTile } from './AgentTile'
import {
  api, type Session, type LinksResponse, type Link, type LibraryDoc, type ScratchPost, type Review,
  type LinkDirection, type LinkTrigger,
} from './api'

const label = (s: Session | undefined): string => {
  const id = s?.identity
  if (!id) return s?.session_id || '?'
  return `${String(id.number ?? '').padStart(2, '0')} ${id.name || id.role || ''}`.trim()
}
const shortId = (id: string, sessions: Session[]): string => label(sessions.find(s => s.session_id === id)) || id

const input: React.CSSProperties = {
  width: '100%', background: C.card, border: `2px solid ${C.border}`, borderRadius: 5,
  padding: '5px 8px', fontSize: 11, color: C.t1, fontFamily: FONT, outline: 'none',
}
const cardStyle: React.CSSProperties = { background: C.card, border: `2px solid ${C.border}`, borderRadius: 5, boxShadow: C.shadowSm, padding: '8px 11px', marginBottom: 8 }

// ---- Library ---------------------------------------------------------------

function LibraryTab({ focused }: { focused: Session | null }) {
  const cwd = focused?.cwd || ''
  const [subdir, setSubdir] = useState<'' | 'plans'>('')
  const [docs, setDocs] = useState<LibraryDoc[]>([])
  const [reviews, setReviews] = useState<Record<string, Review>>({})
  const [open, setOpen] = useState<{ filename: string; content: string } | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!cwd) { setDocs([]); setReviews({}); return }
    let cancelled = false
    setLoading(true)
    Promise.all([api.libraryDocuments(cwd, subdir || undefined), api.libraryReviews(cwd)]).then(([d, r]) => {
      if (cancelled) return
      setDocs(d || []); setReviews(r || {}); setLoading(false)
    })
    return () => { cancelled = true }
  }, [cwd, subdir])

  const openDoc = async (path: string) => {
    const d = await api.libraryDocument(path)
    if (d) setOpen({ filename: d.filename, content: d.content })
  }

  if (!cwd) return <Hint>Select an agent with a working directory to browse its Plans &amp; Documents.</Hint>

  if (open) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderBottom: `2px solid ${C.border}`, background: C.surface }}>
          <Btn variant="cream" onClick={() => setOpen(null)}>← Back</Btn>
          <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, fontFamily: MONO, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{open.filename}</span>
        </div>
        <pre style={{ flex: 1, overflow: 'auto', margin: 0, padding: 12, fontSize: 11, fontFamily: MONO, color: C.t2, whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: C.card }}>{open.content}</pre>
      </div>
    )
  }

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 10 }}>
      <div style={{ width: 180, marginBottom: 8 }}>
        <Segmented options={[{ value: '', label: 'Documents' }, { value: 'plans', label: 'Plans' }]} value={subdir} onChange={v => setSubdir(v as any)} />
      </div>
      {loading ? <Hint>Loading…</Hint> : docs.length === 0 ? (
        <Hint>No .md files in {subdir ? `${cwd}/plans` : cwd}.</Hint>
      ) : docs.map(d => {
        const rev = reviews[d.filename]
        return (
          <div key={d.path} onClick={() => openDoc(d.path)} className="nb-btn" style={{ ...cardStyle, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12 }}>📄</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 11, fontWeight: 800, color: C.t1, fontFamily: MONO, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.filename}</div>
              <div style={{ fontSize: 9, color: C.t5 }}>{(d.size / 1024).toFixed(1)} KB · {timeAgo(d.modified)} ago</div>
            </div>
            {rev?.verdict && <span style={{ fontSize: 8.5, fontWeight: 800, color: '#fff', background: C.railSection, border: `2px solid ${C.border}`, borderRadius: 3, padding: '2px 6px', textTransform: 'uppercase' }}>{rev.verdict}</span>}
          </div>
        )
      })}
    </div>
  )
}

// ---- Links -----------------------------------------------------------------

function LinkRow({ link, sessions, onDelete, onKickoff }: {
  link: Link
  sessions: Session[]
  onDelete: () => void
  onKickoff: (from: string, to: string, prompt: string) => void
}) {
  const [koOpen, setKoOpen] = useState(false)
  // The sender must satisfy the link direction (backend Link.allows), else
  // kickoff 400s. Default + restrict to the allowed sender: a2b -> a, b2a -> b;
  // only 'both' lets the operator pick either end.
  const [from, setFrom] = useState(link.direction === 'b2a' ? link.b : link.a)
  const [text, setText] = useState('')
  const to = from === link.a ? link.b : link.a
  const arrow = link.direction === 'both' ? '↔' : link.direction === 'a2b' ? '→' : '←'

  return (
    <div style={{ ...cardStyle, opacity: link.active ? 1 : 0.55 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: C.t1 }}>{shortId(link.a, sessions)} {arrow} {shortId(link.b, sessions)}</span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 8.5, fontWeight: 800, color: C.t3, background: C.surface, border: `1.5px solid ${C.rule}`, borderRadius: 3, padding: '1px 5px' }}>{link.relationship}</span>
        <span style={{ fontSize: 8.5, fontWeight: 800, color: C.t3, background: C.surface, border: `1.5px solid ${C.rule}`, borderRadius: 3, padding: '1px 5px' }}>{link.trigger}</span>
      </div>
      <div style={{ fontSize: 9, color: C.t5, marginTop: 4, fontFamily: MONO }}>
        {link.exchanges} exchanges · {link.messages} msgs · cap {link.end_after_exchanges ?? '∞'} {link.active ? '' : '· ENDED'}
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <Btn variant="secondary" onClick={() => setKoOpen(o => !o)} disabled={!link.active} style={{ padding: '3px 9px', fontSize: 10 }}>Kick off</Btn>
        <div style={{ flex: 1 }} />
        <Btn variant="danger" onClick={onDelete} style={{ padding: '3px 9px', fontSize: 10 }}>Delete</Btn>
      </div>
      {koOpen && (
        <div style={{ marginTop: 7, borderTop: `1.5px solid ${C.rule}`, paddingTop: 7 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: 10, color: C.t3 }}>
            {link.direction === 'both' ? (
              <select className="nb-in" style={{ ...input, width: 'auto', fontSize: 10 }} value={from} onChange={e => setFrom(e.target.value)}>
                <option value={link.a}>{shortId(link.a, sessions)}</option>
                <option value={link.b}>{shortId(link.b, sessions)}</option>
              </select>
            ) : (
              <span style={{ fontWeight: 800, color: C.t1 }}>{shortId(from, sessions)}</span>
            )}
            <span>→ {shortId(to, sessions)}</span>
          </div>
          <textarea className="nb-in" value={text} onChange={e => setText(e.target.value)} placeholder="Opening message…"
            style={{ ...input, minHeight: 44, resize: 'vertical', fontFamily: MONO, fontSize: 11 }} />
          <Btn variant="primary" onClick={() => { onKickoff(from, to, text.trim()); setText(''); setKoOpen(false) }} disabled={!text.trim()} style={{ marginTop: 6, padding: '3px 9px', fontSize: 10 }}>Send kickoff</Btn>
        </div>
      )}
    </div>
  )
}

function CreateLink({ sessions, onCreate }: { sessions: Session[]; onCreate: (b: any) => void }) {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [direction, setDirection] = useState<LinkDirection>('both')
  const [rel, setRel] = useState<string[]>(['direct'])
  const [trigger, setTrigger] = useState<LinkTrigger>('queue')
  const [cap, setCap] = useState('25')
  const canCreate = a && b && a !== b

  const toggleRel = (r: string) => setRel(prev => prev.includes(r) ? prev.filter(x => x !== r) : [...prev, r])

  const create = () => {
    onCreate({
      a, b, direction, relationship: rel[0] || 'direct', trigger,  // ONE relationship per link (§7.6)
      end_after_exchanges: cap.trim() ? Number(cap) : null,
    })
    setA(''); setB('')
  }

  return (
    <div style={{ ...cardStyle, background: C.bg }}>
      <div style={{ fontSize: 9, fontWeight: 800, color: C.t3, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 7 }}>New link</div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 7 }}>
        <select className="nb-in" style={input} value={a} onChange={e => setA(e.target.value)}>
          <option value="">Agent A…</option>
          {sessions.map(s => <option key={s.session_id} value={s.session_id}>{label(s)}</option>)}
        </select>
        <select className="nb-in" style={input} value={b} onChange={e => setB(e.target.value)}>
          <option value="">Agent B…</option>
          {sessions.map(s => <option key={s.session_id} value={s.session_id}>{label(s)}</option>)}
        </select>
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 7 }}>
        <div style={{ flex: 1 }}>
          <Segmented options={[{ value: 'a2b', label: 'A→B' }, { value: 'both', label: 'A↔B' }, { value: 'b2a', label: 'B→A' }]} value={direction} onChange={v => setDirection(v as LinkDirection)} />
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
        <label style={{ fontSize: 10, fontWeight: 700, color: C.t3, display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
          <input type="checkbox" checked={rel.includes('direct')} onChange={() => toggleRel('direct')} /> direct
        </label>
        <label style={{ fontSize: 10, fontWeight: 700, color: C.t3, display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
          <input type="checkbox" checked={rel.includes('shared')} onChange={() => toggleRel('shared')} /> shared
        </label>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 9, color: C.t5 }}>trigger</span>
        <select className="nb-in" style={{ ...input, width: 'auto' }} value={trigger} onChange={e => setTrigger(e.target.value as LinkTrigger)}>
          {['queue', 'next', 'now', 'inject', 'hold'].map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <span style={{ fontSize: 9, color: C.t5 }}>cap</span>
        <input className="nb-in" style={{ ...input, width: 52 }} value={cap} onChange={e => setCap(e.target.value.replace(/[^0-9]/g, ''))} />
      </div>
      <Btn variant="primary" onClick={create} disabled={!canCreate} style={{ width: '100%' }}>Create link</Btn>
    </div>
  )
}

function LinksTab({ sessions, links, onChanged }: { sessions: Session[]; links: LinksResponse; onChanged: () => void }) {
  const create = async (body: any) => { await api.createLink(body); onChanged() }
  const del = async (id: string) => { await api.deleteLink(id); onChanged() }
  const kickoff = async (id: string, from: string, to: string, prompt: string) => {
    if (!prompt) return
    await api.kickoffLink(id, { from_agent: from, to_agent: to, prompt }); onChanged()
  }
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 10 }}>
      <CreateLink sessions={sessions} onCreate={create} />
      {links.links.length === 0 ? <Hint>No links yet. Create one above to wire two agents together.</Hint> : (
        links.links.map(l => (
          <LinkRow key={l.id} link={l} sessions={sessions} onDelete={() => del(l.id)} onKickoff={(f, t, p) => kickoff(l.id, f, t, p)} />
        ))
      )}
    </div>
  )
}

// ---- Scratch ---------------------------------------------------------------

function ScratchTab({ focused }: { focused: Session | null }) {
  const cwd = focused?.cwd || ''
  const [posts, setPosts] = useState<ScratchPost[]>([])
  const [text, setText] = useState('')
  const author = focused ? label(focused) : 'user'

  const load = () => { if (cwd) api.scratch(cwd).then(r => setPosts(r?.posts || [])) }
  useEffect(() => { load(); const i = setInterval(load, 3000); return () => clearInterval(i) }, [cwd])

  const post = async () => {
    if (!text.trim() || !cwd) return
    await api.postScratch({ cwd, author, text: text.trim() })
    setText(''); load()
  }

  if (!cwd) return <Hint>Select an agent with a working directory — the scratchpad is shared per project.</Hint>

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div style={{ flex: 1, overflow: 'auto', padding: 10 }}>
        {posts.length === 0 ? <Hint>No posts on this project's board yet.</Hint> : posts.map(p => (
          <div key={p.seq} style={cardStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 3 }}>
              <span style={{ fontSize: 9, fontWeight: 800, color: C.railSection, textTransform: 'uppercase' }}>{p.author}</span>
              <span style={{ fontSize: 9, color: C.t5, fontFamily: MONO }}>{p.ts ? new Date(p.ts).toLocaleTimeString() : ''}</span>
            </div>
            <div style={{ fontSize: 11.5, color: C.t2, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{p.text}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6, padding: 10, borderTop: `2px solid ${C.border}`, background: C.surface }}>
        <input className="nb-in" style={input} value={text} placeholder={`Post as ${author}…`}
          onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') post() }} />
        <Btn variant="primary" onClick={post} disabled={!text.trim()}>Post</Btn>
      </div>
    </div>
  )
}

function Hint({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', margin: '30px 12px', lineHeight: 1.6 }}>{children}</div>
}

// ---- Panel shell -----------------------------------------------------------

export function WorkPanel({ sessions, focused, links, onLinksChanged }: {
  sessions: Session[]
  focused: Session | null
  links: LinksResponse
  onLinksChanged: () => void
}) {
  const [tab, setTab] = useState<'library' | 'links' | 'scratch'>('library')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ height: 34, minHeight: 34, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 10px', gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Work</span>
        <div style={{ flex: 1 }} />
        <Tabs tabs={[
          { value: 'library', label: 'Library' },
          { value: 'links', label: 'Links', badge: links.links.filter(l => l.active).length, badgeColor: C.teal },
          { value: 'scratch', label: 'Scratch' },
        ]} active={tab} onChange={(t) => setTab(t as any)} />
      </div>
      {tab === 'library' && <LibraryTab focused={focused} />}
      {tab === 'links' && <LinksTab sessions={sessions} links={links} onChanged={onLinksChanged} />}
      {tab === 'scratch' && <ScratchTab focused={focused} />}
    </div>
  )
}
