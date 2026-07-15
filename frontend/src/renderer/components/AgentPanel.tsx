// ============================================================================
// Agent panel — Details · Create · Console (left column, mockup DOM).
// Live wiring: identity edits → POST /identity; model/mode/effort/fast/think →
// their endpoints (optimistic, reverting with an honest disabled flash on a
// rejected/absent endpoint); Retire/Delete → DELETE /sessions/{id}[?hard];
// Create → POST /sessions. Un-armed permission-mode segments hide when the
// session exposes its armed set (#13 UI half) — all five render otherwise.
// ============================================================================

import React, { useEffect, useRef, useState } from 'react'
import { api, type CreatePayload, type Session } from '../api'
import { useDash } from '../store'
import { Ic, AgGlyph, SPRITE_BY_FILE } from '../lib/icons'
import {
  identOf, runStateOf, ctxColor, createdStamp, modelLabel, jewelName, JEWELS,
  NB_CLASS, NB_LABEL, fmtTokens, MODE_VALUE,
} from '../lib/identity'
import { toast } from '../lib/toast'
import { useConsole, ConsoleFeed, CommandList } from './Console'

const DEFAULT_MAX_TURNS = 50
const CTX_CUTOFF = 80

// ---- small shared atoms -----------------------------------------------------

function EditField({ label, value, onSave, textarea, center, disabled, note }: {
  label: string; value: string; onSave?: (v: string) => void; textarea?: boolean; center?: boolean; disabled?: boolean; note?: string
}) {
  const [editing, setEditing] = useState(false)
  const [v, setV] = useState(value)
  useEffect(() => { if (!editing) setV(value) }, [value, editing])
  const commit = () => { setEditing(false); if (onSave && v !== value) onSave(v) }
  return (
    <div data-comp="edit-lock" className={`field${editing ? ' editing' : ''}`}>
      <div className="flex items-center justify-between mb-1">
        <label className="lbl">{label}</label>
        {onSave && !disabled && (
          <button className="edit-ic" onClick={() => (editing ? commit() : setEditing(true))}>
            <Ic name="square-pen" className="ic-pencil w-3.5 h-3.5" /><Ic name="check" className="ic-save w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {textarea
        ? <textarea className="lockable in autosize" value={v} rows={3} onChange={e => setV(e.target.value)} />
        : <input data-comp="text-input" className={`lockable in${center ? ' text-center' : ''}`} value={v} onChange={e => setV(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') commit() }} />}
      {note && <div className="text-[10px] text-muted-2 mt-1 normal-case font-semibold">{note}</div>}
    </div>
  )
}

const MSEL_CATALOG: Record<string, { group: string; items: string[] }[]> = {
  tools: [
    { group: 'Core tools', items: ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'WebSearch', 'WebFetch'] },
    { group: 'More native tools', items: ['Agent', 'AskUserQuestion', 'NotebookEdit', 'TodoWrite', 'ExitPlanMode', 'Skill', 'SendMessage', 'BashOutput', 'KillShell', 'SlashCommand', 'PowerShell'] },
  ],
  denyrules: [
    { group: 'Deny rules — tools/commands this agent can never run', items: ['Bash(rm -rf:*)', 'Bash(sudo:*)', 'Bash(git push:*)', 'Bash(curl:*)', 'Write(/etc/**)', 'Write(**/.env)', 'Read(**/.env)', 'Read(**/secrets/**)', 'WebFetch', 'Edit(**/*.lock)'] },
  ],
  mcp: [{ group: 'Configured MCP servers — none = all available', items: ['playwright', 'github', 'firecrawl', 'exa', 'notion', 'docker', 'brave-search'] }],
  plugins: [{ group: 'Installed plugins — none = all enabled', items: ['claude-mem', 'superpowers', 'everything-claude-code', 'ui-ux-pro-max', 'pyright-lsp'] }],
  skills: [{ group: 'User skills (~/.claude/skills)', items: ['browser-use', 'defuddle', 'distill', 'research-brief', 'session-handoff', 'workspace-status'] }],
}

function MSel({ kind, sel, onChange, disabled }: { kind: string; sel: string[]; onChange?: (v: string[]) => void; disabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const cat = MSEL_CATALOG[kind] || []
  const toggle = (it: string) => {
    if (!onChange) return
    onChange(sel.includes(it) ? sel.filter(x => x !== it) : [...sel, it])
  }
  return (
    <div data-comp="multi-select" className={`msel${disabled ? ' lockable' : ''}`}>
      <div className="msel-box" onClick={() => !disabled && setOpen(o => !o)}>
        {sel.length
          ? sel.map(it => (
            <span className="msel-chip" key={it}>{it}
              {onChange && !disabled && <button type="button" data-it={it} onClick={e => { e.stopPropagation(); toggle(it) }}><Ic name="x" /></button>}
            </span>
          ))
          : <span className="msel-ph">Select…</span>}
        <Ic name="chevrons-up-down" className="msel-cv" />
      </div>
      <div className={`msel-pop${open ? ' open' : ''}`}>
        {cat.map(g => (
          <React.Fragment key={g.group}>
            <div className="msel-gh">{g.group}</div>
            {g.items.map(it => (
              <button type="button" key={it} className={`msel-opt${sel.includes(it) ? ' on' : ''}`} onClick={e => { e.stopPropagation(); toggle(it) }}>
                <Ic name="check" className="mck" /><span className="mname">{it}</span>
              </button>
            ))}
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}

// lockable wrapper for the on-demand config fields (pencil → editable → save)
function LockField({ label, children, onSave, note, noPencil, title }: {
  label: string; children: (editing: boolean) => React.ReactNode; onSave?: () => void; note?: string; noPencil?: boolean; title?: string
}) {
  const [editing, setEditing] = useState(false)
  return (
    <div className={`field${editing ? ' editing' : ''}`} title={title}>
      <div className="flex items-center justify-between mb-1">
        <label className="lbl">{label}</label>
        {!noPencil && (
          <button className="edit-ic" onClick={() => { if (editing && onSave) onSave(); setEditing(e => !e) }}>
            <Ic name="square-pen" className="ic-pencil w-3.5 h-3.5" /><Ic name="check" className="ic-save w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {children(editing)}
      {note && <div className="text-[10px] text-muted-2 mt-1 normal-case font-semibold">{note}</div>}
    </div>
  )
}

// ---- color + icon pickers ------------------------------------------------------
function ColorPicker({ color, onPick, locked }: { color: string; onPick: (hex: string) => void; locked?: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <div data-comp="color-picker" className={`picker${locked ? ' lockable' : ''}`}>
      <button className="picker-trig" type="button" onClick={() => setOpen(o => !o)}>
        <span className="picker-sw" style={{ background: color }} /><span className="picker-val">{jewelName(color)}</span>
        <Ic name="chevrons-up-down" className="picker-cv" />
      </button>
      <div className={`picker-pop${open ? ' open' : ''}`}>
        <div className="picker-grid">
          {JEWELS.map(j => (
            <button key={j.name} className={`sw${j.hex.toLowerCase() === color.toLowerCase() ? ' on' : ''}`} style={{ background: j.hex }} data-name={j.name}
              onClick={() => { onPick(j.hex); setOpen(false) }} />
          ))}
        </div>
      </div>
    </div>
  )
}

function IconPicker({ icon, color, onPick, locked }: { icon: string; color: string; onPick: (name: string) => void; locked?: boolean }) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const names = Object.keys(SPRITE_BY_FILE)
  return (
    <div data-comp="icon-picker" className={`picker${locked ? ' lockable' : ''}`}>
      <button className="picker-trig" type="button" onClick={() => setOpen(o => !o)}>
        <span className="agtile picker-ico" style={{ color }}><AgGlyph icon={icon} /></span>
        <span className="picker-val">{icon || '—'}</span>
        <Ic name="chevrons-up-down" className="picker-cv" />
      </button>
      <div className={`picker-pop picker-pop--wide${open ? ' open' : ''}`}>
        <div className="picker-search"><Ic name="search" /><input placeholder={`Search ${names.length} icons…`} value={q} onChange={e => setQ(e.target.value)} /></div>
        <div className="picker-grid ico-grid">
          {names.filter(n => !q || n.includes(q.toLowerCase())).map(n => (
            <button key={n} className={`icotile${n === icon ? ' on' : ''}`} data-name={n} title={n} style={{ color }}
              onClick={() => { onPick(n); setOpen(false) }}>
              <svg className="ag-svg"><use href={`#${SPRITE_BY_FILE[n]}`} /></svg>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ---- model tabs ------------------------------------------------------------------
const MODEL_FAMILIES = ['inherit', 'opus', 'sonnet', 'haiku', 'fable'] as const
function ModelTabs({ current, onPick }: { current: string | null; onPick?: (family: string) => void }) {
  const fam = (() => {
    const m = (current || '').toLowerCase()
    for (const f of MODEL_FAMILIES) if (f !== 'inherit' && m.includes(f)) return f
    return current ? 'inherit' : 'inherit'
  })()
  return (
    <div data-comp="model-selector" className="model-tabs">
      {MODEL_FAMILIES.map(f => (
        <button key={f} className={`model-tab${fam === f ? ' active' : ''}`} data-model={f}
          onClick={() => onPick && onPick(f)}>{f[0].toUpperCase() + f.slice(1)}</button>
      ))}
    </div>
  )
}

// ---- mode / effort blocks (live controls with honest revert) ----------------------
const MODES = ['Plan', 'Ask', 'Edit', 'Auto', 'Bypass']
const EFFORTS = ['Low', 'Med', 'High', 'Extra', 'Max', 'Ultra']
const EFFORT_VALUE: Record<string, string> = { Low: 'low', Med: 'medium', High: 'high', Extra: 'extra', Max: 'max', Ultra: 'ultra' }

function modeLabelOf(mode: string | null | undefined): string {
  const m = (mode || '').toLowerCase()
  if (m.includes('plan')) return 'Plan'
  if (m.includes('bypass')) return 'Bypass'
  if (m.includes('acceptedits') || m === 'edit') return 'Edit'
  if (m === 'auto' || m.includes('acceptall')) return 'Auto'
  return 'Ask'
}

function ModeBlock({ s, isOpus, live }: { s?: Session | null; isOpus: boolean; live: boolean }) {
  const current = modeLabelOf(s?.run_state?.permission_mode || s?.permission_mode)
  const [pick, setPick] = useState<string | null>(null)
  const [rejected, setRejected] = useState<string | null>(null)
  const [fast, setFast] = useState<boolean>(!!(s as any)?.fast_mode)
  const [think, setThink] = useState<boolean>(!!(s as any)?.thinking)
  const armed: string[] | null = ((s as any)?.armed_modes || (s?.launch_config as any)?.armed_modes) ?? null
  const shown = armed ? MODES.filter(m => armed.some(a => modeLabelOf(a) === m || a.toLowerCase() === m.toLowerCase())) : MODES
  const active = pick ?? current
  useEffect(() => { setPick(null) }, [s?.session_id])

  const pickMode = async (m: string) => {
    if (!live || !s) return
    setPick(m)
    const r = await api.setMode(s.session_id, MODE_VALUE[m] || m.toLowerCase())
    if (!r) { setPick(null); setRejected(m); setTimeout(() => setRejected(null), 1500); toast(`Mode ${m} rejected by the sidecar`) }
  }
  const toggleFast = async () => {
    if (!isOpus) return
    const next = !fast
    setFast(next)
    if (live && s) { const r = await api.setFast(s.session_id, next); if (!r) { setFast(!next); toast('Fast-mode endpoint unavailable') } }
  }
  const toggleThink = async () => {
    const next = !think
    setThink(next)
    if (live && s) { const r = await api.setThinking(s.session_id, next); if (!r) { setThink(!next); toast('Thinking endpoint unavailable') } }
  }
  return (
    <div>
      <label className="ro-label block mb-1.5">Mode</label>
      <div data-comp="segmented-control" className="seg mode-seg">
        {shown.map(m => (
          <button key={m} className={`${active === m ? 'active ' : ''}${m === 'Bypass' ? 'seg-danger' : ''}`}
            disabled={rejected === m}
            title={m === 'Bypass' ? 'Bypass permissions — dangerous' : undefined}
            onClick={() => pickMode(m)}>{m}</button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2 mt-2">
        <button data-comp="toggle-button" className={`think-tog tog-cell fast-tog${fast && isOpus ? ' on' : ''}${!isOpus ? ' gated' : ''}`}
          disabled={!isOpus} onClick={toggleFast}
          title={isOpus ? 'Opus fast mode (/fast) — faster responses, slightly lower quality' : 'Fast mode (/fast) is Opus-only — select Opus to enable'}>
          <Ic name="zap" /><span className="tt-lbl">Opus Fast-Mode {fast && isOpus ? 'On' : 'Off'}</span>
        </button>
        <button data-comp="toggle-button" className={`think-tog tog-cell${think ? ' on' : ''}`} onClick={toggleThink} title="Extended thinking for this agent">
          <Ic name="brain" /><span className="tt-lbl">Thinking Mode {think ? 'On' : 'Off'}</span>
        </button>
      </div>
    </div>
  )
}

function EffortSeg({ s, live }: { s?: Session | null; live: boolean }) {
  const [active, setActive] = useState<string>('Med')
  useEffect(() => { setActive((s as any)?.effort ? labelOfEffort((s as any).effort) : 'Med') }, [s?.session_id])
  const pick = async (m: string) => {
    const prev = active
    setActive(m)
    if (live && s) { const r = await api.setEffort(s.session_id, EFFORT_VALUE[m]); if (!r) { setActive(prev); toast(`Effort ${m} rejected by the sidecar`) } }
  }
  return (
    <div>
      <label className="ro-label block mb-1.5">Effort</label>
      <div data-comp="segmented-control" className="seg">
        {EFFORTS.map(m => <button key={m} className={active === m ? 'active' : ''} onClick={() => pick(m)}>{m}</button>)}
      </div>
    </div>
  )
}
function labelOfEffort(v: string): string {
  const e = Object.entries(EFFORT_VALUE).find(([, val]) => val === v.toLowerCase())
  return e ? e[0] : 'Med'
}

function Stepper({ label, value, onChange, min = 0, max, step = 5 }: { label: string; value: number; onChange: (n: number) => void; min?: number; max?: number; step?: number }) {
  const clamp = (n: number) => Math.min(max ?? Infinity, Math.max(min, n))
  return (
    <div>
      <span className="block text-[8.5px] text-muted font-bold uppercase tracking-wide mb-1">{label}</span>
      <div data-comp="stepper" className="stepper">
        <button onClick={() => onChange(clamp(value - step))}>−</button>
        <input type="number" value={value} min={min} max={max} step={step} onChange={e => onChange(clamp(parseInt(e.target.value || '0', 10)))} />
        <button onClick={() => onChange(clamp(value + step))}>+</button>
      </div>
    </div>
  )
}

// ---- Details tab ---------------------------------------------------------------
function DetailsTab({ s }: { s: Session }) {
  const d = useDash()
  const a = identOf(s)
  const state = runStateOf(s)
  const [ctxOpen, setCtxOpen] = useState(false)
  const [turnsOpen, setTurnsOpen] = useState(false)
  const [triMode, setTriMode] = useState<null | 'rewind' | 'handoff'>(null)
  const [subsOpen, setSubsOpen] = useState(false)
  const subsRef = useRef<HTMLDivElement>(null)
  const ctx = d.ctx
  const rawPct = Number.isFinite(ctx?.percent as number) ? (ctx!.percent as number) : (d.usageBy[s.session_id]?.percent ?? null)
  const ctxPct = rawPct != null && Number.isFinite(rawPct) ? Math.round(rawPct) : null
  const hasTok = Number.isFinite(ctx?.tokens as number) && Number.isFinite(ctx?.window as number)
  const turns = (Number.isFinite(ctx?.turns as number) ? ctx!.turns : s.total_turns) || 0
  const turnsPct = Math.min(100, Math.round((turns / DEFAULT_MAX_TURNS) * 100))
  const subs = d.subagentsBy[s.session_id] || []
  const isOpus = (s.model || '').toLowerCase().includes('opus')
  const lc = s.launch_config

  // subagent-badge jump: open + highlight the audit row
  const [flashSub, setFlashSub] = useState<string | null>(null)
  useEffect(() => {
    if (d.jump.target === 'subagents' && d.jump.agent === s.session_id) {
      setSubsOpen(true)
      setFlashSub(d.jump.type || null)
      setTimeout(() => subsRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 60)
      const t = setTimeout(() => setFlashSub(null), 1800)
      return () => clearTimeout(t)
    }
  }, [d.jump.seq])

  const onCtxToggle = () => { const next = !ctxOpen; setCtxOpen(next); if (next) d.refreshCtx() }
  const groups = groupSubs(subs)

  return (
    <div data-group="mid" className="p-3 space-y-3 flex flex-col min-h-full">
      <div data-comp="agent-panel-head" className="agent-head">
        <span data-comp="agent-tile" className="agtile" style={{ width: 'var(--size-40)', height: 'var(--size-40)', color: a.color }}><AgGlyph icon={a.icon} /></span>
        <div className="min-w-0 flex-1">
          <div className="text-[9px] text-muted font-bold uppercase tracking-wide truncate">{a.role}</div>
          <div className="text-[15px] font-heading text-foreground leading-tight truncate" style={{ fontWeight: 900 }}>{a.name}</div>
        </div>
        <div className="flex flex-col items-end justify-between flex-1 min-w-0 h-10">
          <button data-comp="status-badge" className={`node-badge ${NB_CLASS[state]} det-badge`} style={{ position: 'static' }}
            onClick={() => d.statusJump(state, s.session_id)}
            title={`${NB_LABEL[state]} — status shortcut`}>{NB_LABEL[state]}</button>
          <div className="text-[9px] font-mono text-muted-2 truncate max-w-full leading-none" title="Created · elapsed">{createdStamp(s.created_at, d.nowMs)}</div>
        </div>
      </div>

      <div className="grid grid-cols-[1fr_70px] gap-2">
        <div className="field">
          <div className="flex items-center justify-between mb-1"><label className="lbl">Role</label></div>
          <div data-comp="role-combobox" className="lockable combo" title="Role is set at create — a running agent's agent.md can't be reassigned">
            <div className="combo-trig"><input className="combo-in" value={a.role} readOnly /><button className="combo-cv" type="button"><Ic name="chevrons-up-down" /></button></div>
          </div>
        </div>
        <EditField label="No." value={a.name.split(' ')[0] || '01'} center
          onSave={async v => { const r = await api.updateIdentity(s.session_id, { number: parseInt(v, 10) || 1 }); if (!r) toast('Number rejected (already taken?)') }} />
      </div>

      <EditField label="Name" value={a.short}
        onSave={async v => { const r = await api.updateIdentity(s.session_id, { name: v.trim() }); if (!r) toast('Rename rejected') }} />

      <EditField label="Description" value={(s as any).description || ''} textarea disabled
        note="stored with the agent.md — not editable on a live session yet" />

      <LockField label="Skills" title="Create/launch-time config — view-only on a live session" noPencil>
        {() => <MSel kind="skills" sel={[]} disabled />}
      </LockField>
      <LockField label="Tools" title="Create/launch-time config — view-only on a live session" noPencil>
        {() => <MSel kind="tools" sel={lc.allowed_tools || []} disabled />}
      </LockField>
      <LockField label="MCP servers" note="none = all configured · applies at next launch" noPencil>
        {() => <MSel kind="mcp" sel={lc.mcp_servers || []} disabled />}
      </LockField>
      <LockField label="Plugins" note="none = all enabled · applies at next launch" noPencil>
        {() => <MSel kind="plugins" sel={lc.enabled_plugins ? Object.keys(lc.enabled_plugins).filter(k => lc.enabled_plugins![k]) : []} disabled />}
      </LockField>
      <LockField label="Deny rules" note="the reliable hard-block (allow-lists are ignored under bypass) · applies at next launch" noPencil>
        {() => <MSel kind="denyrules" sel={lc.disallowed_tools || []} disabled />}
      </LockField>

      <div className="field grid grid-cols-2 gap-3" style={{ ['--cur-color' as any]: a.color }}>
        <div>
          <div className="flex items-center justify-between mb-1.5"><label className="lbl">Color</label></div>
          <ColorPicker color={a.color} onPick={async hex => { const r = await api.updateIdentity(s.session_id, { color: hex }); if (!r) toast('Color update rejected') }} />
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5"><label className="lbl">Icon</label></div>
          <IconPicker icon={a.icon} color={a.color} onPick={async n => { const r = await api.updateIdentity(s.session_id, { icon: n }); if (!r) toast('Icon update rejected') }} />
        </div>
      </div>

      <div>
        <div className="ro-head"><span className="ro-label">Model</span><span className="ml-auto text-[9.5px] text-muted font-mono font-semibold">{modelLabel(s.model)}</span></div>
        <ModelTabs current={s.model} onPick={async f => {
          if (f === 'inherit') return
          const r = await api.setModel(s.session_id, f)
          if (!r) toast(`Model ${f} rejected by the sidecar`)
        }} />
      </div>

      <ModeBlock s={s} isOpus={isOpus} live />
      <EffortSeg s={s} live />

      <div>
        <div className="grid grid-cols-2 gap-2.5">
          <Stepper label="Max turns" value={(s as any).max_turns ?? DEFAULT_MAX_TURNS} onChange={() => toast('Live auto-stop edits land with the lifecycle endpoint')} />
          <Stepper label="Max Context %" value={(s as any).max_context_pct ?? CTX_CUTOFF} max={100} onChange={() => toast('Live auto-stop edits land with the lifecycle endpoint')} />
        </div>
      </div>

      {/* CONTEXT */}
      <div>
        <div className="ro-head">
          <span className="ro-label">Context</span>
          <button data-comp="text-button" className="link-act ml-2" onClick={() => { api.consoleRun(s.session_id, '/compact'); toast('/compact sent') }}>Compact</button>
          <span className="ml-auto text-[10px] font-bold text-muted font-mono">{hasTok ? `${fmtTokens(ctx!.tokens)} / ${fmtTokens(ctx!.window)}` : '—'}</span>
        </div>
        <button className={`ctx-trigger${ctxOpen ? ' open' : ''}`} type="button" onClick={onCtxToggle}>
          <div className="summary-row">
            <div data-comp="progress-bar" className="ctxbar">
              {ctxPct != null && <i style={{ width: `${Math.min(100, ctxPct)}%`, background: ctxColor(ctxPct) }} />}
              <span className="bar-cut" style={{ left: `${CTX_CUTOFF}%` }} />
            </div>
            <span className="text-[10px] font-bold text-muted font-mono">{ctxPct != null ? `${ctxPct}%` : '—'}</span>
            <Ic name="chevron-down" className={`chev${ctxOpen ? ' up' : ''}`} />
          </div>
        </button>
        <div data-comp="accordion" className="acc" style={{ display: ctxOpen ? 'block' : 'none' }}>
          <div data-comp="context-breakdown" className={`bd${d.ctxLoading ? ' is-loading' : ''}`}>
            <div className="bd-head"><h4 className="text-[10px] font-heading uppercase tracking-wide">Context</h4><span className="bd-tot">{hasTok ? `${fmtTokens(ctx!.tokens)} · ${ctxPct}%` : '—'}</span></div>
            {ctx && hasTok ? (
              <>
                <div className="cat"><span className="sw2" style={{ background: ctxColor(ctxPct || 0) }} /><span className="nm">Used context</span><span className="tk" style={{ marginLeft: 'auto' }}>{fmtTokens(ctx.tokens)}</span><span className="pc">{ctxPct}%</span></div>
                <div className="cat"><span className="sw2" style={{ background: 'var(--surface-3)' }} /><span className="nm">Free space</span><span className="tk" style={{ marginLeft: 'auto' }}>{fmtTokens(Math.max(0, ctx.window - ctx.tokens))}</span><span className="pc">{100 - (ctxPct || 0)}%</span></div>
                <div className="bd-sub"><h5>/ Model</h5><div className="ml"><span className="p">{ctx.model || s.model || 'inherit'}</span><span className="t">{fmtTokens(ctx.window)} window</span></div></div>
                <div className="text-[9px] text-muted-2 mt-2 font-semibold">per-category breakdown lands with the context-pull endpoint (§ backlog)</div>
              </>
            ) : <div className="awl-empty">no context reading yet</div>}
          </div>
        </div>
      </div>

      {/* TURNS */}
      <div className="flex flex-col">
        <div className="ro-head"><span className="ro-label">Turns</span><span className="ml-2 text-[10px] font-bold text-muted font-mono">{turns}/{DEFAULT_MAX_TURNS}</span></div>
        <button className={`ctx-trigger${turnsOpen ? ' open' : ''}`} type="button" onClick={() => setTurnsOpen(o => !o)}>
          <div className="summary-row">
            <div data-comp="progress-bar" className="ctxbar"><i style={{ width: `${turnsPct}%`, background: ctxColor(turnsPct) }} /></div>
            <span className="text-[10px] font-bold text-muted font-mono">{turnsPct}%</span>
            <Ic name="chevron-down" className={`chev${turnsOpen ? ' up' : ''}`} />
          </div>
        </button>
        <div data-comp="accordion" className="acc" style={{ display: turnsOpen ? 'block' : 'none' }}>
          <div className="bd">
            <div className="bd-head"><h4 className="text-[10px] font-heading uppercase tracking-wide">By tool</h4><span className="bd-tot">{ctx ? `${ctx.tool_total} calls` : '—'}</span></div>
            {ctx && Object.keys(ctx.tools || {}).length
              ? Object.entries(ctx.tools).sort((x, y) => y[1] - x[1]).map(([tool, n]) => (
                <div className="cat" key={tool}><span className="sw2" style={{ background: 'var(--secondary)' }} /><span className="nm">{tool}</span><span className="tk" style={{ marginLeft: 'auto' }}>{n}</span><span className="pc">{ctx.tool_total ? Math.round((n / ctx.tool_total) * 100) : 0}%</span></div>
              ))
              : <div className="awl-empty">no tool calls recorded yet</div>}
          </div>
        </div>

        <div className="sec-h mt-3">Timeline</div>
        <div data-comp="timeline-mode-switcher" className="tri-tabs">
          <button className={`tri-tab${triMode === 'rewind' ? ' active' : ''}`} onClick={() => setTriMode(m => m === 'rewind' ? null : 'rewind')}><Ic name="undo-2" />Rewind</button>
          <button className={`tri-tab${triMode === 'handoff' ? ' active' : ''}`} onClick={() => setTriMode(m => m === 'handoff' ? null : 'handoff')}><Ic name="git-branch" />Handoff</button>
        </div>
        {triMode && (
          <div data-comp="accordion" className="acc flex flex-col" style={{ display: 'flex', borderTop: 'var(--border-width) solid var(--border)', marginTop: 'var(--space-6)' }}>
            <div className="tl-phead">{triMode === 'handoff' ? 'Hand off from a point — starts a new agent seeded with context up to that turn' : "Rewind to a point — restores this agent's context to the end of that turn"}</div>
            <div data-comp="timeline" className="tl" style={{ minHeight: 120 }}>
              <div className="awl-empty">per-turn timeline pending the turn-capture backend (§11 #46){triMode === 'handoff' && <> — <button className="link-act" onClick={() => d.setAgentTab('create')}>open Create prefilled</button></>}</div>
            </div>
          </div>
        )}
      </div>

      {/* SUBAGENTS AUDIT */}
      <div data-comp="subagents-accordion" className={`subs-audit${subsOpen ? ' open' : ''}`} ref={subsRef}>
        <button className="subs-audit-head" type="button" aria-expanded={subsOpen} onClick={() => setSubsOpen(o => !o)}>
          <Ic name="chevron-right" className="sa-chev" /><span className="sa-title">Subagents</span>
          <span className="sa-count">{subs.length}</span><span className="sa-hint">read-only audit history</span>
        </button>
        <div className="subs-audit-body">
          {groups.map(g => (
            <div className="sa-run" key={g.run}>
              <div className="sa-run-h">Run {g.run} <span className="sa-run-n">· {g.rows.length} subagent{g.rows.length === 1 ? '' : 's'}</span></div>
              {g.rows.map(sub => (
                <div className={`sa-row${flashSub === sub.id ? ' reply-flash' : ''}`} data-sub={sub.id} key={sub.id}>
                  <div className="sa-row-top">
                    <span data-comp="subagent-badge" className={`sbadge ${sub.status === 'error' ? 'sb-error' : sub.status === 'done' ? 'sb-idle' : 'sb-active'}`}>{sub.id}</span>
                    <span className="sa-type">{sub.type || 'subagent'}</span>
                    <span className={`sa-status sa-st-${sub.status === 'done' ? 'done' : sub.status === 'error' ? 'error' : 'running'}`}>{sub.status}</span>
                    <button data-comp="ghost-icon-button" className="ghost-ic sa-tx" title={`Scope the Team Feed to ${sub.id}`} onClick={() => { d.setFeedTab('transcript'); d.gotoSubagent(s.session_id, sub.id) }}><Ic name="file-text" /></button>
                  </div>
                  {sub.description && <div className="sa-task">{sub.description}</div>}
                  {sub.usage && <div className="sa-usage">{usageBits(sub.usage).map((b, i, arr) => <React.Fragment key={i}><span>{b}</span>{i < arr.length - 1 && <span className="sep">·</span>}</React.Fragment>)}</div>}
                </div>
              ))}
            </div>
          ))}
          {!subs.length && <div className="awl-empty">no subagents this session</div>}
        </div>
      </div>
    </div>
  )
}

function groupSubs(subs: { id: string;[k: string]: any }[]): { run: string; rows: any[] }[] {
  const by: Record<string, any[]> = {}
  for (const s of subs) {
    const run = (s.id || '?')[0] || '?'
    ;(by[run] = by[run] || []).push(s)
  }
  return Object.keys(by).sort().map(run => ({ run, rows: by[run] }))
}
function usageBits(u: any): string[] {
  const bits: string[] = []
  if (u?.tokens != null) bits.push(`${fmtTokens(u.tokens)} tok`)
  if (u?.tool_calls != null) bits.push(`${u.tool_calls} tools`)
  if (u?.duration != null) bits.push(String(u.duration))
  if (u?.model) bits.push(modelLabel(u.model))
  return bits.length ? bits : []
}

// ---- Create tab -------------------------------------------------------------------
function CreateTab() {
  const d = useDash()
  const [role, setRole] = useState('agent')
  const [num, setNum] = useState('01')
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [tools, setTools] = useState<string[]>([])
  const [deny, setDeny] = useState<string[]>([])
  const [mcp, setMcp] = useState<string[]>([])
  const [plugins, setPlugins] = useState<string[]>([])
  const [color, setColor] = useState(JEWELS[11].hex)   // emerald
  const [icon, setIcon] = useState('wizard-face')
  const [model, setModel] = useState<string>('inherit')
  const [mode, setMode] = useState('Ask')
  const [armBypass, setArmBypass] = useState(false)    // #13 UI half — launch flags
  const [armAuto, setArmAuto] = useState(true)
  const [effort, setEffort] = useState('Med')
  const [maxTurns, setMaxTurns] = useState(40)
  const [maxCtx, setMaxCtx] = useState(75)
  const [busy, setBusy] = useState(false)

  const NAMES = ['kai', 'drew', 'rowan', 'vale', 'wren', 'sage', 'nova', 'ash', 'juno', 'remy', 'sol', 'bex', 'indi', 'koa']
  const randomize = () => setName(NAMES[Math.floor(Math.random() * NAMES.length)])

  const shownModes = armBypass ? MODES : MODES.filter(m => m !== 'Bypass')

  const create = async () => {
    setBusy(true)
    const payload: CreatePayload = {
      model: model === 'inherit' ? null : model,
      permission_mode: MODE_VALUE[mode] || 'default',
      cwd: d.projectCwd,
      identity: { role: role.trim() || 'agent', number: parseInt(num, 10) || undefined, name: name.trim() || undefined, color, icon },
      allowed_tools: tools.length ? tools : null,
      disallowed_tools: deny.length ? deny : null,
      max_turns: maxTurns, max_context_pct: maxCtx,
    }
    if (mcp.length) payload.mcp_servers = mcp
    if (plugins.length) payload.enabled_plugins = Object.fromEntries(plugins.map(p => [p, true]))
    const s = await api.create(payload)
    setBusy(false)
    if (s) { toast(`Created ${role} · ${s.identity?.name || name || s.session_id}`); d.select(s.session_id); d.setAgentTab('details') }
    else toast('Create failed — see the sidecar log')
  }

  return (
    <>
      <div className="pcard-body flex flex-col overflow-y-auto" style={{ background: 'var(--background)' }}>
      <div data-group="mid" className="p-3 space-y-3">
        <div className="grid grid-cols-[1fr_70px] gap-2">
          <div className="field editing">
            <label className="lbl block mb-1">Role</label>
            <div data-comp="role-combobox" className="combo">
              <div className="combo-trig"><input className="combo-in" value={role} placeholder="Select or type a role…" onChange={e => setRole(e.target.value)} /><button className="combo-cv" type="button" title="agent.md preset loading lands with the roles endpoint"><Ic name="chevrons-up-down" /></button></div>
            </div>
          </div>
          <div className="field editing">
            <label className="lbl block mb-1">No.</label>
            <input className="in text-center" value={num} placeholder="02" onChange={e => setNum(e.target.value)} />
          </div>
        </div>
        <div className="field editing">
          <label className="lbl block mb-1">Name</label>
          <div className="flex items-center gap-2">
            <input className="in flex-1" placeholder="auto-generated if blank" value={name} onChange={e => setName(e.target.value)} />
            <button data-comp="button" className="btn btn-sm shrink-0" title="Randomize name" onClick={randomize}><Ic name="dices" className="w-3.5 h-3.5" />Random</button>
          </div>
        </div>
        <div className="field editing">
          <label className="lbl block mb-1">Description</label>
          <textarea className="in autosize" rows={2} value={desc} onChange={e => setDesc(e.target.value)} />
        </div>
        <div className="field editing"><label className="lbl block mb-1">Skills</label><MSel kind="skills" sel={[]} onChange={() => toast('Skill scoping lands with the skills catalog endpoint')} /></div>
        <div className="field editing"><label className="lbl block mb-1">Tools</label><MSel kind="tools" sel={tools} onChange={setTools} /></div>
        <div className="field editing"><label className="lbl block mb-1">MCP servers</label><MSel kind="mcp" sel={mcp} onChange={setMcp} /></div>
        <div className="field editing"><label className="lbl block mb-1">Plugins</label><MSel kind="plugins" sel={plugins} onChange={setPlugins} /></div>
        <div className="field editing"><label className="lbl block mb-1">Deny rules</label><MSel kind="denyrules" sel={deny} onChange={setDeny} /></div>

        <div className="field editing grid grid-cols-2 gap-3" style={{ ['--cur-color' as any]: color }}>
          <div><label className="lbl block mb-1.5">Color</label><ColorPicker color={color} onPick={setColor} /></div>
          <div><label className="lbl block mb-1.5">Icon</label><IconPicker icon={icon} color={color} onPick={setIcon} /></div>
        </div>

        <div>
          <div className="ro-head"><span className="ro-label">Model</span></div>
          <ModelTabs current={model === 'inherit' ? null : model} onPick={setModel} />
        </div>

        <div>
          <label className="ro-label block mb-1.5">Mode</label>
          <div data-comp="segmented-control" className="seg mode-seg">
            {shownModes.map(m => (
              <button key={m} className={`${mode === m ? 'active ' : ''}${m === 'Bypass' ? 'seg-danger' : ''}`} onClick={() => setMode(m)}>{m}</button>
            ))}
          </div>
          {/* #13 UI half — the launch flags that ARM modes on the real CLI session */}
          <div className="grid grid-cols-2 gap-2 mt-2">
            <button data-comp="toggle-button" className={`think-tog tog-cell${armAuto ? ' on' : ''}`} onClick={() => setArmAuto(v => !v)} title="Arm Auto (accept-all) at launch so the mode can be switched live">
              <Ic name="shield" /><span className="tt-lbl">Arm Auto {armAuto ? 'On' : 'Off'}</span>
            </button>
            <button data-comp="toggle-button" className={`think-tog tog-cell${armBypass ? ' on' : ''}`} onClick={() => { setArmBypass(v => { if (v && mode === 'Bypass') setMode('Ask'); return !v }) }} title="Arm Bypass (--dangerously-skip-permissions) at launch — dangerous; un-armed, the Bypass segment stays hidden">
              <Ic name="zap" /><span className="tt-lbl">Arm Bypass {armBypass ? 'On' : 'Off'}</span>
            </button>
          </div>
        </div>

        <div>
          <label className="ro-label block mb-1.5">Effort</label>
          <div data-comp="segmented-control" className="seg">
            {EFFORTS.map(m => <button key={m} className={effort === m ? 'active' : ''} onClick={() => setEffort(m)}>{m}</button>)}
          </div>
        </div>

        <div>
          <div className="grid grid-cols-2 gap-2.5">
            <Stepper label="Max turns" value={maxTurns} onChange={setMaxTurns} />
            <Stepper label="Max Context %" value={maxCtx} max={100} onChange={setMaxCtx} />
          </div>
        </div>
      </div>
      </div>
      <CreateFooter busy={busy} onCreate={create} onReset={() => { setRole('agent'); setNum('01'); setName(''); setDesc(''); setTools([]); setDeny([]); setMcp([]); setPlugins([]) }} />
    </>
  )
}

function CreateFooter({ busy, onCreate, onReset }: { busy: boolean; onCreate: () => void; onReset: () => void }) {
  const d = useDash()
  return (
    <div className="pcard-foot px-2 py-2.5">
      <div className="grid grid-cols-[1fr_auto_auto] gap-2">
        <button data-comp="button" className="btn-main" disabled={busy} onClick={onCreate}>{busy ? 'Creating…' : 'Create agent'}</button>
        <button data-comp="button" className="btn px-3" onClick={onReset}>Reset</button>
        <button data-comp="button" className="btn px-3" onClick={() => d.setAgentTab('details')}>Cancel</button>
      </div>
    </div>
  )
}

// ---- Details footer (Save / Retire / Delete with inline confirms) --------------
function DetailsFooter({ s }: { s: Session }) {
  const d = useDash()
  const a = identOf(s)
  const [confirm, setConfirm] = useState<null | 'retire' | 'delete' | 'save'>(null)
  const [fname, setFname] = useState(`${a.role || 'agent'}.md`)
  const retire = async () => { setConfirm(null); const r = await api.retire(s.session_id); toast(r ? `Retired ${a.short}` : 'Retire failed') }
  const del = async () => { setConfirm(null); const r = await api.hardDelete(s.session_id); toast(r ? `Deleted ${a.short} — configuration + transcripts wiped` : 'Delete failed') }
  return (
    <div className="pcard-foot px-2 py-2.5">
      {confirm === null && (
        <div className="flex" style={{ gap: 'var(--space-8)' }}>
          <button data-comp="button" className="btn flex-1" title="Save this agent's current config as an agent.md" onClick={() => setConfirm('save')}><Ic name="save" className="w-3.5 h-3.5" />Save</button>
          <button data-comp="button" className="btn-danger flex-1" title="Retire this agent — ends the session" onClick={() => setConfirm('retire')}><Ic name="power" className="w-3.5 h-3.5" />Retire</button>
          <button data-comp="button" className="btn-danger-solid flex-1" title="Permanently delete this agent — configuration + transcripts (irreversible)" onClick={() => setConfirm('delete')}><Ic name="trash-2" className="w-3.5 h-3.5" />Delete</button>
        </div>
      )}
      {confirm === 'retire' && (
        <div data-comp="inline-confirm" className="tl-confirm foot-confirm" style={{ display: 'flex', width: '100%', alignItems: 'center', gap: 'var(--space-8)' }}>
          <span>Retire {a.role} · {a.name}? This ends the session.</span>
          <button className="btn btn-sm ml-auto" onClick={() => setConfirm(null)}>Cancel</button>
          <button className="btn-danger btn-sm" onClick={retire}><Ic name="power" className="w-3.5 h-3.5" />Retire</button>
        </div>
      )}
      {confirm === 'delete' && (
        <div data-comp="inline-confirm" className="tl-confirm foot-confirm foot-confirm--danger" style={{ display: 'flex', width: '100%', alignItems: 'center', gap: 'var(--space-8)' }}>
          <span>Permanently delete {a.role} · {a.name}? This wipes its configuration and transcripts — this can't be undone.</span>
          <button className="btn btn-sm ml-auto" onClick={() => setConfirm(null)}>Cancel</button>
          <button className="btn-danger-solid btn-sm" onClick={del}><Ic name="trash-2" className="w-3.5 h-3.5" />Delete</button>
        </div>
      )}
      {confirm === 'save' && (
        <div data-comp="inline-confirm" className="tl-confirm foot-confirm" style={{ display: 'flex', width: '100%', alignItems: 'center', gap: 'var(--space-6)', flexWrap: 'wrap' }}>
          <span style={{ flex: '0 0 auto' }}>Save config as</span>
          <input className="in" style={{ flex: '1 1 90px', minWidth: 70, height: 'var(--size-24)', padding: '0 var(--space-6)' }} value={fname} onChange={e => setFname(e.target.value)} autoFocus />
          <button className="btn-main btn-sm" onClick={() => { setConfirm(null); toast(`agent.md write pending the backend endpoint (${fname} → project)`) }}>Save to project</button>
          <button className="btn btn-sm" onClick={() => { setConfirm(null); toast(`agent.md write pending the backend endpoint (${fname} → ~/.claude/agents)`) }}>Save to system</button>
          <button className="btn btn-sm" onClick={() => setConfirm(null)}>Cancel</button>
        </div>
      )}
    </div>
  )
}

// ---- in-column Console tab -----------------------------------------------------
function ConsoleTab({ s }: { s: Session | null }) {
  const d = useDash()
  const con = useConsole(s?.session_id || null)
  const [catOpen, setCatOpen] = useState(false)
  const [filter, setFilter] = useState('')
  const [cmd, setCmd] = useState('')
  const a = s ? identOf(s) : null
  const doRun = () => { const v = cmd.trim(); if (!v) return; con.run(v); setCmd('') }
  return (
    <>
      <div className="pcard-body flex flex-col overflow-hidden" style={{ background: 'var(--background)' }}>
      <div data-group="mid" className="flex flex-col console-pane" style={{ flex: 1, minHeight: 0 }}>
        <div className="con-agentbar">
          {a && <span className="agtile" style={{ width: 'var(--size-24)', height: 'var(--size-24)', color: a.color }}><AgGlyph icon={a.icon} /></span>}
          <div className="min-w-0 flex-1 leading-tight">
            <div className="text-[8px] text-muted font-bold uppercase tracking-wide">{a?.role || '—'}</div>
            <div className="text-[11px] font-heading text-foreground" style={{ fontWeight: 900 }}>{a?.name || 'no agent'}</div>
          </div>
          <span className="con-live"><i className="con-dot" />{con.attachState === 'ws' ? 'raw feed' : 'catalog only'}</span>
          <button data-comp="button" className="btn btn-sm con-expand" title="Expand the Console to a step-into view" onClick={() => d.setConsoleExpanded(true)}><Ic name="maximize-2" className="w-3.5 h-3.5" />Expand</button>
        </div>
        <ConsoleFeed id="con-feed-col" con={con} />
        <div data-comp="command-palette" className={`con-catalog${catOpen ? ' open' : ''}`}>
          <div className="con-cat-head">
            <span className="con-cat-title">Commands</span>
            <div className="con-search"><Ic name="search" /><input placeholder="Filter commands…" value={filter} onChange={e => setFilter(e.target.value)} /></div>
            <button data-comp="ghost-icon-button" className="ghost-ic" title="Close" onClick={() => setCatOpen(false)}><Ic name="x" /></button>
          </div>
          <div className="con-cat-list">
            <CommandList catalog={con.catalog} filter={filter} onPick={c => { setCmd(c + ' '); setCatOpen(false) }} />
          </div>
        </div>
      </div>
      </div>
      <div className="pcard-foot px-2 py-2.5">
        <div data-comp="console-runbar" className="flex con-run">
          <button className={`con-cmds-btn${catOpen ? ' on' : ''}`} title="Browse all commands" onClick={() => setCatOpen(o => !o)}><Ic name="terminal" className="w-3.5 h-3.5" /><span>/</span></button>
          <input className="con-input" placeholder="Type a command, or / to browse…" value={cmd} onChange={e => setCmd(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') doRun() }} />
          <button data-comp="button" className="btn-main con-run-btn" onClick={doRun}>Run</button>
        </div>
      </div>
    </>
  )
}

// ---- the panel shell ---------------------------------------------------------------
export function AgentPanel() {
  const d = useDash()
  const s = d.sessions.find(x => x.session_id === d.selectedId) || null
  return (
    <section className="rz-panel" id="pAgent" style={{ flex: '0 0 25%', minWidth: 'var(--col-left-min)', maxWidth: 'var(--col-left-max)' }}>
      <div className="pcard-head">
        <h3>Agent</h3>
        <div data-comp="tab-bar" className="tabset">
          <button className={`tab-btn${d.agentTab === 'details' ? ' active' : ''}`} onClick={() => d.setAgentTab('details')}>Details</button>
          <button className={`tab-btn${d.agentTab === 'create' ? ' active' : ''}`} onClick={() => d.setAgentTab('create')}>Create</button>
          <button className={`tab-btn${d.agentTab === 'console' ? ' active' : ''}`} onClick={() => d.setAgentTab('console')}>Console</button>
        </div>
      </div>
      {d.agentTab === 'details' && (
        <>
          <div className="pcard-body flex flex-col overflow-y-auto" style={{ background: 'var(--background)' }}>
            {s ? <DetailsTab s={s} key={s.session_id} /> : <div className="awl-empty">No agent focused — select a card in the Team Graph, or create one.</div>}
          </div>
          {s && <DetailsFooter s={s} />}
        </>
      )}
      {d.agentTab === 'create' && <CreateTab />}
      {d.agentTab === 'console' && <ConsoleTab s={s} />}
    </section>
  )
}
