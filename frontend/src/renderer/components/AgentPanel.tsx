// ============================================================================
// Agent panel — Details · Create · Console (left column, mockup DOM).
// Live wiring: identity edits → POST /identity; model/mode/effort/fast/think →
// their endpoints (optimistic, reverting with an honest disabled flash on a
// rejected/absent endpoint); Retire/Delete → DELETE /sessions/{id}[?hard];
// Create → POST /sessions. Un-armed permission-mode segments hide when the
// session exposes its armed set (#13 UI half) — all five render otherwise.
// ============================================================================

import React, { useEffect, useRef, useState } from 'react'
import {
  api, type CreatePayload, type Session, type ContextBreakdown, type ResponsePreset,
  type PastAgent, type ArchiveRecord, type TimelineTurn, type TimelineResponse,
  type Identity, type RolePreset, type RolesResponse,
} from '../api'
import { useDash } from '../store'
import { Ic, AgGlyph, SPRITE_BY_FILE } from '../lib/icons'
import {
  identOf, runStateOf, ctxColor, createdStamp, modelLabel, jewelName, JEWELS,
  NB_CLASS, NB_LABEL, fmtTokens, MODE_VALUE, clockTime, timeAgo,
} from '../lib/identity'
import { toast } from '../lib/toast'
import { useConsole, ConsoleFeed, CommandList } from './Console'

const DEFAULT_MAX_TURNS = 50
const CTX_CUTOFF = 80

// ---- §7.11/#13 — launch-gated permission modes -------------------------------
// The sidecar now derives + persists each session's armed set (its
// `armed_modes` field — launch mode + the arm_bypass flag, exact for sessions
// created outside the renderer and across restarts): the Details ring renders
// exactly those segments. The client-side un-armed set below stays as the
// live-400 TEACHING BACKSTOP only — Auto's presence is account-eligibility-
// dependent, so a 400 "unreachable" read-back still drops a segment honestly.
const UNARMED_LIVE: Record<string, Set<string>> = {}
function markUnarmed(sid: string, label: string) {
  ;(UNARMED_LIVE[sid] = UNARMED_LIVE[sid] || new Set()).add(label)
}
// The `--permission-mode` launch spelling per UI label (`auto` is the Auto
// segment's canonical spelling — launch, live set-mode, and indicator agree).
const LAUNCH_MODE_VALUE: Record<string, string> = {
  Plan: 'plan', Ask: 'default', Edit: 'acceptEdits', Auto: 'auto', Bypass: 'bypassPermissions',
}

// ---- §7.19 Timeline — per-session client-side state that must survive a
// focus switch: the proven version gate. The rolled-back ranges are NOT client
// state anymore: the sidecar persists a typed rewind event to turns.jsonl on
// each successful rewind and replays the interleaved stream at the read
// surface, so GET /timeline itself carries per-row `rolled` + the merged
// `rolled_ranges` (same exclusive-`from` representation the arithmetic below
// uses) — the marking survives a reload. Rows inside a range are dimmed AND
// excluded from the k-from-last arithmetic, so a second rewind / a handoff
// after a rewind targets the real prompt stack, and turns appended AFTER a
// rewind (ordinals past every range) stay live and undimmed.
const TL_GATED: Record<string, string> = {}

// Nice labels for the /context per-category keys (§11 #30). Falls back to a
// humanized key for any category the backend adds later.
const CTX_CAT_LABEL: Record<string, string> = {
  system_prompt: 'System prompt', system_tools: 'System tools', mcp_tools: 'MCP tools',
  custom_agents: 'Custom agents', memory: 'Memory files', skills: 'Skills',
  messages: 'Messages', free_space: 'Free space', autocompact_buffer: 'Autocompact buffer',
}
const ctxCatLabel = (key: string): string =>
  CTX_CAT_LABEL[key] || key.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())

// ---- small shared atoms -----------------------------------------------------

