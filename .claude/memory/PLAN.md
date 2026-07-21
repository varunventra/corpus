# PLAN

> Owned by `architect`. One phase = one approval gate. Every phase must be independently runnable and verifiable.

## Project brief

Corpus is a CLI tool that generates and maintains a living second representation of a codebase — per-file docs, folder rollups, and a structural dependency graph — all stored as plain files in `.corpus/`. It serves two audiences from one source of truth: developers get an Obsidian-style visual graph browser, and AI agents (Claude Code) get six precise MCP query tools instead of blind file-crawling. v1 is complete when a developer can point Corpus at a real repo, generate docs and a graph, query it from within Claude Code, and watch the graph light up as the agent works.

## Non-goals — what we are deliberately NOT building

- **No vector search / RAG.** Codebases have exact structure; grep-grade keyword search is deliberate. Similarity search would add a fourth fuzzy copy of the codebase requiring its own sync pipeline.
- **No custom chat UI.** Claude Code is the chat interface. Corpus is plugged into it via MCP. A bespoke chat UI would be weeks of work producing a worse version of something that already exists.
- **No auto-triggering watchers.** `corpus update` is a deliberate command. File-watching on every keystroke or commit is annoyance dressed as magic; automation is a post-core convenience, not a foundation.
- **No AI-decided structure.** The LLM never chooses module boundaries, node identities, or graph topology. Structure is computed deterministically; LLM writes only meaning (prose docs + importance rating).
- **No incremental updates in M1.** Full regeneration every run. Incrementality (M2) is the hardest engineering in the project and slots in without a rewrite because the pipeline is architected for it from day one.
- **No multi-user / cloud / accounts.** Single developer, local machine, free-tier AI, no hosting.
- **No per-node changelog in v1.** Post-core feature; the `.corpus/changelog/` directory is scaffolded but not populated until after M5.

## Stack

| Component | Choice | Justification |
|---|---|---|
| Engine + CLI | Python 3.11+, Click | Best tree-sitter bindings; Click subcommands map cleanly to the five-command surface |
| Parsing | tree-sitter + language grammars | Local AST extraction — deterministic, milliseconds per file, ~36 languages, zero LLM calls |
| Git access | git CLI via subprocess | `git diff -M` gives rename detection and diffs without a Python git library dependency |
| LLM primary | Gemini 2.5 Flash (AI Studio free tier) | ~1,500 req/day, 1M-token context — whole modules in one call |
| LLM fallback | Groq (Llama 3.3 70B free tier) | Auto-retry on Gemini 429s; small per-file patches only due to tight TPM limits |
| MCP server | FastMCP (Python) | Tools as decorated Python functions; stdio transport into Claude Code, no boilerplate |
| Event sidecar | FastAPI + websockets, uvicorn | Tiny localhost sidecar; survives Claude Code session lifecycle; serves static frontend build |
| Frontend | React 18 + Vite | Developer's existing stack; static build on localhost, no hosting needed |
| Graph render | react-force-graph (d3-force) | Force layout, click/hover/zoom out of the box; canvas-based — 500+ nodes stay smooth |
| Storage | Plain markdown + JSON in `.corpus/` | Human-readable, git-diffable, greppable, zero infrastructure |

---

## Phases

### Phase 1a — CLI skeleton + scaffolding `[x]`
**Goal:** `corpus init` runs on a real repo, scaffolds `.corpus/`, respects ignore rules, and lists the files it would process — no LLM, no tree-sitter yet.
**Deliverables:**
- `pyproject.toml` / package installable via `pip install -e .`
- `corpus` CLI entry point with `init` and `update` subcommands (update is a stub that prints "not yet implemented")
- `corpus init` creates `.corpus/corpus.yml`, `.corpus/state.json` (empty), `docs/` tree, and prints the file scan summary
- Ignore logic: `.gitignore` respected + `corpus.yml` defaults (lockfiles, build output, `.corpus/` itself)
- `corpus.yml` default config written to disk with provider, ignore patterns, and budget caps

**Acceptance criteria:**
- [x] `pip install -e .` succeeds and `corpus --help` prints the command list
- [x] `cd` into any git repo, run `corpus init`, and `.corpus/corpus.yml` and `.corpus/state.json` exist on disk
- [x] `corpus init` prints a file count summary ("Found N files — N ignored") without error
- [x] Running `corpus init` a second time does not clobber existing config (prompts or skips gracefully)
- [x] `.corpus/` itself does not appear in the scan list (self-exclusion works)

**Depends on:** Nothing (Phase 1a is the walking skeleton)

---

### Phase 1b — tree-sitter integration → real graph.json `[x]`
**Goal:** `corpus update` parses every tracked file with tree-sitter, extracts symbols and imports, and writes a valid `graph.json` — no LLM calls, human-verifiable output.
**Deliverables:**
- tree-sitter integration for Python (primary) + JavaScript/TypeScript (secondary) with graceful fallback for unsupported languages (node with empty symbols list)
- Node ID assignment: short random strings, stable across runs for unchanged paths
- `graph.json` written to `.corpus/` conforming to the schema in SPEC §04
- `state.json` updated with per-file content hashes and last-run commit hash
- Import/call edge extraction from tree-sitter parse trees

