// Phase 9 — Overview-mode curation.
//
// Pure functions only: no React, no canvas, no DOM. Selects a curated subset
// of file nodes for the Explorer tab's "Overview" mode, either importance-
// ranked (when enough file nodes carry a non-null LLM importance score) or
// degree-ranked (fallback — same algorithm, different scoring function).
//
// hasImportance decision (computed by the caller, ExplorerTab.jsx, not here,
// so this module stays a pure function of its inputs):
//
//   const fileNodes = nodes.filter(n => n.type === 'file')
//   const withScore = fileNodes.filter(n => n.importance != null).length
//   const hasImportance = withScore >= Math.max(3, Math.round(fileNodes.length * 0.5))
//
// i.e. "importance present" means AT LEAST HALF the file nodes (floor of 3)
// have a non-null score. This tolerates partial doc generation (some files
// stale/skipped) instead of requiring literally every node to have a score.

export function idOf(endpoint) {
  return typeof endpoint === 'object' ? endpoint.id : endpoint
}

export function computeDegree(fileNodeIds, edges) {
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
// recursive drill-in curation within a single directory, PLAN.md §7). Pass
// null/undefined for the top-level Overview computation (scope = all files).
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
