// ============================================================================
// Prompt — Compose (Editor + templates + inserted blocks) · History, over the
// shared From → To sub-bar, with the Revise/Send split buttons (right, bottom).
// ============================================================================

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api, type Disposition, type ResponsePreset } from '../api'
import { useDash } from '../store'
import { Ic } from '../lib/icons'
import { identOf, IdentBadge, BadgeXs, USER_IDENT, SCRATCH_IDENT, clockTime, type Ident } from '../lib/identity'
import { MultiAgAccordion, SingleAgAccordion, useRoster } from './selectors'
import { isCliNoise } from '../lib/transcript'
import { ExportControl } from './ExportControl'
import { toast } from '../lib/toast'

const esc = (s: string) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const X_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" style="width:10px;height:10px"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>'

function embedBlockHTML(source: string, body: string): string {
  return '<div data-comp="inserted-block" class="ed-block ed-block--embed" data-block="embed" contenteditable="false">'
    + '<div class="ed-block-head"><span class="ed-block-from">from <b>' + esc(source) + '</b></span><span class="flex-1"></span>'
    + '<button class="ed-block-x" type="button" data-edx title="Remove block">' + X_SVG + '</button></div>'
    + '<div class="ed-block-body">' + esc(body) + '</div></div>'
}
function phSpan(tag: string): string {
  return '<span data-comp="placeholder-pill" class="ph-text" data-tag="' + esc(tag) + '" contenteditable="false">' + esc(tag) + '</span>'
}
function templateBlockHTML(name: string, body: string, placeholders: string[], tplId: string): string {
  let html = esc(body)
  for (const ph of placeholders || []) {
    const tag = ph.startsWith('{') ? ph : `{${ph}}`
    html = html.split(esc(tag)).join(phSpan(tag))
  }
  return '<div data-comp="inserted-block" class="ed-block ed-block--template sel" data-block="template" data-tpl="' + esc(tplId) + '" contenteditable="false">'
    + '<div class="ed-block-head"><span class="ed-block-from">from <b>Template · ' + esc(name) + '</b></span><span class="flex-1"></span>'
    + '<span class="ed-block-kind">template</span>'
    + '<button class="ed-block-x" type="button" data-edx title="Remove block">' + X_SVG + '</button></div>'
    + '<div class="ed-block-body">' + html + '</div></div>'
}