**Acceptance criteria:**
- [x] `corpus update` on a Python repo produces `.corpus/graph.json` that is valid JSON and contains one node per tracked file/directory
- [x] `python -c "import json; d=json.load(open('.corpus/graph.json')); print(len(d['nodes']), 'nodes,', len(d['edges']), 'edges')"` prints non-zero counts
- [x] Re-running `corpus update` on an unchanged repo produces the same node IDs (stability check: `jq '[.nodes[].id]|sort' .corpus/graph.json` output is identical on two consecutive runs)
- [x] A file with known imports (e.g., `import os`) produces at least one edge in `graph.json`
- [x] `.corpus/state.json` contains a `file_hashes` map with an entry for every tracked file


**Depends on:** Phase 1a

---

### Phase 1c — LLM wrapper + per-file docs `[x]`
**Goal:** `corpus update` generates plain-language docs for every tracked file and writes them to `.corpus/docs/`, completing M1 (static brain).
**Deliverables:**
- `llm.py` wrapper: `generate(prompt, max_tokens)` with Gemini 2.5 Flash primary, Groq fallback on 429, structured output parsing, one retry on malformed response
- API key config: read from environment variables (`GEMINI_API_KEY`, `GROQ_API_KEY`), documented in README section
- Per-file doc generation: prompt = file source + symbol list from graph; output = purpose, key symbols, connections, gotchas, importance 1–5
- `.corpus/docs/` tree mirrors repo structure; `_dir.md` rollup files generated from child docs
- `graph.json` updated with `importance` and `doc` path per node
- Hard caps respected: `max_files_per_update`, `max_tokens_per_call`, `max_calls_per_day` from `corpus.yml`; files exceeding cap remain stale with a printed warning
- `corpus init` end-of-run message prints the `claude mcp add corpus ...` registration command

**Acceptance criteria:**
- [ ] `GEMINI_API_KEY=<key> corpus update` on a ~10-file Python repo completes without error and produces one `.md` file per tracked source file under `.corpus/docs/`
- [ ] Each generated doc contains at least a "purpose" paragraph and a "symbols" section (verified by reading 3 sample docs)
- [ ] `cat .corpus/docs/<somefile>.py.md` produces human-readable prose, not JSON or raw prompt
- [ ] `jq '.nodes[] | select(.importance != null) | .importance' .corpus/graph.json` returns numeric values 1–5 for all file nodes
- [ ] Running `corpus update` with `max_calls_per_day: 0` in `corpus.yml` causes zero LLM calls and prints a budget warning
- [ ] A `_dir.md` rollup file exists for every directory that contains tracked files

**Depends on:** Phase 1b

---

### Phase 2 — Incremental updates (M2) `[x]`
**Goal:** `corpus update` re-docs only changed files plus symbol-gated direct importers plus ancestor rollups; a rename preserves node ID; update of ≤15 changed files completes in under 60 seconds.
**Deliverables:**
- Snapshot diff: `git diff -M` between current HEAD and `state.json`'s stored commit hash, supplemented by content-hash comparison for uncommitted edits
- Rename handling: git-detected renames update `path` on existing node; doc file moved to mirror new path; ID/importance/history preserved
- Invalidation logic: re-doc set = changed files ∪ (direct importers where exported symbols changed); max one hop
- Rollup regeneration: only ancestor `_dir.md` files of re-doc'd nodes
- Staleness flag: `stale: true` on nodes whose hash differs from `state.json`; directories stale if any descendant stale

**Acceptance criteria:**
- [x] Edit 3 files in a test repo, run `corpus update`, and confirm via stdout log that only those 3 files (plus any symbol-changed importers) were re-doc'd — not all files
- [x] Rename a file (`git mv old.py new.py`), run `corpus update`, and confirm the node in `graph.json` has the new path but the same `id` as before the rename
- [x] `corpus update` on a repo with 15 changed files completes in under 60 seconds (timed with `time corpus update`)
- [x] An unmodified file's `id` and `importance` are unchanged after an update that touches other files
- [x] `jq '[.nodes[] | select(.stale==true)] | length' .corpus/graph.json` returns the correct count of stale nodes after editing files without running update

**Depends on:** Phase 1c

---

### Phase 3 — MCP bridge + dogfood week (M3) `[x]`
**Goal:** Six MCP tools wired into Claude Code; one week of real daily use; doc format revised from findings.
**Deliverables:**
- `corpus serve --mcp` launches a FastMCP stdio server exposing all six tools: `corpus_overview`, `corpus_doc`, `corpus_relations`, `corpus_find`, `corpus_changes`, `corpus_stale`
- Every tool reads from `.corpus/` (no LLM calls at query time); staleness checked live against working-tree file hashes
- Every tool call POSTs a fire-and-forget event `{tool, node_id, ts}` to the sidecar at `localhost:7077` (silently drops if sidecar not running)
- `claude mcp add corpus` registration documented and tested
- Dogfood: one week of real use on the Corpus repo itself; notes captured in a `DOGFOOD.md` scratch file
- Doc format revision applied based on dogfood notes (≤1 follow-on builder task)

