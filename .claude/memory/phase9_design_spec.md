# Design Spec — Phase 9: Graph UX overhaul (Overview/All-Files modes, label decluttering, layout physics)

> Written by `designer`. Grounds every decision in the actual current code: `App.jsx`, `GraphCanvas.jsx`, `ExplorerTab.jsx`, `FileTree.jsx`. Resolves all 10 open questions from PLAN.md's Phase 9 section. This is the build spec — `builder` should not need to make any further judgment calls on the items below.

---

## 0. The one job

The Explorer tab must answer "what does this codebase look like, at a glance" for a repo the user has never seen the graph of before — on day one, with zero LLM importance data, on a real 40-node repo, without amateur-hour overlap. Every decision below serves that: fewer things on screen by default, real physics so what IS on screen doesn't visually collide, and an explicit, honest escape hatch for "no, show me literally everything."

---

## 1. Resolved answers to the 10 open questions

### Q1 — Overview curation, importance present
Top-`CAP` file nodes by `importance` descending (ties broken by degree, then by `id` for determinism), **plus** a bounded 1-hop dependency-neighbor expansion. See §3 for the exact algorithm — neighbors ARE pulled in as real nodes (not just decorative edges), because a "dependency graph" showing isolated important dots with no visible connections defeats the point of a graph. Expansion is hard-capped at `1.5×CAP` so one hub file can't balloon the view back to "everything."

### Q2 — Overview curation, importance absent (today's actual state, no API key)
Degree-based fallback: same `CAP`/expansion algorithm, ranking file nodes by `in-degree + out-degree` instead of `importance`. This is not a lesser-effort fallback — it's the same code path with a different scoring function, so behavior is predictable and testable either way. See §3 for the exact `hasImportance` decision rule (it's not a strict binary "all-null vs. all-present" check — it tolerates partial doc generation).

### Q3 — Does the cap scale with repo size?
Scales, within bounds: `CAP = clamp(round(0.4 × totalFileNodes), 8, 40)`. Rationale: a fixed absolute number is wrong at both ends — 10 nodes is too many for a genuinely tiny 12-file repo (defeats "curated") and laughably small context for a 2,000-file monorepo (defeats "dependency view"). Percentage-of-total with a floor and ceiling gives a sane view at both extremes without unbounded growth.

### Q4 — Mode-switch control
A two-segment pill control, **inside the Explorer tab only** (not the top nav — Explorer-scoped per binding requirement and non-goals), positioned top-left of the canvas at `top:16px; left:16px`, visually matching the existing bottom-left `ZoomControls`/`StatsBar` chip language already in `ExplorerTab.jsx`. Exact spec in §4.

### Q5 — Label-collision algorithm
Real grid/pairwise displacement pass, executed once per frame in a new `onRenderFramePost` callback (not inside per-node `nodeCanvasObject`), with vertical nudge-apart up to a max offset, a leader line past a displacement threshold, and outright hiding of the lowest-priority label if it still can't fit. Full algorithm in §5.

### Q6 — New label zoom threshold
Fixed constant: **`0.6`** (up from `0.15`). Not dynamic/density-based — see §5 for rationale (the real fix is collision-avoidance, not a smarter threshold; a fixed constant is simpler to reason about and test). A per-node hover tooltip (always available regardless of zoom) is the safety valve so users are never fully blind to a node's identity below threshold.

### Q7 — Hierarchy layout scope
Applies in **both modes**, gated by a node-count threshold: only seeds initial hierarchy positions when the currently-rendered node count (whatever `graphData.nodes.length` GraphCanvas actually receives) is **> 60**. Below that, plain force-from-random-start is fine — it settles fast and a hierarchy skeleton on a small set looks artificially rigid. This means the specific 40-node repo that surfaced this bug is fixed by the physics retune alone (proving that part works standalone), while hierarchy is the scaffolding for hundreds-of-nodes repos later.

