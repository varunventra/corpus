# DESIGN — Phase 7: Sahara Warm Theme + Three-Column Layout + Five Functional Tabs

**Design authority:** `C:\Users\varun\OneDrive\Desktop\stitch\code.html` (Tailwind config + component HTML).
Every hex value below is sourced verbatim from that file. When a value appears here, trust this spec over memory.

---

## 1. The One Job

Replace the Phase 6 dark overlay experience with a warm editorial layout that lets a developer read their codebase — browse the file tree, navigate graph views by intent (architecture vs. dependencies vs. symbols), and read documentation — without the graph fighting for dominance over the content panels.

The graph is one of five equal views, not the entire product.

---

## 2. Layout & Hierarchy

### Visual order across the screen

1. **Top nav** — the user's location and navigation controls. Eye hits "Corpus" wordmark first (EB Garamond, sienna), then the active tab label (active = sienna underline). The search input and icon buttons are secondary; they live on the right, subordinate to navigation.
2. **Left column — File Tree (260px)** — structural context. The user knows where they are in the repo without having to read graph node labels.
3. **Center column (flex-1)** — the current tab's content. This is the work surface. Background is `#faf5ee` (linen). No competing chrome here.
4. **Right column — Doc Reader (450px)** — the answer to "what does this file do?". Opens only when a node is selected. Slides in from the right, pushing layout (not overlaying).

### Why this order

File Tree gives spatial context before the user interacts with the graph. Doc Reader is the result of a graph click — it appears after the action, on the right, matching natural reading direction.

### Structural skeleton

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ header  h=64px  bg=#faf5ee  border-b #d8d0c8                                    │
│ [Corpus]  Explorer · Architecture · Dependencies · Symbols · Overview  [🔍] ⚙ ↺ ❒ │
├────────────────┬────────────────────────────────────────┬───────────────────────┤
│  File Tree     │  Center (tab-dependent)                │  Doc Reader           │
│  w=260px       │  flex-1                                │  w=450px              │
│  flex-shrink=0 │  bg=#faf5ee                            │  bg=#ffffff           │
│  bg=#f6f0e8    │                                        │  slides via           │
│  border-r      │                                        │  translateX(450px)    │
│  #d8d0c8       │                                        │  when closed          │
│                │                                        │                       │
│  toggleable:   │                                        │                       │
│  width:0;      │                                        │                       │
│  overflow:hid  │                                        │                       │
└────────────────┴────────────────────────────────────────┴───────────────────────┘
```

The three columns are a single `display:flex; flex-direction:row` container that takes `flex:1; overflow:hidden` below the header. The header + this flex container form the full 100vh.

---

## 3. tokens.css — Complete Replacement

The entire `:root` block below replaces `frontend/src/styles/tokens.css`. No dark-theme values survive.

```css
:root {
  /* ── Surfaces (all sourced from Stitch Tailwind config) ─────────────────── */
  --color-bg:                #faf5ee;   /* background / surface-bright */
  --color-surface:           #faf5ee;   /* same — body background */
  --color-surface-low:       #f6f0e8;   /* surface-container-low — sidebar bg */
  --color-surface-container: #f2ece4;   /* surface-container */
  --color-surface-high:      #ece6dc;   /* surface-container-high / surface-variant */
  --color-surface-highest:   #e6e0d6;   /* surface-container-highest */
  --color-surface-white:     #ffffff;   /* surface-container-lowest — Doc Reader bg */
  --color-surface-dim:       #dcd6cc;   /* surface-dim */

  /* ── Borders ────────────────────────────────────────────────────────────── */
  --color-border:            #d8d0c8;   /* outline-variant */
  --color-border-strong:     #9a9088;   /* outline */

  /* ── Text ───────────────────────────────────────────────────────────────── */
  --color-text-primary:      #3a302a;   /* on-surface / on-background */
  --color-text-secondary:    #605850;   /* on-surface-variant */
  --color-text-muted:        #9a9088;   /* outline */

  /* ── Accent (burnt sienna) ───────────────────────────────────────────────── */
  --color-accent:            #c2652a;   /* primary / surface-tint */
  --color-accent-dim:        #fbe8d8;   /* primary-fixed — KIND badge background */
  --color-accent-container:  #e08850;   /* primary-container */
  --color-accent-inverse:    #f0a878;   /* inverse-primary / primary-fixed-dim */

  /* ── Node fills (graph canvas) ───────────────────────────────────────────── */
  --color-node-dir:          #c2652a;   /* sienna — dir nodes */
  --color-node-file:         #ffffff;   /* white — fresh file nodes */
  --color-node-stale:        #f59e0b;   /* amber-500 — stale dot/fill */
  --color-node-pulse:        #14b8a6;   /* teal-500 — MCP query pulse */
  --color-node-selected-border: #c2652a; /* primary — selection ring */

  /* ── Edges ────────────────────────────────────────────────────────────────── */
  --color-edge:              rgba(216, 208, 200, 0.6);  /* outline-variant @60% */
  --color-edge-active:       #c2652a;   /* primary — active/selected edges */

  /* ── Staleness badge ─────────────────────────────────────────────────────── */
  --color-stale-badge-bg:    rgba(245, 158, 11, 0.10);  /* amber-500/10 */
  --color-stale-badge-border:rgba(245, 158, 11, 0.20);  /* amber-500/20 */
  --color-stale-badge-text:  #92400e;   /* amber-800 */

  /* ── Panel ────────────────────────────────────────────────────────────────── */
  --color-panel-accent:      #c2652a;

  /* ── Typography ──────────────────────────────────────────────────────────── */
  --font-headline: 'EB Garamond', Georgia, serif;
  --font-body:     'Manrope', system-ui, -apple-system, sans-serif;
  --font-mono:     'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;

  /* Aliases used by existing components — map to new roles */
  --font-sans: var(--font-body);

  /* ── Type scale (px, unchanged from Phase 6) ────────────────────────────── */
  --text-xs:   10px;
  --text-sm:   12px;
  --text-base: 13px;
  --text-md:   14px;
  --text-lg:   15px;
  --text-xl:   20px;

  /* ── Spacing (4/8px base) ────────────────────────────────────────────────── */
  /* Use these in inline styles or class composition. */
  /* 4px = 0.25rem | 8px = 0.5rem | 12px = 0.75rem | 16px = 1rem */
  /* 24px = 1.5rem | 32px = 2rem   | 48px = 3rem   | 64px = 4rem */
}
```

**Note for builder:** The existing `--font-sans` alias is used throughout DocPanel.jsx, App.jsx, and GraphCanvas.jsx via `var(--font-sans)`. Keep the alias pointing to `--font-body` so all existing references continue to work without a find-replace. Do not rename `--font-sans`.

---

## 4. index.html — Font Imports

Add these three `<link>` tags inside `<head>`, before any other stylesheets, in `frontend/index.html`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400..800;1,400..800&family=Manrope:wght@200..800&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
```

The Material Symbols Outlined font is used for icons in the top nav (search, settings, refresh, account_tree) and in DocReader (warning, history, edit, close, arrow_forward, open_in_new). Without it, those elements will show text fallbacks.

---

## 5. App.jsx — Full Layout Structure

### State (what stays from Phase 6, what is added, what is removed)

**Keep (unchanged):**
- `pulseMap` — `Map<node_id, expiry_timestamp>`
- `pulseTimers` ref
- `onQueryEvent` callback (wired to `useGraph`)
- `{ nodes, edges, staleMap, projectName, loading, error, retry }` from `useGraph`
- `collapsedMap` — `Map<nodeId, boolean>`
- `selectedNode` — `node | null`
- `panelOpen` — `boolean`
- `fgRef` — `useRef()` lifted here, passed to GraphCanvas
- `buildDirectChildren`, `buildVisibleIds`, `buildChildCounts` helpers (unchanged)
- `directChildren`, `visibleIds`, `childCounts` memos (unchanged)
- `graphData` memo (unchanged — filters by visibleIds, no importance filter in Phase 7)
- `pulseAncestorIds` memo (unchanged)
- `handleNodeClick` callback (unchanged logic: dir → toggle collapse, file → setSelectedNode + setPanelOpen)
- `closePanel` callback

**Add:**
- `activeTab` — `useState('explorer')` — one of `'explorer' | 'architecture' | 'dependencies' | 'symbols' | 'overview'`
- `fileTreeVisible` — `useState(true)` — controls left column visibility
- `repoRoot` — comes from `useMeta()` hook (new); `string | null`

**Remove:**
- `importanceFilter` state and `filteredVisibleIds` memo — importance filtering is not in Phase 7
- `paletteOpen` state
- `minimapVisible` state
- Imports for `CommandPalette`, `Minimap`, `ImportanceFilter`

**Changed behavior:** `graphData` memo uses `visibleIds` directly (not `filteredVisibleIds`). The importance filter is gone entirely.

### Escape key handler

Replace the existing Ctrl+K handler with an Escape handler that closes the Doc Reader:

