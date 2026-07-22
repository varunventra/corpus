import React, { useMemo } from 'react'
import { lastName } from '../utils/path.js'

function buildTree(nodes) {
  const byPath = new Map(nodes.map(n => [n.path, n]))

  function buildNode(node, depth) {
    const item = { node, depth, children: null }
    if (node.type === 'dir') {
      const prefix = node.path + '/'
      const directChildren = nodes.filter(n => {
        if (!n.path.startsWith(prefix)) return false
        const rest = n.path.slice(prefix.length)
        return !rest.includes('/')
      })
      directChildren.sort((a, b) => {
        if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
        return a.path.localeCompare(b.path)
      })
      item.children = directChildren.map(child => buildNode(child, depth + 1))
    }
    return item
  }

  const rootNodes = nodes.filter(n => {
    const lastSlash = n.path.lastIndexOf('/')
    if (lastSlash === -1) return true
    const parentPath = n.path.slice(0, lastSlash)
    const parentNode = byPath.get(parentPath)
    return !parentNode || parentNode.type !== 'dir'
  })

  rootNodes.sort((a, b) => {
    if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
    return a.path.localeCompare(b.path)
  })

  return rootNodes.map(n => buildNode(n, 0))
}

function TreeNode({ item, selectedNodeId, onNodeSelect, collapsedMap, onToggleCollapse, staleMap }) {
  const { node, depth, children } = item
  const isCollapsed = collapsedMap.get(node.id) ?? true
  const isSelected = node.id === selectedNodeId
  const isStale = staleMap.get(node.id) ?? !!node.stale

  if (node.type === 'dir') {
    return (
      <>
        <div
          onClick={() => onToggleCollapse(node.id)}
          role="treeitem"
          aria-expanded={!isCollapsed}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: `5px 12px 5px ${12 + depth * 16}px`,
            cursor: 'pointer',
            userSelect: 'none',
            color: 'var(--color-text-primary)',
            minHeight: 36,
          }}
          onMouseEnter={e => e.currentTarget.style.background = 'var(--color-surface-container)'}
          onMouseLeave={e => e.currentTarget.style.background = 'none'}
        >
          <span style={{
            display: 'inline-block',
            fontSize: 10,
            color: 'var(--color-text-muted)',
            transform: isCollapsed ? 'rotate(0deg)' : 'rotate(90deg)',
            transition: 'transform 150ms',
            width: 12,
            flexShrink: 0,
          }}>▶</span>
          <span style={{
            fontFamily: 'var(--font-headline)',
            fontSize: 14,
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {lastName(node.path)}
          </span>
          {isStale && (
            <div style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: 'var(--color-node-stale)',
              flexShrink: 0,
            }} title="Documentation stale" />
          )}
        </div>
        {!isCollapsed && children && children.map(child => (
          <TreeNode
            key={child.node.id}
            item={child}
            selectedNodeId={selectedNodeId}
            onNodeSelect={onNodeSelect}
            collapsedMap={collapsedMap}
            onToggleCollapse={onToggleCollapse}
            staleMap={staleMap}
          />
        ))}
      </>
    )
  }

  return (
    <div
      onClick={() => onNodeSelect(node)}
      role="treeitem"
      aria-selected={isSelected}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: `4px 12px 4px ${12 + depth * 16 + 16}px`,
        cursor: 'pointer',
        userSelect: 'none',
        borderLeft: isSelected ? '3px solid var(--color-accent)' : '3px solid transparent',
        background: isSelected ? 'var(--color-surface-container)' : 'none',
        color: isSelected ? 'var(--color-accent)' : 'var(--color-text-secondary)',
        minHeight: 36,
      }}
      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'var(--color-surface-low)' }}
      onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'none' }}
    >
      <span style={{
        fontFamily: 'var(--font-body)',
        fontSize: 13,
        fontWeight: isSelected ? 600 : 500,
        flex: 1,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {lastName(node.path)}
      </span>
      {isStale && (
        <div style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: 'var(--color-node-stale)',
          flexShrink: 0,
        }} title="Documentation stale" />
      )}
    </div>
  )
}

export function FileTree({ nodes, selectedNodeId, onNodeSelect, collapsedMap, onToggleCollapse, staleMap }) {
  const tree = useMemo(() => {
    if (!nodes || nodes.length === 0) return []
    return buildTree(nodes)
  }, [nodes])

  if (!nodes || nodes.length === 0) {
    return (
      <div style={{ padding: 24, color: 'var(--color-text-muted)', fontFamily: 'var(--font-body)', fontSize: 13 }}>
        No files tracked.
      </div>
    )
  }

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '8px 0' }}>
      {tree.map(item => (
        <TreeNode
          key={item.node.id}
          item={item}
          selectedNodeId={selectedNodeId}
          onNodeSelect={onNodeSelect}
          collapsedMap={collapsedMap}
          onToggleCollapse={onToggleCollapse}
          staleMap={staleMap}
        />
      ))}
    </div>
  )
}
