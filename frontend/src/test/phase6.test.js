/**
 * Phase 6 — Obsidian-style frontend rework
 * QA automated checks against acceptance criteria and the 13 structural specs.
 *
 * These tests verify source code structure and token coverage without needing a
 * running browser. Visual rendering checks are annotated as BROWSER-ONLY.
 */

import { readFileSync } from 'fs'
import { resolve } from 'path'
import { describe, it, expect } from 'vitest'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC = resolve(__dirname, '..')          // frontend/src
const ROOT = resolve(SRC, '..')               // frontend/

function src(relPath) {
  return readFileSync(resolve(SRC, relPath), 'utf8')
}

// ---------------------------------------------------------------------------
// CHECK 1 — Build output exists (build already ran; we confirm the dist file)
// ---------------------------------------------------------------------------

describe('Check 1 — Build produces dist/index.html', () => {
  it('dist/index.html exists and is non-empty', () => {
    const html = readFileSync(resolve(ROOT, 'dist/index.html'), 'utf8')
    expect(html.length).toBeGreaterThan(0)
    expect(html).toContain('<!doctype html>')
  })
})

// ---------------------------------------------------------------------------
// CHECK 2 — tokens.css contains all required CSS custom properties
// ---------------------------------------------------------------------------

describe('Check 2 — Token coverage in tokens.css', () => {
  const tokens = src('styles/tokens.css')

  const required = [
    '--color-bg',
    '--color-accent',
    '--color-node-file',
    '--color-node-stale',
    '--color-node-dir',
    '--color-node-pulse',
    '--color-edge',
    '--color-surface',
    // Phase 8: '--color-surface-raised' (Phase 6 Obsidian slot) retired;
    // '--color-surface-container' is the current hover/active surface slot.
    '--color-surface-container',
    '--color-border',
  ]

  for (const token of required) {
    it(`tokens.css defines ${token}`, () => {
      // Match the definition pattern (token followed by colon)
      expect(tokens).toMatch(new RegExp(`${token}\\s*:`))
    })
  }
})

// ---------------------------------------------------------------------------
// CHECK 3 — No hardcoded light hex colors in src files
// Allowed (Phase 8 GitHub dark): #ffffff only as the --color-fg-onEmphasis
//          token definition and the COLOR_DIR_BADGE_TEXT constant in
//          GraphCanvas.jsx. Everything else is a violation.
// ---------------------------------------------------------------------------