```js
useEffect(() => {
  function handleKeyDown(e) {
    if (e.key === 'Escape' && panelOpen) {
      closePanel()
    }
  }
  document.addEventListener('keydown', handleKeyDown)
  return () => document.removeEventListener('keydown', handleKeyDown)
}, [panelOpen, closePanel])
```

### handleNodeClick behavior change

In Phase 7, clicking a file node from the File Tree or any tab always: (1) sets `selectedNode`, (2) sets `panelOpen = true`, and (3) does NOT change `activeTab` unless the caller explicitly does so (SymbolsTab and OverviewTab rows set `activeTab = 'explorer'` themselves before calling `handleNodeClick`).

Pass `setActiveTab` as a prop or lifted callback to tab components that need to switch tabs (SymbolsTab, OverviewTab).

### JSX structure

```jsx
<div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--color-bg)' }}>

  {/* ── Top nav ─────────────────────────────────────────── */}
  <header style={{
    height: 64,
    flexShrink: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 24px',
    background: 'var(--color-surface)',
    borderBottom: '1px solid var(--color-border)',
    zIndex: 30,
  }}>
    {/* Left cluster */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
      {/* Wordmark */}
      <span style={{ fontFamily: 'var(--font-headline)', fontSize: 24, fontWeight: 500, color: 'var(--color-accent)' }}>
        Corpus
      </span>
      {/* Tab links */}
      <nav style={{ display: 'flex', alignItems: 'stretch', height: 64, gap: 0 }}>
        {['explorer', 'architecture', 'dependencies', 'symbols', 'overview'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              fontFamily: 'var(--font-body)',
              fontSize: 14,
              fontWeight: activeTab === tab ? 600 : 500,
              color: activeTab === tab ? 'var(--color-accent)' : 'var(--color-text-secondary)',
              borderBottom: activeTab === tab ? '2px solid var(--color-accent)' : '2px solid transparent',
              borderTop: 'none',
              borderLeft: 'none',
              borderRight: 'none',
              background: 'none',
              padding: '0 16px',
              cursor: 'pointer',
              textTransform: 'capitalize',
              transition: 'color 150ms, border-color 150ms',
            }}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </nav>
    </div>

    {/* Right cluster */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      {/* Search input */}
      <div style={{ position: 'relative' }}>
        <span style={{ /* material-symbols-outlined search icon */ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)', fontSize: 16, pointerEvents: 'none' }} className="material-symbols-outlined">search</span>
        <input
          type="text"
          placeholder="Search nodes..."
          style={{
            paddingLeft: 32, paddingRight: 16, paddingTop: 6, paddingBottom: 6,
            background: 'var(--color-surface-low)',
            border: '1px solid var(--color-border)',
            borderRadius: 9999,
            fontFamily: 'var(--font-body)',
            fontSize: 13,
            color: 'var(--color-text-primary)',
            width: 220,
            outline: 'none',
          }}
          onFocus={e => { e.target.style.borderColor = 'var(--color-accent)'; e.target.style.boxShadow = '0 0 0 1px var(--color-accent)' }}
          onBlur={e => { e.target.style.borderColor = 'var(--color-border)'; e.target.style.boxShadow = 'none' }}
        />
      </div>
      {/* Separator */}
      <div style={{ width: 1, height: 24, background: 'var(--color-border)' }} />
      {/* Refresh */}
      <button
        aria-label="Refresh"
        onClick={() => window.location.reload()}
        style={{ width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', borderRadius: 6, cursor: 'pointer', color: 'var(--color-text-secondary)' }}
        onMouseEnter={e => { e.currentTarget.style.color = 'var(--color-accent)'; e.currentTarget.style.background = 'var(--color-surface-low)' }}
        onMouseLeave={e => { e.currentTarget.style.color = 'var(--color-text-secondary)'; e.currentTarget.style.background = 'none' }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 20 }}>refresh</span>
      </button>
      {/* Settings */}
      <button
        aria-label="Settings"
        style={{ width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', borderRadius: 6, cursor: 'pointer', color: 'var(--color-text-secondary)' }}
        onMouseEnter={e => { e.currentTarget.style.color = 'var(--color-accent)'; e.currentTarget.style.background = 'var(--color-surface-low)' }}
        onMouseLeave={e => { e.currentTarget.style.color = 'var(--color-text-secondary)'; e.currentTarget.style.background = 'none' }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 20 }}>settings</span>
      </button>
      {/* File tree toggle */}
      <button
        aria-label={fileTreeVisible ? 'Hide file tree' : 'Show file tree'}
        aria-pressed={fileTreeVisible}
        onClick={() => setFileTreeVisible(v => !v)}
        style={{
          width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: fileTreeVisible ? 'var(--color-accent-dim)' : 'none',
          border: `1px solid ${fileTreeVisible ? 'var(--color-accent)' : 'var(--color-border)'}`,
          borderRadius: 6, cursor: 'pointer',
          color: fileTreeVisible ? 'var(--color-accent)' : 'var(--color-text-secondary)',
        }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 20 }}>account_tree</span>
      </button>
    </div>
  </header>

  {/* ── Body: three columns ────────────────────────────── */}
  <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

    {/* Column 1: File Tree */}
    <div style={{
      width: fileTreeVisible ? 260 : 0,
      flexShrink: 0,
      overflow: 'hidden',
      transition: 'width 220ms cubic-bezier(0.4, 0, 0.2, 1)',
      borderRight: '1px solid var(--color-border)',
      background: 'var(--color-surface-low)',
    }}>
      <FileTree
        nodes={nodes}
        selectedNodeId={selectedNode?.id ?? null}
        onNodeSelect={handleNodeClick}
        collapsedMap={collapsedMap}
        onToggleCollapse={(nodeId) => setCollapsedMap(prev => { const next = new Map(prev); next.set(nodeId, !(prev.get(nodeId) ?? true)); return next })}
        staleMap={staleMap}
      />
    </div>

    {/* Column 2: Center (tab content) */}
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      {activeTab === 'explorer' && (
        <ExplorerTab
          graphData={graphData}
          staleMap={staleMap}
          collapsedMap={collapsedMap}
          selectedNodeId={selectedNode?.id ?? null}
          onNodeClick={handleNodeClick}
          childCounts={childCounts}
          pulseMap={pulseMap}
          pulseAncestorIds={pulseAncestorIds}
          fgRef={fgRef}
        />
      )}
      {activeTab === 'architecture' && (
        <ArchitectureTab
          graphData={graphData}
          staleMap={staleMap}
          pulseMap={pulseMap}
          pulseAncestorIds={pulseAncestorIds}
          selectedNodeId={selectedNode?.id ?? null}
          onNodeClick={handleNodeClick}
          fgRef={fgRef}
        />
      )}
      {activeTab === 'dependencies' && (
        <DependenciesTab
          graphData={graphData}
          selectedNode={selectedNode}
          onNodeSelect={handleNodeClick}
          staleMap={staleMap}
          pulseMap={pulseMap}
          fgRef={fgRef}
        />
      )}
      {activeTab === 'symbols' && (
        <SymbolsTab
          nodes={nodes}
          onNodeSelect={(node) => { setActiveTab('explorer'); handleNodeClick(node) }}
        />
      )}
      {activeTab === 'overview' && (
        <OverviewTab
          nodes={nodes}
          edges={edges}
          graphData={graphData}
          staleMap={staleMap}
          onNodeSelect={(node) => { setActiveTab('explorer'); handleNodeClick(node) }}
        />
      )}
    </div>

    {/* Column 3: Doc Reader */}
    <DocReader
      node={selectedNode}
      isOpen={panelOpen}
      onClose={closePanel}
      nodes={nodes}
      edges={edges}
      staleMap={staleMap}
      onNodeSelect={handleNodeClick}
      repoRoot={repoRoot}
    />

  </div>
</div>
```

### Loading / error / empty states

These appear in the full-screen center (before the three-column layout renders) and use Sahara tokens:

**Loading:**
```jsx
<div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'100vh', background:'var(--color-bg)', gap:8 }}>
  <span style={{ fontFamily:'var(--font-headline)', fontSize:24, color:'var(--color-text-muted)' }}>Loading...</span>
</div>
```

**Error:**
```jsx
<div style={{ /* same centering */ }}>
  <span style={{ fontFamily:'var(--font-headline)', fontSize:20, color:'var(--color-text-primary)' }}>
    Could not connect to Corpus.
  </span>
  <span style={{ fontFamily:'var(--font-body)', fontSize:13, color:'var(--color-text-muted)', marginTop:4 }}>
    Is corpus serve running on localhost:7077?
  </span>
  <button onClick={retry} style={{ /* outlined sienna button — see tokens */ }}>Retry</button>
</div>
```

**Empty (no nodes):**
```jsx
<span>No files tracked yet.</span>
<span>Run corpus init, then corpus update.</span>
```

---

## 6. GraphCanvas.jsx — Warm Theme Constants + Node Draw

### Color constants (replace the existing dark-theme block at the top of the file)

