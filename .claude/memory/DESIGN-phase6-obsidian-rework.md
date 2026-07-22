# DESIGN SPEC — Phase 6: Obsidian-Style Frontend Rework

> Builder-ready. Every section has exact values. No guessing required.
> Last updated: 2026-07-21

---

## 1. The One Job

Put the graph in complete control of the screen. Every piece of UI is either the graph itself or a temporary layer that appears on demand and disappears when dismissed. Nothing competes with the graph for space.

---

## 2. Layout & Hierarchy

The viewport is a single dark canvas. The eye lands on the graph first because it fills 100% of the window. The second thing visible is the project name in the top-left — a reference anchor, not a nav item. Third is the top-right corner: the Ctrl+K affordance and minimap toggle. The doc panel and command palette are demand-activated overlays; they have no presence in the resting state.

Resting layout (nothing open):

```
┌─────────────────────────────────────────────────────────┐
│ [project-name]          ·  [⌘K]  [⊞]                  │  ← floating chips, z:10
│                                                          │
│                     GRAPH CANVAS                         │
│              (fills entire viewport)                     │
│                                                          │
│                                              [minimap]   │  ← if toggled on, z:10
└─────────────────────────────────────────────────────────┘
```

Panel-open layout:

```
┌─────────────────────────────────────────────────────────┐
│ [project-name]          ·  [⌘K]  [⊞]                  │
│                                        ┌─────────────┐  │
│          GRAPH (full viewport,         │  DOC PANEL  │  │
│          still interactive behind      │  420px wide │  │
│          the panel)                    │  z:20       │  │
│                                        └─────────────┘  │
└─────────────────────────────────────────────────────────┘
```

Command palette open:

```
┌─────────────────────────────────────────────────────────┐
│                ████████████████████████                  │
│                █   COMMAND PALETTE    █                  │  ← modal, z:30
│                █   centered, 520px   █                  │
│                ████████████████████████                  │
│       (backdrop rgba(0,0,0,0.5), z:29)                  │
└─────────────────────────────────────────────────────────┘
```

Z-index ladder: graph = 0, floating chips = 10, doc panel = 20, backdrop = 29, command palette = 30.

---

## 3. All States

### 3a. Loading (initial graph fetch)

Full viewport. Background `#0d1117`. Centered column: spinner or text.

Exact copy: `"Loading graph..."` in `--color-text-muted` (`#484f58`), font-size `--text-base` (13px), `--font-sans`. No spinner animation needed; the text is enough. This state is typically under 500ms on localhost.

### 3b. Error (initial fetch failed)

Full viewport, dark bg. Centered column:

- Line 1: `"Could not connect to Corpus."` — `--color-text-primary`, `--text-md` (14px), weight 500
- Line 2: `"Is corpus serve running on localhost:7077?"` — `--color-text-muted`, `--text-base` (13px)
- Button: `"Retry"` — outlined style: border `1px solid --color-border`, bg `--color-surface-raised`, text `--color-text-secondary`, height 36px, padding `0 16px`, border-radius 6px. On hover: border-color `--color-accent`, text `--color-text-primary`. On click: calls `retry()` from `useGraph`.

Focus: button gets focus automatically when error renders (use `autoFocus` prop or `useEffect` with `.focus()`).

### 3c. Empty graph (nodes.length === 0)

Full viewport, dark bg. Centered column:

- Line 1: `"No files tracked yet."` — `--color-text-primary`, weight 500
- Line 2: `"Run corpus init, then corpus update."` — `--color-text-muted`

No button. The user must go to their terminal.

### 3d. Graph loaded (normal resting state)

Graph renders. Floating chips visible. All overlays hidden.

### 3e. All files hidden by importance filter

The `allFiltered` guard from current App.jsx stays. Render a centered overlay over the graph (not replacing it):

```
position: absolute; top:50%; left:50%; transform: translate(-50%,-50%);
pointer-events: none; z-index: 10;
```

Copy:
- Line 1: `"No files at this importance level."` — `--color-text-primary`
- Line 2: `"Press Ctrl+K and choose All to show everything."` — `--color-text-muted`

### 3f. Doc panel — no doc generated yet

Panel open, `node.doc` is null. Body area shows:

- `"No documentation generated yet."` — `--color-text-muted`
- `"Run corpus update to generate docs."` — `--color-text-muted`

### 3g. Doc panel — loading doc

`"Loading documentation..."` — `--color-text-muted`. No spinner.

### 3h. Doc panel — doc fetch error

- `"Could not load this file's doc."` — `--color-text-muted`
- `"Retry"` button (same style as 3b, but within the panel).

### 3i. Command palette — empty query

Show: importance filter strip only (the 7 buttons). Results area hidden. Placeholder text in input.

### 3j. Command palette — query with no matches

Below the input: `"No files match."` — `--color-text-muted`, centered, 32px top padding.

### 3k. Command palette — query with results

Up to 8 results. Each is a row. Keyboard selection active.

### 3l. Minimap — enabled, graph not yet settled

Dots may be clustered at center during initial force layout. This is expected — no special handling.

### 3m. Minimap — graph empty (no nodes visible after filter)

Minimap canvas clears to `--color-bg`. The border and container still render.

### 3n. Node pulse (query event from MCP)

Node flashes white. Collapsed ancestor dir gets a purple glow ring. After `PULSE_DURATION_MS` (2000ms) the node reverts to its base color. This is existing logic; the visual change is only the new color values.

### 3o. Overflow: long filenames in doc panel breadcrumb

The filename segment (last part) in the breadcrumb truncates with `text-overflow: ellipsis` if longer than panel width minus close-button clearance (approx 340px). Ancestor path segments are also ellipsis-truncated; they each get `max-width: 80px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis`. The full path remains accessible via `title` attribute on the breadcrumb row's outer div.

### 3o2. Overflow: many backlinks (>10)

Show first 10 backlink chips. Below them: `"+ N more"` in `--color-text-muted`. Clicking `"+ N more"` expands to show all. Expansion state is local (useState) within the panel; it resets when `selectedNode` changes.

