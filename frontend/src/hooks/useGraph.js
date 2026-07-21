import { useState, useEffect, useRef, useCallback } from 'react'

const POLL_INTERVAL_MS = 5000
const WS_RECONNECT_DELAY_MS = 3000

/**
 * Fetch the graph once on mount (topology + initial stale flags).
 * Then poll GET /graph every 5s and patch only the stale map — never
 * replacing the full graph data, so the force simulation is not re-init'd.
 *
 * Also opens a WebSocket to ws://localhost:7077/events:
 *   - "query" events  → call onQueryEvent(node_id)
 *   - "graph" events  → re-fetch GET /graph, merge new node data (stale/importance)
 *                        without replacing node objects (preserves force positions)
 *   - "stale" events  → update the stale map for that node_id
 * Reconnects silently after 3s on close/error.
 * 5s stale polling is kept as a fallback.
 *
 * Returns:
 *   nodes        — array from graph.json (stable reference)
 *   edges        — array from graph.json (stable reference)
 *   staleMap     — Map<nodeId, boolean>, updated every poll
 *   projectName  — string derived from graph metadata or empty string
 *   loading      — true during initial fetch
 *   error        — Error | null
 *   retry        — function to re-trigger initial fetch
 *   onQueryEvent — stable callback; pass to WS hook consumer (App.jsx provides it via prop)
 */
export function useGraph({ onQueryEvent } = {}) {
  const [nodes, setNodes] = useState(null)       // null = not loaded
  const [edges, setEdges] = useState(null)
  const [staleMap, setStaleMap] = useState(new Map())
  const [projectName, setProjectName] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [retryKey, setRetryKey] = useState(0)

  const staleMapRef = useRef(new Map())
  // Keep a ref to nodes so the WS handler can merge without a stale closure
  const nodesRef = useRef(null)

  const retry = useCallback(() => setRetryKey(k => k + 1), [])

  // Initial load
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    fetch('/graph')
      .then(res => {
        if (!res.ok) return res.json().then(d => Promise.reject(new Error(d.error || res.statusText)))
        return res.json()
      })
      .then(data => {
        if (cancelled) return
        const initialStale = new Map()
        for (const n of data.nodes || []) {
          initialStale.set(n.id, !!n.stale)
        }
        staleMapRef.current = initialStale
        setStaleMap(new Map(initialStale))
        nodesRef.current = data.nodes || []
        setNodes(data.nodes || [])
        setEdges(data.edges || [])
        setProjectName(data.project_name || '')
        setLoading(false)
      })
      .catch(err => {
        if (cancelled) return
        setError(err)
        setLoading(false)
      })

    return () => { cancelled = true }
  }, [retryKey])

  // Stale polling — only runs after initial load succeeds
  useEffect(() => {
    if (nodes === null) return  // not loaded yet

    const id = setInterval(() => {
      fetch('/graph')
        .then(res => {
          if (!res.ok) return
          return res.json()
        })
        .then(data => {
          if (!data) return
          let changed = false
          const next = new Map(staleMapRef.current)
          for (const n of data.nodes || []) {
            const newStale = !!n.stale
            if (next.get(n.id) !== newStale) {
              next.set(n.id, newStale)
              changed = true
            }
          }
          if (changed) {
            staleMapRef.current = next
            setStaleMap(new Map(next))
          }
        })
        .catch(() => {
          // Silently ignore poll errors — sidecar may restart
        })
    }, POLL_INTERVAL_MS)

    return () => clearInterval(id)
  }, [nodes])  // re-run if nodes object identity changes (new load)

  // WebSocket client — reconnects silently on close/error
  useEffect(() => {
    let ws = null
    let reconnectTimer = null
    let destroyed = false

    function connect() {
      if (destroyed) return
      try {
        ws = new WebSocket('ws://localhost:7077/events')
      } catch (_) {
        // WebSocket constructor can throw on invalid URL — should never happen here
        return
      }

      ws.onmessage = (evt) => {
        let msg
        try {
          msg = JSON.parse(evt.data)
        } catch (_) {
          return
        }

        if (msg.event === 'query') {
          if (onQueryEvent) onQueryEvent(msg.node_id ?? null)
        } else if (msg.event === 'graph') {
          // stale detection via polling (see interval above)
          // Re-fetch graph and merge stale/importance — do NOT replace node objects
          // (replacing objects would reset force simulation positions)
          fetch('/graph')
            .then(res => {
              if (!res.ok) return null
              return res.json()
            })
            .then(data => {
              if (!data || destroyed) return
              // Update stale map from fresh data
              const next = new Map(staleMapRef.current)
              let staleChanged = false
              for (const n of data.nodes || []) {
                const newStale = !!n.stale
                if (next.get(n.id) !== newStale) {
                  next.set(n.id, newStale)
                  staleChanged = true
                }
              }
              if (staleChanged) {
                staleMapRef.current = next
                setStaleMap(new Map(next))
              }

              // Remove nodes that no longer appear in incoming, then patch survivors
              const incomingIds = new Set((data.nodes || []).map(n => n.id))
              const survivingNodes = (nodesRef.current || []).filter(n => incomingIds.has(n.id))

              // Merge importance + stale into surviving node objects in-place
              // so react-force-graph keeps positions
              const incomingMap = new Map((data.nodes || []).map(n => [n.id, n]))
              for (const node of survivingNodes) {
                const fresh = incomingMap.get(node.id)
                if (fresh) {
                  node.importance = fresh.importance
                  node.stale = fresh.stale
                }
              }

              // Append nodes that are new (not in current list)
              const existingIds = new Set(survivingNodes.map(n => n.id))
              const newNodes = (data.nodes || []).filter(n => !existingIds.has(n.id))
              if (survivingNodes.length !== (nodesRef.current || []).length || newNodes.length > 0) {
                nodesRef.current = [...survivingNodes, ...newNodes]
                setNodes(nodesRef.current)
              } else {
                // Trigger a re-render by setting a new stale map reference
                // (the node objects are mutated in-place; that's enough for canvas re-draw)
                setStaleMap(prev => new Map(prev))
              }
            })
            .catch(() => {})
        }
      }

      ws.onclose = () => {
        if (!destroyed) {
          reconnectTimer = setTimeout(connect, WS_RECONNECT_DELAY_MS)
        }
      }

      ws.onerror = () => {
        // onerror is always followed by onclose — let onclose handle reconnect
        // Suppress the error: no console.error here so the browser console stays clean
      }
    }

    connect()

    return () => {
      destroyed = true
      clearTimeout(reconnectTimer)
      if (ws) {
        ws.onclose = null  // prevent reconnect loop on intentional teardown
        ws.onerror = null
        ws.close()
      }
    }
  }, [onQueryEvent])  // onQueryEvent identity is stable (useCallback in App.jsx)

  return { nodes, edges, staleMap, projectName, loading, error, retry }
}
