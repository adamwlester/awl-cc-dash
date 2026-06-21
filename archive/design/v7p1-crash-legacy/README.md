# v7p1 crash legacy — DO NOT BUILD ON THESE

These are **raw artifacts from two crashed v7p1 build attempts** (Claude Desktop, 2026-06-14).
They are archived for forensic/reference value only. **None of them is a usable or complete
dashboard, and none should be edited or continued.** The live build starts fresh from
`agent-dashboard/design/ui-concept-v6p3.html`.

| File | What it is | Useful? |
|------|------------|---------|
| `crashed-partial.html` | The furthest the build got: left + middle panes (incl. the ported model/context/history), **cut off mid Agent→Create**. No right-hand Prompts pane, no footer, no palette ref. | Loose reference for *direction* only. |
| `crashed-skeleton.html` | The retry's intended full structure as a placeholder scaffold (`__RIGHTPANE__`, `__WINFOOTER__`, `__PALETTEREF__`) — crashed before any panel was filled. | Shows the *planned layout*, no content. |
| `raw-jsonwrapped-blob.html` | The crash payload as written to disk — HTML trapped inside a `{"path":...,"content":"..."}` JSON wrapper. Malformed; won't render. | Forensic only. |

**Cleaner reference copies** of the partial and skeleton (clearly labeled, same content) live with
the rest of the reboot materials at `prompts/ui-rockstar-reboot/recovered-examples/`. Use those, not
these, if you want to glance at where the last run was heading. Full source of truth for everything
the crashed session did: `tools/claude-context-extractor/out/2026-06-14-UI-Rockstar-RETRY-1050/`.
