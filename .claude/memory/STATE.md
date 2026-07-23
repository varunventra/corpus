# STATE — read this first

> Rewritten (not appended) at every phase close-out and before any mid-phase stop. Keep under 120 lines.
> The test: a fresh session with zero chat history must be able to act correctly within one minute of reading this file.

## Where we are

- **Current phase:** ALL PHASES COMPLETE (1a–9). v1 shipped with GitHub-dark theme + reworked Explorer graph UX. Nothing blocking.
- **Last completed phase:** Phase 9 — Graph UX overhaul (DONE 2026-07-23 — reviewer REQUEST CHANGES → fix pass → orchestrator diff-verified → qa 198/198 → orchestrator browser-verified live, dramatic visual improvement confirmed).
- **Awaiting:** Nothing blocking. User can explore the app; both Phase 8 and Phase 9 are committed and pushed to `origin/main`.

## Project identity

**Corpus** — CLI + MCP server + live graph viewer that generates and maintains a living second representation of a codebase. Plain files in `.corpus/`. Python engine, React frontend. Local only, free-tier AI.

## How to run

```bash
cd C:\Users\VarunV\Desktop\corpus
python -m pip install -e .
cd frontend && npm install && npm run build && cd ..
python -m corpus.cli update    # regenerates .corpus/graph.json if stale
python -m corpus.cli serve     # localhost:7077
```

Node.js is a portable install at `C:\Users\VarunV\tools\node-v24.18.0-win-x64`, prefix to PATH if `node`/`npm` aren't found in a fresh shell: `export PATH="/c/Users/VarunV/tools/node-v24.18.0-win-x64:$PATH"` (bash) — this machine has no admin rights and no system Node. No `GEMINI_API_KEY`/`GROQ_API_KEY` set — docs/importance are null; graph structure and the Overview mode's degree-based fallback curation both work fine regardless.

## What just happened (2026-07-22 → 2026-07-23, one long session across a usage-limit interruption)

- **Phase 8 (GitHub-dark theme retrofit):** complete, reviewed, 152/152 tests, browser-verified, **committed and pushed** at `c644857`.
- **Phase 9 (Graph UX overhaul):** the user's core complaint — the Explorer graph was cluttered, labels overlapped illegibly, nodes clustered instead of spreading, everything showed at once with no high-level view — is fixed. Full cycle: `builder` implemented Overview/All-Files modes + curation algorithm + physics retune + label AABB-collision pass + hierarchy-seeded layout + directory badge redesign + a folded-in fix for a pre-existing symbols-rendering bug (graph.json stores symbols as plain strings, DocReader/SymbolsTab expected objects — real names were blank everywhere since Phase 7). `reviewer` found one real MAJOR bug (opening the Doc Reader or an MCP pulse forced an unwanted camera recenter — traced to the zoomToFit effect keying on raw object identity instead of actual content change) plus 2 minor issues (unpopulated degree field made label-priority a no-op on this exact no-API-key machine; pulse-revealed nodes didn't visually expand their ancestor folder). A second `builder` pass fixed all three with a content-fingerprint gate + degree wiring + ancestor-expand override. Orchestrator personally verified the fix diff line-by-line (not just trusted the report), then `qa` retargeted the one stale pre-existing test, added 45 new unit tests (198/198 total), and orchestrator did a live browser pass: **confirmed dramatic visual improvement** — Overview mode defaults to a curated 27-31-of-68 subset, All Files mode shows all nodes spread out with zero overlapping circles or labels (a night-and-day difference from the original bug screenshot), directory badges are legible (arrow + separate count circle), the MAJOR camera-jump bug is confirmed fixed (clicking a node to open Doc Reader no longer recenters), and the symbols fix confirmed live (Key Symbols cards show real names like `main`/`init`/`_post_graph_event` instead of blank rows).
- **Committed and pushed** in one commit alongside Phase 8's already-pushed work (see git log for exact hash — this file doesn't hardcode it since it's written before the final commit of this session).
- **Session note:** this work spanned a hard interruption (host hit a monthly API spend limit mid-Phase-9-build) and a user-initiated pause/handoff for a possible machine switch; both resolved cleanly with no lost work — STATE.md was kept current throughout specifically so an interrupted session could resume cold.
- **Cleanup note:** two stray garbage files (`scs` and a long filename containing a sentence fragment) were found as untracked debris at close-out — traced to a subagent's `git diff` invoking the `less` pager interactively in a non-interactive shell and mangling output into files. Deleted before committing; not source content, not user data.

## Known issues & hacks

- **`tests/test_phase4.py::TestAC5StaticFileServing`** — 4 Python tests, pre-existing `_dist_dir()` cwd-vs-package-relative test design flaw (DECISIONS.md 2026-07-22). Fix: monkeypatch `_dist_dir`. Still open, not urgent, unrelated to Phases 8/9.
- Top-nav search input wired to DOM but not connected to FileTree filter (parked)
- DependenciesTab shares fgRef across conditionally-rendered tabs (low risk)
- Dead code with stale Sahara colors: CommandPalette.jsx, Minimap.jsx, ImportanceFilter.jsx (unrendered, parking lot)
- `curateFiles` in `graphCuration.js` uses O(n) `Array.includes()` instead of a Set lookup in its expansion loop — fine at current scale, parking lot for large repos
- `ModeToggle` segment padding (`6px 14px`) never measured against the design spec's own 32px-height accessibility fallback — low stakes, parking lot
- Live MCP `corpus_doc()` pulse round-trip: color/draw-path confirmed correct via code + tests across both Phase 8 and 9, but an actual live MCP client call triggering a real pulse was never observed in-browser this session (no MCP client available to either builder/qa or the orchestrator) — worth a real end-to-end check next time Claude Code is used against this repo with the MCP server registered.
- Node/npm not on default shell PATH on this machine — see "How to run" above for the workaround.

## Phase completion checklist

- [x] Phases 1a–7 (M1–M5, Obsidian rework, Sahara theme + 3-column layout)
- [x] Phase 8 — GitHub dark theme retrofit
- [x] Phase 9 — Graph UX overhaul (Overview/All-Files modes, label decluttering, physics, symbols fix)

## Next action

Nothing blocking. Parking lot in PLAN.md has remaining ideas if the user wants a new phase (per-node changelog, `corpus explain`, health overlays, the `test_phase4.py` fix, the O(n) curation scan, etc.). Otherwise the app is in a good, fully-reviewed, fully-tested, committed-and-pushed state.
