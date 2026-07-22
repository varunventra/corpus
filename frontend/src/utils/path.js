/**
 * Returns the last path segment (filename or dir name).
 * e.g. "src/utils/path.js" → "path.js"
 */
export function lastName(path) {
  if (!path) return ''
  const parts = path.split('/')
  return parts[parts.length - 1] || path
}

/**
 * Returns the file extension (lowercase, no dot).
 * e.g. "src/App.jsx" → "jsx"
 */
export function fileExtension(path) {
  const name = lastName(path)
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
}

/**
 * Returns a human-readable file type label.
 */
export function fileTypeLabel(path, nodeType) {
  if (nodeType === 'dir') return 'Directory'
  const ext = fileExtension(path)
  const map = {
    py: 'Python Module',
    js: 'JavaScript Module',
    jsx: 'React Component',
    ts: 'TypeScript Module',
    tsx: 'React Component',
    rs: 'Rust Module',
    go: 'Go Module',
    md: 'Markdown',
    json: 'JSON',
    css: 'Stylesheet',
    html: 'HTML',
  }
  return map[ext] || 'Source File'
}

/**
 * Splits a path into breadcrumb segments.
 * Each segment has { label, path, node } where node is looked up from nodesByPath.
 * nodesByPath: Map<path, node>
 */
export function splitSegments(path, nodesByPath) {
  if (!path) return []
  const parts = path.split('/')
  return parts.map((label, i) => {
    const segPath = parts.slice(0, i + 1).join('/')
    const node = nodesByPath ? (nodesByPath.get(segPath) ?? null) : null
    return { label, path: segPath, node }
  })
}
