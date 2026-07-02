# Review & Remediation — `docs/ARCHITECTURE.md`

## Context

`docs/ARCHITECTURE.md` was created on 2026-07-01 (commit `108d3c7`) as the first resident of `docs/` — the system counterpart to `design/DESIGN.md` (UI intent) and `DEVLOG.md` (history). You asked for a confidence review before relying on it: does it reflect the real code, is it free of stale info, is it internally consistent and fully defined, does it quarantine dynamic/volatile values so buried-stale-facts don't accumulate, and is it otherwise optimal for conventions + easy maintenance + agentic use.

I verified it two ways: (1) **provenance** — read the full creating session (`.claude/cc-exports/claude-2026-07-01-dev-doc-2a.md`); it was built from DESIGN.md + the OD decisions tracker, cross-checked by four parallel code readers (sidecar/bridge/frontend/coverage-map) and reconciled against DEVLOG. (2) **independent re-verification** — three fresh Explore agents re-checked every concrete claim against live code in `sidecar/`, `bridge/`, `frontend/`, plus the referenced docs.

**Verdict: the doc is accurate and well-built** — the large majority of concrete claims match the code exactly (version, port/host, env vars, driver CAPABILITIES sets verbatim, event envelope, ring size, endpoint surface, storage, reconnect, poll cadences, OD attributions, staleness reconciliation). A small set of concrete defects and one structural gap remain, listed below.

---

## Assessment (your five questions)

**1. Factored in relevant docs + current code (bridge/sidecar/frontend)?** — **Yes, strongly.** Provenance confirmed; independent re-check confirms fidelity across all three layers. It correctly reads *code* as ground truth and cites DESIGN.md/OD-tracker/DEVLOG for intent/decisions/history.

**2. Free of stale info?** — **Mostly.** It actively defends against staleness (a "Sources & freshness" header that names `coverage-map.md` and the CLAUDE.md "one App.tsx" line as *superseded*, with "trust the code" — both confirmed genuinely stale). No evidence it drew wrong facts from stale sources. But it carries a few **authoring-time inaccuracies** (see Defects D1–D3).

**3. Internally consistent & fully defined?** — **Yes for consistency.** After two anchor-link fixes the author already made, all `§` cross-links resolve and all OD-01…OD-23 attributions match the tracker exactly. **Under-defined in one place:** the §10 repo map (see D3).

**4. Stateless / dynamic content quarantined & standardized?** — **Partially — this is the main structural weakness.**
   - *Done well:* volatile **decisions** are externalized to the OD tracker by ID (`OD-01…OD-23`) instead of being restated — so decision-drift lives in one place.
   - *Not done:* volatile **runtime parameters/constants** are embedded inline and scattered, with no standardized tag or single home: `v0.3.0` (repeated 4×), port `7690`, host `0.0.0.0`, env-var names, poll cadences (`5s/2s/3s/4.5s/1.2s`), ring `5000`, SSE cap `~4000`, cap-loop `3s`, End-After `25`, `16 vs 25` colours, the exact `CAPABILITIES` set literals, storage paths. These are exactly the "current parameters" that rot silently when code is tuned. There is no "current values (as-of)" table and no inline marker to find them.

