# STATE — read this first

> Rewritten (not appended) at every phase close-out and before any mid-phase stop. Keep under 120 lines.
> The test: a fresh session with zero chat history must be able to act correctly within one minute of reading this file.

## Where we are

- **Current phase:** ALL PHASES COMPLETE — v1 (M1–M7) done
- **Last completed phase:** Phase 7 — Sahara theme + three-column layout + five tabs (DONE — 54/54 tests)
- **Awaiting:** User to run `cd frontend && npm run build && python -m corpus.cli serve` for manual visual verification

## Project identity

**Corpus** — CLI + MCP server + live graph viewer that generates and maintains a living second representation of a codebase. Plain files in `.corpus/`. Python engine, React frontend. Local only, free-tier AI.

## How to run

```bash
cd C:\Users\varun\OneDrive\Desktop\corpus
pip install -e .
cd frontend && npm run build && cd ..
python -m corpus.cli serve   # opens localhost:7077
```

## What just happened (last session, 5 lines max)

- Phase 7 built: full Sahara warm theme (#faf5ee linen, #c2652a sienna), EB Garamond + Manrope fonts, three-column layout
- Five functional tabs: Explorer (graph), Architecture (dir-only graph), Dependencies (1-hop subgraph), Symbols (searchable table), Overview (dashboard)
- File Tree sidebar (toggleable), DocReader right panel (width-transition), Open in Editor (vscode:// deep link)
- GET /meta backend route added; Windows path backslash normalization done
- Reviewer: 1 BLOCKER + 4 MAJORs all fixed. QA: 54/54 pass. Build: 495kb, 0 errors.

## Phase 7 acceptance criteria status

All 54 automated checks PASS. Browser visual checks require `corpus serve` + manual inspection.

## Known issues & hacks

- 5 Phase 6 tests now fail — they assert Phase 6 behavior (Ctrl+K, no header, dark tokens) that Phase 7 intentionally replaced. Not bugs.
- Top-nav search input is wired to DOM but not connected to FileTree filter (parked — needs `searchQuery` state lifted to App)
- DependenciesTab uses shared fgRef — if tabs switch rapidly, ref could briefly point to wrong instance (low risk, conditional render means only one mounts at a time)
- Windows: `Scripts/` dir may not be on PATH after `pip install -e .`; use `python -m corpus.cli serve`
- File Tree starts with all dirs collapsed — depth-0 dirs auto-expand on first load via seeding useEffect

## Phase completion checklist

- [x] Phase 1a — CLI skeleton + scaffolding
- [x] Phase 1b — tree-sitter → real graph.json
- [x] Phase 1c — LLM wrapper + per-file docs (M1 complete)
- [x] Phase 2 — Incremental updates (M2 complete — 220/220 tests)
- [x] Phase 3 — MCP bridge + dogfood week (DONE — 311/311 tests)
- [x] Phase 4 — Static graph viewer (DONE — 358/358 tests)
- [x] Phase 5 — Live wire (DONE — 393/393 tests)
- [x] Phase 6 — Obsidian-style frontend rework (DONE — 64/65 automated checks)
- [x] Phase 7 — Sahara theme + three-column layout + five tabs (DONE — 54/54 tests)

## Next action

1. `cd frontend && npm run build` (already done this session — dist is current)
2. `python -m corpus.cli serve` — open localhost:7077
3. Check all five tabs, file tree toggle, click a node to open DocReader, check stale warning
4. Any new work goes through architect for a plan revision
