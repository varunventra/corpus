import React, { useState, useMemo, useCallback, useRef } from 'react'
import { GraphCanvas } from '../GraphCanvas.jsx'
import { curateOverview, curateFiles, idOf } from '../../lib/graphCuration.js'
import { lastName } from '../../utils/path.js'

// ---- Pure helpers (Overview-mode-scoped; mirror App.jsx's shape, but keyed
//      to the raw full node list + Overview's own collapse map, per DECISIONS.md
//      2026-07-22: curation/layout logic stays out of App.jsx/GraphCanvas.jsx,
//      and Overview's collapse state is deliberately independent of the
//      All-Files collapsedMap — see design spec §10.) ----

function buildDirectChildrenAll(nodes) {
  const byPath = new Map(nodes.map(n => [n.path, n]))
  const children = new Map()
  for (const node of nodes) {
    const parts = node.path.split('/')
    if (parts.length < 2) continue
    const parentPath = parts.slice(0, parts.length - 1).join('/')
    const parentNode = byPath.get(parentPath)
    if (parentNode && parentNode.type === 'dir') {
      if (!children.has(parentNode.id)) children.set(parentNode.id, new Set())
      children.get(parentNode.id).add(node.id)
    }
  }
  return children
}

function buildFullChildCounts(nodes) {
  const counts = new Map()
  for (const dir of nodes) {
    if (dir.type !== 'dir') continue
    const prefix = dir.path + '/'
    let count = 0
    for (const n of nodes) {
      if (n.id !== dir.id && n.path.startsWith(prefix)) count++
    }
    counts.set(dir.id, count)
  }
  return counts
}

function ancestorDirIds(node, nodesByPath) {
  const ids = []
  if (!node) return ids
  const parts = node.path.split('/')
  for (let i = 1; i < parts.length; i++) {
    const ancestorPath = parts.slice(0, i).join('/')
    const ancestor = nodesByPath.get(ancestorPath)
    if (ancestor && ancestor.type === 'dir') ids.push(ancestor.id)
  }
  return ids
}

/**
 * Computes Overview mode's visible node id set: the always-shown top-level
 * dirs + the globally-curated file set (importance- or degree-ranked, per
 * graphCuration.js), plus recursive drill-in additions for any dir the user
 * has expanded via overviewCollapsedMap (design spec §7).
 */
function computeOverviewNodeIds(nodes, edges, overviewCollapsedMap, hasImportance) {
  const byId = new Map(nodes.map(n => [n.id, n]))
  const directChildren = buildDirectChildrenAll(nodes)
  const fileNodes = nodes.filter(n => n.type === 'file')

  const base = curateOverview(nodes, edges, { hasImportance })
  const nodeIds = new Set(base.nodeIds)

  const topDirs = nodes.filter(n => n.type === 'dir' && !n.path.includes('/'))
  const queue = topDirs.map(d => d.id)
  const processed = new Set()

  while (queue.length > 0) {
    const dirId = queue.shift()
    if (processed.has(dirId)) continue
    processed.add(dirId)

    const isExpanded = overviewCollapsedMap.get(dirId) === false
    if (!isExpanded) continue

    const childIds = directChildren.get(dirId)
    if (!childIds) continue

    const childFileIds = new Set()
    for (const cid of childIds) {
      const cnode = byId.get(cid)
      if (!cnode) continue
      if (cnode.type === 'dir') {
        nodeIds.add(cid)
        queue.push(cid)
      } else {
        childFileIds.add(cid)
      }
    }

    if (childFileIds.size > 0) {
      const { curatedIds } = curateFiles(fileNodes, edges, { hasImportance, scopeFileIds: childFileIds })
      for (const id of curatedIds) nodeIds.add(id)
    }
  }

  return { nodeIds, curatedFileCount: base.curatedFileIds.size }
}

// ---- Mode toggle + count chip + pulse-reveal banner ----

