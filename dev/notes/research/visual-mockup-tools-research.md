---
source: claude
created: 2026-04-01
tags: [research, claude-code, visual-design, mcp-servers, mockups]
---

# Visual Mockup & Design Tools for Claude Code

Research brief: What tools, plugins, MCP servers, or workflows let Claude Code generate proper visual mockups (SVGs, PNGs, wireframes, design files)?

**Date:** 2026-04-01

---

## 1. Excalidraw MCP Servers (Mature Ecosystem)

The most active category. Multiple implementations exist:

| Repo | Description | Status |
|------|-------------|--------|
| [yctimlin/mcp_excalidraw](https://github.com/yctimlin/mcp_excalidraw) | Programmatic canvas toolkit — create, edit, export diagrams with real-time sync | Active (Mar 2026) |
| [BV-Venky/excalidraw-architect-mcp](https://github.com/BV-Venky/excalidraw-architect-mcp) | Architecture diagrams with auto-layout | Active (Mar 2026) |
| [bassimeledath/excalidraw-render-mcp](https://github.com/bassimeledath/excalidraw-render-mcp) | Headless rendering — no data sent to third-party servers | Active (Mar 2026) |
| [debu-sinha/excalidraw-mcp-server](https://github.com/debu-sinha/excalidraw-mcp-server) | Security-hardened, WebSocket sync, 14 diagramming tools | Feb 2026 |
| [mklinovsky/excalimaid](https://github.com/mklinovsky/excalimaid) | Converts Mermaid -> Excalidraw, serves locally, opens in browser | Feb 2026 |
| [al1y/mcp-excalidraw](https://github.com/al1y/mcp-excalidraw) | Live web app preview for Claude Desktop/Cursor | May 2025 |

**Key capabilities:** Create shapes/arrows/text, convert Mermaid to Excalidraw, real-time browser preview, export to PNG/SVG, manage multiple sessions.

**Claude Code skill also available:** "Excalidraw Wireframe Creator" on MCP Market — generates Excalidraw-compatible JSON diagrams.

---

## 2. Figma MCP Server (Official, Bidirectional)

**Official Figma MCP** — announced Feb 2026, maintained by Figma.

- **Remote install:** `claude mcp add --transport http figma https://mcp.figma.com/mcp`
- **Guide repo:** [figma/mcp-server-guide](https://github.com/figma/mcp-server-guide)
- **Figma Learn:** [help.figma.com](https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server)

**Capabilities:**
- **Design-to-code:** Reference Figma designs in Claude Code prompts, extract components/tokens/styles/layout, generate matching code
- **Code-to-canvas:** Push production code back into Figma as editable designs ("Code Connect")
- **Bidirectional workflow:** Edit in Figma, pull into Claude Code; build in Claude Code, push to Figma

**Limitation:** Requires Figma Pro plan. Reads design structure, not screenshots — so it works through semantic data, not pixel-level mockups.

---

## 3. Wireframe-Specific MCP Servers

| Tool | Description | How It Works |
|------|-------------|--------------|
| **Wirekitty** | MCP server for wireframe generation | Generates wireframes as clickable links that open in browser; browser-based editor for refinement |
| **MockFlow WireframePro MCP** ([mockflow/wireframepro-mcp](https://github.com/mockflow/wireframepro-mcp)) | Convert HTML to editable wireframes, create flowcharts and cloud architecture diagrams | Local MCP server; works with Claude Code, Cursor, Copilot |
| **Waiframe** ([waiframe.com](https://waiframe.com/docs/mcp)) | Structured wireframes from descriptions | MCP server that produces wireframes for AI coding tools to read |
| **bengous/wireframer** ([GitHub](https://github.com/bengous/wireframer)) | AI-driven wireframe generation | Playwright captures DOM -> Claude analyzes -> renders to PNG via napi-rs/canvas |
| **Superdesign MCP** ([jonthebeef/superdesign-mcp-claude-code](https://github.com/jonthebeef/superdesign-mcp-claude-code)) | Design orchestrator — UI designs, wireframes, components, logos, SVG icons | Generates design specifications using the IDE's LLM; no external API key needed |

---

## 4. Diagram Rendering MCP Servers (Mermaid, PlantUML, D2, etc.)

| Tool | Formats | Output |
|------|---------|--------|
| **peng-shawn/mermaid-mcp-server** | Mermaid | PNG via Puppeteer |
| **hustcc/mcp-mermaid** | Mermaid | Dynamic chart/diagram generation |
| **veelenga/claude-mermaid** | Mermaid | Live reload preview in browser |
| **rtuin/mcp-mermaid-validator** | Mermaid | Validates and renders diagrams |
| **ryu1maniwa/mermaid-local-mcp** | Mermaid | PNG via mmdc for Claude Code visual feedback loops |
| **antoinebou12/uml-mcp** | PlantUML, Mermaid, D2, Graphviz, TikZ, ERD, BlockDiag, BPMN, C4 | Multiple UML diagram types |
| **tohachan/diagram-bridge-mcp** | Mermaid, PlantUML, D2, Graphviz, ERD | PNG or SVG output |
| **draw.io MCP** ([jgraph/drawio-mcp](https://github.com/jgraph/drawio-mcp)) | XML, CSV, Mermaid | Opens in draw.io editor; also renders inline in chat |
| **@drawio/mcp (npm)** | draw.io native | MCP App Server renders inline; skill generates .drawio with PNG/SVG/PDF export |

**Best multi-format option:** `antoinebou12/uml-mcp` or `tohachan/diagram-bridge-mcp` — both support many formats and output PNG/SVG.

---

## 5. Browser-Based Rendering Workflow (Playwright)

**Already available in this workspace** via the Playwright MCP server.

**Workflow pattern:**
1. Claude Code writes HTML/CSS/JS to a local file
2. Uses `browser_navigate` to open `file:///path/to/mockup.html`
3. Uses `browser_take_screenshot` to capture the rendered result
4. Claude examines the screenshot and iterates

**Real-world validation:** Multiple Reddit posts confirm this workflow:
- One user saves mockups as HTML with LiveReload, Claude screenshots and iterates automatically
- Another built a 30-line CDP MCP server for the same loop (screenshot -> generate HTML variants -> screenshot again)
- The pattern works well for CSS debugging and UI iteration

**Strength:** No additional MCP server needed — you already have Playwright. Claude can generate arbitrarily complex HTML/CSS mockups and screenshot them.

**Limitation:** Requires manual orchestration in prompts. No native "design mode" — you have to tell Claude to use this pattern.

---

## 6. AI Image Generation MCP Servers

For generating actual images (photos, illustrations, complex visual assets) rather than structured diagrams:

| Server | Backend | Notes |
|--------|---------|-------|
| **GongRzhe/Image-Generation-MCP-Server** | Replicate Flux | Text-to-image via Replicate API |
| **SureScaleAI/openai-gpt-image-mcp** | GPT-4o / gpt-image-1 | OpenAI image gen + editing APIs |
| **qhdrl12/mcp-server-gemini-image-generator** | Google Gemini Flash | Text-to-image, active development |
| **shinpr/mcp-image** | Gemini (multiple models) | Prompt optimization, quality presets |
| **Ichigo3766/image-gen-mcp** | Stable Diffusion WebUI (Forge/A1111) | Local SD instance |
| **guinacio/claude-image-gen** | Google Gemini | Claude Code Skill + MCP server, structured JSON output |
| **MiniMax-AI/MiniMax-MCP** | MiniMax API | Official; also does TTS and video |

**Key fact:** Claude cannot natively generate raster images. All image generation goes through external APIs. These MCP servers bridge that gap.

**For UI mockups specifically:** GPT-image or Gemini image generation could produce screenshot-quality mockups from descriptions, but the results are photorealistic rather than structured/editable.

---

## 7. SVG Generation — Native Claude Capability

**Claude can write SVG directly.** No MCP server needed.

- Claude.ai (web) has "Artifacts" that render SVGs inline as interactive visuals (as of March 2026, Claude creates interactive charts/diagrams/visualizations natively in Artifacts)
- In Claude Code (CLI/VS Code), Claude writes SVG as code to a `.svg` file. The file can be opened in any browser or SVG viewer
- Claude is genuinely good at SVG — it can produce diagrams, icons, simple wireframes, charts, and data visualizations
- For complex UI mockups, HTML/CSS is typically better than raw SVG

**Practical pattern for Claude Code:**
1. Ask Claude to write an SVG file
2. Open it in a browser or VS Code preview
3. Or use Playwright to screenshot it for Claude's visual feedback loop

---

## Summary: What to Use When

| Goal | Best Tool | Maturity |
|------|-----------|----------|
| Architecture diagrams, flowcharts | Excalidraw MCP or draw.io MCP | High |
| Low-fi wireframes | Wirekitty, MockFlow MCP, or Superdesign MCP | Medium |
| Design-to-code / code-to-design | Figma MCP (official) | High |
| Sequence diagrams, UML | uml-mcp or mermaid-mcp-server | High |
| Quick visual mockups | Playwright workflow (HTML->screenshot) | High (already available) |
| SVG icons, simple diagrams | Native Claude SVG output | Built-in |
| Photorealistic UI mockups | Image gen MCP (GPT-image or Gemini) | Medium |
| Multi-format diagrams | diagram-bridge-mcp or uml-mcp | Medium |

---

## Recommended Setup for This Workspace

**Already have:** Playwright MCP (browser rendering workflow is ready to use today)

**Highest-value additions:**
1. **Excalidraw MCP** (e.g., `yctimlin/mcp_excalidraw`) — interactive diagrams with real-time preview
2. **Figma MCP** — if working with designers or needing polished design output
3. **Mermaid MCP** (e.g., `peng-shawn/mermaid-mcp-server`) — for quick diagram rendering to PNG
4. **draw.io MCP** (`@drawio/mcp`) — for editable architecture diagrams
