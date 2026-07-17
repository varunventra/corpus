# STATE — read this first

> Rewritten (not appended) at every phase close-out and before any mid-phase stop. Keep under 120 lines.
> The test: a fresh session with zero chat history must be able to act correctly within one minute of reading this file.

## Where we are

- **Current phase:** Phase 2 — Incremental updates (NOT STARTED)
- **Last completed phase:** Phase 1c — LLM wrapper + per-file docs (DONE — 179/179 tests passing)
- **Awaiting:** User approval to start Phase 2

## Project identity

**Corpus** — CLI + MCP server + live graph viewer that generates and maintains a living second representation of a codebase. Plain files in `.corpus/`. Python engine, React frontend. Local only, free-tier AI.

## How to run

```bash
# From repo root: /c/Users/varun/OneDrive/Desktop/corpus/
pip install -e .
corpus init   # scaffolds .corpus/; prints claude mcp add corpus registration hint
GEMINI_API_KEY=<key> corpus update  # parses files, calls LLM, writes docs + graph.json
# Or with budget cap to skip LLM:
corpus update  # (no API key set) → graph written, docs skipped with warning
```

## What just happened (last session, 5 lines max)

- Phase 1c implemented + reviewed + QA'd: 179/179 tests passing (51 new tests added)
- New files: corpus/llm.py, corpus/docs.py, tests/test_phase1c.py
- Modified: corpus/cli.py (doc gen loop + dir rollups), corpus/scaffold.py (MCP hint), pyproject.toml (requests dep)
- Reviewer found 2 MAJORs (ancestor dirs missing from rollup, model names hardcoded) + 3 minor/nit — all fixed
- Phase 1c fully closed out — all 6 ACs met

## Phase 2 — what needs to happen

Goal: `corpus update` re-docs only changed files + symbol-gated direct importers + ancestor rollups; rename preserves node ID; ≤15 changed files completes in under 60 seconds.

Key deliverables:
- Snapshot diff: `git diff -M` between current HEAD and state.json's stored commit hash + content-hash comparison for uncommitted edits
- Rename handling: git-detected renames update `path` on existing node; doc file moved to mirror new path; ID/importance preserved
- Invalidation logic: re-doc set = changed files ∪ (direct importers where exported symbols changed); max one hop
- Rollup regeneration: only ancestor `_dir.md` files of re-doc'd nodes
- Staleness flag: `stale: true` on nodes whose hash differs from state.json; directories stale if any descendant stale

## Next action (specific enough to execute blind)

1. User approves → delegate `builder` (no UI, so no designer needed) → `reviewer` → `qa`
2. Close out, report, stop.

## Blockers / open questions

- None known.

## Known issues & hacks

- `corpus.mcp` module doesn't exist yet (Phase 3) — expected. `corpus init` prints the registration hint anyway.
- Windows: `Scripts/` dir may not be on PATH after `pip install -e .` — user may need to add manually.
- `pathspec` `gitwildmatch` deprecation warning (~2664 warnings in test run) — parked.
- Old 4-char node IDs in state.json persist from pre-fix runs — correct, IDs are stable once assigned.
- Schema field `type` vs `kind` divergence noted by reviewer — deferred to Phase 3.
- llm.generate retry: each provider gets one retry on malformed (up to 4 total calls per file). Spec implied 1 total. More resilient than spec; noted in parking lot.

## Phase completion checklist

- [x] Phase 1a — CLI skeleton + scaffolding
- [x] Phase 1b — tree-sitter → real graph.json
- [x] Phase 1c — LLM wrapper + per-file docs (M1 complete)
- [ ] Phase 2 — Incremental updates (M2 complete)
- [ ] Phase 3 — MCP bridge + dogfood week (M3 complete)
- [ ] Phase 4 — Static graph viewer (M4 complete)
- [ ] Phase 5 — Live wire (M5 complete)
