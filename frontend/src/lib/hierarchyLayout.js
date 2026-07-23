// Phase 9 — d3-hierarchy-seeded initial placement.
//
// Pure function(s) only: no React, no canvas. Builds a folder-keyed tree from
// the flat node list (dirs and files positioned by path structure), computes
// a tree layout via d3-hierarchy, and returns initial x/y coordinates. These
// are seeded onto the force-graph's node objects *before* the force
// simulation runs so large graphs start from a structurally sane skeleton
// instead of random jitter, with d3-force layered on top for local
// separation/jitter.
//
// Gated by node count (see HIERARCHY_NODE_THRESHOLD) — small graphs settle
// fast from a random start and a rigid tree skeleton looks artificial there.

import { hierarchy, tree } from 'd3-hierarchy'

export const HIERARCHY_NODE_THRESHOLD = 60

// Builds a synthetic root -> dir -> dir -> file tree keyed by node.path,
// mirroring the folder structure. Directory nodes are the internal tree
// nodes; file nodes are leaves. Nodes with no matching directory ancestor
// (e.g. depth-0 files) attach directly under the synthetic root.
function buildPathTree(nodes) {
  const dirEntries = new Map()   // path -> entry
  const root = { path: '', id: null, childEntries: new Map() }
  dirEntries.set('', root)

  function ensureDir(path) {
    if (dirEntries.has(path)) return dirEntries.get(path)
    const lastSlash = path.lastIndexOf('/')
    const parentPath = lastSlash === -1 ? '' : path.slice(0, lastSlash)
    const parent = ensureDir(parentPath)
    const entry = { path, id: null, childEntries: new Map() }
    parent.childEntries.set(path, entry)
    dirEntries.set(path, entry)
    return entry
  }

  for (const n of nodes) {
    if (n.type !== 'dir') continue
    const entry = ensureDir(n.path)
    entry.id = n.id
  }
  for (const n of nodes) {
    if (n.type !== 'file') continue
    const lastSlash = n.path.lastIndexOf('/')
    const parentPath = lastSlash === -1 ? '' : n.path.slice(0, lastSlash)
    const parent = ensureDir(parentPath)
    const leafKey = `file:${n.id}`
    parent.childEntries.set(leafKey, { path: leafKey, id: n.id, childEntries: new Map() })
  }

  function toPlain(entry) {
    const children = [...entry.childEntries.values()].map(toPlain)
    return { id: entry.id, children: children.length ? children : undefined }
  }

  return toPlain(root)
}

/**
 * Computes initial tree-layout coordinates for every node, keyed by node id.
 * Returns Map<nodeId, {x, y}>. Pure — does not mutate `nodes`.
 */
export function computeHierarchyPositions(nodes, { width = 800, height = 600 } = {}) {
  const positions = new Map()
  if (!nodes || nodes.length === 0) return positions

  const rootData = buildPathTree(nodes)
  const rootHierarchy = hierarchy(rootData)
  const layout = tree().size([Math.max(width, 200), Math.max(height, 200)])
  layout(rootHierarchy)

  rootHierarchy.each(d => {
    if (d.data.id != null) positions.set(d.data.id, { x: d.x, y: d.y })
  })
  return positions
}

/**
 * Seeds x/y onto node objects in-place, only for nodes that don't already
 * have a position (so re-seeding on every render doesn't fight the running
 * force simulation) and only when the node count exceeds the threshold.
 * No-op below the threshold or when `nodes` is empty.
 */
export function seedHierarchyPositions(nodes, { width, height } = {}) {
  if (!nodes || nodes.length <= HIERARCHY_NODE_THRESHOLD) return
  const positions = computeHierarchyPositions(nodes, { width, height })
  for (const n of nodes) {
    if (n.x != null && n.y != null) continue
    const pos = positions.get(n.id)
    if (pos) {
      n.x = pos.x
      n.y = pos.y
    }
  }
}