### 3p. Overflow: 99+ results in command palette

Only first 8 results are ever shown (no "show more"). The result count above the list reads: `"Showing 8 of N"` when there are more than 8 matches.

---

## 4. Tokens (tokens.css)

Replace every existing token. The file should contain exactly this `:root` block and nothing else:

```css
:root {
  /* Surface */
  --color-bg:              #0d1117;
  --color-surface:         #161b22;
  --color-surface-raised:  #21262d;
  --color-border:          #30363d;

  /* Text */
  --color-text-primary:    #e6edf3;
  --color-text-secondary:  #8b949e;
  --color-text-muted:      #484f58;

  /* Accent */
  --color-accent:          #7c6af7;
  --color-accent-dim:      #4a4280;

  /* Node fills */
  --color-node-fresh:      #7c6af7;
  --color-node-dir:        #a5d8ff;
  --color-node-stale:      #e3b341;
  --color-node-pulse:      #ffffff;

  /* Edges */
  --color-edge:            #30363d;

  /* Staleness badge */
  --color-stale-badge-bg:  #2d1f00;
  --color-stale-badge-text:#e3b341;

  /* Panel */
  --color-panel-accent:    #7c6af7;

  /* Typography */
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;

  /* Type scale */
  --text-xs:   10px;
  --text-sm:   12px;
  --text-base: 13px;
  --text-md:   14px;
  --text-lg:   15px;
  --text-xl:   20px;
}
```

**What changed vs. today's tokens.css:**
- `--color-bg` was `#ffffff`, now `#0d1117`
- `--color-surface` was `#fafafa`, now `#161b22`
- `--color-surface-raised` was `#f0f0f0`, now `#21262d`
- `--color-border` was `#e0e0e0`, now `#30363d`
- `--color-text-primary` was `#111111`, now `#e6edf3`
- `--color-text-secondary` was `#333333`, now `#8b949e`
- `--color-text-muted` was `#888888`, now `#484f58`
- `--color-accent` was `#E63946` (red), now `#7c6af7` (purple)
- `--color-accent-dark` renamed to `--color-accent-dim`, value `#4a4280`
- `--color-stale`, `--color-stale-dark` removed; replaced by `--color-node-stale: #e3b341`
- `--color-stale-badge-bg` changed from `#FFF3E0` to `#2d1f00`
- `--color-stale-badge-text` changed from `#E65100` to `#e3b341`
- `--color-edge` changed from `#aaaaaa` to `#30363d`
- `--color-selected-ring` removed; use `--color-accent` directly
- Added `--color-node-fresh`, `--color-node-dir`, `--color-node-pulse`, `--color-accent-dim`

**Spacing:** All spacing in this codebase uses a 4/8px base. Components use padding multiples of 4: 4, 8, 12, 16, 20, 24. Gap values: 4, 8, 12. No odd values (no 3px, no 6px, no 10px) except where icon sizing or border-radius demands it. The existing code has some violations (e.g., `gap: '3px'` in ImportanceFilter) — fix those to 4px during rework.

---

## 5. global.css

Structural changes: none. The file keeps its reset, `html/body/#root { height:100%; overflow:hidden }`, focus-visible rules, and button reset. The only functional change is that `background: var(--color-bg)` on `body` now resolves to `#0d1117` instead of white, which is automatic once tokens.css is updated.

One addition: add a scrollbar style block so the doc panel's overflow-y scroll doesn't render a white native scrollbar:

```css
/* Thin dark scrollbar for doc panel and any other scrollable surfaces */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: var(--color-surface);
}
::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-muted);
}
```

---

## 6. App.jsx

### Props

None (root component).

### New state additions

```js
const [paletteOpen, setPaletteOpen] = useState(false)
const [minimapVisible, setMinimapVisible] = useState(false)
```

All existing state (collapsedMap, importanceFilter, selectedNode, panelOpen, pulseMap) is unchanged.

### Keyboard listener

Add a `useEffect` in App.jsx with `[]` dependency that registers one `keydown` listener on `document`:

```
document.addEventListener('keydown', handler)
return () => document.removeEventListener('keydown', handler)
```

Handler logic:
```
if event.key === 'k' AND (event.ctrlKey OR event.metaKey):
  event.preventDefault()
  if paletteOpen:
    setPaletteOpen(false)
  else:
    setPaletteOpen(true)
if event.key === 'Escape':
  if paletteOpen:
    setPaletteOpen(false)
    return
  if panelOpen:
    closePanel()
    return
```

The handler must use a ref for `paletteOpen` and `panelOpen` to avoid stale closure. Pattern: `const paletteOpenRef = useRef(false)` — update it in the same setState call.

Alternatively, simpler: the Escape key in the CommandPalette and DocPanel handle their own close. Only the Ctrl+K handler lives in App.jsx. This avoids the stale closure problem entirely. Prefer this approach.

```js
useEffect(() => {
  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault()
      setPaletteOpen(open => !open)
    }
  }
  document.addEventListener('keydown', handleKeyDown)
  return () => document.removeEventListener('keydown', handleKeyDown)
}, [])
```

### New props to pass down

App.jsx needs to pass `edges` to DocPanel (for backlinks) and `nodes` to CommandPalette (for search). Both are already available from `useGraph`.

DocPanel now also needs `onNodeSelect: (node) => void` — the same function as `handleNodeClick` — so backlink chips can trigger panel switches.

CommandPalette needs:
- `nodes` — full node list (not filtered) for search
- `importanceFilter` and `onImportanceChange` — for the embedded filter strip
- `onSelect(node)` — called when user hits Enter on a result; App.jsx handles centering the graph and opening the panel
- `onClose` — sets `paletteOpen(false)`
- `fgRef` — forwarded from GraphCanvas to App so CommandPalette can call `fgRef.current.centerAt(node.x, node.y, 600)` on select

**How fgRef flows:** GraphCanvas currently owns `fgRef` internally. Change this: lift `fgRef` to App.jsx (create it there with `useRef()`), pass it down as a prop to GraphCanvas (which attaches it to ForceGraph2D as `ref={fgRef}`), and also pass it to CommandPalette for the `centerAt` call.

