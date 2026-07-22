# STATE — read this first

> Rewritten (not appended) at every phase close-out and before any mid-phase stop. Keep under 120 lines.
> The test: a fresh session with zero chat history must be able to act correctly within one minute of reading this file.

## Where we are

- **Current phase:** Phase 9 — Graph UX overhaul. **NOT STARTED on disk** — the builder agent for it crashed immediately (host hit an account-level API spend limit, not a code error) before writing a single file. Zero Phase 9 code exists anywhere in the repo.
- **Last completed phase:** Phase 8 — GitHub dark theme retrofit (DONE — reviewer APPROVE, qa PASS 152/152, browser-verified live). This is what's actually sitting in the working tree right now, uncommitted.
- **Awaiting:** A fresh session (possibly on a different machine — user is moving to their personal laptop) to launch Phase 9's builder from scratch. The user has already approved the Phase 9 design direction and the folded-in symbols fix — **no design/approval conversation is needed, go straight to delegating `builder`.**

## Session interruption context (read this if you're the resuming session)

This session hit a hard stop: the model account ran out of monthly spend credit mid-flight (`"You've hit your monthly spend limit"`), which killed the Phase 9 builder agent before it read a single file, let alone wrote one. The user then switched the session model back to Sonnet 5 and asked to pause everything and hand off cleanly — likely to continue from a different machine/login. **This is an infra/billing interruption, not a code or design failure.** Everything scoped for Phase 9 (PLAN.md section, `.claude/memory/phase9_design_spec.md`) is fully valid and ready to execute as-is.

**Verified via `git status`/`git diff --stat` at hand-off (2026-07-22):** working tree = exactly Phase 8's finished state. 14 modified files (memory docs + Phase 8's frontend files), 2 untracked new files (`phase8.test.js`, `phase9_design_spec.md`). No `frontend/src/lib/` directory exists. No `d3-hierarchy` in `node_modules` or `package.json`. **Nothing to roll back — the failed agent left zero fingerprints.**

**None of this is committed to git yet** — it's all working-tree changes. If continuing on another machine, this machine's uncommitted diff needs to travel with you (e.g. `git stash`, or just copy the working directory / push a WIP commit) — otherwise a fresh clone on the other laptop will show Phase 7's Sahara theme, not Phase 8's finished GitHub-dark theme.

## Project identity

**Corpus** — CLI + MCP server + live graph viewer that generates and maintains a living second representation of a codebase. Plain files in `.corpus/`. Python engine, React frontend. Local only, free-tier AI.

## How to run (verified working on this machine 2026-07-22)

```bash
cd C:\Users\VarunV\Desktop\corpus
python -m pip install -e .
cd frontend && npm install && npm run build && cd ..
python -m corpus.cli serve     # opens localhost:7077
```

Node.js portable install at `C:\Users\VarunV\tools\node-v24.18.0-win-x64` on User PATH — **this path is specific to this machine; a personal laptop will need its own Node install** (system Node is fine there, this workaround was only needed because this machine had none and no admin rights). No `GEMINI_API_KEY`/`GROQ_API_KEY` set — docs/importance are null; graph structure works fine regardless.

## What just happened (this session, 2026-07-22)