```js
// ── Sahara warm palette ─────────────────────────────────────────────────────
const COLOR_BG                 = '#faf5ee'   // linen background
const COLOR_NODE_FILE          = '#ffffff'   // white fill — fresh file nodes
const COLOR_NODE_DIR           = '#c2652a'   // sienna fill — dir nodes
const COLOR_NODE_STALE         = '#f59e0b'   // amber-500 — stale nodes
const COLOR_NODE_PULSE         = '#14b8a6'   // teal-500 — MCP query pulse
const COLOR_NODE_SELECTED_RING = '#c2652a'   // sienna — selection ring
const COLOR_EDGE               = 'rgba(216,208,200,0.6)'   // outline-variant @60%
const COLOR_FILE_BORDER        = '#d8d0c8'   // outline-variant — fresh file node border
const COLOR_LABEL              = '#605850'   // on-surface-variant
const COLOR_DIR_BADGE_TEXT     = '#ffffff'   // white text on sienna dir badge

const FONT_LABEL     = "12px 'Manrope', system-ui, sans-serif"
const FONT_DIR_BADGE = "bold 8px 'Manrope', system-ui, sans-serif"
const FONT_DIR_COUNT = "8px 'Manrope', system-ui, sans-serif"
```

### Node radius

```js
function fileRadius(importance) {
  if (importance == null) return 8
  // importance 1 → 9.5px, importance 5 → 14px (capped)
  return Math.min(8 + importance * 1.5, 14)
}

function nodeRadius(node) {
  if (node.type === 'dir') return 18   // larger than Phase 6's 14px for warm aesthetics
  return fileRadius(node.importance)
}
```

### nodeCanvasObject — full draw logic

Replace the existing function body. The shape of arguments and `useCallback` dependency array remain identical.

```js
const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
  const r = nodeRadius(node)
  const isStale = staleMap.get(node.id) ?? !!node.stale
  const isDir = node.type === 'dir'
  const isCollapsed = collapsedMap.get(node.id) ?? true
  const isSelected = node.id === selectedNodeId
  const nodePulsing = isPulsing(node, pulseMap)

  // ── Step 1: fill pass ──────────────────────────────────────────────────────

  if (nodePulsing) {
    // Teal fill + teal glow
    ctx.save()
    ctx.shadowColor = COLOR_NODE_PULSE
    ctx.shadowBlur = 14 / globalScale
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
    ctx.fillStyle = COLOR_NODE_PULSE
    ctx.fill()
    ctx.restore()
  } else if (isDir) {
    // Sienna fill, no border, no glow
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
    ctx.fillStyle = COLOR_NODE_DIR
    ctx.fill()
  } else if (isStale) {
    // Amber fill + soft amber glow
    ctx.save()
    ctx.shadowColor = COLOR_NODE_STALE
    ctx.shadowBlur = 8 / globalScale
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
    ctx.fillStyle = COLOR_NODE_STALE
    ctx.fill()
    ctx.restore()
  } else {
    // Fresh file node: white fill + thin warm-gray border
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
    ctx.fillStyle = COLOR_NODE_FILE
    ctx.fill()
    // Border stroke (warm gray, 1px scaled)
    ctx.strokeStyle = COLOR_FILE_BORDER
    ctx.lineWidth = 1 / globalScale
    ctx.stroke()
  }

  // ── Step 2: pulse ancestor ring (collapsed dir containing a pulsing descendant) ──
  if (isDir && isCollapsed && !nodePulsing && pulseAncestorIds.has(node.id)) {
    ctx.beginPath()
    ctx.arc(node.x, node.y, r + 3, 0, 2 * Math.PI)
    ctx.strokeStyle = COLOR_NODE_PULSE
    ctx.lineWidth = 2 / globalScale
    ctx.stroke()
  }

  // ── Step 3: selection ring ─────────────────────────────────────────────────
  if (isSelected) {
    ctx.beginPath()
    ctx.arc(node.x, node.y, r + 2.5, 0, 2 * Math.PI)
    ctx.strokeStyle = COLOR_NODE_SELECTED_RING
    ctx.lineWidth = 2.5 / globalScale
    ctx.stroke()
  }

  // ── Step 4: dir badge (▶ + collapsed child count) ─────────────────────────
  if (isDir && isCollapsed) {
    const count = childCounts.get(node.id) ?? 0
    if (count > 0) {
      ctx.fillStyle = COLOR_DIR_BADGE_TEXT
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.font = FONT_DIR_BADGE
      ctx.fillText('▶', node.x, node.y - 2)
      ctx.font = FONT_DIR_COUNT
      ctx.fillText(String(count), node.x, node.y + 6)
    }
  }

  // ── Step 5: label ──────────────────────────────────────────────────────────
  if (globalScale >= 0.15) {
    const label = lastName(node.path)
    const labelY = node.y + r + 6
    ctx.font = FONT_LABEL
    ctx.fillStyle = COLOR_LABEL
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillText(label, node.x, labelY)
  }
}, [staleMap, collapsedMap, selectedNodeId, childCounts, pulseMap, pulseAncestorIds])
```

### Container div background

```jsx
<div
  style={{
    flex: 1,
    height: '100%',
    overflow: 'hidden',
    position: 'relative',
    background: COLOR_BG,
    backgroundImage: `linear-gradient(to right, rgba(58,48,42,0.04) 1px, transparent 1px),
                      linear-gradient(to bottom, rgba(58,48,42,0.04) 1px, transparent 1px)`,
    backgroundSize: '32px 32px',
  }}
>
```

(The grid lines use warm dark `rgba(58,48,42,0.04)` instead of the dark-theme `rgba(255,255,255,0.03)`.)

### linkColor change

```js
const linkColor = useCallback(() => 'rgba(216,208,200,0.6)', [])
```

### Zoom controls (inside ExplorerTab / on graph views)

The zoom controls that were bottom-left absolutely positioned in Phase 6 App.jsx now live inside the graph container wrapper in ExplorerTab (and ArchitectureTab, DependenciesTab). Background changes from the dark glassmorphism to a warm surface:

```js
background: 'rgba(250,245,238,0.9)'   // --color-bg at 90% opacity
border: '1px solid var(--color-border)'
color: 'var(--color-text-secondary)'
```

---

## 7. FileTree.jsx — New Component

**File:** `frontend/src/components/FileTree.jsx`

### Props

```js
FileTree({
  nodes,          // Node[] — full node list from useGraph
  selectedNodeId, // string | null
  onNodeSelect,   // (node) => void — called on file click or dir toggle
  collapsedMap,   // Map<nodeId, boolean>
  onToggleCollapse, // (nodeId) => void
  staleMap,       // Map<nodeId, boolean>
})
```

### Tree structure derivation

Build a tree from node paths before rendering. This runs inside a `useMemo([nodes])`:

```js
function buildTree(nodes) {
  // Returns array of tree items sorted: dirs first, then files, both alpha within group
  // Each item: { node, depth, children: [] | null }
  // 'children' is null for file nodes; [] (possibly empty) for dir nodes

  const byPath = new Map(nodes.map(n => [n.path, n]))

  // Find root-level items: nodes whose parent path does not correspond to any dir node
  // Depth = number of '/' separators in path (depth 0 = root segment)

  const rootItems = []

  function buildNode(node, depth) {
    const item = { node, depth, children: null }
    if (node.type === 'dir') {
      // Direct children: nodes whose path is node.path + '/' + single-segment
      const prefix = node.path + '/'
      const directChildren = nodes.filter(n => {
        if (!n.path.startsWith(prefix)) return false
        const rest = n.path.slice(prefix.length)
        return !rest.includes('/')   // one level down only
      })
      directChildren.sort((a, b) => {
        // dirs first, then alpha
        if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
        return a.path.localeCompare(b.path)
      })
      item.children = directChildren.map(child => buildNode(child, depth + 1))
    }
    return item
  }

  // Root-level nodes: path has no '/' OR parent path is not a dir node
  const rootNodes = nodes.filter(n => {
    const lastSlash = n.path.lastIndexOf('/')
    if (lastSlash === -1) return true   // no slash = root level
    const parentPath = n.path.slice(0, lastSlash)
    const parentNode = byPath.get(parentPath)
    return !parentNode || parentNode.type !== 'dir'
  })

  rootNodes.sort((a, b) => {
    if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
    return a.path.localeCompare(b.path)
  })

  return rootNodes.map(n => buildNode(n, 0))
}
```

### Rendering

The component renders a scrollable `<div style={{ overflowY: 'auto', height: '100%', padding: '8px 0' }}>`. Recurse over tree items.