### Layout structure (JSX skeleton, not code)

The outer div: `position: relative; width: 100vw; height: 100vh; background: var(--color-bg); overflow: hidden`.

Inside, in render order (back to front):

1. `<GraphCanvas fgRef={fgRef} ... />` — no wrapper div needed; GraphCanvas itself renders `position:relative; width:100%; height:100%`

2. `<div className="name-chip">` — `position:absolute; top:16px; left:16px; z-index:10; display:flex; align-items:center; gap:8px`
   - `<span>` with project display name, `--font-sans`, `--text-base` (13px), weight 600, `--color-text-primary`
   - A subtle dot separator `·` in `--color-text-muted`
   - `<span>` with node count: `"{visibleNodes} nodes"` in `--color-text-muted`, `--text-sm`
   - `visibleNodes` = `graphData.nodes.length` — the post-filter count

3. `<div className="toolbar-corner">` — `position:absolute; top:16px; right:16px; z-index:10; display:flex; align-items:center; gap:8px`
   - `<button className="palette-trigger">` — text `"⌘K"` on macOS, `"Ctrl K"` on Windows (detect via `navigator.platform.includes('Mac')`); width auto; height 28px; padding `0 10px`; bg `--color-surface-raised`; border `1px solid --color-border`; border-radius 6px; `--text-sm`; `--color-text-secondary`; on hover: border-color `--color-accent`, color `--color-text-primary`; on click: `setPaletteOpen(true)`; `aria-label="Open command palette"`, `aria-keyshortcuts="Control+K"`
   - `<button className="minimap-toggle">` — icon only: `"⊞"` or a simple grid icon; width 28px; height 28px; same surface/border style as palette-trigger but square; `aria-label="Toggle minimap"`, `aria-pressed={minimapVisible}`; on click: `setMinimapVisible(v => !v)`; when `minimapVisible` is true: bg `--color-accent-dim`, border-color `--color-accent`

4. `{paletteOpen && <CommandPalette ... />}` — renders its own backdrop via React portal to `document.body`

5. `<DocPanel ... />` — always in DOM, slides in/out via transform. Positioned `absolute; top:0; right:0; height:100%; z-index:20`

6. `{minimapVisible && <Minimap graphData={graphData} staleMap={staleMap} fgRef={fgRef} />}`

### Loading / error / empty states

These remain full-viewport takeovers (same conditional render pattern as today) but with dark colors. The `fullscreenCenter` style object changes: `background: 'var(--color-bg)'` now resolves to `#0d1117`. No structural change needed — it already uses the token.

The `allFiltered` overlay: update its positioned container to use `position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); z-index:10; pointer-events:none; text-align:center`. Update copy per state 3e above.

### What is removed

The entire `<header>` element (56px bar) is deleted. The `<ImportanceFilter>` import in App.jsx is removed (it is now imported only by CommandPalette). The `flex-direction: column` layout is gone; the outer div is `position:relative` not `display:flex; flex-direction:column`.

---

## 7. GraphCanvas.jsx

### Constant block (replace entirely)

```js
const COLOR_BG          = '#0d1117'
const COLOR_NODE_FRESH  = '#7c6af7'
const COLOR_NODE_DIR    = '#a5d8ff'
const COLOR_NODE_STALE  = '#e3b341'
const COLOR_NODE_PULSE  = '#ffffff'
const COLOR_EDGE        = '#30363d'
const COLOR_LABEL       = '#8b949e'
const COLOR_ACCENT      = '#7c6af7'
const COLOR_ACCENT_DIM  = '#4a4280'

const FONT_LABEL     = "13px 'Inter', system-ui, sans-serif"
const FONT_DIR_BADGE = "bold 8px 'Inter', system-ui, sans-serif"
const FONT_DIR_COUNT = "8px 'Inter', system-ui, sans-serif"
```

### Props interface (additions)

Add `fgRef` as a required prop. GraphCanvas no longer creates its own `useRef()`; it receives the ref from App.jsx.

```js
export function GraphCanvas({
  fgRef,           // NEW — forwarded from App.jsx
  graphData,
  staleMap,
  collapsedMap,
  selectedNodeId,
  onNodeClick,
  childCounts,
  pulseMap = new Map(),
})
```

### nodeColor function (replace)

```js
function nodeColor(node, staleMap, pulseMap) {
  if (isPulsing(node, pulseMap)) return COLOR_NODE_PULSE
  const isStale = staleMap.get(node.id) ?? !!node.stale
  if (node.type === 'dir') return isStale ? COLOR_NODE_STALE : COLOR_NODE_DIR
  return isStale ? COLOR_NODE_STALE : COLOR_NODE_FRESH
}
```

### nodeRadius function (unchanged in formula, dir radius changes)

```js
function nodeRadius(node) {
  if (node.type === 'dir') return 14   // was 16; slightly tighter in dark theme
  return fileRadius(node.importance)   // unchanged formula
}
```

### nodeCanvasObject draw order (per node)

For each node, in this exact order:

**Step 1 — glow pass (stale nodes and pulsing nodes only)**

For stale file nodes:
```
ctx.save()
ctx.shadowColor = '#e3b341'
ctx.shadowBlur = 8 / globalScale
// draw circle (no fill yet — shadow draws on the fill below)
ctx.restore()
```

Wait — canvas shadow requires the draw call to happen inside the save/restore. The correct pattern:
```
ctx.save()
ctx.shadowColor = COLOR_NODE_STALE
ctx.shadowBlur = 8 / globalScale
ctx.beginPath()
ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
ctx.fillStyle = COLOR_NODE_STALE
ctx.fill()
ctx.restore()
```
This path is used when: `isStale && !nodePulsing`.

For pulsing nodes:
```
ctx.save()
ctx.shadowColor = COLOR_ACCENT
ctx.shadowBlur = 14 / globalScale
ctx.beginPath()
ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
ctx.fillStyle = COLOR_NODE_PULSE
ctx.fill()
ctx.restore()
```
This path is used when: `nodePulsing`.

