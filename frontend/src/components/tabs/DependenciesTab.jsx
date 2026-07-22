import React, { useMemo, useEffect } from 'react'
import { GraphCanvas } from '../GraphCanvas.jsx'

export function DependenciesTab({ graphData, selectedNode, onNodeSelect, staleMap, pulseMap, fgRef }) {
  const depGraphData = useMemo(() => {
    if (!selectedNode || selectedNode.type === 'dir' || !graphData.nodes) return null

    const nodeById = new Map(graphData.nodes.map(n => [n.id, n]))
    const centerId = selectedNode.id
    const includedIds = new Set([centerId])

    for (const link of (graphData.links || [])) {
      const srcId = link.source?.id ?? link.source
      const tgtId = link.target?.id ?? link.target
      if (srcId === centerId) includedIds.add(tgtId)
      if (tgtId === centerId) includedIds.add(srcId)
    }

    const subNodes = [...includedIds].map(id => nodeById.get(id)).filter(Boolean)
    const subLinks = (graphData.links || []).filter(link => {
      const srcId = link.source?.id ?? link.source
      const tgtId = link.target?.id ?? link.target
      return includedIds.has(srcId) && includedIds.has(tgtId)
    })

    return { nodes: subNodes, links: subLinks }
  }, [graphData, selectedNode])

  useEffect(() => {
    if (!depGraphData || !fgRef?.current) return
    const id = setTimeout(() => fgRef.current?.zoomToFit(400, 40), 300)
    return () => clearTimeout(id)
  }, [depGraphData])

  const emptyMap = useMemo(() => new Map(), [])
  const emptySet = useMemo(() => new Set(), [])

  if (!selectedNode || selectedNode.type === 'dir') {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <span style={{
          fontFamily: 'var(--font-headline)',
          fontStyle: 'italic',
          fontSize: 20,
          color: 'var(--color-text-muted)',
        }}>
          Select a file to explore its dependency graph.
        </span>
      </div>
    )
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
      <GraphCanvas
        fgRef={fgRef}
        graphData={depGraphData || { nodes: [], links: [] }}
        staleMap={staleMap}
        collapsedMap={emptyMap}
        selectedNodeId={selectedNode?.id}
        onNodeClick={onNodeSelect}
        childCounts={emptyMap}
        pulseMap={pulseMap || emptyMap}
        pulseAncestorIds={emptySet}
      />
    </div>
  )
}
