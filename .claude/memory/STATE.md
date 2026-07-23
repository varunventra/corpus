# STATE — read this first

> Rewritten (not appended) at every phase close-out and before any mid-phase stop. Keep under 120 lines.
> The test: a fresh session with zero chat history must be able to act correctly within one minute of reading this file.

## Where we are

- **Current phase:** ALL PHASES COMPLETE (1a–9), plus one post-close-out fix. v1 is in a clean, fully-reviewed, fully-tested, committed-and-pushed state. **Nothing is running, nothing is uncommitted, nothing is blocking.**
- **Working tree:** clean. `git status --short` returns nothing.
- **Sync status:** local `main` and `origin/main` are identical at commit `2af9129`. Verified via `git log origin/main --oneline -1` immediately before writing this file.
- **Awaiting:** Nothing. This is a deliberate stopping point for a machine switch — user is moving to their personal laptop.

## Resume on personal laptop — exact steps

```bash
git clone https://github.com/varunventra/corpus.git
cd corpus
python -m pip install -e .
cd frontend && npm install && npm run build && cd ..
python -m corpus.cli init      # first time on this machine only
python -m corpus.cli update    # populates .corpus/graph.json (not tracked in git, .gitignore'd)
python -m corpus.cli serve     # opens localhost:7077
```

Node.js: use whatever's on the new machine's normal PATH (this desktop needed a portable-install workaround because it had no admin rights and no system Node — that workaround is machine-specific, irrelevant on a personal laptop with normal Node access). No `GEMINI_API_KEY`/`GROQ_API_KEY` needed for any of the above to work — docs/importance stay null, graph structure and the Explorer view's degree-based fallback curation both work fine without a key.

## Recent history (git log, newest first) — what to tell a fresh session if asked "what happened last"

1. **`2af9129`** — Fixed disconnected/isolated nodes (files with zero edges, e.g. `README.md`, `LICENSE`; and small disconnected components like `frontend/src`) drifting arbitrarily far from the main graph cluster under the force simulation, which forced the camera to zoom out drastically and made the outliers nearly invisible. Fix: added a weak constant centering force (`forceX`/`forceY`, strength 0.02) in `GraphCanvas.jsx` alongside the existing charge/link/collide forces — reeled in isolated nodes without disturbing the main cluster's link-driven layout. User-reported, diagnosed live in browser (confirmed 10 zero-degree nodes via `/graph` data), fixed by `builder`, diff-verified by orchestrator, then re-confirmed live in browser: all 40 nodes now sit together in one cohesive cluster. Tests 199/199.
2. **`3b8955c`** — Phase 9: Explorer graph UX overhaul. This was the big one — user's original complaint was "the graph looks cluttered, labels overlap, nodes are clustered instead of spread out, everything shows at once." Delivered: **Overview mode** (default) shows a curated subset (importance-ranked if an LLM key is set, degree-ranked fallback otherwise — this machine has no key, so fallback is what's live); **All Files mode** is an explicit toggle showing everything. Real force-physics retune (radius-aware collision, retuned charge/link distance), a d3-hierarchy folder-keyed layout seed for graphs >60 nodes, and a genuine per-frame label-collision-avoidance pass (nudge → leader line → hide, replacing the old "just stack on top of each other" behavior). Directory child-count badges redesigned (separate arrow + count-circle + hover tooltip, instead of the old overlapping badge the user mistook for "random letters or symbols"). Also folded in a real pre-existing bug fix (not a Phase 9 regression, dates to Phase 7): `graph.json` stores `symbols` as plain strings but `DocReader.jsx`/`SymbolsTab.jsx` expected `{name, kind}` objects, so symbol names rendered blank everywhere — now fixed. Went through a full review cycle: reviewer caught a real MAJOR bug (opening the Doc Reader or an MCP query pulse forced an unwanted camera recenter — traced to `zoomToFit` firing on any object-identity change instead of actual content change) plus 2 minor issues, all fixed and both diff-verified and live-browser-verified by the orchestrator before closing out. Tests: 198/198.
3. **`c644857`** — Phase 8: GitHub-dark theme retrofit. Wholesale-replaced the "Sahara" warm-light theme with a GitHub-dark palette (`#0d1117` canvas, blue accent, amber stale, green pulse) across all frontend components — a pure CSS/token/value pass, reviewer-confirmed zero structural/JSX changes. Tests: 152/152 (suite made fully green for the first time this session — 17 stale theme-lock assertions from the Sahara/Obsidian eras retargeted).

Full reasoning, alternatives-rejected, and judgment calls for all of the above are in `.claude/memory/DECISIONS.md` (append-only, dated entries) and `.claude/memory/PLAN.md` (Phase 8 and Phase 9 sections have complete acceptance criteria and file-touch lists, both checked `[x]`).

## Project identity

**Corpus** — CLI + MCP server + live graph viewer that generates and maintains a living second representation of a codebase. Plain files in `.corpus/`. Python engine, React frontend. Local only, free-tier AI.

## Known issues & hacks (all pre-existing, none introduced by recent work, none urgent)

- **`tests/test_phase4.py::TestAC5StaticFileServing`** — 4 Python tests, pre-existing `_dist_dir()` cwd-vs-package-relative test design flaw (see DECISIONS.md 2026-07-22). Fix: monkeypatch `_dist_dir` in the test. Still open.
- Top-nav search input wired to DOM but not connected to FileTree filter (parked, PLAN.md parking lot).
- Dead code carrying stale Sahara-era colors: `CommandPalette.jsx`, `Minimap.jsx`, `ImportanceFilter.jsx` — none are imported/rendered anywhere, zero visual impact, parked.
- `curateFiles` in `graphCuration.js` uses an O(n) array scan instead of a Set lookup in its expansion loop — fine at current repo scale, will matter on very large repos, parked.
- Live MCP `corpus_doc()` pulse round-trip: color and draw-path are confirmed correct via code + tests across Phase 8 and 9, but an actual live MCP client call (from a real Claude Code session with the MCP server registered) triggering a real pulse was never observed end-to-end in-browser — everything short of that final wire has been verified. Worth doing once, low priority.

## Phase completion checklist

- [x] Phases 1a–7 (M1–M5, Obsidian rework, Sahara theme + 3-column layout — see PLAN.md for full detail)
- [x] Phase 8 — GitHub dark theme retrofit
- [x] Phase 9 — Graph UX overhaul (Overview/All-Files modes, label decluttering, physics, symbols fix)
- [x] Post-close-out fix — disconnected-node centering force

## Next action

Nothing blocking, nothing in flight. If starting fresh: read this file, then `PLAN.md`'s parking lot section for backlog ideas (per-node changelog, `corpus explain` command, health overlays, the `test_phase4.py` fix, the O(n) curation scan) if the user wants a new phase — otherwise just run the app and use it.