export function PromptPanel() {
  const d = useDash()
  const roster = useRoster()
  const fieldRef = useRef<HTMLDivElement>(null)

  // ---- From / To ------------------------------------------------------------
  const [source, setSource] = useState('user')
  const [targets, setTargets] = useState<Set<string>>(new Set())
  const [histOff, setHistOff] = useState<Set<string>>(new Set())
  const agentKeys = d.sessions.map(s => s.session_id)
  const histSel = useMemo(() => new Set(agentKeys.filter(k => !histOff.has(k))), [agentKeys, histOff])

  // default target: the focused agent
  useEffect(() => {
    if (!targets.size && d.selectedId) setTargets(new Set([d.selectedId]))
  }, [d.selectedId])

  // ---- pending compose (Reply / Retry / Embed hand-offs) ----------------------
  useEffect(() => {
    if (!d.pendingCompose.seq) return
    const p = d.pendingCompose
    if (p.targets?.length) setTargets(new Set(p.targets.filter(Boolean)))
    const f = fieldRef.current
    if (f) {
      if (p.text != null) f.innerText = p.text
      for (const e of p.embeds || []) f.insertAdjacentHTML('beforeend', embedBlockHTML(e.source, e.text))
      f.focus()
    }
    const pc = document.getElementById('pPrompts')
    if (pc) { pc.classList.remove('reply-flash'); void (pc as HTMLElement).offsetWidth; pc.classList.add('reply-flash'); setTimeout(() => pc.classList.remove('reply-flash'), 900) }
  }, [d.pendingCompose.seq])

  // remove-block clicks (imperative DOM inside the contenteditable)
  useEffect(() => {
    const f = fieldRef.current
    if (!f) return
    const onClick = (e: MouseEvent) => {
      const x = (e.target as HTMLElement).closest?.('[data-edx]')
      if (x) { e.preventDefault(); e.stopPropagation(); x.closest('.ed-block')?.remove(); return }
      const pill = (e.target as HTMLElement).closest?.('.ph-text') as HTMLElement | null
      if (pill) {
        f.querySelectorAll('.ph-text.sel').forEach(p2 => p2.classList.remove('sel'))
        pill.classList.add('sel')
        setActivePill(pill)
        const blk = pill.closest('.ed-block--template')
        if (blk) { f.querySelectorAll('.ed-block--template.sel').forEach(b => b.classList.remove('sel')); blk.classList.add('sel') }
      }
    }
    f.addEventListener('click', onClick)
    return () => f.removeEventListener('click', onClick)
  }, [d.promptTab])

  // ---- templates --------------------------------------------------------------
  const [tplPick, setTplPick] = useState('')
  const [activePill, setActivePill] = useState<HTMLElement | null>(null)
  const [fillValue, setFillValue] = useState('')
  const applyTemplate = (id: string) => {
    setTplPick(id)
    const f = fieldRef.current
    if (!f) return
    if (id === '') { f.querySelectorAll('.ed-block--template.sel,.ph-text.sel').forEach(p => p.classList.remove('sel')); setActivePill(null); return }
    const t = d.templates.find(t => t.id === id)
    if (!t) return
    f.querySelectorAll('.ed-block--template.sel').forEach(b => b.classList.remove('sel'))
    f.insertAdjacentHTML('beforeend', templateBlockHTML(t.name, t.body, t.placeholders || [], t.id))
  }
  const fillPill = () => {
    if (!activePill) { toast('Tap a placeholder pill first'); return }
    const v = fillValue.trim()
    if (v) { activePill.classList.add('filled'); activePill.textContent = v; activePill.dataset.value = v }
    else { activePill.classList.remove('filled'); activePill.textContent = activePill.dataset.tag || '' }
  }
  const resetPill = () => {
    if (!activePill) return
    activePill.classList.remove('filled')
    activePill.textContent = activePill.dataset.tag || ''
    setFillValue('')
  }

  // ---- send / revise -------------------------------------------------------------
  const [timing, setTiming] = useState<Disposition>('now')
  const [scope, setScope] = useState<'grammar' | 'language' | 'refactor'>('grammar')
  const [busy, setBusy] = useState(false)
  const composeText = (): string => fieldRef.current?.innerText.trim() || ''
  const send = async () => {
    const text = composeText()
    if (!text) { toast('Nothing to send'); return }
    const tg = [...targets]
    if (!tg.length) { toast('Pick a target first'); return }
    setBusy(true)
    const r = await d.sendPrompt(text, { source, targets: tg, timing })
    setBusy(false)
    toast(`Send → ${r}`)
    if (fieldRef.current && /queued|sent|delivered|posted|injected/.test(r)) fieldRef.current.innerHTML = ''
  }
  const revise = async () => {
    const text = composeText()
    if (!text) { toast('Nothing to revise'); return }
    setBusy(true)
    const r = await api.revise(text, scope)
    setBusy(false)
    if (r?.result && fieldRef.current) { fieldRef.current.innerText = r.result; toast(`Revised (${scope})`) }
    else toast('Revise unavailable (utility endpoint)')
  }

  // ---- history --------------------------------------------------------------------
  const prompts = useMemo(() => {
    const out: { key: string; from: string; to: string[]; text: string; time: string; status: string; badge: string }[] = []
    for (const e of d.events) {
      if (!(e.sdk_type === 'UserMessage' || e.type === 'user')) continue
      const content = Array.isArray(e.content) ? e.content : (typeof e.content === 'string' ? [{ type: 'text', text: e.content }] : [])
      const texts = content.filter((b: any) => b.type === 'text' && b.text?.trim() && !isCliNoise(b.text)).map((b: any) => b.text)
      if (!texts.length) continue
      const from = (e.source && e.source !== 'user' && e.source !== e.agent_id) ? e.source : 'user'
      out.push({
        key: e.id || `h:${e.seq}`, from,
        to: (e.recipients?.length && !(e.recipients.length === 1 && e.recipients[0] === 'user') ? e.recipients : (e.agent_id ? [e.agent_id] : [])),
        text: texts.join('\n\n'), time: clockTime(e.ts || e.timestamp),
        status: 'Complete', badge: 'db-complete',
      })
    }
    return out.reverse()
  }, [d.events])
  const [histSelCards, setHistSelCards] = useState<Set<string>>(new Set())
  const [histOpen, setHistOpen] = useState<Set<string>>(new Set())
  const shownPrompts = prompts.filter(p => p.from === 'user' ? true : histSel.has(p.from))
  const histSelection = shownPrompts.filter(p => histSelCards.has(p.key))

  const identFor = (key: string): Ident => {
    if (key === 'user') return USER_IDENT
    if (key === 'scratch') return SCRATCH_IDENT
    const s = d.sessions.find(x => x.session_id === key)
    return s ? identOf(s) : { key, role: 'agent', name: key.slice(0, 12), short: key, color: 'var(--muted)', icon: '' }
  }

  return (
    <section className="rz-panel" id="pPrompts" style={{ flex: '1 1 48%', minHeight: 'var(--pane-prompts-min-h)', maxHeight: 'var(--pane-prompts-max-h)' }}>
      <div className="pcard-head">
        <h3>Prompt</h3>
        <div data-comp="tab-bar" className="tabset">
          <button className={`tab-btn${d.promptTab === 'compose' ? ' active' : ''}`} onClick={() => d.setPromptTab('compose')}>Compose</button>
          <button className={`tab-btn${d.promptTab === 'history' ? ' active' : ''}`} onClick={() => d.setPromptTab('history')}>History</button>
        </div>
      </div>
      <div className="pcard-body flex flex-col overflow-hidden" style={{ background: 'var(--background)' }}>
        <div className="subbar">
          {d.promptTab === 'compose' ? (
            <SingleAgAccordion id="source-dd" rows={roster.agents} lead={[USER_IDENT]} sel={source} onSel={setSource} />
          ) : (
            <MultiAgAccordion id="hist-from" header="From" rows={roster.agents} sel={histSel}
              onSel={next => setHistOff(new Set(agentKeys.filter(k => !next.has(k))))} />
          )}
          <span className="subbar-route" title="to"><Ic name="arrow-right" /></span>
          <MultiAgAccordion id="prompt-targets" header="Target" rows={roster.agents} lead={[SCRATCH_IDENT]} sel={targets} onSel={setTargets} />
        </div>

        <div className="flex-1 min-w-0 flex flex-col p-2.5 overflow-hidden">
          {d.promptTab === 'compose' && (
            <div className="flex-1 flex flex-col min-h-0">
              <div className="flex items-center gap-1.5 mb-1.5">
                <span className="text-[9px] font-heading uppercase tracking-wide text-muted">Editor</span>
                <button data-comp="ghost-icon-button" className="ghost-ic editor-mic" title="Dictate (voice → text) — pending the dictation backend" disabled><Ic name="mic" /></button>
                <span className="flex-1" />
                <button data-comp="ghost-icon-button" className="ghost-ic" title="Copy" onClick={() => { navigator.clipboard?.writeText(composeText()); toast('Editor copied') }}><Ic name="copy" /></button>
                <button data-comp="ghost-icon-button" className="ghost-ic ghost-ic--danger" title="Clear" onClick={() => { if (fieldRef.current) fieldRef.current.innerHTML = '' }}><Ic name="trash-2" /></button>
              </div>
              <div className="compose-jump-wrap flex-1 min-h-0 flex flex-col">
                <div data-comp="prompt-editor" id="compose-field" ref={fieldRef}
                  className="in compose-rich flex-1 min-h-[90px] text-[12px] leading-relaxed" contentEditable suppressContentEditableWarning />
              </div>
              <div className="sec-h mt-3">Templates <span className="text-muted-2 font-semibold normal-case">insert a template block at the cursor</span></div>
              <select data-comp="template-select" className="in tpl-select shrink-0" value={tplPick} onChange={e => applyTemplate(e.target.value)}>
                <option value="">None</option>
                {d.templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              <div data-comp="template-fill" className="tpl-fill mt-2 shrink-0">
                <textarea className="autosize" rows={1} placeholder={activePill ? `Fill ${activePill.dataset.tag}` : 'Insert a template, then tap a placeholder pill…'}
                  disabled={!activePill} value={fillValue} onChange={e => setFillValue(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); fillPill() } }} />
                <button data-comp="fill-button" className="fill-btn" title="Reset placeholder" disabled={!activePill} onClick={resetPill}><Ic name="rotate-ccw" /></button>
                <button data-comp="fill-button" className="fill-btn fill-btn--go" title="Apply value" disabled={!activePill} onClick={fillPill}><Ic name="corner-down-left" /></button>
              </div>
            </div>
          )}

          {d.promptTab === 'history' && (
            <div className="flex-1 overflow-y-auto -mr-1 pr-1">
              <div className="flex flex-col gap-2">
                {shownPrompts.map(p => (
                  <div data-comp="history-card" key={p.key} className={`fcard${histSelCards.has(p.key) ? ' sel' : ''}${histOpen.has(p.key) ? ' open' : ''}`}>
                    <div className="fcard-head">
                      <button className="fcard-exp msel-head" title="Select this prompt"
                        onClick={() => setHistSelCards(prev => { const n = new Set(prev); n.has(p.key) ? n.delete(p.key) : n.add(p.key); return n })}>
                        <span data-comp="lifecycle-badge" className={`dbadge ${p.badge}`}>{p.status}</span>
                        <IdentBadge a={identFor(p.from)} />
                        <Ic name="arrow-right" style={{ width: 'var(--size-12)', height: 'var(--size-12)', color: 'var(--muted)', flex: '0 0 auto' }} />
                        {p.to.slice(0, 2).map(t => <BadgeXs key={t} a={identFor(t)} />)}
                        {p.to.length > 2 && <span className="rcpt-more">+{p.to.length - 2}</span>}
                        <span className="flex-1" />
                        <span className="fcard-time">{p.time}</span>
                      </button>
                      <button data-comp="ghost-icon-button" className="ghost-ic" title="Edit in Compose"
                        onClick={e => { e.stopPropagation(); d.replyTo(p.to[0] || '', undefined, p.text) }}><Ic name="square-pen" /></button>
                      <button className="fcard-chevbtn" title="Expand / collapse"
                        onClick={() => setHistOpen(prev => { const n = new Set(prev); n.has(p.key) ? n.delete(p.key) : n.add(p.key); return n })}>
                        <Ic name="chevron-right" className="fcard-chev" />
                      </button>
                    </div>
                    <div className="fcard-body"><div className="fcard-full">{p.text}</div></div>
                  </div>
                ))}
                {!shownPrompts.length && <div className="awl-empty">No prompts yet — everything you send lands here.</div>}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ACTION STRIP — Compose */}
      {d.promptTab === 'compose' && (
        <div className="pcard-foot px-2 py-2.5">
          <div className="flex items-center gap-2">
            <button data-comp="attach-button" className="mic-btn attach-btn" title="Attach an asset (from the Library → Assets)"
              onClick={() => { d.setLibTab('assets'); toast('Pick an asset in Library → Assets') }}><Ic name="paperclip" /></button>
            <SplitButton kind="outline" label={scope[0].toUpperCase() + scope.slice(1)} actIcon="wand-sparkles" actTitle="Revise the draft"
              onAct={revise} busy={busy}
              menuHeader="Revise scope"
              items={[
                { short: 'Grammar', sub: 'Fix spelling & grammar only', on: () => setScope('grammar'), sel: scope === 'grammar' },
                { short: 'Language', sub: 'Tighten wording & tone', on: () => setScope('language'), sel: scope === 'language' },
                { short: 'Refactor', sub: 'Restructure for clarity', on: () => setScope('refactor'), sel: scope === 'refactor' },
              ]} />
            <ResponseFormat />
            <div className="flex-1" />
            <SplitButton kind="primary" label={timing[0].toUpperCase() + timing.slice(1)} actIcon="send-horizontal" actTitle="Send to target agents"
              onAct={send} busy={busy} menuRight
              menuHeader="When to deliver"
              items={[
                { short: 'Now', sub: 'Interrupt & deliver immediately', on: () => setTiming('now'), sel: timing === 'now' },
                { short: 'Inject', sub: 'Deliver to the running agent without stopping it', on: () => setTiming('inject'), sel: timing === 'inject' },
                { short: 'Next', sub: 'Deliver at the next turn boundary', on: () => setTiming('next'), sel: timing === 'next' },
                { short: 'Queue', sub: "Add to the agent's prompt queue", on: () => setTiming('queue'), sel: timing === 'queue' },
              ]} />
          </div>
        </div>
      )}

      {/* ACTION STRIP — History */}
      {d.promptTab === 'history' && (
        <div className="pcard-foot px-2 py-2.5">
          <div className="flex items-center gap-2 flex-wrap">
            <button data-comp="icon-button" className="icon-btn" title="Select / deselect all prompts"
              onClick={() => setHistSelCards(p => p.size === shownPrompts.length ? new Set() : new Set(shownPrompts.map(x => x.key)))}><Ic name="list-checks" /></button>
            <ExportControl a={{
              enabled: histSelection.length > 0,
              fileDisabled: !d.projectCwd,
              onCopy: () => { navigator.clipboard?.writeText(histSelection.map(p => p.text).join('\n\n')); toast('Copied') },
              onFile: async () => {
                if (!d.projectCwd) return
                const r = await api.createDocument({ cwd: d.projectCwd, filename: `prompts-${Date.now()}.md`, content: histSelection.map(p => p.text).join('\n\n'), subdir: 'docs' })
                toast(r ? 'Exported → Library → Documents' : 'Export failed')
              },
              onEmbed: () => d.replyTo(d.selectedId || '', { source: 'History', text: histSelection.map(p => p.text).join('\n\n') }),
              onAttach: () => toast('Attach lands with the attachment strip backend'),
            }} />
            <div className="flex-1" />
            <button data-comp="icon-button" className="icon-btn" title="Retry prompt"
              onClick={() => { if (histSelection[0]) { d.replyTo(histSelection[0].to[0] || '', undefined, histSelection[0].text); d.setPromptTab('compose') } else toast('Select a prompt first') }}><Ic name="rotate-ccw" /></button>
            <button data-comp="icon-button" className="icon-btn icon-btn--danger-solid" title="Stop this run"
              onClick={async () => {
                const targets = new Set(histSelection.flatMap(p => p.to).filter(t => t !== 'scratch' && t !== 'user'))
                if (!targets.size && d.selectedId) targets.add(d.selectedId)
                for (const id of targets) await api.interrupt(id)
                toast(`Stop sent to ${targets.size} agent(s)`)
              }}><Ic name="square" /></button>
          </div>
        </div>
      )}
    </section>
  )
}

