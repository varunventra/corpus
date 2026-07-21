import React, { useState, useMemo, useCallback, useRef } from 'react'
import { useGraph } from './hooks/useGraph.js'
import { GraphCanvas } from './components/GraphCanvas.jsx'
import { DocPanel } from './components/DocPanel.jsx'
import { ImportanceFilter } from './components/ImportanceFilter.jsx'

// ---- Helpers ----

/**
 * Build a Map<dirId, Set<childId>> from the raw nodes array.
 * A node is a direct child of a dir if its path starts with dir.path + '/'.
 * We only consider one level down.
 */
function buildDirectChildren(nodes) {
  const byPath = new Map(nodes.map(n => [n.path, n]))
  const children = new Map()  // dirId → Set<nodeId>

  for (const node of nodes) {
    const parts = node.path.split('/')
    if (parts.length < 2) continue  // root-level file, no parent dir node
    const parentPath = parts.slice(0, parts.length - 1).join('/')
    const parentNode = byPath.get(parentPath)
    if (parentNode && parentNode.type === 'dir') {
      if (!children.has(parentNode.id)) children.set(parentNode.id, new Set())
      children.get(parentNode.id).add(node.id)
    }
  }
  return children
}

/**
 * Given a set of collapsed dir IDs and the direct-children map,
 * return a Set of all node IDs that should be visible.
 * A node is hidden if any of its ancestor dirs is collapsed.
 */
function buildVisibleIds(nodes, collapsedMap, directChildren) {
  // Map nodeId → node
  const byId = new Map(nodes.map(n => [n.id, n]))
  const byPath = new Map(nodes.map(n => [n.path, n]))

  const visible = new Set()

  for (const node of nodes) {
    // Walk up path segments looking for a collapsed ancestor
    let hidden = false
    const parts = node.path.split('/')
    for (let i = 1; i < parts.length; i++) {
      const ancestorPath = parts.slice(0, i).join('/')
      const ancestor = byPath.get(ancestorPath)
      if (ancestor && ancestor.type === 'dir') {
        const isCollapsed = collapsedMap.get(ancestor.id) ?? true
        if (isCollapsed) {
          hidden = true
          break
        }
      }
    }
    if (!hidden) visible.add(node.id)
  }
  return visible
}

/**
 * For each collapsed dir node, count the TOTAL number of file descendants
 * (not just direct children) so the badge is meaningful.
 */
function buildChildCounts(nodes, collapsedMap) {
  const counts = new Map()
  for (const dir of nodes) {
    if (dir.type !== 'dir') continue
    const isCollapsed = collapsedMap.get(dir.id) ?? true
    if (!isCollapsed) continue
    const prefix = dir.path + '/'
    let count = 0
    for (const n of nodes) {
      if (n.id !== dir.id && n.path.startsWith(prefix)) count++
    }
    counts.set(dir.id, count)
  }
  return counts
}

/**
 * Apply importance filter to visible file nodes.
 * 'All'  → no filter
 * '1'–'5' → show file nodes with importance >= N, or importance === null
 * Dir nodes and nodes with null importance are always shown.
 */
function applyImportanceFilter(nodes, filter, visibleIds) {
  if (filter === 'All') return visibleIds
  const minImp = parseInt(filter, 10)
  const filtered = new Set()
  for (const id of visibleIds) {
    // We need the node to check — rebuild lookup happens below in App.
    filtered.add(id)
  }
  return filtered
}

// ---- App ----

const PULSE_DURATION_MS = 2000

