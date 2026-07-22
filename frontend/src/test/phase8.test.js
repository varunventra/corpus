/**
 * Phase 8 — GitHub dark theme retrofit
 * QA automated checks against the Phase 8 acceptance criteria in PLAN.md.
 *
 * All checks are static source-code assertions — no browser required.
 * Browser-only ACs (visual contrast spot-check, live MCP pulse, solid header
 * on scroll, `npm run dev` rendering) are covered by their structural halves
 * here and noted as BROWSER-ONLY in the QA report.
 *
 * Run: cd frontend && npx vitest run phase8
 */

import { readFileSync } from 'fs'
import { resolve } from 'path'
import { describe, it, expect } from 'vitest'

const SRC  = resolve(__dirname, '..')           // frontend/src
const ROOT = resolve(SRC, '..')                 // frontend/

function src(relPath) {
  return readFileSync(resolve(SRC, relPath), 'utf8')
}

// ---------------------------------------------------------------------------
// AC — "grep -c 'faf5ee|EB Garamond|Manrope' tokens.css global.css index.html
//       returns 0 total matches" (verbatim acceptance criterion)
// ---------------------------------------------------------------------------

describe('AC — retired Sahara literals/fonts fully removed', () => {
  const targets = {
    'styles/tokens.css': src('styles/tokens.css'),
    'styles/global.css': src('styles/global.css'),
    'index.html': readFileSync(resolve(ROOT, 'index.html'), 'utf8'),
  }

  for (const [name, content] of Object.entries(targets)) {
    it(`${name} contains no faf5ee / EB Garamond / Manrope`, () => {
      expect(content, `faf5ee found in ${name}`).not.toMatch(/faf5ee/i)
      expect(content, `EB Garamond found in ${name}`).not.toMatch(/EB[+ ]Garamond/)
      expect(content, `Manrope found in ${name}`).not.toContain('Manrope')
    })
  }
})

// ---------------------------------------------------------------------------
// AC — outermost background is #0d1117 (structural half of the visual check)
// ---------------------------------------------------------------------------

