// ============================================================================
// Sidecar API — base URL, types, and thin fetch helpers
// ----------------------------------------------------------------------------
// The renderer reaches the sidecar via window.awl.sidecarUrl (injected by the
// Electron preload), falling back to http://127.0.0.1:7690 when served standalone
// in a browser for verification.
//
// This layer speaks the CURRENT sidecar contract (the OD build): the merged
// /events SSE bus, the 5-type /inbox, agent-to-agent /links, /scratch, /library,
// /console, interactive /settings, /templates, and the /utility LLM passes — not
// the old per-session /history + send({prompt}) minimum.
// ============================================================================

// Dev override: when served standalone in a browser, `?sidecar=http://…` picks
// the sidecar instance to verify against (multiple lanes run parallel sidecars).
const _q = typeof location !== 'undefined' ? new URLSearchParams(location.search).get('sidecar') : null
export const API: string = (window as any).awl?.sidecarUrl || _q || 'http://127.0.0.1:7690'

// ---- Types (mirror sidecar to_dict / endpoint shapes) ----------------------

export interface Identity {
  role: string
  number: number
  name: string
  color: string   // hex from the 16 --ag-* tokens
  icon: string    // name from assets/icons/agents/
}

export interface LaunchConfig {
  allowed_tools: string[] | null
  disallowed_tools: string[] | null
  permission_rules: Record<string, string[]> | null
  enabled_plugins: Record<string, boolean> | null
  mcp_servers: string[] | null
  // Per-agent reply-format preset id (§11 #39); null = the agent's default style.
  response_preset?: string | null
  // Arm-without-activate (§7.11/#13): Bypass pre-armed at launch via
  // --allow-dangerously-skip-permissions without being the launch mode.
  arm_bypass?: boolean
}

// Response-format preset menu (§7.14/§11 #39). The instruction text is a launch
// detail the sidecar owns; the menu carries only id/label/description.
export interface ResponsePreset {
  id: string
  label: string
  description: string
}
export interface ResponsePresetCatalog {
  default: string
  presets: ResponsePreset[]
}

// The arbitrated run-state (§7.4): hook-pushed fields when fresh (source="push"),
// the screen-poll floor otherwise. Additive beside `status`.
export interface RunState {
  source: 'push' | 'poll'
  age_s: number | null
  phase: string | null
  permission_mode: string | null
  current_tool: string | null
  prompt_id: string | null
}

export interface Session {
  session_id: string
  agent_type: string | null
  model: string | null
  permission_mode: string
  cwd: string | null
  driver: string
  status: string // connecting | idle | running | error | closed
  created_at: string
  total_cost_usd: number
  total_turns: number
  event_count: number
  has_pending_permission: boolean
  permission_request: PermissionDetail | null
  identity: Identity | null
  // The launch-armed permission-mode set (§7.11): exactly the segments this
  // session's Shift+Tab ring contains — the Details ring hides the rest. The
  // live 400 "unreachable" stays the account-dependence backstop (Auto).
  armed_modes?: string[] | null
  run_state?: RunState
  launch_config: LaunchConfig
}

// A merged-bus event. Every event carries the common envelope
// (id/agent_id/seq/ts) + the addressing fields (source/recipients) on top of its
// own payload. `sdk_type` + `content` drive the assistant/user block renderers.
export interface SDKEvent {
  id?: string
  agent_id?: string          // the sender session id (identity stamp)
  seq?: number               // monotonic ordering key — order by this, never the id
  type: string
  subtype?: string
  sdk_type?: string
  ts?: string
  timestamp?: string
  source?: string            // addressing: from
  recipients?: string[]      // addressing: to (user | <agent-id> | scratch)
  data?: any
  content?: any
  status?: string
  [key: string]: any
}
export type AWLEvent = SDKEvent

export interface ContextUsage {
  tokens: number
  window: number
  model: string | null
  percent: number
  turns: number
  work_steps: number
  tools: Record<string, number>
  tool_total: number
}