For fresh, non-pulsing nodes (no glow):
```
ctx.beginPath()
ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
ctx.fillStyle = fill   // COLOR_NODE_FRESH or COLOR_NODE_DIR
ctx.fill()
```

The three paths are mutually exclusive. Use `if (nodePulsing) { ... } else if (isStale) { ... } else { ... }`.

**Step 2 — pulse ring (collapsed dir ancestor of pulsing node)**

Condition: `isDir && isCollapsed && !nodePulsing && node.__pulseAncestor`

```
ctx.beginPath()
ctx.arc(node.x, node.y, r + 3, 0, 2 * Math.PI)
ctx.strokeStyle = COLOR_ACCENT
ctx.lineWidth = 2 / globalScale
ctx.stroke()
```

**Step 3 — selection ring**

Condition: `isSelected`

```
ctx.beginPath()
ctx.arc(node.x, node.y, r + 2, 0, 2 * Math.PI)
ctx.strokeStyle = COLOR_ACCENT
ctx.lineWidth = 2.5 / globalScale
ctx.stroke()
```

**Step 4 — dir badge (▶ + count)**

Condition: `isDir && isCollapsed` with `count > 0`

Text color is `COLOR_BG` (`#0d1117`) — dark text on the light blue dir node fill. This is readable because `#a5d8ff` on `#0d1117` is high contrast.

```
ctx.fillStyle = COLOR_BG
ctx.textAlign = 'center'
ctx.textBaseline = 'middle'
ctx.font = FONT_DIR_BADGE
ctx.fillText('▶', node.x, node.y - 2)
ctx.font = FONT_DIR_COUNT
ctx.fillText(String(count), node.x, node.y + 5)
```

**Step 5 — label**

Threshold: `globalScale >= 0.15` (was 0.2; lowered by one step).

```
const label = lastName(node.path)
const labelY = node.y + r + 6
ctx.font = FONT_LABEL
ctx.fillStyle = COLOR_LABEL
ctx.textAlign = 'center'
ctx.textBaseline = 'top'
ctx.fillText(label, node.x, labelY)
```

No change to label layout. No background pill. `#8b949e` on `#0d1117` is approximately 5.5:1 contrast — passes AA at this font size.

### linkColor and linkWidth

```js
const linkColor = useCallback(() => COLOR_EDGE, [])   // '#30363d'
const linkWidth = useCallback(() => 1, [])             // was 1.5; thin edges read on dark bg
```

### Container div background

The wrapper div's inline style `background` changes from `COLOR_BG` (now `#0d1117`). ForceGraph2D `backgroundColor` prop also changes to `COLOR_BG` = `#0d1117`.

### nodePointerAreaPaint

Unchanged.

---

## 8. DocPanel.jsx

### Props interface (additions)

```js
export function DocPanel({
  node,
  isOpen,
  onClose,
  staleMap,
  edges,          // NEW — full edges array from useGraph, for backlinks
  onNodeSelect,   // NEW — (node) => void, same as App's handleNodeClick
  nodes,          // NEW — needed to resolve backlink source nodes by id
})
```

### Positioning change

The panel is no longer a flex child that shrinks the canvas. It is `position:absolute`:

```js
style={{
  position: 'absolute',
  top: 0,
  right: 0,
  height: '100%',
  width: `${PANEL_WIDTH}px`,   // 420 unchanged
  background: 'var(--color-surface)',
  borderLeft: '1px solid var(--color-border)',  // was 3px accent; now 1px border
  display: 'flex',
  flexDirection: 'column',
  transform: isOpen ? 'translateX(0)' : 'translateX(420px)',
  transition: 'transform 220ms cubic-bezier(0.4, 0, 0.2, 1)',
  overflow: 'hidden',
  zIndex: 20,
  // No box-shadow — the border + dark surface create enough separation
}}
```

Note: the left border changes from `3px solid --color-panel-accent` to `1px solid --color-border`. The accent treatment was appropriate for a light theme where the panel sat next to white canvas. On dark, a 1px divider is sufficient; the heavy accent line looks garish.

### Close button

Style update only. The button stays at `position:absolute; top:8px; right:8px; width:44px; height:44px`. Change:
- color: `--color-text-muted` (now `#484f58`)
- hover color: `--color-text-primary` (now `#e6edf3`)
- no background change needed; the button is transparent

### Breadcrumb row (replaces the path div)

Where the old `<div>` showing `node.path` was, render:

```
<div
  title={node.path}
  style={{ padding:'16px 52px 8px 16px', display:'flex', alignItems:'center', flexWrap:'nowrap', overflow:'hidden', gap:4 }}
>
  {segments.map((segment, i) => {
    const isLast = i === segments.length - 1
    return [
      i > 0 && <span key={`sep-${i}`} style={{ color:'--color-text-muted', flexShrink:0, padding:'0 2px' }}>/</span>,
      <span
        key={segment.path}
        onClick={isLast ? undefined : () => handleBreadcrumbClick(segment.node)}
        style={{
          color: isLast ? '--color-text-primary' : '--color-text-muted',
          fontFamily: '--font-sans',
          fontSize: '--text-sm',  // 12px — tighter than the old md
          fontWeight: isLast ? 600 : 400,
          cursor: isLast ? 'default' : 'pointer',
          maxWidth: isLast ? '180px' : '80px',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          flexShrink: isLast ? 1 : 0,
        }}
        onMouseEnter={!isLast ? e => e.currentTarget.style.color = '--color-text-primary' : undefined}
        onMouseLeave={!isLast ? e => e.currentTarget.style.color = '--color-text-muted' : undefined}
      >
        {segment.label}
      </span>
    ]
  })}
</div>
```

**How to build `segments` from `node.path`:**

```
const parts = node.path.split('/')
const byPath = new Map((nodes || []).map(n => [n.path, n]))

segments = parts.map((label, i) => {
  const segPath = parts.slice(0, i + 1).join('/')
  const matchingNode = byPath.get(segPath) ?? null
  return { label, path: segPath, node: matchingNode }
})
```

