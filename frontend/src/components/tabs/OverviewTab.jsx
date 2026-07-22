import React, { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { useDoc } from '../../hooks/useDoc.js'
import { lastName } from '../../utils/path.js'

const mdComponents = {
  h1: ({ children }) => <h1 style={{ fontFamily: 'var(--font-headline)', fontSize: 20, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 12, marginTop: 0 }}>{children}</h1>,
  h2: ({ children }) => <h2 style={{ fontFamily: 'var(--font-headline)', fontSize: 16, fontWeight: 600, color: 'var(--color-text-primary)', borderBottom: '1px solid var(--color-border)', paddingBottom: 4, marginBottom: 8, marginTop: 24 }}>{children}</h2>,
  h3: ({ children }) => <h3 style={{ fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: 8, marginTop: 16 }}>{children}</h3>,
  p: ({ children }) => <p style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--color-text-secondary)', lineHeight: 1.7, marginBottom: 12 }}>{children}</p>,
  code: ({ inline, children }) => inline
    ? <code style={{ fontFamily: 'var(--font-mono)', fontSize: 12, background: 'var(--color-surface-high)', padding: '2px 5px', borderRadius: 3, color: 'var(--color-accent)' }}>{children}</code>
    : <code style={{ fontFamily: 'var(--font-mono)', fontSize: 12, display: 'block', background: 'var(--color-surface-high)', borderRadius: 6, padding: '12px 16px', color: 'var(--color-text-secondary)', overflowX: 'auto', borderLeft: '3px solid var(--color-accent)' }}>{children}</code>,
  a: ({ href, children }) => <a href={href} style={{ color: 'var(--color-accent)', textDecoration: 'none' }} onMouseEnter={e => e.currentTarget.style.textDecoration = 'underline'} onMouseLeave={e => e.currentTarget.style.textDecoration = 'none'}>{children}</a>,
  ul: ({ children }) => <ul style={{ paddingLeft: 20, listStyle: 'disc', color: 'var(--color-text-secondary)', marginBottom: 12 }}>{children}</ul>,
  li: ({ children }) => <li style={{ fontFamily: 'var(--font-body)', fontSize: 14, lineHeight: 1.7 }}>{children}</li>,
}

function NodeRow({ node, section, degreeMap, onNodeSelect }) {
  return (
    <div
      onClick={() => onNodeSelect(node)}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 16px',
        background: 'var(--color-surface-white)',
        border: '1px solid var(--color-border)',
        borderRadius: 8,
        cursor: 'pointer',
        marginBottom: 6,
        transition: 'border-color 120ms',
      }}
      onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--color-accent)'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--color-border)'}
    >
      {section === 'stale' && <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-node-stale)', flexShrink: 0 }} />}
      <span style={{ fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', flex: 1 }}>
        {lastName(node.path)}
      </span>
      {section === 'important' && node.importance != null && (
        <span style={{ background: 'var(--color-accent-dim)', color: 'var(--color-accent)', fontFamily: 'var(--font-body)', fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4 }}>
          {node.importance}
        </span>
      )}
      {section === 'connected' && degreeMap && (
        <span style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
          {degreeMap.get(node.id) ?? 0} edges
        </span>
      )}
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }}>
        {node.path}
      </span>
    </div>
  )
}

