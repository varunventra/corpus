import React, { useMemo } from 'react'
import { GraphCanvas } from '../GraphCanvas.jsx'

export function ArchitectureTab({ graphData, staleMap, pulseMap, pulseAncestorIds, selectedNodeId, onNodeClick, fgRef }) {
  const archGraphData = useMemo(() => {
    if (!graphData || !graphData.nodes) return { nodes: [], links: [] }

    const dirNodes = graphData.nodes.filter(n => n.type === 'dir')
    const dirNodeIds = new Set(dirNodes.map(n => n.id))

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

    const edgeSet = new Set()
    const dirLinks = []

    for (const link of (graphData.links || [])) {
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

  const emptyMap = useMemo(() => new Map(), [])
  const emptySet = useMemo(() => new Set(), [])

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
      <GraphCanvas
        fgRef={fgRef}
        graphData={archGraphData}
        staleMap={staleMap}
        collapsedMap={emptyMap}
        selectedNodeId={selectedNodeId}
        onNodeClick={onNodeClick}
        childCounts={emptyMap}
        pulseMap={pulseMap}
        pulseAncestorIds={emptySet}
      />
    </div>
  )
}