**Dir row:**
```jsx
<div
  key={item.node.id}
  onClick={() => onToggleCollapse(item.node.id)}
  role="treeitem"
  aria-expanded={!isCollapsed}
  style={{
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    padding: `5px 12px 5px ${12 + item.depth * 16}px`,
    cursor: 'pointer',
    userSelect: 'none',
    color: 'var(--color-text-primary)',
  }}
  onMouseEnter={e => e.currentTarget.style.background = 'var(--color-surface-container)'}
  onMouseLeave={e => e.currentTarget.style.background = 'none'}
>
  {/* Chevron — rotates when expanded */}
  <span style={{
    display: 'inline-block',
    fontSize: 10,
    color: 'var(--color-text-muted)',
    transform: isCollapsed ? 'rotate(0deg)' : 'rotate(90deg)',
    transition: 'transform 150ms',
    width: 12,
    flexShrink: 0,
  }}>▶</span>

  {/* Name */}
  <span style={{
    fontFamily: 'var(--font-headline)',
    fontSize: 14,
    fontWeight: 600,
    color: 'var(--color-text-primary)',
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  }}>
    {lastName(item.node.path)}
  </span>

  {/* Stale dot */}
  {isStale && (
    <div style={{
      width: 8,
      height: 8,
      borderRadius: '50%',
      background: '#f59e0b',
      flexShrink: 0,
    }} title="Documentation stale" />
  )}
</div>
```

**File row:**
```jsx
<div
  key={item.node.id}
  onClick={() => onNodeSelect(item.node)}
  role="treeitem"
  aria-selected={isSelected}
  style={{
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    padding: `4px 12px 4px ${12 + item.depth * 16 + 16}px`,  // +16 to align past chevron
    cursor: 'pointer',
    userSelect: 'none',
    borderLeft: isSelected ? '3px solid var(--color-accent)' : '3px solid transparent',
    background: isSelected ? 'var(--color-surface-container)' : 'none',
    color: isSelected ? 'var(--color-accent)' : 'var(--color-text-secondary)',
  }}
  onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'var(--color-surface-low)' }}
  onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'none' }}
>
  {/* Name */}
  <span style={{
    fontFamily: 'var(--font-body)',
    fontSize: 13,
    fontWeight: isSelected ? 600 : 500,
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  }}>
    {lastName(item.node.path)}
  </span>

  {/* Stale dot */}
  {isStale && (
    <div style={{
      width: 8,
      height: 8,
      borderRadius: '50%',
      background: '#f59e0b',
      flexShrink: 0,
    }} title="Documentation stale" />
  )}
</div>
```

**Collapsed dir: do not render its children.** When `collapsedMap.get(node.id) ?? true` is `true`, skip the children array entirely.

**Root-level dirs are expanded by default.** The `collapsedMap` starts as an empty `Map`. The `??` fallback of `true` means all dirs start collapsed unless explicitly set to `false`. For Phase 7, change the default: root-level dirs (depth 0) should default to `false` (expanded). Implement this by seeding `collapsedMap` initial state in App.jsx after first load:

```js
// In App.jsx, after nodes load (in a useEffect on nodes):
useEffect(() => {
  if (!nodes || nodes.length === 0) return
  setCollapsedMap(prev => {
    const next = new Map(prev)
    for (const n of nodes) {
      if (n.type !== 'dir') continue
      // depth = number of '/' in path
      const depth = (n.path.match(/\//g) || []).length
      if (depth === 0 && !prev.has(n.id)) {
        next.set(n.id, false)  // root dirs start expanded
      }
    }
    return next
  })
}, [nodes])
```

### States

- **Empty (no nodes):** render `<div style={{ padding: 24, color: 'var(--color-text-muted)', fontFamily: 'var(--font-body)', fontSize: 13 }}>No files tracked.</div>`
- **Normal:** scrollable tree as above
- **All files in one flat dir:** renders flat list of file rows with no nesting indentation

### Touch targets

Each row has `min-height: 36px` (enforce via `padding: 5px 12px` which yields ~36px on 14px line-height). This meets the 44px recommendation only in combination with finger size; accept 36px as minimum for a developer tool, explicitly documented.

---

## 8. Tab Components

### 8a. ExplorerTab.jsx

**File:** `frontend/src/components/tabs/ExplorerTab.jsx`

```jsx
import { GraphCanvas } from '../GraphCanvas.jsx'

export function ExplorerTab({ graphData, staleMap, collapsedMap, selectedNodeId, onNodeClick, childCounts, pulseMap, pulseAncestorIds, fgRef }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
      <GraphCanvas
        fgRef={fgRef}
        graphData={graphData}
        staleMap={staleMap}
        collapsedMap={collapsedMap}
        selectedNodeId={selectedNodeId}
        onNodeClick={onNodeClick}
        childCounts={childCounts}
        pulseMap={pulseMap}
        pulseAncestorIds={pulseAncestorIds}
      />
      {/* Zoom controls — absolute, bottom-left of this column */}
      <ZoomControls fgRef={fgRef} />
      {/* Stats bar — absolute, bottom-left below zoom */}
      <StatsBar graphData={graphData} />
    </div>
  )
}
```

`ZoomControls` and `StatsBar` are small inline sub-components within ExplorerTab (or extracted to shared components if also used in ArchitectureTab). Their styles change from the dark glassmorphism to warm surfaces:

```js
// Warm zoom controls style
background: 'rgba(250,245,238,0.92)'
border: '1px solid var(--color-border)'
color: 'var(--color-text-secondary)'
// hover: color = var(--color-accent)
```

---

### 8b. ArchitectureTab.jsx

**File:** `frontend/src/components/tabs/ArchitectureTab.jsx`

**Props:** `{ graphData, staleMap, pulseMap, pulseAncestorIds, selectedNodeId, onNodeClick, fgRef }`

**Dir-only graph derivation (inside `useMemo([graphData])`):**

```js
const archGraphData = useMemo(() => {
  if (!graphData || !graphData.nodes) return { nodes: [], links: [] }

  // 1. Filter to dir nodes only
  const dirNodes = graphData.nodes.filter(n => n.type === 'dir')
  const dirNodeIds = new Set(dirNodes.map(n => n.id))

  // 2. Build a map from file node id → parent dir node id
  //    Parent dir = the dir node whose path is the immediate parent of the file
  const fileToDir = new Map()
  const dirByPath = new Map(dirNodes.map(n => [n.path, n]))

  for (const n of graphData.nodes) {
    if (n.type !== 'file') continue
    const lastSlash = n.path.lastIndexOf('/')
    if (lastSlash === -1) continue
    const parentPath = n.path.slice(0, lastSlash)
    const parentDir = dirByPath.get(parentPath)
    if (parentDir) fileToDir.set(n.id, parentDir.id)
  }

  // 3. Derive dir-to-dir edges
  //    For each link (source_file → target_file), look up both dirs.
  //    If they differ, add edge (source_dir → target_dir).
  //    Deduplicate by "sourceDir|targetDir" string key.
  const edgeSet = new Set()
  const dirLinks = []

  for (const link of graphData.links) {
    const srcId = link.source?.id ?? link.source
    const tgtId = link.target?.id ?? link.target
    const srcDir = fileToDir.get(srcId)
    const tgtDir = fileToDir.get(tgtId)
    if (!srcDir || !tgtDir || srcDir === tgtDir) continue
    if (!dirNodeIds.has(srcDir) || !dirNodeIds.has(tgtDir)) continue
    const key = `${srcDir}|${tgtDir}`
    if (edgeSet.has(key)) continue
    edgeSet.add(key)
    dirLinks.push({ source: srcDir, target: tgtDir })
  }

  return { nodes: dirNodes, links: dirLinks }
}, [graphData])
```

Pass `archGraphData` to `<GraphCanvas>`. The `collapsedMap` and `childCounts` props are not relevant here (dirs are never collapsed in the architecture view). Pass empty `new Map()` for both.

**Note:** `selectedNodeId` and `onNodeClick` still work normally — clicking a dir node opens the Doc Reader with that dir's `_dir.md`.

---

### 8c. DependenciesTab.jsx

**File:** `frontend/src/components/tabs/DependenciesTab.jsx`

**Props:** `{ graphData, selectedNode, onNodeSelect, staleMap, pulseMap, fgRef }`

**Empty state (no file selected or selected node is a dir):**

```jsx
{(!selectedNode || selectedNode.type === 'dir') && (
  <div style={{
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  }}>
    <span style={{
      fontFamily: 'var(--font-headline)',
      fontStyle: 'italic',
      fontSize: 20,
      color: 'var(--color-text-muted)',
    }}>
      Select a file to explore its dependency graph.
    </span>
  </div>
)}
```

**Subgraph derivation (inside `useMemo([graphData, selectedNode])`):**

```js
const depGraphData = useMemo(() => {
  if (!selectedNode || selectedNode.type === 'dir' || !graphData.nodes) return null

  const nodeById = new Map(graphData.nodes.map(n => [n.id, n]))
  const centerId = selectedNode.id

  // Collect 1-hop neighbors
  const includedIds = new Set([centerId])

  for (const link of graphData.links) {
    const srcId = link.source?.id ?? link.source
    const tgtId = link.target?.id ?? link.target
    if (srcId === centerId) includedIds.add(tgtId)
    if (tgtId === centerId) includedIds.add(srcId)
  }

  const subNodes = [...includedIds]
    .map(id => nodeById.get(id))
    .filter(Boolean)

  const subLinks = graphData.links.filter(link => {
    const srcId = link.source?.id ?? link.source
    const tgtId = link.target?.id ?? link.target
    return includedIds.has(srcId) && includedIds.has(tgtId)
  })

  return { nodes: subNodes, links: subLinks }
}, [graphData, selectedNode])
```