export function OverviewTab({ nodes, edges, graphData, staleMap, onNodeSelect }) {
  const rootDirNode = useMemo(() => nodes.find(n => n.type === 'dir' && !n.path.includes('/')), [nodes])
  const { content: rootDocContent, loading: rootDocLoading } = useDoc(rootDirNode?.path ?? null)

  const { fileCount, dirCount, edgeCount, staleCount, degreeMap, mostImportant, mostConnected, staleFiles } = useMemo(() => {
    const fileNodes = nodes.filter(n => n.type === 'file')
    const dirNodes = nodes.filter(n => n.type === 'dir')
    const staleFiles = nodes.filter(n => staleMap.get(n.id) === true)
    const edgeCount = edges ? edges.length : 0

    const degreeMap = new Map()
    if (edges) {
      for (const e of edges) {
        const srcId = e.source?.id ?? e.source
        const tgtId = e.target?.id ?? e.target
        degreeMap.set(srcId, (degreeMap.get(srcId) ?? 0) + 1)
        degreeMap.set(tgtId, (degreeMap.get(tgtId) ?? 0) + 1)
      }
    }

    const mostImportant = [...fileNodes]
      .filter(n => n.importance != null)
      .sort((a, b) => b.importance - a.importance)
      .slice(0, 5)

    const mostConnected = [...fileNodes]
      .sort((a, b) => (degreeMap.get(b.id) ?? 0) - (degreeMap.get(a.id) ?? 0))
      .slice(0, 5)

    return {
      fileCount: fileNodes.length,
      dirCount: dirNodes.length,
      edgeCount,
      staleCount: staleFiles.length,
      degreeMap,
      mostImportant,
      mostConnected,
      staleFiles,
    }
  }, [nodes, edges, staleMap])

  const sectionHeadingStyle = {
    fontFamily: 'var(--font-headline)',
    fontSize: 22,
    fontWeight: 600,
    color: 'var(--color-text-primary)',
    marginBottom: 16,
    borderBottom: '1px solid var(--color-border)',
    paddingBottom: 8,
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', height: '100%' }}>
      <div style={{ padding: '32px 48px', maxWidth: 900, margin: '0 auto' }}>

        {/* Stat chips */}
        <div style={{ display: 'flex', gap: 16, marginBottom: 48 }}>
          {[
            { count: fileCount, label: 'Files' },
            { count: dirCount, label: 'Directories' },
            { count: edgeCount, label: 'Edges' },
            { count: staleCount, label: 'Stale' },
          ].map(({ count, label }) => (
            <div key={label} style={{
              flex: 1, background: 'var(--color-surface-white)',
              border: '1px solid var(--color-border)', borderRadius: 8,
              padding: '24px 20px', display: 'flex', flexDirection: 'column', gap: 4,
            }}>
              <span style={{ fontFamily: 'var(--font-headline)', fontSize: 36, fontWeight: 700, color: 'var(--color-accent)', lineHeight: 1 }}>{count}</span>
              <span style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
            </div>
          ))}
        </div>

        {/* About this project */}
        {rootDirNode && (
          <div style={{ marginBottom: 48 }}>
            <h2 style={sectionHeadingStyle}>About this Project</h2>
            {rootDocLoading && <p style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--color-text-muted)' }}>Loading project summary...</p>}
            {!rootDocLoading && rootDocContent && <ReactMarkdown components={mdComponents}>{rootDocContent}</ReactMarkdown>}
            {!rootDocLoading && !rootDocContent && <p style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--color-text-muted)', fontStyle: 'italic' }}>No project doc found.</p>}
          </div>
        )}

        {/* Three columns */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 32 }}>
          <div>
            <h2 style={sectionHeadingStyle}>Most Important</h2>
            {mostImportant.length === 0 ? (
              <p style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)', fontStyle: 'italic' }}>—</p>
            ) : mostImportant.map(n => (
              <NodeRow key={n.id} node={n} section="important" onNodeSelect={onNodeSelect} />
            ))}
          </div>
          <div>
            <h2 style={sectionHeadingStyle}>Most Connected</h2>
            {mostConnected.map(n => (
              <NodeRow key={n.id} node={n} section="connected" degreeMap={degreeMap} onNodeSelect={onNodeSelect} />
            ))}
          </div>
          <div>
            <h2 style={sectionHeadingStyle}>Stale Files</h2>
            {staleFiles.length === 0 ? (
              <p style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)', fontStyle: 'italic' }}>All files are up to date.</p>
            ) : staleFiles.map(n => (
              <NodeRow key={n.id} node={n} section="stale" onNodeSelect={onNodeSelect} />
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}
