import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useGraph } from './hooks/useGraph.js'
import { useMeta } from './hooks/useMeta.js'
import { GraphCanvas } from './components/GraphCanvas.jsx'
import { FileTree } from './components/FileTree.jsx'
import { DocReader } from './components/DocReader.jsx'
import { ExplorerTab } from './components/tabs/ExplorerTab.jsx'
import { ArchitectureTab } from './components/tabs/ArchitectureTab.jsx'
import { DependenciesTab } from './components/tabs/DependenciesTab.jsx'
import { SymbolsTab } from './components/tabs/SymbolsTab.jsx'
import { OverviewTab } from './components/tabs/OverviewTab.jsx'

// ---- Helpers ----

function buildDirectChildren(nodes) {
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

function buildVisibleIds(nodes, collapsedMap, directChildren) {
  const byPath = new Map(nodes.map(n => [n.path, n]))
  const visible = new Set()
  for (const node of nodes) {
    let hidden = false
    const parts = node.path.split('/')
    for (let i = 1; i < parts.length; i++) {
      const ancestorPath = parts.slice(0, i).join('/')
      const ancestor = byPath.get(ancestorPath)
      if (ancestor && ancestor.type === 'dir') {
        const isCollapsed = collapsedMap.get(ancestor.id) ?? true
        if (isCollapsed) { hidden = true; break }
      }
    }
    if (!hidden) visible.add(node.id)
  }
  return visible
}

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

// ---- App ----

const PULSE_DURATION_MS = 2000

export default function App() {
  const [pulseMap, setPulseMap] = useState(new Map())
  const pulseTimers = useRef(new Map())

  const onQueryEvent = useCallback((nodeId) => {
    if (!nodeId) return
    const expiry = Date.now() + PULSE_DURATION_MS
    setPulseMap(prev => { const next = new Map(prev); next.set(nodeId, expiry); return next })
    if (pulseTimers.current.has(nodeId)) clearTimeout(pulseTimers.current.get(nodeId))
    const timer = setTimeout(() => {
      setPulseMap(prev => { const next = new Map(prev); next.delete(nodeId); return next })
      pulseTimers.current.delete(nodeId)
    }, PULSE_DURATION_MS)
    pulseTimers.current.set(nodeId, timer)
  }, [])

  const { nodes, edges, staleMap, loading, error, retry } = useGraph({ onQueryEvent })
  const { repoRoot } = useMeta()

  const [activeTab, setActiveTab] = useState('explorer')
  const [fileTreeVisible, setFileTreeVisible] = useState(true)
  const [collapsedMap, setCollapsedMap] = useState(new Map())
  const [selectedNode, setSelectedNode] = useState(null)
  const [panelOpen, setPanelOpen] = useState(false)

  const fgRef = useRef()

  // Seed root-level dirs as expanded on first load
  useEffect(() => {
    if (!nodes || nodes.length === 0) return
    setCollapsedMap(prev => {
      const next = new Map(prev)
      for (const n of nodes) {
        if (n.type !== 'dir') continue
        const depth = (n.path.match(/\//g) || []).length
        if (depth === 0 && !prev.has(n.id)) {
          next.set(n.id, false)
        }
      }
      return next
    })
  }, [nodes])

  // Escape key closes doc reader
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape' && panelOpen) closePanel()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [panelOpen, closePanel])

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

  const graphData = useMemo(() => {
    if (!nodes || !edges) return { nodes: [], links: [] }
    const visibleNodeList = nodes.filter(n => visibleIds.has(n.id))
    const visibleSet = new Set(visibleNodeList.map(n => n.id))
    const links = edges
      .filter(e => visibleSet.has(e.source?.id ?? e.source) && visibleSet.has(e.target?.id ?? e.target))
      .map(e => ({ source: e.source?.id ?? e.source, target: e.target?.id ?? e.target }))
    return { nodes: visibleNodeList, links }
  }, [nodes, edges, visibleIds])

  const pulseAncestorIds = useMemo(() => {
    const ids = new Set()
    if (!nodes) return ids
    for (const [nodeId] of pulseMap) {
      const node = nodes.find(n => n.id === nodeId)
      if (!node) continue
      const parts = node.path.split('/')
      for (let i = 1; i < parts.length; i++) {
        const ancestorPath = parts.slice(0, i).join('/')
        const ancestor = nodes.find(n => n.path === ancestorPath && n.type === 'dir')
        if (ancestor && collapsedMap.get(ancestor.id)) ids.add(ancestor.id)
      }
    }
    return ids
  }, [pulseMap, nodes, collapsedMap])

  const handleNodeClick = useCallback((node) => {
    if (node.type === 'dir') {
      setCollapsedMap(prev => {
        const next = new Map(prev)
        const current = next.get(node.id) ?? true
        next.set(node.id, !current)
        return next
      })
    } else {
      setSelectedNode(node)
      setPanelOpen(true)
    }
  }, [])

  const closePanel = useCallback(() => {
    setPanelOpen(false)
    setSelectedNode(null)
  }, [])

  // ---- Loading / error / empty ----

  if (loading) {
    return (
      <div style={fullscreenCenter}>
        <span style={{ fontFamily: 'var(--font-headline)', fontSize: 24, color: 'var(--color-text-muted)' }}>Loading...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div style={fullscreenCenter}>
        <span style={{ fontFamily: 'var(--font-headline)', fontSize: 20, color: 'var(--color-text-primary)' }}>Could not connect to Corpus.</span>
        <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)', marginTop: 4 }}>Is corpus serve running on localhost:7077?</span>
        <button onClick={retry} style={retryBtn}>Retry</button>
      </div>
    )
  }

  if (!nodes || nodes.length === 0) {
    return (
      <div style={fullscreenCenter}>
        <span style={{ fontFamily: 'var(--font-headline)', fontSize: 20, color: 'var(--color-text-primary)' }}>No files tracked yet.</span>
        <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)', marginTop: 4 }}>Run corpus init, then corpus update.</span>
      </div>
    )
  }

  const TABS = ['explorer', 'architecture', 'dependencies', 'symbols', 'overview']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--color-bg)' }}>

      {/* Top nav */}
      <header style={{
        height: 64, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px',
        background: 'var(--color-surface)',
        borderBottom: '1px solid var(--color-border)',
        zIndex: 30,
      }}>
        {/* Left cluster */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
          <span style={{ fontFamily: 'var(--font-headline)', fontSize: 24, fontWeight: 500, color: 'var(--color-accent)' }}>Corpus</span>
          <nav style={{ display: 'flex', alignItems: 'stretch', height: 64, gap: 0 }}>
            {TABS.map(tab => (
              <button
                key={tab}
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  fontFamily: 'var(--font-body)', fontSize: 14,
                  fontWeight: activeTab === tab ? 600 : 500,
                  color: activeTab === tab ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                  borderBottom: activeTab === tab ? '2px solid var(--color-accent)' : '2px solid transparent',
                  borderTop: 'none', borderLeft: 'none', borderRight: 'none',
                  background: 'none', padding: '0 16px', cursor: 'pointer',
                  textTransform: 'capitalize',
                  transition: 'color 150ms, border-color 150ms',
                }}
                onMouseEnter={e => { if (activeTab !== tab) { e.currentTarget.style.color = 'var(--color-accent)'; e.currentTarget.style.background = 'var(--color-surface-low)' } }}
                onMouseLeave={e => { if (activeTab !== tab) { e.currentTarget.style.color = 'var(--color-text-secondary)'; e.currentTarget.style.background = 'none' } }}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </nav>
        </div>

        {/* Right cluster */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ position: 'relative' }}>
            <span className="material-symbols-outlined" aria-hidden="true" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)', fontSize: 16, pointerEvents: 'none' }}>search</span>
            <input
              type="text"
              aria-label="Search nodes"
              placeholder="Search nodes..."
              style={{
                paddingLeft: 32, paddingRight: 16, paddingTop: 6, paddingBottom: 6,
                background: 'var(--color-surface-low)', border: '1px solid var(--color-border)',
                borderRadius: 9999, fontFamily: 'var(--font-body)', fontSize: 13,
                color: 'var(--color-text-primary)', width: 220, outline: 'none',
              }}
              onFocus={e => { e.target.style.borderColor = 'var(--color-accent)'; e.target.style.boxShadow = '0 0 0 1px var(--color-accent)' }}
              onBlur={e => { e.target.style.borderColor = 'var(--color-border)'; e.target.style.boxShadow = 'none' }}
            />
          </div>
          <div style={{ width: 1, height: 24, background: 'var(--color-border)' }} />
          <button
            aria-label="Refresh"
            onClick={() => window.location.reload()}
            style={{ width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', borderRadius: 6, cursor: 'pointer', color: 'var(--color-text-secondary)' }}
            onMouseEnter={e => { e.currentTarget.style.color = 'var(--color-accent)'; e.currentTarget.style.background = 'var(--color-surface-low)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--color-text-secondary)'; e.currentTarget.style.background = 'none' }}
          >
            <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 20 }}>refresh</span>
          </button>
          <button
            aria-label="Settings"
            style={{ width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', borderRadius: 6, cursor: 'pointer', color: 'var(--color-text-secondary)' }}
            onMouseEnter={e => { e.currentTarget.style.color = 'var(--color-accent)'; e.currentTarget.style.background = 'var(--color-surface-low)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--color-text-secondary)'; e.currentTarget.style.background = 'none' }}
          >
            <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 20 }}>settings</span>
          </button>
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
            <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 20 }}>account_tree</span>
          </button>
        </div>
      </header>

      {/* Body: three columns */}
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
          <div style={{ width: 260, height: '100%' }}>
            <FileTree
              nodes={nodes}
              selectedNodeId={selectedNode?.id ?? null}
              onNodeSelect={handleNodeClick}
              collapsedMap={collapsedMap}
              onToggleCollapse={(nodeId) => setCollapsedMap(prev => {
                const next = new Map(prev)
                next.set(nodeId, !(prev.get(nodeId) ?? true))
                return next
              })}
              staleMap={staleMap}
            />
          </div>
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
  )
}

// ---- Shared style objects ----

const fullscreenCenter = {
  display: 'flex', flexDirection: 'column', alignItems: 'center',
  justifyContent: 'center', height: '100vh', background: 'var(--color-bg)', gap: 4,
}

const retryBtn = {
  fontFamily: 'var(--font-body)', fontSize: 13,
  height: 36, border: '1px solid var(--color-border)', borderRadius: 6,
  padding: '0 16px', background: 'var(--color-surface-low)',
  color: 'var(--color-text-secondary)', cursor: 'pointer', marginTop: 12,
  display: 'inline-flex', alignItems: 'center',
}
