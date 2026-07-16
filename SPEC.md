# Corpus — Technical Design Document

**v1 · Companion to PRODUCT.md**

Every decision that was open in conversation is resolved here as a concrete proposal — items marked **[DECISION]** were vetoable before build; after M1 starts, changes cost code.

**Constraints:**
- 100% free stack — every dependency FOSS or free tier
- Local only: no cloud, no accounts
- Storage: plain files, no database

---

## 01 · Stack

| Component | Choice | Why | Cost |
|---|---|---|---|
| Engine + CLI | Python 3.11+, Click | Best tree-sitter bindings; developer's primary language; Click gives clean subcommands | FOSS |
| Parsing | tree-sitter + language grammars | Local AST extraction — symbols, imports, calls — deterministic, ms per file, ~36 languages. Zero LLM calls for structure | MIT |
| Git access | git CLI via subprocess | Diffs, rename detection (`git diff -M`), status for staleness. Git itself is the API | FOSS |
| LLM | Gemini 2.5 Flash (AI Studio free tier) | ~1,500 req/day, 1M-token context — whole modules in one call. Behind a provider-agnostic wrapper | Free tier |
| LLM fallback | Groq (Llama 3.3 70B free tier) | Automatic retry lane on Gemini 429s. Small per-file patches only — tight TPM limits | Free tier |
| MCP server | FastMCP (Python) | Tools as decorated Python functions; stdio transport into Claude Code | MIT |
| Event bridge | FastAPI + websockets, uvicorn | Tiny sidecar for the live monitor; serves frontend build | FOSS |
| Frontend | React 18 + Vite | Developer's stack; static build, runs on localhost, no hosting | FOSS |
| Graph render | react-force-graph (d3-force) | Force layout, click/hover/zoom out of the box, canvas-based — 500+ nodes stay smooth | MIT |
| Storage | Plain markdown + JSON in `.corpus/` | Human-readable, git-diffable, greppable, zero infra | Free |

**[DECISION]** Python for engine + MCP server, React for frontend, no database anywhere. Plain files make every layer inspectable with `cat` and debuggable without tooling.

---

## 02 · CLI Lifecycle — Five Commands, the Whole Surface

```
pipx install corpus        # once per machine — puts the CLI on PATH
cd myproject
corpus init                # once per project — scaffolds .corpus/, then prompts:
                           #   "Found 143 files (~90 API calls). First scan can take
                           #    a while on large projects. Run now? [Y/n]"
corpus update              # whenever you want the brain current
corpus serve               # sidecar + frontend — opens the window
corpus explain             # post-core: plain-English summary of uncommitted diff
```

- `init` scaffolds instantly and **never scans without asking** — declining leaves everything scaffolded and stale; the first `corpus update` then performs the full scan deliberately.
- `init` ends by printing (or offering to run) the one-time `claude mcp add corpus …` registration — the brain isn't usable until the bridge is plugged into Claude Code. This is where demos silently fail if forgotten.
- If the command surface ever grows past five, the design has gone wrong somewhere.

---

## 03 · Data Layout — Everything Lives in `.corpus/`

One hidden directory at the repo root (same convention as `.git/`: tooling metadata, not project content). Committed to git — teammates and CI get the brain for free.

```
.corpus/
├── graph.json          # nodes, edges, hierarchy — the map
├── state.json          # last update: commit hash, timestamp, file hashes
├── docs/
│   ├── _root.md        # project-level overview (rollup of top dirs)
│   ├── api/
│   │   ├── _dir.md     # rollup doc for api/
│   │   ├── auth.py.md  # file doc — mirrors repo structure
│   │   └── routes.py.md
│   └── frontend/…
├── changelog/
│   └── n_04f2.jsonl    # per-node history, append-only (post-core)
└── corpus.yml          # config: ignore rules, collapse pins, provider
```

- `docs/` mirrors the repo tree exactly — no lookup table needed.
- `state.json` stores a content hash per tracked file at last update — staleness and incrementality both diff against it.
- Ignore rules: `.gitignore` respected automatically, plus a list in `corpus.yml` (defaults: lockfiles, migrations, build output, vendored code, binary assets, **and `.corpus/` itself** — otherwise updating docs triggers updates forever).

---

## 04 · Graph Schema & Node Identity

**The problem:** if node IDs are file paths, moving `scraper.py` to `ingest/scraper.py` destroys its history — the system sees a deletion and a creation. Identity must be decoupled from location.

```jsonc
// graph.json (abridged)
{
  "version": 1,
  "nodes": [
    {
      "id": "n_04f2",                    // stable random ID — never changes
      "path": "api/auth.py",             // current location — mutable
      "kind": "file",                    // file | dir
      "parent": "n_00a1",
      "lang": "python",
      "loc": 214,
      "symbols": ["hash_pw", "verify", "AuthMiddleware"],
      "importance": 4,                   // LLM rating from doc pass, 1–5
      "score": 0.81,                     // computed: fan-in + centrality + churn
      "stale": false,
      "doc": "docs/api/auth.py.md"
    },
    { "id": "n_00a1", "path": "api", "kind": "dir",
      "parent": "n_root", "collapsed": false, "doc": "docs/api/_dir.md" }
  ],
  "edges": [
    { "from": "n_04f2", "to": "n_07c9", "type": "imports" }
  ]
}
```

