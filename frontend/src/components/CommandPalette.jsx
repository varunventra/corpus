import React, { useState, useEffect, useRef, useMemo } from 'react'
import ReactDOM from 'react-dom'
import { ImportanceFilter } from './ImportanceFilter.jsx'
import { lastName } from '../utils/path.js'

export function CommandPalette({
  nodes,
  importanceFilter,
  onImportanceChange,
  onSelect,
  onClose,
  fgRef,
}) {
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef(null)

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Reset active index when query changes
  useEffect(() => {
    setActiveIndex(0)
  }, [query])

  const { results, totalMatches } = useMemo(() => {
    if (!query.trim()) return { results: [], totalMatches: 0 }
    const q = query.toLowerCase()
    const allMatches = (nodes || []).filter(n => lastName(n.path).toLowerCase().includes(q))
    return {
      results: allMatches.slice(0, 8),
      totalMatches: allMatches.length,
    }
  }, [nodes, query])

  function handleSelect(node) {
    onSelect(node)
    if (fgRef && fgRef.current && node.x != null) {
      try {
        fgRef.current.centerAt(node.x, node.y, 600)
        const currentZoom = fgRef.current.zoom()
        if (currentZoom < 1) {
          fgRef.current.zoom(2.5, 600)
        }
      } catch (_) {
        // fgRef not ready — skip centering
      }
    }
    onClose()
  }

  function handleImportanceChange(level) {
    onImportanceChange(level)
    onClose()
  }

  function handleKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex(i => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      if (results[activeIndex]) {
        handleSelect(results[activeIndex])
      }
    } else if (e.key === 'Escape') {
      onClose()
    }
  }

  const isMac = typeof navigator !== 'undefined' && navigator.platform.includes('Mac')

  const content = (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 29,
          background: 'rgba(0,0,0,0.5)',
        }}
      />

      {/* Modal */}
      <div
        role="dialog"
        aria-label="Command palette"
        onKeyDown={handleKeyDown}
        style={{
          position: 'fixed',
          top: '20%',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 30,
          width: 'min(520px, 90vw)',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: '8px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
          overflow: 'hidden',
        }}
      >
        {/* Input row */}
        <div style={{
          padding: '0 16px',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <span style={{ color: 'var(--color-text-muted)', fontSize: '18px', flexShrink: 0 }}>⌕</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search files and folders..."
            aria-label="Search files and folders"
            aria-autocomplete="list"
            aria-controls="palette-results-list"
            style={{
              height: '48px',
              width: '100%',
              background: 'transparent',
              border: 'none',
              color: 'var(--color-text-primary)',
              fontFamily: 'var(--font-sans)',
              fontSize: 'var(--text-md)',
              outline: 'none',
              paddingLeft: '8px',
            }}
          />
        </div>

        {/* Results */}
        {results.length > 0 && (
          <div
            id="palette-results-list"
            role="listbox"
            style={{ maxHeight: '300px', overflowY: 'auto', padding: '4px 0' }}
          >
            {query && totalMatches > results.length && (
              <div style={{
                padding: '4px 16px',
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text-muted)',
              }}>
                Showing {results.length} of {totalMatches}
              </div>
            )}
            {results.map((node, i) => (
              <div
                key={node.id}
                role="option"
                aria-selected={i === activeIndex}
                onClick={() => handleSelect(node)}
                style={{
                  padding: '8px 16px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  background: i === activeIndex ? 'var(--color-surface-raised)' : 'transparent',
                  color: 'var(--color-text-primary)',
                }}
                onMouseEnter={() => setActiveIndex(i)}
              >
                <span style={{ width: 16, textAlign: 'center', flexShrink: 0 }}>
                  {node.type === 'dir'
                    ? <span style={{ color: '#a5d8ff' }}>📁</span>
                    : <span style={{ color: '#7c6af7' }}>◆</span>
                  }
                </span>
                <span style={{
                  fontFamily: 'var(--font-sans)',
                  fontSize: 'var(--text-base)',
                  color: 'var(--color-text-primary)',
                  fontWeight: 500,
                  flexShrink: 0,
                }}>
                  {lastName(node.path)}
                </span>
                {node.importance != null && (
                  <span style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-muted)',
                    flexShrink: 0,
                  }}>
                    {'·'.repeat(node.importance)}
                  </span>
                )}
                <span style={{
                  marginLeft: 'auto',
                  fontSize: 'var(--text-sm)',
                  color: 'var(--color-text-muted)',
                  maxWidth: '200px',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  direction: 'rtl',
                  flexShrink: 1,
                }}>
                  {node.path}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {query && results.length === 0 && (
          <div style={{
            padding: '32px 16px',
            textAlign: 'center',
            color: 'var(--color-text-muted)',
            fontSize: 'var(--text-base)',
          }}>
            No files match.
          </div>
        )}

        {/* Filter row */}
        <div style={{
          padding: '12px 16px',
          borderTop: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <ImportanceFilter value={importanceFilter} onChange={handleImportanceChange} />
        </div>
      </div>
    </>
  )

  return ReactDOM.createPortal(content, document.body)
}