The last segment is the file itself. Ancestor segments whose `matchingNode` is null (no graph node for that path) are rendered as non-clickable muted text (same style as non-last but `cursor:default`, no hover).

`handleBreadcrumbClick(segmentNode)`: if `segmentNode` is not null, call `onNodeSelect(segmentNode)`. This triggers the same logic as clicking the node in the graph — if it's a dir, it toggles collapse; if it's a file, it opens its panel.

### Staleness badge

Style update only. Colors already reference `--color-stale-badge-bg` and `--color-stale-badge-text` which are updated in tokens.css. No structural change.

### Divider

`height:1px; background: var(--color-border)` — now resolves to `#30363d`. No change needed.

### Doc body (ReactMarkdown components)

Update all hard-coded hex values to use CSS variables. The full updated `mdComponents` object:

```
h1: { font: '--font-sans'; size: 16px; weight: 700; color: '--color-text-primary'; marginBottom: 12px; marginTop: 0 }
h2: { font: '--font-sans'; size: '--text-sm'; weight: 600; textTransform: uppercase; letterSpacing: '0.07em'; color: '--color-text-muted'; borderBottom: '1px solid --color-border'; paddingBottom: 4px; marginBottom: 8px; marginTop: 20px }
h3: { font: '--font-sans'; size: '--text-base'; weight: 600; color: '--color-text-secondary'; marginBottom: 8px; marginTop: 16px }
p:  { font: '--font-sans'; size: '--text-md'; color: '--color-text-secondary'; lineHeight: 1.7; marginBottom: 12px }
code (inline): { font: '--font-mono'; size: 12.5px; background: '--color-surface-raised'; borderRadius: 3px; padding: '2px 5px'; color: '--color-accent' }
code (block): { font: '--font-mono'; size: 12.5px; display: block; background: '--color-surface-raised'; borderRadius: 5px; padding: '12px 16px'; color: '--color-text-secondary'; overflowX: auto; borderLeft: '3px solid --color-panel-accent' }
a: { color: '--color-accent'; textDecoration: none; hover: underline }
ul: { paddingLeft: 20px; listStyle: disc; color: '--color-text-secondary'; marginBottom: 12px }
li: { font: '--font-sans'; size: '--text-md'; lineHeight: 1.7 }
```

Specifically: the old hard-coded `#f0f0f0` inline code background becomes `var(--color-surface-raised)` (`#21262d`). The old `#f5f5f5` block code background becomes `var(--color-surface-raised)`. The old `#c7254e` inline code text color becomes `var(--color-accent)` (`#7c6af7`). The old `#555555` h2 color becomes `var(--color-text-muted)`. All other places that used `#333333` become `var(--color-text-secondary)`.

### Backlinks section

Rendered below the doc body, within the same `overflowY:auto` scroll container. The backlinks section is the last element inside the scrollable div.

**Derive backlinks:**

```
const backlinks = useMemo(() => {
  if (!edges || !node) return []
  const nodeId = node.id
  const byId = new Map((nodes || []).map(n => [n.id, n]))
  return edges
    .filter(e => {
      const targetId = e.target?.id ?? e.target
      return targetId === nodeId
    })
    .map(e => {
      const sourceId = e.source?.id ?? e.source
      return byId.get(sourceId)
    })
    .filter(Boolean)
}, [edges, nodes, node])
```

**Render:**

If `backlinks.length === 0`: render nothing (no section at all).

If `backlinks.length > 0`:

```
<div style={{ marginTop:24, paddingTop:16, borderTop:'1px solid --color-border' }}>
  <p style={{ '--font-sans', '--text-sm', weight:600, textTransform:'uppercase', letterSpacing:'0.07em', '--color-text-muted', marginBottom:12 }}>
    Linked from
  </p>
  <div style={{ display:'flex', flexWrap:'wrap', gap:8 }}>
    {visibleBacklinks.map(bl => (
      <button
        key={bl.id}
        onClick={() => onNodeSelect(bl)}
        style={{
          '--font-sans', '--text-sm', padding:'4px 10px',
          background: '--color-surface-raised',
          border: '1px solid --color-border',
          borderRadius: 4,
          color: '--color-text-secondary',
          cursor: 'pointer',
          // hover: border-color '--color-accent', color '--color-text-primary'
        }}
      >
        {lastName(bl.path)}
      </button>
    ))}
    {backlinks.length > 10 && !showAllBacklinks && (
      <button onClick={() => setShowAllBacklinks(true)} style={{ same chip style but '--color-text-muted' }}>
        +{backlinks.length - 10} more
      </button>
    )}
  </div>
</div>
```

`visibleBacklinks = showAllBacklinks ? backlinks : backlinks.slice(0, 10)`. State: `const [showAllBacklinks, setShowAllBacklinks] = useState(false)` — reset via `useEffect([node?.id])`.

`lastName` is the same helper as in GraphCanvas: `path.split('/').at(-1)`. Duplicate the function in DocPanel or extract to a shared `utils.js`. Prefer extracting to `src/utils/path.js` — both GraphCanvas and DocPanel import from there. (Builder: this is a new file, but it is tiny — just two functions: `lastName(path)` and `splitSegments(path)`. Add it.)

---

## 9. CommandPalette.jsx (new file)

File path: `frontend/src/components/CommandPalette.jsx`

### Props interface

```js
function CommandPalette({
  nodes,              // full node array from useGraph (unfiltered)
  importanceFilter,   // current value: 'All' | '1'...'5'
  onImportanceChange, // (level: string) => void
  onSelect,           // (node) => void — called on Enter/click of result
  onClose,            // () => void — called on Esc or backdrop click
  fgRef,              // forwarded ref to ForceGraph2D — for centerAt on select
})
```

### Key state

```js
const [query, setQuery] = useState('')
const [activeIndex, setActiveIndex] = useState(0)
const inputRef = useRef(null)
```

### Mount behavior

On mount, focus the input: `useEffect(() => { inputRef.current?.focus() }, [])`.