describe('Check 3 — No hardcoded light-theme hex colors', () => {
  const lightHex = [
    '#f0f0f0', '#fafafa', '#333333', '#111111',
    '#e0e0e0', '#aaaaaa', '#E63946', '#888888',
  ]

  const files = [
    'styles/tokens.css',
    'styles/global.css',
    'App.jsx',
    'components/GraphCanvas.jsx',
    'components/DocReader.jsx',
    'components/CommandPalette.jsx',
    'components/Minimap.jsx',
    'components/ImportanceFilter.jsx',
  ]

  for (const hex of lightHex) {
    it(`${hex} does not appear in any src file`, () => {
      for (const file of files) {
        const content = src(file)
        // Strip comments before checking
        const noComments = content
          .replace(/\/\*[\s\S]*?\*\//g, '')   // block comments
          .replace(/\/\/.*/g, '')               // line comments
        expect(noComments, `found ${hex} in ${file}`).not.toContain(hex)
      }
    })
  }

  it('#ffffff only appears as fg-onEmphasis token and GraphCanvas dir-badge constant', () => {
    const tokensCss = src('styles/tokens.css')
    const graphCanvas = src('components/GraphCanvas.jsx')
    const otherFiles = [
      'styles/global.css', 'App.jsx', 'components/DocReader.jsx',
      'components/CommandPalette.jsx', 'components/Minimap.jsx',
      'components/ImportanceFilter.jsx',
    ]

    // Phase 8: node-pulse is GH success-green (#3fb950); the only white left in
    // tokens.css is the GH primitive --color-fg-onEmphasis.
    const tokenMatches = [...tokensCss.matchAll(/#ffffff/gi)]
    expect(tokenMatches.length, 'tokens.css should have exactly one #ffffff (fg-onEmphasis)').toBe(1)
    expect(tokensCss).toMatch(/--color-fg-onEmphasis:\s*#ffffff/)

    // In GraphCanvas the only white is the dir-badge text on blue dir nodes
    const gcMatches = [...graphCanvas.matchAll(/#ffffff/gi)]
    expect(gcMatches.length, 'GraphCanvas.jsx should have exactly one #ffffff (COLOR_DIR_BADGE_TEXT)').toBe(1)
    expect(graphCanvas).toMatch(/COLOR_DIR_BADGE_TEXT\s*=\s*'#ffffff'/)

    // All other files: zero
    for (const file of otherFiles) {
      const content = src(file)
      const noComments = content
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/\/\/.*/g, '')
      expect(noComments, `unexpected #ffffff in ${file}`).not.toMatch(/#ffffff/i)
    }
  })
})

// ---------------------------------------------------------------------------
// CHECK 4 — App.jsx layout shell
// (Phase 6's "no header" assertion retired: Phase 7 introduced the permanent
//  top-nav <header> with the five tabs, and Phase 8 keeps it. The layout lock
//  now asserts the header IS present.)
// ---------------------------------------------------------------------------

describe('Check 4 — App.jsx layout shell (Phase 7+ top-nav header)', () => {
  const app = src('App.jsx')

  it('App.jsx renders the top-nav <header (Phase 7 three-column layout)', () => {
    expect(app).toContain('<header')
  })

  it('App.jsx does not contain role="banner"', () => {
    expect(app).not.toContain('role="banner"')
  })

  it('App root div uses position:relative + 100vh (full-screen layout)', () => {
    // The root return div must have both height:100vh and position:relative
    expect(app).toContain("height: '100vh'")
    expect(app).toContain("position: 'relative'")
  })
})

// ---------------------------------------------------------------------------
// CHECK 5 — DocPanel is an absolute-positioned overlay
// ---------------------------------------------------------------------------

describe('Check 5 — DocReader panel positioning', () => {
  const panel = src('components/DocReader.jsx')

  it("DocReader outermost div uses width transition (not translateX)", () => {
    // Phase 7 DocReader uses width: isOpen ? 450 : 0 transition instead of translateX
    expect(panel).toContain('width:')
    expect(panel).toContain('transition:')
  })

  it("DocReader has a close handler", () => {
    expect(panel).toContain('onClose')
  })

  it("DocReader panel does not use translateX for slide-in", () => {
    // Phase 7 uses width-transition, not transform translateX
    expect(panel).not.toContain('translateX(420px)')
  })
})

// ---------------------------------------------------------------------------
// CHECK 6 — App.jsx keyboard wiring
// (Phase 6's Ctrl+K palette assertions retired: Phase 7 removed the
//  CommandPalette from the rendered tree. The keydown listener now serves
//  Escape-closes-doc-reader; this check locks that behavior AND locks the
//  palette's removal so it doesn't silently return.)
// ---------------------------------------------------------------------------

describe('Check 6 — App.jsx keydown listener (Escape closes doc reader)', () => {
  const app = src('App.jsx')

  it('App.jsx has a document keydown listener', () => {
    expect(app).toContain("document.addEventListener('keydown'")
  })

  it('keydown handler checks key === "Escape"', () => {
    expect(app).toMatch(/e\.key\s*===\s*['"]Escape['"]/)
  })

  it('App.jsx no longer references the removed CommandPalette', () => {
    expect(app).not.toContain('setPaletteOpen')
    expect(app).not.toContain('CommandPalette')
  })
})

// ---------------------------------------------------------------------------
// CHECK 7 — CommandPalette uses ReactDOM.createPortal
// ---------------------------------------------------------------------------

describe('Check 7 — CommandPalette renders via ReactDOM.createPortal', () => {
  const palette = src('components/CommandPalette.jsx')

  it('CommandPalette.jsx imports ReactDOM', () => {
    expect(palette).toContain("import ReactDOM from 'react-dom'")
  })

  it('CommandPalette.jsx calls ReactDOM.createPortal', () => {
    expect(palette).toContain('ReactDOM.createPortal')
  })

  it('createPortal targets document.body', () => {
    expect(palette).toContain('document.body')
  })
})

// ---------------------------------------------------------------------------
// CHECK 8 — DocPanel has useMemo filtering edges + "Linked from" heading
// ---------------------------------------------------------------------------

describe('Check 8 — DocReader backlinks section', () => {
  const panel = src('components/DocReader.jsx')

  it('DocReader has a useMemo that references edges', () => {
    // Look for useMemo with edges in its body
    expect(panel).toMatch(/useMemo\([^)]*\)/s)
    expect(panel).toContain('edges')
  })

  it('DocReader backlinks useMemo filters by target matching node id', () => {
    // Phase 7 DocReader uses === node.id pattern
    expect(panel).toContain('node.id')
  })

  it('DocReader has backlinks section (Imported by)', () => {
    // Phase 7 uses "Imported by" label instead of "Linked from"
    expect(panel).toContain('backlinks')
  })

  it('Backlinks section is hidden when backlinks.length === 0 (conditional render)', () => {
    // The JSX should gate on backlinks.length > 0
    expect(panel).toContain('backlinks.length > 0')
  })
})

// ---------------------------------------------------------------------------
// CHECK 9 — Minimap uses <canvas and setInterval
// ---------------------------------------------------------------------------

describe('Check 9 — Minimap canvas and interval', () => {
  const minimap = src('components/Minimap.jsx')

  it('Minimap.jsx renders a <canvas element', () => {
    expect(minimap).toContain('<canvas')
  })

  it('Minimap.jsx uses setInterval for periodic redraw', () => {
    expect(minimap).toContain('setInterval')
  })

  it('Minimap setInterval is called with 1000ms', () => {
    expect(minimap).toContain('setInterval(drawMinimap, 1000)')
  })

  it('Minimap clears the interval on cleanup (clearInterval)', () => {
    expect(minimap).toContain('clearInterval')
  })
})

// ---------------------------------------------------------------------------
// CHECK 10 — fgRef is lifted to App.jsx; GraphCanvas accepts it as a prop
// ---------------------------------------------------------------------------

describe('Check 10 — fgRef lift to App.jsx', () => {
  const app = src('App.jsx')
  const gc = src('components/GraphCanvas.jsx')

  it('App.jsx creates fgRef with useRef()', () => {
    expect(app).toMatch(/fgRef\s*=\s*useRef\(\)/)
  })

  it('App.jsx passes fgRef as a prop to GraphCanvas', () => {
    expect(app).toContain('fgRef={fgRef}')
  })

  it('GraphCanvas.jsx does NOT create its own useRef for fgRef', () => {
    // GraphCanvas should accept fgRef as a prop — it should not have
    // a "const fgRef = useRef" pattern inside the component
    expect(gc).not.toMatch(/const fgRef\s*=\s*useRef/)
  })

  it('GraphCanvas.jsx destructures fgRef in its props', () => {
    // The component should destructure fgRef from its argument
    expect(gc).toContain('fgRef,')
  })

  it('GraphCanvas.jsx passes fgRef as ref= to ForceGraph2D', () => {
    expect(gc).toContain('ref={fgRef}')
  })
})

// ---------------------------------------------------------------------------
// CHECK 11 — pulseAncestorIds is a Set in App.jsx; GraphCanvas uses .has()
// ---------------------------------------------------------------------------

describe('Check 11 — pulseAncestorIds as Set', () => {
  const app = src('App.jsx')
  const gc = src('components/GraphCanvas.jsx')

  it('App.jsx computes pulseAncestorIds using new Set()', () => {
    expect(app).toContain('const ids = new Set()')
    expect(app).toContain('return ids')
  })

  it('App.jsx passes pulseAncestorIds to GraphCanvas', () => {
    expect(app).toContain('pulseAncestorIds={pulseAncestorIds}')
  })

  it('GraphCanvas.jsx reads pulseAncestorIds.has(node.id)', () => {
    expect(gc).toContain('pulseAncestorIds.has(node.id)')
  })

  it('GraphCanvas.jsx does NOT use node.__pulseAncestor', () => {
    expect(gc).not.toContain('node.__pulseAncestor')
  })

  // REGRESSION FINDING: App.jsx line 197 uses bracket notation on a Map
  // (collapsedMap[ancestor.id]) which always returns undefined, making
  // pulseAncestorIds permanently empty.
  it('REGRESSION — App.jsx must use collapsedMap.get() not collapsedMap[] for ancestor collapsed check', () => {
    // This test asserts the CORRECT behavior per spec.
    // The current code uses collapsedMap[ancestor.id] which is WRONG for a Map.
    // This test will FAIL to surface the bug.
    expect(app).not.toMatch(/collapsedMap\[ancestor\.id\]/)
  })
})

// ---------------------------------------------------------------------------
// CHECK 12 — DocPanel staleMap default is new Map()
// ---------------------------------------------------------------------------

describe('Check 12 — DocReader staleMap prop', () => {
  const panel = src('components/DocReader.jsx')

  it('DocReader accepts a staleMap prop', () => {
    // Phase 7 DocReader receives staleMap as a prop (no default needed — App always passes it)
    expect(panel).toContain('staleMap')
  })
})

// ---------------------------------------------------------------------------
// CHECK 13 — aria-modal does NOT appear in CommandPalette
// ---------------------------------------------------------------------------

describe('Check 13 — No aria-modal in CommandPalette', () => {
  const palette = src('components/CommandPalette.jsx')

  it('CommandPalette.jsx does not contain aria-modal', () => {
    expect(palette).not.toContain('aria-modal')
  })
})

// ---------------------------------------------------------------------------
// Additional structural checks derived from spec
// ---------------------------------------------------------------------------

describe('Additional spec checks', () => {
  it('GraphCanvas label threshold is 0.15 (not 0.2)', () => {
    const gc = src('components/GraphCanvas.jsx')
    expect(gc).toContain('globalScale >= 0.15')
    expect(gc).not.toContain('globalScale >= 0.2')
  })

  it('GraphCanvas edge width is 1 (not 1.5)', () => {
    const gc = src('components/GraphCanvas.jsx')
    // linkWidth callback should return 1
    expect(gc).toContain('() => 1')
  })

  it('CommandPalette max results is 8', () => {
    const palette = src('components/CommandPalette.jsx')
    expect(palette).toContain('.slice(0, 8)')
  })

  it('Minimap is 160x120 px', () => {
    const minimap = src('components/Minimap.jsx')
    expect(minimap).toContain('width={160}')
    expect(minimap).toContain('height={120}')
  })

  it('Minimap is positioned bottom:16 right:16', () => {
    const minimap = src('components/Minimap.jsx')
    expect(minimap).toContain('bottom: 16')
    expect(minimap).toContain('right: 16')
  })

  it('CommandPalette search placeholder is correct', () => {
    const palette = src('components/CommandPalette.jsx')
    expect(palette).toContain('Search files and folders...')
  })

  it('CommandPalette backdrop has rgba(0,0,0,0.5)', () => {
    const palette = src('components/CommandPalette.jsx')
    expect(palette).toContain('rgba(0,0,0,0.5)')
  })

  it('CommandPalette modal width is min(520px, 90vw)', () => {
    const palette = src('components/CommandPalette.jsx')
    expect(palette).toContain('min(520px, 90vw)')
  })

  it('DocReader slide-in uses width transition (Phase 7 replaces translateX with width)', () => {
    const panel = src('components/DocReader.jsx')
    // Phase 7 DocReader uses width: isOpen ? 450 : 0 instead of translateX
    expect(panel).toContain('isOpen')
    expect(panel).toContain('450')
  })

  it('DocReader panel width is 450px', () => {
    const panel = src('components/DocReader.jsx')
    expect(panel).toContain('450')
  })

  it('GraphCanvas bg color is #0d1117 (Phase 8 GitHub dark palette)', () => {
    const gc = src('components/GraphCanvas.jsx')
    expect(gc).toContain("'#0d1117'")
    expect(gc).not.toContain("'#faf5ee'")
  })

  it('GraphCanvas pulse glow uses shadowBlur = 14 / globalScale', () => {
    const gc = src('components/GraphCanvas.jsx')
    expect(gc).toContain('14 / globalScale')
  })

  it('GraphCanvas stale glow uses shadowBlur = 8 / globalScale', () => {
    const gc = src('components/GraphCanvas.jsx')
    expect(gc).toContain('8 / globalScale')
  })
})