// The §7.18 deep context readout (§11 #30) — ON-DEMAND ONLY (GET
// /sessions/{id}/context/breakdown). `rows` are the per-category `/context`
// slices in canonical order; `compact_history` is the compaction ledger. null
// from the helper means the endpoint is absent (400), the agent is busy (409),
// or unreachable — the accordion falls back to the JSONL floor honestly.
export interface ContextBreakdownRow {
  key: string
  tokens: number
  percent: number
  raw?: string
}
export interface ContextBreakdown {
  rows: ContextBreakdownRow[]
  compact_history?: { count: number; boundaries?: any[] }
  fetched_at?: string
}

// Per-agent cost (§7.15, §11 #32) — ON-DEMAND ONLY (GET /sessions/{id}/cost),
// Claude Code's own `/cost` estimate scraped idle-gated. `usd: null` is the
// honest miss (no panel rendered); null from the helper is absent/busy/offline.
// ⚠ No card surface yet: DESIGN.md + mockup both scope per-agent dollar spend
// out, so this contract method is unused pending a design-lane placement.
export interface CostBreakdown {
  usd: number | null
  per_model: number[]
  raw?: string
  fetched_at?: string
}

export interface UsageAgent {
  session_id: string
  model: string | null
  status: string
  tokens: number | null
  window: number | null
  percent: number | null
  work_steps: number | null
  tool_total: number | null
}

export interface Usage {
  agents: UsageAgent[]
  fleet: { agent_count: number; total_tokens: number }
  token_pill: number
}

export interface Subagent {
  // NOTE: the wire can carry `id: null` on the §7.17 blend's hook-registry
  // "extra" records (a SubagentStart the transcript hasn't matched) — the
  // store normalizes those away (merge or mint) so every consumer sees a
  // non-null display id. See normalizeSubs in store.tsx.
  id: string
  tool_use_id: string | null
  agent_id: string | null
  type: string | null
  description: string | null
  status: 'running' | 'done' | 'error'
  // Hook-fed live fields (§7.17 blend): live_status is the authoritative
  // active-vs-quiet signal when present; transcript status is the fallback.
  live_status?: string | null
  transcript_path?: string | null
  usage: any
}

export interface Subagents {
  count: number
  subagents: Subagent[]
}

export interface PermissionDetail {
  question?: string
  options?: { index: number; label: string }[]
  raw?: string
}

// ---- Inbox (5 typed sections) ----------------------------------------------

// Open-ended (§7.8) — the current vocabulary; `response` is the coalesced
// non-blocking "run ended with unreviewed output" card. The reserved `system`
// agent id groups the fleet-wide System Error cards.
export type InboxType = 'permission' | 'error' | 'warning' | 'plan' | 'decision' | 'response' | string

export interface InboxItem {
  id: string
  agent_id: string
  type: InboxType
  data: any
  resolved?: boolean
  sticky?: boolean
  dedup_key?: string | null
  answer?: any
  created_at?: string
}

export interface InboxResponse {
  inbox: Record<string, InboxItem[]>   // grouped by agent_id
  fleet_badge: number
}

// ---- Linking (agent-to-agent links) ----------------------------------------

export type LinkDirection = 'a2b' | 'b2a' | 'both'
export type LinkTrigger = 'now' | 'next' | 'queue' | 'inject' | 'hold' | 'piggyback'

export interface Link {
  id: string
  a: string
  b: string
  direction: LinkDirection
  relationship: string          // exactly one of {direct, shared} (§7.6 — both = two links)
  shared_content: string[]
  shared_backfill: boolean
  trigger: LinkTrigger
  end_after_exchanges: number | null
  end_after_tokens: number | null
  messages: number
  exchanges: number             // direction-aware: one-way = every fire; two-way = messages ÷ 2
  tokens: number
  active: boolean
}

export interface GroupedLink {
  link_id: string
  other: string | null
  arrow: string                 // → / ← / ↔
  relationship: string
  trigger: string
  active: boolean
}

export interface LinksResponse {
  links: Link[]
  grouped: Record<string, GroupedLink[]>
}

// ---- Scratch / Library / Console / Templates / Checklist / Marquee ---------

export interface ScratchPost { seq: number; author: string; text: string; ts: string }

