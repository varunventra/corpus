# PLAN

> Owned by `architect`. One phase = one approval gate. Every phase must be independently runnable and verifiable.

## Project brief

Corpus is a CLI tool that generates and maintains a living second representation of a codebase — per-file docs, folder rollups, and a structural dependency graph — all stored as plain files in `.corpus/`. It serves two audiences from one source of truth: developers get an Obsidian-style visual graph browser, and AI agents (Claude Code) get six precise MCP query tools instead of blind file-crawling. v1 is complete when a developer can point Corpus at a real repo, generate docs and a graph, query it from within Claude Code, and watch the graph light up as the agent works.

## Non-goals — what we are deliberately NOT building

- **No vector search / RAG.** Codebases have exact structure; grep-grade keyword search is deliberate. Similarity search would add a fourth fuzzy copy of the codebase requiring its own sync pipeline.
- **No custom chat UI.** Claude Code is the chat interface. Corpus is plugged into it via MCP. A bespoke chat UI would be weeks of work producing a worse version of something that already exists.
- **No auto-triggering watchers.** `corpus update` is a deliberate command. File-watching on every keystroke or commit is annoyance dressed as magic; automation is a post-core convenience, not a foundation.
- **No AI-decided structure.** The LLM never chooses module boundaries, node identities, or graph topology. Structure is computed deterministically; LLM writes only meaning (prose docs + importance rating).
- **No incremental updates in M1.** Full regeneration every run. Incrementality (M2) is the hardest engineering in the project and slots in without a rewrite because the pipeline is architected for it from day one.
- **No multi-user / cloud / accounts.** Single developer, local machine, free-tier AI, no hosting.
- **No per-node changelog in v1.** Post-core feature; the `.corpus/changelog/` directory is scaffolded but not populated until after M5.

## Stack

| Component | Choice | Justification |
|---|---|---|
| Engine + CLI | Python 3.11+, Click | Best tree-sitter bindings; Click subcommands map cleanly to the five-command surface |
| Parsing | tree-sitter + language grammars | Local AST extraction — deterministic, milliseconds per file, ~36 languages, zero LLM calls |
| Git access | git CLI via subprocess | `git diff -M` gives rename detection and diffs without a Python git library dependency |
| LLM primary | Gemini 2.5 Flash (AI Studio free tier) | ~1,500 req/day, 1M-token context — whole modules in one call |
| LLM fallback | Groq (Llama 3.3 70B free tier) | Auto-retry on Gemini 429s; small per-file patches only due to tight TPM limits |
| MCP server | FastMCP (Python) | Tools as decorated Python functions; stdio transport into Claude Code, no boilerplate |
| Event sidecar | FastAPI + websockets, uvicorn | Tiny localhost sidecar; survives Claude Code session lifecycle; serves static frontend build |
| Frontend | React 18 + Vite | Developer's existing stack; static build on localhost, no hosting needed |
| Graph render | react-force-graph (d3-force) | Force layout, click/hover/zoom out of the box; canvas-based — 500+ nodes stay smooth |
| Storage | Plain markdown + JSON in `.corpus/` | Human-readable, git-diffable, greppable, zero infrastructure |

---

## Phases

### Phase 1a — CLI skeleton + scaffolding `[x]`
**Goal:** `corpus init` runs on a real repo, scaffolds `.corpus/`, respects ignore rules, and lists the files it would process — no LLM, no tree-sitter yet.
**Deliverables:**
- `pyproject.toml` / package installable via `pip install -e .`
- `corpus` CLI entry point with `init` and `update` subcommands (update is a stub that prints "not yet implemented")
- `corpus init` creates `.corpus/corpus.yml`, `.corpus/state.json` (empty), `docs/` tree, and prints the file scan summary
- Ignore logic: `.gitignore` respected + `corpus.yml` defaults (lockfiles, build output, `.corpus/` itself)
- `corpus.yml` default config written to disk with provider, ignore patterns, and budget caps

**Acceptance criteria:**
- [x] `pip install -e .` succeeds and `corpus --help` prints the command list
- [x] `cd` into any git repo, run `corpus init`, and `.corpus/corpus.yml` and `.corpus/state.json` exist on disk
- [x] `corpus init` prints a file count summary ("Found N files — N ignored") without error
- [x] Running `corpus init` a second time does not clobber existing config (prompts or skips gracefully)
- [x] `.corpus/` itself does not appear in the scan list (self-exclusion works)

**Depends on:** Nothing (Phase 1a is the walking skeleton)

---

### Phase 1b — tree-sitter integration → real graph.json `[x]`
**Goal:** `corpus update` parses every tracked file with tree-sitter, extracts symbols and imports, and writes a valid `graph.json` — no LLM calls, human-verifiable output.
**Deliverables:**
- tree-sitter integration for Python (primary) + JavaScript/TypeScript (secondary) with graceful fallback for unsupported languages (node with empty symbols list)
- Node ID assignment: short random strings, stable across runs for unchanged paths
- `graph.json` written to `.corpus/` conforming to the schema in SPEC §04
- `state.json` updated with per-file content hashes and last-run commit hash
- Import/call edge extraction from tree-sitter parse trees

**Acceptance criteria:**
- [x] `corpus update` on a Python repo produces `.corpus/graph.json` that is valid JSON and contains one node per tracked file/directory
- [x] `python -c "import json; d=json.load(open('.corpus/graph.json')); print(len(d['nodes']), 'nodes,', len(d['edges']), 'edges')"` prints non-zero counts
- [x] Re-running `corpus update` on an unchanged repo produces the same node IDs (stability check: `jq '[.nodes[].id]|sort' .corpus/graph.json` output is identical on two consecutive runs)
- [x] A file with known imports (e.g., `import os`) produces at least one edge in `graph.json`
- [x] `.corpus/state.json` contains a `file_hashes` map with an entry for every tracked file


**Depends on:** Phase 1a

---

### Phase 1c — LLM wrapper + per-file docs `[x]`
**Goal:** `corpus update` generates plain-language docs for every tracked file and writes them to `.corpus/docs/`, completing M1 (static brain).
**Deliverables:**
- `llm.py` wrapper: `generate(prompt, max_tokens)` with Gemini 2.5 Flash primary, Groq fallback on 429, structured output parsing, one retry on malformed response
- API key config: read from environment variables (`GEMINI_API_KEY`, `GROQ_API_KEY`), documented in README section
- Per-file doc generation: prompt = file source + symbol list from graph; output = purpose, key symbols, connections, gotchas, importance 1–5
- `.corpus/docs/` tree mirrors repo structure; `_dir.md` rollup files generated from child docs
- `graph.json` updated with `importance` and `doc` path per node
- Hard caps respected: `max_files_per_update`, `max_tokens_per_call`, `max_calls_per_day` from `corpus.yml`; files exceeding cap remain stale with a printed warning
- `corpus init` end-of-run message prints the `claude mcp add corpus ...` registration command

**Acceptance criteria:**
- [ ] `GEMINI_API_KEY=<key> corpus update` on a ~10-file Python repo completes without error and produces one `.md` file per tracked source file under `.corpus/docs/`
- [ ] Each generated doc contains at least a "purpose" paragraph and a "symbols" section (verified by reading 3 sample docs)
- [ ] `cat .corpus/docs/<somefile>.py.md` produces human-readable prose, not JSON or raw prompt
- [ ] `jq '.nodes[] | select(.importance != null) | .importance' .corpus/graph.json` returns numeric values 1–5 for all file nodes
- [ ] Running `corpus update` with `max_calls_per_day: 0` in `corpus.yml` causes zero LLM calls and prints a budget warning
- [ ] A `_dir.md` rollup file exists for every directory that contains tracked files

**Depends on:** Phase 1b

---

### Phase 2 — Incremental updates (M2) `[x]`
**Goal:** `corpus update` re-docs only changed files plus symbol-gated direct importers plus ancestor rollups; a rename preserves node ID; update of ≤15 changed files completes in under 60 seconds.
**Deliverables:**
- Snapshot diff: `git diff -M` between current HEAD and `state.json`'s stored commit hash, supplemented by content-hash comparison for uncommitted edits
- Rename handling: git-detected renames update `path` on existing node; doc file moved to mirror new path; ID/importance/history preserved
- Invalidation logic: re-doc set = changed files ∪ (direct importers where exported symbols changed); max one hop
- Rollup regeneration: only ancestor `_dir.md` files of re-doc'd nodes
- Staleness flag: `stale: true` on nodes whose hash differs from `state.json`; directories stale if any descendant stale

**Acceptance criteria:**
- [x] Edit 3 files in a test repo, run `corpus update`, and confirm via stdout log that only those 3 files (plus any symbol-changed importers) were re-doc'd — not all files
- [x] Rename a file (`git mv old.py new.py`), run `corpus update`, and confirm the node in `graph.json` has the new path but the same `id` as before the rename
- [x] `corpus update` on a repo with 15 changed files completes in under 60 seconds (timed with `time corpus update`)
- [x] An unmodified file's `id` and `importance` are unchanged after an update that touches other files
- [x] `jq '[.nodes[] | select(.stale==true)] | length' .corpus/graph.json` returns the correct count of stale nodes after editing files without running update

**Depends on:** Phase 1c

---

### Phase 3 — MCP bridge + dogfood week (M3) `[x]`
**Goal:** Six MCP tools wired into Claude Code; one week of real daily use; doc format revised from findings.
**Deliverables:**
- `corpus serve --mcp` launches a FastMCP stdio server exposing all six tools: `corpus_overview`, `corpus_doc`, `corpus_relations`, `corpus_find`, `corpus_changes`, `corpus_stale`
- Every tool reads from `.corpus/` (no LLM calls at query time); staleness checked live against working-tree file hashes
- Every tool call POSTs a fire-and-forget event `{tool, node_id, ts}` to the sidecar at `localhost:7077` (silently drops if sidecar not running)
- `claude mcp add corpus` registration documented and tested
- Dogfood: one week of real use on the Corpus repo itself; notes captured in a `DOGFOOD.md` scratch file
- Doc format revision applied based on dogfood notes (≤1 follow-on builder task)