### Q8 — Pulse targeting a curated-out node
**Reveal temporarily, don't auto-switch modes.** When a `query` event names a node that isn't in Overview's current curated set: add it to a short-lived `pinnedNodeIds` set (lives exactly as long as `pulseMap` holds that node, i.e. the existing 2s pulse window, no extra grace period needed since disappearing when the pulse ends reads as "it was here for the query, now it's gone" rather than a UI glitch) and, if it's nested under a dir the Overview drill-state hasn't expanded, force that one ancestor chain open for the same window. Simultaneously show a small inline banner next to the mode-switch control: `"Showing {filename} — outside Overview's curated view"` with a text link `"Show in All Files"`. Auto-switching modes on every MCP call would be disorienting (the view would jump every time Claude Code does a lookup); a temporary reveal + an explicit opt-in link respects the user's chosen mode while still answering "where is this."

### Q9 — Directory badge legibility fix
Split the single centered glyph-cluster into two distinct, separated elements: the `▶` arrow stays large and centered in the dir circle (pure affordance: "closed, click to open"); the child count moves to a small separate badge circle at the node's lower-right corner, with its own background/border so it reads as a UI chrome element, not part of the node fill. Full spec in §6. Adds a hover tooltip ("N files inside") as a second, redundant legibility channel.

### Q10 — Overview mode's collapse/expand state
**Independent from All-Files' `collapsedMap`.** Overview mode manages its own `overviewCollapsedMap` (same `Map<nodeId, boolean>` shape, reusing GraphCanvas's existing collapsed-badge rendering logic unchanged) and its own recursive curation-on-drill-in. Rationale: All-Files' collapse state is a manual, user-driven, persistent-within-session model (matches FileTree's sidebar, which is explicitly untouched by this phase). Overview's collapse state is algorithmic and mode-scoped — conflating the two would mean expanding a folder in the sidebar unexpectedly changes what Overview shows, or vice versa, which breaks the "two clearly distinct modes" premise the whole phase rests on.

---

## 2. Architecture — how this fits the existing code (no invented framework)

Current data flow: `App.jsx` computes one `graphData` (nodes/links already filtered by the shared `collapsedMap`) and passes the same object to `ExplorerTab`, `ArchitectureTab`, `DependenciesTab`. That's exactly right for "All Files" mode (it just *is* today's existing behavior, renamed) — it must stay unchanged for those other two tabs.