// ---- Response-format control (§11 #39) — the focused agent's reply-format preset ----
// The backend shipped a FLAT preset catalog (id / label / description), not the
// mockup's older Style·Behavior axes, so the popover renders the presets as a
// single-choice list. A set persists to state/agents.json and takes effect at the
// agent's NEXT launch/restart (append-system-prompt is a launch flag); the fmt
// badge reads "1" when a non-default preset is active. Binds to the focused agent.
function ResponseFormat() {
  const d = useDash()
  const [open, setOpen] = useState(false)
  const [presets, setPresets] = useState<ResponsePreset[]>([])
  const [dflt, setDflt] = useState('default')
  const [sel, setSel] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const id = d.selectedId

  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  useEffect(() => { api.responsePresets().then(c => { if (c) { setPresets(c.presets); setDflt(c.default) } }) }, [])
  // Pull the focused agent's current preset whenever the focus changes.
  useEffect(() => {
    if (!id) { setSel(null); return }
    let cancelled = false
    api.responsePreset(id).then(r => { if (!cancelled) setSel(r?.response_preset ?? null) })
    return () => { cancelled = true }
  }, [id])

  const current = sel ?? dflt
  const overridden = !!sel && sel !== dflt
  const pick = async (pid: string) => {
    if (!id) { toast('Focus an agent first'); return }
    const prev = sel
    setSel(pid); setBusy(true)
    const r = await api.setResponsePreset(id, pid)
    setBusy(false)
    if (r) toast(`Response format → ${presets.find(p => p.id === pid)?.label || pid} (applies at next launch)`)
    else { setSel(prev); toast('Response-format set rejected') }
  }
  return (
    <div data-comp="response-format-control" className="fmt" ref={ref}>
      <button className={`fmt-btn${overridden ? ' active' : ''}`} title="Response format — the focused agent's reply-format preset" onClick={e => { e.stopPropagation(); setOpen(o => !o) }}>
        <Ic name="sliders-horizontal" className="ic" /><span className="fmt-lbl">Response</span>
        <span data-comp="count-square" className="fmt-badge">{overridden ? 1 : 0}</span><Ic name="chevron-down" className="cv" />
      </button>
      <div data-comp="format-popover" className={`fmt-menu up left${open ? ' open' : ''}`}>
        <div className="split-menu-h">{id ? 'Reply-format preset · applies at next launch' : 'Focus an agent to set its reply format'}</div>
        {presets.map(p => (
          <button key={p.id} className={`split-mi${current === p.id ? ' sel' : ''}`} disabled={busy || !id} onClick={() => pick(p.id)}>
            <span className="lead"><b>{p.label}</b><span className="sub">{p.description}</span></span><span className="ck">✓</span>
          </button>
        ))}
        {!presets.length && <div className="awl-empty" style={{ padding: 'var(--space-10)' }}>No presets — the sidecar's /presets/response is unavailable.</div>}
      </div>
    </div>
  )
}

// ---- split button (Send + timing · Revise + scope) --------------------------------
function SplitButton({ kind, label, actIcon, actTitle, onAct, busy, menuHeader, items, menuRight }: {
  kind: 'primary' | 'outline'
  label: string; actIcon: string; actTitle: string; onAct: () => void; busy?: boolean
  menuHeader: string
  items: { short: string; sub: string; on: () => void; sel: boolean }[]
  menuRight?: boolean
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  return (
    <div data-comp="split-button" className={`split split--${kind}`} ref={ref}>
      <button className="split-drop" onClick={e => { e.stopPropagation(); setOpen(o => !o) }}><Ic name="chevron-down" /><span className="split-lbl">{label}</span></button>
      <button className="split-act" title={actTitle} disabled={busy} onClick={onAct}><Ic name={actIcon} /></button>
      <div className={`split-menu${menuRight ? ' split-menu--right' : ''}${open ? ' open' : ''}`}>
        <div className="split-menu-h">{menuHeader}</div>
        {items.map(it => (
          <button key={it.short} className={`split-mi${it.sel ? ' sel' : ''}`} onClick={() => { it.on(); setOpen(false) }}>
            <span className="lead"><b>{it.short}</b><span className="sub">{it.sub}</span></span><span className="ck">✓</span>
          </button>
        ))}
      </div>
    </div>
  )
}
