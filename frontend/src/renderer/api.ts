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

export const API: string = (window as any).awl?.sidecarUrl || 'http://127.0.0.1:7690'

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
  id: string
  tool_use_id: string | null
  agent_id: string | null
  type: string | null
  description: string | null
  status: 'running' | 'done' | 'error'
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

export type InboxType = 'permission' | 'error' | 'warning' | 'plan' | 'decision'

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

export interface LibraryDoc { filename: string; path: string; size: number; modified: string }
export interface LibraryDocument { filename: string; path: string; content: string }
export interface Review { owner?: string; state?: string; verdict?: string; comments?: any; updated_at?: string }

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
}

export type Disposition = 'now' | 'next' | 'queue' | 'hold' | 'inject'

export interface SendOpts {
  source?: string
  recipients?: string[] | null
  disposition?: Disposition
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
  send: (id: string, prompt: string, opts?: SendOpts) =>
    postJSON<SendResult>(`/sessions/${id}/send`, {
      prompt,
      source: opts?.source ?? 'user',
      recipients: opts?.recipients ?? null,
      disposition: opts?.disposition ?? 'queue',
    }),
  interrupt: (id: string) => postJSON(`/sessions/${id}/interrupt`),
  setModel: (id: string, model: string) => postJSON(`/sessions/${id}/model`, { model }),
  setMode: (id: string, mode: string) => postJSON(`/sessions/${id}/mode`, { mode }),
  setEffort: (id: string, effort: string) => postJSON(`/sessions/${id}/effort`, { effort }),
  answerPermission: (id: string, approve: boolean) => postJSON(`/sessions/${id}/permission`, { approve }),

  // ---- per-agent readouts --------------------------------------------------
  context: (id: string) => getJSON<ContextUsage>(`/sessions/${id}/context`),
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

  // ---- library (read + render) ---------------------------------------------
  libraryDocuments: (cwd: string, subdir?: string) =>
    getJSON<LibraryDoc[]>(`/library/documents${qs({ cwd, subdir })}`),
  libraryDocument: (path: string) => getJSON<LibraryDocument>(`/library/document${qs({ path })}`),
  libraryReviews: (cwd: string) => getJSON<Record<string, Review>>(`/library/reviews${qs({ cwd })}`),

  // ---- console (slash-command runner) ----------------------------------------
  consoleCatalog: (q?: string) => getJSON<ConsoleCatalog & { commands?: ConsoleCommand[] }>(`/console/catalog${qs({ q })}`),
  consoleRun: (id: string, command: string) =>
    postJSON<ConsoleRunResult>(`/sessions/${id}/console/run`, { command }),

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

  // ---- assets --------------------------------------------------------------
  iconUrl: (icon: string, color: string) =>
    `${API}/assets/agent-icons/${encodeURIComponent(icon)}.svg?color=${encodeURIComponent(color)}`,
}
