/**
 * Phase 9 — Graph UX overhaul (Overview/All-Files modes, label decluttering,
 * layout physics)
 * QA automated checks against the Phase 9 acceptance criteria in PLAN.md and
 * the exact algorithms/thresholds in phase9_design_spec.md.
 *
 * Split into three kinds of checks:
 *  1. Real unit tests against the pure logic modules (`graphCuration.js`,
 *     `hierarchyLayout.js`) — given fixtures, does the CAP formula/ranking/
 *     expansion/scoping actually behave per spec.
 *  2. Rendered-component tests (React Testing Library) for the two
 *     non-canvas components touched this phase (`SymbolsTab.jsx`,
 *     `DocReader.jsx`) — real behavior, not just source grep.
 *  3. Structural source-assertions for the canvas-based wiring that can't be
 *     meaningfully unit-tested (react-force-graph-2d does not render in
 *     jsdom) — confirming the reviewer's MAJOR/MINOR fixes are still present
 *     in the code, matching the existing project convention used in
 *     phase6/7/8 test files for this exact category of check.
 *
 * Run: cd frontend && npx vitest run phase9
 */

import { readFileSync } from 'fs'
import { resolve } from 'path'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import {
  idOf,
  computeDegree,
  curateFiles,
  curateOverview,
} from '../lib/graphCuration.js'
import {
  HIERARCHY_NODE_THRESHOLD,
  computeHierarchyPositions,
  seedHierarchyPositions,
} from '../lib/hierarchyLayout.js'
import { SymbolsTab } from '../components/tabs/SymbolsTab.jsx'
import { DocReader } from '../components/DocReader.jsx'

const SRC = resolve(__dirname, '..')

function src(relPath) {
  return readFileSync(resolve(SRC, relPath), 'utf8')
}

function fileNode(id, importance = null) {
  return { id, type: 'file', path: `src/${id}.js`, importance }
}

function dirNode(id, path) {
  return { id, type: 'dir', path }
}

// ---------------------------------------------------------------------------
// graphCuration.js — idOf / computeDegree
// ---------------------------------------------------------------------------

describe('graphCuration.idOf', () => {
  it('extracts .id from an object endpoint', () => {
    expect(idOf({ id: 'abc' })).toBe('abc')
  })
  it('returns a plain string endpoint unchanged', () => {
    expect(idOf('abc')).toBe('abc')
  })
})

