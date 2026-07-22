# DECISIONS (append-only — never edit or delete past entries)

> One entry per decision that a future session might otherwise relitigate: stack choices, architecture, data models, cut features, naming schemes. If an agent finds itself re-arguing something, the argument belongs here.

---

## 2026-07-16 — Python for engine + CLI + MCP server; React for frontend; no database
**Decision:** Engine, CLI, and MCP server are Python 3.11+. Frontend is React 18 + Vite. All storage is plain files (markdown + JSON) in `.corpus/`. No database of any kind.
**Why:** Python has the best tree-sitter bindings available. It is the developer's primary language. FastMCP makes MCP tool authoring trivial (decorated functions). Plain files are human-readable, git-diffable, greppable, and require zero infrastructure. React is the developer's existing frontend stack; a static build on localhost needs no hosting.
**Alternatives rejected:** Node.js engine (weaker tree-sitter bindings, not the developer's primary language). SQLite (adds tooling requirement, removes human-readability and git-diffability; query patterns are simple enough that JSON serves). A monolith serving both MCP and frontend from one process (MCP uses stdio owned by Claude Code; the sidecar must be a separate process that outlives Claude Code sessions).
**Revisit if:** tree-sitter Python bindings become unmaintained or a superior parsing library emerges; or if the developer switches primary language.

---

## 2026-07-16 — Node IDs are short random strings, never derived from paths
**Decision:** Every node in `graph.json` gets a short random ID (e.g. `n_04f2`) assigned at first sight. IDs never change. The `path` field is mutable. Edges reference IDs, not paths. MCP tools accept paths as input and resolve to IDs internally.
**Why:** If IDs were derived from paths, any file rename would destroy that node's history, importance rating, and changelog. Decoupling identity from location is the only way to make rename survival work correctly.
**Alternatives rejected:** Path-as-ID (destroys history on rename). Content-hash-as-ID (two identical files would collide; file is edited → ID changes, same problem as path). Incrementing integers (require a central counter, awkward for concurrent tooling).
**Revisit if:** The random ID space causes collisions in practice (astronomically unlikely at repo scale) or if a better stable identity signal emerges (e.g., git object hash for content identity).

---

## 2026-07-16 — Gemini 2.5 Flash primary LLM; Groq (Llama 3.3 70B) as automatic fallback on 429
**Decision:** LLM calls use a single `llm.generate(prompt, max_tokens)` wrapper. Provider is set in `corpus.yml`. Gemini 2.5 Flash is the default primary (AI Studio free tier: ~1,500 req/day, 1M-token context). On a 429 response, the wrapper automatically retries the same call via Groq's free tier (Llama 3.3 70B) for small per-file patches.
**Why:** Gemini 2.5 Flash free tier is the most generous available at time of design (whole modules in one call due to 1M context). Groq provides a second lane to absorb rate-limit bursts without dropping updates. The wrapper architecture means swapping providers requires only a config edit — free-tier quotas change monthly and the system must tolerate it.
**Alternatives rejected:** OpenAI (no free tier with adequate quota). Local models via Ollama (hardware-dependent; not suitable as a default). Single-provider without fallback (a quota hit would stall all updates). Treating the fallback as a manual config switch (too slow; 429s happen mid-update and need automatic retry).
**Revisit if:** Gemini free tier quota is cut materially; a better free-tier option emerges; the developer obtains a paid API key (swap in corpus.yml, no code change needed).

---

## 2026-07-16 — One-hop, symbol-gated invalidation rule for incremental updates
**Decision:** When `corpus update` runs incrementally (M2+), the set of files to re-doc is: (1) every file with actual diff lines, plus (2) direct importers of changed files *only if* the change touched exported/public symbols (identified by tree-sitter). No further cascade. Ancestor `_dir.md` rollups refresh for all affected files.
**Why:** Transitive invalidation (re-doc everything that imports something that imports something changed) balloons LLM cost for marginal accuracy gain. Second-hop and deeper drift is caught on the next update of those files. Staleness flags ensure Corpus never claims false freshness.
**Alternatives rejected:** Full re-doc on any change (correct but quota-expensive; defeats the purpose of M2). Transitive invalidation (correct in theory; exponential cost in practice for large dependency graphs). No importer invalidation (misses the critical case where a changed function signature makes an importer's doc factually wrong).
**Revisit if:** Real-world dogfood shows meaningful doc inaccuracy from second-hop drift that staleness flags don't adequately communicate.

---

## 2026-07-16 — Six MCP tools maximum; no tool list growth without displacement
**Decision:** The MCP bridge exposes exactly six tools: `corpus_overview`, `corpus_doc`, `corpus_relations`, `corpus_find`, `corpus_changes`, `corpus_stale`. Adding a seventh tool requires either retiring an existing tool or proving the new capability cannot be expressed as an argument on an existing tool.
**Why:** Every tool in an MCP tool list occupies tokens in every agent prompt. A prior finding from tool-list curation showed that cutting from 13 tools to 1 reduced prompt token cost by 76%. A fat tool list also degrades agent decision quality by expanding the choice space unnecessarily.
**Alternatives rejected:** Unlimited tool growth as features are added (token cost compounds; agent prompt quality degrades). Namespaced tool groups (adds cognitive overhead for the agent; the six tools already cover the full query surface).
**Revisit if:** Real-world dogfood reveals a query pattern that genuinely cannot be served by the existing six tools and cannot be expressed as an argument variant.

---

## 2026-07-16 — MCP server (stdio) and event sidecar are two separate processes
**Decision:** The FastMCP server runs over stdio, owned by Claude Code's process lifecycle. The event sidecar (FastAPI + uvicorn) is a separate long-running process on `localhost:7077`. MCP tools POST fire-and-forget events to the sidecar. If the sidecar is not running, events drop silently and MCP tools are unaffected.
**Why:** MCP's stdio transport means the MCP server process is launched and owned by Claude Code — it dies when Claude Code exits. The graph frontend and its websocket connections must outlive individual Claude Code sessions. Two processes with a clean HTTP boundary between them is the only architecture that satisfies both constraints without coupling them.
**Alternatives rejected:** Single process for both (stdio lifecycle would kill the frontend server when Claude Code exits). IPC / shared memory (platform-specific, complex, no benefit over localhost HTTP for this throughput level). Making the frontend poll graph.json directly (works for graph display but cannot receive real-time agent query events).
**Revisit if:** The two-process overhead proves operationally annoying (e.g., users forget to start the sidecar); in that case `corpus serve` can manage both as subprocesses.

---

## 2026-07-16 — Files are the atoms; directories are the view (module rules locked)
**Decision:** Docs, staleness, history, and diff-mapping are all file-level, everywhere, with no exceptions. Directories are a view layer: rollup docs generated from child docs, shown collapsed or expanded in the graph. The LLM never defines structure — structure is computed deterministically.
**Why:** File-level granularity is the only level where tree-sitter, git diff, and content hashes all operate cleanly. Coarser "module" granularity defined by AI would drift between runs (different LLM calls, model updates) and corrupt history. The product principle from PRODUCT.md §02: "Structure is computed. Meaning is generated."
**Alternatives rejected:** LLM-defined module boundaries (drift, hallucination risk, non-reproducibility). Directory-level docs as atoms without file-level docs (loses per-file staleness tracking; can't do import-level invalidation). Hybrid where some dirs are "real" modules (arbitrary, hard to explain to users, complicates the graph schema).
**Revisit if:** A codebase pattern emerges (e.g., generated files, monorepo packages) where file-level granularity is clearly wrong and directory-level would serve users better.

---

## 2026-07-16 — M1 is full regeneration; no incremental logic until M2
**Decision:** M1's `corpus update` re-docs every tracked file every run. There is no diffing, no invalidation, no staleness optimization. The pipeline is architecturally shaped for M2 (steps 1 and 3 of the §05 pipeline are stubs) but not implemented.
**Why:** Full regeneration is correct, fast to implement, and immediately useful. Incrementality (M2) is the hardest engineering in the project — attempting it in M1 would delay the first working demo and introduce complexity before the doc format is stable. M1 exists to validate the end-to-end pipeline and the doc quality before optimizing it.
**Alternatives rejected:** Attempting incrementality in M1 (delays first demo, adds risk before format is proven). Skipping M1 and building M2 directly (no baseline to diff against; pipeline unvalidated).
**Revisit if:** The M1 full-regeneration quota cost is too high for real daily use on large repos (in which case M2 priority increases, not M1 scope).

---

## 2026-07-17 — Phase 1c: Gemini API key passed as header, not URL query param
**Decision:** The `x-goog-api-key` HTTP header is used for Gemini authentication instead of the `?key=` URL query parameter.
**Why:** Network errors (DNS failure, timeout) can include the full request URL in exception messages, which would expose the API key in terminal output. Headers are not included in exception stack traces.
**Alternatives rejected:** URL query param (default in many Google examples, but leaks key on network errors).

---

## 2026-07-17 — Phase 1c: Dir rollups generated deepest-first to ensure child _dir.md exists before parent reads it
**Decision:** When generating `_dir.md` rollup files, directories are sorted by depth (most slashes first) so children are always written before parents.
**Why:** Parent rollups pull the first sentence of the Summary from child `_dir.md` files. If parent is generated first, the child file doesn't exist yet and the parent's Contents entry for that subdirectory would be empty.
**Alternatives rejected:** Two-pass generation (write all file docs, then write all rollups in a second pass sorted depth-first — functionally equivalent, current approach is a single pass).

---

## 2026-07-17 — Import edge resolution: intra-repo only, external imports dropped
**Decision:** `graph.json` edges of type `imports` connect only files within the tracked set. Imports that resolve to external packages (e.g., `os`, `click`, `react`) produce no edge and are silently dropped. For Python: `corpus.scaffold` → `corpus/scaffold.py` (dotted path to file path). For JS/TS: relative specifiers (`./foo`) resolved with common extension probing; bare specifiers (npm packages) skipped.
**Why:** External dependency edges would add noise without value — the graph is a map of the repo's own structure. External deps are not tracked files and have no node to point to. M2 may add an "external dependency" node type if that proves useful.
**Alternatives rejected:** Creating stub nodes for external packages (would pollute the graph and complicate every query). Storing import specifiers as string attributes on edges without target nodes (inconsistent schema; nothing can resolve them).
**Revisit if:** Dogfood shows that seeing which external packages each file uses is valuable in the graph viewer.

---

## 2026-07-17 — Phase 2: Stale flag set only when prior hash exists and hash differs
**Decision:** `stale: true` is only written when `old_hash is not None and current_hash != old_hash`. Brand-new files (no prior hash) are NOT marked stale.
**Why:** A reviewer BLOCKER caught the original code marking files with `old_hash is None` as stale, causing every file to be re-doc'd on every run after init, defeating M2's core invariant.
**Alternatives rejected:** Treating new files as stale (incorrect — they were just doc'd on the full rebuild that added them; re-doc'ing them on the next run wastes LLM quota).

---

## 2026-07-19 — Phase 4: Edge normalization at serve time (from/to → source/target)
**Decision:** `server.py GET /graph` normalizes edge keys from `from`/`to` (disk format) to `source`/`target` (react-force-graph format) at serve time. The on-disk `graph.json` format is unchanged.
**Why:** react-force-graph requires `source`/`target`. Changing the graph.json schema would break all existing MCP tools and Phase 2 tests. A one-liner transform at the HTTP boundary is the least-invasive fix.
**Alternatives rejected:** Changing graph.json schema to use source/target (would break MCP tools, test fixtures, and prior decisions). Adding a second edge format field on disk (redundant, doubles edge storage).

---

## 2026-07-19 — Phase 4: `webbrowser.open` fires via 1.5s daemon thread before uvicorn.run
**Decision:** A daemon thread sleeps 1.5s then calls `webbrowser.open`, started before the blocking `uvicorn.run()` call.
**Why:** `uvicorn.run()` is blocking — nothing after it executes until the server is killed. The browser must open after the server is ready; a 1.5s delay is safe on localhost (uvicorn binds well within 200ms).
**Alternatives rejected:** uvicorn startup callback (uvicorn 0.29 doesn't expose a clean pre-request callback that fires after bind). Polling the port in the thread (correct but overengineered for localhost).

---

## 2026-07-19 — Phase 3: Click test runner cannot host a stdio MCP server in-process
**Decision:** Tests for `corpus serve --mcp` mock `corpus.mcp.run` (the FastMCP entry point) rather than invoking the real server in the Click test runner.
**Why:** FastMCP's stdio server writes directly to `sys.stdout`. Click's `CliRunner` replaces `sys.stdout` with a buffer and closes it after `invoke()` returns. The real server writing after that close raises `ValueError: I/O operation on closed file`. The product behavior is correct; only the in-process test harness is incompatible.
**Alternatives rejected:** `mix_stderr=False` + `catch_exceptions=False` (doesn't help — the problem is stdout closed after invoke, not exception swallowing). Subprocess-based integration test (correct approach for a true end-to-end test, but disproportionate for a unit AC; deferred to Phase 5 dogfood verification).

---

## 2026-07-17 — Phase 2: Graph load gated on graph_path.exists() only, not stored_commit
**Decision:** The incremental path is taken whenever `graph_path.exists()`, regardless of whether `stored_commit` is set in state.
**Why:** A reviewer BLOCKER: gating on `stored_commit is not None` meant git-less environments always discarded the graph and ran a full rebuild. The stored commit is only needed to compute `git diff`, not to decide whether a valid graph exists on disk.
**Alternatives rejected:** Keeping the commit gate (breaks git-less repos and repos where git has been re-initialized).

---

## 2026-07-21 — Phase 6: Frontend reworked to Obsidian-style dark graph experience
**Decision:** Replace the light-theme header+panel layout with a full-screen dark graph (Obsidian-inspired `#0d1117` background, purple accent `#7c6af7`, amber stale `#e3b341`). The 56px header bar is removed. The graph fills 100vh. The doc panel becomes an absolute-positioned overlay (not a layout column). A Cmd/Ctrl+K command palette replaces the header-mounted importance filter strip. A togglable minimap is added. The doc panel gains a breadcrumb row and a backlinks section derived from existing graph edges (no new API calls). Data-layer hooks (`useGraph`, `useDoc`) and all App.jsx logic are unchanged.
**Why:** The v1 light theme with a fixed header and a shrinking canvas does not match the product brief ("Obsidian-style visual graph browser" is in the project brief, PLAN.md line 7). After v1 shipped with working data plumbing, a focused Phase 6 lets the UI catch up to the original vision without touching any backend code. The Obsidian graph model — dark background, glowing nodes, floating panels that overlay rather than displace the canvas — is the right mental model for a codebase exploration tool because the graph is the primary object, not a secondary decoration next to a panel.
**Alternatives rejected:** Keeping the light theme and just adding palette + backlinks (doesn't address the fundamental layout problem — the header+shrink model fights the graph). Adopting a full Obsidian clone with multiple panes and a sidebar (over-engineered for a single-repo tool; conflicts with non-goal "No bespoke chat UI" philosophy — the viewer should stay lean). Using a pre-built Obsidian-like component library (none exist for React that cover force-graph integration; we'd be fighting the library for the canvas node rendering). Adding minimap click-to-navigate in Phase 6 (parked — orientation aid is useful; interactive minimap requires mapping canvas coordinates to graph space, a non-trivial addition that does not affect the demo value).
**Revisit if:** The dark palette conflicts with user environments (e.g., projector use); in that case a `prefers-color-scheme: light` media query can restore light tokens without touching layout code, because all colors are CSS variables.

---

## 2026-07-21 — Phase 7: "Sahara" warm light theme selected from Stitch design file
**Decision:** The Phase 6 Obsidian dark theme is replaced wholesale by the "Sahara" warm light theme defined in the Stitch design file at `C:\Users\varun\OneDrive\Desktop\stitch\code.html`. Primary color is `#c2652a` (burnt sienna). Background is `#faf5ee` (warm linen). Typography: EB Garamond for headlines/display, Manrope for body/labels. This is a complete replacement — no dark mode toggle, no `prefers-color-scheme` query.
**Why:** The user selected the Sahara/Stitch design as the target aesthetic for v1. Stitch provides exact Tailwind color tokens and a complete HTML mockup of the three-column layout, making it the authoritative design spec rather than a loose brief. Implementing it faithfully in Phase 7 (rather than iterating incrementally) avoids a partial "neither dark nor light" intermediate state that would be hard to demo. Dark mode support is parked because the Sahara palette requires a different typographic hierarchy (EB Garamond at large sizes relies on warm backgrounds for contrast; inverting it correctly would be a separate design task).
**Alternatives rejected:** Keeping the Obsidian dark theme and adding a toggle (two complete themes doubles the CSS surface area to maintain; neither theme would be polished). Mapping dark tokens to warm equivalents without redesigning layout (the Stitch design also changes layout — three-column, fixed Doc Reader, File Tree sidebar — so a token-only swap would produce an incoherent result). Adopting a pre-built component library with built-in theming (no library matches the EB Garamond + Manrope + sienna aesthetic; would require fighting the library for the canvas node rendering which is already custom).
**Revisit if:** The user decides to ship both themes after seeing v1 in Sahara; or if projector/accessibility requirements demand high-contrast dark mode.

---

## 2026-07-22 — Phase 8: GitHub-dark theme supersedes Sahara wholesale; pulse indicator repurposes GH success-green
**Decision:** The "Sahara" warm light theme (Phase 7) is replaced entirely by a GitHub-dark-mode-style theme — dark canvas (`#0d1117`), system font stack (no EB Garamond/Manrope), 1px borders over shadows, ≤8px border radius, restrained button coloring. No light mode, no toggle — same single-theme model Sahara itself used. This is a pure CSS/token/typography pass: no component structure, layout, routing, state, or functionality changes. Corpus's live-agent-query pulse indicator (a Corpus-specific concept with no GitHub UI equivalent) is remapped from the Sahara-era teal `#14b8a6` to GitHub's success-green `#3fb950`, reusing an existing spec token rather than introducing an off-palette color; it stays visually distinct from stale-amber (`#d29922`) and dir-node blue (`#4493f8`).
**Why:** User request, explicitly confirmed to supersede rather than supplement Sahara (same precedent as Phase 7 superseding Phase 6's Obsidian theme). GraphCanvas.jsx's JS color constants are included in scope despite being `.jsx` file edits, not CSS — they are pure `ctx.fillStyle`/`ctx.strokeStyle` presentation arguments with no branching logic, and both prior theme phases (6, 7) used this same mechanism to reskin the canvas; leaving them Sahara-colored would produce an incoherent half-migrated result.
**Alternatives rejected:** Adding GitHub-dark as a second, toggleable theme alongside Sahara (would require building a light-mode token set too, doubling CSS surface area — user explicitly chose full replacement instead). Keeping the pulse indicator on off-palette teal (visually fine but leaves one un-mapped legacy color in an otherwise-complete token migration). Reusing accent-blue for the pulse (would collide with dir-node color, breaking at-a-glance distinguishability between "just queried" and "directory").
**Revisit if:** The user wants both themes after seeing GitHub-dark in practice; or if the pulse/dir-node color choice proves confusing in real use.

---

## 2026-07-21 — Phase 7: Five tabs (Explorer / Architecture / Dependencies / Symbols / Overview) as primary navigation
**Decision:** The top nav exposes exactly five tabs. Each tab renders a distinct center-column content type. The Ctrl+K command palette and the importance filter strip (from Phase 6) are removed from the UI. Tab identity replaces filter-based navigation as the primary way to change what is shown in the center.
**Why:** The Stitch design specifies a tab-based nav. Five tabs map cleanly onto the five distinct query modes that emerge from real usage: (1) free graph exploration, (2) architectural/module-level view, (3) per-file dependency tracing, (4) symbol lookup, (5) project health overview. These five modes are meaningfully different enough to warrant separate rendering paths rather than modes within a single graph. The command palette added value in Phase 6 when the graph was the only surface; now that there is a File Tree sidebar for navigation and a Symbols tab for lookup, the palette is redundant overhead.
**Alternatives rejected:** Keeping the command palette alongside tabs (two navigation systems for the same task creates confusion about which to use). Accordion panels instead of tabs (accordion doesn't map well to a full-viewport center column — it would create awkward partial-height graph renders). Sidebar nav instead of top tabs (the Stitch design explicitly uses a top nav; a sidebar-within-sidebar would compete with the File Tree for horizontal space).
**Revisit if:** Users find tab-switching friction higher than command-palette search; in that case the command palette can be re-added as a supplementary accelerator (Ctrl+K) without changing the tab layout.

---

## 2026-07-22 — Phase 7 blank-page bug: `closePanel` used before declaration in App.jsx — fixed by reordering, not investigating build tooling
**Decision:** The browser-blank-page issue left open at Phase 7 close-out was a genuine JS temporal-dead-zone bug, not a build/bundler/environment problem. `App.jsx`'s "Escape closes doc reader" `useEffect` referenced `closePanel` in its dependency array before the `const closePanel = useCallback(...)` line that declared it, ~60 lines later in the same component. Dependency arrays are evaluated eagerly on every render — this threw a `ReferenceError` on first mount, unconditionally, on every machine. Fixed by moving the `closePanel` declaration above its first use. No logic changed.
**Why:** Confirmed via a temporary `sourcemap: true, minify: false` rebuild (reverted immediately after) plus Claude-in-Chrome live console reads — the production-minified stack trace only showed `Cannot access 'L' before initialization`; the unminified rebuild resolved it to the real identifier `closePanel` and the real component (`App`), which pointed straight at the fix.
**Alternatives rejected:** None investigated at length — once the readable stack trace named the exact variable and file, the fix was mechanical and obviously correct (a hooks-ordering bug has exactly one fix: declare before use).
**Revisit if:** Never — this is closed. If a similar "works everywhere except the browser" bug appears again, the sourcemap+unminify diagnostic technique here is the fast path, not re-guessing from the 4 hypotheses STATE.md previously listed.

---

## 2026-07-22 — `tests/test_phase4.py::TestAC5StaticFileServing` (4 tests) cannot pass once `frontend/dist/` is built anywhere — pre-existing test flaw, not fixed yet
**Decision:** Left unfixed and documented rather than patched in the same session as the `closePanel` fix, to keep that fix isolated and reviewable on its own.
**Why:** These 4 tests assert the server returns 500 when `frontend/dist/` is missing, using `chdir(tmp_path)` for isolation. But `corpus/server.py:_dist_dir()` resolves the dist path relative to `__file__` (the installed package location), not `cwd` — so `chdir` never actually hides dist from the server's perspective. The tests only ever passed because no one had run `npm run build` on whatever machine ran them. This session built `frontend/dist/` for the first time on this machine (required to fix and verify the blank-page bug), which permanently exposed the flaw: these 4 tests will now fail on any machine where the frontend has ever been built, which is every real deployment.
**Alternatives rejected:** None implemented yet. The eventual fix is almost certainly monkeypatching `corpus.server._dist_dir` in the test rather than relying on `chdir`.
**Revisit if:** Next session picks up test maintenance — this is next on deck, flagged in STATE.md "Known issues & hacks".

---

## 2026-07-22 — Phase 8: "Sahara" warm light theme replaced wholesale by GitHub-dark theme — supersedes the 2026-07-21 Sahara entry
**Decision:** The Phase 7 "Sahara" warm light theme is replaced wholesale by a GitHub-dark-mode-style theme (`#0d1117` canvas background, GitHub's blue/amber/green/purple status palette, system UI font stack in place of EB Garamond + Manrope). This is a full replacement, not an addition: no dark/light toggle, no `prefers-color-scheme` query — the same "one theme, done well" rule the 2026-07-21 entry used to justify Sahara, re-applied to a new palette. Layout, three-column structure, five tabs, and all component behavior from Phase 7 are unchanged; this is a CSS-token/color/typography/radius pass only, scoped in detail in PLAN.md Phase 8.
**Why:** The user was shown the 2026-07-21 Sahara decision explicitly, including its "no dark mode toggle" rationale and the reasoning that two themes double CSS maintenance surface for no payoff, before requesting this change — and chose full replacement over adding a second theme or a toggle. That same rationale is preserved here: this phase retires Sahara rather than running it alongside GitHub-dark.
**Alternatives rejected:** Togglable second theme alongside Sahara (reintroduces the exact CSS-doubling problem 2026-07-21 rejected; user explicitly chose replacement after being shown the conflict). `prefers-color-scheme` auto-switching (same doubling problem, plus explicitly excluded by the 2026-07-21 entry). Component-by-component incremental re-theming across multiple phases (leaves the app in an incoherent half-Sahara/half-GitHub-dark state mid-transition).
**Revisit if:** The user requests a GitHub light-mode variant (parked in PLAN.md, not built — wasn't requested for this phase); or if projector/accessibility needs demand a different-contrast variant (only `tokens.css` values need to change again, since the whole app renders through CSS custom properties).

---

## 2026-07-21 — Phase 7: File Tree sidebar is toggleable, default visible, 260px fixed width
**Decision:** The left File Tree sidebar is always mounted in the DOM. Its visibility is toggled by a button in the top-nav right cluster. Default state: visible. When hidden, the sidebar gets `width: 0; overflow: hidden` (not `display: none`) so the center column expands smoothly via CSS transition. Width when visible: `260px`, `flex-shrink: 0`.
**Why:** The File Tree provides persistent spatial orientation — users can track where they are in the repo without opening the Symbols tab or reading graph node labels. Default-visible matches the Stitch design, which shows it open. Toggling rather than removing from DOM preserves the tree's expand/collapse state across hides (a user who collapses a directory should not find it re-expanded after toggling the sidebar). Width 260px is taken directly from the Stitch layout class `w-64` (16rem = 256px, rounded to 260px for pixel alignment with the 1px border).
**Alternatives rejected:** Always visible with no toggle (wastes horizontal space on small screens or when users want a wider graph view). Always hidden with explicit open button (forces an extra click for the common case; the Stitch design has it open). Resizable sidebar (adds significant complexity — drag handle, mouse event tracking, min/max constraints — for limited value in a single-developer local tool). `display: none` on hide (loses scroll position and expand/collapse state; also causes layout flash on re-show).

---

## 2026-07-22 — Phase 9 planned: `d3-hierarchy` added as a new frontend dependency; curation/layout logic split into standalone `frontend/src/lib/` modules, not inlined in GraphCanvas.jsx or App.jsx
**Decision:** Phase 9 (Explorer graph UX overhaul) adds `d3-hierarchy` to `frontend/package.json` to compute a folder-keyed tree/radial initial node placement, layered under the existing d3-force simulation for local jitter/separation. The Overview-mode curation algorithm (importance-based, with a degree-based fallback when `node.importance` is null everywhere) and the hierarchy-layout seeding are each implemented as small standalone pure-function modules (`frontend/src/lib/graphCuration.js`, `frontend/src/lib/hierarchyLayout.js`) rather than inlined into `GraphCanvas.jsx` or `App.jsx`.
**Why:** The user's brief explicitly named `d3-hierarchy` as the mechanism for the tree/radial structural skeleton, and it composes naturally with `react-force-graph-2d`'s underlying `d3-force` - same ecosystem, no new rendering paradigm, tree-shakeable, no runtime cost when unused. Splitting curation and layout-seeding into standalone modules keeps two genuinely algorithmic, testable pieces of logic (a selection function; a coordinate-computation function) out of the canvas draw loop and out of App.jsx's already-large body of memoized derivations - both target files are edited by consecutive theme phases (6, 7, 8) and by this phase; keeping the new algorithmic logic in its own files reduces collision surface and makes the curation/layout logic unit-testable without mounting the canvas.
**Alternatives rejected:** `dagre` or `elkjs` for the hierarchical layout (heavier, graph-editor-oriented libraries aimed at DAG diagramming, not a natural fit with `d3-force`'s node/link data shape; would require an adapter layer `d3-hierarchy` doesn't need). Inlining curation/layout logic directly inside `GraphCanvas.jsx`'s `nodeCanvasObject` callback or as ad hoc `useMemo` blocks in `App.jsx` (works, but couples pure selection/placement math to React re-render timing and to files three prior phases have already repeatedly touched for unrelated reasons, raising both merge-conflict risk and test difficulty).
**Revisit if:** `d3-hierarchy`'s tree/radial output proves visually unhelpful even as a seed (in which case the hybrid layout requirement itself would need revisiting with the user, not just the library choice); or if a future phase needs the same curation/layout math server-side (Python), in which case porting the pure-function modules is more tractable than porting logic embedded in canvas draw callbacks.

---

## 2026-07-22 — Phase 8 reviewer MINOR: Open-in-Editor hover-fill opacity 0.08 is a builder judgment call, accepted
**Decision:** In `DocReader.jsx`, the "Open in Editor" button's hover background became `rgba(68,147,248,0.08)` — the Sahara value was `rgba(...,0.05)` and the Phase 8 token-mapping table specified no literal for this slot (only the border's `0.30`). The `0.08` value is accepted as-is.
**Why:** Reviewer flagged it as the one unstated deviation in an otherwise fully-documented phase — harmless, chosen for legibility of a hover state on a dark background, but previously lacking a paper trail. This entry is that paper trail.
**Alternatives rejected:** Reverting to `0.05` (visually weaker on `#0d1117`; no spec value existed to be faithful to).