### Rename survival
1. **Git detects the rename:** `git diff -M --name-status` between last-update commit and HEAD reports `R097 scraper.py → ingest/scraper.py`.
2. **Engine updates the path, keeps the ID:** `n_04f2`'s `path` changes; ID, doc history, changelog, importance persist. Doc file moves to mirror the new path.
3. **Fallback for git-invisible moves:** content-hash matching in `state.json` catches identical files at new paths. A genuinely rewritten-and-moved file is honestly a new node — correct behavior.

**[DECISION]** Node IDs are short random strings assigned at first sight, never derived from paths. Edges reference IDs, not paths. Frontend and MCP tools accept paths for convenience and resolve internally.

### Module rules (locked)
- **Files are the atoms:** docs, staleness, history, diff-mapping — all file-level, everywhere, no exceptions.
- **Directories are the view:** rollup docs generated from child docs, shown collapsed or expanded.
- **Collapse heuristic is deterministic:** `collapse if file_count > 10 and median_loc < 80` (tunable in `corpus.yml`; per-directory pins override).
- **Display rank** inside an expanded dir = computed score (fan-in, hub centrality, size, churn) adjusted by the LLM's 1–5 importance rating. Low scorers sit behind "show all". Wrong ranking is harmless by design.
- **The LLM never defines structure.** Structure is computed; meaning is generated.

---

## 05 · The Update Pipeline — What `corpus update` Does

1. **Snapshot diff.** Working tree vs `state.json`: git diff (with `-M`) plus content hashes → sets of added / modified / renamed / deleted files.
2. **Structural pass (deterministic, free).** tree-sitter re-parses changed files → symbols, imports, calls. Nodes/edges updated. Deleted files' nodes removed; new files get fresh IDs.
3. **Invalidation — compute the blast radius.** Docs to regenerate = changed files ∪ their direct importers whose contract-facing symbols changed (§06). Ancestor rollups of all affected files queued.
4. **Semantic pass (the only LLM step).** Per invalidated file: prompt = file source + old doc + diff + one-hop neighbor summaries. Output = new doc + importance rating + optional coupling notes. Batched, budget-capped.
5. **Rollups & commit state.** Affected `_dir.md` rollups regenerate from child docs. `state.json` updated. Staleness flags clear.

**[DECISION]** Performance budget: an update after a typical session (≤15 changed files) completes in under 60 seconds and fits the free tier with room for 10+ updates/day. This budget is a design constraint, not an aspiration — it's why incrementality (M2) is core.

**M1 simplification:** M1 skips steps 1 and 3 — full regeneration every run. Correct, slow, quota-hungry, fine. Pipeline is architected as above from day one so M2 slots in without a rewrite.

---

## 06 · Invalidation Rule

The subtle failure: change `auth.py`'s function signature, and `api.py`'s doc — which describes how it calls auth — is now wrong, with zero diff lines in `api.py`.

- **Always re-doc:** every file with actual diff lines.
- **Also re-doc:** direct importers of a changed file, *if* the change touched exported/public symbols (tree-sitter identifies changed symbols; the edge list identifies importers).
- **Never cascade further than one hop.** Transitive invalidation balloons cost for marginal accuracy. Second-hop drift is caught next time those files change — and staleness means Corpus never claims false freshness anyway.
- **Directory rollups:** refresh every ancestor of any re-doc'd file, root last.

**[DECISION]** One-hop, symbol-gated invalidation. Deeper cascades are a config flag later if drift proves annoying — not a v1 default.

---

## 07 · Staleness Mechanics — Amber, Precisely Defined

- A node is **stale** when its file's current content hash ≠ the hash in `state.json`. Computed against the **working tree** — uncommitted edits count, because mid-session is exactly when it matters.
- A directory is stale if any descendant is stale.
- The MCP server checks staleness at query time and attaches it to every response: `"stale": true, "changed_since_doc": "+42/−7 lines"`. The agent knows to trust the doc less and read the file if precision matters. **Corpus never silently serves a stale doc as fresh.**
- The frontend renders stale nodes amber; a cheap mtime poll flips them live as edits happen.

---

## 08 · MCP Tool Contract — Six Tools, That's the Whole Bridge

| Tool | Input | Returns |
|---|---|---|
| `corpus_overview()` | — | Project rollup + top-level dir summaries + graph stats. The agent's first call every session. |
| `corpus_doc(path)` | file or dir path | The doc, plus staleness flag and symbol list. Dir paths return the rollup. |
| `corpus_relations(path)` | file path | Importers, imports, shared-symbol edges — the node's neighborhood. |
| `corpus_find(query)` | keyword(s) | Nodes matching by symbol name, path, or doc text. Plain text search — grep-grade, deliberately not semantic. |
| `corpus_changes(since?)` | optional ref/date | What's changed: stale files now; changelog entries once post-core ships. |
| `corpus_stale()` | — | All currently stale nodes — lets the agent suggest running `corpus update`. |

