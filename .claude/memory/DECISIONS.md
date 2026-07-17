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
