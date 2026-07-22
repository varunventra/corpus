import React from 'react'
import { GraphCanvas } from '../GraphCanvas.jsx'

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
      background: 'rgba(250,245,238,0.92)',
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
      background: 'rgba(250,245,238,0.92)',
      border: '1px solid var(--color-border)',
      borderRadius: 6,
      pointerEvents: 'none',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#ffffff', border: '1px solid #d8d0c8' }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Fresh</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b' }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Stale</span>
      </div>
      <div style={{ width: 1, height: 12, background: 'var(--color-border)' }} />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
        {`Nodes: ${graphData.nodes?.length ?? 0} | Edges: ${(graphData.links ?? []).length}`}
      </span>
    </div>
  )
}

export function ExplorerTab({ graphData, staleMap, collapsedMap, selectedNodeId, onNodeClick, childCounts, pulseMap, pulseAncestorIds, fgRef }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
      <GraphCanvas
        fgRef={fgRef}
        graphData={graphData}
        staleMap={staleMap}
        collapsedMap={collapsedMap}
        selectedNodeId={selectedNodeId}
        onNodeClick={onNodeClick}
        childCounts={childCounts}
        pulseMap={pulseMap}
        pulseAncestorIds={pulseAncestorIds}
      />
      <ZoomControls fgRef={fgRef} />
      <StatsBar graphData={graphData} />
    </div>
  )
}
