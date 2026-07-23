import React, { useCallback, useRef, useState, useEffect, useMemo } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { forceCollide, forceX, forceY } from 'd3-force-3d'
import { lastName } from '../utils/path.js'
import { seedHierarchyPositions } from '../lib/hierarchyLayout.js'
import { computeDegree, idOf } from '../lib/graphCuration.js'

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
const COLOR_LABEL_LEADER       = '#6e7681'
const COLOR_DIR_BADGE_TEXT     = '#ffffff'
const COLOR_DIR_COUNT_BG       = '#21262d'
const COLOR_DIR_COUNT_BORDER   = '#30363d'
const COLOR_DIR_COUNT_TEXT     = '#e6edf3'

const FONT_LABEL     = "12px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
const FONT_DIR_BADGE = "bold 8px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
const FONT_DIR_COUNT = "bold 8px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

const LABEL_MIN_ZOOM = 0.6
const LABEL_COLLISION_NODE_LIMIT = 150

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
  const graphDataRef = useRef(graphData)
  const [hover, setHover] = useState(null) // { node, x, y } | null

  useEffect(() => {
    if (!containerRef.current) return
    const ro = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      setDims({ width, height })
    })
    ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  // Keep a ref in sync so the per-frame label-collision pass and hover
  // handler always see the latest data without re-creating those callbacks
  // every render (which would fight the running force simulation).
  useEffect(() => {
    graphDataRef.current = graphData
  }, [graphData])

  // Degree map (in-links + out-links per node), recomputed only when the
  // link set actually changes. Feeds label priority (see nodeCanvasObject's
  // handleRenderFramePost) so well-connected file nodes win label position
  // over poorly-connected ones even when no LLM importance score exists.
  const degreeMap = useMemo(() => {
    if (!graphData) return new Map()
    const nodeIds = graphData.nodes.map(n => n.id)
    return computeDegree(nodeIds, graphData.links ?? [])
  }, [graphData])

  // Cheap content signature of the rendered dataset, used to gate zoomToFit
  // (see effect below) instead of the effect firing on every new graphData
  // object identity. Nodes/links that are only present because of a
  // temporary MCP pulse reveal (pulseMap / pulseAncestorIds) are excluded —
  // a pulse starting or ending must never recenter the camera on its own.
  const graphSignature = useMemo(() => {
    if (!graphData) return ''
    const excluded = new Set([...pulseMap.keys(), ...pulseAncestorIds])
    const ids = graphData.nodes
      .map(n => n.id)
      .filter(id => !excluded.has(id))
      .sort()
    const linkCount = (graphData.links ?? []).filter(l => {
      const s = idOf(l.source)
      const t = idOf(l.target)
      return !excluded.has(s) && !excluded.has(t)
    }).length
    return `${ids.join(',')}|${linkCount}`
  }, [graphData, pulseMap, pulseAncestorIds])

  const lastZoomSignatureRef = useRef(null)

  // ── d3-hierarchy seed + force retune ────────────────────────────────────────
  // Seeds folder-keyed initial positions (large graphs only — see
  // hierarchyLayout.js), then retunes charge/collision/link-distance.
  // zoomToFit itself only fires when graphSignature actually changes — i.e.
  // on initial load, mode-switch, or a real filter/node-set change — not on
  // every dims/graphData object-identity churn (DocReader open/close resizes,
  // MCP pulse start/end ticks). See Phase 9 fix-review MAJOR finding.
  useEffect(() => {
    if (!fgRef?.current || !graphData) return

    seedHierarchyPositions(graphData.nodes, { width: dims.width, height: dims.height })

    const fg = fgRef.current
    const chargeForce = fg.d3Force('charge')
    if (chargeForce) chargeForce.strength(-220)

    const linkForce = fg.d3Force('link')
    if (linkForce) linkForce.distance(70)

    fg.d3Force('collide', forceCollide(node => nodeRadius(node) + 6))

    // Weak constant centering pull so disconnected nodes/components (no
    // edges to be reeled in by the link force) don't drift arbitrarily far
    // under charge/repulsion alone — they'd otherwise force zoomToFit to
    // zoom out drastically, shrinking the main connected cluster. Strength
    // is intentionally small so it doesn't fight or compress the existing
    // link-driven layout of the main cluster, only nudges isolated nodes
    // back toward center over a few seconds.
    fg.d3Force('x', forceX(dims.width / 2).strength(0.02))
    fg.d3Force('y', forceY(dims.height / 2).strength(0.02))

    fg.d3ReheatSimulation()

    if (lastZoomSignatureRef.current === graphSignature) return
    lastZoomSignatureRef.current = graphSignature

    const id = setTimeout(() => fg.zoomToFit(400, 60), 350)
    return () => clearTimeout(id)
  }, [graphData, graphSignature, dims.width, dims.height])

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

    // ── Step 4: dir badge — centered arrow (affordance) + separate satellite
    //            count badge lower-right (legibility fix, Phase 9 §6) ──────────
    if (isDir && isCollapsed) {
      ctx.fillStyle = COLOR_DIR_BADGE_TEXT
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.font = FONT_DIR_BADGE
      ctx.fillText('▶', node.x, node.y)

      const count = childCounts.get(node.id) ?? 0
      if (count > 0) {
        const bx = node.x + r * 0.72
        const by = node.y + r * 0.72
        ctx.beginPath()
        ctx.arc(bx, by, 7, 0, 2 * Math.PI)
        ctx.fillStyle = COLOR_DIR_COUNT_BG
        ctx.fill()
        ctx.strokeStyle = COLOR_DIR_COUNT_BORDER
        ctx.lineWidth = 1 / globalScale
        ctx.stroke()

        ctx.fillStyle = COLOR_DIR_COUNT_TEXT
        ctx.font = FONT_DIR_COUNT
        ctx.fillText(String(count), bx, by + 0.5)
      }
    }

    // Labels are drawn in a single collision-avoidance pass after all nodes
    // are painted — see handleRenderFramePost below (Phase 9 §5).
  }, [staleMap, collapsedMap, selectedNodeId, childCounts, pulseMap, pulseAncestorIds])

  // ── Label collision-avoidance pass (Phase 9 §5) ─────────────────────────────
  // Runs once per frame after all nodes are drawn. Below LABEL_MIN_ZOOM,
  // nothing is drawn. Above LABEL_COLLISION_NODE_LIMIT visible nodes, the
  // pass (and labels entirely) is skipped as a perf guard — Overview mode
  // is always well under this ceiling; only huge All-Files graphs hit it.
  const handleRenderFramePost = useCallback((ctx, globalScale) => {
    if (globalScale < LABEL_MIN_ZOOM) return

    const nodes = graphDataRef.current?.nodes ?? []
    if (nodes.length === 0 || nodes.length > LABEL_COLLISION_NODE_LIMIT) return

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
        x: node.x, y: node.y + r + 6,
        w, h,
        priority: node.type === 'dir' ? Infinity : (node.importance ?? 0) * 10 + (degreeMap.get(node.id) ?? 0),
        hidden: false,
      })
    }

    // 2. Higher-priority labels claim their ideal position first.
    boxes.sort((a, b) => b.priority - a.priority)

    // 3. Pairwise AABB collision check against already-placed boxes.
    const placed = []
    for (const box of boxes) {
      let attempt = 0
      const maxAttempts = 4
      while (attempt <= maxAttempts) {
        const candidateY = box.idealY + attempt * 10
        const overlaps = placed.some(p =>
          Math.abs(box.idealX - p.x) < (box.w + p.w) / 2 + 4 &&
          Math.abs(candidateY - p.y) < (box.h + p.h) / 2 + 2
        )
        if (!overlaps) { box.y = candidateY; break }
        attempt++
      }
      if (attempt > maxAttempts) { box.hidden = true; continue }
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
        ctx.strokeStyle = COLOR_LABEL_LEADER
        ctx.lineWidth = 1 / globalScale
        ctx.stroke()
      }
      ctx.font = FONT_LABEL
      ctx.fillStyle = COLOR_LABEL
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillText(box.label, box.x, box.y)
    }
  }, [degreeMap])

  // ── Hover tooltip — safety valve independent of the zoom threshold ──────────
  const handleNodeHover = useCallback((node) => {
    if (!node || !fgRef?.current) { setHover(null); return }
    const screen = fgRef.current.graph2ScreenCoords(node.x, node.y)
    setHover({ node, x: screen.x, y: screen.y })
  }, [fgRef])

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

  const tooltipText = hover
    ? (hover.node.type === 'dir'
        ? `${childCounts.get(hover.node.id) ?? 0} files inside`
        : lastName(hover.node.path))
    : null

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
        onRenderFramePost={handleRenderFramePost}
        linkColor={linkColor}
        linkWidth={linkWidth}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        nodeLabel={() => ''}
        enableNodeDrag
        enableZoomInteraction
        enablePanInteraction
        width={dims.width || undefined}
        height={dims.height || undefined}
      />
      {tooltipText && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            left: hover.x + 12,
            top: hover.y - 8,
            zIndex: 20,
            pointerEvents: 'none',
            background: 'rgba(22,27,34,0.95)',
            border: '1px solid var(--color-border)',
            borderRadius: 6,
            padding: '4px 8px',
            fontFamily: 'var(--font-body)',
            fontSize: 12,
            color: 'var(--color-text-primary)',
            whiteSpace: 'nowrap',
          }}
        >
          {tooltipText}
        </div>
      )}
    </div>
  )
}