// Provenance (created-by / when / session) lifted from a doc's .meta.json
// sidecar (§8.5) onto the Library read path so the Authors lens (§11 #41) can
// group by author. `{}` for un-stamped / browse-read-only docs.
export interface DocProvenance { created_by?: string; created_at?: string; session?: string }

export interface LibraryDoc { filename: string; path: string; size: number; modified: string; provenance?: DocProvenance }
export interface LibraryDocument { filename: string; path: string; content: string; provenance?: DocProvenance }
export interface Review { owner?: string; state?: string; verdict?: string; comments?: any; updated_at?: string }

// Per-doc .meta.json sidecar shape (§8.5): review + comments + provenance.
export interface DocComment {
  id: string
  text: string
  author: string
  ts?: string
  resolved?: boolean
  anchor_quote?: string | null
  anchor_heading?: string | null
}
export interface DocMeta {
  schema_version?: number
  owner?: string
  state?: string
  verdict?: string
  verdict_by?: string
  verdict_at?: string
  comments?: DocComment[]
  provenance?: DocProvenance
  updated_at?: string
}

// Projects picker feed (§3.2/§11 #26).
export interface ProjectEntry {
  path: string
  name: string
  last_used: string | null
  agent_count: number
  open: boolean
}
export interface ProjectsResponse { open: string | null; projects: ProjectEntry[] }

// ---- Past agents + archive (§11 #17/#18 — the Agent → Past tab) ------------

// One GET /sessions/past row: a persisted agent that isn't live — a dead
// roster record (source "roster") or a deep-frozen retired one ("archive").
export interface PastAgent {
  session_id: string | null
  name: string | null
  identity: Identity | null
  cwd: string | null
  model: string | null
  claude_session_id: string | null
  created_at: string | null
  // When the sidecar observed the agent stop/die (#17): roster rows only;
  // null for legacy records / unwitnessed deaths — the row falls back to
  // its created stamp.
  died_at?: string | null
  retired_at: string | null
  source: 'roster' | 'archive'
  archive_id: string | null
  live: boolean
  resumable: boolean
}
export interface PastResponse { past: PastAgent[]; count: number }

// The §11 #18 LIGHT archive record (transcript referenced in place, never copied).
export interface ArchiveRecord {
  archive_id: string
  session_id?: string | null
  name?: string | null
  identity?: Identity | null
  role?: string | null
  model?: string | null
  permission_mode?: string | null
  cwd?: string | null
  created_at?: string | null
  retired_at?: string | null
  lineage?: { parent?: string | null; fork?: any; handoff?: any } | null
  git_author?: { name?: string; email?: string } | string | null
  transcript?: { claude_session_id?: string | null; transcript_path?: string | null } | null
  [key: string]: any
}
export interface ArchiveResponse { archived: ArchiveRecord[]; count: number }

// ---- Timeline (§7.19/§11 #46) — one thin record per dashboard-initiated turn.
export interface TimelineTurn {
  turn: number                 // ordinal re-minted 1..N in stored order
  timestamp: string | null
  model: string | null
  mode: string | null
  effort: string | null
  thinking: boolean | null
  settings: string | null     // the rendered settings string (row tooltip)
  summary: string | null      // one-line reply summary; null = honest "—"
}
export interface TimelineResponse { session_id: string; count: number; turns: TimelineTurn[] }

// ---- Import (§11 #28) — pull an external Claude session into the workspace.
export interface ImportSessionRow {
  source: 'web' | 'desktop'
  id: string | null            // claude.ai conversation uuid; null for desktop
  title: string
  updated_at: string | null
  model: string | null         // desktop-only
}
export interface ImportResult {
  source: string
  destination: string
  title: string
  filename: string
  external_id: string | null
  markdown?: string            // destination "panel"
  path?: string                // destination "library"
  target_agent?: string        // destination "agent"
  delivery?: any
  [key: string]: any
}

