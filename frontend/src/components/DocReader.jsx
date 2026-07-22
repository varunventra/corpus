import React, { useMemo, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { useDoc } from '../hooks/useDoc.js'
import { lastName } from '../utils/path.js'

function typeLabel(node) {
  if (!node) return ''
  if (node.type === 'dir') return 'Directory'
  const ext = (node.path || '').split('.').pop().toLowerCase()
  const map = {
    py: 'Python Module', js: 'JavaScript Module', jsx: 'React Component',
    ts: 'TypeScript Module', tsx: 'React Component', md: 'Markdown',
    json: 'JSON', css: 'Stylesheet', html: 'HTML',
    rs: 'Rust Module', go: 'Go Module',
  }
  return map[ext] || 'File'
}

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

export function DocReader({ node, isOpen, onClose, nodes, edges, staleMap, onNodeSelect, repoRoot }) {
  const isStale = node ? (staleMap?.get(node.id) ?? !!node.stale) : false
  const hasDoc = !!node
  const { content, loading, error, retry } = useDoc(isOpen && node ? node.path : null)

  useEffect(() => {
    if (!isOpen) return
    function handleKeyDown(e) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  const outgoingDeps = useMemo(() => {
    if (!edges || !node) return []
    const nodeById = new Map((nodes || []).map(n => [n.id, n]))
    return edges
      .filter(e => (e.source?.id ?? e.source) === node.id)
      .map(e => nodeById.get(e.target?.id ?? e.target))
      .filter(Boolean)
  }, [edges, nodes, node])

  const backlinks = useMemo(() => {
    if (!edges || !node) return []
    const nodeById = new Map((nodes || []).map(n => [n.id, n]))
    return edges
      .filter(e => (e.target?.id ?? e.target) === node.id)
      .map(e => nodeById.get(e.source?.id ?? e.source))
      .filter(Boolean)
  }, [edges, nodes, node])

  const segments = useMemo(() => {
    if (!node) return []
    const parts = node.path.split('/')
    const byPath = new Map((nodes || []).map(n => [n.path, n]))
    return parts.map((label, i) => {
      const segPath = parts.slice(0, i + 1).join('/')
      return { label, path: segPath, node: byPath.get(segPath) ?? null }
    })
  }, [node, nodes])

  const sectionHeadingStyle = {
    fontFamily: 'var(--font-headline)',
    fontSize: 18,
    fontWeight: 600,
    color: 'var(--color-text-primary)',
    borderBottom: '1px solid var(--color-border)',
    paddingBottom: 8,
    marginBottom: 16,
    marginTop: 0,
  }

  return (
    <div style={{
      width: isOpen ? 450 : 0,
      flexShrink: 0,
      overflow: 'hidden',
      transition: 'width 220ms cubic-bezier(0.4, 0, 0.2, 1)',
      borderLeft: isOpen ? '1px solid var(--color-border)' : 'none',
    }}>
      <div style={{
        width: 450,
        height: '100%',
        background: 'var(--color-surface-white)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 24px 16px',
          borderBottom: '1px solid var(--color-border)',
          background: 'var(--color-canvas-overlay)',
          flexShrink: 0,
        }}>
          {/* Row 1: type badge + buttons */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 18, color: 'var(--color-accent)' }}>
                {node?.type === 'dir' ? 'folder' : 'description'}
              </span>
              <span style={{ fontFamily: 'var(--font-body)', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-accent)' }}>
                {typeLabel(node)}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <button
                aria-label="Open in editor"
                onClick={() => { if (repoRoot && node) window.open(`vscode://file/${repoRoot.replace(/\\/g, '/')}/${node.path.replace(/\\/g, '/')}`) }}
                disabled={!repoRoot || !node}
                title={repoRoot ? `Open ${node?.path} in VS Code` : 'repoRoot not available — corpus serve needed'}
                style={{
                  width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: 'none', border: 'none', borderRadius: 6,
                  cursor: repoRoot ? 'pointer' : 'not-allowed',
                  color: repoRoot ? 'var(--color-text-secondary)' : 'var(--color-text-muted)',
                }}
              >
                <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 16 }}>edit</span>
              </button>
              <button
                aria-label="Close doc reader"
                onClick={onClose}
                style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', borderRadius: 6, cursor: 'pointer', color: 'var(--color-text-secondary)' }}
                onMouseEnter={e => e.currentTarget.style.color = 'var(--color-text-primary)'}
                onMouseLeave={e => e.currentTarget.style.color = 'var(--color-text-secondary)'}
              >
                <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 18 }}>close</span>
              </button>
            </div>
          </div>

          {/* Filename */}
          <h2 style={{ fontFamily: 'var(--font-headline)', fontSize: 28, fontWeight: 700, color: 'var(--color-text-primary)', lineHeight: 1.1, margin: '0 0 6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {node ? lastName(node.path) : ''}
          </h2>

          {/* Breadcrumb */}
          <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'nowrap', overflow: 'hidden', gap: 4, marginBottom: 4 }}>
            {segments.map((seg, i) => {
              const isLast = i === segments.length - 1
              const isClickable = !isLast && seg.node !== null
              return (
                <React.Fragment key={seg.path}>
                  {i > 0 && <span style={{ color: 'var(--color-text-muted)', flexShrink: 0, padding: '0 2px' }}>/</span>}
                  <span
                    onClick={isClickable ? () => onNodeSelect(seg.node) : undefined}
                    style={{
                      color: isLast ? 'var(--color-accent)' : 'var(--color-text-muted)',
                      fontFamily: 'var(--font-body)', fontSize: 12,
                      fontWeight: isLast ? 600 : 400,
                      cursor: isClickable ? 'pointer' : 'default',
                      maxWidth: isLast ? '180px' : '80px',
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flexShrink: isLast ? 1 : 0,
                    }}
                    onMouseEnter={isClickable ? e => { e.currentTarget.style.color = 'var(--color-text-primary)' } : undefined}
                    onMouseLeave={isClickable ? e => { e.currentTarget.style.color = 'var(--color-text-muted)' } : undefined}
                  >{seg.label}</span>
                </React.Fragment>
              )
            })}
          </div>

          {/* Staleness line */}
          <p style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
            <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 14 }}>history</span>
            {isStale ? 'Documentation may be outdated' : 'Documentation up to date'}
          </p>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {/* Stale warning */}
          {isStale && (
            <div style={{
              margin: '16px 24px 0',
              padding: '12px 16px',
              background: 'var(--color-stale-badge-bg)',
              border: '1px solid var(--color-stale-badge-border)',
              borderRadius: 8,
              display: 'flex', gap: 12, alignItems: 'flex-start',
            }}>
              <span className="material-symbols-outlined" aria-hidden="true" style={{ color: 'var(--color-stale-badge-text)', fontSize: 20, marginTop: 1, flexShrink: 0 }}>warning</span>
              <div>
                <h4 style={{ fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 700, color: 'var(--color-stale-badge-text)', margin: '0 0 4px' }}>Documentation Stale</h4>
                <p style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--color-stale-badge-text)', margin: 0, lineHeight: 1.5 }}>
                  Source code has changed significantly since this documentation was generated. Review recommended.
                </p>
              </div>
            </div>
          )}

          {/* Doc content */}
          <div style={{ padding: '24px 24px 0' }}>
            {!node && null}
            {node && !hasDoc && (
              <p style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)' }}>
                No documentation generated yet. Run <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--color-surface-high)', padding: '2px 5px', borderRadius: 3 }}>corpus update</code> to generate docs.
              </p>
            )}
            {node && hasDoc && loading && (
              <p style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)' }}>Loading documentation...</p>
            )}
            {node && hasDoc && error && (
              <div>
                <p style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)' }}>Could not load this file's doc.</p>
                <button onClick={retry} style={{ marginTop: 8, padding: '6px 12px', border: '1px solid var(--color-border)', borderRadius: 6, fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-secondary)', cursor: 'pointer', background: 'var(--color-surface-low)' }}>Retry</button>
              </div>
            )}
            {node && hasDoc && !loading && !error && content && (
              <ReactMarkdown components={mdComponents}>{content}</ReactMarkdown>
            )}
          </div>

          {/* Key Symbols */}
          {node?.symbols && node.symbols.length > 0 && (
            <div style={{ padding: '0 24px', marginTop: 24 }}>
              <h3 style={sectionHeadingStyle}>Key Symbols</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {node.symbols.map(sym => (
                  <div key={sym.name} style={{ padding: '14px 16px', background: 'var(--color-surface)', borderRadius: 8, border: '1px solid var(--color-border)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: sym.description ? 6 : 0 }}>
                      <span style={{
                        background: sym.kind?.toUpperCase() === 'CLASS' ? 'var(--color-accent-dim)' : 'rgba(125,133,144,0.08)',
                        color: sym.kind?.toUpperCase() === 'CLASS' ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                        fontFamily: 'var(--font-body)', fontSize: 10, fontWeight: 700,
                        padding: '2px 8px', borderRadius: 4, textTransform: 'uppercase', letterSpacing: '0.06em',
                      }}>{sym.kind || 'SYMBOL'}</span>
                      <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)' }}>{sym.name}</span>
                    </div>
                    {sym.description && (
                      <p style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-secondary)', margin: 0, lineHeight: 1.6 }}>{sym.description}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Dependencies */}
          {outgoingDeps.length > 0 && (
            <div style={{ padding: '0 24px', marginTop: 24 }}>
              <h3 style={sectionHeadingStyle}>Dependencies</h3>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {outgoingDeps.map(dep => (
                  <li key={dep.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 14, color: 'var(--color-text-muted)' }}>arrow_forward</span>
                    <button
                      onClick={() => onNodeSelect(dep)}
                      style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-accent)' }}
                      onMouseEnter={e => e.currentTarget.style.textDecoration = 'underline'}
                      onMouseLeave={e => e.currentTarget.style.textDecoration = 'none'}
                    >{lastName(dep.path)}</button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Backlinks */}
          {backlinks.length > 0 && (
            <div style={{ padding: '0 24px', marginTop: 24 }}>
              <h3 style={sectionHeadingStyle}>Imported by</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {backlinks.map(bl => (
                  <button
                    key={bl.id}
                    onClick={() => onNodeSelect(bl)}
                    style={{
                      fontFamily: 'var(--font-body)', fontSize: 12,
                      padding: '4px 10px',
                      background: 'var(--color-surface-container)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 4, color: 'var(--color-text-secondary)', cursor: 'pointer',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--color-accent)'; e.currentTarget.style.color = 'var(--color-accent)' }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text-secondary)' }}
                  >{lastName(bl.path)}</button>
                ))}
              </div>
            </div>
          )}

          {/* Open in Editor */}
          <div style={{ padding: '24px', paddingTop: 24 }}>
            <a
              href={repoRoot && node ? `vscode://file/${repoRoot.replace(/\\/g, '/')}/${node.path.replace(/\\/g, '/')}` : undefined}
              onClick={e => { if (!repoRoot || !node) e.preventDefault() }}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                width: '100%', padding: '10px 0',
                background: 'var(--color-surface)', color: 'var(--color-accent)',
                border: '1px solid rgba(68,147,248,0.30)', borderRadius: 8,
                fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600,
                textDecoration: 'none',
                cursor: repoRoot && node ? 'pointer' : 'not-allowed',
                opacity: repoRoot && node ? 1 : 0.5,
                transition: 'background 120ms',
              }}
              onMouseEnter={e => { if (repoRoot && node) e.currentTarget.style.background = 'rgba(68,147,248,0.08)' }}
              onMouseLeave={e => e.currentTarget.style.background = 'var(--color-surface)'}
              title={!repoRoot ? 'repoRoot not available — start corpus serve to enable this' : undefined}
            >
              <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 16 }}>open_in_new</span>
              Open in Editor
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