**5. Optimal for conventions / maintenance / agentic use?** — **Largely yes.** Right name+location (matklad `ARCHITECTURE.md` convention, placed in the repo's designated `docs/`); clear scope header, numbered sections, tables, ASCII topology, repo map, honest build-status matrix, clickable relative links, greppable OD IDs — all strong for agentic navigation. Improvements are the parameter-quarantine (Q4) plus a short maintenance-contract note.

---

## Defects found (evidence-backed)

| ID | Severity | Where | Issue | Fix |
|----|----------|-------|-------|-----|
| **D1** | **High (wrong path)** | §4.3 (line ~198) & §10 (line ~398) | Doc locates `serialize.py` at `sidecar/drivers/serialize.py`. It is actually at **`sidecar/serialize.py`** (root); `drivers/` holds only `__init__/base/bridge/sdk`. SDK driver imports it as top-level `serialize`. | Correct both path references + the §10 grouping (list `serialize.py` under `sidecar/`, not the `drivers/` row). |
| **D2** | Medium (unsupported claim) | §3.3 (line ~145) | Lists `/scratch (3s)` as a client poll cadence. No dedicated `/scratch` poll exists in `App.tsx`; scratch reads are on-demand and OD-17 delivery rides the hook/watermark path, not polling. | Remove `/scratch` from the polling list (or footnote it as on-demand + hook-pushed, not polled). |
| **D3** | Medium (incomplete) | §10 repo map | Omits 13 real sidecar modules that `main.py` imports: `checklist, console_catalog, deletion, library, links, marquee, scratchpad, settings_io, storage, subagents_naming, templates_store, utility_llm, watermark`. Understates the sidecar and leaves agents unable to locate them via the map. | Add the missing modules to the §10 sidecar row(s), grouped by concern. |
| **D4** | Low (optional) | §4.2 endpoint table | `GET /sessions/{id}/events` (per-session SSE) exists but isn't listed (the doc documents the merged `/events` bus only). | Add a one-line row, or a note that per-session SSE also exists but the client uses the merged bus. |
| **D5** | Low (optional) | §5.4 | "~20 documented methods" lists 22; 4 more public methods exist (`session_id_for`, `register_session_id`, `wsl_host_ip`, `sidecar_hook_base_url`). Mechanism *is* described in prose, so honesty is intact. | Optionally note the hook/registration helpers exist, or soften to "the ~20 CLAUDE.md-documented methods, plus internal helpers." |
| **D6** | Low (wording) | §4.2 / §5.3 | "`/utility/*` routed through the **`sdk` driver**" — it actually calls the in-process Claude Agent **SDK** `query()` directly, not the `sdk` *driver* class. | Reword to "the in-process SDK path" to be precise. |

Everything else re-checked (dozens of claims) came back **CONFIRMED** against code.

---

## Two kinds of "dynamic" (clarifying your Q4)

- **In-flux / undecided** (design questions, not-yet-built, bridge-blocked, parked). *Already handled well* by §9's build-status matrix + the `OD-*` references. Keep this pattern.
- **Volatile-but-currently-fixed parameters** (version, port/host, env-var names, poll cadences, ring size, SSE cap, cap-loop interval, End-After default, colour counts, `CAPABILITIES` literals, storage paths). *Not* quarantined today — scattered inline, so they rot silently on any code tune. **This** is the buried-stale risk to fix.

## Decision (LOCKED, from your answers)

- **Scope:** targeted fixes on the existing doc — it's substantively accurate, so keep its structure. Fix the 3 real defects + cosmetics, collapse the repeated version, re-ground touched claims against code.
- **Volatile-parameter mechanism:** **none** (declined the appendix table). Rationale you and I agreed on: agents treat *code* as truth (the doc already says so), and a parallel table just duplicates each value → a second sync burden + a new staleness surface. Instead: **don't duplicate volatile values; where one must appear, name its source file beside it.** The only real smell is the version repeated 4× → collapse to one mention.

## Edit plan

**Preserve verbatim** everything the reviews CONFIRMED (layer descriptions, coordination-spine mechanics, flows, OD attributions, topology diagram, mental model, staleness reconciliation, §9 build-status matrix). Per the editing-discipline rule, carry untouched sections forward exactly — this is surgical, not a rewrite.

1. **D1** — correct `serialize.py` → `sidecar/serialize.py` in §4.3 and §10 (out of the `drivers/` grouping).
2. **D2** — remove `/scratch` from the §3.3 polling list; footnote it as on-demand + hook/watermark-pushed (OD-17), not polled.
3. **D3** — complete the §10 sidecar map: add `checklist, console_catalog, deletion, library, links, marquee, scratchpad, settings_io, storage, subagents_naming, templates_store, utility_llm, watermark`, grouped by concern.
4. **D4** — note `GET /sessions/{id}/events` (per-session SSE) in §4.2, flagging the client uses the merged bus.
5. **D5** — in §5.4, reconcile the method count ("the ~20 CLAUDE.md-documented methods, plus internal helpers `session_id_for`/`register_session_id`/`wsl_host_ip`/`sidecar_hook_base_url`").
6. **D6** — reword "`/utility/*` routed through the `sdk` driver" → "the in-process Claude Agent SDK path" (it calls SDK `query()` directly, not the `sdk` *driver* class).
7. **Version** — collapse `v0.3.0` to a single mention (freshness header); elsewhere refer to "the sidecar" without restating the number.
8. **No new sections, no table, no tags.**

**Critical files (read-only inputs, already verified):** `docs/ARCHITECTURE.md` (reference), and the source-of-truth files behind each parameter — `sidecar/main.py`, `sidecar/eventbus.py`, `sidecar/drivers/{bridge,sdk,base,__init__}.py`, `sidecar/serialize.py`, `sidecar/runtime_store.py`, `sidecar/links.py`, `frontend/src/renderer/{App.tsx,tokens.ts,api.ts}`, `bridge/{bridge,paths}.py`, `dev/notes/open-system-decisions-2026-06-29.md`.

## Verification

- Re-grep the rewritten doc: `serialize.py` path correct; no `/scratch` poll cadence; all 13 modules present; appendix values each match their cited source file (spot-check version, port, ring `5000`, cap `4000`, cadences, cap-loop `3s`).
- Confirm every `§` anchor link and `OD-*` reference still resolves after renumber/edits (this is a Markdown doc — the "render + resize + click" UI rule does not apply; link-integrity + value-accuracy is the bar).
- Diff against the original to confirm no CONFIRMED content was dropped or altered (editing-discipline check).
- Append a `DEVLOG.md` entry (append-only) before finishing.
- No commit/push unless you ask.