describe('graphCuration.computeDegree', () => {
  it('counts in-degree + out-degree per id, ignoring ids outside the given set', () => {
    const ids = ['a', 'b', 'c']
    const edges = [
      { source: 'a', target: 'b' },
      { source: 'b', target: 'c' },
      { source: 'c', target: 'a' },
      { source: 'a', target: 'zzz-not-in-set' }, // should not create a 'zzz' entry, and should still count toward 'a'
    ]
    const degree = computeDegree(ids, edges)
    expect(degree.get('a')).toBe(3) // a->b, c->a, a->zzz
    expect(degree.get('b')).toBe(2) // a->b, b->c
    expect(degree.get('c')).toBe(2) // b->c, c->a
    expect(degree.has('zzz-not-in-set')).toBe(false)
  })

  it('tolerates object-shaped edge endpoints ({id} not just plain strings)', () => {
    const ids = ['a', 'b']
    const edges = [{ source: { id: 'a' }, target: { id: 'b' } }]
    const degree = computeDegree(ids, edges)
    expect(degree.get('a')).toBe(1)
    expect(degree.get('b')).toBe(1)
  })

  it('returns zero for every id when there are no edges', () => {
    const degree = computeDegree(['a', 'b'], [])
    expect(degree.get('a')).toBe(0)
    expect(degree.get('b')).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// graphCuration.js — curateFiles: CAP formula (design spec §3, Q3)
//   CAP = clamp(round(0.4 * total), 8, 40)
// ---------------------------------------------------------------------------

describe('graphCuration.curateFiles — CAP formula', () => {
  it('floors at 8 for a small repo (total=20 -> raw CAP 8)', () => {
    const nodes = Array.from({ length: 20 }, (_, i) => fileNode(`f${i}`))
    const { curatedIds } = curateFiles(nodes, [], { hasImportance: false })
    expect(curatedIds.size).toBe(8)
  })

  it('scales linearly in the middle of the range (total=100 -> CAP 40, the ceiling)', () => {
    const nodes = Array.from({ length: 100 }, (_, i) => fileNode(`f${String(i).padStart(3, '0')}`))
    const { curatedIds } = curateFiles(nodes, [], { hasImportance: false })
    expect(curatedIds.size).toBe(40)
  })

  it('ceilings at 40 even for a very large repo (total=200 -> raw CAP 80, clamped to 40)', () => {
    const nodes = Array.from({ length: 200 }, (_, i) => fileNode(`f${String(i).padStart(3, '0')}`))
    const { curatedIds } = curateFiles(nodes, [], { hasImportance: false })
    expect(curatedIds.size).toBe(40)
  })

  it('never selects more nodes than actually exist (total=5, raw CAP would floor to 8)', () => {
    const nodes = Array.from({ length: 5 }, (_, i) => fileNode(`f${i}`))
    const { curatedIds } = curateFiles(nodes, [], { hasImportance: false })
    expect(curatedIds.size).toBe(5)
  })

  it('returns an empty result for an empty pool without throwing', () => {
    const { curatedIds, edges } = curateFiles([], [], { hasImportance: false })
    expect(curatedIds.size).toBe(0)
    expect(edges).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// graphCuration.js — curateFiles: importance-ranked vs degree-ranked (Q1/Q2)
// ---------------------------------------------------------------------------

describe('graphCuration.curateFiles — importance ranking', () => {
  it('selects the top-CAP nodes by importance descending when hasImportance=true', () => {
    // 10 nodes, importance 10..1 descending; CAP for total=10 is 8.
    const nodes = Array.from({ length: 10 }, (_, i) => fileNode(`f${i}`, 10 - i))
    const { curatedIds } = curateFiles(nodes, [], { hasImportance: true })
    expect(curatedIds.size).toBe(8)
    // f0..f7 have importance 10..3, the top 8 — f8 (importance 2) and f9 (importance 1) excluded.
    for (let i = 0; i < 8; i++) expect(curatedIds.has(`f${i}`)).toBe(true)
    expect(curatedIds.has('f8')).toBe(false)
    expect(curatedIds.has('f9')).toBe(false)
  })

  it('breaks importance ties by degree (higher degree wins the slot)', () => {
    // 9 nodes all importance=5 (CAP for total=9 -> round(3.6)=4, clamped to 8, so CAP=8;
    // total=9 means exactly one node is excluded). Give one node zero edges so it's the
    // lowest-degree / lowest-id tiebreak loser.
    const nodes = Array.from({ length: 9 }, (_, i) => fileNode(`f${i}`, 5))
    // Connect f0..f7 to each other in a chain (each gets degree >= 1); leave f8 with 0 edges.
    const edges = []
    for (let i = 0; i < 7; i++) edges.push({ source: `f${i}`, target: `f${i + 1}` })
    const { curatedIds } = curateFiles(nodes, edges, { hasImportance: true })
    expect(curatedIds.size).toBe(8)
    expect(curatedIds.has('f8')).toBe(false) // zero-degree node loses the tiebreak
  })

  it('falls back to id (localeCompare) as the final tiebreak when score and degree are equal', () => {
    // All same importance, all zero degree (no edges) -> pure id-order tiebreak.
    // total=10 -> CAP=8, so the two highest ids (lexicographically last) are excluded.
    const nodes = Array.from({ length: 10 }, (_, i) => fileNode(`f${i}`, 5))
    const { curatedIds } = curateFiles(nodes, [], { hasImportance: true })
    expect(curatedIds.size).toBe(8)
    expect(curatedIds.has('f8')).toBe(false)
    expect(curatedIds.has('f9')).toBe(false)
    for (let i = 0; i < 8; i++) expect(curatedIds.has(`f${i}`)).toBe(true)
  })
})

describe('graphCuration.curateFiles — degree fallback ranking (hasImportance=false)', () => {
  it('selects the top-CAP nodes by degree descending, ignoring importance entirely', () => {
    // 10 nodes; give importance in the OPPOSITE order of degree, to prove degree (not
    // importance) drives the ranking when hasImportance=false.
    const nodes = Array.from({ length: 10 }, (_, i) => fileNode(`f${i}`, i)) // f0 lowest importance ... f9 highest
    // Star topology centered on f0..f7 (high degree), f8/f9 isolated (degree 0).
    const edges = []
    for (let i = 0; i < 8; i++) {
      edges.push({ source: 'hub', target: `f${i}` }) // gives f0..f7 degree 1 each — hub isn't in the pool
    }
    // give f0 extra edges so ranking is unambiguous
    edges.push({ source: 'f0', target: 'f1' }, { source: 'f0', target: 'f2' })
    const { curatedIds } = curateFiles(nodes, edges, { hasImportance: false })
    expect(curatedIds.size).toBe(8)
    // f8 and f9 have degree 0 and should be excluded despite having the highest importance.
    expect(curatedIds.has('f8')).toBe(false)
    expect(curatedIds.has('f9')).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// graphCuration.js — 1-hop expansion (design spec §3)
// ---------------------------------------------------------------------------

describe('graphCuration.curateFiles — 1-hop neighbor expansion', () => {
  it('pulls in a low-score neighbor directly connected to a core node', () => {
    // 10 nodes, CAP=8 (top-8 by importance). f8 is a low-score node connected to
    // core node f0 -> should be expanded in. f9 is low-score and NOT connected ->
    // stays excluded.
    const nodes = Array.from({ length: 10 }, (_, i) => fileNode(`f${i}`, 10 - i))
    const edges = [{ source: 'f0', target: 'f8' }]
    const { curatedIds } = curateFiles(nodes, edges, { hasImportance: true })
    expect(curatedIds.has('f8')).toBe(true)
    expect(curatedIds.has('f9')).toBe(false)
  })

  it('expansion works in both edge directions (core as target, not just source)', () => {
    const nodes = Array.from({ length: 10 }, (_, i) => fileNode(`f${i}`, 10 - i))
    const edges = [{ source: 'f8', target: 'f0' }] // core (f0) is the edge target this time
    const { curatedIds } = curateFiles(nodes, edges, { hasImportance: true })
    expect(curatedIds.has('f8')).toBe(true)
  })

  it('caps total curated size at round(CAP * 1.5) even with many eligible neighbors', () => {
    // 100 nodes, CAP=40, expansionCap=60. Connect every one of the 60 non-core
    // nodes to a core node so all of them are eligible for expansion, then assert
    // the result stops at exactly 60, not 100.
    const nodes = Array.from({ length: 100 }, (_, i) => fileNode(`f${String(i).padStart(3, '0')}`, 100 - i))
    const edges = []
    for (let i = 40; i < 100; i++) {
      edges.push({ source: 'f000', target: `f${String(i).padStart(3, '0')}` })
    }
    const { curatedIds } = curateFiles(nodes, edges, { hasImportance: true })
    expect(curatedIds.size).toBe(60)
  })

  it('curated edges output only includes edges where both endpoints survived curation', () => {
    const nodes = Array.from({ length: 10 }, (_, i) => fileNode(`f${i}`, 10 - i))
    const edges = [
      { source: 'f0', target: 'f1' },     // both in core -> kept
      { source: 'f8', target: 'f9' },     // both excluded, neither connected to core -> dropped
    ]
    const { edges: curatedEdges } = curateFiles(nodes, edges, { hasImportance: true })
    expect(curatedEdges).toEqual([{ source: 'f0', target: 'f1' }])
  })
})

// ---------------------------------------------------------------------------
// graphCuration.js — scopeFileIds (drill-in recursion, design spec §7)
// ---------------------------------------------------------------------------

describe('graphCuration.curateFiles — scopeFileIds restricts pool and expansion', () => {
  it('only ranks/selects files within the given scope', () => {
    const nodes = Array.from({ length: 10 }, (_, i) => fileNode(`f${i}`, 10 - i))
    const scope = new Set(['f5', 'f6', 'f7', 'f8', 'f9']) // scope = the bottom-importance half
    const { curatedIds } = curateFiles(nodes, [], { hasImportance: true, scopeFileIds: scope })
    // CAP for a pool of 5 is clamp(round(2),8,40)=8, but pool only has 5 -> all 5 selected.
    expect(curatedIds.size).toBe(5)
    for (const id of curatedIds) expect(scope.has(id)).toBe(true)
    expect(curatedIds.has('f0')).toBe(false) // outside scope, despite highest importance
  })

  it('never expands outside the given scope even if an edge points out of it', () => {
    const nodes = Array.from({ length: 10 }, (_, i) => fileNode(`f${i}`, 10 - i))
    const scope = new Set(['f5', 'f6'])
    const edges = [{ source: 'f5', target: 'f0' }] // f0 is outside scope
    const { curatedIds } = curateFiles(nodes, edges, { hasImportance: true, scopeFileIds: scope })
    expect(curatedIds.has('f0')).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// graphCuration.js — curateOverview: top-level dirs + curated files
// ---------------------------------------------------------------------------

describe('graphCuration.curateOverview', () => {
  it('always includes depth-0 directories but excludes nested directories', () => {
    const nodes = [
      dirNode('d1', 'src'),
      dirNode('d2', 'src/components'), // nested — should NOT be auto-included
      ...Array.from({ length: 5 }, (_, i) => fileNode(`f${i}`)),
    ]
    const { nodeIds } = curateOverview(nodes, [], { hasImportance: false })
    expect(nodeIds.has('d1')).toBe(true)
    expect(nodeIds.has('d2')).toBe(false)
  })

  it('merges top-level dirs with curateFiles output for the file portion', () => {
    const nodes = [
      dirNode('d1', 'src'),
      ...Array.from({ length: 5 }, (_, i) => fileNode(`f${i}`)),
    ]
    const { nodeIds, curatedFileIds } = curateOverview(nodes, [], { hasImportance: false })
    expect(curatedFileIds.size).toBe(5) // total files (5) < CAP floor (8) -> all included
    for (const id of curatedFileIds) expect(nodeIds.has(id)).toBe(true)
    expect(nodeIds.size).toBe(6) // 1 dir + 5 files
  })

  it('returns an empty-but-valid result when given zero nodes', () => {
    const { nodeIds, curatedFileIds, edges } = curateOverview([], [], { hasImportance: false })
    expect(nodeIds.size).toBe(0)
    expect(curatedFileIds.size).toBe(0)
    expect(edges).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// hierarchyLayout.js — node-count gating (design spec Q7, HIERARCHY_NODE_THRESHOLD)
// ---------------------------------------------------------------------------

describe('hierarchyLayout — threshold gating', () => {
  it('exposes a threshold of 60, matching the design spec', () => {
    expect(HIERARCHY_NODE_THRESHOLD).toBe(60)
  })

  it('seedHierarchyPositions is a no-op at or below the threshold', () => {
    const nodes = Array.from({ length: 60 }, (_, i) => ({ id: `f${i}`, type: 'file', path: `src/f${i}.js` }))
    seedHierarchyPositions(nodes, { width: 800, height: 600 })
    for (const n of nodes) {
      expect(n.x).toBeUndefined()
      expect(n.y).toBeUndefined()
    }
  })

  it('seedHierarchyPositions assigns x/y to every node above the threshold', () => {
    const nodes = Array.from({ length: 61 }, (_, i) => ({ id: `f${i}`, type: 'file', path: `src/f${i}.js` }))
    seedHierarchyPositions(nodes, { width: 800, height: 600 })
    for (const n of nodes) {
      expect(typeof n.x).toBe('number')
      expect(typeof n.y).toBe('number')
    }
  })

  it('does not overwrite a node that already has a position (would fight the running simulation)', () => {
    const nodes = Array.from({ length: 61 }, (_, i) => ({ id: `f${i}`, type: 'file', path: `src/f${i}.js` }))
    nodes[0].x = 12345
    nodes[0].y = 6789
    seedHierarchyPositions(nodes, { width: 800, height: 600 })
    expect(nodes[0].x).toBe(12345)
    expect(nodes[0].y).toBe(6789)
  })

  it('does not throw and returns an empty map for an empty node list', () => {
    const positions = computeHierarchyPositions([], { width: 800, height: 600 })
    expect(positions.size).toBe(0)
  })

  it('computes a distinct position for each dir/file node in a small folder tree', () => {
    const nodes = [
      dirNode('d1', 'src'),
      fileNode('a'),
      fileNode('b'),
    ]
    nodes[1].path = 'src/a.js'
    nodes[2].path = 'src/b.js'
    const positions = computeHierarchyPositions(nodes, { width: 800, height: 600 })
    expect(positions.size).toBe(3)
    expect(positions.has('d1')).toBe(true)
    expect(positions.has('a')).toBe(true)
    expect(positions.has('b')).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// SymbolsTab.jsx — symbols shape-tolerance fix (deliverable 9) + search filter
// (rendered-component test, not just source grep — this is real user behavior)
// ---------------------------------------------------------------------------

describe('SymbolsTab — symbol shape tolerance + search filter', () => {
  afterEach(() => cleanup())

  const nodes = [
    { id: 'n1', type: 'file', path: 'api/auth.py', symbols: ['JWTAuthenticator', 'verify_session'] },
    { id: 'n2', type: 'file', path: 'api/db.py', symbols: [{ name: 'connect', kind: 'FUNCTION' }] },
  ]

  it('renders real symbol names for plain-string symbol entries (not blank rows)', () => {
    render(<SymbolsTab nodes={nodes} onNodeSelect={() => {}} />)
    expect(screen.getByText('JWTAuthenticator')).toBeInTheDocument()
    expect(screen.getByText('verify_session')).toBeInTheDocument()
  })

  it('renders real symbol names for object-shaped symbol entries too', () => {
    render(<SymbolsTab nodes={nodes} onNodeSelect={() => {}} />)
    expect(screen.getByText('connect')).toBeInTheDocument()
  })

  it('search input filters rows by typed text on every keystroke', () => {
    render(<SymbolsTab nodes={nodes} onNodeSelect={() => {}} />)
    const input = screen.getByLabelText('Filter symbols')
    fireEvent.change(input, { target: { value: 'verify' } })
    expect(screen.getByText('verify_session')).toBeInTheDocument()
    expect(screen.queryByText('JWTAuthenticator')).not.toBeInTheDocument()
    expect(screen.queryByText('connect')).not.toBeInTheDocument()
  })

  it('shows the empty-match message when the search matches nothing', () => {
    render(<SymbolsTab nodes={nodes} onNodeSelect={() => {}} />)
    const input = screen.getByLabelText('Filter symbols')
    fireEvent.change(input, { target: { value: 'zzz-nonexistent' } })
    expect(screen.getByText('No symbols match "zzz-nonexistent".')).toBeInTheDocument()
  })

  it('does not throw a duplicate-key error for two different files sharing a symbol name', () => {
    // Regression guard for the reviewer-flagged key={sym.name} duplicate-key bug —
    // rows must key on nodeId+name+index, not name alone.
    const dupNodes = [
      { id: 'n1', type: 'file', path: 'a.py', symbols: ['run'] },
      { id: 'n2', type: 'file', path: 'b.py', symbols: ['run'] },
    ]
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<SymbolsTab nodes={dupNodes} onNodeSelect={() => {}} />)
    const duplicateKeyWarning = errorSpy.mock.calls.some(call =>
      call.some(arg => typeof arg === 'string' && arg.includes('same key'))
    )
    expect(duplicateKeyWarning).toBe(false)
    errorSpy.mockRestore()
  })
})

// ---------------------------------------------------------------------------
// DocReader.jsx — Key Symbols shape-tolerance fix (deliverable 9)
// (rendered-component test; fetch is mocked so useDoc's request never
// resolves and never throws inside jsdom)
// ---------------------------------------------------------------------------

describe('DocReader — Key Symbols shape tolerance', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('shows real symbol names for plain-string symbols.entries (not blank)', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {}))) // never resolves — loading state is fine for this check
    const node = {
      id: 'n1', type: 'file', path: 'cli.py',
      symbols: ['main', 'init', 'update', 'serve'],
    }
    render(
      <DocReader
        node={node}
        isOpen={true}
        onClose={() => {}}
        nodes={[node]}
        edges={[]}
        staleMap={new Map()}
        onNodeSelect={() => {}}
        repoRoot={null}
      />
    )
    expect(screen.getByText('main')).toBeInTheDocument()
    expect(screen.getByText('init')).toBeInTheDocument()
    expect(screen.getByText('update')).toBeInTheDocument()
    expect(screen.getByText('serve')).toBeInTheDocument()
    // Plain-string symbols have no kind — badge should fall back to the
    // generic "SYMBOL" placeholder, not blow up.
    expect(screen.getAllByText('SYMBOL').length).toBe(4)
  })

  it('does not render a Key Symbols section at all when node.symbols is empty', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    const node = { id: 'n1', type: 'file', path: 'empty.py', symbols: [] }
    render(
      <DocReader
        node={node}
        isOpen={true}
        onClose={() => {}}
        nodes={[node]}
        edges={[]}
        staleMap={new Map()}
        onNodeSelect={() => {}}
        repoRoot={null}
      />
    )
    expect(screen.queryByText('Key Symbols')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Structural checks — reviewer's fix-pass items still present in the code
// (react-force-graph-2d cannot meaningfully render in jsdom, so the
// canvas-drawing wiring itself is verified structurally, matching the
// existing phase6/7/8 convention for this category of check — NOT a
// substitute for the live-browser visual pass.)
// ---------------------------------------------------------------------------

describe('Structural — GraphCanvas.jsx reviewer fix-pass items', () => {
  const gc = src('components/GraphCanvas.jsx')

  it('[MAJOR fix] zoomToFit gates on a content signature that excludes pulse-only nodes', () => {
    expect(gc).toContain('graphSignature')
    expect(gc).toMatch(/excluded\s*=\s*new Set\(\[\.\.\.pulseMap\.keys\(\),\s*\.\.\.pulseAncestorIds\]\)/)
  })

  it('[MINOR fix] node.__degree label-priority is wired to a real computeDegree map, not a no-op constant', () => {
    expect(gc).toContain('degreeMap.get(node.id)')
    expect(gc).toContain("import { computeDegree, idOf } from '../lib/graphCuration.js'")
  })

  it('collision force is keyed to each node\'s actual rendered radius, not a fixed constant', () => {
    expect(gc).toMatch(/forceCollide\(node => nodeRadius\(node\)/)
  })

  it('[bugfix] a weak centering force reels in disconnected nodes/components instead of letting them drift', () => {
    expect(gc).toContain("import { forceCollide, forceX, forceY } from 'd3-force-3d'")
    expect(gc).toMatch(/d3Force\('x',\s*forceX\(dims\.width \/ 2\)\.strength\(0\.02\)\)/)
    expect(gc).toMatch(/d3Force\('y',\s*forceY\(dims\.height \/ 2\)\.strength\(0\.02\)\)/)
  })

  it('directory badge is split into a centered arrow + a separate satellite count circle', () => {
    expect(gc).toContain("fillText('▶'")
    expect(gc).toMatch(/node\.x \+ r \* 0\.72/)
    expect(gc).toMatch(/node\.y \+ r \* 0\.72/)
  })

  it('hover tooltip safety valve is wired (independent of the zoom threshold)', () => {
    expect(gc).toContain('onNodeHover')
  })
})

describe('Structural — ExplorerTab.jsx mode toggle + pulse-reveal', () => {
  const et = src('components/tabs/ExplorerTab.jsx')

  it('explorerMode defaults to overview', () => {
    expect(et).toMatch(/useState\(['"]overview['"]\)/)
  })

  it('mode switch re-triggers zoomToFit', () => {
    expect(et).toMatch(/zoomToFit\(400, 60\)/)
  })

  it('[MINOR fix] pulse-reveal of a curated-out node also force-expands its ancestor chain', () => {
    expect(et).toContain('overviewEffectiveCollapsedMap')
    expect(et).toContain('pulseAncestorDirIds')
  })

  it('pulse-reveal banner uses the exact copy from the design spec', () => {
    expect(et).toContain('outside curated view')
    expect(et).toContain('Show in All Files')
  })
})
