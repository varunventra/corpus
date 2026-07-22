import React, { useRef, useEffect } from 'react'

export function Minimap({ graphData, staleMap, fgRef }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    function drawMinimap() {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      const W = 160
      const H = 120

      // Clear
      ctx.clearRect(0, 0, W, H)
      ctx.fillStyle = '#0d1117'
      ctx.fillRect(0, 0, W, H)

      const nodes = (graphData.nodes || []).filter(n => n.x != null)
      if (nodes.length === 0) return

      // Find bounding box
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
      for (const n of nodes) {
        if (n.x < minX) minX = n.x
        if (n.x > maxX) maxX = n.x
        if (n.y < minY) minY = n.y
        if (n.y > maxY) maxY = n.y
      }

      // Add 10% padding around bounds
      const padX = (maxX - minX) * 0.1 || 10
      const padY = (maxY - minY) * 0.1 || 10
      minX -= padX; maxX += padX
      minY -= padY; maxY += padY

      const scaleX = W / (maxX - minX)
      const scaleY = H / (maxY - minY)
      const scale = Math.min(scaleX, scaleY)

      // Center the scaled graph in the canvas
      const offsetX = (W - (maxX - minX) * scale) / 2
      const offsetY = (H - (maxY - minY) * scale) / 2

      function toMiniX(x) { return (x - minX) * scale + offsetX }
      function toMiniY(y) { return (y - minY) * scale + offsetY }

      // Draw nodes as dots
      for (const n of nodes) {
        const isStale = (staleMap && staleMap.get(n.id)) ?? !!n.stale
        const dotColor = n.type === 'dir'
          ? '#a5d8ff'
          : (isStale ? '#e3b341' : '#7c6af7')
        const dotRadius = n.type === 'dir' ? 3 : 2

        ctx.beginPath()
        ctx.arc(toMiniX(n.x), toMiniY(n.y), dotRadius, 0, 2 * Math.PI)
        ctx.fillStyle = dotColor
        ctx.fill()
      }

      // Draw viewport rectangle
      if (fgRef && fgRef.current) {
        try {
          const center = fgRef.current.centerAt()
          const zoom = fgRef.current.zoom()
          const vpW = window.innerWidth / zoom
          const vpH = window.innerHeight / zoom

          const vx1 = toMiniX(center.x - vpW / 2)
          const vy1 = toMiniY(center.y - vpH / 2)
          const vx2 = toMiniX(center.x + vpW / 2)
          const vy2 = toMiniY(center.y + vpH / 2)

          ctx.strokeStyle = 'rgba(255,255,255,0.3)'
          ctx.lineWidth = 1
          ctx.strokeRect(vx1, vy1, vx2 - vx1, vy2 - vy1)
        } catch (_) {
          // fgRef not ready — skip viewport rect
        }
      }
    }

    drawMinimap()
    const id = setInterval(drawMinimap, 1000)
    return () => clearInterval(id)
  // fgRef is a stable object reference; fgRef.current will be populated
  // by the time the first interval fires (1000ms after mount). The try/catch
  // in drawMinimap handles the case where it is not yet ready.
  }, [graphData, staleMap])

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 16,
        right: 16,
        width: 160,
        height: 120,
        border: '1px solid var(--color-border)',
        borderRadius: 6,
        overflow: 'hidden',
        zIndex: 10,
        pointerEvents: 'none',
      }}
    >
      <canvas ref={canvasRef} width={160} height={120} />
    </div>
  )
}