Reset `activeIndex` to 0 whenever `query` changes: `useEffect(() => setActiveIndex(0), [query])`.

### Render via React Portal

The entire component renders into `document.body` via `ReactDOM.createPortal(...)`. This ensures it sits above all other z-index stacking contexts.

### DOM structure

```
portal root (document.body):
  <div class="palette-backdrop">   /* position:fixed; inset:0; z-index:29; background:rgba(0,0,0,0.5); */
    onClick: onClose
  </div>
  <div class="palette-modal">      /* position:fixed; top:20%; left:50%; transform:translateX(-50%); z-index:30; */
    /* width: min(520px, 90vw); */
    /* background: var(--color-surface); */
    /* border: 1px solid var(--color-border); */
    /* border-radius: 8px; */
    /* box-shadow: 0 8px 32px rgba(0,0,0,0.6); */
    /* overflow: hidden; */

    <div class="palette-input-row">   /* padding: 0 16px; border-bottom: 1px solid var(--color-border); */
      <span class="palette-search-icon">  /* "⌕" or SVG, color: --color-text-muted */
      <input
        ref={inputRef}
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search files and folders..."
        /* height: 48px; width: 100%; background: transparent; border: none; */
        /* color: --color-text-primary; font: --font-sans; font-size: --text-md; */
        /* outline: none; padding-left: 8px; */
      />
    </div>

    {results.length > 0 && (
      <div class="palette-results">   /* max-height: 300px; overflow-y: auto; padding: 4px 0; */
        {query && results.length < totalMatches && (
          <div class="result-count">  /* padding: 4px 16px; --text-sm; --color-text-muted */
            Showing {results.length} of {totalMatches}
          </div>
        )}
        {results.map((node, i) => (
          <div
            key={node.id}
            class="result-row"
            aria-selected={i === activeIndex}
            onClick={() => handleSelect(node)}
            /* padding: 8px 16px; cursor:pointer; display:flex; align-items:center; gap:8px; */
            /* background: i === activeIndex ? '--color-surface-raised' : 'transparent' */
            /* color: --color-text-primary */
          >
            <span class="result-type-icon">
              /* dir: "📁" or a simple folder glyph in --color-node-dir (#a5d8ff) */
              /* file: "◆" in --color-node-fresh (#7c6af7) */
              /* width: 16px; text-align: center */
            </span>
            <span class="result-filename">
              /* --text-base; --color-text-primary; font-weight: 500 */
              {lastName(node.path)}
            </span>
            {node.importance != null && (
              <span class="result-importance">
                /* --text-xs; --color-text-muted */
                {"·".repeat(node.importance)}
              </span>
            )}
            <span class="result-path">
              /* margin-left:auto; --text-sm; --color-text-muted; max-width:200px; */
              /* white-space:nowrap; overflow:hidden; text-overflow:ellipsis; direction:rtl */
              {node.path}
            </span>
          </div>
        ))}
      </div>
    )}

    {query && results.length === 0 && (
      <div class="palette-empty">   /* padding: 32px 16px; text-align: center; --color-text-muted; --text-base */
        No files match.
      </div>
    )}

    <div class="palette-filter-row">   /* padding: 12px 16px; border-top: 1px solid var(--color-border); */
      /* display:flex; align-items:center; gap:8px */
      <span>  /* --text-sm; --color-text-muted; padding-right:4px */
        Importance ≥
      </span>
      <ImportanceFilter value={importanceFilter} onChange={onImportanceChange} />
    </div>
  </div>
```

### Results derivation

```
const filtered = useMemo(() => {
  if (!query.trim()) return []
  const q = query.toLowerCase()
  return nodes
    .filter(n => lastName(n.path).toLowerCase().includes(q))
    .slice(0, 8)   // hard cap at 8 visible
}, [nodes, query])

const totalMatches = useMemo(() => {
  if (!query.trim()) return 0
  const q = query.toLowerCase()
  return nodes.filter(n => lastName(n.path).toLowerCase().includes(q)).length
}, [nodes, query])

const results = filtered
```

### Keyboard handler

Attach `onKeyDown` to the outer modal div (`tabIndex={-1}`) or to the input:

```
ArrowDown: setActiveIndex(i => Math.min(i + 1, results.length - 1)), prevent default
ArrowUp:   setActiveIndex(i => Math.max(i - 1, 0)), prevent default
Enter:     if results[activeIndex] exists: handleSelect(results[activeIndex])
Escape:    onClose()
```

### handleSelect(node)

```
function handleSelect(node) {
  onSelect(node)        // App.jsx: calls handleNodeClick(node) — opens panel or toggles dir
  if (fgRef.current && node.x != null) {
    fgRef.current.centerAt(node.x, node.y, 600)   // 600ms fly-to animation
    fgRef.current.zoom(2.5, 600)                    // zoom in if very zoomed out
  }
  onClose()
}
```

Note: `fgRef.current.zoom(2.5, 600)` should only fire if current zoom is below 1.0. Check: `fgRef.current.zoom()` returns current zoom level (no args). If it's less than 1, set it to 2.5. Otherwise leave zoom unchanged.

```
const currentZoom = fgRef.current.zoom()
if (currentZoom < 1) {
  fgRef.current.zoom(2.5, 600)
}
```

### Importance filter behavior

When a filter level is clicked, call `onImportanceChange(level)` and then `onClose()`. The graph updates because `importanceFilter` state in App.jsx drives `filteredVisibleIds`.

### CSS class names for ImportanceFilter in dark context

The ImportanceFilter component is reused inside CommandPalette. Its existing inline styles use hard-coded light colors (`#f0f0f0`, `#E63946`, `#666666`). These must be updated in ImportanceFilter.jsx itself so that all instances (palette) use the dark-theme values. See section 11 below.

### Accessibility

