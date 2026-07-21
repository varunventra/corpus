import React from 'react'
import ReactMarkdown from 'react-markdown'
import { useDoc } from '../hooks/useDoc.js'

const PANEL_WIDTH = 420

const retryBtnStyle = {
  fontFamily: 'var(--font-sans)',
  fontSize: 'var(--text-sm)',
  height: '30px',
  minHeight: '36px',
  border: '1px solid var(--color-border)',
  borderRadius: '5px',
  padding: '0 12px',
  background: 'var(--color-surface-raised)',
  color: 'var(--color-text-muted)',
  cursor: 'pointer',
  marginTop: '8px',
  display: 'inline-flex',
  alignItems: 'center',
}

const mdComponents = {
  h1: ({ children }) => (
    <h1 style={{
      fontFamily: 'var(--font-sans)',
      fontSize: '16px',
      fontWeight: 700,
      color: 'var(--color-text-primary)',
      marginBottom: '12px',
      marginTop: 0,
    }}>{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 style={{
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-base)',
      fontWeight: 600,
      textTransform: 'uppercase',
      letterSpacing: '0.07em',
      color: '#555555',
      borderBottom: '1px solid var(--color-border)',
      paddingBottom: '4px',
      marginBottom: '10px',
      marginTop: '20px',
    }}>{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 style={{
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-base)',
      fontWeight: 600,
      color: 'var(--color-text-secondary)',
      marginBottom: '8px',
      marginTop: '16px',
    }}>{children}</h3>
  ),
  p: ({ children }) => (
    <p style={{
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-md)',
      color: 'var(--color-text-secondary)',
      lineHeight: '1.7',
      marginBottom: '12px',
    }}>{children}</p>
  ),
  code: ({ inline, children }) => (
    inline
      ? <code style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '12.5px',
          background: '#f0f0f0',
          borderRadius: '3px',
          padding: '2px 5px',
          color: '#c7254e',
        }}>{children}</code>
      : <code style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '12.5px',
          display: 'block',
          background: '#f5f5f5',
          borderRadius: '5px',
          padding: '12px 16px',
          color: 'var(--color-text-secondary)',
          overflowX: 'auto',
          borderLeft: '3px solid var(--color-panel-accent)',
        }}>{children}</code>
  ),
  a: ({ href, children }) => (
    <a href={href} style={{
      color: 'var(--color-accent)',
      textDecoration: 'none',
    }}
    onMouseEnter={e => e.currentTarget.style.textDecoration = 'underline'}
    onMouseLeave={e => e.currentTarget.style.textDecoration = 'none'}
    >{children}</a>
  ),
  ul: ({ children }) => (
    <ul style={{
      paddingLeft: '20px',
      listStyle: 'disc',
      color: 'var(--color-text-secondary)',
      marginBottom: '12px',
    }}>{children}</ul>
  ),
  li: ({ children }) => (
    <li style={{
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-md)',
      lineHeight: '1.7',
    }}>{children}</li>
  ),
}

export function DocPanel({ node, isOpen, onClose, staleMap }) {
  const isStale = node ? (staleMap.get(node.id) ?? !!node.stale) : false
  const hasDoc = node?.doc != null
  const { content, loading, error, retry } = useDoc(isOpen && hasDoc ? node?.path : null)

  const transform = isOpen ? 'translateX(0)' : `translateX(${PANEL_WIDTH}px)`

  return (
    <div
      style={{
        width: `${PANEL_WIDTH}px`,
        flexShrink: 0,
        height: '100%',
        background: 'var(--color-surface)',
        borderLeft: '3px solid var(--color-panel-accent)',
        display: 'flex',
        flexDirection: 'column',
        transform,
        transition: 'transform 200ms ease-out',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Close button — 44x44px tap target */}
      <button
        aria-label="Close doc panel"
        tabIndex={isOpen ? 0 : -1}
        onClick={onClose}
        style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          width: '44px',
          height: '44px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--color-text-muted)',
          fontSize: 'var(--text-xl)',
          borderRadius: '4px',
          zIndex: 1,
        }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--color-text-primary)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--color-text-muted)'}
      >
        ×
      </button>

      {node && (
        <>
          {/* File path */}
          <div style={{ padding: '24px 52px 6px 24px' }}>
            <div
              title={node.path}
              style={{
                fontFamily: 'var(--font-sans)',
                fontSize: 'var(--text-md)',
                fontWeight: 600,
                color: 'var(--color-text-primary)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {node.path}
            </div>
          </div>

          {/* Staleness badge — show only when stale; silence = healthy */}
          <div style={{ padding: '0 24px 16px 24px' }}>
            {isStale && (
              <span style={{
                background: 'var(--color-stale-badge-bg)',
                color: 'var(--color-stale-badge-text)',
                fontFamily: 'var(--font-sans)',
                fontSize: '11px',
                fontWeight: 500,
                padding: '3px 10px',
                borderRadius: '4px',
                border: '1px solid #FFB74D',
                display: 'inline-block',
              }}>Outdated</span>
            )}
          </div>

          {/* Divider */}
          <div style={{ height: '1px', background: 'var(--color-border)', margin: '0' }} />

          {/* Doc body */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
            {!hasDoc && (
              <div>
                <p style={{ fontFamily: 'var(--font-sans)', fontSize: 'var(--text-md)', color: 'var(--color-text-muted)' }}>
                  No documentation generated yet.
                </p>
                <p style={{ fontFamily: 'var(--font-sans)', fontSize: 'var(--text-md)', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                  Run corpus update to generate docs.
                </p>
              </div>
            )}
            {hasDoc && loading && (
              <p style={{ fontFamily: 'var(--font-sans)', fontSize: 'var(--text-md)', color: 'var(--color-text-muted)' }}>
                Loading...
              </p>
            )}
            {hasDoc && error && (
              <div>
                <p style={{ fontFamily: 'var(--font-sans)', fontSize: 'var(--text-md)', color: 'var(--color-text-muted)' }}>
                  Could not load doc for this file.
                </p>
                <button
                  tabIndex={isOpen ? 0 : -1}
                  onClick={retry}
                  style={retryBtnStyle}
                  onMouseEnter={e => e.currentTarget.style.background = '#e0e0e0'}
                  onMouseLeave={e => e.currentTarget.style.background = 'var(--color-surface-raised)'}
                >
                  Retry
                </button>
              </div>
            )}
            {hasDoc && !loading && !error && content && (
              <ReactMarkdown components={mdComponents}>{content}</ReactMarkdown>
            )}
          </div>
        </>
      )}
    </div>
  )
}