Every tool call also emits a fire-and-forget event to the event bridge: `{tool, node_id, ts}`. If no frontend is listening, events drop silently — the bridge is never load-bearing for the agent.

**[DECISION]** Six tools, no more. A fat tool list taxes every agent prompt (prior finding: curating 13 tools → 1 cut prompt tokens 76%). New tools must displace an existing one or prove they can't be an argument on an existing one.

---

## 09 · Live Event Protocol — The Wire Behind the Window

The MCP server (stdio, owned by Claude Code) POSTs events to a tiny local sidecar (FastAPI, `localhost:7077`), which fans out over websocket to any open frontend. Two processes because MCP's stdio lifecycle belongs to Claude Code — the sidecar outlives sessions and serves the static frontend build.

```jsonc
// websocket frames, sidecar → frontend
{ "ev": "query",  "node": "n_04f2", "tool": "corpus_doc", "ts": 1721000000 }
{ "ev": "stale",  "node": "n_04f2", "on": true }
{ "ev": "graph",  "reason": "update_complete" }   // frontend refetches graph.json
```

- `query` → node pulses teal ~2s; collapsed ancestors glow so activity is visible at any zoom.
- `stale` → node flips amber / back.
- `graph` → soft reload after `corpus update` finishes.
- No buffering, no replay, no auth — localhost-only, ephemeral by design.

---

## 10 · LLM Layer — One Wrapper, Two Providers, Hard Budgets

- Single `llm.generate(prompt, max_tokens)` wrapper; provider set in `corpus.yml`. Gemini 2.5 Flash primary; on 429, retry via Groq for small patches. Swapping providers is a config edit, never a refactor — free tiers change monthly and the architecture assumes it.
- Doc prompts demand structured output: purpose (2–3 sentences), key symbols with one-liners, connections, gotchas, `importance: 1–5`. Parsed, validated, rejected-and-retried once on malformed output.
- **Citation discipline:** every doc claim about a symbol must name the symbol it describes — makes hallucinated claims spot-checkable and keeps docs greppable.
- Hard caps in config: max files per update, max tokens per call, max calls per day. Hitting a cap degrades gracefully — remaining files stay amber rather than the update failing.
- **Privacy rule:** free-tier prompts may be used for provider model training. Personal repos: fine. Internship/company code: requires explicit clearance or a paid/local provider first. Config-level allowlist.

---

## 11 · Milestones with Acceptance Criteria

| # | Name | Done means |
|---|---|---|
| **M1** | Static brain | `corpus init` on a real repo produces graph.json + full docs tree. ✓ every non-ignored file has a doc; graph.json validates; ~50-file repo completes within free-tier quota. |
| **M2** | Incremental updates | ✓ editing 3 files re-docs only those + gated importers + rollups; a rename preserves node ID and history; update ≤60s. |
| **M3** | Bridge + dogfood | FastMCP server, six tools, wired into Claude Code, then a week of real use. ✓ a fresh session answers an architecture question via corpus tools without reading raw files; doc format revised from dogfood notes. |
| **M4** | Static window | ✓ a 200-node repo renders smoothly: collapse/expand, click-to-doc, importance-ranked reveal, amber staleness. |
| **M5** | Live wire | ✓ asking Claude Code a question makes the consulted nodes visibly light up in real time. The demo. |

**Post-core, by cheapness:** per-node changelog → `corpus explain` → health overlays → tour mode.

---

## 12 · Known Risks

| Risk | Mitigation |
|---|---|
| **Doc hallucination** | LLM docs served to the agent as truth can poison its work. Symbol-citation discipline (§10), staleness honesty (§07), dogfood week explicitly hunting confident-but-wrong claims. |
| **Free-tier volatility** | Quotas get cut without notice. Provider wrapper + Groq lane + hard local budgets. Worst case: updates get slower, never broken. |
| **M2 complexity spiral** | Symbol-level change detection can rabbit-hole. Guardrail: fall back to "re-doc all direct importers" — costlier but correct — and ship. |
| **Graph hairball at scale** | Force layouts degrade past ~500 visible nodes. Collapse-by-default + importance-gated reveal cap visible nodes; edges render on hover/selection above a threshold. |
| **Scope creep** | The project owner's documented additive-planning pattern. Guardrail: new component ideas go to LATER.md; the six-tool cap and five milestones are the contract. |

---

## Build Rules (for the coding agent)

1. Implement **only the current milestone**. Do not scaffold ahead.
2. New ideas go to `LATER.md`, not into code.
3. Every session ends with something runnable and inspected by the human.
4. M1 session split: (a) CLI skeleton + init scaffolding + ignore rules + scan prompt, no LLM/tree-sitter · (b) tree-sitter → real graph.json, human-verified · (c) LLM wrapper + docs for a handful of files, human-read before scaling.