- `role="dialog"`, `aria-modal="true"`, `aria-label="Command palette"` on the modal div
- `role="listbox"` on the results list div
- Each result row: `role="option"`, `aria-selected={i === activeIndex}`
- The input: `aria-autocomplete="list"`, `aria-controls="palette-results-list"` (id on the listbox)
- Trap focus within the modal: on Tab, keep focus inside (input and results). Simplest approach: because the input is always focused and arrow keys navigate results, Tab/Shift+Tab can be allowed to escape (no trap needed — this is a search palette, not a dialog).

---

## 10. Minimap.jsx (new file)

File path: `frontend/src/components/Minimap.jsx`

### Props interface

```js
function Minimap({
  graphData,    // { nodes, links } — from App.jsx
  staleMap,     // Map<id, boolean>
  fgRef,        // ref to ForceGraph2D — for viewport read
})
```

### Key state

None. The minimap is stateless and redraws on an interval.

### Canvas setup

```js
const canvasRef = useRef(null)

useEffect(() => {
  const canvas = canvasRef.current
  if (!canvas) return
  const id = setInterval(() => drawMinimap(), 1000)
  drawMinimap()   // draw immediately on mount
  return () => clearInterval(id)
}, [graphData, staleMap])   // re-register interval if graph changes
```

### drawMinimap logic

```
function drawMinimap() {
  const canvas = canvasRef.current
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const W = 160, H = 120

  // Clear
  ctx.clearRect(0, 0, W, H)
  ctx.fillStyle = '#0d1117'   // --color-bg hardcoded because tokens not available in JS
  ctx.fillRect(0, 0, W, H)

  const nodes = graphData.nodes.filter(n => n.x != null)
  if (nodes.length === 0) return

  // Find bounding box of node positions
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const n of nodes) {
    if (n.x < minX) minX = n.x
    if (n.x > maxX) maxX = n.x
    if (n.y < minY) minY = n.y
    if (n.y > maxY) maxY = n.y
  }

  // Add 10% padding around bounds
  const padX = (maxX - minX) * 0.1 || 10
  const padY = (maxY - minY) * 0.1 || 10
  minX -= padX; maxX += padX
  minY -= padY; maxY += padY

  const scaleX = W / (maxX - minX)
  const scaleY = H / (maxY - minY)
  const scale = Math.min(scaleX, scaleY)

  // Center the scaled graph in the canvas
  const offsetX = (W - (maxX - minX) * scale) / 2
  const offsetY = (H - (maxY - minY) * scale) / 2

  function toMiniX(x) { return (x - minX) * scale + offsetX }
  function toMiniY(y) { return (y - minY) * scale + offsetY }

  // Draw nodes as small dots (radius 2 for files, 3 for dirs)
  for (const n of nodes) {
    const isStale = staleMap.get(n.id) ?? !!n.stale
    const dotColor = n.type === 'dir'
      ? '#a5d8ff'
      : (isStale ? '#e3b341' : '#7c6af7')
    const dotRadius = n.type === 'dir' ? 3 : 2

    ctx.beginPath()
    ctx.arc(toMiniX(n.x), toMiniY(n.y), dotRadius, 0, 2 * Math.PI)
    ctx.fillStyle = dotColor
    ctx.fill()
  }

  // Draw viewport rectangle
  if (fgRef?.current) {
    try {
      const center = fgRef.current.centerAt()    // returns {x, y}
      const zoom = fgRef.current.zoom()          // returns number
      // ForceGraph2D canvas container dimensions
      const container = fgRef.current.d3Force   // not the container — see note below
      // We need the canvas element dimensions from the container div
      // Approximation: viewport in graph-space is (containerW / zoom) × (containerH / zoom)
      // Container dimensions: use window.innerWidth and window.innerHeight as proxy
      const vpW = window.innerWidth / zoom
      const vpH = window.innerHeight / zoom

      const vx1 = toMiniX(center.x - vpW / 2)
      const vy1 = toMiniY(center.y - vpH / 2)
      const vx2 = toMiniX(center.x + vpW / 2)
      const vy2 = toMiniY(center.y + vpH / 2)

      ctx.strokeStyle = 'rgba(255,255,255,0.3)'
      ctx.lineWidth = 1
      ctx.strokeRect(vx1, vy1, vx2 - vx1, vy2 - vy1)
    } catch (_) {
      // fgRef not ready — skip viewport rect
    }
  }
}
```

Note on `fgRef.current.centerAt()`: the react-force-graph-2d API exposes `centerAt(x, y, ms)` for setting the center and `centerAt()` (no args) for getting the current center. Similarly `zoom()` returns current zoom. These are in the library's public API. If the library version used does not support no-arg `centerAt()`, omit the viewport rect silently (the try/catch handles it).

### Container JSX

```jsx
<div
  style={{
    position: 'absolute',
    bottom: 16,
    right: 16,
    width: 160,
    height: 120,
    border: '1px solid var(--color-border)',
    borderRadius: 6,
    overflow: 'hidden',
    zIndex: 10,
    pointerEvents: 'none',   // read-only; no click events in Phase 6
  }}
>
  <canvas ref={canvasRef} width={160} height={120} />
</div>
```

The minimap has `pointerEvents: 'none'` on the container. There is no click-to-navigate (explicitly parked). The canvas's physical pixel dimensions match the display dimensions (160×120 CSS px = 160×120 canvas pixels) — no devicePixelRatio correction needed for a minimap this small.

---

## 11. ImportanceFilter.jsx

### What changes

The component's internal hard-coded colors are updated to reference dark theme values. No behavior changes.

Updated inline style values:

```
Active button:
  background: var(--color-accent)          // was '#E63946' (red)
  color: var(--color-bg)                   // was '#ffffff' — still white-ish (#0d1117 is very dark, but the text needs to be light)

  Correction: active button text should be '#e6edf3' (--color-text-primary) not --color-bg.
  background: '#7c6af7'  OR  var(--color-accent)
  color: '#e6edf3'
  borderColor: var(--color-accent)

Inactive button:
  background: var(--color-surface-raised)  // was '#f0f0f0' (now '#21262d')
  color: var(--color-text-secondary)       // was '#666666' (now '#8b949e')
  borderColor: var(--color-border)         // was 'var(--color-border)' (now '#30363d')

Inactive button hover:
  background: var(--color-border)          // was '#e0e0e0' (now '#30363d' — subtle)

Label span "Show files with importance ≥":
  color: var(--color-text-muted)           // was '#888888'
```

