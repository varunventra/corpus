# STATE — read this first

> Rewritten (not appended) at every phase close-out and before any mid-phase stop. Keep under 120 lines.
> The test: a fresh session with zero chat history must be able to act correctly within one minute of reading this file.

## Where we are

- **Current phase:** ALL PHASES COMPLETE — v1 (M1–M5) done
- **Last completed phase:** Phase 5 — Live wire (DONE — 393/393 tests)
- **Awaiting:** User to run frontend build + manual demo verification

## Project identity

**Corpus** — CLI + MCP server + live graph viewer that generates and maintains a living second representation of a codebase. Plain files in `.corpus/`. Python engine, React frontend. Local only, free-tier AI.

## How to run

```bash
# From repo root: /c/Users/varun/OneDrive/Desktop/corpus/
pip install -e .
corpus init
GEMINI_API_KEY=<key> corpus update
python -m corpus.mcp      # MCP server (stdio)
corpus serve              # same via CLI (--mcp flag missing — see blockers)
```

## What just happened (last session, 5 lines max)

- Phase 5 built: MCP tools POST events, sidecar /event + WS fanout, frontend pulse animation + WS client
- Reviewer found 2 MAJORs (graph merge dropped new nodes; dead stale handler) + 1 MINOR — all fixed
- 35 new Phase 5 tests; full suite 393/393 passing
- Frontend dist still not built — user must run `cd frontend && npm install && npm run build`

## Phase 5 acceptance criteria status

All ACs automated-tested: PASS. Browser pulse animation and WS soft-reload require `npm run build` + manual check.

## Known issues & hacks

- Windows: `Scripts/` dir may not be on PATH after `pip install -e .`
- `pathspec` `gitwildmatch` deprecation warning — parked
- Edge regeneration for added files — parked
- `_corpus_dir()` resolves from cwd at call time — server must be launched from repo root
- Live stale recomputation not implemented (reads graph.json stale field) — parking lot

## Phase completion checklist

- [x] Phase 1a — CLI skeleton + scaffolding
- [x] Phase 1b — tree-sitter → real graph.json
- [x] Phase 1c — LLM wrapper + per-file docs (M1 complete)
- [x] Phase 2 — Incremental updates (M2 complete — 220/220 tests)
- [x] Phase 3 — MCP bridge + dogfood week (DONE — 311/311 tests)
- [x] Phase 4 — Static graph viewer (DONE — 358/358 tests)
- [x] Phase 5 — Live wire (DONE — 393/393 tests)

## Next action (specific enough to execute blind)

v1 complete. User should:
1. `cd frontend && npm install && npm run build`
2. `corpus serve` — verify graph opens in browser
3. In Claude Code: `claude mcp add corpus -- python -m corpus.mcp` then call `corpus_overview()` and watch the node pulse teal
4. Post dogfood notes to DOGFOOD.md and log any doc format changes to DECISIONS.md (Phase 3 AC6 deferred item)

Any new work should go through architect for a plan revision.
