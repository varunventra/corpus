import React from 'react'

const LEVELS = ['All', '1', '2', '3', '4', '5']

const btnBase = {
  fontFamily: 'var(--font-sans)',
  fontSize: 'var(--text-sm)',
  height: '30px',
  minHeight: '36px',
  border: '1px solid var(--color-border)',
  borderRadius: '5px',
  padding: '0 4px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'background 100ms',
  cursor: 'pointer',
}

export function ImportanceFilter({ value, onChange }) {
  return (
    <div style={{ display: 'flex', gap: '3px', alignItems: 'center' }}>
      <span style={{
        fontFamily: 'var(--font-sans)',
        fontSize: 'var(--text-sm)',
        color: '#888888',
        paddingRight: '8px',
      }}>
        Show files with importance ≥
      </span>
      {LEVELS.map(level => {
        const active = value === level
        return (
          <button
            key={level}
            tabIndex={0}
            aria-pressed={active}
            onClick={() => onChange(level)}
            style={{
              ...btnBase,
              width: level === 'All' ? '44px' : '32px',
              background: active ? '#E63946' : '#f0f0f0',
              color: active ? '#ffffff' : '#666666',
              borderColor: active ? '#E63946' : 'var(--color-border)',
              fontWeight: active ? '600' : '500',
            }}
            onMouseEnter={e => {
              if (!active) e.currentTarget.style.background = '#e0e0e0'
            }}
            onMouseLeave={e => {
              if (!active) e.currentTarget.style.background = '#f0f0f0'
            }}
          >
            {level}
          </button>
        )
      })}
    </div>
  )
}