Gap fix: change `gap: '3px'` to `gap: '4px'` on the wrapper div.

---

## 12. Event Wiring Summary

All wiring passes through App.jsx. No component calls a sibling directly.

```
App.jsx state:
  paletteOpen        → CommandPalette (prop: mount/unmount)
  minimapVisible     → Minimap (mount/unmount)
  importanceFilter   → CommandPalette (for display), filteredVisibleIds (for graph)
  selectedNode       → DocPanel (node prop)
  panelOpen          → DocPanel (isOpen prop)
  collapsedMap       → GraphCanvas (for draw), App's filtering logic
  pulseMap           → GraphCanvas (for draw)
  fgRef              → GraphCanvas (attach), CommandPalette (centerAt)

User actions:
  Ctrl+K pressed           → setPaletteOpen(true)
  Palette Esc / backdrop   → setPaletteOpen(false)
  Palette result selected  → onSelect(node) → handleNodeClick(node) + centerAt + close
  Palette filter changed   → setImportanceFilter(level) + setPaletteOpen(false)
  Graph node clicked       → handleNodeClick(node):
                               dir → toggle collapse
                               file → setSelectedNode, setPanelOpen(true)
  Breadcrumb segment click → onNodeSelect(node) → handleNodeClick(node)
  Backlink chip click      → onNodeSelect(bl) → handleNodeClick(bl)
  Panel close              → closePanel() → setPanelOpen(false), setSelectedNode(null)
  Panel Esc key            → panel handles own Escape keydown → calls onClose
  Minimap toggle           → setMinimapVisible(v => !v)
```

DocPanel's own Escape handler:

```js
useEffect(() => {
  if (!isOpen) return
  function handleKeyDown(e) {
    if (e.key === 'Escape') onClose()
  }
  document.addEventListener('keydown', handleKeyDown)
  return () => document.removeEventListener('keydown', handleKeyDown)
}, [isOpen, onClose])
```

---

## 13. Accessibility Floor

| Requirement | Implementation |
|---|---|
| 4.5:1 body text contrast | `#8b949e` on `#0d1117` = 5.5:1 (passes AA). `#e6edf3` on `#0d1117` = 14.6:1. |
| 3:1 large text / UI components | `#30363d` on `#0d1117` = 1.4:1 — borders are decorative, not text. OK. |
| 44px minimum touch targets | Minimap toggle button: 28px. This fails the 44px touch target floor. Fix: make it 36px × 36px minimum, with an `::after` pseudo-element or transparent padding to extend the touch area to 44px. Same applies to the palette-trigger button. Set `padding: 0 12px; height: 36px` and accept that 36px is the visual size but the tap area requirement is best handled with `min-height: 44px` on mobile if needed. For a dev-only desktop tool, 36px is acceptable — note the trade-off. |
| Every input labeled | Command palette input: `aria-label="Search files and folders"`. |
| Focus always visible | `global.css` `:focus-visible` rule applies; `outline: 2px solid var(--color-accent)` — now purple, still visible on dark backgrounds. |
| Dialog trap | CommandPalette: `role="dialog"`, `aria-modal="true"`. Focus moves to input on open. Esc closes. No hard tab trap needed for this pattern. |
| Close button label | DocPanel close button keeps `aria-label="Close doc panel"`. |
| Backlink buttons | Each backlink chip button has accessible text (the filename). No additional label needed. |

---

## 14. Copy — All User-Facing Strings

Loading state: `"Loading graph..."`
Error state line 1: `"Could not connect to Corpus."`
Error state line 2: `"Is corpus serve running on localhost:7077?"`
Error retry button: `"Retry"`
Empty graph line 1: `"No files tracked yet."`
Empty graph line 2: `"Run corpus init, then corpus update."`
All-filtered overlay line 1: `"No files at this importance level."`
All-filtered overlay line 2: `"Press Ctrl+K and choose All to show everything."`
Doc panel — no doc: `"No documentation generated yet."`
Doc panel — no doc line 2: `"Run corpus update to generate docs."`
Doc panel — loading: `"Loading documentation..."`
Doc panel — error: `"Could not load this file's doc."`
Doc panel — error button: `"Retry"`
Staleness badge: `"Outdated"` (unchanged)
Backlinks section heading: `"Linked from"`
Command palette input placeholder: `"Search files and folders..."`
Command palette empty state: `"No files match."`
Command palette result count: `"Showing 8 of {N}"` (only when results are capped)
ImportanceFilter label: `"Importance ≥"` (shortened from `"Show files with importance ≥"` — it's inside the palette now, context is clear)
Minimap toggle aria-label: `"Toggle minimap"`
Palette trigger aria-label: `"Open command palette"`
Palette trigger visible label: `"⌘K"` (macOS) or `"Ctrl K"` (Windows/Linux)

---

## 15. Files Touched (complete list for builder)

**Modified:**
- `frontend/src/styles/tokens.css` — full replacement
- `frontend/src/styles/global.css` — scrollbar block added
- `frontend/src/App.jsx` — layout shell, state additions, keyboard listener, fgRef lift
- `frontend/src/components/GraphCanvas.jsx` — constant block, nodeColor, nodeRadius, draw order, fgRef prop, container bg
- `frontend/src/components/DocPanel.jsx` — positioning, breadcrumb, backlinks, dark md styles, new props, Escape handler
- `frontend/src/components/ImportanceFilter.jsx` — dark inline colors, gap fix

**Created:**
- `frontend/src/components/CommandPalette.jsx`
- `frontend/src/components/Minimap.jsx`
- `frontend/src/utils/path.js` — exports `lastName(path)` and `splitSegments(path, nodesByPath)`

**Unchanged:**
- `frontend/src/hooks/useGraph.js`
- `frontend/src/hooks/useDoc.js`
- `frontend/src/main.jsx`
- All Python backend files