// ---- Assets (§7.14/§7.16) — the materialized attachment store. -------------
export interface AssetRecord {
  id: string | null            // null = loose hand-dropped file (not byte-addressable)
  filename: string
  rel_path?: string
  mime?: string | null
  size?: number | null
  sha256?: string | null
  created?: string | null
  provenance?: { created_by?: string; created_at?: string; source?: string; session?: string } | null
  citation?: { doc?: string; location?: string } | null
  agent_path?: string | null   // the receiving agent's WSL-absolute rendering
  http_url?: string | null     // sidecar-relative byte URL (client prefixes API)
  [key: string]: any
}

export interface ConsoleCommand {
  command: string
  description: string
  cluster: string
  interactive: boolean
  also_in: string | null
}
export interface ConsoleCatalog {
  clusters: string[]
  by_cluster: Record<string, ConsoleCommand[]>
}
export interface ConsoleRunResult { command: string; interactive: boolean; screen: string }

export interface Template { id: string; name: string; body: string; placeholders: string[]; created_at: number }

export interface ChecklistItem { text: string; done: boolean }
export interface Checklist {
  total: number
  done: number
  items: ChecklistItem[]
  current: string | null
  indeterminate: boolean
  fraction: number
}

export interface Marquee { line: string; idle: boolean }

export interface AccountBand { email?: string; org?: string; plan?: string; signed_out?: boolean }

// ---- Create + send payloads ------------------------------------------------

export interface CreatePayload {
  model?: string | null
  permission_mode?: string
  cwd?: string | null
  allowed_tools?: string[] | null
  disallowed_tools?: string[] | null
  identity?: Partial<Identity> | null
  max_turns?: number | null
  max_context_pct?: number | null
  // Per-agent scoping (LaunchConfig mirror) — sent only when the user picked
  // values; older sidecars ignore unknown fields.
  mcp_servers?: string[] | null
  enabled_plugins?: Record<string, boolean> | null
  // Chosen reply-format preset id (§11 #39) — injected at launch. Omit for the
  // agent's default style.
  response_preset?: string | null
  // Arm Bypass without activating it (§7.11/#13): maps to
  // --allow-dangerously-skip-permissions at launch — Bypass joins the mode
  // ring while the agent still launches in permission_mode.
  arm_bypass?: boolean
}

export type Disposition = 'now' | 'next' | 'queue' | 'hold' | 'inject'

export interface SendOpts {
  source?: string
  recipients?: string[] | null
  disposition?: Disposition
  // Asset ids from POST /library/assets (§7.14): the sidecar appends ONE
  // attributed path block to the delivered text; an unknown id is an honest 400.
  attachments?: string[] | null
}
export interface SendResult { status: string; position?: number; session_id?: string; inject_id?: string }

// ---- Fetch helpers ---------------------------------------------------------

async function getJSON<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${API}${path}`)
    if (!r.ok) return null
    return (await r.json()) as T
  } catch {
    return null
  }
}

async function postJSON<T>(path: string, body?: any): Promise<T | null> {
  try {
    const r = await fetch(`${API}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!r.ok) return null
    return (await r.json()) as T
  } catch {
    return null
  }
}

async function delJSON<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${API}${path}`, { method: 'DELETE' })
    if (!r.ok) return null
    return (await r.json()) as T
  } catch {
    return null
  }
}

// Status-aware request — for surfaces that must render the HONEST failure
// (409 busy / 400 unreachable / 404 / the import 4xx messages) rather than
// collapsing every non-ok into null. `detail` carries the sidecar's
// plain-language `{detail: …}` body when present; status 0 = network-level
// failure (sidecar unreachable).
export interface ApiResult<T> { ok: boolean; status: number; data: T | null; detail: string | null }

async function reqJSON<T>(method: 'GET' | 'POST' | 'DELETE', path: string, body?: any): Promise<ApiResult<T>> {
  try {
    const r = await fetch(`${API}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    let payload: any = null
    try { payload = await r.json() } catch { /* non-JSON body */ }
    if (!r.ok) {
      const detail = payload && (typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail ?? payload))
      return { ok: false, status: r.status, data: null, detail: detail || `HTTP ${r.status}` }
    }
    return { ok: true, status: r.status, data: payload as T, detail: null }
  } catch {
    return { ok: false, status: 0, data: null, detail: 'sidecar unreachable' }
  }
}

