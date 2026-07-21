import React, { useCallback, useRef } from 'react'
import ForceGraph2D from 'react-force-graph-2d'

// ---- Constants from design spec (light theme, white/red/achromatic) ----
const COLOR_BG         = '#ffffff'
const COLOR_FRESH      = '#E63946'
const COLOR_FRESH_DARK = '#B71C2A'
const COLOR_STALE      = '#9E9E9E'
const COLOR_STALE_DARK = '#616161'
const COLOR_EDGE       = '#aaaaaa'
const COLOR_LABEL      = '#555555'
const COLOR_RING       = '#E63946'

const FONT_LABEL     = "13px 'Inter', system-ui, sans-serif"
const FONT_DIR_BADGE = "bold 8px 'Inter', system-ui, sans-serif"
const FONT_DIR_COUNT = "8px 'Inter', system-ui, sans-serif"

function fileRadius(importance) {
  if (importance == null) return 6
  // importance 1 → 4px, importance 5 → 12px
  return importance * 1.6 + 2.4
}

function isPulsing(node, pulseMap) {
  if (!pulseMap) return false
  const expiry = pulseMap.get(node.id)
  return expiry !== undefined && expiry > Date.now()
}

function nodeColor(node, staleMap, pulseMap) {
  if (isPulsing(node, pulseMap)) return '#ffffff'
  const isStale = staleMap.get(node.id) ?? !!node.stale
  if (node.type === 'dir') {
    return isStale ? COLOR_STALE_DARK : COLOR_FRESH_DARK
  }
  return isStale ? COLOR_STALE : COLOR_FRESH
}

function nodeRadius(node) {
  if (node.type === 'dir') return 16
  return fileRadius(node.importance)
}

function lastName(path) {
  const parts = path.split('/')
  return parts[parts.length - 1] || path
}

/**
 * GraphCanvas renders the force-directed graph via react-force-graph.
 *
 * Props:
 *   graphData      — { nodes, links } already filtered for collapse/importance
 *   staleMap       — Map<id, boolean>
 *   collapsedMap   — Map<id, boolean>
 *   selectedNodeId — string | null
 *   onNodeClick    — (node) => void
 *   childCounts    — Map<id, number>  (visible child count for collapsed dirs)
 *   pulseMap       — Map<id, expiry_timestamp>  (node pulses white for ~2s)
 */
export function GraphCanvas({
  graphData,
  staleMap,
  collapsedMap,
  selectedNodeId,
  onNodeClick,
  childCounts,
  pulseMap = new Map(),
}) {
  const fgRef = useRef()

  // nodeCanvasObject: custom rendering per node
  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const r = nodeRadius(node)
    const isStale = staleMap.get(node.id) ?? !!node.stale
    const isDir = node.type === 'dir'
    const isCollapsed = collapsedMap.get(node.id) ?? true
    const isSelected = node.id === selectedNodeId
    const nodePulsing = isPulsing(node, pulseMap)
    const fill = nodeColor(node, staleMap, pulseMap)

    // Stale ancestor glow (collapsed dir with stale descendants)
    if (isDir && isCollapsed && isStale && !nodePulsing) {
      ctx.save()
      ctx.shadowColor = '#9E9E9E'
      ctx.shadowBlur = 5 / globalScale
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = fill
      ctx.fill()
      ctx.restore()
    } else {
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = fill
      ctx.fill()
    }

    // Pulse ring for collapsed dirs whose descendants are pulsing
    if (isDir && isCollapsed && !nodePulsing && node.__pulseAncestor) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, r + 2, 0, 2 * Math.PI)
      ctx.strokeStyle = COLOR_RING
      ctx.lineWidth = 2 / globalScale
      ctx.stroke()
    }

    // Selection ring — red, sits outside fill
    if (isSelected) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, r + 2, 0, 2 * Math.PI)
      ctx.strokeStyle = COLOR_RING
      ctx.lineWidth = 2.5 / globalScale
      ctx.stroke()
    }

    // Dir node: ▶ indicator + child count when collapsed
    if (isDir && isCollapsed) {
      const count = childCounts.get(node.id) ?? 0
      if (count > 0) {
        ctx.fillStyle = '#ffffff'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        // ▶ character centered slightly above middle
        ctx.font = FONT_DIR_BADGE
        ctx.fillText('▶', node.x, node.y - 2)
        // count below ▶
        ctx.font = FONT_DIR_COUNT
        ctx.fillText(String(count), node.x, node.y + 5)
      }
    }

    // Node label — hide below zoom 0.2 (was 0.4)
    if (globalScale >= 0.2) {
      const label = lastName(node.path)
      const labelY = node.y + r + 6
      ctx.font = FONT_LABEL
      ctx.fillStyle = COLOR_LABEL
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillText(label, node.x, labelY)
    }
  }, [staleMap, collapsedMap, selectedNodeId, childCounts, pulseMap])

  const nodePointerAreaPaint = useCallback((node, color, ctx) => {
    const r = nodeRadius(node)
    ctx.beginPath()
    ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI)
    ctx.fillStyle = color
    ctx.fill()
  }, [])

  const linkColor = useCallback(() => COLOR_EDGE, [])
  const linkWidth = useCallback(() => 1.5, [])

  const handleNodeClick = useCallback((node) => {
    onNodeClick(node)
  }, [onNodeClick])

  return (
    <div
      style={{
        flex: 1,
        height: '100%',
        overflow: 'hidden',
        position: 'relative',
        background: COLOR_BG,
      }}
    >
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        backgroundColor={COLOR_BG}
        nodeCanvasObject={nodeCanvasObject}
        nodePointerAreaPaint={nodePointerAreaPaint}
        nodeCanvasObjectMode={() => 'replace'}
        linkColor={linkColor}
        linkWidth={linkWidth}
        onNodeClick={handleNodeClick}
        nodeLabel={() => ''}   // no built-in tooltip — we render labels in canvas
        enableNodeDrag
        enableZoomInteraction
        enablePanInteraction
        width={undefined}   // fills container
        height={undefined}
      />
    </div>
  )
}