- **Phase 8 complete and closed out:** Sahara warm theme wholesale-replaced by GitHub-dark (canvas `#0d1117`, accent blue `#4493f8`, stale amber `#d29922`, pulse green `#3fb950`, system font stack, EB Garamond/Manrope removed, Material Symbols icons kept). Pure CSS/token/value pass — reviewer read every JSX diff, confirmed zero structural changes. Files: tokens.css, global.css, index.html, GraphCanvas.jsx, DocReader.jsx, FileTree.jsx, ExplorerTab.jsx, OverviewTab.jsx, App.jsx. See DECISIONS.md 2026-07-22 entries (3 of them: theme supersession, pulse-color choice, hover-opacity judgment call).
- **Frontend test suite fully green for the first time: 152/152.** QA retargeted 17 stale Sahara/Obsidian theme-lock assertions, added `phase8.test.js` (31 tests), fixed the long-standing build-check flake (explicit 60s per-test timeout).
- **Phase 9 fully scoped, designed, and user-approved — but zero implementation exists.** User tested the live graph and found it badly broken: overlapping illegible labels, nodes clustered into a fraction of the canvas, circles overlapping, everything shown expanded at once with no high-level view (confirmed via live screenshot on a real 40-node/49-edge repo). Full requirements in PLAN.md's "### Phase 9 — Graph UX overhaul" section; every open design question resolved concretely in `.claude/memory/phase9_design_spec.md` (curation algorithm, Overview/All-Files mode toggle, label AABB-collision decluttering, d3-hierarchy-seeded layout for >60 nodes, directory badge redesign, pulse-reveal-when-curated-out behavior).
- **Pre-existing bug found & folded into Phase 9 as deliverable 9:** `graph.json` stores `symbols` as plain strings but `DocReader.jsx`/`SymbolsTab.jsx` render `sym.name`/`sym.kind` as if they were objects → blank symbol names everywhere, dead Symbols-tab search, React duplicate-key warnings. Broken since Phase 7, not a Phase 8 regression. User explicitly delegated the "fold in vs. separate fix" call; folded in as its own discrete, separately-tested item — full one-line fix spec is in PLAN.md Phase 9 deliverable 9.

## Known issues & hacks

- **Phase 8's one unverified AC:** live MCP `corpus_doc()` → green pulse round-trip not re-tested live after the theme swap (structural half is test-covered: `COLOR_NODE_PULSE '#3fb950'`, draw path unchanged). Verify opportunistically during Phase 9 qa, which needs the same round-trip anyway.
- **`tests/test_phase4.py::TestAC5StaticFileServing`** — 4 Python tests assert 500-when-dist-missing but can't observe it because `server.py:_dist_dir()` is package-relative, not cwd-relative. Pre-existing test design flaw (DECISIONS.md 2026-07-22). Fix: monkeypatch `_dist_dir`. Still open, not urgent.
- Top-nav search input wired to DOM but not connected to FileTree filter (parked)
- DependenciesTab shares fgRef across conditionally-rendered tabs (low risk)
- Windows: use `python -m corpus.cli serve` if `Scripts/` isn't on PATH
- Dead code with stale Sahara colors: CommandPalette.jsx, Minimap.jsx, ImportanceFilter.jsx (unrendered — parking lot)

## Phase completion checklist

- [x] Phases 1a–5 (M1–M5: CLI, graph, docs, incremental, MCP, viewer, live wire)
- [x] Phase 6 — Obsidian-style frontend rework
- [x] Phase 7 — Sahara theme + three-column layout + five tabs
- [x] Phase 8 — GitHub dark theme retrofit (DONE 2026-07-22 — reviewer APPROVE, qa 152/152, browser-verified)
- [ ] Phase 9 — Graph UX overhaul: Overview/All-Files modes, label decluttering, layout physics + symbols shape fix (**SCOPED + APPROVED, ZERO CODE WRITTEN** — safe to launch `builder` immediately, no re-scoping or re-approval needed)

## Next action (exact resume steps)

1. Confirm this machine's working tree still matches the Phase 8 diff described above (`git status` — expect the same 14 modified + 2 untracked files; if it doesn't match, the hand-off didn't transfer cleanly).
2. Delegate straight to `builder` with: PLAN.md's Phase 9 section + `.claude/memory/phase9_design_spec.md` as the spec (both are complete, do not need re-reading by architect/designer — that work is done). The previous prompt used for this launch is reconstructable from PLAN.md deliverables 1–9 directly; nothing was lost by the crash since the builder agent never started reading.
3. After builder reports: `reviewer` → `qa` (baseline to protect: 152/152 green) → close out Phase 8... (already done) → close out Phase 9, update this file, report to user with before/after graph screenshots (browser-verify visually — this whole phase exists because "the graph looks bad" isn't catchable by unit tests alone).
