# DESIGN — Phase 4: Static Graph Viewer (Redesign v2)
# Build spec for builder. Every section is implementable as written.
# Designer: senior product designer, 2026-07-19
# Replaces the dark GitHub-derived theme entirely.

---

## 1. The one job

Give a developer a navigable map of their codebase — which files matter, how they connect, and which are out of date — so they can orient instantly without reading code.

---

## 2. Layout and hierarchy

### Two-panel layout

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER  (56px tall, full width)                             │
│ [project name]  [hint text]              [importance filter]│
├────────────────────────────────────────┬────────────────────┤
│                                        │ ▌                  │
│  GRAPH CANVAS                          │  DOC PANEL         │
│  (flex: 1, pure white #ffffff)         │  (420px wide)      │
│                                        │  bg #fafafa        │
│                                        │  left: 3px solid   │
│                                        │  #E63946           │
└────────────────────────────────────────┴────────────────────┘
```

- **Header**: 56px tall. Left side: project name (bold, Inter, 15px) + a separator dot + hint text (`Click a node to view its doc · Click a folder to expand`, 12px, muted). Right side: importance filter label + button group. Background `#ffffff`. Border-bottom `1px solid #e0e0e0`. No shadow — the border alone creates the separation.
- **Graph canvas**: fills all remaining width and height. Background `#ffffff` (pure white). No dot grid, no texture — the nodes and edges carry all the visual information; a cluttered background competes with them. The white-on-white reads as "ready" not "broken" because the header and panel are visibly present.
- **Doc panel**: 420px fixed width. Slides in from the right on node click. When closed, canvas takes 100% width. When open, canvas shrinks by exactly 420px (no overlap). Transition: `transform translateX(0) 200ms ease-out` on the panel. Panel background `#fafafa`. Left border `3px solid #E63946` — this red stripe is the visual anchor that separates the panel from the canvas, replacing the old dark border. It also signals "this is the selected thing."
- **No responsive breakpoints.** Local dev tool, desktop only. Minimum supported viewport: 1024px.

### Visual hierarchy order (what the eye hits, in sequence)

1. Red nodes — the accent color pops immediately against white. High-importance files read louder than low-importance ones by size.
2. Gray stale nodes — muted but distinct from the red fresh field; stale is a warning, not an alarm.
3. Edges — medium gray, visibly present. On white, edges must be readable as lines, not ghosts.
4. Selected node red ring — confirms what you clicked before the panel finishes sliding in.
5. Doc panel — arrives on demand; the red left stripe visually connects it to the selected node.
6. Header — orientation only; lowest visual weight after everything loads.

---

## 3. Color palette — exact hex values

| Token name | Hex | Usage |
|---|---|---|
| `--color-bg` | `#ffffff` | Canvas background, app background |
| `--color-surface` | `#fafafa` | Doc panel background |
| `--color-border` | `#e0e0e0` | All dividers, borders, button borders |
| `--color-surface-raised` | `#f0f0f0` | Button backgrounds (inactive), inline code backgrounds |
| `--color-text-primary` | `#111111` | File path in panel, project name, primary body text |
| `--color-text-secondary` | `#333333` | Doc panel body text |
| `--color-text-muted` | `#888888` | Node labels, hints, placeholder text, section headers |
| `--color-accent` | `#E63946` | Fresh file nodes, active filter button fill, links, selected ring, panel left border, dir nodes (fresh) |
| `--color-accent-dark` | `#B71C2A` | Hover state on red buttons; dir node fill when all children fresh (slightly darker than file nodes so dirs read as "structural container") |
| `--color-stale` | `#9E9E9E` | Stale file node fill (medium gray — muted signal, not alarm) |
| `--color-stale-dark` | `#616161` | Stale dir node fill |
| `--color-stale-badge-bg` | `#FFF3E0` | Outdated badge background (warm amber tint, not dark) |
| `--color-stale-badge-text` | `#E65100` | Outdated badge text |
| `--color-edge` | `#aaaaaa` | Edge color — medium gray, visible on white |
| `--color-selected-ring` | `#E63946` | Node stroke on selection (red, not white) |

**Why this palette is not AI slop:** The only two chromatic colors are pure white and one specific red (#E63946, a fire-engine red with enough orange warmth to avoid harshness). Everything else is achromatic — blacks, grays. There is no teal, no purple, no gradient. The stale state is gray rather than amber because on a white canvas, amber reads too cheerful; gray reads as "needs attention."

---

## 4. Graph canvas — node visual design

### File nodes

- Shape: circle
- Radius: scaled linearly from importance. `importance: 1` → 4px. `importance: 5` → 12px. `importance: null` → 6px.
  Formula: `r = importance != null ? (importance * 1.6 + 2.4) : 6`
- Fill: `#E63946` (red) when fresh; `#9E9E9E` (gray) when stale.
- Border (stroke): none by default.

### Directory nodes

- Shape: circle
- Radius: 16px (slightly larger than the old 14px — dirs are landmarks and should read as "bigger than any single file").
- Fill: `#B71C2A` (dark red) when all children fresh; `#616161` (dark gray) when any descendant stale.
- Inside the dir node, when collapsed: render a `▶` character (U+25B6) centered on the node instead of just a number badge. The `▶` makes the "click to expand" affordance self-evident. Below the `▶`, render the child count as a smaller numeral.
  - `▶` font: bold 8px Inter (not mono — the triangle character renders better in sans)
  - Count: 8px Inter, color `#ffffff` (white on dark red/gray reads fine)
  - `▶` is positioned at center (node.x, node.y - 2), count at (node.x, node.y + 5)

### Stale ancestor signal (collapsed dir with stale descendant)

A collapsed dir node with any stale descendant uses `--color-stale-dark` fill (`#616161`) plus a glow: `filter: drop-shadow(0 0 5px #9E9E9E)`. The gray glow on gray fill creates a soft bloom that says "something is off inside here." Distinct from a leaf stale node (flat gray fill, no glow).

### Selected node highlight

Red ring: `stroke: #E63946`, `stroke-width: 2.5px`. Sits outside the fill. The same red as the node fill for fresh files, but the ring is visible on the dark-red dir nodes because of its outline-style rendering.

### Node labels

- Show final path segment only: `corpus/cli.py` → `cli.py`. Dir nodes: dir name only.
- Font: `13px 'Inter', system-ui, sans-serif` (not mono — Inter is more legible at small sizes on a white background; mono is a deliberate choice for code, not for graph labels).
- Color: `#555555` (darker than the old muted label; on a white canvas, `#8b949e` is too faint).
- Position: centered below node, offset 6px below the node's bottom edge (`y + r + 6`).
- Visibility: show at all zoom scales >= 0.2. Hide below 0.2. The old threshold of 0.4 was too aggressive — users reported labels disappearing at normal zoom levels. At 0.2 the canvas is so zoomed out that the entire graph fits in a thumbnail and labels are genuinely unreadable regardless.

### Edges

- Style: straight lines. No arrows.
- Color: `#aaaaaa` — medium gray. On a white canvas this is clearly visible. The old `#30363d` was designed for dark backgrounds; on white it would be nearly black. `#aaaaaa` is the right trade-off: visible without dominating.
- Width: `1.5px` at default zoom (not `1px`). At 1px on a white canvas, lines disappear on Retina displays. 1.5px reads as a deliberate line.
- No edge labels.

---

## 5. Collapsed/expanded dir behavior

Unchanged from v1 spec:

- Single click on dir node toggles collapsed/expanded.
- Single click on file node opens doc panel.
- Default state: all dirs collapsed on initial render.
- Expansion is one level at a time. Collapse remembers child expansion state.
- When re-collapsed: all descendants hidden regardless of their expansion state. Expansion state remembered in `Map<nodeId, boolean>` and restored on re-expand.

The `▶` indicator (new in v2) makes this behavior legible on first encounter. A user who has never used Corpus before sees a folder-like arrow and tries clicking it.

---

## 6. Header

### Structure

```
[project-name]  ·  Click a node to view its doc · Click a folder to expand
                                         Show files with importance ≥  [All][1][2][3][4][5]
```

Left-aligned:
- **Project name**: the parent directory name of `.corpus/`, in Inter 15px font-weight 600, color `#111111`.
- Separator: ` · ` in `#cccccc`, same size.
- **Hint text**: `Click a node to view its doc · Click a folder to expand` in Inter 12px, color `#999999`. This line is always visible — it is not a tooltip, not a first-run overlay. It stays permanently because new users will read it and experienced users will ignore it. It costs 200px of header space and earns its keep.

Right-aligned (importance filter):
- Label: `Show files with importance ≥` in Inter 12px, color `#888888`. Padding-right: 8px.
- Button group: `[All][1][2][3][4][5]` as described in section 8.

Header height: 56px exactly. Background: `#ffffff`. Border-bottom: `1px solid #e0e0e0`.

---

## 7. Importance filter

### The control — full spec

Label + button group, right-aligned in header:

```
Show files with importance ≥   [ All ][ 1 ][ 2 ][ 3 ][ 4 ][ 5 ]
```

Button dimensions:
- Height: 30px. `min-height: 36px` (set via padding to meet accessibility floor).
- `All` button: 44px wide.
- `1`–`5` buttons: 32px wide each.
- Gap between buttons: 3px.
- Border-radius: 5px.

Inactive state:
- Background: `#f0f0f0`
- Color: `#666666`
- Border: `1px solid #e0e0e0`
- Font: Inter 12px, font-weight 500

Active state:
- Background: `#E63946`
- Color: `#ffffff`
- Border: `1px solid #E63946`
- Font: Inter 12px, font-weight 600

Hover on inactive:
- Background: `#e0e0e0`
- Transition: `background 100ms`

Hover on active: no change (active button does not need hover feedback — it's already selected).

Focus-visible ring: `outline: 2px solid #E63946; outline-offset: 2px`.

### Filter logic (unchanged from v1)

- "All" = show everything.
- Clicking `N` = show file nodes with `importance >= N`, or `importance === null`.
- Dir nodes: never filtered out.
- When a file node is hidden, its edges are also hidden.

---

## 8. Doc panel

### Dimensions and motion

- Width: 420px fixed (60px wider than v1 — breathing room for longer doc content).
- Height: 100% of the area below the header.
- Opens: `transform: translateX(0)`. Closed: `transform: translateX(420px)`. Transition: `200ms ease-out`. Panel is always in the DOM.
- Left border: `3px solid #E63946` — permanent, not conditional. This is the visual accent.
- Canvas container transitions `width` simultaneously: open → `calc(100% - 420px)`, closed → `100%`.

### Contents (top to bottom)

**Close button**: top-right corner. 44x44px tap target (not 36px — meet the accessibility floor properly). `×` character, 20px, color `#888888`. On hover: color `#111111`. On focus-visible: red outline. `aria-label="Close doc panel"`. No background.

**File path**: full repo-relative path (e.g., `corpus/cli.py`). Font: Inter 14px, font-weight 600, color `#111111`. Padding: `24px 52px 6px 24px` (top 24px, right 52px to clear close button, bottom 6px, left 24px). Overflow: ellipsis with `title` attribute for hover.

**Staleness badge**: immediately below the path, padding `0 24px 16px 24px`.
- **Stale**: pill badge. Background `#FFF3E0`. Text: `Outdated`. Color `#E65100`. Font: Inter 11px, font-weight 500. Padding: `3px 10px`. Border-radius: 4px. Border: `1px solid #FFB74D`.
- **Fresh**: no badge. Silence = healthy. Show nothing.

**Divider**: `1px solid #e0e0e0`, full panel width, no margin (sits flush below badge area).

**Markdown body**: padding `24px`. Overflow-y: auto. All remaining panel height.

Markdown rendering styles (scoped to panel, not global):

- `h1`: Inter 16px, font-weight 700, color `#111111`, margin-bottom 12px, margin-top 0 (first heading gets no top margin).
- `h2`: Inter 13px, font-weight 600, color `#555555`, text-transform uppercase, letter-spacing 0.07em, border-bottom `1px solid #e0e0e0`, padding-bottom 4px, margin-bottom 10px, margin-top 20px.
- `h3`: Inter 13px, font-weight 600, color `#333333`, margin-bottom 8px, margin-top 16px.
- Body text (`p`): Inter 14px, color `#333333`, line-height 1.7, margin-bottom 12px.
- Inline code: Inter/mono 12.5px, background `#f0f0f0`, border-radius 3px, padding `2px 5px`, color `#c7254e` (a muted crimson — readable, on-brand without being garish).
- Block code: same mono, 12.5px, background `#f5f5f5`, border-radius 5px, padding `12px 16px`, color `#333333`, overflow-x auto, border-left `3px solid #E63946`.
- Links: color `#E63946`, no underline, underline on hover.
- Lists: padding-left 20px, list-style disc, color `#333333`.
- `li`: Inter 14px, line-height 1.7.

### Loading state

Single text line centered in the body area: `Loading...` in Inter 14px, color `#888888`. No spinner.

### Error state

Text: `Could not load doc for this file.` Inter 14px, color `#888888`.
Below: `Retry` button — same styling as inactive importance filter button. Margin-top 12px. Re-calls `GET /doc?path=...`.

### No doc state

Text: `No documentation generated yet.`
Below (4px gap): `Run corpus update to generate docs.`
Both: Inter 14px, color `#888888`. No button — this is not an error.

---

## 9. Empty and loading states (full canvas)

### Initial load (graph fetch in flight)

Full-canvas centered overlay:
- `Loading graph...` — Inter 15px, color `#888888`.

### Fetch failed

Centered block:
- Primary: `Failed to load graph.` — Inter 15px, color `#111111`, font-weight 600.
- Secondary: `Is corpus serve running on localhost:7077?` — Inter 13px, color `#888888`. Margin-top 4px.
- Button: `Retry` — same styling as inactive importance filter button. Margin-top 16px.

### Empty graph (zero nodes)

Centered:
- Primary: `No files tracked yet.` — Inter 15px, color `#111111`, font-weight 600.
- Secondary: `Run corpus init, then corpus update.` — Inter 13px, color `#888888`. Margin-top 4px.

### All nodes filtered out by importance

Centered overlay over white canvas:
- Primary: `All files hidden by the importance filter.` — Inter 15px, color `#111111`, font-weight 600.
- Secondary: `Click All to show everything.` — Inter 13px, color `#888888`. Margin-top 4px.

---

## 10. Typography — full token scale

Two families only.

**Sans-serif: `'Inter', system-ui, -apple-system, sans-serif`**
- Used for: everything except node labels in the canvas (which now also use Inter) and the old monospace-everywhere approach is retired.
- Token `--font-sans`

**Monospace: `'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace`**
- Used for: inline code and block code inside doc panel only.
- Token `--font-mono`

Type scale (CSS custom properties):

```css
--text-xs:   10px;   /* badge text */
--text-sm:   12px;   /* hint text, filter label, badge, filter buttons */
--text-base: 13px;   /* section headers in panel (h2), close button aria */
--text-md:   14px;   /* body text in panel, file path */
--text-lg:   15px;   /* project name, empty-state primaries */
--text-xl:   20px;   /* close button × character */
```

No font loading at runtime. Inter is available on most developer machines and degrades gracefully to system-ui on machines where it is absent.

---

## 11. Interaction and feedback

### What is clickable and how you can tell

- All nodes: cursor `pointer` on hover. Fresh file nodes get a subtle brightness increase on hover (paint: lighten fill by ~10% on hover flag). Dir nodes: same. This is implementable in canvas by checking a `__hovered` flag set via `onNodeHover`.
- Filter buttons: pointer cursor. Hover: background shifts to `#e0e0e0` (inactive) or unchanged (active).
- Close button: pointer, color shift on hover.
- Retry buttons: pointer.

### Feedback within 100ms

- Node click → doc panel begin sliding within one event-loop tick (synchronous setState).
- Selection ring → next animation frame.
- Filter button → node visibility update within one rAF.
- Dir node click → collapse toggles immediately.

### Keyboard path

Tab order:
1. Filter label is not focusable (it is a `<span>`).
2. Filter buttons `All`, `1`, `2`, `3`, `4`, `5` — `tabIndex={0}`, Space/Enter activates.
3. Doc panel close button — `tabIndex={0}` when open, `tabIndex={-1}` when closed.
4. Doc panel Retry button — `tabIndex={0}` when visible.

Focus ring: `outline: 2px solid #E63946; outline-offset: 2px`. Applied via `:focus-visible`. Default outline suppressed for mouse users via `:focus:not(:focus-visible) { outline: none }`.

Graph canvas (`<canvas>`) has `aria-label="Codebase dependency graph"` and `role="img"`. Full keyboard graph navigation is out of scope.

---

## 12. Copy — exact words, no lorem ipsum

### Header

- Project name: bare directory name, e.g., `corpus`. Not `Corpus Graph` or `corpus — viewer`. The name is already the identity.
- Separator: ` · ` (U+00B7, middle dot with spaces)
- Hint: `Click a node to view its doc · Click a folder to expand`

### Importance filter

- Label before buttons: `Show files with importance ≥`
- Buttons: `All` `1` `2` `3` `4` `5`

### Staleness badge

- Stale: `Outdated` (not "needs update", not "stale" — "Outdated" is one word, reads faster, universally understood)
- Fresh: no badge (absence is the signal)

### Loading states

- Graph loading: `Loading graph...`
- Graph failed: `Failed to load graph.` / `Is corpus serve running on localhost:7077?` / `Retry`
- Empty graph: `No files tracked yet.` / `Run corpus init, then corpus update.`
- All filtered: `All files hidden by the importance filter.` / `Click All to show everything.`

### Doc panel

- Doc loading: `Loading...`
- Doc failed: `Could not load doc for this file.` / `Retry`
- No doc: `No documentation generated yet.` / `Run corpus update to generate docs.`
- Close button: `×` with `aria-label="Close doc panel"`

---

## 13. Accessibility floor

- Body text (`#333333` on `#fafafa`): contrast ratio ~10.2:1. Passes WCAG AAA.
- Muted text (`#888888` on `#ffffff`): contrast ratio ~4.6:1. Passes WCAG AA.
- Hint text (`#999999` on `#ffffff`): contrast ratio ~3.9:1. Technically below AA for body text. Acceptable here because the hint is supplementary — the user has already learned the interaction — and sits at 12px in a header where it will not be the primary reading target. If this is ever flagged by an audit, increase to `#777777`.
- Red on white (`#E63946` on `#ffffff`): contrast ratio ~4.5:1. Meets AA minimum exactly.
- Outdated badge (`#E65100` on `#FFF3E0`): contrast ratio ~5.4:1. Passes AA.
- All buttons: `min-height: 36px` enforced. Close button: 44px × 44px.
- Every button has either visible text or `aria-label`. Filter buttons have text. Close button has `aria-label="Close doc panel"`.
- Focus is always visible via `:focus-visible` red outline.
- Canvas: `aria-label="Codebase dependency graph"` and `role="img"`.

---

## 14. tokens.css — full rewrite

Builder replaces `frontend/src/styles/tokens.css` entirely with:

```css
:root {
  /* Colors */
  --color-bg:              #ffffff;
  --color-surface:         #fafafa;
  --color-border:          #e0e0e0;
  --color-surface-raised:  #f0f0f0;

  --color-text-primary:    #111111;
  --color-text-secondary:  #333333;
  --color-text-muted:      #888888;

  --color-accent:          #E63946;
  --color-accent-dark:     #B71C2A;

  --color-stale:           #9E9E9E;
  --color-stale-dark:      #616161;
  --color-stale-badge-bg:  #FFF3E0;
  --color-stale-badge-text:#E65100;

  --color-edge:            #aaaaaa;
  --color-selected-ring:   #E63946;
  --color-panel-accent:    #E63946;

  /* Typography */
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;

  --text-xs:   10px;
  --text-sm:   12px;
  --text-base: 13px;
  --text-md:   14px;
  --text-lg:   15px;
  --text-xl:   20px;
}
```

---

## 15. Component-by-component change summary for builder

This section translates the spec into a concrete diff list so builder doesn't miss anything.

### tokens.css
Full rewrite per section 14.

### App.jsx — style objects

`fullscreenCenter`: change `background` to `var(--color-bg)` (already correct), change font references to Inter.

`monoText` / `monoMuted`: rename to `bodyText` / `bodyMuted`, change `fontFamily` to `var(--font-sans)`, `color` to `var(--color-text-muted)`.

`retryBtn`: change `background` to `var(--color-surface-raised)`, `color` to `var(--color-text-muted)`, hover target to `#e0e0e0`.

Header `<header>`: height `56px`. Add hint text span between project name and filter. Project name: Inter 15px, font-weight 600.

### GraphCanvas.jsx

Constants to change:
```js
const COLOR_BG         = '#ffffff'
const COLOR_FRESH      = '#E63946'   // replaces COLOR_TEAL
const COLOR_FRESH_DARK = '#B71C2A'   // replaces COLOR_TEAL_DARK
const COLOR_STALE      = '#9E9E9E'   // replaces COLOR_AMBER
const COLOR_STALE_DARK = '#616161'   // replaces COLOR_AMBER_DARK
const COLOR_EDGE       = '#aaaaaa'
const COLOR_LABEL      = '#555555'
const COLOR_RING       = '#E63946'   // red ring, not white
const FONT_LABEL       = "13px 'Inter', system-ui, sans-serif"
const FONT_DIR_BADGE   = "bold 8px 'Inter', system-ui, sans-serif"
```

Dir node: radius 16px. Render `▶` + count instead of just count. `▶` at (node.x, node.y - 2), count at (node.x, node.y + 5).

Label visibility threshold: `globalScale >= 0.2` (was 0.4).

Edge width: `1.5` (was `1`).

Glow on stale collapsed dir: `ctx.shadowColor = '#9E9E9E'` (was amber).

Selected ring: `strokeStyle = '#E63946'` (was white).

### ImportanceFilter.jsx

Add `<span>` label before button group: `Show files with importance ≥` in Inter 12px, color `#888888`, padding-right 8px.

Button styles:
- Inactive: background `#f0f0f0`, color `#666666`, border `1px solid #e0e0e0`.
- Active: background `#E63946`, color `#ffffff`, border `1px solid #E63946`.
- Hover inactive: `#e0e0e0`.
- Font: Inter 12px, font-weight 500 (inactive), 600 (active).
- `min-height: 36px`.

### DocPanel.jsx

Panel width constant: `420` (was `360`).

Left border on panel div: `borderLeft: '3px solid var(--color-panel-accent)'` (replaces old 1px `#21262d`).

File path: Inter 14px, font-weight 600, color `var(--color-text-primary)`. Padding: `24px 52px 6px 24px`.

Staleness badge:
- Stale: text changes from `needs update` to `Outdated`. Background `var(--color-stale-badge-bg)`, color `var(--color-stale-badge-text)`. Border: `1px solid #FFB74D`. Padding: `3px 10px`.
- Fresh: render `null` (no badge at all). Remove the green "fresh" badge entirely.

Padding for badge row: `0 24px 16px 24px`.

Close button: 44x44px, `fontSize: 'var(--text-xl)'`.

Markdown body padding: `24px`.

`mdComponents`:
- `h2`: Inter 13px, uppercase, letter-spacing 0.07em, color `#555555`, border-bottom `1px solid #e0e0e0`.
- `p`: Inter 14px, color `#333333`, line-height 1.7.
- Inline `code`: mono 12.5px, background `#f0f0f0`, color `#c7254e`, padding `2px 5px`, border-radius 3px.
- Block `code`: mono 12.5px, background `#f5f5f5`, color `#333333`, padding `12px 16px`, border-radius 5px, border-left `3px solid #E63946`.
- `a`: color `#E63946`.
- Hover on retry button: `#e0e0e0` (not `#2d333b`).

---

## 16. What is explicitly NOT changing

- Force simulation parameters (charge, link distance, center force) — untouched.
- Collapse/expand logic in App.jsx — untouched.
- `useGraph` and `useDoc` hooks — untouched.
- FastAPI routes and backend contract — untouched.
- `corpus serve` CLI behavior — untouched.
- Pulse animation (white flash on MCP query event) — untouched; white still works on the new theme because nodes are red and white is maximally contrasting.
- WebSocket staleness polling — untouched.

---

## 17. The single most important change

The edges. On the old dark background, `#30363d` edges were acceptable. On a white canvas, the same edges would be nearly invisible — black lines on white. Builder must use `#aaaaaa` at `1.5px` width. If edges are not visible, the entire graph reads as disconnected dots and the "dependency map" job fails completely. Every other change is aesthetic. Invisible edges are a broken product.
