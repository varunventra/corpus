import { useState, useEffect, useCallback } from 'react'

/**
 * Fetch the doc markdown for a given repo-relative path.
 *
 * Returns { content, loading, error, retry }
 * content is null until loaded.
 */
export function useDoc(path) {
  const [content, setContent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [retryKey, setRetryKey] = useState(0)

  const retry = useCallback(() => setRetryKey(k => k + 1), [])

  useEffect(() => {
    if (!path) {
      setContent(null)
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setContent(null)
    setError(null)

    fetch(`/doc?path=${encodeURIComponent(path)}`)
      .then(res => {
        if (!res.ok) return res.json().then(d => Promise.reject(new Error(d.error || res.statusText)))
        return res.text()
      })
      .then(text => {
        if (cancelled) return
        setContent(text)
        setLoading(false)
      })
      .catch(err => {
        if (cancelled) return
        setError(err)
        setLoading(false)
      })

    return () => { cancelled = true }
  }, [path, retryKey])

  return { content, loading, error, retry }
}
