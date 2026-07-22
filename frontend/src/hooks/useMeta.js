import { useState, useEffect } from 'react'

/**
 * Fetch GET /meta once on mount.
 * Returns { repoRoot: string | null }
 * repoRoot is null until fetched or if fetch fails.
 */
export function useMeta() {
  const [repoRoot, setRepoRoot] = useState(null)

  useEffect(() => {
    fetch('/meta')
      .then(res => {
        if (!res.ok) throw new Error('meta fetch failed')
        return res.json()
      })
      .then(data => {
        setRepoRoot(data.repo_root ?? null)
      })
      .catch(() => {
        // Silently fail — repoRoot stays null; "Open in Editor" button becomes disabled
      })
  }, [])

  return { repoRoot }
}
