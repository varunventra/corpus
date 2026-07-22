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
  // The build subprocess takes ~6s — well over vitest's 5s default per-test
  // timeout, which made this test a flake. Explicit generous timeout instead.
  it('build completes without error', () => {
    // Run the build; throws if exit code != 0
    let error = null
    try {
      execSync('npm run build', { cwd: ROOT, stdio: 'pipe', timeout: 120_000 })
    } catch (e) {
      error = e
    }
    expect(error, `Build failed:\n${error?.stderr?.toString()}`).toBeNull()
  }, 60_000)
})

// ---------------------------------------------------------------------------
// CHECK 2 — Theme tokens
// (Phase 8: Sahara literal expectations retargeted to the GitHub-dark palette.
//  Same slots, new locked values.)
// ---------------------------------------------------------------------------

describe('Check 2 — GitHub-dark theme tokens in tokens.css', () => {
  const tokens = src('styles/tokens.css')

  it('--color-bg is defined', () => {
    expect(tokens).toMatch(/--color-bg\s*:/)
  })

  it('--color-bg value contains 0d1117 (GH canvas-default)', () => {
    expect(tokens).toMatch(/--color-bg\s*:[^;]*0d1117/)
  })

  it('--color-accent contains 4493f8 (GH accent-fg blue)', () => {
    expect(tokens).toMatch(/--color-accent\s*:[^;]*4493f8/)
  })

  it('--color-node-stale contains attention amber d29922', () => {
    expect(tokens).toMatch(/--color-node-stale\s*:[^;]*d29922/)
  })
})

// ---------------------------------------------------------------------------
// CHECK 3 — Surfaces are GitHub-dark; retired Sahara literals are gone
// (Phase 8 inverts the old "no dark surfaces" lock.)
// ---------------------------------------------------------------------------

describe('Check 3 — GitHub-dark surface hex values in tokens.css', () => {
  const tokens = src('styles/tokens.css')

  it('contains GH dark bg #0d1117', () => {
    expect(tokens).toContain('#0d1117')
  })

  it('contains GH dark surface #161b22', () => {
    expect(tokens).toContain('#161b22')
  })

  it('contains GH dark raised surface #21262d', () => {
    expect(tokens).toContain('#21262d')
  })

  it('does NOT contain retired Sahara literals (faf5ee / c2652a / f59e0b)', () => {
    expect(tokens).not.toContain('faf5ee')
    expect(tokens).not.toContain('c2652a')
    expect(tokens).not.toContain('f59e0b')
  })
})

// ---------------------------------------------------------------------------
// CHECK 4 — Fonts in index.html
// (Phase 8: Google display fonts removed; Material Symbols icon font must stay
//  — every icon glyph in the app depends on it.)
// ---------------------------------------------------------------------------

describe('Check 4 — Font link tags in index.html', () => {
  const html = readFileSync(resolve(ROOT, 'index.html'), 'utf8')

  it('does NOT contain EB+Garamond font link', () => {
    expect(html).not.toContain('EB+Garamond')
  })

  it('does NOT contain Manrope font link', () => {
    expect(html).not.toContain('Manrope')
  })

  it('still contains the Material Symbols Outlined icon font link', () => {
    expect(html).toContain('Material+Symbols+Outlined')
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
// CHECK 15 — GraphCanvas GitHub-dark palette
// (Phase 8: Sahara constants retargeted to the GH-dark constants.)
// ---------------------------------------------------------------------------

describe('Check 15 — GraphCanvas.jsx GitHub-dark palette', () => {
  const gc = src('components/GraphCanvas.jsx')

  it('has #0d1117 as background color constant', () => {
    expect(gc).toContain('#0d1117')
  })

  it('has the GH-dark node color constants (file/dir/stale/pulse)', () => {
    expect(gc).toMatch(/COLOR_NODE_FILE\s*=\s*'#161b22'/)
    expect(gc).toMatch(/COLOR_NODE_DIR\s*=\s*'#4493f8'/)
    expect(gc).toMatch(/COLOR_NODE_STALE\s*=\s*'#d29922'/)
    expect(gc).toMatch(/COLOR_NODE_PULSE\s*=\s*'#3fb950'/)
  })

  it('uses ResizeObserver', () => {
    expect(gc).toContain('ResizeObserver')
  })

  it('does NOT contain retired Sahara colors (faf5ee / c2652a / f59e0b / 14b8a6)', () => {
    expect(gc).not.toContain('#faf5ee')
    expect(gc).not.toContain('#c2652a')
    expect(gc).not.toContain('#f59e0b')
    expect(gc).not.toContain('#14b8a6')
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