function ModeToggle({ explorerMode, setExplorerMode, fgRef, shownCount, totalCount, hasImportance, banner }) {
  const segmentStyle = (active) => ({
    padding: '6px 14px',
    fontFamily: 'var(--font-body)',
    fontSize: 12,
    fontWeight: 600,
    border: 'none',
    cursor: 'pointer',
    background: active ? 'var(--color-accent-dim)' : 'transparent',
    color: active ? 'var(--color-accent)' : 'var(--color-text-secondary)',
  })

  const switchMode = useCallback((mode) => {
    setExplorerMode(mode)
    setTimeout(() => fgRef.current?.zoomToFit(400, 60), 0)
  }, [setExplorerMode, fgRef])

  return (
    <div style={{ position: 'absolute', top: 16, left: 16, zIndex: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        background: 'rgba(22,27,34,0.92)',
        border: '1px solid var(--color-border)',
        borderRadius: 6,
        display: 'flex',
        overflow: 'hidden',
      }}>
        <button
          type="button"
          aria-pressed={explorerMode === 'overview'}
          onClick={() => switchMode('overview')}
          style={segmentStyle(explorerMode === 'overview')}
          onMouseEnter={e => { if (explorerMode !== 'overview') e.currentTarget.style.color = 'var(--color-accent)' }}
          onMouseLeave={e => { if (explorerMode !== 'overview') e.currentTarget.style.color = 'var(--color-text-secondary)' }}
        >Overview</button>
        <button
          type="button"
          aria-pressed={explorerMode === 'all'}
          onClick={() => switchMode('all')}
          style={{ ...segmentStyle(explorerMode === 'all'), borderLeft: '1px solid var(--color-border)' }}
          onMouseEnter={e => { if (explorerMode !== 'all') e.currentTarget.style.color = 'var(--color-accent)' }}
          onMouseLeave={e => { if (explorerMode !== 'all') e.currentTarget.style.color = 'var(--color-text-secondary)' }}
        >All Files</button>
      </div>

      {explorerMode === 'overview' && (
        <div style={{
          background: 'rgba(22,27,34,0.92)',
          border: '1px solid var(--color-border)',
          borderRadius: 6,
          padding: '6px 12px',
          fontFamily: 'var(--font-body)',
          fontSize: 12,
          color: 'var(--color-text-secondary)',
          whiteSpace: 'nowrap',
        }}>
          {`${shownCount} of ${totalCount} shown · by ${hasImportance ? 'importance' : 'connections'}`}
        </div>
      )}

      {explorerMode === 'overview' && banner && (
        <div style={{
          background: 'rgba(22,27,34,0.92)',
          border: '1px solid var(--color-border)',
          borderRadius: 6,
          padding: '6px 12px',
          fontFamily: 'var(--font-body)',
          fontSize: 12,
          color: 'var(--color-node-pulse)',
          whiteSpace: 'nowrap',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <span>{`Showing ${banner.filename} — outside curated view`}</span>
          <span
            onClick={() => setExplorerMode('all')}
            style={{ color: 'var(--color-accent)', textDecoration: 'underline', cursor: 'pointer' }}
          >Show in All Files</span>
        </div>
      )}
    </div>
  )
}

function ZoomControls({ fgRef }) {
  return (
    <div style={{
      position: 'absolute',
      bottom: 68,
      left: 16,
      zIndex: 10,
      display: 'flex',
      flexDirection: 'column',
      gap: 1,
      background: 'rgba(22,27,34,0.92)',
      border: '1px solid var(--color-border)',
      borderRadius: 6,
      overflow: 'hidden',
    }}>
      {[
        { label: '+', title: 'Zoom in',  onClick: () => fgRef.current && fgRef.current.zoom(fgRef.current.zoom() * 1.3, 200) },
        { label: '−', title: 'Zoom out', onClick: () => fgRef.current && fgRef.current.zoom(fgRef.current.zoom() * 0.7, 200) },
        { label: '⊙', title: 'Fit',      onClick: () => fgRef.current && fgRef.current.zoomToFit(400, 40) },
      ].map(btn => (
        <button
          key={btn.label}
          title={btn.title}
          onClick={btn.onClick}
          style={{
            width: 32, height: 32, border: 'none',
            borderTop: btn.label === '+' ? 'none' : '1px solid var(--color-border)',
            background: 'transparent', color: 'var(--color-text-secondary)', cursor: 'pointer',
            fontFamily: 'var(--font-sans)', fontSize: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--color-accent)'}
          onMouseLeave={e => e.currentTarget.style.color = 'var(--color-text-secondary)'}
        >{btn.label}</button>
      ))}
    </div>
  )
}

function StatsBar({ graphData }) {
  if (!graphData) return null
  return (
    <div style={{
      position: 'absolute',
      bottom: 16,
      left: 16,
      zIndex: 10,
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '6px 12px',
      background: 'rgba(22,27,34,0.92)',
      border: '1px solid var(--color-border)',
      borderRadius: 6,
      pointerEvents: 'none',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-node-file)', border: '1px solid var(--color-border)' }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Fresh</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-node-stale)' }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Stale</span>
      </div>
      <div style={{ width: 1, height: 12, background: 'var(--color-border)' }} />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
        {`Nodes: ${graphData.nodes?.length ?? 0} | Edges: ${(graphData.links ?? []).length}`}
      </span>
    </div>
  )
}

export function ExplorerTab({
  graphData, nodes, edges, staleMap, collapsedMap, selectedNodeId, onNodeClick,
  childCounts, pulseMap, pulseAncestorIds, fgRef,
}) {
  const [explorerMode, setExplorerMode] = useState('overview')
  const [overviewCollapsedMap, setOverviewCollapsedMap] = useState(new Map())

  const hasImportance = useMemo(() => {
    const fileNodes = (nodes || []).filter(n => n.type === 'file')
    const withScore = fileNodes.filter(n => n.importance != null).length
    return withScore >= Math.max(3, Math.round(fileNodes.length * 0.5))
  }, [nodes])

  const overviewResult = useMemo(() => {
    if (explorerMode !== 'overview' || !nodes || !edges) return null
    return computeOverviewNodeIds(nodes, edges, overviewCollapsedMap, hasImportance)
  }, [explorerMode, nodes, edges, overviewCollapsedMap, hasImportance])

  const nodesByPath = useMemo(() => new Map((nodes || []).map(n => [n.path, n])), [nodes])
  const nodesById = useMemo(() => new Map((nodes || []).map(n => [n.id, n])), [nodes])

  // Pulse-reveal (design spec Q8): a query event naming a node outside
  // Overview's curated set gets temporarily pinned in, for exactly as long
  // as pulseMap holds it — plus its ancestor dir chain, so it isn't floating
  // with no path context.
  //
  // pinnedNodeIdsRef caches the previous result and is returned as-is when
  // the contents haven't actually changed (e.g. a same-node pulse re-tick),
  // so downstream memos (overviewGraphData -> graphData) don't see a new
  // object identity and needlessly re-trigger GraphCanvas's zoomToFit effect.
  const pinnedNodeIdsRef = useRef(new Set())
  const pinnedNodeIds = useMemo(() => {
    const ids = new Set()
    if (explorerMode === 'overview' && overviewResult && pulseMap) {
      for (const [nodeId] of pulseMap) {
        if (overviewResult.nodeIds.has(nodeId)) continue
        const node = nodesById.get(nodeId)
        if (!node) continue
        ids.add(nodeId)
        for (const ancestorId of ancestorDirIds(node, nodesByPath)) ids.add(ancestorId)
      }
    }
    const prev = pinnedNodeIdsRef.current
    if (prev.size === ids.size && [...ids].every(id => prev.has(id))) {
      return prev
    }
    pinnedNodeIdsRef.current = ids
    return ids
  }, [explorerMode, overviewResult, pulseMap, nodesById, nodesByPath])

  // Of the pinned ids, the subset that are ancestor directories (not the
  // pulsed node itself) — these get temporarily forced "expanded" for
  // rendering purposes below, so the pulsed node reads as "revealed inside
  // its folder" rather than floating next to a still-collapsed folder badge.
  // Lifecycle mirrors pinnedNodeIds exactly (same source, same eviction).
  const pulseAncestorDirIds = useMemo(() => {
    const ids = new Set()
    for (const id of pinnedNodeIds) {
      const node = nodesById.get(id)
      if (node && node.type === 'dir') ids.add(id)
    }
    return ids
  }, [pinnedNodeIds, nodesById])

  // Overview's collapsed-state map, overridden (not mutated) so ancestor
  // dirs of a pulse-revealed node render as expanded for the duration of the
  // reveal. Used for rendering/badge purposes only — computeOverviewNodeIds
  // above still reads the real overviewCollapsedMap, so this override does
  // not trigger a full recursive drill-in curation of the directory.
  const overviewEffectiveCollapsedMap = useMemo(() => {
    if (pulseAncestorDirIds.size === 0) return overviewCollapsedMap
    const next = new Map(overviewCollapsedMap)
    for (const id of pulseAncestorDirIds) next.set(id, false)
    return next
  }, [overviewCollapsedMap, pulseAncestorDirIds])

  const bannerNode = useMemo(() => {
    if (pinnedNodeIds.size === 0 || !pulseMap) return null
    for (const [nodeId] of pulseMap) {
      if (overviewResult && !overviewResult.nodeIds.has(nodeId)) {
        const node = nodesById.get(nodeId)
        if (node) return node
      }
    }
    return null
  }, [pinnedNodeIds, pulseMap, overviewResult, nodesById])

  const overviewChildCounts = useMemo(() => {
    if (!nodes) return new Map()
    const full = buildFullChildCounts(nodes)
    const counts = new Map()
    for (const [id, count] of full) {
      const isCollapsed = overviewEffectiveCollapsedMap.get(id) ?? true
      if (isCollapsed) counts.set(id, count)
    }
    return counts
  }, [nodes, overviewEffectiveCollapsedMap])

  const overviewGraphData = useMemo(() => {
    if (!overviewResult || !nodes || !edges) return { nodes: [], links: [] }
    const finalIds = new Set(overviewResult.nodeIds)
    for (const id of pinnedNodeIds) finalIds.add(id)
    const visibleNodeList = nodes.filter(n => finalIds.has(n.id))
    const links = edges
      .filter(e => finalIds.has(idOf(e.source)) && finalIds.has(idOf(e.target)))
      .map(e => ({ source: idOf(e.source), target: idOf(e.target) }))
    return { nodes: visibleNodeList, links }
  }, [overviewResult, pinnedNodeIds, nodes, edges])

  const handleOverviewNodeClick = useCallback((node) => {
    if (node.type === 'dir') {
      setOverviewCollapsedMap(prev => {
        const next = new Map(prev)
        const current = next.get(node.id) ?? true
        next.set(node.id, !current)
        return next
      })
    } else {
      onNodeClick(node)
    }
  }, [onNodeClick])

  const activeGraphData = explorerMode === 'overview' ? overviewGraphData : graphData
  const activeCollapsedMap = explorerMode === 'overview' ? overviewEffectiveCollapsedMap : collapsedMap
  const activeChildCounts = explorerMode === 'overview' ? overviewChildCounts : childCounts
  const activeOnNodeClick = explorerMode === 'overview' ? handleOverviewNodeClick : onNodeClick

  const totalFileCount = useMemo(() => (nodes || []).filter(n => n.type === 'file').length, [nodes])
  const shownFileCount = useMemo(() => {
    if (explorerMode !== 'overview') return totalFileCount
    return (overviewGraphData.nodes || []).filter(n => n.type === 'file').length
  }, [explorerMode, overviewGraphData, totalFileCount])

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
      <GraphCanvas
        fgRef={fgRef}
        graphData={activeGraphData}
        staleMap={staleMap}
        collapsedMap={activeCollapsedMap}
        selectedNodeId={selectedNodeId}
        onNodeClick={activeOnNodeClick}
        childCounts={activeChildCounts}
        pulseMap={pulseMap}
        pulseAncestorIds={pulseAncestorIds}
      />
      <ModeToggle
        explorerMode={explorerMode}
        setExplorerMode={setExplorerMode}
        fgRef={fgRef}
        shownCount={shownFileCount}
        totalCount={totalFileCount}
        hasImportance={hasImportance}
        banner={bannerNode ? { filename: lastName(bannerNode.path) } : null}
      />
      <ZoomControls fgRef={fgRef} />
      <StatsBar graphData={activeGraphData} />
    </div>
  )
}