export default function App() {
  // pulseMap: Map<node_id, expiry_timestamp> — entries removed after 2s
  const [pulseMap, setPulseMap] = useState(new Map())
  // Keep expiry timers so we can clear them if the component unmounts
  const pulseTimers = useRef(new Map())  // node_id → timer id

  const onQueryEvent = useCallback((nodeId) => {
    if (!nodeId) return
    const expiry = Date.now() + PULSE_DURATION_MS
    setPulseMap(prev => {
      const next = new Map(prev)
      next.set(nodeId, expiry)
      return next
    })
    // Clear any existing timer for this node and set a new one
    if (pulseTimers.current.has(nodeId)) {
      clearTimeout(pulseTimers.current.get(nodeId))
    }
    const timer = setTimeout(() => {
      setPulseMap(prev => {
        const next = new Map(prev)
        next.delete(nodeId)
        return next
      })
      pulseTimers.current.delete(nodeId)
    }, PULSE_DURATION_MS)
    pulseTimers.current.set(nodeId, timer)
  }, [])

  const { nodes, edges, staleMap, projectName, loading, error, retry } = useGraph({ onQueryEvent })

  // collapsedMap: Map<nodeId, boolean> — dirs start collapsed
  const [collapsedMap, setCollapsedMap] = useState(new Map())
  const [importanceFilter, setImportanceFilter] = useState('All')
  const [selectedNode, setSelectedNode] = useState(null)
  const [panelOpen, setPanelOpen] = useState(false)

  // Derive collapse state: default = true (collapsed) if not in map
  const getCollapsed = useCallback((id) => collapsedMap.get(id) ?? true, [collapsedMap])

  // Build supporting data structures
  const directChildren = useMemo(() => {
    if (!nodes) return new Map()
    return buildDirectChildren(nodes)
  }, [nodes])

  const visibleIds = useMemo(() => {
    if (!nodes) return new Set()
    return buildVisibleIds(nodes, collapsedMap, directChildren)
  }, [nodes, collapsedMap, directChildren])

  const childCounts = useMemo(() => {
    if (!nodes) return new Map()
    return buildChildCounts(nodes, collapsedMap)
  }, [nodes, collapsedMap])

  // Importance filter: filter file nodes, keep dirs and null-importance nodes
  const filteredVisibleIds = useMemo(() => {
    if (!nodes || importanceFilter === 'All') return visibleIds
    const minImp = parseInt(importanceFilter, 10)
    const byId = new Map(nodes.map(n => [n.id, n]))
    const result = new Set()
    for (const id of visibleIds) {
      const n = byId.get(id)
      if (!n) continue
      if (n.type === 'dir') { result.add(id); continue }
      if (n.importance === null || n.importance === undefined) { result.add(id); continue }
      if (n.importance >= minImp) result.add(id)
    }
    return result
  }, [nodes, visibleIds, importanceFilter])

  // Build graphData for react-force-graph
  const graphData = useMemo(() => {
    if (!nodes || !edges) return { nodes: [], links: [] }
    const visibleNodeList = nodes.filter(n => filteredVisibleIds.has(n.id))
    const visibleSet = new Set(visibleNodeList.map(n => n.id))
    const links = edges
      .filter(e => visibleSet.has(e.source?.id ?? e.source) && visibleSet.has(e.target?.id ?? e.target))
      .map(e => ({
        source: e.source?.id ?? e.source,
        target: e.target?.id ?? e.target,
      }))
    return { nodes: visibleNodeList, links }
  }, [nodes, edges, filteredVisibleIds])

  // Stamp __pulseAncestor on collapsed dir nodes that have pulsing descendants.
  // Mutates node objects in-place (same pattern as force simulation x/y mutation).
  // Runs whenever pulseMap changes so the canvas sees fresh flags on the next frame.
  useMemo(() => {
    if (!nodes) return
    const now = Date.now()
    // Build set of paths of currently active pulses
    const pulsingPaths = new Set()
    if (pulseMap.size > 0) {
      const byId = new Map(nodes.map(n => [n.id, n]))
      for (const [nodeId, expiry] of pulseMap) {
        if (expiry > now) {
          const n = byId.get(nodeId)
          if (n) pulsingPaths.add(n.path)
        }
      }
    }
    for (const node of nodes) {
      if (node.type !== 'dir') continue
      const prefix = node.path + '/'
      node.__pulseAncestor = pulsingPaths.size > 0 &&
        [...pulsingPaths].some(p => p.startsWith(prefix))
    }
  }, [nodes, pulseMap])

  const handleNodeClick = useCallback((node) => {
    if (node.type === 'dir') {
      // Toggle collapse
      setCollapsedMap(prev => {
        const next = new Map(prev)
        const current = next.get(node.id) ?? true
        next.set(node.id, !current)
        return next
      })
    } else {
      // Open doc panel
      setSelectedNode(node)
      setPanelOpen(true)
    }
  }, [])

  const closePanel = useCallback(() => {
    setPanelOpen(false)
    setSelectedNode(null)
  }, [])

  // Derive project name from cwd metadata or graph path
  const displayName = projectName || 'corpus'

  // ---- Loading / error / empty states ----

  if (loading) {
    return (
      <div style={fullscreenCenter}>
        <span style={monoMuted}>Loading graph...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div style={fullscreenCenter}>
        <span style={{ ...monoText, color: 'var(--color-text-primary)' }}>Failed to load graph.</span>
        <span style={{ ...bodyMuted, marginTop: '4px' }}>Is corpus serve running on localhost:7077?</span>
        <button
          onClick={retry}
          style={retryBtn}
          onMouseEnter={e => e.currentTarget.style.background = '#e0e0e0'}
          onMouseLeave={e => e.currentTarget.style.background = 'var(--color-surface-raised)'}
        >Retry</button>
      </div>
    )
  }

  if (!nodes || nodes.length === 0) {
    return (
      <div style={fullscreenCenter}>
        <span style={{ ...monoText, color: 'var(--color-text-primary)' }}>No files tracked yet.</span>
        <span style={{ ...bodyMuted, marginTop: '4px' }}>Run corpus init, then corpus update.</span>
      </div>
    )
  }

  const allFiltered = graphData.nodes.filter(n => n.type === 'file').length === 0 &&
                       importanceFilter !== 'All'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--color-bg)' }}>
      {/* Header */}
      <header style={{
        height: '56px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-bg)',
        flexShrink: 0,
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0' }}>
          <span style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 'var(--text-lg)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
          }}>
            {displayName}
          </span>
          <span style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 'var(--text-lg)',
            color: '#cccccc',
            margin: '0 6px',
          }}>·</span>
          <span style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 'var(--text-sm)',
            color: '#999999',
          }}>
            Click a node to view its doc · Click a folder to expand
          </span>
        </span>
        <ImportanceFilter value={importanceFilter} onChange={setImportanceFilter} />
      </header>

      {/* Main content */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative' }}>
        {/* Canvas area — shrinks when panel is open */}
        <div style={{
          flex: 1,
          overflow: 'hidden',
          position: 'relative',
          transition: 'width 200ms ease-out',
        }}>
          {allFiltered && (
            <div style={{ ...absoluteCenter }}>
              <span style={{ ...monoText, fontWeight: 600, color: 'var(--color-text-primary)' }}>
                All files hidden by the importance filter.
              </span>
              <span style={{ ...bodyMuted, marginTop: '4px' }}>
                Click All to show everything.
              </span>
            </div>
          )}
          <GraphCanvas
            graphData={graphData}
            staleMap={staleMap}
            collapsedMap={collapsedMap}
            selectedNodeId={selectedNode?.id ?? null}
            onNodeClick={handleNodeClick}
            childCounts={childCounts}
            pulseMap={pulseMap}
          />
        </div>

        {/* Doc panel */}
        <DocPanel
          node={selectedNode}
          isOpen={panelOpen}
          onClose={closePanel}
          staleMap={staleMap}
        />
      </div>
    </div>
  )
}

// ---- Shared style objects ----

const fullscreenCenter = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100vh',
  background: 'var(--color-bg)',
  gap: '4px',
}

const absoluteCenter = {
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '4px',
  zIndex: 10,
  pointerEvents: 'none',
}

const bodyText = {
  fontFamily: 'var(--font-sans)',
  fontSize: 'var(--text-md)',
  color: 'var(--color-text-muted)',
}

// monoText and monoMuted kept as aliases so inline JSX above still works
const monoText = bodyText
const monoMuted = bodyText

const bodyMuted = {
  fontFamily: 'var(--font-sans)',
  fontSize: 'var(--text-base)',
  color: 'var(--color-text-muted)',
}

const retryBtn = {
  fontFamily: 'var(--font-sans)',
  fontSize: 'var(--text-sm)',
  height: '30px',
  minHeight: '36px',
  border: '1px solid var(--color-border)',
  borderRadius: '5px',
  padding: '0 12px',
  background: 'var(--color-surface-raised)',
  color: 'var(--color-text-muted)',
  cursor: 'pointer',
  marginTop: '12px',
  display: 'inline-flex',
  alignItems: 'center',
}
