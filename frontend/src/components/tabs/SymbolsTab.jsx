import React, { useMemo, useState } from 'react'
import { lastName } from '../../utils/path.js'

function kindBadgeStyle(kind) {
  const k = (kind || '').toUpperCase()
  if (k === 'CLASS') return { background: 'var(--color-accent-dim)', color: 'var(--color-accent)' }
  if (k === 'FUNCTION') return { background: 'var(--color-surface-high)', color: 'var(--color-text-secondary)' }
  return { background: 'none', border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }
}

export function SymbolsTab({ nodes, onNodeSelect }) {
  const [query, setQuery] = useState('')

  const allSymbols = useMemo(() => {
    if (!nodes) return []
    const result = []
    for (const node of nodes) {
      if (!node.symbols || node.type !== 'file') continue
      for (const sym of node.symbols) {
        result.push({
          name: sym.name,
          kind: (sym.kind || 'SYMBOL').toUpperCase(),
          filePath: node.path,
          fileName: lastName(node.path),
          nodeId: node.id,
          node,
        })
      }
    }
    result.sort((a, b) => a.name.localeCompare(b.name))
    return result
  }, [nodes])

  const filtered = allSymbols.filter(s => s.name.toLowerCase().includes(query.toLowerCase()))
  const visible = filtered.slice(0, 500)

  if (allSymbols.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '32px 48px' }}>
        <div style={{ padding: 48, textAlign: 'center' }}>
          <p style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--color-text-muted)' }}>
            No symbols indexed yet. Run <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--color-surface-high)', padding: '2px 6px', borderRadius: 4 }}>corpus update</code> to index symbols.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--color-border)', flexShrink: 0 }}>
        <input
          type="text"
          aria-label="Filter symbols"
          placeholder="Filter symbols..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          style={{
            padding: '10px 16px',
            border: '1px solid var(--color-border)',
            borderRadius: 8,
            fontFamily: 'var(--font-body)',
            fontSize: 14,
            color: 'var(--color-text-primary)',
            background: 'var(--color-surface-white)',
            width: '100%',
            boxSizing: 'border-box',
            outline: 'none',
          }}
          onFocus={e => { e.target.style.borderColor = 'var(--color-accent)'; e.target.style.boxShadow = '0 0 0 1px var(--color-accent)' }}
          onBlur={e => { e.target.style.borderColor = 'var(--color-border)'; e.target.style.boxShadow = 'none' }}
        />
        {allSymbols.length > 500 && (
          <div style={{ marginTop: 8, padding: '8px 16px', background: 'var(--color-accent-dim)', color: 'var(--color-accent)', fontFamily: 'var(--font-body)', fontSize: 12, borderRadius: 6 }}>
            {allSymbols.length} symbols — showing first 500. Use search to narrow results.
          </div>
        )}
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--color-surface-low)', position: 'sticky', top: 0, zIndex: 2 }}>
              <th style={{ fontFamily: 'var(--font-body)', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-muted)', padding: '8px 16px', textAlign: 'left' }}>Name</th>
              <th style={{ fontFamily: 'var(--font-body)', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-muted)', padding: '8px 16px', textAlign: 'left' }}>Kind</th>
              <th style={{ fontFamily: 'var(--font-body)', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-muted)', padding: '8px 16px', textAlign: 'left' }}>File</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td colSpan={3} style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--color-text-muted)', fontFamily: 'var(--font-body)', fontSize: 13 }}>
                  No symbols match "{query}".
                </td>
              </tr>
            ) : visible.map((s, i) => (
              <tr
                key={`${s.nodeId}-${s.name}-${i}`}
                onClick={() => onNodeSelect(s.node)}
                style={{ cursor: 'pointer', borderBottom: '1px solid var(--color-border)' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--color-surface-low)'}
                onMouseLeave={e => e.currentTarget.style.background = 'none'}
              >
                <td style={{ padding: '10px 16px', fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-primary)', fontWeight: 500 }}>{s.name}</td>
                <td style={{ padding: '10px 16px' }}>
                  <span style={{
                    ...kindBadgeStyle(s.kind),
                    fontFamily: 'var(--font-body)',
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '2px 6px',
                    borderRadius: 4,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    whiteSpace: 'nowrap',
                  }}>{s.kind}</span>
                </td>
                <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-text-muted)' }} title={s.filePath}>
                  {s.fileName}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