const qs = (params: Record<string, string | number | undefined | null>): string => {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  return parts.length ? `?${parts.join('&')}` : ''
}

// ---- Merged event stream ---------------------------------------------------
// Opens an EventSource on /events. The sidecar replays the bounded ring then
// streams live; `?since/source/recipient` filter server-side. EventSource
// auto-reconnects (and re-replays the ring) — callers must dedup by event.id.

export interface EventStreamOpts {
  since?: number
  source?: string      // comma-separated From filter
  recipient?: string   // comma-separated To filter
  onEvent: (ev: SDKEvent) => void
  onError?: (e: Event) => void
  onOpen?: () => void
}

export function openEventStream(opts: EventStreamOpts): EventSource {
  const url = `${API}/events${qs({ since: opts.since, source: opts.source, recipient: opts.recipient })}`
  const es = new EventSource(url)
  es.onmessage = (m) => {
    if (!m.data) return
    try { opts.onEvent(JSON.parse(m.data)) } catch { /* ignore malformed */ }
  }
  if (opts.onOpen) es.onopen = opts.onOpen
  es.onerror = (e) => { if (opts.onError) opts.onError(e) }
  return es
}

export const api = {
  // ---- health / roster / lifecycle ----------------------------------------
  health: () => getJSON<{ status: string; version: string; active_sessions: number; driver: string }>('/health'),
  sessions: () => getJSON<Session[]>('/sessions'),
  session: (id: string) => getJSON<Session>(`/sessions/${id}`),
  create: (payload: CreatePayload) => postJSON<Session>('/sessions', payload),
  retire: (id: string) => delJSON<any>(`/sessions/${id}`),
  hardDelete: (id: string) => delJSON<any>(`/sessions/${id}?hard=true`),

  // ---- merged event history (backfill for the SSE stream) -----------------
  eventsHistory: (opts?: { since?: number; source?: string; recipient?: string }) =>
    getJSON<SDKEvent[]>(`/events/history${qs({ since: opts?.since, source: opts?.source, recipient: opts?.recipient })}`),

  // ---- send (queue/timing dispositions) + run control ----------------------
  // Status-aware: the endpoint's honest 4xx details — unknown attachment asset
  // id, "agent has no cwd; attachments need a project store", busy — must reach
  // the user verbatim, never collapse into a bare "send failed".
  send: (id: string, prompt: string, opts?: SendOpts) =>
    reqJSON<SendResult>('POST', `/sessions/${id}/send`, {
      prompt,
      source: opts?.source ?? 'user',
      recipients: opts?.recipients ?? null,
      disposition: opts?.disposition ?? 'queue',
      ...(opts?.attachments?.length ? { attachments: opts.attachments } : {}),
    }),
  interrupt: (id: string) => postJSON(`/sessions/${id}/interrupt`),
  setModel: (id: string, model: string) => postJSON(`/sessions/${id}/model`, { model }),
  setMode: (id: string, mode: string) => postJSON(`/sessions/${id}/mode`, { mode }),
  // Status-aware mode set (§7.11/#13): the bridge answers an honest 409 "busy"
  // (screen not idle — retryable) or 400 "unreachable" (an un-armed Bypass/Auto
  // segment silently absent from the Shift+Tab ring) — the UI renders those
  // states instead of a silent revert.
  setModeStatus: (id: string, mode: string) =>
    reqJSON<{ status: string; mode: string }>('POST', `/sessions/${id}/mode`, { mode }),
  setEffort: (id: string, effort: string) => postJSON(`/sessions/${id}/effort`, { effort }),
  // Live toggles the backend lane is adding — callers treat a null return as
  // "endpoint absent / rejected" and revert their optimistic UI (renderer #37).
  setFast: (id: string, on: boolean) => postJSON<{ status: string; on?: boolean }>(`/sessions/${id}/fast`, { on }),
  setThinking: (id: string, on: boolean) => postJSON<{ status: string; on?: boolean }>(`/sessions/${id}/thinking`, { on }),
  answerPermission: (id: string, approve: boolean) => postJSON(`/sessions/${id}/permission`, { approve }),
  // Post-create identity edit (§7.5): merge any subset of the five fields.
  // 400 on a retired number; a name change also /rename's the live session.
  updateIdentity: (id: string, patch: Partial<Identity>) =>
    postJSON<{ status: string; session_id: string; identity: Identity }>(`/sessions/${id}/identity`, patch),
  // Draw a random unused agent name from the shipped 179-name pool (§7.5/#40).
  // The draw excludes every live agent's name; pass `exclude` for extra names
  // (e.g. one staged in the Create form). A user-typed name is always allowed.
  randomName: (exclude?: string[]) =>
    getJSON<{ name: string | null }>(`/identity/random-name${qs({ exclude: exclude?.length ? exclude.join(',') : undefined })}`),

  // ---- response-format presets (§7.14/§11 #39) ----------------------------
  // The menu, plus per-agent get/set. A set persists to state/agents.json and
  // takes effect at the agent's next launch/restart (append-system-prompt is a
  // launch flag); the create-time choice applies immediately. 400 on unknown id.
  responsePresets: () => getJSON<ResponsePresetCatalog>('/presets/response'),
  responsePreset: (id: string) =>
    getJSON<{ session_id: string; response_preset: string | null }>(`/sessions/${id}/response-preset`),
  setResponsePreset: (id: string, preset: string) =>
    postJSON<{ status: string; session_id: string; response_preset: string }>(`/sessions/${id}/response-preset`, { preset }),

  // ---- per-agent readouts --------------------------------------------------
  context: (id: string) => getJSON<ContextUsage>(`/sessions/${id}/context`),
  // On-demand deep readouts (§7.15/§7.18, §11 #30/#32) — never on a poll loop;
  // each costs a live TUI round-trip, so the frontend pulls them lazily.
  contextBreakdown: (id: string) => getJSON<ContextBreakdown>(`/sessions/${id}/context/breakdown`),
  cost: (id: string) => getJSON<CostBreakdown>(`/sessions/${id}/cost`),
  subagents: (id: string) => getJSON<Subagents>(`/sessions/${id}/subagents`),
  checklist: (id: string) => getJSON<Checklist>(`/sessions/${id}/checklist`),
  marquee: (id: string) => getJSON<Marquee>(`/sessions/${id}/marquee`),
  usage: () => getJSON<Usage>('/usage'),

  // ---- inbox ---------------------------------------------------------------
  inbox: () => getJSON<InboxResponse>('/inbox'),
  resolveInbox: (agent: string, itemId: string, answer?: any) =>
    postJSON(`/inbox/${agent}/${encodeURIComponent(itemId)}/resolve`, answer !== undefined ? { answer } : {}),

  // ---- linking ---------------------------------------------------------------
  links: () => getJSON<LinksResponse>('/links'),
  createLink: (body: {
    a: string; b: string; direction?: LinkDirection; relationship?: string
    shared_content?: string[]; shared_backfill?: boolean; trigger?: LinkTrigger
    end_after_exchanges?: number | null; end_after_tokens?: number | null
  }) => postJSON<Link>('/links', body),
  deleteLink: (id: string) => delJSON<any>(`/links/${id}`),
  kickoffLink: (id: string, body: { from_agent: string; to_agent: string; prompt: string }) =>
    postJSON<any>(`/links/${id}/kickoff`, body),

  // ---- scratch (shared scratchpad) -------------------------------------------
  scratch: (cwd: string) => getJSON<{ posts: ScratchPost[] }>(`/scratch${qs({ cwd })}`),
  postScratch: (body: { cwd: string; author: string; text: string }) =>
    postJSON<{ status: string; post: ScratchPost }>('/scratch', body),

  // ---- library (docs + per-doc .meta.json sidecars, §8.5) ------------------
  libraryDocuments: (cwd: string, subdir?: string) =>
    getJSON<LibraryDoc[]>(`/library/documents${qs({ cwd, subdir })}`),
  libraryDocument: (path: string) => getJSON<LibraryDocument>(`/library/document${qs({ path })}`),
  libraryReviews: (cwd: string) => getJSON<Record<string, DocMeta>>(`/library/reviews${qs({ cwd })}`),
  createDocument: (body: { cwd: string; filename: string; content: string; subdir?: 'docs' | 'plans' }) =>
    postJSON<{ status: string; path: string }>('/library/document', body),
  writeDocument: (body: { cwd: string; path: string; content: string }) =>
    fetch(`${API}/library/document`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(r => (r.ok ? r.json() : null)).catch(() => null),
  deleteDocument: (path: string, cwd: string) =>
    delJSON<any>(`/library/document${qs({ path, cwd })}`),
  renameDocument: (body: { cwd: string; path: string; new_filename: string }) =>
    postJSON<{ old: string; new: string }>('/library/document/rename', body),
  addComment: (body: { cwd: string; path: string; text: string; author: string; anchor_quote?: string; anchor_heading?: string }) =>
    postJSON<DocComment>('/library/comments', body),
  resolveComment: (body: { cwd: string; path: string; comment_id: string }) =>
    postJSON<{ status: string }>('/library/comments/resolve', body),

  // ---- plans action loop (§7.16/§9.7) ---------------------------------------
  planVerdict: (id: string, body: { verdict: 'approve' | 'revise'; text?: string; filename?: string; by?: string }) =>
    postJSON<{ status: string; verdict: string }>(`/sessions/${id}/plan/verdict`, body),

  // ---- projects (§3, one project at a time) ---------------------------------
  projects: () => getJSON<ProjectsResponse>('/projects'),
  registerProject: (path: string) => postJSON<ProjectEntry>('/projects/register', { path }),
  openProject: (path: string) => postJSON<ProjectEntry & { status: string }>('/projects/open', { path }),
  closeProject: (stopAgents = false) =>
    postJSON<{ status: string; path: string; stopped_agents: boolean }>('/projects/close', { stop_agents: stopAgents }),

  // ---- console (slash-command runner + live terminal attach) ---------------
  consoleCatalog: (q?: string) => getJSON<ConsoleCatalog & { commands?: ConsoleCommand[] }>(`/console/catalog${qs({ q })}`),
  consoleRun: (id: string, command: string) =>
    postJSON<ConsoleRunResult>(`/sessions/${id}/console/run`, { command }),
  // Attach-on-open streaming terminal (backend lane, §11 #37f contract):
  // POST /sessions/{id}/console/attach → { ws_url } (ttyd-style raw WebSocket).
  // Null → endpoint not merged yet; the Console degrades to catalog-only.
  consoleAttach: (id: string) => postJSON<{ ws_url: string }>(`/sessions/${id}/console/attach`),

  // ---- templates -------------------------------------------------------------
  templates: () => getJSON<Template[]>('/templates'),
  addTemplate: (body: { name: string; body: string; placeholders?: string[] | null }) =>
    postJSON<Template>('/templates', body),
  deleteTemplate: (id: string) => delJSON<any>(`/templates/${id}`),

  // ---- utility LLM passes (the sdk-driver carve-out) -----------------------
  revise: (text: string, scope: 'grammar' | 'language' | 'refactor' = 'grammar', model?: string) =>
    postJSON<{ scope: string; result: string }>('/utility/revise', { text, scope, model }),
  summarize: (text: string, model?: string) =>
    postJSON<{ result: string }>('/utility/summarize', { text, model }),

  // ---- settings (interactive writes + the registry reads) ------------------
  settingsRead: (path: string) => getJSON<any>(`/settings/read${qs({ path })}`),
  settingsAccount: (creds_path: string) => getJSON<AccountBand>(`/settings/account${qs({ creds_path })}`),
  settingsWrite: (body: { path: string; key?: string | null; value?: any; op?: 'write' | 'set' | 'toggle' | 'remove'; confirm?: boolean }) =>
    postJSON<any>('/settings/write', body),
  settingsMcp: (project?: string) =>
    getJSON<{ user: any[]; project: any[] }>(`/settings/mcp${qs({ project })}`),
  settingsPlugins: () => getJSON<{ installed: any[]; marketplaces: any[] }>('/settings/plugins'),
  settingsConfig: (project?: string) => getJSON<any>(`/settings/config${qs({ project })}`),

  // ---- past agents + archive (§11 #17/#18 — Agent → Past) ------------------
  sessionsPast: () => getJSON<PastResponse>('/sessions/past'),
  // Status-aware resume: 404 no match · 409 already live · 400 no conversation
  // id — each rendered honestly on the Past tab.
  resumeSession: (sel: { session_id?: string; name?: string; archive_id?: string }) =>
    reqJSON<Session & { resumed_from?: string; archive_id?: string | null }>('POST', '/sessions/resume', sel),
  archive: () => getJSON<ArchiveResponse>('/archive'),
  archiveRecord: (id: string) => getJSON<ArchiveRecord>(`/archive/${encodeURIComponent(id)}`),
  deleteArchive: (id: string) =>
    reqJSON<{ status: string; archive_id: string }>('DELETE', `/archive/${encodeURIComponent(id)}`),

  // ---- Timeline + Rewind/Handoff (§7.19, §11 #15/#46) -----------------------
  timeline: (id: string) => getJSON<TimelineResponse>(`/sessions/${id}/timeline`),
  // k-from-last addressing: to_prompt_index = how many prompt checkpoints to
  // roll back from the end (the record carries no anchor — §7.19's caveat).
  // Honest failures: 409 busy · 400 version-gated (< 2.1.191) / no capability.
  rewind: (id: string, k: number) =>
    reqJSON<{ status: string; [key: string]: any }>('POST', `/sessions/${id}/rewind`, { to_prompt_index: k }),
  fork: (id: string, body: { to_prompt_index?: number | null; handoff?: boolean; model?: string | null }) =>
    reqJSON<Session & {
      forked_from?: string; rewound_to?: number | null
      filestate?: { mode?: string; isolated?: boolean; cwd?: string; note?: string; [key: string]: any } | null
      handoff?: { filename?: string; path?: string; error?: string; [key: string]: any } | null
    }>('POST', `/sessions/${id}/fork`, body),

  // ---- Import an external Claude session (§11 #28) ---------------------------
  // Both are status-aware: the 4xx messages (missing session key, no desktop
  // store, no title match, extractor timeout) surface verbatim in the drawer.
  importList: (source: 'web' | 'desktop') =>
    reqJSON<{ source: string; sessions: ImportSessionRow[] }>('GET', `/import/external${qs({ source })}`),
  importRun: (body: { source: string; title: string; destination: 'agent' | 'panel' | 'library'; target_agent?: string | null; cwd?: string | null }) =>
    reqJSON<ImportResult>('POST', '/import/external', body),

  // ---- Library assets (§7.14/§7.16) — materialized attachments ---------------
  libraryAssets: (cwd: string) => getJSON<AssetRecord[]>(`/library/assets${qs({ cwd })}`),
  // Ingest — exactly one of content_base64 / source_path; status-aware so the
  // 400s (over-size, bad name, no cwd) render honestly on the Attach flow.
  ingestAsset: (body: {
    cwd: string; filename?: string; content_base64?: string; source_path?: string
    created_by?: string; session?: string; citation?: { doc?: string; location?: string } | null
  }) => reqJSON<{ asset: AssetRecord; agent_path: string | null; http_url: string | null }>('POST', '/library/assets', body),
  // Delete one ingested asset — bytes dir + sidecar (§7.16 Remove). Status-
  // aware: 404 unknown/loose id · 400 no store · 500 failed removal, verbatim.
  deleteAsset: (id: string, cwd: string) =>
    reqJSON<{ status: string; asset_id: string }>('DELETE', `/library/assets/${encodeURIComponent(id)}${qs({ cwd })}`),
  // The renderer's byte URL for an asset (localhost HTTP — the recommended
  // render path; http_url from the records is the same, sidecar-relative).
  assetUrl: (rec: AssetRecord): string | null => (rec.http_url ? `${API}${rec.http_url}` : null),

  // ---- assets --------------------------------------------------------------
  iconUrl: (icon: string, color: string) =>
    `${API}/assets/agent-icons/${encodeURIComponent(icon)}.svg?color=${encodeURIComponent(color)}`,
}