Render `<GraphCanvas>` with `depGraphData`. Pass `staleMap`, `pulseMap`. No `collapsedMap` needed (pass `new Map()`). No `childCounts` (pass `new Map()`). Pass `selectedNodeId={selectedNode?.id}` and `onNodeClick={onNodeSelect}`.

**Layout hint for the subgraph:** After `depGraphData` is set, call `fgRef.current?.zoomToFit(400, 60)` in a `useEffect([depGraphData])` to frame the subgraph.

---

### 8d. SymbolsTab.jsx

**File:** `frontend/src/components/tabs/SymbolsTab.jsx`

**Props:** `{ nodes, onNodeSelect }`

**Symbol flattening (inside `useMemo([nodes])`):**

```js
const allSymbols = useMemo(() => {
  if (!nodes) return []
  const result = []
  for (const node of nodes) {
    if (!node.symbols || node.type !== 'file') continue
    for (const sym of node.symbols) {
      result.push({
        name: sym.name,
        kind: (sym.kind || 'SYMBOL').toUpperCase(),
        filePath: node.path,
        fileName: lastName(node.path),
        nodeId: node.id,
        node,   // keep reference for onNodeSelect
      })
    }
  }
  result.sort((a, b) => a.name.localeCompare(b.name))
  return result
}, [nodes])
```

**Filtered list:** `const filtered = allSymbols.filter(s => s.name.toLowerCase().includes(query.toLowerCase()))`

**Layout:**

```
┌───────────────────────────────────────────────────────────────┐
│  [search input — full width, border, rounded-lg, 40px tall]   │
├───────────────────────────────────────────────────────────────┤
│  Name               │  Kind         │  File                   │
│  (Manrope 13px)     │  (badge pill) │  (text-muted, truncate) │
├───────────────────────────────────────────────────────────────┤
│  ...rows...                                                    │
└───────────────────────────────────────────────────────────────┘
```

**Search input styling:**
```js
style={{
  padding: '10px 16px',
  border: '1px solid var(--color-border)',
  borderRadius: 8,
  fontFamily: 'var(--font-body)',
  fontSize: 14,
  color: 'var(--color-text-primary)',
  background: 'var(--color-surface-white)',
  width: '100%',
  boxSizing: 'border-box',
  outline: 'none',
}}
// focus: borderColor = var(--color-accent), boxShadow = '0 0 0 1px var(--color-accent)'
```

**Table:**
- Container: `<div style={{ flex:1, overflowY:'auto' }}>` wrapping `<table style={{ width:'100%', borderCollapse:'collapse' }}>`
- Header row: `background: var(--color-surface-low)`, sticky top 0, `font-family: var(--font-body)`, `font-size: 11px`, `font-weight: 600`, `text-transform: uppercase`, `letter-spacing: 0.06em`, `color: var(--color-text-muted)`, `padding: 8px 16px`
- Data rows: `padding: 10px 16px`, `border-bottom: 1px solid var(--color-border)`. Hover: `background: var(--color-surface-low)`. Cursor: pointer.

**Kind badge:**
```js
// CLASS
{ background: 'var(--color-accent-dim)', color: 'var(--color-accent)' }
// FUNCTION
{ background: 'var(--color-surface-high)', color: 'var(--color-text-secondary)' }
// other (METHOD, VARIABLE, etc.)
{ background: 'none', border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }

// All badges: font-size: 10px, font-weight: 700, padding: 2px 6px, border-radius: 4px, text-transform: uppercase, letter-spacing: 0.05em, white-space: nowrap
```

**File cell:** `font-family: var(--font-mono)`, `font-size: 12px`, `color: var(--color-text-muted)`. Truncate from left if long: show only the `lastName(filePath)` in the table, with the full path as a `title` attribute.

**Click row:** calls `onNodeSelect(row.node)` — App.jsx's wrapper sets `activeTab = 'explorer'` first.

**Empty state (no symbols indexed):**
```jsx
<div style={{ padding: 48, textAlign: 'center' }}>
  <p style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--color-text-muted)' }}>
    No symbols indexed yet. Run <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--color-surface-high)', padding: '2px 6px', borderRadius: 4 }}>corpus update</code> to index symbols.
  </p>
</div>
```

**Empty state (search returns no results):**
```jsx
<tr><td colSpan={3} style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--color-text-muted)', fontFamily: 'var(--font-body)', fontSize: 13 }}>No symbols match "{query}".</td></tr>
```

**Large dataset:** If `allSymbols.length > 500`, render a warning banner below the search input:
```jsx
<div style={{ padding: '8px 16px', background: 'var(--color-accent-dim)', color: 'var(--color-accent)', fontFamily: 'var(--font-body)', fontSize: 12, borderBottom: '1px solid var(--color-border)' }}>
  {allSymbols.length} symbols — showing first 500. Use search to narrow results.
</div>
```
Then `filtered.slice(0, 500)` for the rendered rows.

---

### 8e. OverviewTab.jsx

**File:** `frontend/src/components/tabs/OverviewTab.jsx`

**Props:** `{ nodes, edges, graphData, staleMap, onNodeSelect }`

Uses `useDoc` hook to fetch root dir doc. Uses `ReactMarkdown` with Sahara `mdComponents`.

**Layout:** scrollable column, `padding: 32px 48px`, `max-width: 900px`, `margin: 0 auto`.

#### Section 1 — Stat chips row

```js
const fileCount = nodes.filter(n => n.type === 'file').length
const dirCount = nodes.filter(n => n.type === 'dir').length
const edgeCount = edges ? edges.length : 0
const staleCount = nodes.filter(n => staleMap.get(n.id) === true).length
```

Chips row: `display: flex`, `gap: 16px`, `margin-bottom: 48px`. Each chip:

```jsx
<div style={{
  flex: 1,
  background: 'var(--color-surface-white)',
  border: '1px solid var(--color-border)',
  borderRadius: 12,
  padding: '24px 20px',
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}}>
  <span style={{ fontFamily: 'var(--font-headline)', fontSize: 36, fontWeight: 700, color: 'var(--color-accent)', lineHeight: 1 }}>
    {count}
  </span>
  <span style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
    {label}
  </span>
</div>
```

Labels: "Files", "Directories", "Edges", "Stale".

#### Section 2 — About this project

Find the root dir node: `nodes.find(n => n.type === 'dir' && !n.path.includes('/'))`. If found, call `useDoc(rootDirNode?.path)`. Path passed to `useDoc` follows the same pattern as DocPanel — just `node.path`, and the server constructs the `.corpus/docs/<path>.md` path.

If loading: show `<p style={{ color: 'var(--color-text-muted)' }}>Loading project summary...</p>`.
If error or no content: show `<p style={{ color: 'var(--color-text-muted)', fontStyle: 'italic' }}>No project doc found.</p>`.

Heading style: `fontFamily: 'var(--font-headline)'`, `fontSize: 22`, `fontWeight: 600`, `color: 'var(--color-text-primary)'`, `margin-bottom: 16px`, `border-bottom: 1px solid var(--color-border)`, `padding-bottom: 8px`.

`mdComponents` for OverviewTab — same as DocReader (defined once, imported by both, or duplicated — builder chooses):

```js
const mdComponents = {
  h1: ({ children }) => <h1 style={{ fontFamily: 'var(--font-headline)', fontSize: 20, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 12, marginTop: 0 }}>{children}</h1>,
  h2: ({ children }) => <h2 style={{ fontFamily: 'var(--font-headline)', fontSize: 16, fontWeight: 600, color: 'var(--color-text-primary)', borderBottom: '1px solid var(--color-border)', paddingBottom: 4, marginBottom: 8, marginTop: 24 }}>{children}</h2>,
  h3: ({ children }) => <h3 style={{ fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: 8, marginTop: 16 }}>{children}</h3>,
  p: ({ children }) => <p style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--color-text-secondary)', lineHeight: 1.7, marginBottom: 12 }}>{children}</p>,
  code: ({ inline, children }) => inline
    ? <code style={{ fontFamily: 'var(--font-mono)', fontSize: 12, background: 'var(--color-surface-high)', padding: '2px 5px', borderRadius: 3, color: 'var(--color-accent)' }}>{children}</code>
    : <code style={{ fontFamily: 'var(--font-mono)', fontSize: 12, display: 'block', background: 'var(--color-surface-high)', borderRadius: 6, padding: '12px 16px', color: 'var(--color-text-secondary)', overflowX: 'auto', borderLeft: '3px solid var(--color-accent)' }}>{children}</code>,
  a: ({ href, children }) => <a href={href} style={{ color: 'var(--color-accent)', textDecoration: 'none' }} onMouseEnter={e => e.currentTarget.style.textDecoration = 'underline'} onMouseLeave={e => e.currentTarget.style.textDecoration = 'none'}>{children}</a>,
  ul: ({ children }) => <ul style={{ paddingLeft: 20, listStyle: 'disc', color: 'var(--color-text-secondary)', marginBottom: 12 }}>{children}</ul>,
  li: ({ children }) => <li style={{ fontFamily: 'var(--font-body)', fontSize: 14, lineHeight: 1.7 }}>{children}</li>,
}
```