Only change to `App.jsx`: **pass the raw `nodes` and `edges` arrays through to `ExplorerTab`** (both already exist in `App`'s scope — `nodes`/`edges` are already destructured from `useGraph()`), in addition to the existing `graphData` prop. Nothing else about `App.jsx` changes — no new state lifted, no toggle rendered there.

```
<ExplorerTab
  graphData={graphData}      // unchanged — used when explorerMode === 'all'
  nodes={nodes}               // NEW — raw, full node list, for Overview curation
  edges={edges}                // NEW — raw, full edge list, for Overview curation
  staleMap={staleMap}
  collapsedMap={collapsedMap}  // unchanged — used when explorerMode === 'all'
  ...
/>
```

`ExplorerTab.jsx` owns everything new:
- `const [explorerMode, setExplorerMode] = useState('overview')` — local state. Because `App.jsx` conditionally renders `{activeTab === 'explorer' && <ExplorerTab .../>}`, this component unmounts on tab switch and remounts fresh — which is exactly the "resets on every fresh load **or tab switch**" non-goal, for free, no extra reset code needed.
- `const [overviewCollapsedMap, setOverviewCollapsedMap] = useState(new Map())` — Overview's own drill-in state (Q10).
- Computes `curatedGraphData` via `graphCuration.js` (memoized on `nodes`, `edges`, `overviewCollapsedMap`) when `explorerMode === 'overview'`; otherwise passes through the existing `graphData` prop unchanged for `'all'` mode.
- Computes its own `overviewChildCounts` via the existing `buildChildCounts`-shaped helper (same logic as `App.jsx`'s, called against the full `nodes` list + `overviewCollapsedMap` — copy the 12-line pure function or export it from `App.jsx`/a shared `lib/` file; either is fine, builder's call, not a design decision).
- Feeds `GraphCanvas` the right `graphData` / `collapsedMap` / `childCounts` triple depending on `explorerMode`.

`GraphCanvas.jsx` itself does not know about "modes" at all — it only ever receives one `graphData`/`collapsedMap`/`childCounts` triple, same as today. This keeps the physics/label work (which Architecture and Dependencies tabs also benefit from) fully decoupled from the Overview/All-Files concept, exactly per the plan's scope note.

---

## 3. Curation algorithm — `frontend/src/lib/graphCuration.js`

```js
// hasImportance decision (computed once by ExplorerTab, not inside this module,
// so the module stays a pure function of its inputs):
//
//   const fileNodes = nodes.filter(n => n.type === 'file')
//   const withScore = fileNodes.filter(n => n.importance != null).length
//   const hasImportance = withScore >= Math.max(3, Math.round(fileNodes.length * 0.5))
//
// i.e. "importance present" means AT LEAST HALF the file nodes (floor of 3) have a
// non-null score. This tolerates partial doc generation (some files stale/skipped)
// instead of requiring literally every node to have a score. Below that bar, treat
// importance as absent project-wide and use degree for everyone — a 50/50 mixed
// state ranked by "importance-or-zero" would silently bury real degree-based signal
// under a coin flip of which files happen to have docs yet.

export function idOf(endpoint) {
  return typeof endpoint === 'object' ? endpoint.id : endpoint
}

function computeDegree(fileNodeIds, edges) {
  const degree = new Map()
  for (const id of fileNodeIds) degree.set(id, 0)
  for (const e of edges) {
    const s = idOf(e.source), t = idOf(e.target)
    if (degree.has(s)) degree.set(s, degree.get(s) + 1)
    if (degree.has(t)) degree.set(t, degree.get(t) + 1)
  }
  return degree
}

// scopeFileIds: optional — restrict scoring/expansion to a subset (used for
// recursive drill-in curation within a single directory, §7). Pass null/undefined
// for the top-level Overview computation (scope = all file nodes).
export function curateFiles(fileNodes, edges, { hasImportance, scopeFileIds } = {}) {
  const pool = scopeFileIds ? fileNodes.filter(n => scopeFileIds.has(n.id)) : fileNodes
  const total = pool.length
  if (total === 0) return { curatedIds: new Set(), edges: [] }

  const CAP = Math.min(40, Math.max(8, Math.round(total * 0.4)))
  const poolIds = pool.map(n => n.id)
  const degree = computeDegree(poolIds, edges)

  const scored = pool.map(n => ({
    id: n.id,
    score: hasImportance ? (n.importance ?? 0) : (degree.get(n.id) ?? 0),
    degree: degree.get(n.id) ?? 0,
  }))
  scored.sort((a, b) => b.score - a.score || b.degree - a.degree || a.id.localeCompare(b.id))

  const core = new Set(scored.slice(0, CAP).map(s => s.id))

  const expansionCap = Math.round(CAP * 1.5)
  const curatedIds = new Set(core)
  for (const e of edges) {
    if (curatedIds.size >= expansionCap) break
    const s = idOf(e.source), t = idOf(e.target)
    if (core.has(s) && poolIds.includes(t) && !curatedIds.has(t)) curatedIds.add(t)
    if (curatedIds.size >= expansionCap) break
    if (core.has(t) && poolIds.includes(s) && !curatedIds.has(s)) curatedIds.add(s)
  }

  const curatedEdges = edges.filter(e =>
    curatedIds.has(idOf(e.source)) && curatedIds.has(idOf(e.target))
  )

  return { curatedIds, edges: curatedEdges }
}

// Top-level Overview computation: top-level dirs (always shown, collapsed) + curated files.
export function curateOverview(nodes, edges, { hasImportance }) {
  const fileNodes = nodes.filter(n => n.type === 'file')
  const dirNodes = nodes.filter(n => n.type === 'dir')
  const topDirs = dirNodes.filter(d => !d.path.includes('/'))  // depth-0 dirs only

  const { curatedIds, edges: curatedEdges } = curateFiles(fileNodes, edges, { hasImportance })

  const nodeIds = new Set([...topDirs.map(d => d.id), ...curatedIds])
  return { nodeIds, curatedFileIds: curatedIds, edges: curatedEdges }
}
```

`ExplorerTab` builds the actual `graphData` object passed to `GraphCanvas` from this output: `nodes.filter(n => nodeIds.has(n.id))` for the node list, `curatedEdges` (converted to `{source, target}` link shape, same as `App.jsx` already does) for links.

---

## 4. Mode-switch control — exact spec

**Component:** new small function inside `ExplorerTab.jsx` (no new file needed — it's ~20 lines, same weight as the existing `ZoomControls`/`StatsBar` helpers already in that file).

**Placement:** `position: absolute; top: 16px; left: 16px; z-index: 10` — mirrors the existing bottom-left chip positioning, opposite corner so it never collides with `ZoomControls` (bottom-left) or `StatsBar` (bottom-left, stacked above zoom controls).

**Visual:**
```
┌──────────────────┐
│ Overview │ All Files │      <- single pill container
└──────────────────┘
```
- Container: `background: rgba(22,27,34,0.92)`, `border: 1px solid var(--color-border)`, `borderRadius: 6px`, `display: flex`, `overflow: hidden` — identical container treatment to `ZoomControls`.
- Each segment: `padding: 6px 14px`, `fontFamily: var(--font-body)`, `fontSize: 12px`, `fontWeight: 600`, `border: none`, `cursor: pointer`, `aria-pressed={explorerMode === 'overview'|'all'}`.
- **Active segment:** `background: var(--color-accent-dim)`, `color: var(--color-accent)`.
- **Inactive segment:** `background: transparent`, `color: var(--color-text-secondary)`; hover: `color: var(--color-accent)`.
- Divider between segments: `1px solid var(--color-border)` (border-left on the second button only).
- Click behavior: sets `explorerMode`, then calls `fgRef.current?.zoomToFit(400, 60)` after the next tick (per binding requirement — mode switch re-triggers zoom-to-fit).

**Node-count context chip:** immediately to the right of the segmented control (same row, `gap: 8px`), a small non-interactive text chip, same background/border treatment, shown only in Overview mode:
`"12 of 40 shown · by connections"` (or `"· by importance"` when `hasImportance` is true). This directly satisfies the AC that the reduced count must be visible, and answers "why fewer nodes" without a separate legend.

**Pulse-reveal banner (Q8):** when `pinnedNodeIds` is non-empty in Overview mode, render one more inline chip to the right of the count chip: `Showing {lastName(node.path)} — outside curated view` in `var(--color-node-pulse)` text, with a trailing text link `Show in All Files` (`color: var(--color-accent)`, `textDecoration: underline`, `cursor: pointer`) that calls `setExplorerMode('all')`. Disappears automatically when the pulse (and thus `pinnedNodeIds`) expires.

---

## 5. Label-collision algorithm — exact spec

**Where it lives:** remove step 5 (label drawing) entirely from `nodeCanvasObject` in `GraphCanvas.jsx`. Add a new `onRenderFramePost={handleRenderFramePost}` prop to `ForceGraph2D` (this callback fires once per frame, after all per-node draws, with the same `(ctx, globalScale)` signature — it's the correct place to do a pass that needs to see all nodes at once, which per-node `nodeCanvasObject` structurally cannot).

**Algorithm** (runs every frame the graph is visible — cheap because it's gated by node count, see below):

```js
function handleRenderFramePost(ctx, globalScale) {
  if (globalScale < LABEL_MIN_ZOOM) return         // §6: LABEL_MIN_ZOOM = 0.6

  const nodes = graphDataRef.current.nodes
  if (nodes.length > 150) return                    // perf guard — skip collision pass
                                                       // above 150 visible nodes; labels
                                                       // simply don't render at all rather
                                                       // than pay O(n^2) every frame. Overview
                                                       // mode is always well under this
                                                       // (cap ≤ 60); only huge All-Files
                                                       // graphs hit this ceiling.

  // 1. Build ideal label boxes for nodes with valid positions.
  const boxes = []
  for (const node of nodes) {
    if (node.x == null || node.y == null) continue
    const r = nodeRadius(node)
    const label = lastName(node.path)
    ctx.font = FONT_LABEL
    const w = ctx.measureText(label).width
    const h = 14
    boxes.push({
      node, label, r,
      idealX: node.x, idealY: node.y + r + 6,
      x: node.x, y: node.y + r + 6,           // current (mutated below)
      w, h,
      priority: node.type === 'dir' ? Infinity : (node.importance ?? 0) * 10 + (node.__degree ?? 0),
      hidden: false,
    })
  }

  // 2. Sort by priority descending — higher-priority labels get first claim on their
  //    ideal position; lower-priority ones get pushed/hidden when they'd overlap.
  boxes.sort((a, b) => b.priority - a.priority)

  // 3. Pairwise AABB collision check against all higher-priority boxes already placed.
  //    Grid-bucket by 40px cells for cheap neighbor lookup instead of full O(n^2) —
  //    at ≤150 nodes this is a minor optimization, not a correctness requirement, but
  //    keep it simple: a flat array scan is fine at this scale (≤150 → ≤11,175 pairs
  //    worst case, once per frame, well within a 16ms budget). No bucket needed in
  //    practice; note only if profiling later shows otherwise.
  const placed = []
  for (const box of boxes) {
    let attempt = 0
    const maxAttempts = 4        // 0 = ideal position, 1..3 = push down in 10px steps
    while (attempt <= maxAttempts) {
      const candidateY = box.idealY + attempt * 10
      const overlaps = placed.some(p =>
        Math.abs(box.idealX - p.x) < (box.w + p.w) / 2 + 4 &&
        Math.abs(candidateY - p.y) < (box.h + p.h) / 2 + 2
      )
      if (!overlaps) { box.y = candidateY; break }
      attempt++
    }
    if (attempt > maxAttempts) { box.hidden = true; continue }   // couldn't fit — drop it
    box.displaced = box.y !== box.idealY
    placed.push(box)
  }

  // 4. Draw: leader line first (if displaced beyond one line-height), then label text.
  for (const box of placed) {
    if (box.hidden) continue
    if (box.displaced && (box.y - box.idealY) > 10) {
      ctx.beginPath()
      ctx.moveTo(box.node.x, box.node.y + box.r + 2)
      ctx.lineTo(box.x, box.y - 2)
      ctx.strokeStyle = 'var(--color-text-muted)'   // resolved to a literal hex by builder,
                                                       // same as every other GraphCanvas color
      ctx.lineWidth = 1 / globalScale
      ctx.stroke()
    }
    ctx.font = FONT_LABEL
    ctx.fillStyle = COLOR_LABEL
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillText(box.label, box.x, box.y)
  }
}
```

**Leader line style:** 1px solid (no dash), color `--color-text-muted` (`#6e7681` per current GH-dark tokens), drawn from the node's bottom edge to the label's actual anchor point. Only drawn when displacement exceeds 10px (one nudge step) — a label pushed down exactly one step (10px, still visually "attached") doesn't need a line; two-or-more steps away does.

**Hover safety valve (independent of the above):** add `onNodeHover` to `ForceGraph2D`. On hover, regardless of `globalScale` or whether the label is currently hidden/decluttered, render a small floating tooltip (plain positioned `<div>` over the canvas, not canvas-drawn text) showing the full `lastName(node.path)` plus, for dir nodes, the child count (`"N files inside"` — same copy as the badge tooltip in §6, since it's the same underlying information surfaced two ways).

---

## 6. Directory badge redesign — exact spec

**Problem today:** `▶` and the count digit are both centered in the same spot inside the dir circle, in the same white color, at nearly the same font size — reads as noise, not "N files."

**Fix:**
- **Arrow** (`▶`): stays exactly where it is today — centered in the dir circle, `FONT_DIR_BADGE` (`bold 8px ...`), color `COLOR_DIR_BADGE_TEXT` (`#ffffff`) against the sienna/blue fill. This alone is the "closed folder, click to open" affordance and needs no further change.
- **Count badge**: moves OUT of the main circle into its own small satellite circle, positioned at `(node.x + r * 0.72, node.y + r * 0.72)` (lower-right, standard "notification badge" position), independent fill:
  - Radius: `7px` (fixed, not scaled by `r` — stays legible at the node's own scale-invariant minimum size).
  - Fill: `var(--color-surface-container)` / actual resolved hex from current tokens (`#21262d` today).
  - Border: `1px solid var(--color-border)` (`#30363d`).
  - Text: the count number only (no arrow), `color: var(--color-text-primary)` (`#e6edf3` — NOT white-on-white, fixes the actual contrast complaint), `font: bold 8px` same family as `FONT_DIR_COUNT`.
  - Only rendered when `count > 0` (same guard as today) and `isCollapsed` (same guard as today).
- **Hover tooltip:** wired through the same `onNodeHover` handler as §5 — hovering a collapsed dir node (whether or not the badge is visually present) shows `"{count} files inside"` in a floating div tooltip. This is the redundant, unambiguous channel: even a user who still doesn't parse the tiny badge glyph gets the plain-English count on hover.
- Nothing else about dir-node rendering changes (fill color, radius, selection ring, pulse ring all untouched).

---

## 7. Recursive drill-in curation (Overview mode dir expansion)

When a user clicks a top-level dir node while `explorerMode === 'overview'`:
1. `setOverviewCollapsedMap` flips that dir's entry to `false` (exactly the same toggle shape as `App.jsx`'s existing `handleNodeClick` dir-branch — copy that one-line pattern, not new logic).
2. `ExplorerTab` recomputes the visible set for the next render: the now-expanded dir's **direct children** (one level — sub-dirs and files whose path has that dir as immediate parent, same computation as `App.jsx`'s `buildDirectChildren`) are added to candidates. Sub-dirs among them are added to the node set as new collapsed dir nodes (badge = their own full descendant count, via the same `buildChildCounts`-style helper). Files among them go through `curateFiles(fileNodes, edges, { hasImportance, scopeFileIds: <that dir's direct file children> })` — i.e., a fresh, smaller-scope curation pass, not "show all children" (a huge subdirectory shouldn't dump hundreds of files just because its parent was expanded).
3. The now-visible dir node itself keeps rendering (no badge, since `isCollapsed` is now `false` for it) — exactly matching today's existing App-level behavior for expanded dirs, reusing `GraphCanvas`'s current `isDir && isCollapsed` badge guard unchanged.
4. Clicking the same dir node again collapses it back (`overviewCollapsedMap` entry flips to `true`), which naturally drops its children from the computed node set on next render (same filter logic as `buildVisibleIds`, scoped to Overview's own map).

This means Overview drill-in behaves identically, level by level, to All-Files' existing expand affordance — the only difference is each level shows a curated subset of files instead of literally all of them, and the state backing it is a separate map.

---

## 8. Copy reference (exact strings)

| Location | Copy |
|---|---|
| Mode toggle segments | `Overview` / `All Files` |
| Overview count chip (importance present) | `{N} of {total} shown · by importance` |
| Overview count chip (degree fallback) | `{N} of {total} shown · by connections` |
| Pulse-reveal banner | `Showing {filename} — outside curated view` |
| Pulse-reveal link | `Show in All Files` |
| Dir badge hover tooltip | `{count} files inside` |
| File node hover tooltip (below label threshold) | `{filename}` |

No lorem ipsum, no "Toggle View" or "Filter Options" hand-waving — every string above is what actually renders.

---

## 9. What does NOT change

- `GraphCanvas.jsx`'s node fill/stroke/selection-ring/pulse-ring drawing (steps 1–3 of `nodeCanvasObject`) — untouched.
- `FileTree.jsx`, `DocReader.jsx`, `useGraph.js`, `useDoc.js`, `useMeta.js` — untouched, per plan.
- Architecture/Dependencies/Symbols/Overview(dashboard)Tab — untouched; they keep consuming the same App-level `graphData` they do today. They inherit the physics retune and label-collision pass automatically because those live in the shared `GraphCanvas.jsx`, which is the intended, explicitly-scoped bonus.
- No new toast/notification system — the pulse-reveal banner in §4 is a plain inline chip in the existing control row, not a new global component.

---

## 10. Accessibility floor

- Mode-toggle buttons: real `<button>` elements, `aria-pressed`, visible focus ring (`outline: 2px solid var(--color-accent); outline-offset: 2px` on `:focus-visible`), 44×32px minimum hit area (segment padding already yields ~32px height — bump vertical padding to `8px 14px` if measured height comes in under 32px in practice).
- Hover tooltips (§5, §6) are a supplementary channel, not the only way to get the information — the count chip and inline banner text already convey the same info without requiring hover, so nothing here is hover-only-accessible.
- Color is never the sole signal: stale = amber fill AND glow AND (unchanged) badge elsewhere in DocReader; pulse = distinct teal/green fill AND ring AND banner text, not fill alone.