**Acceptance criteria:**
- [ ] `claude mcp add corpus -- python -m corpus.mcp` (or equivalent) registers without error; `claude` lists `corpus` in its tool panel
- [ ] In a Claude Code session, calling `corpus_overview()` returns a project summary without reading any raw source files
- [ ] `corpus_doc("path/to/file.py")` returns the doc for that file including its staleness flag
- [ ] `corpus_find("AuthMiddleware")` returns the node for the file containing that symbol
- [ ] `corpus_stale()` returns a list of all stale nodes (verified by editing a file and calling the tool)
- [ ] After dogfood week, at least one doc format change is implemented and noted in DECISIONS.md

**Depends on:** Phase 1c (Phase 2 recommended but not blocking — stale flags cover the gap)

---

### Phase 4 — Static graph viewer (M4) `[x]`
**Goal:** `corpus serve` opens a browser with a force-directed graph; folders collapse/expand; clicking a node shows its doc; importance shapes visible rank; stale nodes are amber.
**Deliverables:**
- React 18 + Vite frontend in `frontend/`; `corpus serve` builds (or uses pre-built dist) and launches uvicorn serving it on `localhost:7077`
- react-force-graph rendering `graph.json`; dir nodes collapsible; file nodes revealed by importance rank with "show all" toggle
- Click a node → doc panel opens with rendered markdown content fetched from the sidecar
- Stale nodes rendered amber; non-stale nodes teal; collapsed ancestors of stale descendants glow amber
- Sidecar FastAPI routes: `GET /graph` returns `graph.json`; `GET /doc?path=...` returns doc markdown; `WS /events` accepts websocket connections (events stubbed for now)

**Acceptance criteria:**
- [ ] `corpus serve` opens a browser tab (or prints the URL) and the graph renders within 5 seconds on a 200-node repo
- [ ] Clicking a directory node collapses/expands its children without a page reload
- [ ] Clicking a file node opens a side panel with the doc content
- [ ] After editing a file (without running `corpus update`), the corresponding node is amber within the polling interval (≤5 seconds)
- [ ] `curl localhost:7077/graph` returns valid JSON with `nodes` and `edges` arrays
- [ ] On a 200-node repo, pan and zoom remain smooth (no visible frame drops on a normal dev machine)

**Depends on:** Phase 1c (needs `.corpus/` populated), Phase 3 (sidecar architecture established)

---

### Phase 5 — Live wire (M5) `[x]`
**Goal:** Agent queries from Claude Code make the consulted graph nodes light up in real time in the browser — the demo.
**Deliverables:**
- MCP tools POST events to `localhost:7077/event` on every tool call (fire-and-forget, connection errors silently ignored)
- Sidecar fans out `{ev: "query", node, tool, ts}` frames over `WS /events` to all connected frontends
- Frontend websocket client: on `query` event, pulse the named node teal for ~2 seconds; collapsed ancestors glow so activity is visible at any zoom
- On `graph` event (fired after `corpus update`), frontend soft-reloads `graph.json` without full page refresh
- On `stale` event, frontend flips node amber or back without polling

**Acceptance criteria:**
- [ ] In a browser with the graph open, run `corpus_overview()` in Claude Code and confirm the root/overview node pulses teal within 1 second
- [ ] Run `corpus_doc("some/file.py")` and confirm exactly that file's node pulses teal
- [ ] Run `corpus update` and confirm the graph refreshes (node positions may shuffle; content updates) without a manual reload
- [ ] Edit a file; sidecar detects the stale event (via the existing poll or a triggered check) and the node flips amber in the open browser
- [ ] If no browser is open, MCP tool calls complete normally with no errors (event POST silently drops)

**Depends on:** Phase 3 (MCP event emission), Phase 4 (frontend websocket client)

---

---

### Phase 6 — Obsidian-style frontend rework `[ ]`

**Goal:** Replace the current light-theme header+panel layout with a full-screen dark graph experience that feels like Obsidian: graph fills the viewport, a floating command palette handles search and filter, the doc panel is a closeable right drawer, and node/edge rendering conveys staleness and importance through glow and weight rather than color alone.

---

#### What to keep (unchanged)

| Item | Reason |
|---|---|
| `useGraph.js` | Data fetching, WS reconnect, stale polling — correct and stable. No changes. |
| `useDoc.js` | Doc fetching with retry. No changes. |
| All App.jsx logic | `buildDirectChildren`, `buildVisibleIds`, `buildChildCounts`, collapse/expand state, pulseMap, importance filter logic — all stays. Only the rendering shell around it changes. |
| Graph topology and physics | react-force-graph-2d, force simulation, drag/zoom/pan — stays. |
| `nodeCanvasObject` core draw path | Circle shape, selection ring, pulse ring, ▶ badge. Adapted to dark palette, not rewritten from scratch. |

---

#### What changes

| Item | Change |
|---|---|
| `tokens.css` | Full dark palette replacing all light-theme tokens (see palette spec below). |
| `global.css` | Body background now `--color-bg` (dark). |
| `App.jsx` layout | Remove fixed 56px header. Graph fills `100vh`. Floating overlay layer contains command palette trigger and status chip. |
| `GraphCanvas.jsx` | Dark canvas background, new node/edge colors, ambient glow on stale and pulse nodes, labels always on at ≥ 0.15 zoom. |
| `DocPanel.jsx` | Dark surface, updated markdown component colors, breadcrumb row replacing bare path, backlinks section appended below doc body. |
| `ImportanceFilter.jsx` | Moved inside the command palette; removed from the header strip. |
| New: `CommandPalette.jsx` | Cmd+K (Win: Ctrl+K) opens a centered modal input. Searches node labels. Arrow keys navigate results; Enter selects (centers graph + opens doc panel). Esc closes. Includes importance filter buttons below the search input. |
| New: `Minimap.jsx` | Small fixed-position canvas in the bottom-right corner (160×120px). Mirrors graph node positions at 1/8th scale. No interaction — read-only orientation aid. Toggled by a corner button. |

---

#### Palette spec (tokens.css target values)

```
--color-bg:              #0d1117   (GitHub dark; Obsidian uses near-black)
--color-surface:         #161b22   (panel background)
--color-surface-raised:  #21262d   (hover states, badges)
--color-border:          #30363d   (dividers, rings)

--color-text-primary:    #e6edf3
--color-text-secondary:  #8b949e
--color-text-muted:      #484f58

--color-accent:          #7c6af7   (Obsidian purple; replaces red)
--color-accent-dim:      #4a4280   (for glow, shadow-color)

--color-node-fresh:      #7c6af7   (purple — healthy file nodes)
--color-node-dir:        #a5d8ff   (light blue — directory nodes)
--color-node-stale:      #e3b341   (amber — stale nodes; Obsidian warning yellow)
--color-node-pulse:      #ffffff   (white flash on agent query)

--color-edge:            #30363d   (dim, nearly invisible at rest)
--color-edge-hover:      #7c6af7   (accent on hovered node's edges — future)

--color-stale-badge-bg:  #2d1f00
--color-stale-badge-text:#e3b341
--color-panel-accent:    #7c6af7
```

---

#### GraphCanvas visual spec