**Acceptance criteria:**
- [ ] `claude mcp add corpus -- python -m corpus.mcp` (or equivalent) registers without error; `claude` lists `corpus` in its tool panel
- [ ] In a Claude Code session, calling `corpus_overview()` returns a project summary without reading any raw source files
- [ ] `corpus_doc("path/to/file.py")` returns the doc for that file including its staleness flag
- [ ] `corpus_find("AuthMiddleware")` returns the node for the file containing that symbol
- [ ] `corpus_stale()` returns a list of all stale nodes (verified by editing a file and calling the tool)
- [ ] After dogfood week, at least one doc format change is implemented and noted in DECISIONS.md

**Depends on:** Phase 1c (Phase 2 recommended but not blocking — stale flags cover the gap)

---

### Phase 4 — Static graph viewer (M4) `[x]`
**Goal:** `corpus serve` opens a browser with a force-directed graph; folders collapse/expand; clicking a node shows its doc; importance shapes visible rank; stale nodes are amber.
**Deliverables:**
- React 18 + Vite frontend in `frontend/`; `corpus serve` builds (or uses pre-built dist) and launches uvicorn serving it on `localhost:7077`
- react-force-graph rendering `graph.json`; dir nodes collapsible; file nodes revealed by importance rank with "show all" toggle
- Click a node → doc panel opens with rendered markdown content fetched from the sidecar
- Stale nodes rendered amber; non-stale nodes teal; collapsed ancestors of stale descendants glow amber
- Sidecar FastAPI routes: `GET /graph` returns `graph.json`; `GET /doc?path=...` returns doc markdown; `WS /events` accepts websocket connections (events stubbed for now)

**Acceptance criteria:**
- [ ] `corpus serve` opens a browser tab (or prints the URL) and the graph renders within 5 seconds on a 200-node repo
- [ ] Clicking a directory node collapses/expands its children without a page reload
- [ ] Clicking a file node opens a side panel with the doc content
- [ ] After editing a file (without running `corpus update`), the corresponding node is amber within the polling interval (≤5 seconds)
- [ ] `curl localhost:7077/graph` returns valid JSON with `nodes` and `edges` arrays
- [ ] On a 200-node repo, pan and zoom remain smooth (no visible frame drops on a normal dev machine)

**Depends on:** Phase 1c (needs `.corpus/` populated), Phase 3 (sidecar architecture established)

---

### Phase 5 — Live wire (M5) `[x]`
**Goal:** Agent queries from Claude Code make the consulted graph nodes light up in real time in the browser — the demo.
**Deliverables:**
- MCP tools POST events to `localhost:7077/event` on every tool call (fire-and-forget, connection errors silently ignored)
- Sidecar fans out `{ev: "query", node, tool, ts}` frames over `WS /events` to all connected frontends
- Frontend websocket client: on `query` event, pulse the named node teal for ~2 seconds; collapsed ancestors glow so activity is visible at any zoom
- On `graph` event (fired after `corpus update`), frontend soft-reloads `graph.json` without full page refresh
- On `stale` event, frontend flips node amber or back without polling

**Acceptance criteria:**
- [ ] In a browser with the graph open, run `corpus_overview()` in Claude Code and confirm the root/overview node pulses teal within 1 second
- [ ] Run `corpus_doc("some/file.py")` and confirm exactly that file's node pulses teal
- [ ] Run `corpus update` and confirm the graph refreshes (node positions may shuffle; content updates) without a manual reload
- [ ] Edit a file; sidecar detects the stale event (via the existing poll or a triggered check) and the node flips amber in the open browser
- [ ] If no browser is open, MCP tool calls complete normally with no errors (event POST silently drops)

**Depends on:** Phase 3 (MCP event emission), Phase 4 (frontend websocket client)

---

## Parking lot

> Ideas deferred mid-work. One line each. Reviewed only during plan revisions — not a backlog to secretly build from.

- Per-node changelog (`corpus/changelog/*.jsonl`) — post-core, SPEC §03 mentions it
- `corpus explain` — plain-English summary of uncommitted diff — post-core command
- Health overlays (churn, last-touched date) on graph nodes
- Onboarding tour mode
- `LATER.md` file for capturing in-session scope-creep ideas (per SPEC build rules)
- Auto-watcher / commit hook convenience wrapper (explicitly cut from v1, may revisit post-M5)
- Per-language grammar coverage beyond Python + JS/TS (add grammars per user demand)
- Paid / local LLM provider support (config-level swap, architecture already supports it)
- Switch `pathspec` dialect from `"gitwildmatch"` to `"gitignore"` in `ignore.py`/`config.py` — `gitwildmatch` deprecated in pathspec 1.1.1, will become breaking in a future release
- `Found 1 files` grammar nit — should be `Found 1 file` (singular)
- `corpus init --help` em-dash mojibake in Windows CP1252 console — encoding issue, not a code bug
