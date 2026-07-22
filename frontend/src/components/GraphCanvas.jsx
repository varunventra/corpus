import React, { useCallback, useRef, useState, useEffect } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { lastName } from '../utils/path.js'

// ── GitHub dark palette ──────────────────────────────────────────────────────
const COLOR_BG                 = '#0d1117'
const COLOR_NODE_FILE          = '#161b22'
const COLOR_NODE_DIR           = '#4493f8'
const COLOR_NODE_STALE         = '#d29922'
const COLOR_NODE_PULSE         = '#3fb950'
const COLOR_NODE_SELECTED_RING = '#4493f8'
const COLOR_EDGE               = 'rgba(48,54,61,0.6)'
const COLOR_FILE_BORDER        = '#30363d'
const COLOR_LABEL              = '#7d8590'
const COLOR_DIR_BADGE_TEXT     = '#ffffff'

const FONT_LABEL     = "12px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
const FONT_DIR_BADGE = "bold 8px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
const FONT_DIR_COUNT = "8px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

function fileRadius(importance) {
  if (importance == null) return 8
  return Math.min(8 + importance * 1.5, 14)
}

function nodeRadius(node) {
  if (node.type === 'dir') return 18
  return fileRadius(node.importance)
}

function isPulsing(node, pulseMap) {
  if (!pulseMap) return false
  const expiry = pulseMap.get(node.id)
  return expiry !== undefined && expiry > Date.now()
}

/**
 * GraphCanvas renders the force-directed graph via react-force-graph.
 *
 * Props:
 *   fgRef            — forwarded ref from App.jsx, attached to ForceGraph2D
 *   graphData        — { nodes, links } already filtered for collapse
 *   staleMap         — Map<id, boolean>
 *   collapsedMap     — Map<id, boolean>
 *   selectedNodeId   — string | null
 *   onNodeClick      — (node) => void
 *   childCounts      — Map<id, number>
 *   pulseMap         — Map<id, expiry_timestamp>
 *   pulseAncestorIds — Set<id>
 */
export function GraphCanvas({
  fgRef,
  graphData,
  staleMap,
  collapsedMap,
  selectedNodeId,
  onNodeClick,
  childCounts,
  pulseMap = new Map(),
  pulseAncestorIds = new Set(),
}) {
  const containerRef = useRef(null)
  const [dims, setDims] = useState({ width: 0, height: 0 })

  useEffect(() => {
    if (!containerRef.current) return
    const ro = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      setDims({ width, height })
    })
    ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const r = nodeRadius(node)
    const isStale = staleMap.get(node.id) ?? !!node.stale
    const isDir = node.type === 'dir'
    const isCollapsed = collapsedMap.get(node.id) ?? true
    const isSelected = node.id === selectedNodeId
    const nodePulsing = isPulsing(node, pulseMap)

    // ── Step 1: fill pass ──────────────────────────────────────────────────────

    if (nodePulsing) {
      ctx.save()
      ctx.shadowColor = COLOR_NODE_PULSE
      ctx.shadowBlur = 14 / globalScale
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = COLOR_NODE_PULSE
      ctx.fill()
      ctx.restore()
    } else if (isDir) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = COLOR_NODE_DIR
      ctx.fill()
    } else if (isStale) {
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
      ctx.strokeStyle = COLOR_FILE_BORDER
      ctx.lineWidth = 1 / globalScale
      ctx.stroke()
    }

    // ── Step 2: pulse ancestor ring ────────────────────────────────────────────
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

    // ── Step 4: dir badge ──────────────────────────────────────────────────────
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

  const nodePointerAreaPaint = useCallback((node, color, ctx) => {
    const r = nodeRadius(node)
    ctx.beginPath()
    ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI)
    ctx.fillStyle = color
    ctx.fill()
  }, [])

  const linkColor = useCallback(() => COLOR_EDGE, [])
  const linkWidth = useCallback(() => 1, [])

  const handleNodeClick = useCallback((node) => {
    onNodeClick(node)
  }, [onNodeClick])

  return (
    <div
      ref={containerRef}
      style={{
        flex: 1,
        height: '100%',
        overflow: 'hidden',
        position: 'relative',
        background: COLOR_BG,
        backgroundImage: `linear-gradient(to right, rgba(230,237,243,0.03) 1px, transparent 1px),
                          linear-gradient(to bottom, rgba(230,237,243,0.03) 1px, transparent 1px)`,
        backgroundSize: '32px 32px',
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
        nodeLabel={() => ''}
        enableNodeDrag
        enableZoomInteraction
        enablePanInteraction
        width={dims.width || undefined}
        height={dims.height || undefined}
      />
    </div>
  )
}