- **Background:** `--color-bg` (`#0d1117`)
- **File node (fresh):** filled `--color-node-fresh`, radius scales with importance (unchanged formula)
- **File node (stale):** filled `--color-node-stale` amber; ambient glow: `ctx.shadowColor = '#e3b341'; ctx.shadowBlur = 8 / globalScale`
- **Dir node (fresh):** filled `--color-node-dir`; radius 14px
- **Dir node (stale):** filled `--color-node-stale`; same amber glow as stale file nodes
- **Pulse (any node type):** fill `--color-node-pulse` (#ffffff); outer ring pulse: `strokeStyle = --color-accent`, lineWidth 2.5/globalScale; glow: `shadowColor = #7c6af7; shadowBlur = 14 / globalScale`
- **Selection ring:** `--color-accent` at 2.5px, same as today but purple not red
- **Labels:** always visible at zoom ≥ 0.15 (lowered from 0.2); color `--color-text-secondary` (#8b949e); font unchanged (Inter 13px); no background pill needed at this contrast ratio
- **Edges:** color `--color-edge` (#30363d); width 1px (was 1.5px); opacity dim by default — the graph background is dark enough that thin edges read clearly
- **Collapsed dir ▶ badge:** text color `--color-bg` (#0d1117) against the dir node fill; unchanged layout

---

#### App.jsx layout spec

```
<div style="position:relative; width:100vw; height:100vh; background: var(--color-bg)">
  <GraphCanvas />                        /* fills entire viewport */

  /* Floating top-left: project name chip */
  <div class="name-chip" />              /* position: absolute; top:16px; left:16px */

  /* Floating top-right: minimap toggle + status dot */
  <div class="toolbar-corner" />         /* position: absolute; top:16px; right:16px */

  /* Command palette modal — rendered via React portal, centered */
  {paletteOpen && <CommandPalette />}

  /* Doc panel — right drawer, 420px, overlays graph */
  <DocPanel />                           /* position: absolute; top:0; right:0; height:100% */
</div>
```

The header bar is gone. No layout shift when the panel opens — the panel overlays the graph rather than shrinking it. This matches Obsidian's behavior: the graph continues to fill the screen; the panel floats over it.

---

#### DocPanel spec

- **Breadcrumb row** replaces the bare path string. Format: each path segment is a `<span>` separated by ` / `; the last segment is `--color-text-primary`; ancestors are `--color-text-muted`. Clicking an ancestor segment selects the dir node in the graph (calls `onNodeClick` for that dir node).
- **Staleness badge** stays; color updated to new amber tokens.
- **Backlinks section** appended below the doc body. Uses `edges` from `useGraph` — no new API call. Finds all nodes whose `target` is `selectedNode.id`. Renders a flat list: each entry is the source node's filename as a clickable chip. Clicking a backlink chip selects that node (closes current panel, opens the backlink's panel). If there are zero backlinks, the section is hidden entirely.
- **Close button** stays; position unchanged.
- **Panel slides in from right** with `transform: translateX` — same as today but overlay instead of shrink.

---

#### CommandPalette spec

- Trigger: `Cmd+K` (macOS) / `Ctrl+K` (Win/Linux) — `keydown` listener on `document`, active when palette is closed.
- Also triggerable by clicking a small search icon in the top-right toolbar corner.
- **Input:** full-width text input at top of modal. Placeholder: `Search files and folders...`
- **Results list:** filters nodes by `lastName(node.path)` containing the query string (case-insensitive). Max 8 results shown. Each result row: `[type icon] filename  importance dots  path`. Arrow up/down moves selection. Enter: center graph on node + open doc panel (for file nodes) or expand dir node (for dir nodes). Esc: close palette.
- **Importance filter row:** below results (or above if empty query), the existing 7-button strip (All, 1–5). Selecting a level filters the graph and closes the palette.
- **Backdrop:** `position:fixed; inset:0; background:rgba(0,0,0,0.5)` click-to-close.
- **Modal card:** centered, `width: min(520px, 90vw)`, `background: --color-surface`, `border: 1px solid --color-border`, `border-radius: 8px`, `box-shadow: 0 8px 32px rgba(0,0,0,0.6)`.

---

#### Minimap spec

- `<canvas>` element, fixed 160×120px, `position:absolute; bottom:16px; right:16px`.
- Draws once per second via `requestAnimationFrame` gated on a 1s interval (not every frame — low priority).
- Uses `graphData.nodes` positions (set by force simulation) to paint dots at 1/8th scale. Same color mapping as the main canvas (fresh = purple, stale = amber, dir = blue).
- A white rectangle indicates the current viewport (derived from `fgRef.current.centerAt()` and `zoom()`).
- Minimap has a thin `--color-border` border and `border-radius: 6px`. It is hidden by default; a `[⊞]` button in the top-right corner toggles it.
- No click-to-navigate interaction in Phase 6. That is explicitly parked.

---

#### New files

| File | Purpose |
|---|---|
| `frontend/src/components/CommandPalette.jsx` | Full-screen modal with search input, results list, importance filter strip |
| `frontend/src/components/Minimap.jsx` | Small read-only canvas showing graph overview |

#### Modified files

| File | Change summary |
|---|---|
| `frontend/src/styles/tokens.css` | All tokens replaced with dark Obsidian palette |
| `frontend/src/styles/global.css` | No structural changes; inherits new tokens |
| `frontend/src/App.jsx` | Remove header; add absolute-positioned overlay layout; wire CommandPalette and Minimap; graph fills viewport; DocPanel becomes overlay not shrink |
| `frontend/src/components/GraphCanvas.jsx` | New node/edge colors and glow; lower label zoom threshold; thin edges; updated constants |
| `frontend/src/components/DocPanel.jsx` | Breadcrumb row; backlinks section; dark markdown component styles; overlay positioning |
| `frontend/src/components/ImportanceFilter.jsx` | Moved into CommandPalette; this component still exists and is imported there |

---

**Deliverables:**
1. Dark Obsidian palette in `tokens.css` — all CSS variables replaced; no light-theme values remain
2. `GraphCanvas.jsx` — dark bg, purple fresh / amber stale / white pulse nodes, ambient glow on stale and pulse, thin dim edges, labels at ≥ 0.15 zoom
3. `App.jsx` — header removed, graph fills viewport, DocPanel is an overlay, floating name chip and toolbar corner
4. `DocPanel.jsx` — breadcrumb path row, backlinks section from existing graph edges, dark markdown styles
5. `CommandPalette.jsx` — Ctrl+K trigger, node search, arrow-key navigation, importance filter strip embedded
6. `Minimap.jsx` — read-only 160×120 canvas, toggled by corner button, 1s refresh rate
7. All existing behaviors preserved: collapse/expand, stale polling, WS pulse events, importance filter, retry on error

**Acceptance criteria:**
- [ ] `cd frontend && npm run dev` serves the app with a dark background (`#0d1117`); no white flash or light-theme remnant visible anywhere in the UI
- [ ] On a graph with at least one stale node, that node renders amber and has a visible soft glow; a fresh node renders purple
- [ ] Pressing `Ctrl+K` (or `Cmd+K`) opens the command palette; typing a filename filters results; pressing `Enter` on a result centers the graph on that node and opens its doc panel; `Esc` closes the palette
- [ ] Clicking a file node opens the doc panel as an overlay (graph behind it still visible and interactive); the panel header shows a breadcrumb (`src / components / GraphCanvas.jsx`, not the flat path)
- [ ] The backlinks section in the doc panel lists at least one entry for a file that is imported by another file; clicking that entry switches the panel to the backlink's doc
- [ ] The minimap toggle button in the top-right corner shows/hides the 160×120 minimap; the minimap displays colored dots corresponding to visible nodes
- [ ] An MCP `corpus_doc()` call in Claude Code still pulses the target node white with a purple glow ring — live wire behavior is unbroken
- [ ] The importance filter in the command palette (All, 1–5 buttons) filters graph nodes identically to how the old header filter did
- [ ] `npm run build` produces a dist with no build errors; `corpus serve` opens the dark-themed app in the browser

**Depends on:** Phase 5 (complete — all graph data, WS events, and sidecar infrastructure are in place; Phase 6 is a pure frontend change)

---

---

### Phase 7 — "Sahara" warm theme + three-column layout + five functional tabs `[ ]`

**Goal:** Replace the Phase 6 Obsidian dark experience with the "Sahara" warm light theme from the Stitch design file: three-column layout (File Tree | Center | Doc Reader), five nav tabs each rendering distinct content, and a fully redesigned Doc Reader panel — while leaving all data hooks and Python backend untouched.

---

#### Non-goals for Phase 7

- No dark mode toggle. Sahara is the only theme. `prefers-color-scheme` media query is not added.
- No Minimap. The Minimap component introduced in Phase 6 is removed from the layout. It is parked for a later phase.
- No Command Palette (Ctrl+K). Replaced by the top-nav search input and tab navigation. The `CommandPalette.jsx` component is removed from the rendered tree.
- No per-node history or changelog rendering in the Doc Reader.
- No backend changes of any kind: `useGraph.js`, `useDoc.js`, all Python, all MCP tools, `.corpus/` storage are completely untouched.

---

#### Palette — Sahara tokens (exact values from Stitch `code.html` Tailwind config)

```
--color-bg:                  #faf5ee   (background / surface-bright)
--color-surface:             #faf5ee   (same — body background)
--color-surface-low:         #f6f0e8   (surface-container-low)
--color-surface-container:   #f2ece4   (surface-container)
--color-surface-high:        #ece6dc   (surface-container-high / surface-variant)
--color-surface-highest:     #e6e0d6   (surface-container-highest)
--color-surface-white:       #ffffff   (surface-container-lowest)
--color-surface-dim:         #dcd6cc   (surface-dim)

--color-border:              #d8d0c8   (outline-variant)
--color-border-strong:       #9a9088   (outline)

--color-text-primary:        #3a302a   (on-surface / on-background)
--color-text-secondary:      #605850   (on-surface-variant / on-secondary-container)
--color-text-muted:          #9a9088   (outline)

--color-accent:              #c2652a   (primary / surface-tint)
--color-accent-dim:          #fbe8d8   (primary-fixed)
--color-accent-container:    #e08850   (primary-container)
--color-accent-inverse:      #f0a878   (inverse-primary / primary-fixed-dim)

--color-node-dir:            #c2652a   (primary — sienna fill for dir nodes)
--color-node-file:           #ffffff   (surface-container-lowest — white fill for file nodes)
--color-node-stale:          #f59e0b   (amber-500 from Stitch pulse-amber animation)
--color-node-pulse:          #14b8a6   (teal-500 from Stitch pulse-teal animation)
--color-node-selected-border:#c2652a   (primary)

--color-edge:                #d8d0c8   (outline-variant, 0.6 opacity per Stitch svg-line)
--color-edge-active:         #c2652a   (primary — active connection, per Stitch svg-line.active)

--color-stale-badge-bg:      rgba(245,158,11,0.10)   (amber-500/10)
--color-stale-badge-border:  rgba(245,158,11,0.20)   (amber-500/20)
--color-stale-badge-text:    #92400e   (amber-800)

--color-panel-accent:        #c2652a

--font-headline: 'EB Garamond', serif
--font-body:     'Manrope', sans-serif
--font-mono:     'JetBrains Mono', 'Fira Code', monospace
```

Google Fonts import string (added to `index.html`):
```
https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400..800;1,400..800&family=Manrope:wght@200..800&display=swap
```

---

#### Layout spec — three columns

```
┌─────────────────────────────────────────────────────────────────┐
│  [Corpus]  Explorer  Architecture  Dependencies  Symbols  Overview   [Search]  ⚙ ↺  │  h-16, bg-surface, border-b border-border
├──────────────┬─────────────────────────────────┬────────────────┤
│  File Tree   │   CENTER (tab-dependent)        │  Doc Reader    │
│  260px wide  │   flex-1                        │  450px wide    │
│  toggleable  │                                 │  slides in/out │
│  bg-surface- │   bg-bg                         │  bg-surface-   │
│  container-  │                                 │  white         │
│  low         │                                 │                │
└──────────────┴─────────────────────────────────┴────────────────┘
```

The three-column layout is a permanent flex row. The File Tree sidebar has `width: 260px`, `flex-shrink: 0` and is hidden (`display: none` / `width: 0`) when toggled off. The Doc Reader panel has `width: 450px`, `flex-shrink: 0` and slides in via `transform: translateX(450px)` when closed — same slide-in mechanic as Phase 6 but now it displaces layout instead of overlaying.

---

#### Top nav

- `<header>` — `height: 64px`, `background: var(--color-surface)`, `border-bottom: 1px solid var(--color-border)`, `font-family: var(--font-headline)`.
- Left cluster: "Corpus" wordmark in EB Garamond `text-2xl font-medium text-accent` + 5 tab links (`Explorer`, `Architecture`, `Dependencies`, `Symbols`, `Overview`). Active tab: sienna text + 2px bottom border in accent color. Inactive: text-secondary, hover text-accent.
- Right cluster: search input (rounded-full, `w-64`), Settings icon button, Refresh icon button (triggers `window.location.reload()`), File Tree toggle button (icon: `account_tree` or a sidebar icon; toggles left panel visibility).
- The `ImportanceFilter` strip is removed from all surfaces. Importance filtering is not available in Phase 7 (parked — the five tabs replace it as the primary navigation model).

---

#### Left sidebar — File Tree

**Data source:** `graphData.nodes` from `useGraph`.

**Behavior:**
- Builds a collapsible directory tree from node paths. Root-level dirs are expanded by default. Sub-dirs collapsed by default.
- Click a dir row → toggle collapse/expand of that dir's children.
- Click a file row → calls `handleNodeClick(node)` which selects it on the graph AND opens Doc Reader.
- Stale indicator: a 10px amber dot (`bg-amber-500`) positioned to the right of the file/dir name, shown when `staleMap.get(node.id) === true`.
- Selected file: row background `var(--color-surface-container)`, left border `3px solid var(--color-accent)`, text color `var(--color-accent)`.
- Dir rows: EB Garamond, `font-weight: 600`, text-primary. Expand/collapse caret (`▶` rotates to `▼` when expanded) on the left.
- File rows: Manrope, `font-weight: 500`, text-secondary. Indented by `16px` per depth level.
- Overflow: `overflow-y: auto`. No footer inside the sidebar.

**Toggle:** A button in the top nav (top-right cluster) toggles `fileTreeVisible` state. When `false`, the sidebar `div` gets `width: 0; overflow: hidden` (no re-layout shift — the center column expands into the space).

---

#### Center column — 5 tabs

State: `activeTab` in App — one of `'explorer' | 'architecture' | 'dependencies' | 'symbols' | 'overview'`. Default: `'explorer'`.

**Tab 1 — Explorer**

Renders `<GraphCanvas>` re-skinned to warm palette. All existing collapse/expand, pulse, stale logic preserved. Graph fills the center column's remaining height (`flex: 1`). Zoom controls remain (bottom-left of center column). Stats bar remains. No importance filter buttons.

**Tab 2 — Architecture**

Renders `<GraphCanvas>` with a filtered dataset:
- `archNodes`: only nodes where `node.type === 'dir'`.
- `archLinks`: for each original edge `(source_file_id, target_file_id)`, look up both nodes. If they belong to different parent directories, emit an edge `(source_dir_id, target_dir_id)`. Deduplicate. Only include edges where both dir nodes exist in `archNodes`.
- Clicking a dir node opens the Doc Reader for that dir's `_dir.md` (uses existing `useDoc` path resolution — dir nodes have `node.doc` pointing to `_dir.md`).
- Same zoom controls. Same stale logic. Same pulse logic.

**Tab 3 — Dependencies**

Two sub-states:
1. **No file selected:** render a centered prompt — EB Garamond italic, `text-xl`, text-secondary: "Select a file to explore its dependency graph."
2. **File selected (`selectedNode` is not null and `selectedNode.type === 'file'`):** render a mini force graph. Dataset:
   - Center node: `selectedNode`.
   - Outgoing (imports): all nodes reachable via edges where `edge.source === selectedNode.id` (files this node imports), up to 2 hops.
   - Incoming (imported-by): all nodes where `edge.target === selectedNode.id`, up to 2 hops.
   - Links: all edges between nodes in the above set.
   - This uses the same `<GraphCanvas>` component with a subset `graphData`. Clicking any node in the subgraph calls `handleNodeClick` normally.

**Tab 4 — Symbols**

A searchable flat table. No graph canvas.

Layout:
```
[  Search: _______________________ ]   (Manrope input, full-width, rounded-lg, border)
┌─────────────────┬──────────┬──────────────────────────┐
│  Name           │  Kind    │  File                    │
├─────────────────┼──────────┼──────────────────────────┤
│  JWTAuthenticator│ CLASS   │  api/auth.py             │
│  verify_session │ FUNCTION │  api/auth.py             │
└─────────────────┴──────────┴──────────────────────────┘
```

Data: iterate all nodes, for each `node.symbols` array, emit rows `{ name: sym.name, kind: sym.kind, file: node.path, nodeId: node.id }`. Flatten into one array, sort by name.

Search: filters by `name.toLowerCase().includes(query.toLowerCase())` on every keystroke (no debounce needed at this scale).

Click a row: calls `handleNodeClick` for that file node + switches to Explorer tab so the user can see the graph context.

Kind badge: small pill — `background: color-accent-dim`, `color: color-accent`, `font-size: 10px`, `font-weight: 700`, uppercase.

**Tab 5 — Overview**

A non-graph dashboard. Scrollable. No canvas.

Sections (top to bottom):

1. **Stat chips row** — four chips in a flex row:
   - Total Files: count of nodes where `type === 'file'`
   - Total Dirs: count of nodes where `type === 'dir'`
   - Total Edges: `edges.length`
   - Stale: count of nodes where `staleMap.get(id) === true`
   Each chip: rounded-xl, bg-surface-container, border, EB Garamond `text-3xl font-bold text-accent` for the number, Manrope `text-xs text-secondary` for the label below.

2. **About this project** — heading "About" in EB Garamond `text-xl`. Body: fetches the root `_dir.md` via `/doc?path=_dir.md` (or the path of the root dir node if it exists). Renders as `<ReactMarkdown>` with Sahara-themed `mdComponents`. Shows "No project doc found." if fetch fails.

3. **Most Important Files** — heading "Most Important" in EB Garamond `text-xl`. Top 5 nodes by `node.importance` descending (file nodes only, skip null importance). Each row: file name in Manrope `font-semibold`, importance score as a sienna pill, path in text-muted. Clicking a row: selects node + switches to Explorer tab.

4. **Most Connected** — heading "Most Connected" in EB Garamond `text-xl`. Top 5 file nodes by `(in-degree + out-degree)` across all edges. Same row layout. Clicking: same behavior.

5. **Stale Files** — heading "Stale Files" in EB Garamond `text-xl`. Lists all nodes where `staleMap.get(id) === true`. If none: "All files are up to date." in text-muted italic. Each row: amber dot + file name, path in text-muted. Clicking: selects node + switches to Explorer tab.

---

#### Doc Reader panel (replaces DocPanel.jsx behavior, same file)

Width: `450px`. Position: right column in flex row. Slides in/out via `transform: translateX(450px)` when `panelOpen === false`. Background: `var(--color-surface-white)` (`#ffffff`).

**Header** (sticky, `border-bottom: 1px solid var(--color-border)`):
- Row 1: file-type icon (derives from extension — `.py` → `description` material icon or a text label "PYTHON MODULE"; `.js`/`.jsx`/`.ts`/`.tsx` → "JAVASCRIPT"; `.md` → "MARKDOWN"; dir → "DIRECTORY"; other → "FILE") in `color-accent`, next to a Manrope `text-xs font-semibold uppercase tracking-wider text-accent` type label.
- Row 2: EB Garamond `text-3xl font-bold text-on-surface` filename (just the `lastName(node.path)`).
- Row 3: "Last updated N days ago" in Manrope `text-sm text-secondary`. For now, if `node.stale === true` show "Documentation may be outdated"; otherwise show "Up to date". (Precise date is not in the graph schema; this is a placeholder.)
- Right side of header: Edit button (`vscode://file/{repoRoot}/{node.path}` deep link — opens the file in VS Code) + Close button.

**Stale warning box** (only when stale): amber banner below header (inside the scrollable body). Exact styling from Stitch: `bg-amber-500/10 border border-amber-500/20 rounded-xl`, amber warning icon + "Documentation Stale" heading + explanation text.

**Body** (scrollable `flex-1 overflow-y-auto`):

1. **Purpose paragraph** — EB Garamond italic `text-lg text-on-surface`, pulled from the doc markdown (the `## Purpose` or first paragraph of the fetched doc). Rendered inside the `<ReactMarkdown>` body.
2. Full doc markdown rendered with Sahara `mdComponents` (warm color equivalents of Phase 6's dark `mdComponents`).
3. **Key Symbols section** — heading "Key Symbols" in EB Garamond `text-xl`. For each entry in `node.symbols`:
   - A card: `bg-surface rounded-xl border border-border p-4`.
   - KIND badge: `bg-accent/10 text-accent text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wide` (matches Stitch exactly).
   - Symbol name: `font-bold text-primary` next to the badge.
   - Description: `text-sm text-secondary` below (if `sym.description` exists; otherwise omit).
4. **Dependencies section** — heading "Dependencies" in EB Garamond `text-xl`. For each outgoing edge from this node (edges where `source === node.id`), render a list item: arrow-forward icon + linked file name. Uses same `edges` prop already passed to DocPanel.
5. **Open in Editor button** — full-width button at the bottom of the panel body (not sticky footer). `href="vscode://file/{repoRoot}/{node.path}"`. Styled: `border border-accent/30 text-accent hover:bg-accent/5 rounded-lg`.

`repoRoot` derivation: The sidecar already knows the corpus dir. Add a `GET /meta` endpoint to `server.py` that returns `{ repo_root: str }` (the resolved absolute path of the directory `corpus serve` was launched from). Frontend fetches this once on mount in `useGraph` or a new `useMeta` hook and stores it in state for the "Open in Editor" link.

**Breadcrumb row** — kept from Phase 6 but restyled to Sahara palette. Manrope `text-sm`. Same click-ancestor-to-select behavior.

**Backlinks section** — kept from Phase 6. Restyled chips: `bg-surface-container border-border text-secondary hover:border-accent hover:text-accent`.

---

#### GraphCanvas changes (warm re-skin)

All draw logic preserved exactly. Only the color constants change:

```js
// Phase 7 Sahara palette constants in GraphCanvas.jsx
COLOR_BG           = '#faf5ee'
COLOR_NODE_FILE    = '#ffffff'          // white fill, file nodes
COLOR_NODE_DIR     = '#c2652a'          // sienna fill, dir nodes
COLOR_NODE_STALE   = '#f59e0b'          // amber-500
COLOR_NODE_PULSE   = '#14b8a6'          // teal-500 (active query)
COLOR_NODE_SELECTED_BORDER = '#c2652a'  // sienna selection ring
COLOR_EDGE         = 'rgba(216,208,200,0.6)'  // outline-variant at 0.6 opacity
COLOR_EDGE_ACTIVE  = '#c2652a'          // sienna (future hover; unused now)
COLOR_LABEL        = '#605850'          // on-surface-variant
COLOR_ACCENT       = '#c2652a'          // for selection ring + pulse ring
```

Node draw logic adjustments:
- File node (not selected, not stale, not pulsing): white fill (`#ffffff`), thin border `1px` in `#d8d0c8` (outline-variant). To draw a border on canvas: stroke a circle after fill. `strokeStyle = '#d8d0c8'; lineWidth = 1/globalScale`.
- File node (selected): white fill + sienna border `2.5px`, same as current selection ring.
- File node (stale): amber fill `#f59e0b` + soft amber glow (`shadowColor = '#f59e0b'; shadowBlur = 8/globalScale`).
- File node (pulsing): teal fill `#14b8a6` + teal glow ring. The outer ring pulse: `strokeStyle = '#14b8a6'; lineWidth = 2.5/globalScale`. Glow: `shadowColor = '#14b8a6'; shadowBlur = 14/globalScale`.
- Dir node: sienna fill `#c2652a`. No border. Badge text: white (`#ffffff`) against sienna.
- Grid background: replace the dark grid lines with `rgba(58,48,42,0.04)` (warm near-transparent lines on linen background).
- Label font: change to `"12px 'Manrope', sans-serif"`. Label color: `#605850`.
- Label zoom threshold: keep at `>= 0.15`.
- Edge width: keep `1px`. Edge color: `rgba(216,208,200,0.6)`.

---

#### New files

| File | Purpose |
|---|---|
| `frontend/src/components/FileTree.jsx` | Collapsible directory/file tree from graph nodes |
| `frontend/src/components/tabs/ExplorerTab.jsx` | Thin wrapper: renders GraphCanvas with full graphData |
| `frontend/src/components/tabs/ArchitectureTab.jsx` | Dir-only filtered graph; cross-folder edge derivation |
| `frontend/src/components/tabs/DependenciesTab.jsx` | No-selection prompt or 2-hop subgraph around selected node |
| `frontend/src/components/tabs/SymbolsTab.jsx` | Searchable symbol table |
| `frontend/src/components/tabs/OverviewTab.jsx` | Dashboard: stats, about, most important, most connected, stale list |
| `frontend/src/hooks/useMeta.js` | Single `GET /meta` fetch; returns `{ repoRoot }` |

#### Modified files

| File | Change |
|---|---|
| `frontend/src/styles/tokens.css` | All tokens replaced with Sahara warm palette; font stack updated to EB Garamond + Manrope |
| `frontend/index.html` | Add Google Fonts link for EB Garamond + Manrope |
| `frontend/src/App.jsx` | Three-column layout; 5-tab nav; File Tree toggle state; active tab state; remove CommandPalette and Minimap from render tree; wire new tab components; pass `repoRoot` down to DocPanel |
| `frontend/src/components/GraphCanvas.jsx` | Sahara color constants; file node border stroke; warm grid background; Manrope label font |
| `frontend/src/components/DocPanel.jsx` | Sahara palette mdComponents; header with type label + EB Garamond filename; stale warning in amber-500 Stitch style; Key Symbols cards in Stitch layout; Dependencies list; Open in Editor button; update breadcrumb + backlinks chip styles |
| `corpus/server.py` | Add `GET /meta` route returning `{ repo_root: str }` |

#### Deleted / removed from render tree

| Item | Reason |
|---|---|
| `CommandPalette.jsx` | Replaced by top-nav search + tab navigation. File may remain on disk but is not imported or rendered. |
| `Minimap.jsx` | Parked. File may remain on disk but is not imported or rendered. |
| `ImportanceFilter.jsx` | Not used in Phase 7. File may remain on disk but is not imported or rendered. |

---

**Acceptance criteria:**

- [ ] `cd frontend && npm run dev` serves the app; body background is `#faf5ee` (warm linen); no dark surfaces visible anywhere; EB Garamond renders for the "Corpus" wordmark and panel headings; Manrope renders for nav links and body text
- [ ] The left File Tree sidebar is visible by default, showing the directory/file hierarchy; clicking the toggle button in the top nav hides it (center column expands); clicking again shows it
- [ ] A stale file in the File Tree shows a 10px amber dot to the right of its name
- [ ] Clicking a file name in the File Tree selects that node in the Explorer graph AND opens the Doc Reader panel to the right
- [ ] The top nav has exactly 5 tab links: Explorer, Architecture, Dependencies, Symbols, Overview; clicking each switches the center content without a page reload
- [ ] Explorer tab: the force-directed graph renders with `#faf5ee` background, sienna dir nodes, white file nodes with thin gray border, amber stale nodes; clicking a node selects it and opens the Doc Reader
- [ ] Architecture tab: only dir-type nodes are visible; edges exist only between dirs that have cross-folder import edges in the original graph; clicking a dir node opens the Doc Reader showing that dir's rollup doc
- [ ] Dependencies tab with no file selected: shows the centered italic prompt "Select a file to explore its dependency graph."; after clicking a file node in any other tab, the Dependencies tab shows a mini subgraph with the selected file at center
- [ ] Symbols tab: table renders with Name/Kind/File columns; typing in the search box filters rows instantly; clicking a row switches to Explorer tab and selects that file's node
- [ ] Overview tab: stat chips display correct counts (verified by comparing with `jq '.nodes | length' .corpus/graph.json` for node count); Most Important list shows up to 5 nodes; Stale Files list matches nodes where stale is true
- [ ] Doc Reader panel (right column): header shows file-type label + EB Garamond filename + stale/up-to-date line; Edit button opens a `vscode://file/...` link; Close button slides panel away; stale warning box (amber, Stitch style) appears only when node is stale
- [ ] Doc Reader Key Symbols section shows symbol KIND badge in sienna + name for each entry in `node.symbols`; Dependencies section lists outgoing edges as arrow + filename
- [ ] An MCP `corpus_doc()` call in Claude Code pulses the target node in teal (`#14b8a6`) with a glow ring — live wire behavior is unbroken
- [ ] `GET localhost:7077/meta` returns JSON with a `repo_root` key containing an absolute path string
- [ ] `npm run build` completes with no errors; `corpus serve` opens the warm-themed three-column layout in the browser

**Depends on:** Phase 6 (complete — all graph data, WS events, sidecar infrastructure, and Phase 6 components are the baseline being reskinned)

---

### Phase 8 — GitHub dark theme retrofit `[x]`

**Goal:** Wholesale-replace the "Sahara" warm light theme with a GitHub-dark-mode-style theme, using the user-supplied token/typography/structural spec verbatim — a pure CSS/token/typography pass with zero component structure, layout, routing, state, or functionality changes.

**Scope constraint (binding):** If achieving any requirement below would require moving a component, adding/removing a prop or handler, or restructuring JSX (not just its inline `style` object or a CSS file), that requirement is skipped and flagged in the PR, not implemented.

---

#### Non-goals for Phase 8

- No light mode, no `prefers-color-scheme` toggle. GitHub-dark is the sole theme, same as Sahara was. (User confirmed this explicitly — supersedes the Sahara-only decision the same way Phase 7 superseded Phase 6.)
- No new components, no Button/Card/Input/Modal primitives extracted. This codebase has no such shared primitives today (styling is inline `style={{...}}` objects per component, not a component library) — Phase 8 edits those inline objects' *values* in place, it does not refactor them into shared components. Extracting primitives is a real refactor and is explicitly out of scope.
- No change to `useGraph.js`, `useDoc.js`, `useMeta.js`, any Python/backend file (other than what's already true — none), MCP tools, or `.corpus/` storage.
- No restyle of `CommandPalette.jsx`, `Minimap.jsx`, `ImportanceFilter.jsx`. These three components exist on disk but are **not imported or rendered** anywhere (confirmed Phase 7 decision — dead code). Restyling unrendered code has zero user-visible effect; leaving their Sahara-era literal colors in place is fine. Parking-lot note added instead.
- No redesign of layout, tab structure, or the five-tab / three-column model. Only surface treatment changes.

---

#### Token mapping — GitHub dark primitives (user spec, verbatim) → existing app-specific CSS variable *names*

Per the user's own implementation instruction ("preserve variable *names* already in use where possible — just remap their values"), `tokens.css`'s existing variable names stay; only values change. The user's spec gives generic GitHub primitives but this app's `tokens.css` has Corpus-specific slots (`--color-node-dir`, `--color-node-pulse`, etc.) that the generic spec doesn't address 1:1. The mapping below applies the given primitives to those slots. **This mapping is a judgment call, not given literally in the user's spec — flagged for a quick confirmation before `builder` starts, not a request to redesign the palette.**

```
--color-bg                 → --color-canvas-default   #0d1117
--color-surface             → --color-canvas-overlay   #161b22   (was Sahara "surface"; used for header/nav bg)
--color-surface-low         → --color-canvas-subtle    #161b22   (FileTree sidebar bg)
--color-surface-container   → #21262d                            (hover/active row backgrounds)
--color-surface-high        → #21262d
--color-surface-highest     → #30363d
--color-surface-white       → --color-canvas-overlay   #161b22   (DocReader panel bg — GH-dark has no "white" surface; this replaces Sahara's literal #ffffff panel background)
--color-surface-dim         → #010409                  (--color-canvas-inset)

--color-border               → --color-border-default   #30363d
--color-border-strong        → --color-fg-subtle        #6e7681   (nearest "stronger divider" GH offers)

--color-text-primary         → --color-fg-default        #e6edf3
--color-text-secondary       → --color-fg-muted          #7d8590
--color-text-muted           → --color-fg-subtle         #6e7681

--color-accent                → --color-accent-fg         #4493f8
--color-accent-dim            → --color-accent-subtle     rgba(56,139,253,0.15)
--color-accent-container      → --color-accent-emphasis   #1f6feb
--color-accent-inverse        → --color-accent-muted      rgba(56,139,253,0.4)

--color-node-dir               → #4493f8   (dir nodes become blue — nearest GH-dark analog to a folder/info color; no sienna equivalent exists in the spec)
--color-node-file              → --color-canvas-overlay  #161b22 (fill) + border --color-border-default (was white fill + tan border)
--color-node-stale              → --color-attention-fg     #d29922
--color-node-pulse               → --color-success-fg       #3fb950   (user-decided: reuse GH success-green rather than off-palette teal)
--color-node-selected-border      → --color-accent-fg       #4493f8

--color-edge                → --color-border-muted     #21262d (or --color-border-default at reduced opacity — builder's call within these two, cosmetic only)
--color-edge-active           → --color-accent-fg        #4493f8

--color-stale-badge-bg       → rgba(210,153,34,0.10)
--color-stale-badge-border    → rgba(210,153,34,0.20)
--color-stale-badge-text       → --color-attention-fg     #d29922

--color-panel-accent        → --color-accent-fg         #4493f8
```

Add (new, not previously in `tokens.css`, needed to satisfy the user's spec exactly): `--color-success-fg`, `--color-success-emphasis`, `--color-danger-fg`, `--color-danger-emphasis`, `--color-attention-fg`, `--color-attention-emphasis`, `--color-done-fg`, `--color-btn-bg`, `--color-btn-border`, `--color-btn-hover-bg`, `--color-btn-primary-bg`, `--color-btn-primary-hover-bg`, `--shadow-resting`, `--shadow-overlay`, `--color-fg-onEmphasis`, `--color-canvas-inset`. These are added verbatim from the user's spec block even where nothing in Corpus currently consumes them — they establish the token vocabulary for future components without inventing new hex values.

**Typography:**
```
--font-headline → -apple-system, BlinkMacSystemFont, "Segoe UI", Noto Sans, Helvetica, Arial, sans-serif
--font-body     → -apple-system, BlinkMacSystemFont, "Segoe UI", Noto Sans, Helvetica, Arial, sans-serif
--font-mono     → ui-monospace, "SFMono-Regular", "SF Mono", Consolas, "Liberation Mono", monospace
--font-sans     → (alias, unchanged relationship to --font-body)
```
`--font-headline` and `--font-body` collapse to the same system stack per the user's spec ("system font stack, not a display font" — there is no separate display/headline face in GitHub's type system). Components that reference `var(--font-headline)` for large filename/heading text (`DocReader.jsx`, `App.jsx` wordmark, tab headings in `OverviewTab.jsx`) keep their weight/size but inherit the system stack instead of EB Garamond.

---

#### Files this phase must touch

| File | What changes | Why |
|---|---|---|
| `frontend/src/styles/tokens.css` | All values remapped per table above; add the missing GH-spec tokens listed | The single source of truth for CSS custom properties |
| `frontend/src/styles/global.css` | `body` background/color inherit new tokens (no literal `#faf5ee` — currently hardcoded on line 16, must become `var(--color-canvas-default)`); confirm/adjust base `font-size` to 14px (see risk flag) | Root-level typography + the one hardcoded literal color outside tokens.css |
| `frontend/index.html` | Remove the EB Garamond + Manrope Google Fonts `<link>` (line 9). **Keep** the Material Symbols Outlined icon font `<link>` (line 10) — every icon in the app (`search`, `settings`, `refresh`, `folder`, `description`, `close`, `edit`, `warning`, `arrow_forward`, `account_tree`, `history`, `open_in_new`) depends on it; removing it breaks every icon glyph in the UI, which is a functional regression disguised as a font cleanup | Directly named in the task brief; confirmed distinction between display-font removal (in scope) and icon-font removal (out of scope, would break rendering) |
| `frontend/src/components/GraphCanvas.jsx` | The 10 module-level `COLOR_*` JS constants (lines 6–15) remapped to the GH-dark equivalents in the table above; the 3 `FONT_*` constants (lines 17–19) drop `'Manrope'` for the system stack (or monospace — see risk flag on node labels); the two literal `rgba(58,48,42,0.04)` grid-line values (lines 187–188) recolored to a GH-dark-appropriate faint value (e.g. `rgba(230,237,243,0.03)`) | **Decided in-scope** (see reasoning below) — these are pure presentation constants consumed only by `ctx.fillStyle`/`ctx.strokeStyle`; no logic branches on their values |
| `frontend/src/components/DocReader.jsx` | `mdComponents` object (lines 19–30) — all `var(--color-*)` references already token-driven, auto-propagate from `tokens.css`, but hardcoded literals do not: `color: '#d97706'` (line 194, stale warning icon), `color: '#92400e'` (line 196), `color: '#b45309'` (line 197), `border: '1px solid rgba(194,101,42,0.30)'` (line 304, Open-in-Editor button), `rgba(194,101,42,0.05)` hover fill (line 311) — all need direct remap to GH-dark attention/accent equivalents. Also: `backdropFilter: 'blur(8px)'` on the sticky header (line 104) must be **removed** — the user's spec explicitly forbids glassmorphism/blur (spec §4); replace with a solid `var(--color-canvas-overlay)` background, no transparency. Border-radius literals (12, 10, 8, 4, 6, 3 scattered across this file) capped per spec §3 (6px controls, 8px max containers) | Highest concentration of hardcoded Sahara-sienna literals + the one explicit blur violation in the whole codebase |
| `frontend/src/components/FileTree.jsx` | 2 literal `'#f59e0b'` occurrences (stale dot) remapped to `var(--color-attention-fg)` or the literal GH amber; row selection border/background remapped via tokens (already var-driven, should mostly cascade) | Small but non-token literal |
| `frontend/src/components/tabs/ExplorerTab.jsx` | Legend swatches use literal `'#ffffff'`, `'#d8d0c8'`, `'#f59e0b'`, and `rgba(250,245,238,0.92)` translucent overlay backgrounds (lines 14, 55, 61, 65) — all remapped | Stats-bar / legend chip literals |
| `frontend/src/components/tabs/OverviewTab.jsx` | One literal `'#f59e0b'` (stale dot, line 36); stat-chip border-radius/padding audited against §3 density rules | Overview dashboard chips |
| `frontend/src/components/tabs/SymbolsTab.jsx`, `DependenciesTab.jsx`, `ArchitectureTab.jsx` | Border-radius/badge literals audited for the 6/8px cap; no color literals found outside tokens — should mostly cascade from `tokens.css` alone | Confirm-only pass expected, not a rewrite |
| `frontend/src/App.jsx` | Search input `borderRadius: 9999` (line 265, a full pill) **must drop to ≤8px** per spec §3 ("no pill buttons... nothing above [8px]"); tab-active/hover backgrounds already token-driven; `retryBtn`/`fullscreenCenter` shared style objects (bottom of file) — border-radius/colors confirmed against spec | The one clear pill-button spec violation in the codebase today |
| `corpus/server.py` | **Not touched.** No backend file is in scope for this phase. | Confirms the "pure CSS pass" boundary explicitly, since Phase 7 touched `server.py` for `/meta` and a reviewer might otherwise assume symmetry |

**Files intentionally left untouched (parking lot, dead code):** `CommandPalette.jsx`, `Minimap.jsx`, `ImportanceFilter.jsx` — unrendered, no visual effect from restyling them.

---

#### Reasoning: GraphCanvas.jsx JS color constants are in scope

The task brief asks this to be decided explicitly rather than silently expanded. Decision: **in scope**, alongside `tokens.css`. Reasoning:
1. They are pure presentation values — each is consumed only as an argument to `ctx.fillStyle` / `ctx.strokeStyle` / `ctx.shadowColor`; no conditional logic reads or branches on the specific hex value.
2. Editing them changes zero props, handlers, JSX structure, or component boundaries — only the literal string assigned to a `const`.
3. Direct precedent: both Phase 6 (Obsidian) and Phase 7 (Sahara) — the two prior "theme" phases — explicitly re-touched this exact file's color constants as their mechanism for re-skinning the canvas. Treating it as out-of-scope for Phase 8 alone would produce a canvas frozen in Sahara colors while every surrounding surface is GitHub-dark — an incoherent, half-migrated result, which is a worse outcome than the minor scope note this decision requires.

---

#### Risk flags / ambiguities requiring a decision before `builder` starts

1. **RESOLVED by user:** `--color-node-pulse` maps to `--color-success-fg` (`#3fb950`, GitHub success-green) rather than keeping the off-palette teal `#14b8a6` or colliding with dir-node blue. Distinct from stale-amber (`#d29922`) and dir-blue (`#4493f8`), so at-a-glance distinguishability is preserved.
2. **Base font size (§2: "14px, not 16px").** `tokens.css` already defines `--text-base: 13px` and `--text-md: 14px`; `global.css` sets `body { font-size: var(--text-base) }` (13px). Only 4 files in the whole frontend consume the `--text-*` scale directly (`global.css`, and three components — most components hardcode literal `fontSize: 13` / `14` per element instead of using the scale). Net effect: the app is already sub-16px everywhere in practice. Flagging so `builder` doesn't spend time chasing a requirement that's structurally already satisfied — the only real action needed is deciding whether `global.css`'s inherited default moves from 13px to 14px for consistency, which is cosmetically negligible either way.
3. **GraphCanvas node labels (filenames) — sans vs. monospace.** The user's spec says monospace applies to "code, IDs, hashes, or tabular/technical data." A rendered filename on a graph canvas node arguably qualifies as "technical data," but Phase 6/7 both used the body sans font here, and GitHub's own file-tree/graph-like UIs (e.g. the repo file browser) use a sans face for filenames, reserving monospace for actual code/diff content. **Recommend keeping labels on the system sans stack**, not monospace — flagging only so this isn't silently decided without a paper trail.
4. **GraphCanvas grid background technically uses `linear-gradient(...)`** (two 1px repeating lines forming a dot-grid), which is the standard CSS technique for a background grid — not a decorative gradient in the sense the user's §4 "no gradients" rule is targeting (visible color transitions/hero-banner gradients). **Recommend keeping the technique**, only recoloring the `rgba()` value to a GH-dark-appropriate faint tint. Flagged so a literal reading of "no gradients" doesn't strip the grid entirely, which would be a visual regression unrelated to the theme swap.
5. **Spec §3 "only the single primary action per view gets `--color-btn-primary-bg`."** This app currently has no filled/primary CTA button anywhere in the rendered tree — buttons are icon-only (Refresh, Settings, Toggle) or bare-text (Retry, tab links). There is nothing to demote *from* colorful, and nothing that obviously qualifies as "the one primary action" to promote *to* green. **No action needed** — this requirement has no applicable target in the current UI; noting it so it isn't treated as an unmet acceptance criterion later.
6. **`--color-border-strong` mapping.** GitHub's dark palette has no separate "strong border" tier the way Sahara did (`outline` vs `outline-variant`). Mapped to `--color-fg-subtle` (`#6e7681`) as the nearest available "more visible divider" — a judgment call, flagged for the same reason as the node-token mapping table above.

---

**Deliverables:**
1. `tokens.css` — all existing variable names retained, values remapped to the table above; new GH-spec tokens added
2. `global.css` — literal `#faf5ee` background removed in favor of `var(--color-canvas-default)`; font stack confirmed system-only
3. `index.html` — EB Garamond/Manrope Google Fonts link removed; Material Symbols icon link retained unchanged
4. `GraphCanvas.jsx` — 10 color constants + 3 font constants + grid-line rgba remapped; zero changes to draw logic, props, or component structure
5. `DocReader.jsx` — hardcoded Sahara-sienna literals remapped; `backdropFilter: blur(8px)` removed (spec §4 blur ban); border-radius literals capped at 6/8px per §3
6. `FileTree.jsx`, `ExplorerTab.jsx`, `OverviewTab.jsx` — literal `#f59e0b`/`#ffffff`/`#d8d0c8`/translucent-overlay values remapped
7. `SymbolsTab.jsx`, `DependenciesTab.jsx`, `ArchitectureTab.jsx` — confirm-only pass for border-radius/badge compliance with §3
8. `App.jsx` — search input border-radius dropped from `9999` (pill) to ≤8px; other inline literals confirmed against tokens
9. A written resolution (from the user/orchestrator, not invented by `builder`) for risk flags 1–6 above, captured in DECISIONS.md before or alongside phase close-out

**Acceptance criteria:**
- [ ] `cd frontend && npm run dev` serves the app with `#0d1117` as the outermost background — visually confirm via browser: zero warm/tan/cream (`#faf5ee`-family) surfaces remain anywhere, including the DocReader panel (previously literal white) and the search input
- [ ] `grep -c "faf5ee\|EB Garamond\|Manrope" frontend/src/styles/tokens.css frontend/src/styles/global.css frontend/index.html` returns `0` total matches (confirms full replacement of the removed literals/fonts; Material Symbols link is a separate string and is unaffected by this grep)
- [ ] `fg-default` (`#e6edf3`) on `canvas-default` (`#0d1117`) is used for primary body text — visually confirm legible ~13:1 contrast per spec §5.6 (spot-check: nav wordmark, DocReader filename heading, FileTree file rows)
- [ ] Search input in the top nav renders with `border-radius` ≤ 8px, not a full pill (visually confirm rounded corners are subtle, not capsule-shaped)
- [ ] A stale node (in Explorer tab, FileTree, and DocReader stale badge) renders in the GitHub-dark attention/amber tone (`#d29922`-family), not the old Sahara amber (`#f59e0b`) or Sahara badge colors (`#92400e`/`#b45309`)
- [ ] An MCP `corpus_doc()` call in Claude Code still pulses the target node green (`#3fb950`) with a visible glow ring — live-wire behavior is unbroken
- [ ] DocReader panel header no longer has a blurred/translucent sticky background (spec §4 no-blur rule) — visually confirm a solid, opaque header background on scroll
- [ ] `npm run build` completes with zero errors; `npm test` (or `npx vitest run`) shows no new failures beyond the pre-existing documented Phase 6/7 baseline in STATE.md
- [ ] No JSX structure diff in any touched file beyond `style={{...}}` object values, `className`/font-family string literals, and the two named CSS files — verified by `git diff --stat` showing no added/removed lines outside style-value edits (a spot-check, not a strict line-count rule: new opening/closing tags, new props, new components, or moved elements in the diff would indicate scope creep)

**Depends on:** Phase 7 (complete — this phase reskins the exact three-column/five-tab structure Phase 7 built; no new backend or data-layer work)

---

### Phase 9 — Graph UX overhaul: Overview/All-Files modes, label decluttering, layout physics `[x]`

**Goal:** The Explorer tab defaults to a curated "Overview" subgraph (importance- or degree-driven, dirs collapsed) with an explicit "All Files" escape hatch, non-overlapping physics-correct node placement, and legible non-overlapping labels — verified end-to-end on the same real repo (40 nodes / 49 edges) that surfaced the current breakage.

**Binding requirements (already decided with the user — not open for re-litigation; this phase turns them into deliverables/ACs):**
1. Two navigation modes in the Explorer tab: **Overview** (default, importance-curated subgraph + direct dependency edges, dirs collapsed) and **All Files** (explicit toggle, full expanded graph). Overview must degrade gracefully when `node.importance` is null everywhere (the current state of this dev machine — no LLM key set) rather than breaking or silently showing everything.
2. Labels: tighten the existing `globalScale >= 0.15` visibility threshold **and** add real collision-avoidance (nudge-apart, optionally with a leader line) for labels simultaneously visible at a given zoom — both techniques, not either/or.
3. Physics: retune d3-force parameters (charge/repulsion, radius-correct collision force, link distance, zoom-to-fit on load/mode-switch/filter-change) **and** apply a hierarchical/tree-or-radial (d3-hierarchy) initial-placement skeleton keyed to folder structure, with force simulation layered on top for local jitter/separation — both techniques, not either/or.

---

#### Scope note — this phase is Explorer-tab-scoped, but GraphCanvas.jsx is shared

The physics retune, collision force, and label-collision pass live in `GraphCanvas.jsx`, which is also rendered by the Architecture and Dependencies tabs. Those tabs inherit the physics/label improvements for free (that's a good thing — they have the same overlap problems). The **Overview/All-Files mode toggle and curation logic are Explorer-tab-only** in this phase; Architecture and Dependencies tabs keep their existing dataset-filtering logic untouched.

---

#### Non-goals for Phase 9

- **No backend or graph-schema changes.** `.corpus/graph.json`, the importance-scoring LLM pipeline, `staleMap` computation, and all Python code are untouched. This is a frontend rendering/interaction phase only.
- **No curation/mode toggle for Architecture, Dependencies, or Symbols tabs.** Only the Explorer tab gets Overview/All-Files. If those tabs turn out to need the same treatment, that's a future phase.
- **No persistence of the user's mode choice across page reloads or tab switches.** `explorerMode` resets to `'overview'` on every fresh load. LocalStorage persistence is parked, not built.
- **No solving "All Files" legibility beyond layout physics + label decluttering.** No node clustering/aggregation UI, no search-within-graph, no progressive-disclosure-by-scroll for huge repos. All Files on a 1000-node repo may still be dense — that's the accepted trade-off of the explicit escape hatch, not a bug this phase fixes further.
- **No keyboard-shortcut or accessibility pass for the new mode toggle** beyond standard button semantics (`aria-pressed`, focus ring). Full a11y audit is out of scope.
- **No redesign of DocReader or FileTree.** Their content and behavior are unchanged; FileTree's own collapse/expand state is untouched by Explorer-mode switching.

---

#### Process note (per project protocol): designer build-spec required before builder starts

This phase is heavily interaction-design-shaped — a curation algorithm, a mode-switch control, a label-declutter visual treatment, and a badge legibility fix all have multiple reasonable implementations. Per `CLAUDE.md`, `designer` must produce a concrete build spec (exact algorithm, exact thresholds, exact visual treatment, exact placement) before `builder` touches any code. The open questions below are what that spec must resolve — they are not proposals for `architect` to pick between, they're the list `designer` must answer definitively.

**Open design questions for `designer`:**

1. **Overview-mode curation algorithm, importance present:** exact selection rule — e.g. top-N by `node.importance` descending, or `importance >= threshold`, or top-X% capped at an absolute max? Does the selected set always pull in each included node's direct (1-hop) dependency neighbors even if those neighbors score low, per the binding requirement ("high-signal nodes... plus their direct dependency edges")?
2. **Overview-mode curation algorithm, importance absent (this machine's actual current state):** exact fallback — collapsed-dirs-only (show zero file nodes until a dir is expanded) vs. degree-based curation (top-N file nodes by in+out edge degree) vs. a hybrid of both? Exact N or percentage cap?
3. **Does the Overview node cap scale with repo size** (e.g., top 20% capped at 50) or stay a fixed absolute number regardless of repo size (10 nodes on a 40-node repo, 10 nodes on a 2000-node repo)?
4. **Mode-switch UI control:** toggle button / segmented control / dropdown — and exact placement (top-nav right cluster, inside Explorer tab's existing stats-bar/zoom-controls corner, or a new dedicated control). Visual state for "which mode is active."
5. **Label-collision algorithm and visual treatment:** simple iterative push-apart per frame vs. a real label-layout pass; how far a label may be displaced before a leader line is drawn back to its node; leader line style (color, width, dash pattern).
6. **Exact new label zoom threshold** to replace `>= 0.15` — a fixed constant (e.g. `0.35`) or dynamic based on local node density in the current viewport?
7. **Hierarchical/tree-or-radial layout scope:** does the d3-hierarchy initial-placement skeleton apply in both modes, or only in All Files mode (per the binding requirement's framing, "matters most for All Files... on large repos")? If threshold-gated, at what node count does it activate vs. plain force-from-random-start (e.g., only above 60–100 nodes)?
8. **Live-wire pulse interaction with Overview mode's curated-out nodes:** when an MCP `corpus_doc()`/`corpus_overview()` call pulses a node that Overview mode has curated out of the visible set, what happens? Options include: temporarily reveal that node (and its ancestor chain) in Overview mode, auto-switch to All Files, or pulse the nearest visible collapsed ancestor only (the existing `pulseAncestorIds` mechanic). This is currently undefined and must not be left to `builder`'s guess.
9. **Directory child-count badge legibility fix** (the sienna "29"/"6" badges the user mistook for noise): smaller badge treatment, hover tooltip, repositioning, or some combination — exact visual spec (size, position relative to node, background/text color from the GH-dark token set, whether the `▶` glyph and the count should visually separate more clearly).
10. **Overview-mode collapse state:** does Overview mode reuse the exact same `collapsedMap` as All Files mode (so a manual expand/collapse in one mode is visible in the other), or does it maintain a separate mode-scoped collapse state so switching modes doesn't carry over a user's manual expansions?

---

#### Deliverables

1. New pure-logic module — e.g. `frontend/src/lib/graphCuration.js` — exporting a function that takes `(nodes, edges, { hasImportance })` and returns the Overview-mode node/edge subset per designer's resolved algorithm (covers both the importance-present and importance-absent/degree-fallback paths).
2. Mode toggle control (Overview / All Files) wired into the Explorer tab per designer's placement spec; `explorerMode` state (default `'overview'`), reset on fresh load.
3. `GraphCanvas.jsx` — force-simulation retune: increased charge/repulsion (`d3Force('charge').strength(...)`), a collision force sized to each node's actual rendered radius (`d3Force('collide')`), increased link distance, `zoomToFit` triggered on initial load, on Overview/All-Files mode switch, and on any filter change.
4. `GraphCanvas.jsx` — label-collision-avoidance pass per designer's spec (nudge-apart, optional leader line) layered on top of the tightened zoom threshold (replacing the current `>= 0.15` constant).
5. New pure-logic module — e.g. `frontend/src/lib/hierarchyLayout.js` — using `d3-hierarchy` to compute an initial tree/radial position (keyed to folder path) for each node, seeded into the force simulation before it runs, per designer's scope decision (always-on vs. All-Files-only vs. node-count-gated).
6. Directory child-count badge legibility fix in `GraphCanvas.jsx` per designer's exact spec.
7. New dependency: `d3-hierarchy` added to `frontend/package.json`.
8. All existing Explorer-tab behaviors preserved: collapse/expand of dirs, stale amber rendering + glow, live-wire pulse (teal→green already migrated in Phase 8) with ancestor-glow fallback, node click → Doc Reader.
9. **Folded-in bug fix (discrete item, user-approved 2026-07-22):** `DocReader.jsx` (Key Symbols cards) and `SymbolsTab.jsx` treat `node.symbols` entries as `{name, kind, description}` objects, but `graph.json` stores plain strings — make both components shape-tolerant (`typeof sym === 'string'` → name is the string, kind/description absent; object → current behavior), fixing blank symbol names, always-"SYMBOL" badges, dead SymbolsTab search, and `key={sym.name}` React duplicate keys. No visual redesign — same markup, real data. This is the only change either file receives in this phase.

---

#### Files this phase will touch

| File | What changes | Why |
|---|---|---|
| `frontend/src/components/GraphCanvas.jsx` | Force-sim parameter retune (charge, collision keyed to `nodeRadius()`, link distance), `zoomToFit` calls, label-collision/declutter pass layered on the zoom threshold, tightened threshold constant, dir badge legibility fix, seeding hook for hierarchy-layout initial positions | Owns the physics, the canvas draw loop, and the badge rendering already |
| `frontend/src/components/tabs/ExplorerTab.jsx` | Mode toggle control (or its mount point, per designer placement), `explorerMode` state if scoped locally, passes curated vs. full `graphData` to `GraphCanvas`, triggers `zoomToFit` on mode switch | Owns Explorer-tab-only UI; mode toggle lives here unless designer places it in the top nav |
| `frontend/src/App.jsx` | If designer places the mode toggle in the top-nav right cluster (an App-owned region) rather than inside the Explorer tab, `explorerMode` state lifts here instead; wires the curated-vs-full `graphData` computation before passing to `ExplorerTab` | Only touched if designer's placement choice requires it — flagged as conditional, not a guaranteed edit |
| `frontend/src/lib/graphCuration.js` (new) | Pure function(s) implementing the Overview-mode selection algorithm, both importance-present and importance-absent/degree-fallback paths | Keeps curation logic unit-testable in isolation from React/canvas rendering |
| `frontend/src/lib/hierarchyLayout.js` (new) | Pure function(s) wrapping `d3-hierarchy` to compute initial tree/radial coordinates from folder-path structure | Same testability rationale; isolates a new external dependency behind a small surface |
| `frontend/package.json` | Add `d3-hierarchy` dependency | New layout technique requires it — not currently installed (confirmed: only `react-force-graph-2d` and `react-markdown` are current runtime deps) |

**Files explicitly NOT touched by this phase:** `frontend/src/components/FileTree.jsx`, `frontend/src/hooks/useGraph.js`, `frontend/src/hooks/useDoc.js`, `frontend/src/hooks/useMeta.js`, `frontend/src/components/tabs/ArchitectureTab.jsx`, `frontend/src/components/tabs/DependenciesTab.jsx`, `frontend/src/components/tabs/OverviewTab.jsx`, all Python/backend files. (`DocReader.jsx` and `SymbolsTab.jsx` receive exactly one change each: the deliverable-9 symbols shape-tolerance fix — nothing else.)

---

**Acceptance criteria:**

- [ ] On the same real test repo the user tested (40 nodes / 49 edges, no LLM key set → `node.importance` null on all nodes), loading the Explorer tab shows **Overview mode by default**, using the degree-based (or collapsed-dirs-only, per designer's resolved fallback) curation path — the stats-bar node count in Overview is visibly smaller than the full 40-node count.
- [ ] Clicking the "All Files" toggle shows every node — stats-bar node count matches `jq '.nodes | length' .corpus/graph.json` exactly.
- [ ] Switching between Overview and All Files re-triggers `zoomToFit` — all visible nodes are within the viewport bounds without manual panning immediately after the switch.
- [ ] On the same 40-node repo in All Files mode at rest (simulation settled), no two node circles visually overlap — verified by a screenshot spot-check comparable to the one that surfaced this bug, now clean.
- [ ] At a zoom level where 5+ node labels would be simultaneously visible, no two label bounding boxes overlap — at least one label in a dense cluster shows a visibly nudged/offset position (with leader line if designer's spec calls for one) rather than stacking illegibly.
- [ ] The directory child-count badge (e.g., "29", "6") is visually legible as "a directory with N files," per designer's chosen treatment — spot-checked against the original user complaint ("random letters or symbols").
- [ ] An MCP `corpus_doc()` call in Claude Code still triggers the live-wire pulse correctly in both modes, per designer's resolved answer to open question 8 (reveal / auto-switch / ancestor-glow-only).
- [ ] `cd frontend && npm run build` completes with zero errors after adding `d3-hierarchy`; `npm test` (or `npx vitest run`) shows no new failures beyond the documented Phase 6/7/8 baseline in STATE.md.
- [ ] Architecture and Dependencies tabs (which share `GraphCanvas.jsx`) still render correctly post-retune — spot-check that the physics/label changes don't break their existing filtered-dataset rendering.
- [ ] Symbols fix: opening `cli.py` in the Doc Reader shows Key Symbols cards with real names (`main`, `init`, `update`, `serve`, ...) instead of blank rows; the Symbols tab lists real symbol names and typing `main` in its search filters to matching rows; no React duplicate-key warnings in the browser console.

**Depends on:** Phase 8 closing out first (reviewer + qa + STATE.md/DECISIONS.md close-out complete) — Phase 8 and Phase 9 both edit `GraphCanvas.jsx`; `builder` must not start Phase 9 while Phase 8 is still open, to avoid two agents concurrently editing the same file. Also depends on Phase 7 (three-column layout, five tabs, Doc Reader — the structural baseline this phase reskins interaction on top of).

---

## Parking lot

> Ideas deferred mid-work. One line each. Reviewed only during plan revisions — not a backlog to secretly build from.

- Per-node changelog (`corpus/changelog/*.jsonl`) — post-core, SPEC §03 mentions it
- `corpus explain` — plain-English summary of uncommitted diff — post-core command
- Health overlays (churn, last-touched date) on graph nodes
- Onboarding tour mode
- `LATER.md` file for capturing in-session scope-creep ideas (per SPEC build rules)
- Auto-watcher / commit hook convenience wrapper (explicitly cut from v1, may revisit post-M5)
- Per-language grammar coverage beyond Python + JS/TS (add grammars per user demand)
- Paid / local LLM provider support (config-level swap, architecture already supports it)
- Switch `pathspec` dialect from `"gitwildmatch"` to `"gitignore"` in `ignore.py`/`config.py` — `gitwildmatch` deprecated in pathspec 1.1.1, will become breaking in a future release
- `Found 1 files` grammar nit — should be `Found 1 file` (singular)
- `corpus init --help` em-dash mojibake in Windows CP1252 console — encoding issue, not a code bug
- `CommandPalette.jsx` / `Minimap.jsx` / `ImportanceFilter.jsx` still carry Sahara-era literal colors after Phase 8 (unrendered dead code, zero visual impact — restyle only if one of these is ever revived)
- ~~Symbols string-vs-object shape bug (pre-existing since Phase 7)~~ — **folded into Phase 9 as deliverable 9** (user delegated the call 2026-07-22); see that phase's section
- No shared Button/Card/Input/Modal primitive components exist anywhere in the frontend — every component inlines its own `style={{...}}` object, causing color/border-radius values to be duplicated dozens of times across files instead of centralized; a real extraction refactor, out of scope for any theme-only phase
- Phase 9 reviewer NIT: `curateFiles` in `graphCuration.js` uses `Array.includes()` inside its expansion loop (O(n) per edge) instead of a `Set` lookup — fine at current repo scale, will matter on genuinely large repos
- Phase 9 reviewer NIT: Explorer's `ModeToggle` segment padding is `6px 14px`; the design spec's own accessibility-floor fallback suggested `8px 14px` if measured height comes in under 32px — never actually measured. Low stakes, the real keyboard-focus requirement is already covered by the global `:focus-visible` rule.
