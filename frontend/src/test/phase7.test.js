/**
 * Phase 7 — "Sahara" warm theme + three-column layout + five functional tabs
 * QA automated checks against the 18 acceptance criteria from PLAN.md / DESIGN-phase7-sahara.md
 *
 * All checks are source-code assertions — no browser required.
 * Run: cd frontend && npm test -- phase7
 */

import { readFileSync, existsSync } from 'fs'
import { resolve } from 'path'
import { execSync } from 'child_process'
import { describe, it, expect } from 'vitest'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC  = resolve(__dirname, '..')           // frontend/src
const ROOT = resolve(SRC, '..')                 // frontend/
const REPO = resolve(ROOT, '..')                // repo root (corpus/)

function src(relPath) {
  return readFileSync(resolve(SRC, relPath), 'utf8')
}
function repo(relPath) {
  return readFileSync(resolve(REPO, relPath), 'utf8')
}
function exists(absPath) {
  return existsSync(absPath)
}

// ---------------------------------------------------------------------------
// CHECK 1 — Build exits 0
// ---------------------------------------------------------------------------

describe('Check 1 — npm run build exits 0', () => {
  it('build completes without error', () => {
    // Run the build; throws if exit code != 0
    let error = null
    try {
      execSync('npm run build', { cwd: ROOT, stdio: 'pipe', timeout: 120_000 })
    } catch (e) {
      error = e
    }
    expect(error, `Build failed:\n${error?.stderr?.toString()}`).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// CHECK 2 — Warm theme tokens
// ---------------------------------------------------------------------------

describe('Check 2 — Warm theme tokens in tokens.css', () => {
  const tokens = src('styles/tokens.css')

  it('--color-bg is defined', () => {
    expect(tokens).toMatch(/--color-bg\s*:/)
  })

  it('--color-bg value contains faf5ee', () => {
    expect(tokens).toMatch(/--color-bg\s*:[^;]*faf5ee/)
  })

  it('--color-primary OR --color-accent contains c2652a', () => {
    // Spec uses --color-accent for sienna primary
    expect(tokens).toMatch(/--color-accent\s*:[^;]*c2652a/)
  })

  it('--color-node-stale contains amber value f59e0b', () => {
    expect(tokens).toMatch(/--color-node-stale\s*:[^;]*f59e0b/)
  })
})

// ---------------------------------------------------------------------------
// CHECK 3 — No dark surfaces
// ---------------------------------------------------------------------------

describe('Check 3 — No dark surface hex values in tokens.css', () => {
  const tokens = src('styles/tokens.css')

  it('does NOT contain old dark bg #0d1117', () => {
    expect(tokens).not.toContain('#0d1117')
  })

  it('does NOT contain old dark surface #161b22', () => {
    expect(tokens).not.toContain('#161b22')
  })

  it('does NOT contain old dark raised surface #21262d', () => {
    expect(tokens).not.toContain('#21262d')
  })
})

// ---------------------------------------------------------------------------
// CHECK 4 — Fonts in index.html
// ---------------------------------------------------------------------------

describe('Check 4 — Google Fonts link tags in index.html', () => {
  const html = readFileSync(resolve(ROOT, 'index.html'), 'utf8')

  it('contains EB+Garamond font link', () => {
    expect(html).toContain('EB+Garamond')
  })

  it('contains Manrope font link', () => {
    expect(html).toContain('Manrope')
  })
})

// ---------------------------------------------------------------------------
// CHECK 5 — Three-column layout in App.jsx
// ---------------------------------------------------------------------------

describe('Check 5 — Three-column layout state and components in App.jsx', () => {
  const app = src('App.jsx')

  it('has fileTreeVisible state', () => {
    expect(app).toMatch(/fileTreeVisible/)
  })

  it('has activeTab state', () => {
    expect(app).toMatch(/activeTab/)
  })

  it('renders FileTree component', () => {
    expect(app).toMatch(/FileTree/)
  })

  it('renders DocReader component', () => {
    expect(app).toMatch(/DocReader/)
  })

  it('has at least 4 of the 5 tab names', () => {
    const tabs = ['explorer', 'architecture', 'dependencies', 'symbols', 'overview']
    const found = tabs.filter(t => app.includes(t))
    expect(found.length).toBeGreaterThanOrEqual(4)
  })
})

// ---------------------------------------------------------------------------
// CHECK 6 — FileTree component
// ---------------------------------------------------------------------------

describe('Check 6 — FileTree.jsx exists and is correct', () => {
  const ftPath = resolve(SRC, 'components/FileTree.jsx')

  it('FileTree.jsx file exists', () => {
    expect(exists(ftPath)).toBe(true)
  })

  it('exports a FileTree component', () => {
    const ft = readFileSync(ftPath, 'utf8')
    expect(ft).toMatch(/export\s+(function|const)\s+FileTree/)
  })

  it('uses collapsedMap prop', () => {
    const ft = readFileSync(ftPath, 'utf8')
    expect(ft).toContain('collapsedMap')
  })

  it('has stale dot logic (staleMap or stale)', () => {
    const ft = readFileSync(ftPath, 'utf8')
    expect(ft).toMatch(/staleMap|\.stale/)
  })
})

// ---------------------------------------------------------------------------
// CHECK 7 — Five tab component files exist
// ---------------------------------------------------------------------------

describe('Check 7 — All 5 tab component files exist', () => {
  const tabFiles = [
    'components/tabs/ExplorerTab.jsx',
    'components/tabs/ArchitectureTab.jsx',
    'components/tabs/DependenciesTab.jsx',
    'components/tabs/SymbolsTab.jsx',
    'components/tabs/OverviewTab.jsx',
  ]

  tabFiles.forEach(rel => {
    it(`${rel} exists`, () => {
      expect(exists(resolve(SRC, rel))).toBe(true)
    })
  })
})

// ---------------------------------------------------------------------------
// CHECK 8 — DocReader
// ---------------------------------------------------------------------------

describe('Check 8 — DocReader.jsx correctness', () => {
  const drPath = resolve(SRC, 'components/DocReader.jsx')

  it('DocReader.jsx file exists', () => {
    expect(exists(drPath)).toBe(true)
  })

  it('contains vscode://file/ deep link', () => {
    const dr = readFileSync(drPath, 'utf8')
    expect(dr).toContain('vscode://file/')
  })

  it('uses EB Garamond or font-headline font reference', () => {
    const dr = readFileSync(drPath, 'utf8')
    expect(dr).toMatch(/EB Garamond|font-headline/)
  })

  it('accepts isOpen prop', () => {
    const dr = readFileSync(drPath, 'utf8')
    expect(dr).toContain('isOpen')
  })
})

// ---------------------------------------------------------------------------
// CHECK 9 — SymbolsTab
// ---------------------------------------------------------------------------

describe('Check 9 — SymbolsTab.jsx symbol table and search', () => {
  const sym = src('components/tabs/SymbolsTab.jsx')

  it('references node.symbols or sym.kind', () => {
    expect(sym).toMatch(/node\.symbols|sym\.kind/)
  })

  it('has search input with onChange + setQuery', () => {
    expect(sym).toContain('onChange')
    expect(sym).toContain('setQuery')
  })
})

// ---------------------------------------------------------------------------
// CHECK 10 — OverviewTab
// ---------------------------------------------------------------------------

describe('Check 10 — OverviewTab.jsx dashboard logic', () => {
  const ov = src('components/tabs/OverviewTab.jsx')

  it('has stat chip filter logic (.filter(n => n.type)', () => {
    expect(ov).toMatch(/\.filter\s*\(n\s*=>\s*n\.type/)
  })

  it('sorts by importance', () => {
    expect(ov).toMatch(/importance/)
  })

  it('has stale files filter (staleFiles or staleMap)', () => {
    expect(ov).toMatch(/staleFiles|staleMap/)
  })
})

// ---------------------------------------------------------------------------
// CHECK 11 — ArchitectureTab
// ---------------------------------------------------------------------------

describe('Check 11 — ArchitectureTab.jsx dir-to-dir edge derivation', () => {
  const arch = src('components/tabs/ArchitectureTab.jsx')

  it('derives source dir (srcDir or fileToDir)', () => {
    expect(arch).toMatch(/srcDir|fileToDir/)
  })

  it('deduplicates edges (edgeSet or seen.add)', () => {
    expect(arch).toMatch(/edgeSet|seen\.add/)
  })

  it("filters to dir nodes (type === 'dir')", () => {
    expect(arch).toMatch(/type\s*===\s*['"]dir['"]/)
  })
})

// ---------------------------------------------------------------------------
// CHECK 12 — DependenciesTab
// ---------------------------------------------------------------------------

describe('Check 12 — DependenciesTab.jsx empty state and cleanup', () => {
  const dep = src('components/tabs/DependenciesTab.jsx')

  it('has empty-state prompt text "Select a file"', () => {
    expect(dep).toContain('Select a file')
  })

  it('has clearTimeout cleanup', () => {
    expect(dep).toContain('clearTimeout')
  })
})

// ---------------------------------------------------------------------------
// CHECK 13 — useMeta hook
// ---------------------------------------------------------------------------

describe('Check 13 — useMeta.js hook', () => {
  const hookPath = resolve(SRC, 'hooks/useMeta.js')

  it('useMeta.js file exists', () => {
    expect(exists(hookPath)).toBe(true)
  })

  it("contains fetch('/meta')", () => {
    const hook = readFileSync(hookPath, 'utf8')
    expect(hook).toContain("fetch('/meta')")
  })
})

// ---------------------------------------------------------------------------
// CHECK 14 — server.py /meta route
// ---------------------------------------------------------------------------

describe('Check 14 — server.py /meta route', () => {
  const server = repo('corpus/server.py')

  it("contains /meta route", () => {
    expect(server).toContain('/meta')
  })

  it('contains repo_root in response', () => {
    expect(server).toContain('repo_root')
  })

  it('normalizes backslashes with .replace', () => {
    // Accepts any replace call that handles backslashes
    expect(server).toMatch(/replace\s*\(["'\\]/)
  })
})

// ---------------------------------------------------------------------------
// CHECK 15 — GraphCanvas warm theme
// ---------------------------------------------------------------------------

describe('Check 15 — GraphCanvas.jsx Sahara warm palette', () => {
  const gc = src('components/GraphCanvas.jsx')

  it('has #faf5ee as background color constant', () => {
    expect(gc).toContain('#faf5ee')
  })

  it('has #c2652a as a node color constant', () => {
    expect(gc).toContain('#c2652a')
  })

  it('uses ResizeObserver', () => {
    expect(gc).toContain('ResizeObserver')
  })

  it('does NOT contain old dark bg #0d1117', () => {
    expect(gc).not.toContain('#0d1117')
  })
})

// ---------------------------------------------------------------------------
// CHECK 16 — MCP pulse still wired
// ---------------------------------------------------------------------------

describe('Check 16 — MCP pulse wiring (pulseMap + pulseAncestorIds)', () => {
  const app = src('App.jsx')
  const gc  = src('components/GraphCanvas.jsx')

  it('App.jsx has pulseMap', () => {
    expect(app).toContain('pulseMap')
  })

  it('App.jsx has pulseAncestorIds', () => {
    expect(app).toContain('pulseAncestorIds')
  })

  it('GraphCanvas.jsx receives pulseMap prop', () => {
    expect(gc).toContain('pulseMap')
  })

  it('GraphCanvas.jsx receives pulseAncestorIds prop', () => {
    expect(gc).toContain('pulseAncestorIds')
  })
})

// ---------------------------------------------------------------------------
// CHECK 17 — DocPanel shim exists (test compatibility)
// ---------------------------------------------------------------------------

describe('Check 17 — DocPanel.jsx shim exists', () => {
  it('frontend/src/components/DocPanel.jsx exists', () => {
    expect(exists(resolve(SRC, 'components/DocPanel.jsx'))).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// CHECK 18 — Open in Editor URL normalization
// ---------------------------------------------------------------------------

describe('Check 18 — Windows path normalization in Open in Editor', () => {
  const dr     = src('components/DocReader.jsx')
  const server = repo('corpus/server.py')

  it('DocReader.jsx normalizes backslashes in vscode:// URL', () => {
    // Matches .replace(/\\/g or .replace('\\', '/')
    expect(dr).toMatch(/replace\s*\(/)
    // More specifically: a replace on backslash for the vscode URL
    expect(dr).toMatch(/replace.*\\\\|replace.*\\/g)
  })

  it('server.py normalizes backslashes in repo_root', () => {
    expect(server).toMatch(/replace\s*\(\s*["'\\\\]/)
  })
})