describe('AC — GitHub-dark canvas background', () => {
  const tokens = src('styles/tokens.css')
  const global = src('styles/global.css')

  it('tokens.css defines --color-canvas-default: #0d1117', () => {
    expect(tokens).toMatch(/--color-canvas-default:\s*#0d1117/)
  })

  it('global.css body background uses var(--color-canvas-default), no literal', () => {
    expect(global).toContain('background: var(--color-canvas-default)')
    expect(global).not.toMatch(/#faf5ee/i)
  })
})

// ---------------------------------------------------------------------------
// AC — primary text is fg-default (#e6edf3) — structural half of the ~13:1
//      contrast spot-check
// ---------------------------------------------------------------------------

describe('AC — fg-default text tokens', () => {
  const tokens = src('styles/tokens.css')

  it('tokens.css defines --color-fg-default: #e6edf3', () => {
    expect(tokens).toMatch(/--color-fg-default:\s*#e6edf3/)
  })

  it('--color-text-primary is remapped to #e6edf3', () => {
    expect(tokens).toMatch(/--color-text-primary:\s*#e6edf3/)
  })
})

// ---------------------------------------------------------------------------
// Deliverable — new GH-spec tokens added verbatim to tokens.css
// ---------------------------------------------------------------------------

describe('Deliverable — new GitHub-dark primitive tokens in tokens.css', () => {
  const tokens = src('styles/tokens.css')

  const required = {
    '--color-success-fg': '#3fb950',
    '--color-success-emphasis': '#238636',
    '--color-danger-fg': '#f85149',
    '--color-danger-emphasis': '#da3633',
    '--color-attention-fg': '#d29922',
    '--color-done-fg': '#a371f7',
    '--color-canvas-inset': '#010409',
    '--color-btn-primary-bg': '#238636',
  }

  for (const [token, value] of Object.entries(required)) {
    it(`tokens.css defines ${token}: ${value}`, () => {
      expect(tokens).toMatch(new RegExp(`${token}:\\s*${value}`))
    })
  }

  it('tokens.css defines the shadow tokens (--shadow-resting, --shadow-overlay)', () => {
    expect(tokens).toMatch(/--shadow-resting:/)
    expect(tokens).toMatch(/--shadow-overlay:/)
  })
})

// ---------------------------------------------------------------------------
// Deliverable — typography collapses to the system stack (no display face)
// ---------------------------------------------------------------------------

describe('Deliverable — system font stack in tokens.css', () => {
  const tokens = src('styles/tokens.css')

  it('--font-headline is the system stack (starts with -apple-system)', () => {
    expect(tokens).toMatch(/--font-headline:\s*-apple-system,\s*BlinkMacSystemFont/)
  })

  it('--font-body is the system stack (starts with -apple-system)', () => {
    expect(tokens).toMatch(/--font-body:\s*-apple-system,\s*BlinkMacSystemFont/)
  })

  it('--font-mono is a monospace stack (ui-monospace / Consolas)', () => {
    expect(tokens).toMatch(/--font-mono:\s*ui-monospace/)
    expect(tokens).toContain('Consolas')
  })
})

// ---------------------------------------------------------------------------
// AC — stale rendering is GH attention amber (#d29922-family), not Sahara amber
// ---------------------------------------------------------------------------

describe('AC — stale colors are GH attention amber, Sahara amber gone', () => {
  const tokens = src('styles/tokens.css')

  it('stale badge tokens use the rgba(210,153,34,...) attention family', () => {
    expect(tokens).toMatch(/--color-stale-badge-bg:\s*rgba\(210,\s*153,\s*34,\s*0\.10\)/)
    expect(tokens).toMatch(/--color-stale-badge-border:\s*rgba\(210,\s*153,\s*34,\s*0\.20\)/)
    expect(tokens).toMatch(/--color-stale-badge-text:\s*#d29922/)
  })

  const staleConsumers = [
    'components/FileTree.jsx',
    'components/tabs/ExplorerTab.jsx',
    'components/tabs/OverviewTab.jsx',
    'components/DocReader.jsx',
  ]

  for (const file of staleConsumers) {
    it(`${file} contains no Sahara amber/badge literals (f59e0b / d97706 / 92400e / b45309)`, () => {
      const content = src(file)
      expect(content).not.toMatch(/f59e0b/i)
      expect(content).not.toMatch(/d97706/i)
      expect(content).not.toMatch(/92400e/i)
      expect(content).not.toMatch(/b45309/i)
    })
  }
})

// ---------------------------------------------------------------------------
// AC — live-wire pulse is GH success-green #3fb950 (structural half; the
//      actual MCP round-trip is BROWSER-ONLY)
// ---------------------------------------------------------------------------

describe('AC — pulse indicator remapped to GH success-green', () => {
  it('tokens.css --color-node-pulse is #3fb950', () => {
    const tokens = src('styles/tokens.css')
    expect(tokens).toMatch(/--color-node-pulse:\s*#3fb950/)
  })

  it('GraphCanvas COLOR_NODE_PULSE is #3fb950 and old teal is gone', () => {
    const gc = src('components/GraphCanvas.jsx')
    expect(gc).toMatch(/COLOR_NODE_PULSE\s*=\s*'#3fb950'/)
    expect(gc).not.toContain('#14b8a6')
  })

  it('pulse glow ring draw path still uses 14 / globalScale (behavior unchanged)', () => {
    const gc = src('components/GraphCanvas.jsx')
    expect(gc).toContain('14 / globalScale')
  })
})

// ---------------------------------------------------------------------------
// AC — DocReader sticky header: no blur/glassmorphism (spec §4)
// ---------------------------------------------------------------------------

describe('AC — no backdropFilter / blur in DocReader', () => {
  const dr = src('components/DocReader.jsx')

  it('DocReader.jsx contains no backdropFilter', () => {
    expect(dr).not.toContain('backdropFilter')
  })

  it('DocReader header background is the solid canvas-overlay token', () => {
    expect(dr).toContain("background: 'var(--color-canvas-overlay)'")
  })
})

// ---------------------------------------------------------------------------
// AC — no pill radii: search input ≤ 8px; container radii capped (spec §3)
// ---------------------------------------------------------------------------

describe('AC — border-radius caps (no pills, max 8px)', () => {
  it('App.jsx has no borderRadius: 9999 (pill) and no radius above 8', () => {
    const app = src('App.jsx')
    expect(app).not.toContain('borderRadius: 9999')
    // any numeric radius of 9 or 2+ digits would violate the 8px cap
    expect(app).not.toMatch(/borderRadius:\s*(9|\d{2,})/)
  })

  it('DocReader.jsx has no radius above 8 (12/10 literals from Sahara are gone)', () => {
    const dr = src('components/DocReader.jsx')
    expect(dr).not.toMatch(/borderRadius:\s*(9|\d{2,})/)
  })
})