#### Section 3 — Most Important

```js
const mostImportant = [...nodes]
  .filter(n => n.type === 'file' && n.importance != null)
  .sort((a, b) => b.importance - a.importance)
  .slice(0, 5)
```

#### Section 4 — Most Connected

```js
// Compute degree per node
const degreeMap = new Map()
if (edges) {
  for (const e of edges) {
    const srcId = e.source?.id ?? e.source
    const tgtId = e.target?.id ?? e.target
    degreeMap.set(srcId, (degreeMap.get(srcId) ?? 0) + 1)
    degreeMap.set(tgtId, (degreeMap.get(tgtId) ?? 0) + 1)
  }
}
const mostConnected = [...nodes]
  .filter(n => n.type === 'file')
  .sort((a, b) => (degreeMap.get(b.id) ?? 0) - (degreeMap.get(a.id) ?? 0))
  .slice(0, 5)
```

#### Section 5 — Stale Files

```js
const staleFiles = nodes.filter(n => staleMap.get(n.id) === true)
```

If `staleFiles.length === 0`: `<p style={{ fontStyle: 'italic', color: 'var(--color-text-muted)' }}>All files are up to date.</p>`

**Row style (used in sections 3, 4, 5):**
```jsx
<div
  onClick={() => onNodeSelect(node)}
  style={{
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '10px 16px',
    background: 'var(--color-surface-white)',
    border: '1px solid var(--color-border)',
    borderRadius: 8,
    cursor: 'pointer',
    marginBottom: 6,
    transition: 'border-color 120ms',
  }}
  onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--color-accent)'}
  onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--color-border)'}
>
  {/* For stale rows: amber dot */}
  {section === 'stale' && <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b', flexShrink: 0 }} />}

  {/* Name */}
  <span style={{ fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', flex: 1 }}>
    {lastName(node.path)}
  </span>

  {/* Importance pill (sections 3) */}
  {section === 'important' && (
    <span style={{ background: 'var(--color-accent-dim)', color: 'var(--color-accent)', fontFamily: 'var(--font-body)', fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4 }}>
      {node.importance}
    </span>
  )}

  {/* Degree count (section 4) */}
  {section === 'connected' && (
    <span style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
      {degreeMap.get(node.id) ?? 0} edges
    </span>
  )}

  {/* Path (muted) */}
  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }}>
    {node.path}
  </span>
</div>
```

**`degreeMap`, `mostImportant`, `mostConnected`, `staleFiles` are all computed inside `useMemo([nodes, edges, staleMap])`.**

---

## 9. DocReader.jsx — Replaces DocPanel.jsx

**File:** `frontend/src/components/DocReader.jsx` (new file name).

**Note to builder:** `DocPanel.jsx` is the target. You may either rename it to `DocReader.jsx` and update the import in App.jsx, or rewrite it in place as `DocPanel.jsx` with the export renamed to `DocReader`. Either is acceptable. Do not leave both files in the repo.

### Props

```js
DocReader({
  node,         // Node | null
  isOpen,       // boolean
  onClose,      // () => void
  nodes,        // Node[]
  edges,        // Edge[]
  staleMap,     // Map<nodeId, boolean>
  onNodeSelect, // (node) => void
  repoRoot,     // string | null — from useMeta()
})
```

### Position and slide mechanic

The Doc Reader is the **third column** in the flex layout, not an absolute overlay. It always occupies 450px but slides its content out via `transform: translateX` on its inner container, OR uses `width` transition. Choose `width` transition for column layout (so the center column expands when Doc Reader closes):

```jsx
<div style={{
  width: isOpen ? 450 : 0,
  flexShrink: 0,
  overflow: 'hidden',
  transition: 'width 220ms cubic-bezier(0.4, 0, 0.2, 1)',
  borderLeft: isOpen ? '1px solid var(--color-border)' : 'none',
}}>
  <div style={{
    width: 450,
    height: '100%',
    background: 'var(--color-surface-white)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  }}>
    {/* panel content */}
  </div>
</div>
```

This means the panel never overlays — it displaces the center column by 450px when open, matching the PLAN.md spec.

### Header (sticky)

```jsx
<div style={{
  padding: '20px 24px 16px',
  borderBottom: '1px solid var(--color-border)',
  background: 'rgba(250,245,238,0.8)',
  backdropFilter: 'blur(8px)',
  position: 'sticky',
  top: 0,
  zIndex: 5,
  flexShrink: 0,
}}>
  {/* Row 1: type badge + edit button + close button */}
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--color-accent)' }}>
        {/* icon based on type: 'description' for file, 'folder' for dir */}
        {node?.type === 'dir' ? 'folder' : 'description'}
      </span>
      <span style={{
        fontFamily: 'var(--font-body)',
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--color-accent)',
      }}>
        {typeLabel(node)}   {/* see typeLabel() below */}
      </span>
    </div>
    <div style={{ display: 'flex', gap: 4 }}>
      {/* Edit button — opens file in VS Code */}
      <button
        aria-label="Open in editor"
        onClick={() => {
          if (repoRoot && node) window.open(`vscode://file/${repoRoot}/${node.path}`)
        }}
        disabled={!repoRoot || !node}
        title={repoRoot ? `Open ${node?.path} in VS Code` : 'repoRoot not available — corpus serve needed'}
        style={{
          width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'none', border: 'none', borderRadius: 6, cursor: repoRoot ? 'pointer' : 'not-allowed',
          color: repoRoot ? 'var(--color-text-secondary)' : 'var(--color-text-muted)',
        }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>edit</span>
      </button>
      {/* Close button */}
      <button
        aria-label="Close doc reader"
        onClick={onClose}
        style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', borderRadius: 6, cursor: 'pointer', color: 'var(--color-text-secondary)' }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--color-text-primary)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--color-text-secondary)'}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
      </button>
    </div>
  </div>

  {/* Row 2: filename in EB Garamond */}
  <h2 style={{
    fontFamily: 'var(--font-headline)',
    fontSize: 28,
    fontWeight: 700,
    color: 'var(--color-text-primary)',
    lineHeight: 1.1,
    margin: '0 0 6px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  }}>
    {node ? lastName(node.path) : ''}
  </h2>

  {/* Row 3: breadcrumb */}
  <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'nowrap', overflow: 'hidden', gap: 4, marginBottom: 4 }}>
    {/* existing breadcrumb logic from Phase 6 DocPanel — keep it unchanged, restyle colors only */}
    {/* ancestor segments: color = var(--color-text-muted), clickable */}
    {/* last segment: color = var(--color-accent), not clickable */}
  </div>

  {/* Row 4: staleness line */}
  <p style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>history</span>
    {isStale ? 'Documentation may be outdated' : 'Documentation up to date'}
  </p>