function EditField({ label, value, onSave, textarea, center, disabled, note }: {
  label: string; value: string; onSave?: (v: string) => void; textarea?: boolean; center?: boolean; disabled?: boolean; note?: string
}) {
  const [editing, setEditing] = useState(false)
  const [v, setV] = useState(value)
  useEffect(() => { if (!editing) setV(value) }, [value, editing])
  const commit = () => { setEditing(false); if (onSave && v !== value) onSave(v) }
  return (
    <div className={`field${editing ? ' editing' : ''}`}>
      <div className="flex items-center justify-between mb-1">
        <label className="lbl">{label}</label>
        {onSave && !disabled && (
          <button className="edit-ic" onClick={() => (editing ? commit() : setEditing(true))}>
            <Ic name="square-pen" className="ic-pencil w-3.5 h-3.5" /><Ic name="check" className="ic-save w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {/* readOnly when not editing: the .lockable CSS only kills pointer events —
          without it the control stays Tab-reachable and locally typable, a lie
          when locked (no commit path). */}
      {textarea
        ? <textarea className="lockable in autosize" value={v} rows={3} readOnly={!editing} onChange={e => setV(e.target.value)} />
        : <input data-comp="text-input" className={`lockable in${center ? ' text-center' : ''}`} value={v} readOnly={!editing} onChange={e => setV(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') commit() }} />}
      {note && <div className="text-[10px] text-muted-2 mt-1 normal-case font-semibold">{note}</div>}
    </div>
  )
}

// Fully-locked text display for the Details identity fields (view-only from
// Role through Icon — config is create-time): EditField's non-editing render
// minus the pencil, with the input truly readOnly (no commit machinery at all).
function LockedText({ label, value, center, title, note }: {
  label: string; value: string; center?: boolean; title?: string; note?: string
}) {
  return (
    <div className="field" title={title}>
      <div className="flex items-center justify-between mb-1">
        <label className="lbl">{label}</label>
      </div>
      <input data-comp="text-input" className={`lockable in${center ? ' text-center' : ''}`} value={value} readOnly />
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
            <button key={n} className={`icotile${n === icon ? ' on' : ''}`} data-name={n} title={n}
              onClick={() => { onPick(n); setOpen(false) }}>
              {/* the .agtile wrap is load-bearing: `.icotile .agtile` carries the
                  26px tile size (a bare .ag-svg falls back to the browser's
                  300×150 svg default) and its currentColor drives the recolor —
                  mirrors the mockup's buildIconGrids (design/behavior.js). */}
              <span className="agtile" style={{ color }}><AgGlyph icon={n} /></span>
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
  const [, setUnarmedTick] = useState(0)   // re-render after an unreachable verdict drops a segment
  // §7.11/#13 — un-armed segments are ABSENT from the ring. The sidecar's
  // `armed_modes` (derived from the launch mode + arm_bypass, persisted on
  // the roster record) is the ring's source of truth — exact for sessions
  // created outside the renderer and across restarts. The client-known
  // un-armed set stays as the live-400 "unreachable" teaching backstop
  // (Auto's presence is account-eligibility-dependent).
  const armed: string[] | null = s?.armed_modes ?? null
  const unarmed = (s && UNARMED_LIVE[s.session_id]) || new Set<string>()
  const shown = (armed
    ? MODES.filter(m => armed.some(a => modeLabelOf(a) === m || a.toLowerCase() === m.toLowerCase()))
    : MODES).filter(m => !unarmed.has(m))
  const active = pick ?? current
  useEffect(() => { setPick(null) }, [s?.session_id])

  const pickMode = async (m: string) => {
    if (!live || !s) return
    setPick(m)
    // Honest states off the mode endpoint (§11 #12/#13): 409 busy (screen not
    // idle — retryable), 400 "unreachable" (the segment is launch-gated and
    // absent from the real ring — remove it here too), other 400s verbatim.
    const r = await api.setModeStatus(s.session_id, MODE_VALUE[m] || m.toLowerCase())
    if (r.ok) {
      const back = r.data?.mode
      if (back) setPick(modeLabelOf(back))   // render the READ-BACK mode, never the echo
      return
    }
    setPick(null)
    if (r.status === 409) {
      setRejected(m); setTimeout(() => setRejected(null), 1500)
      toast(`${m}: agent is busy — mode changes need an idle screen (retry at idle)`)
    } else if (r.status === 400 && /unreachable/i.test(r.detail || '')) {
      markUnarmed(s.session_id, m); setUnarmedTick(t => t + 1)
      toast(`${m} isn't armed on this agent — launch-gated (arm it at create); segment removed from the ring`)
    } else {
      setRejected(m); setTimeout(() => setRejected(null), 1500)
      toast(`Mode ${m} failed: ${r.detail || 'rejected by the sidecar'}`)
    }
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
  const [bd, setBd] = useState<ContextBreakdown | null>(null)
  const [bdLoading, setBdLoading] = useState(false)
  const [bdMsg, setBdMsg] = useState<string | null>(null)
  const [turnsOpen, setTurnsOpen] = useState(false)
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

  // Opening the accordion triggers BOTH the cheap JSONL floor (d.refreshCtx) and
  // the on-demand deep `/context` breakdown pull (§11 #30). The deep pull is
  // idle-gated + slow (a live TUI round-trip), so the floor rows show at once
  // while the breakdown shimmers in; a busy/absent agent keeps the floor honestly.
  const pullBreakdown = async () => {
    setBdLoading(true); setBdMsg(null)
    const r = await api.contextBreakdown(s.session_id)
    setBdLoading(false)
    if (r && r.rows?.length) { setBd(r) }
    else { setBd(null); setBdMsg(r ? 'no category rows parsed — showing the JSONL floor' : 'deep readout unavailable (agent busy, or the driver has none) — showing the JSONL floor') }
  }
  const onCtxToggle = () => { const next = !ctxOpen; setCtxOpen(next); if (next) { d.refreshCtx(); pullBreakdown() } }
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
        <LockedText label="No." value={a.name.split(' ')[0] || '01'} center
          title="Set at create — view-only on a live session" />
      </div>

      <LockedText label="Name" value={a.short}
        title="Set at create — view-only on a live session" />

      <EditField label="Description" value={(s as any).description || ''} textarea disabled
        note="stored with the agent.md — config is create-time, view-only on a live session" />

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

      {/* Color + Icon — locked displays (view-only from Role through Icon —
          identity is create-time): the pickers' closed-trigger look, but
          genuinely non-interactive markup — no button, no popover, no onClick
          (the pickers' `locked` prop only adds a class and does NOT gate the
          trigger click, so it is not relied on here). */}
      <div className="field grid grid-cols-2 gap-3" style={{ ['--cur-color' as any]: a.color }}>
        <div>
          <div className="flex items-center justify-between mb-1.5"><label className="lbl">Color</label></div>
          <div data-comp="color-picker" className="picker lockable" title="Set at create — view-only on a live session">
            <div className="picker-trig">
              <span className="picker-sw" style={{ background: a.color }} /><span className="picker-val">{jewelName(a.color)}</span>
            </div>
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5"><label className="lbl">Icon</label></div>
          <div data-comp="icon-picker" className="picker lockable" title="Set at create — view-only on a live session">
            <div className="picker-trig">
              <span className="agtile picker-ico" style={{ color: a.color }}><AgGlyph icon={a.icon} /></span>
              <span className="picker-val">{a.icon || '—'}</span>
            </div>
          </div>
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
          <div data-comp="context-breakdown" className={`bd${bdLoading ? ' is-loading' : ''}`}>
            <div className="bd-head">
              <h4 className="text-[10px] font-heading uppercase tracking-wide">Context</h4>
              <button data-comp="text-button" className="link-act" style={{ marginLeft: 'auto', marginRight: 'var(--space-6)' }} onClick={pullBreakdown} title="Re-pull the deep /context breakdown (idle-gated)">{bdLoading ? 'Reading…' : 'Refresh'}</button>
              <span className="bd-tot">{hasTok ? `${fmtTokens(ctx!.tokens)} · ${ctxPct}%` : '—'}</span>
            </div>
            {bd && bd.rows.length ? (
              <div className="bd-rows">
                {bd.rows.map(r => (
                  <div className="cat" key={r.key}>
                    <span className="sw2" style={{ background: r.key === 'free_space' ? 'var(--surface-3)' : 'var(--secondary)' }} />
                    <span className="nm">{ctxCatLabel(r.key)}</span>
                    <span className="tk" style={{ marginLeft: 'auto' }}>{fmtTokens(r.tokens)}</span>
                    <span className="pc">{Math.round(r.percent)}%</span>
                  </div>
                ))}
                <div className="bd-sub"><h5>/ Model</h5><div className="ml"><span className="p">{ctx?.model || s.model || 'inherit'}</span><span className="t">{hasTok ? `${fmtTokens(ctx!.window)} window` : ''}</span></div></div>
                {bd.compact_history && bd.compact_history.count > 0 && (
                  <div className="bd-sub"><h5>Compactions</h5><div className="ml"><span className="p">{bd.compact_history.count} compaction{bd.compact_history.count === 1 ? '' : 's'}</span></div></div>
                )}
              </div>
            ) : ctx && hasTok ? (
              <div className="bd-rows">
                <div className="cat"><span className="sw2" style={{ background: ctxColor(ctxPct || 0) }} /><span className="nm">Used context</span><span className="tk" style={{ marginLeft: 'auto' }}>{fmtTokens(ctx.tokens)}</span><span className="pc">{ctxPct}%</span></div>
                <div className="cat"><span className="sw2" style={{ background: 'var(--surface-3)' }} /><span className="nm">Free space</span><span className="tk" style={{ marginLeft: 'auto' }}>{fmtTokens(Math.max(0, ctx.window - ctx.tokens))}</span><span className="pc">{100 - (ctxPct || 0)}%</span></div>
                <div className="bd-sub"><h5>/ Model</h5><div className="ml"><span className="p">{ctx.model || s.model || 'inherit'}</span><span className="t">{fmtTokens(ctx.window)} window</span></div></div>
                <div className="text-[9px] text-muted-2 mt-2 font-semibold">{bdLoading ? 'reading the deep /context breakdown…' : (bdMsg || 'the per-category breakdown pulls on open')}</div>
              </div>
            ) : <div className="awl-empty">{bdLoading ? 'reading context…' : 'no context reading yet'}</div>}
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

        <TimelineSection s={s} />
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

// ---- Timeline — the standing per-turn log + Rewind/Handoff (§7.19, #50) ----------
// One row per DASHBOARD-INITIATED turn from GET /sessions/{id}/timeline (§11 #46):
// record ordinal · "now" pill on the head row · the settings chips (unknown
// fields honestly omitted; the rendered settings string rides the tooltip) ·
// right-aligned time · the one-line summary (a missing one reads a muted "—").
// The Rewind|Handoff switcher ARMS row clicks; Rewind addresses k-FROM-LAST
// over the records (no prompt-checkpoint anchor exists — the confirm says so),
// Handoff forks via POST /sessions/{id}/fork (+ the #16 handoff-report switch,
// the file-state note read honestly off the response's `filestate`). Edge
// states render off the REAL responses: 409 → busy · 400 version → gated ·
// no rows → empty · post-rewind → rolled rows dimmed off the server-replayed
// `rolled_ranges` (marked, never truncated — the record is append-only).
function tlChip({ icon, title, val }: { icon: string; title: string; val: string }) {
  return <span className="node-chip" title={title}><Ic name={icon} />{val}</span>
}

function TimelineSection({ s }: { s: Session }) {
  const d = useDash()
  const a = identOf(s)
  const sid = s.session_id
  const [tl, setTl] = useState<TimelineResponse | null>(null)
  const [triMode, setTriMode] = useState<null | 'rewind' | 'handoff'>(null)
  const [confirm, setConfirm] = useState<{ mode: 'rewind' | 'handoff'; n: number } | null>(null)
  const [handoffReport, setHandoffReport] = useState(true)
  const [acting, setActing] = useState(false)
  const [busy409, setBusy409] = useState(false)
  const [, setTick] = useState(0)   // re-render after TL_GATED updates
  const running = runStateOf(s) === 'active'
  const gated = TL_GATED[sid] || null
  // Server-replayed rolled truth (persisted rewind events — survives a reload);
  // the anchor note names the last rewind's still-live target: the top merged
  // range's exclusive `from`.
  const ranges = tl?.rolled_ranges || []
  const anchor = ranges.length ? ranges[ranges.length - 1].from : null
  // A full-depth (clamped) rewind's still-live target is ordinal 0 — read it
  // as "the beginning", never a nonexistent "Turn 0".
  const anchorLabel = anchor == null ? 'the end of Turn n' : anchor === 0 ? 'the beginning' : `the end of Turn ${anchor}`
  // Rolled-row + live-position arithmetic over the append-only record: a row
  // inside a rolled range no longer exists in the live conversation; livePos
  // maps a LIVE ordinal to its position in the real prompt stack.
  const rolledOf = (t: number) => ranges.some(r => t > r.from && t <= r.to)
  const livePos = (t: number) => t - ranges.reduce((acc, r) => acc + (r.to <= t ? r.to - r.from : 0), 0)

  // Every timeline fetch (the 5s poll AND doRewind's refetch) takes a seq off
  // this ref and only the newest issued fetch may land in state — a slow poll
  // response resolving AFTER the post-rewind refetch would otherwise clobber
  // the fresh server-replayed rolled truth with stale (un-rolled) state.
  const tlSeq = useRef(0)
  const pullTl = async () => {
    const seq = ++tlSeq.current
    const r = await api.timeline(sid)
    if (r && seq === tlSeq.current) setTl(r)
  }

  // Own light poll (5s, in-flight-guarded) — never bundled into the roster poll.
  useEffect(() => {
    let cancelled = false
    let inflight = false
    const pull = async () => {
      if (cancelled || inflight) return
      inflight = true
      try { await pullTl() } finally { inflight = false }
    }
    pull()
    const i = setInterval(pull, 5000)
    return () => { cancelled = true; clearInterval(i) }
  }, [sid])

  const turns = tl?.turns || []
  const liveTurns = turns.filter(t => !rolledOf(t.turn))
  const liveHead = liveTurns.length ? liveTurns[liveTurns.length - 1].turn : 0   // newest LIVE ordinal
  // k-from-last over the LIVE prompt stack (rolled rows excluded) — the record
  // is append-only, so raw ordinal subtraction overshoots after any rewind.
  const kFor = (n: number) => livePos(liveHead) - livePos(n)
  const state = !turns.length ? 'empty' : (running || busy409) ? 'busy' : gated ? 'gated' : null
  const clsState = [
    !turns.length ? 'tl--empty' : '',
    (running || busy409) ? 'tl--busy' : '',
    gated ? 'tl--gated' : '',
    anchor != null ? 'tl--no-anchor' : '',
    triMode ? `tl--armed tl--${triMode}` : '',
  ].filter(Boolean).join(' ')

  const arm = (m: 'rewind' | 'handoff') => {
    if (gated) return   // the gated switcher is inert — the note carries the reason
    setConfirm(null)
    setTriMode(prev => (prev === m ? null : m))
  }
  const rowTitle = (t: TimelineTurn): string => {
    if (rolledOf(t.turn)) return 'Rolled back — this turn is no longer part of the live conversation and can’t be targeted'
    if (!triMode) return 'Arm Rewind or Handoff above to act from this turn'
    if (triMode === 'rewind') return t.turn === liveHead ? 'Already the head — rewinding here is a no-op' : 'Rewind to the end of this turn'
    return t.turn === liveHead ? 'Hand off from here (fork at head)' : 'Hand off from the end of this turn'
  }
  const pickRow = (n: number) => {
    if (!triMode || state === 'busy' || state === 'gated' || state === 'empty') return
    if (rolledOf(n)) return                              // rolled rows are not valid targets
    if (triMode === 'rewind' && n === liveHead) return   // the live head is not a rewind target
    setHandoffReport(true)
    setConfirm({ mode: triMode, n })
  }

  const failHonestly = (rr: { status: number; detail: string | null }, op: string) => {
    if (rr.status === 409) {
      setBusy409(true)
      setTimeout(() => setBusy409(false), 4000)
      toast(`${op} refused — ${rr.detail || 'busy: agent is not idle'}`)
    } else if (rr.status === 400) {
      // The version gate (< 2.1.191) and capability absences render as the
      // standing gated note, carrying the endpoint's own words.
      TL_GATED[sid] = rr.detail || `${op} unavailable on this agent`
      setTick(t => t + 1)
      setTriMode(null)
      toast(rr.detail || `${op} unavailable`)
    } else {
      toast(`${op} failed: ${rr.detail || 'sidecar error'}`)
    }
  }

  const doRewind = async (n: number) => {
    const k = kFor(n)
    setActing(true)
    const rr = await api.rewind(sid, k)
    setActing(false)
    setConfirm(null)
    if (rr.ok) {
      setTriMode(null)
      toast(`Rewound ${a.short} to the end of Turn ${n} — rolled back ${k} prompt${k === 1 ? '' : 's'}`)
      // The refetch carries the server-replayed rolled truth — the sidecar
      // persisted a rewind event to turns.jsonl, so no client-side range merge
      // (and the seq guard keeps a slower in-flight poll from clobbering it).
      await pullTl()
    } else failHonestly(rr, 'rewind')
  }

  const doHandoff = async (n: number) => {
    const k = kFor(n)
    setActing(true)
    const rr = await api.fork(sid, { to_prompt_index: k > 0 ? k : null, handoff: handoffReport })
    setActing(false)
    setConfirm(null)
    if (rr.ok && rr.data) {
      setTriMode(null)
      const fs = rr.data.filestate
      const fsNote = fs?.note || (fs?.isolated ? 'fork isolated in its own git worktree' : 'file-state shared with the source')
      const ho = rr.data.handoff
      const hoNote = handoffReport ? (ho?.error ? ` · handoff report failed: ${ho.error}` : ho?.filename ? ` · handoff report filed: ${ho.filename}` : '') : ''
      // A fork's backend-assigned identity can carry an empty name today —
      // never print a dangling "role · " separator; fall back to the id.
      const newIdent = rr.data.identity
      const identLabel = newIdent && (newIdent.name || newIdent.role)
        ? [newIdent.role, newIdent.name].filter(Boolean).join(' · ')
        : rr.data.session_id
      toast(`Handed off from Turn ${n} → ${identLabel} — ${fsNote}${hoNote}`)
      d.select(rr.data.session_id)
      d.setAgentTab('details')
    } else failHonestly(rr, 'fork')
  }

  return (
    <>
      <div className="sec-h mt-3">Timeline</div>
      <div data-comp="timeline-mode-switcher" className={`tri-tabs${gated ? ' tri-tabs--gated' : ''}`}
        title={gated ? gated : ''}>
        <button className={`tri-tab${triMode === 'rewind' ? ' active' : ''}`} onClick={() => arm('rewind')}><Ic name="undo-2" />Rewind</button>
        <button className={`tri-tab${triMode === 'handoff' ? ' active' : ''}`} onClick={() => arm('handoff')}><Ic name="git-branch" />Handoff</button>
      </div>
      <div className="tl-wrap flex flex-col">
        {triMode && (
          <div className="tl-phead">
            {triMode === 'handoff'
              ? 'Hand off from a point — branches a NEW agent seeded with context through that turn'
              : 'Rewind to a point — restores this agent’s conversation to the end of that turn'}
          </div>
        )}
        {confirm && confirm.mode === 'rewind' && (
          <div data-comp="inline-confirm" className="tl-confirm tl-confirm--stack foot-confirm--danger" style={{ display: 'flex' }}>
            <div className="tlc-row"><span>Rewind {a.short} to the end of Turn {confirm.n}? The {kFor(confirm.n) === 1 ? 'turn' : `${kFor(confirm.n)} turns`} after it {kFor(confirm.n) === 1 ? 'is' : 'are'} discarded.</span></div>
            <div className="tlc-note">Addressed as {kFor(confirm.n)} back from the latest live turn — dashboard-initiated turns only. Turns driven from a raw terminal are invisible to this record, so the real target can sit that many prompts off if this agent was also driven outside the dashboard.</div>
            <div className="tlc-row">
              <button className="btn btn-sm ml-auto" onClick={() => setConfirm(null)}>Cancel</button>
              <button className="btn-danger btn-sm" disabled={acting} onClick={() => doRewind(confirm.n)}><Ic name="undo-2" className="w-3.5 h-3.5" />{acting ? 'Rewinding…' : 'Rewind'}</button>
            </div>
          </div>
        )}
        {confirm && confirm.mode === 'handoff' && (
          <div data-comp="inline-confirm" className="tl-confirm tl-confirm--stack" style={{ display: 'flex' }}>
            <div className="tlc-row"><span>Hand off a new agent seeded through Turn {confirm.n}{confirm.n === liveHead ? ' (the head)' : ''}?</span></div>
            <div className="tlc-row tlc-opt">
              <span className="tlc-optlab">With handoff report</span>
              <span className="tlc-optnote">files a short summary of the source&#8217;s recent work to the Library and hands it to the new agent</span>
              <button data-comp="switch" className={`swh${handoffReport ? ' on' : ''}`}
                title={handoffReport ? 'On — a handoff report is generated and filed' : 'Off — plain context carry-over only'}
                onClick={() => setHandoffReport(o => !o)} />
            </div>
            <div className="tlc-note">File state: when {s.cwd || 'the working folder'} is a git repo the fork gets its own git worktree (its file changes stay isolated from {a.short}&#8217;s); otherwise it shares the folder — concurrent edits can collide. The confirm toast reports which case actually applied.</div>
            <div className="tlc-row">
              <button className="btn btn-sm ml-auto" onClick={() => setConfirm(null)}>Cancel</button>
              <button className="btn-main btn-sm" disabled={acting} onClick={() => doHandoff(confirm.n)}><Ic name="git-branch" className="w-3.5 h-3.5" />{acting ? 'Forking…' : 'Hand off'}</button>
            </div>
          </div>
        )}
        <div data-comp="timeline" className={`tl ${clsState}`}>
          {/* the four state notes are emitted hidden; the .tl root's state class shows the matching one (styles.css) */}
          <div className="tl-note tl-note--fresh"><Ic name="clock" /><span>No turns yet — a row lands here as each dashboard-initiated turn completes.</span></div>
          <div className="tl-note tl-note--running"><Ic name="clock" /><span>{a.short} is mid-run — Rewind &amp; Handoff need an idle agent. The log stays readable; the actions return when the run completes.</span></div>
          <div className="tl-note tl-note--version"><Ic name="shield" /><span>{gated || 'Rewind & Handoff need Claude Code ≥ 2.1.191 — relaunch this agent on a newer CLI to enable both.'}</span></div>
          <div className="tl-note tl-note--anchor"><Ic name="triangle-alert" /><span>Rewound to {anchorLabel} — the record is append-only, so the rolled-back rows stay in the log (dimmed; the rewind is recorded, so this marking survives a reload) and new turns will append after them.</span></div>
          {turns.map(t => {
            const rolled = rolledOf(t.turn)
            const cur = t.turn === liveHead
            return (
              <div key={t.turn} data-comp="timeline-row"
                className={`tl-row${cur ? ' current' : ''}${rolled ? ' tl-row--rolled' : ''}`}
                role="button" tabIndex={0} title={t.settings ? `${rowTitle(t)} — ${t.settings}` : rowTitle(t)}
                onClick={() => pickRow(t.turn)}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pickRow(t.turn) } }}>
                <div className="tl-main">
                  <div className="tl-top">
                    <span className="tl-turn">{t.turn}</span>
                    {cur && <span className="tl-now">now</span>}
                    {rolled && <span className="tl-rolltag">rolled back</span>}
                    <span className="tl-set" title={t.settings || ''}>
                      {modelLabel(t.model)}
                      {t.mode ? tlChip({ icon: 'shield', title: 'Permission mode', val: t.mode }) : null}
                      {t.effort ? tlChip({ icon: 'gauge', title: 'Reasoning effort', val: t.effort }) : null}
                      {t.thinking != null ? tlChip({ icon: 'brain', title: 'Extended thinking', val: t.thinking ? 'on' : 'off' }) : null}
                    </span>
                    <span className="tl-time">{clockTime(t.timestamp)}</span>
                  </div>
                  {t.summary
                    ? <div className="tl-desc">{t.summary}</div>
                    : <div className="tl-desc tl-desc--none">— no summary recorded</div>}
                </div>
              </div>
            )
          })}
          <div className="tl-foot">Dashboard-initiated turns only — turns driven from a raw terminal aren&#8217;t recorded and can&#8217;t be targeted.</div>
        </div>
      </div>
    </>
  )
}

// ---- Create tab -------------------------------------------------------------------
function CreateTab() {
  const d = useDash()
  const [role, setRole] = useState('agent')
  // No. defaults to '' = AUTO: the server's auto-numbering applies the retired-
  // numbers skip set only when no explicit number is sent, so the UI must not
  // volunteer one (the old '01' default made every UI create claim #1, even
  // when 1 was retired). An explicit typed number is still honored verbatim.
  const [num, setNum] = useState('')
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [tools, setTools] = useState<string[]>([])
  const [deny, setDeny] = useState<string[]>([])
  const [mcp, setMcp] = useState<string[]>([])
  const [plugins, setPlugins] = useState<string[]>([])
  const [color, setColor] = useState(JEWELS[11].hex)   // emerald
  const [icon, setIcon] = useState('wizard-face')
  const [model, setModel] = useState<string>('inherit')
  const [mode, setMode] = useState('Bypass')
  // #13 — Launch permissions (operator decision 2026-07-17): Bypass is the
  // DEFAULT launch mode and its arming is prepopulated ON — supersedes the
  // earlier "Create ALWAYS starts un-armed, never prepopulated" stance.
  // Disarming (or picking a tamer mode) stays an explicit per-create act;
  // Auto still starts un-armed. Launching IN Bypass arms it implicitly, so
  // the payload's `arm_bypass` flag stays reserved for arm-without-activate.
  const [armBypass, setArmBypass] = useState(true)
  const [armAuto, setArmAuto] = useState(false)
  const [effort, setEffort] = useState('Med')
  const [maxTurns, setMaxTurns] = useState(40)
  const [maxCtx, setMaxCtx] = useState(75)
  const [respPreset, setRespPreset] = useState('default')
  const [presets, setPresets] = useState<ResponsePreset[]>([])
  const [busy, setBusy] = useState(false)

  // Response-format preset catalog (§11 #39) — the create-time choice is applied
  // immediately at launch (append-system-prompt), unlike a live edit.
  useEffect(() => { api.responsePresets().then(c => { if (c) setPresets(c.presets) }) }, [])

  // #40 — draw an unused name from the shipped pool; the sidecar already excludes
  // every live agent's name, so we only pass the staged name (so a re-roll differs).
  // Falls back to a tiny local pool when the sidecar is unreachable.
  const FALLBACK_NAMES = ['kai', 'drew', 'rowan', 'vale', 'wren', 'sage', 'nova', 'ash', 'juno', 'remy', 'sol', 'bex', 'indi', 'koa']
  const randomize = async () => {
    const r = await api.randomName(name.trim() ? [name.trim()] : [])
    if (r && r.name) setName(r.name)
    else setName(FALLBACK_NAMES[Math.floor(Math.random() * FALLBACK_NAMES.length)])
  }

  // ND 12 — the Role combobox IS the agent.md preset loader: the chevron opens
  // a System/Project grouped popup off GET /roles (fetched lazily on open,
  // cached; a reopen refreshes it cheaply); free-typing the input stays as-is.
  const [roleOpen, setRoleOpen] = useState(false)
  const [rolesCat, setRolesCat] = useState<RolesResponse | null>(null)
  // Honest failure state for the preset fetch: without it a failed GET /roles
  // leaves the "reading agent.md presets…" row up forever. Cleared on each
  // open, so reopening retries.
  const [rolesErr, setRolesErr] = useState(false)
  const comboRef = useRef<HTMLDivElement>(null)
  const toggleRoles = () => {
    setRoleOpen(o => !o)
    if (!roleOpen) {
      setRolesErr(false)
      api.roles(d.projectCwd).then(r => { if (r) setRolesCat(r); else setRolesErr(true) })
    }
  }
  useEffect(() => {
    if (!roleOpen) return
    const onDown = (e: MouseEvent) => { if (comboRef.current && !comboRef.current.contains(e.target as Node)) setRoleOpen(false) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setRoleOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [roleOpen])
  // Picking a preset prefills the Create state from the file's front matter.
  // Icon is NEVER prefilled — the icon is the per-agent differentiator, not a
  // front-matter field. Skills: the Create Skills MSel is still a stub, so the
  // skills prefill lands with the skills catalog endpoint.
  const pickRole = (r: RolePreset) => {
    setRoleOpen(false)
    setRole(r.name)
    setDesc(r.description || '')
    if (r.color_hex) setColor(r.color_hex)
    // Accept exactly the families the Create ModelTabs offers (incl. 'inherit');
    // unknown values / full model IDs still skip — the segment can't show them.
    if (r.model && (MODEL_FAMILIES as readonly string[]).includes(r.model)) setModel(r.model)
    if (r.tools?.length) setTools(r.tools)
    if (r.max_turns) setMaxTurns(r.max_turns)
    if (r.effort) {
      const e = r.effort.toLowerCase()
      const label = e === 'med' ? 'Med' : Object.entries(EFFORT_VALUE).find(([, v]) => v === e)?.[0]
      if (label) setEffort(label)   // only values the Effort segment actually has
    }
    if (r.permission_mode) {
      const label = Object.entries(LAUNCH_MODE_VALUE).find(([, v]) => v === r.permission_mode)?.[0]
      // Only armed-reachable segments: an un-armed Auto/Bypass label would
      // select a segment `shownModes` hides — skip the prefill instead.
      if (label && (label !== 'Bypass' || armBypass) && (label !== 'Auto' || armAuto)) setMode(label)
    }
  }

  // The Create ring never shows a segment that would silently no-op: Auto and
  // Bypass render only once ARMED (mirrors armToggle in design/behavior.js).
  const shownModes = MODES.filter(m => (m !== 'Bypass' || armBypass) && (m !== 'Auto' || armAuto))
  // Disarming a mode that was the active pick falls the selection back to Edit.
  const toggleArm = (which: 'auto' | 'bypass') => {
    if (which === 'auto') setArmAuto(v => { if (v && mode === 'Auto') setMode('Edit'); return !v })
    else setArmBypass(v => { if (v && mode === 'Bypass') setMode('Edit'); return !v })
  }

  const create = async () => {
    setBusy(true)
    const payload: CreatePayload = {
      model: model === 'inherit' ? null : model,
      // Arming (§7.11/#13): launching IN a mode arms it (`--permission-mode`);
      // the Bypass switch additionally maps to the backend's arm-without-
      // activate flag (`arm_bypass` → --allow-dangerously-skip-permissions)
      // when Bypass is armed but not the launch pick — Bypass joins the ring
      // without the agent starting in it.
      permission_mode: LAUNCH_MODE_VALUE[mode] || 'default',
      cwd: d.projectCwd,
      identity: { role: role.trim() || 'agent', number: num.trim() ? parseInt(num, 10) || undefined : undefined, name: name.trim() || undefined, color, icon },
      allowed_tools: tools.length ? tools : null,
      disallowed_tools: deny.length ? deny : null,
      max_turns: maxTurns, max_context_pct: maxCtx,
    }
    if (armBypass && mode !== 'Bypass') payload.arm_bypass = true
    if (mcp.length) payload.mcp_servers = mcp
    if (plugins.length) payload.enabled_plugins = Object.fromEntries(plugins.map(p => [p, true]))
    if (respPreset && respPreset !== 'default') payload.response_preset = respPreset
    const s = await api.create(payload)
    setBusy(false)
    if (s) {
      // The Details ring seeds from the session's server-derived `armed_modes`
      // (§7.11) — no client-side seeding needed; the live 400 "unreachable"
      // stays the account-dependence backstop (Auto).
      toast(`Created ${role} · ${s.identity?.name || name || s.session_id}`)
      d.select(s.session_id)
      d.setAgentTab('details')
    } else toast('Create failed — see the sidecar log')
  }

  return (
    <>
      <div className="pcard-body flex flex-col overflow-y-auto" style={{ background: 'var(--background)' }}>
      <div data-group="mid" className="p-3 space-y-3">
        <div className="grid grid-cols-[1fr_70px] gap-2">
          <div className="field editing">
            <label className="lbl block mb-1">Role</label>
            <div data-comp="role-combobox" className="combo" ref={comboRef}>
              <div className="combo-trig"><input className="combo-in" value={role} placeholder="Select or type a role…" onChange={e => setRole(e.target.value)} /><button className="combo-cv" type="button" title="Load an agent.md preset (System / Project)" onClick={toggleRoles}><Ic name="chevrons-up-down" /></button></div>
              <div className={`combo-pop${roleOpen ? ' open' : ''}`}>
                {rolesCat
                  ? [rolesCat.system, rolesCat.project].map(g => (
                    <React.Fragment key={g.label}>
                      <div className="combo-gh">{g.label}</div>
                      {g.roles.map(r => (
                        <button type="button" key={`${g.label}:${r.name}`} className="combo-opt" data-name={r.name} onClick={() => pickRole(r)}>
                          <b>{r.name}</b><span className="sub">{r.description || ''}</span>
                        </button>
                      ))}
                      {!g.roles.length && <div className="combo-opt" style={{ cursor: 'default' }}><span className="sub">no agent.md files in this scope</span></div>}
                    </React.Fragment>
                  ))
                  : rolesErr
                    ? <div className="combo-gh">couldn't load presets — sidecar unreachable</div>
                    : <div className="combo-gh">reading agent.md presets…</div>}
              </div>
            </div>
          </div>
          <div className="field editing">
            <label className="lbl block mb-1">No.</label>
            <input className="in text-center" value={num} placeholder="auto" onChange={e => setNum(e.target.value)} />
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
        </div>

        {/* LAUNCH PERMISSIONS — Bypass/Auto pre-arming (#13, §7.11): an un-armed
            mode is silently ABSENT from the ring above (never a greyed no-op);
            arming can't be granted mid-run — relaunch to change it. */}
        <div>
          <label className="ro-label block mb-1.5" title="Auto and Bypass must be pre-armed at launch. An un-armed mode is silently absent from the agent's mode ring — not a greyed no-op — and arming can't be granted mid-run: relaunch to change it. The ring above hides its Auto/Bypass segments until armed here.">Launch permissions</label>
          <div data-comp="launch-arm" className="arm-box">
            <div className="arm-row">
              <span className="arm-lab">Arm Auto</span>
              <span className="arm-note">adds Auto to the mode ring at launch</span>
              <button data-comp="switch" className={`swh${armAuto ? ' on' : ''}`} onClick={() => toggleArm('auto')}
                title={armAuto ? 'Armed — Auto joins the mode ring at launch' : 'Un-armed — Auto is absent from the mode ring'} />
            </div>
            <div className="arm-row arm-row--danger">
              <span className="arm-lab">Arm Bypass</span>
              <span className="arm-note">skips approvals — dangerous</span>
              <button data-comp="switch" className={`swh swh--danger${armBypass ? ' on' : ''}`} onClick={() => toggleArm('bypass')}
                title={armBypass ? 'Armed — Bypass joins the mode ring at launch' : 'Un-armed — Bypass is absent from the mode ring'} />
            </div>
          </div>
          {/* Honest-limit note (§7.11 — never a control that silently
              no-ops): Bypass arming now transmits for real (`arm_bypass` →
              --allow-dangerously-skip-permissions), so the note only covers
              what remains genuinely unreachable — there is NO arm-without-
              activate flag for Auto; its availability is the account's. */}
          {armAuto && mode !== 'Auto' && (
            <div className="text-[10px] text-muted-2 mt-1 normal-case font-semibold">
              Honest limit: Auto has no arm-without-activate flag — pick <b>Auto</b> as the launch Mode (<span className="font-mono">--permission-mode auto</span>) to launch armed-and-active, or rely on the account: Auto sits in eligible accounts&#8217; default ring regardless, and a live 400 &#8220;unreachable&#8221; drops it honestly.
            </div>
          )}
        </div>

        <div>
          <label className="ro-label block mb-1.5">Effort</label>
          <div data-comp="segmented-control" className="seg">
            {EFFORTS.map(m => <button key={m} className={effort === m ? 'active' : ''} onClick={() => setEffort(m)}>{m}</button>)}
          </div>
        </div>

        <div className="field editing">
          <label className="lbl block mb-1">Response format</label>
          <select className="in" value={respPreset} onChange={e => setRespPreset(e.target.value)} title="Reply-format preset injected into the agent's system prompt at launch (§11 #39)">
            {presets.length ? presets.map(p => <option key={p.id} value={p.id}>{p.label}</option>) : <option value="default">Default</option>}
          </select>
          {(() => { const p = presets.find(x => x.id === respPreset); return p && p.id !== 'default' ? <div className="text-[10px] text-muted-2 mt-1 normal-case font-semibold">{p.description}</div> : null })()}
        </div>

        <div>
          <div className="grid grid-cols-2 gap-2.5">
            <Stepper label="Max turns" value={maxTurns} onChange={setMaxTurns} />
            <Stepper label="Max Context %" value={maxCtx} max={100} onChange={setMaxCtx} />
          </div>
        </div>
      </div>
      </div>
      {/* Reset restores the FULL default create state (the useState initializers
          above) — presets (pickRole) and arm toggles mutate color/model/effort/
          maxTurns/mode too, so a partial reset would leave preset residue. */}
      <CreateFooter busy={busy} onCreate={create} onReset={() => {
        setRole('agent'); setNum(''); setName(''); setDesc('')
        setTools([]); setDeny([]); setMcp([]); setPlugins([])
        setColor(JEWELS[11].hex); setIcon('wizard-face'); setModel('inherit')
        setMode('Bypass'); setArmBypass(true); setArmAuto(false)
        setEffort('Med'); setMaxTurns(40); setMaxCtx(75); setRespPreset('default')
      }} />
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

// ---- Past tab — the resume picker + the per-agent archive (#17/#18, §7.12) ------
// RESUMABLE: GET /sessions/past — every persisted agent that isn't live (dead
// roster records + archived/retired ones), source-tagged, each with an honest
// `resumable` flag (a row with no conversation id reads greyed, Resume
// disabled). Resume → POST /sessions/resume: relaunch on the SAME conversation
// (never a fork); resuming an archived row also un-retires it. ARCHIVE: the
// deep-freeze records behind the rows (GET /archive) — expandable key/value
// cards over Resume + the true-delete (DELETE /archive/{id}, behind the
// designed inline danger confirm; the referenced transcript is untouched).
function pastStampFmt(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d2 = new Date(iso)
  if (isNaN(d2.getTime())) return String(iso).slice(0, 16)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d2.getMonth() + 1)}-${p(d2.getDate())} ${p(d2.getHours())}:${p(d2.getMinutes())}`
}
function pastIdentBits(identity: Identity | null, fallbackName?: string | null, sessionId?: string | null) {
  const num = identity?.number != null ? String(identity.number).padStart(2, '0') : ''
  // A fork's backend-assigned identity can carry an empty name (backend gap):
  // fall back to the session id it always has rather than a blank / bare "—".
  const idShort = sessionId ? sessionId.replace(/^awl-/, '').slice(0, 8) : ''
  return {
    role: identity?.role || 'agent',
    display: `${num ? num + ' ' : ''}${identity?.name || fallbackName || idShort || '—'}`,
    color: identity?.color || 'var(--muted)',
    icon: identity?.icon || '',
  }
}

function PastTab() {
  const d = useDash()
  const [past, setPast] = useState<PastAgent[] | null>(null)
  const [arch, setArch] = useState<ArchiveRecord[] | null>(null)
  const [openArc, setOpenArc] = useState<Set<string>>(new Set())
  const [confirmArc, setConfirmArc] = useState<string | null>(null)
  const [busyKey, setBusyKey] = useState<string | null>(null)

  // Own 5s cadence while the tab is open (in-flight guarded) — never bundled
  // into the roster poll (#33's lesson).
  useEffect(() => {
    let cancelled = false
    let inflight = false
    const pull = async () => {
      if (inflight) return
      inflight = true
      try {
        const [p, ar] = await Promise.all([api.sessionsPast(), api.archive()])
        if (cancelled) return
        if (p) setPast(p.past)
        if (ar) setArch(ar.archived)
      } finally { inflight = false }
    }
    pull()
    const i = setInterval(pull, 5000)
    return () => { cancelled = true; clearInterval(i) }
  }, [])

  const refresh = async () => {
    const [p, ar] = await Promise.all([api.sessionsPast(), api.archive()])
    if (p) setPast(p.past)
    if (ar) setArch(ar.archived)
  }

  const doResume = async (sel: { session_id?: string; archive_id?: string }, label: string) => {
    const key = sel.archive_id || sel.session_id || ''
    setBusyKey(key)
    const r = await api.resumeSession(sel.archive_id ? { archive_id: sel.archive_id } : { session_id: sel.session_id })
    setBusyKey(null)
    if (r.ok && r.data) {
      toast(`Resumed ${label} — same conversation, same identity${r.data.resumed_from === 'archive' ? ' (un-retired from the archive)' : ''}`)
      d.select(r.data.session_id)
      d.setAgentTab('details')
      refresh()
    } else {
      toast(`Resume failed: ${r.detail || 'sidecar error'}`)   // honest 400/404/409 verbatim
    }
  }

  const doArcDelete = async (arcId: string, label: string) => {
    setConfirmArc(null)
    const r = await api.deleteArchive(arcId)
    toast(r.ok ? `Archive record ${arcId} deleted forever (${label}'s transcript is untouched)` : `Delete failed: ${r.detail || 'sidecar error'}`)
    refresh()
  }

  const rows = past || []
  const arcs = arch || []
  const rez = rows.filter(p => p.resumable).length
  const kv = (k: string, v: React.ReactNode, plain?: boolean) => (
    <div className="arch-kv"><span className="k">{k}</span><span className={`v${plain ? ' plain' : ''}`}>{v}</span></div>
  )

  return (
    <div data-group="mid" className="p-3 space-y-3">
      <div className="agent-head">
        <span className="agtile agtile--user" style={{ width: 'var(--size-40)', height: 'var(--size-40)' }}><Ic name="history" className="agtile-luc" /></span>
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-heading text-foreground leading-tight" style={{ fontWeight: 900 }}>Past agents</div>
          <div className="text-[10px] text-muted font-semibold">resume a dead or archived agent — same conversation, same identity</div>
        </div>
      </div>

      <div>
        <div className="ro-head">
          <span className="ro-label" title="Every persisted agent that isn't live right now — dead roster records plus the archive, merged and source-tagged. Resume relaunches the agent on its own conversation (never a fork); a row with no conversation id can't resume and reads greyed.">Resumable</span>
          <span className="ml-auto text-[9.5px] text-muted font-mono font-semibold">{past == null ? '…' : `${rows.length} past · ${rez} resumable`}</span>
        </div>
        <div data-comp="past-agent-picker" className="aglist past-list">
          {rows.map(p => {
            const b = pastIdentBits(p.identity, p.name, p.session_id)
            // Roster rows carry the mockup's "died …" stamp when the sidecar
            // witnessed the stop/death (#17 died_at); legacy records and
            // unwitnessed deaths (reboot) fall back to the created stamp.
            const stamp = p.source === 'archive' ? `retired ${pastStampFmt(p.retired_at)}`
              : p.died_at ? `died ${pastStampFmt(p.died_at)}` : `created ${pastStampFmt(p.created_at)}`
            const key = p.archive_id || p.session_id || b.display
            return (
              <div key={key} data-comp="past-agent-row" className={`agrow past-row${p.resumable ? '' : ' past-row--norez'}`}
                title={p.resumable ? `${p.model || 'model inherit'} · ${stamp}` : 'No conversation id persisted — can’t resume onto its conversation'}>
                <span className="agtile" style={{ width: 'var(--size-28)', height: 'var(--size-28)', color: b.color }}><AgGlyph icon={b.icon} /></span>
                <span className="ag-lab">
                  <span className="ag-role">{b.role}{p.model ? ` · ${modelLabel(p.model)}` : ''}</span>
                  <span className="ag-name">{b.display}</span>
                </span>
                <span data-comp="past-source-badge" className={`past-src${p.source === 'archive' ? ' past-src--archive' : ''}`}
                  title={p.source === 'archive' ? 'From the archive — Resume un-retires it' : 'A dead roster record — the agent process is gone, the record persists'}>{p.source}</span>
                <span className="past-stamp">{stamp}</span>
                <button data-comp="button" className="btn btn-sm past-resume" disabled={!p.resumable || busyKey === key}
                  title={p.resumable ? 'Resume — relaunch on the same conversation, same identity' : 'Can’t resume — no conversation id to resume onto'}
                  onClick={() => doResume(p.source === 'archive' && p.archive_id ? { archive_id: p.archive_id } : { session_id: p.session_id || undefined }, b.display)}>
                  <Ic name="rotate-ccw" className="w-3 h-3" />{busyKey === key ? 'Resuming…' : 'Resume'}
                </button>
              </div>
            )
          })}
          {past != null && !rows.length && <div className="awl-empty">No past agents — everything persisted is live.</div>}
          {past == null && <div className="awl-empty">reading the past-agents feed…</div>}
        </div>
      </div>

      <div>
        <div className="ro-head">
          <span className="ro-label" title="Retire = deep-freeze: a light archive record — identity snapshot, created/retired stamps, lineage, per-agent git author — with the transcript referenced in place, never copied. Resume un-retires the agent; Delete forever true-deletes the record (the referenced transcript is untouched).">Archive</span>
          <span className="ml-auto text-[9.5px] text-muted font-mono font-semibold">{arch == null ? '…' : `${arcs.length} archived`}</span>
        </div>
        <div data-comp="archive-roster" className="arch-list">
          {arcs.map(rec => {
            const b = pastIdentBits((rec.identity as Identity) || null, rec.name, rec.session_id)
            const lin = rec.lineage || {}
            const linBits = [
              lin.parent ? `parent ${lin.parent}` : null,
              lin.fork ? `fork${typeof lin.fork === 'object' && lin.fork?.rewound_to != null ? ` @ turn ${lin.fork.rewound_to}` : ''}` : null,
              lin.handoff ? `handoff ${typeof lin.handoff === 'string' ? lin.handoff : ''}`.trim() : null,
            ].filter(Boolean).join(' · ')
            const isOpen = openArc.has(rec.archive_id)
            return (
              <div key={rec.archive_id} data-comp="archive-row" className={`fcard arch-card${isOpen ? ' open' : ''}`}>
                <div className="fcard-head">
                  <button className="fcard-exp" onClick={() => setOpenArc(prev => { const n = new Set(prev); n.has(rec.archive_id) ? n.delete(rec.archive_id) : n.add(rec.archive_id); return n })} title="Expand the archive record">
                    <span className="agtile" style={{ width: 'var(--size-28)', height: 'var(--size-28)', color: b.color }}><AgGlyph icon={b.icon} /></span>
                    <span className="ag-lab"><span className="ag-role">{b.role}</span><span className="ag-name">{b.display}</span></span>
                    <span className="fcard-time">retired {pastStampFmt(rec.retired_at)}</span>
                  </button>
                  <button className="fcard-chevbtn" onClick={() => setOpenArc(prev => { const n = new Set(prev); n.has(rec.archive_id) ? n.delete(rec.archive_id) : n.add(rec.archive_id); return n })} title="Expand / collapse"><Ic name="chevron-right" className="fcard-chev" /></button>
                </div>
                {confirmArc === rec.archive_id && (
                  <div data-comp="inline-confirm" className="tl-confirm foot-confirm--danger arch-del-confirm" style={{ display: 'flex' }}>
                    <span>Delete {b.display}&#8217;s archive record forever? This can&#8217;t be undone (the transcript it references is untouched).</span>
                    <button className="btn btn-sm ml-auto" onClick={() => setConfirmArc(null)}>Cancel</button>
                    <button className="btn-danger-solid btn-sm" onClick={() => doArcDelete(rec.archive_id, b.display)}><Ic name="trash-2" className="w-3.5 h-3.5" />Delete forever</button>
                  </div>
                )}
                <div className="fcard-body arch-body">
                  {kv('Archive id', rec.archive_id)}
                  {kv('Created', pastStampFmt(rec.created_at))}
                  {kv('Retired', pastStampFmt(rec.retired_at))}
                  {kv('Model · mode', `${modelLabel(rec.model)} · ${rec.permission_mode || '—'}`, true)}
                  {kv('CWD', rec.cwd || '—')}
                  {kv('Lineage', linBits || '—', !linBits)}
                  {kv('Git author', (rec as any).git_author_email || '—')}
                  {kv('Transcript', rec.transcript?.transcript_path || '—')}
                  <div className="arch-acts">
                    <button data-comp="button" className="btn btn-sm" disabled={!rec.transcript?.claude_session_id}
                      title={rec.transcript?.claude_session_id ? 'Resume — un-retires the agent back onto the roster, same conversation' : 'Can’t resume — no conversation id referenced'}
                      onClick={() => doResume({ archive_id: rec.archive_id }, b.display)}><Ic name="rotate-ccw" className="w-3 h-3" />Resume</button>
                    <span className="flex-1" />
                    <button data-comp="button" className="btn-danger btn-sm" title="Delete forever — true-deletes this archive record (the referenced transcript is untouched)"
                      onClick={() => setConfirmArc(rec.archive_id)}><Ic name="trash-2" className="w-3 h-3" />Delete forever</button>
                  </div>
                </div>
              </div>
            )
          })}
          {arch != null && !arcs.length && <div className="awl-empty">No archived agents — Retire deep-freezes an agent here.</div>}
          {arch == null && <div className="awl-empty">reading the archive…</div>}
        </div>
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
  // Honest retire toast: a 200 does NOT mean archived — the response's
  // `archived` field is the truth (null = the record was skipped or the write
  // failed). Whether anything survives depends on the driver: `record_kept`
  // says if a persisted roster row remains (bridge stop() keeps one; the sdk
  // close() fallback keeps nothing) — only then is "kept on Past" true.
  const retire = async () => {
    setConfirm(null)
    const r = await api.retire(s.session_id)
    const reason = r.data?.archive_error || r.data?.archive_skipped || 'no archive record written'
    if (r.ok && r.data?.archived) toast(`Retired ${a.short} (archived)`)
    else if (r.ok && r.data?.record_kept) toast(`Retired ${a.short} — not archived (kept on Past): ${reason}`)
    else if (r.ok) toast(`Retired ${a.short} — not archived — record not kept: ${reason}`)
    else toast(`Retire failed: ${r.detail || 'sidecar error'}`)
  }
  const del = async () => {
    setConfirm(null)
    const r = await api.hardDelete(s.session_id)
    toast(r.ok ? `Deleted ${a.short} — configuration + transcripts wiped` : `Delete failed: ${r.detail || 'sidecar error'}`)
  }
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
        {/* single-writer rule: while the expanded overlay is open it is the
            topmost view — this in-column instance stops driving pane geometry */}
        <ConsoleFeed id="con-feed-col" con={con} sendResize={!d.consoleExpanded} />
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
          <button className={`tab-btn${d.agentTab === 'past' ? ' active' : ''}`} onClick={() => d.setAgentTab('past')}>Past</button>
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
      {d.agentTab === 'past' && (
        <>
          <div className="pcard-body flex flex-col overflow-y-auto" style={{ background: 'var(--background)' }}>
            <PastTab />
          </div>
          <div className="pcard-foot px-2 py-2.5">
            <div className="flex items-center">
              <span className="text-[9.5px] text-muted font-mono font-semibold">Resume relaunches on the same conversation, never a fork — actions are per-row.</span>
            </div>
          </div>
        </>
      )}
      {d.agentTab === 'console' && <ConsoleTab s={s} />}
    </section>
  )
}