</div>
```

**`typeLabel(node)` function:**
```js
function typeLabel(node) {
  if (!node) return ''
  if (node.type === 'dir') return 'Directory'
  const ext = node.path.split('.').pop().toLowerCase()
  const map = {
    py: 'Python Module',
    js: 'JavaScript Module',
    jsx: 'JavaScript Module',
    ts: 'TypeScript Module',
    tsx: 'TypeScript Module',
    md: 'Markdown',
    json: 'JSON',
    css: 'Stylesheet',
    html: 'HTML',
  }
  return map[ext] || 'File'
}
```

### Stale warning box

Render immediately after the header, inside the scrollable body, only when `isStale === true`:

```jsx
{isStale && (
  <div style={{
    margin: '16px 24px 0',
    padding: '12px 16px',
    background: 'var(--color-stale-badge-bg)',   /* rgba(245,158,11,0.10) */
    border: '1px solid var(--color-stale-badge-border)',  /* rgba(245,158,11,0.20) */
    borderRadius: 12,
    display: 'flex',
    gap: 12,
    alignItems: 'flex-start',
  }}>
    <span className="material-symbols-outlined" style={{ color: '#d97706', fontSize: 20, marginTop: 1, flexShrink: 0 }}>warning</span>
    <div>
      <h4 style={{ fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 700, color: '#92400e', margin: '0 0 4px' }}>
        Documentation Stale
      </h4>
      <p style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: '#b45309', margin: 0, lineHeight: 1.5 }}>
        Source code has changed significantly since this documentation was generated. Review recommended.
      </p>
    </div>
  </div>
)}
```

### Doc body (scrollable `flex: 1, overflow-y: auto`)

Content order:
1. Stale warning box (above)
2. ReactMarkdown of fetched doc content (Sahara mdComponents)
3. Key Symbols section
4. Dependencies section
5. Backlinks section
6. Open in Editor button

**Loading state:**
```jsx
<p style={{ padding: '24px', fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)' }}>Loading documentation...</p>
```

**No doc state:**
```jsx
<p style={{ /* same */ }}>No documentation generated yet. Run <code>corpus update</code> to generate docs.</p>
```

**Error state:**
```jsx
<p>Could not load this file's doc.</p>
<button onClick={retry}>Retry</button>
```

#### Key Symbols section

```jsx
{node?.symbols && node.symbols.length > 0 && (
  <div style={{ padding: '0 24px', marginTop: 24 }}>
    <h3 style={{ fontFamily: 'var(--font-headline)', fontSize: 18, fontWeight: 600, color: 'var(--color-text-primary)', borderBottom: '1px solid var(--color-border)', paddingBottom: 8, marginBottom: 16 }}>
      Key Symbols
    </h3>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {node.symbols.map(sym => (
        <div key={sym.name} style={{
          padding: '14px 16px',
          background: 'var(--color-surface)',
          borderRadius: 10,
          border: '1px solid var(--color-border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: sym.description ? 6 : 0 }}>
            {/* KIND badge — matches Stitch exactly */}
            <span style={{
              background: sym.kind?.toUpperCase() === 'CLASS' ? 'var(--color-accent-dim)' : 'rgba(96,88,80,0.08)',
              color: sym.kind?.toUpperCase() === 'CLASS' ? 'var(--color-accent)' : 'var(--color-text-secondary)',
              fontFamily: 'var(--font-body)',
              fontSize: 10,
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: 4,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}>
              {sym.kind || 'SYMBOL'}
            </span>
            <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)' }}>
              {sym.name}
            </span>
          </div>
          {sym.description && (
            <p style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-secondary)', margin: 0, lineHeight: 1.6 }}>
              {sym.description}
            </p>
          )}
        </div>
      ))}
    </div>
  </div>
)}
```

#### Dependencies section (outgoing edges)

```js
const outgoingDeps = useMemo(() => {
  if (!edges || !node) return []
  const nodeById = new Map((nodes || []).map(n => [n.id, n]))
  return edges
    .filter(e => (e.source?.id ?? e.source) === node.id)
    .map(e => nodeById.get(e.target?.id ?? e.target))
    .filter(Boolean)
}, [edges, nodes, node])
```

```jsx
{outgoingDeps.length > 0 && (
  <div style={{ padding: '0 24px', marginTop: 24 }}>
    <h3 style={{ /* same heading style */ }}>Dependencies</h3>
    <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
      {outgoingDeps.map(dep => (
        <li key={dep.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--color-text-muted)' }}>arrow_forward</span>
          <button
            onClick={() => onNodeSelect(dep)}
            style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-accent)', textDecoration: 'none' }}
            onMouseEnter={e => e.currentTarget.style.textDecoration = 'underline'}
            onMouseLeave={e => e.currentTarget.style.textDecoration = 'none'}
          >
            {lastName(dep.path)}
          </button>
        </li>
      ))}
    </ul>
  </div>
)}
```

#### Backlinks section (incoming edges — keep Phase 6 logic)

```js
const backlinks = useMemo(() => {
  if (!edges || !node) return []
  const nodeById = new Map((nodes || []).map(n => [n.id, n]))
  return edges
    .filter(e => (e.target?.id ?? e.target) === node.id)
    .map(e => nodeById.get(e.source?.id ?? e.source))
    .filter(Boolean)
}, [edges, nodes, node])
```

Section heading: "Imported by". Chip style:
```js
{
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  padding: '4px 10px',
  background: 'var(--color-surface-container)',
  border: '1px solid var(--color-border)',
  borderRadius: 4,
  color: 'var(--color-text-secondary)',
  cursor: 'pointer',
}
// hover: borderColor = var(--color-accent), color = var(--color-accent)
```

Show all chips (no 10-item truncation in Phase 7). If `backlinks.length === 0`, omit the section entirely.

#### Open in Editor button

Render at the bottom of the scrollable content area (not a sticky footer):

```jsx
<div style={{ padding: '24px', paddingTop: 8 }}>
  <a
    href={repoRoot && node ? `vscode://file/${repoRoot}/${node.path}` : undefined}
    onClick={e => { if (!repoRoot || !node) e.preventDefault() }}
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      width: '100%',
      padding: '10px 0',
      background: 'var(--color-surface)',
      color: 'var(--color-accent)',
      border: '1px solid rgba(194,101,42,0.30)',
      borderRadius: 8,
      fontFamily: 'var(--font-body)',
      fontSize: 13,
      fontWeight: 600,
      textDecoration: 'none',
      cursor: repoRoot && node ? 'pointer' : 'not-allowed',
      opacity: repoRoot && node ? 1 : 0.5,
      transition: 'background 120ms',
    }}
    onMouseEnter={e => { if (repoRoot && node) e.currentTarget.style.background = 'rgba(194,101,42,0.05)' }}
    onMouseLeave={e => e.currentTarget.style.background = 'var(--color-surface)'}
    title={!repoRoot ? 'repoRoot not available — start corpus serve to enable this' : undefined}
  >
    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>open_in_new</span>
    Open in Editor
  </a>
</div>
```

### Escape key (useEffect)

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

### Empty state (no node selected, panel open=false)

When `isOpen === false`, the panel has `width: 0` — nothing is visible. No empty-state render needed.

### States summary for DocReader

| State | What renders |
|---|---|
| `isOpen === false` | `width: 0`, center column fills |
| `isOpen === true, node === null` | panel open but no node — should not occur (always set node before isOpen) |
| `node.type === 'dir'` | No doc fetch; render header + dir symbol count + "Directory" label; no stale warning; no key symbols (dirs have no symbols array) |
| `loading === true` | "Loading documentation..." |
| `error !== null` | "Could not load this file's doc." + Retry button |
| `!hasDoc` | "No documentation generated yet." message |
| `isStale === true` | Stale warning box, badge in header row 4 |
| `backlinks.length === 0` | Backlinks section omitted entirely |
| `outgoingDeps.length === 0` | Dependencies section omitted entirely |

---

## 10. useMeta.js — New Hook

**File:** `frontend/src/hooks/useMeta.js`

```js
import { useState, useEffect } from 'react'

/**
 * Fetch GET /meta once on mount.
 * Returns { repoRoot: string | null }
 * repoRoot is null until fetched or if fetch fails.
 */
export function useMeta() {
  const [repoRoot, setRepoRoot] = useState(null)

  useEffect(() => {
    fetch('/meta')
      .then(res => {
        if (!res.ok) throw new Error('meta fetch failed')
        return res.json()
      })
      .then(data => {
        setRepoRoot(data.repo_root ?? null)
      })
      .catch(() => {
        // Silently fail — repoRoot stays null; "Open in Editor" button becomes disabled
      })
  }, [])

  return { repoRoot }
}
```

**Usage in App.jsx:**
```js
import { useMeta } from './hooks/useMeta.js'
// ...
const { repoRoot } = useMeta()
// Pass repoRoot down to DocReader
```

---

## 11. server.py — New /meta Route

Add this route to `corpus/server.py` **between the `/doc` route and the `/event` route** (i.e., after line 85, before line 88):

```python
@app.get("/meta")
async def get_meta() -> Response:
    """Return absolute repo root path for the 'Open in Editor' deep link."""
    repo_root = str(_corpus_dir().parent.resolve())
    return JSONResponse(content={"repo_root": repo_root})
```

`_corpus_dir()` returns `Path.cwd() / ".corpus"`. So `_corpus_dir().parent.resolve()` returns the resolved absolute path of the directory from which `corpus serve` was launched — the repo root. This is the correct value for constructing `vscode://file/{repo_root}/{node.path}`.

**CORS note:** The existing server has no CORS configuration. `GET /meta` from `localhost:7077` to the same origin is same-origin, so no CORS headers are needed.

---

## 12. States — Every Screen, Every Case

### Top nav search input

The search input in Phase 7 is a UI element but has no wired behavior in this phase — it does not filter the graph (importance filter is removed; search is parked for a later phase). Placeholder text: `"Search nodes..."`. It should accept focus and keyboard input without error. It does not mutate any state.

**Exception:** If builder finds a natural way to wire it to the File Tree filter with < 10 lines of code, they may do so. Document the decision. Do not block on it.

### File Tree states

| State | What renders |
|---|---|
| `nodes` is null or loading | FileTree not rendered; left column shows loading shimmer or nothing |
| `nodes.length === 0` | "No files tracked." empty state |
| `fileTreeVisible === false` | Column `width: 0`, content hidden via `overflow: hidden` |
| Normal | Scrollable tree |
| Node selected | That file row has sienna left border + accent color text |
| Dir collapsed (default) | Children hidden; chevron points right |
| Dir expanded | Children visible; chevron points down |
| Stale node | Amber 8px dot on right side of row |

### Explorer tab states

| State | What renders |
|---|---|
| `graphData.nodes.length === 0` | Empty graph canvas; no overlay needed |
| All nodes collapsed | All file nodes hidden; only root dirs visible |
| Node selected | Sienna ring drawn by `nodeCanvasObject` |
| Pulsing node | Teal fill + glow (from WS event) |
| Stale node | Amber fill + soft glow |

### Architecture tab states

| State | What renders |
|---|---|
| No dir-to-dir edges exist (single dir repo) | All dir nodes visible, no edges |
| No dir nodes | Empty canvas with no error (graphData will be `{ nodes: [], links: [] }`) |
| Dir node selected | Opens DocReader with `_dir.md` doc |

### Dependencies tab states

| State | What renders |
|---|---|
| No file selected | Centered italic prompt |
| Dir node selected | Centered italic prompt (deps only for files) |
| File selected, no edges | Just the center node alone |
| File selected, has edges | Subgraph with center + neighbors |

### Symbols tab states

| State | What renders |
|---|---|
| No nodes loaded | Empty table, no search input shimmer |
| No symbols in any node | "No symbols indexed yet" empty state |
| Query returns no results | "No symbols match '{query}'." row |
| > 500 symbols | Warning banner + first 500 rows |

### Overview tab states

| State | What renders |
|---|---|
| Loading root dir doc | "Loading project summary..." |
| Root dir doc fetch fails | "No project doc found." |
| No stale files | "All files are up to date." |
| Most Important: all nodes have `importance === null` | Section renders with 0 items; show "—" or omit |

### DocReader states

See Section 9 states table above.

### Loading / Error / Empty (full screen, before layout)

| State | What renders |
|---|---|
| `loading === true` | Full screen linen bg, "Loading..." in EB Garamond |
| `error !== null` | Full screen linen bg, error message + Retry button |
| `nodes.length === 0` | Full screen, "No files tracked yet." message |

---

## 13. Accessibility Floor

- **Contrast:** `#c2652a` on `#faf5ee` = 3.8:1 — below 4.5:1 for body text. **Do not use accent color for body text.** Use `#3a302a` (`--color-text-primary`) for all body copy. Accent is allowed for large text (>18px), UI controls, and decorative elements only.
- **Tab nav links:** Must be `<button>` elements (not `<a>` without href) for keyboard accessibility. `role="tab"`, `aria-selected={activeTab === tab}`.
- **File Tree rows:** `role="treeitem"`, `aria-expanded` on dir rows. Keyboard: `Enter`/`Space` to expand/select. Arrow keys for tree navigation are a MAJOR enhancement but not required in Phase 7 — accept click-only with keyboard-focusable elements.
- **Doc Reader close button:** `aria-label="Close doc reader"`. Escape key closes panel (already specified).
- **All inputs labeled:** Search input gets `aria-label="Search nodes"`. Symbols tab search input gets `aria-label="Filter symbols"`.
- **Focus visible:** Do not suppress `outline` without replacement. Use `outline: '2px solid var(--color-accent)'` as the universal focus ring.
- **Touch targets:** Nav tab buttons minimum 44px tall (64px header provides this). File Tree rows minimum 36px. Acceptable for a developer tool.
- **Images/icons:** Material Symbols icons inside interactive elements must have their parent button carry `aria-label`. The icon span itself carries `aria-hidden="true"` (or is decorative).

---

## 14. Copy — Exact Words

### Navigation tabs
"Explorer" | "Architecture" | "Dependencies" | "Symbols" | "Overview"

### File Tree header
No visible heading. The left border and bg distinguish it.

### Empty states

| Location | Copy |
|---|---|
| File Tree empty | "No files tracked." |
| Dependencies tab, no selection | "Select a file to explore its dependency graph." |
| Symbols tab, no symbols | "No symbols indexed yet. Run corpus update to index symbols." |
| Symbols tab, no search results | `No symbols match "{query}".` |
| Overview > stale = none | "All files are up to date." |
| Overview > root doc fetch failed | "No project doc found." |
| App loading | "Loading..." |
| App error | "Could not connect to Corpus. Is corpus serve running on localhost:7077?" |
| App empty | "No files tracked yet. Run corpus init, then corpus update." |

### DocReader

| Element | Copy |
|---|---|
| Type badge | "Python Module" / "JavaScript Module" / "TypeScript Module" / "Markdown" / "Directory" / "File" |
| Stale status line | "Documentation may be outdated" (when stale) / "Documentation up to date" (when fresh) |
| Stale warning heading | "Documentation Stale" |
| Stale warning body | "Source code has changed significantly since this documentation was generated. Review recommended." |
| No doc | "No documentation generated yet. Run corpus update to generate docs." |
| Doc loading | "Loading documentation..." |
| Doc error | "Could not load this file's doc." |
| Doc error retry button | "Retry" |
| Sections | "Key Symbols" / "Dependencies" / "Imported by" |
| Open in editor button | "Open in Editor" |
| Open in editor, disabled tooltip | "repoRoot not available — start corpus serve to enable this" |

### Error/retry buttons
"Retry" (not "Try again", not "Reload").

---

## 15. Interaction Spec

### Keyboard path (full)

1. Tab → focuses header "Corpus" wordmark (non-interactive, skip) → first tab button ("Explorer")
2. Tab → cycles through 5 tab buttons
3. Enter/Space on tab button → switches center content
4. Tab → search input → accepts text input
5. Tab → Refresh button → Settings button → File Tree toggle button
6. Tab → first File Tree row → Down arrow or Tab to next row
7. Enter/Space on dir row → expand/collapse
8. Enter/Space on file row → select + open DocReader
9. Escape → close DocReader (always active when `panelOpen === true`)
10. Tab into DocReader → first focusable = edit button → close button → doc links → backlink chips → "Open in Editor" button

### Click feedback

- Tab button click → center changes within one render frame (<16ms) — no loading state needed
- File Tree row click → DocReader slides in (220ms CSS transition); graph selection ring appears on next canvas draw
- Node click in graph → same as above
- Backlink chip click → DocReader content swaps (200ms for doc fetch if fast; show loading text if >200ms)
- "Open in Editor" click → browser opens `vscode://` protocol; no in-app feedback needed

### Hover states

| Element | Hover |
|---|---|
| Tab nav link | `color: var(--color-accent)`, `background: var(--color-surface-low)` |
| File Tree row | `background: var(--color-surface-container)` (dir) or `background: var(--color-surface-low)` (file) |
| Overview row | `border-color: var(--color-accent)` |
| Symbol table row | `background: var(--color-surface-low)` |
| Backlink chip | `border-color: var(--color-accent)`, `color: var(--color-accent)` |
| Graph node | cursor: pointer; handled by react-force-graph internally |

---

## 16. Files Changed / Created / Deleted

### New files
| Path | Purpose |
|---|---|
| `frontend/src/components/FileTree.jsx` | Collapsible directory/file tree |
| `frontend/src/components/DocReader.jsx` | Replaces DocPanel.jsx |
| `frontend/src/components/tabs/ExplorerTab.jsx` | Thin wrapper + zoom controls |
| `frontend/src/components/tabs/ArchitectureTab.jsx` | Dir-only filtered graph |
| `frontend/src/components/tabs/DependenciesTab.jsx` | 1-hop subgraph around selected file |
| `frontend/src/components/tabs/SymbolsTab.jsx` | Searchable flat symbol table |
| `frontend/src/components/tabs/OverviewTab.jsx` | Stats + about + ranked lists |
| `frontend/src/hooks/useMeta.js` | Single GET /meta fetch |

### Modified files
| Path | Change |
|---|---|
| `frontend/src/styles/tokens.css` | Complete replacement with Sahara palette |
| `frontend/index.html` | Add Google Fonts + Material Symbols link tags |
| `frontend/src/App.jsx` | Three-column layout; 5-tab nav; remove CommandPalette, Minimap, ImportanceFilter; add useMeta, FileTree, DocReader, tab components; seed collapsedMap for root dirs |
| `frontend/src/components/GraphCanvas.jsx` | Sahara color constants; warm grid bg; file node border stroke; Manrope labels; dir radius 18 |
| `corpus/server.py` | Add GET /meta route after /doc route |

### Removed from render tree (files may remain on disk)
| File | Reason |
|---|---|
| `frontend/src/components/CommandPalette.jsx` | Replaced by top-nav search + tabs |
| `frontend/src/components/Minimap.jsx` | Parked |
| `frontend/src/components/ImportanceFilter.jsx` | No importance filter in Phase 7 |
| `frontend/src/components/DocPanel.jsx` | Replaced by DocReader.jsx |

If builder creates `DocReader.jsx` as a new file, delete `DocPanel.jsx` or confirm it is not imported anywhere. Do not leave both files exporting different components with the same purpose.

---

## 17. What Must Not Change

The following files and their exports must not be modified at all:

- `frontend/src/hooks/useGraph.js` — all data fetching, WS reconnect, stale polling
- `frontend/src/hooks/useDoc.js` — doc fetching with retry
- `frontend/src/utils/path.js` — `lastName`, `splitSegments`
- All Python files except `corpus/server.py` (which gets one new route only)
- `.corpus/` directory structure

The live-wire behavior (MCP tool call → WS event → teal pulse on node) must remain unbroken. The `pulseMap` → `isPulsing()` → `COLOR_NODE_PULSE` (#14b8a6) draw path in GraphCanvas is the mechanism. Verify it end-to-end after implementing.
