# DESIGN — Phase 1c Doc Format
# Build spec for builder. Every section is implementable as written.

---

## 1. Per-file doc format

### The one job

Each `.md` file must let a developer (or an AI agent) understand what a file does, what names it exposes, how it connects to the rest of the codebase, what will bite you, and how important it is — without reading the source.

### Exact section structure

Sections appear in this exact order with these exact H2 headings. No other headings. No preamble before the first heading.

```
## Purpose
## Symbols
## Connections
## Gotchas
## Importance
```

**Purpose** — One to three sentences of prose. What the file does, not what it contains. No bullet points. Must answer "why does this file exist?"

**Symbols** — A markdown list. One entry per exported/top-level symbol from the `symbols` array in `graph.json`. Format: `` - `SymbolName` — one-line description ``. If the symbols list is empty (unsupported language or no exports), write `- none`. Never invent symbols not in the list.

**Connections** — A markdown list of files this file depends on or is depended on by, drawn from the edges in `graph.json`. Format: `` - `path/to/other.py` — nature of relationship (imports / imported by) ``. If no connections exist in the graph, write `- none`.

**Gotchas** — A markdown list of non-obvious things: hidden coupling, side effects on import, required ordering, config assumptions, known fragility. If there is nothing worth flagging, write `- none`. Do not pad this section with obvious observations.

**Importance** — A single line in this exact format, no variation:

```
Rating: N/5 — one-sentence reason.
```

Where N is an integer 1 through 5. The sentence after the em dash explains the rating in the context of the repo, not generic software commentary.

### Importance scale

```
1 — Peripheral utility or test helper. Rarely touched, narrow blast radius.
2 — Supporting module. Used by a few callers; failure is contained.
3 — Workhorse. Central to a feature or subsystem; breaking it hurts multiple things.
4 — Load-bearing. Multiple subsystems depend on it; changes require cross-repo reasoning.
5 — Foundation. Everything else depends on this; a change here is a refactor event.
```

### Concrete example

Source file: `corpus/ignore.py` (~30 lines, extracts tracked files by applying gitignore + corpus.yml ignore patterns).

Symbols extracted by tree-sitter: `["get_tracked_files"]`
Connections in graph: imports `corpus/config.py`; imported by `corpus/cli.py`

Expected doc output at `.corpus/docs/corpus/ignore.py.md`:

```markdown
## Purpose

Determines which files in the repository corpus should process. Applies two layers of filtering: the repo's own `.gitignore` rules, then the additional patterns from `corpus.yml`. Returns an absolute-path list of files that are in scope for parsing and doc generation.

## Symbols

- `get_tracked_files` — accepts a repo root and a loaded config dict; returns `(tracked_files, ignored_count)` where `tracked_files` is a list of absolute Paths and `ignored_count` is the number of files excluded.

## Connections

- `corpus/config.py` — imports config dict to read the `ignore` patterns list
- `corpus/cli.py` — imported by; `update` command calls `get_tracked_files` to build the file list before parsing

## Gotchas

- Relies on `pathspec` for gitignore-style matching; the `gitwildmatch` dialect used in v0.1 is deprecated in pathspec 1.1.1 and will break in a future release.
- `.corpus/` self-exclusion is enforced here, not in the caller — removing this file from scope would cause corpus to doc itself recursively.

## Importance

Rating: 3/5 — Every run of `corpus update` passes through this function; wrong ignore logic silently drops or includes files, corrupting every downstream artifact.
```

---

## 2. `_dir.md` rollup format

### Exact structure

One file per directory that contains tracked files. Filename is always `_dir.md`. Located at `.corpus/docs/<dir-path>/_dir.md`.

Sections in this exact order:

```
## Directory: <relative-dir-path>
## Contents
## Summary
```

**Directory header** — The H2 heading itself names the directory. `relative-dir-path` is the posix path relative to the repo root (e.g., `corpus` or `src/auth`).

**Contents** — A markdown list of all direct children (files and subdirectories) that are tracked. One line per child. Format:

For files: `` - `filename.py` — first sentence from that file's Purpose section, verbatim. Importance: N/5. ``

For subdirectories: `` - `subdir/` — (rollup) first sentence from `subdir/_dir.md`'s Summary section. ``

Entries are sorted: subdirectories first (alphabetical), then files (alphabetical).

**Summary** — Two to four sentences of prose synthesized from the child purposes. What does this directory as a unit accomplish? What is its boundary? This is what gets pulled into a parent directory's rollup — write it so it stands alone out of context.

### Concrete example

Directory: `corpus/` with three tracked files: `config.py`, `ignore.py`, `parser.py`.

Output at `.corpus/docs/corpus/_dir.md`:

```markdown
## Directory: corpus

## Contents

- `config.py` — Reads and writes `corpus.yml`, supplying typed defaults for every config key. Importance: 2/5.
- `ignore.py` — Determines which files in the repository corpus should process. Importance: 3/5.
- `parser.py` — Extracts top-level symbols and import specifiers from Python, JavaScript, and TypeScript source files using tree-sitter. Importance: 4/5.

## Summary

The `corpus` package implements the full CLI engine: configuration loading, file filtering, AST-based symbol extraction, graph construction, and LLM-driven doc generation. It is the entire backend — the frontend and MCP layer call into this package but own no logic themselves. Changes to modules in this directory affect every downstream artifact.
```

---

## 3. LLM prompt template

### System prompt (constant across all calls)

```
You are a senior software engineer writing internal documentation for a codebase.
Your output will be stored as a plain markdown file and read by both developers and AI agents.

Rules:
- Write only what is directly supported by the source code provided. Do not speculate.
- Be specific. Name the actual functions, classes, and modules involved.
- Gotchas must be genuinely non-obvious. Do not list things any reader can see in the first two lines.
- Importance must reflect this file's role in THIS repository, not generic importance of its pattern.
- Output exactly the five sections below, in order, with exactly these H2 headings. No other text before, between, or after them.

## Purpose
## Symbols
## Connections
## Gotchas
## Importance
```

### User prompt template

```
File: {file_path}
Language: {language}

Source code:
```{language}
{source_code}
```

Symbols already extracted by static analysis (use these exactly — do not add or remove):
{symbol_list}

Files that import this file (from the dependency graph):
{imported_by_list}

Files this file imports (from the dependency graph):
{imports_list}

Write the documentation for this file. Follow the format in your instructions exactly.
For the Importance section, output this exact line format:
Rating: N/5 — one-sentence reason.
where N is an integer from 1 to 5.
```

### Placeholder definitions

| Placeholder | Value | Format |
|---|---|---|
| `{file_path}` | Repo-relative posix path | `corpus/ignore.py` |
| `{language}` | Lang string from graph node | `python`, `javascript`, `typescript`, `tsx`, or `unknown` |
| `{source_code}` | Full file text, read from disk | Raw string, no truncation unless `max_tokens_per_call` forces it |
| `{symbol_list}` | From `node["symbols"]` in graph | Newline-separated bare names, one per line. If empty: `(none detected)` |
| `{imported_by_list}` | Nodes with an `imports` edge pointing TO this node | Newline-separated posix paths. If empty: `(none)` |
| `{imports_list}` | Nodes this node has `imports` edges TO | Newline-separated posix paths. If empty: `(none)` |

### Token budget for the user prompt

Assemble the prompt in this order. If the total assembled prompt exceeds `(max_tokens_per_call * 0.75)` estimated tokens, truncate `{source_code}` from the bottom (add `\n... [truncated]` as the last line) until it fits. Never truncate symbol or connection lists.

---

## 4. Structured output parsing

### Extracting the importance value

After receiving the LLM response text, extract the importance integer with this regex applied to the full response string:

```python
import re

_IMPORTANCE_RE = re.compile(r"Rating:\s*([1-5])\s*/\s*5", re.IGNORECASE)

def extract_importance(response_text: str) -> int | None:
    """Return the importance integer (1-5) from the LLM response, or None if not found."""
    match = _IMPORTANCE_RE.search(response_text)
    if match:
        return int(match.group(1))
    return None
```

If `extract_importance` returns `None` on the first response, that counts as a malformed response. Trigger the one retry (re-send identical prompt). If the retry also returns `None`, log a warning and store `importance: null` on the node. Do not raise an exception; the doc text is still valid and should be written.

### Extracting the doc body

The entire LLM response string is the doc body. Write it to disk as-is. Do not strip or reformat. The LLM is instructed to produce only the five sections; if it includes preamble text despite instructions (rare), it still renders fine as markdown.

### Malformed response definition

A response is malformed if and only if:
1. It does not contain the substring `## Purpose`, OR
2. `extract_importance` returns `None`.

Any response containing `## Purpose` and a parseable `Rating: N/5` line is considered valid, even if other sections are thin.

---

## 5. File naming convention

### Rule

`.corpus/docs/` mirrors the repo structure exactly. Append `.md` to the full filename.

```
{repo_root}/{rel_path}  →  {corpus_dir}/docs/{rel_path}.md
```

### Examples

| Source file (repo-relative) | Doc file (corpus-relative) |
|---|---|
| `corpus/ignore.py` | `.corpus/docs/corpus/ignore.py.md` |
| `corpus/cli.py` | `.corpus/docs/corpus/cli.py.md` |
| `src/auth/middleware.ts` | `.corpus/docs/src/auth/middleware.ts.md` |
| `main.py` | `.corpus/docs/main.py.md` |
| `index.js` | `.corpus/docs/index.js.md` |

### Directory rollup files

```
{dir_path}/  →  {corpus_dir}/docs/{dir_path}/_dir.md
```

| Directory (repo-relative) | Rollup file |
|---|---|
| `corpus/` | `.corpus/docs/corpus/_dir.md` |
| `src/auth/` | `.corpus/docs/src/auth/_dir.md` |
| `.` (repo root) | `.corpus/docs/_dir.md` |

The repo root rollup is generated when there are tracked files directly in the root (not just in subdirectories). Its heading is `## Directory: .` (dot, not blank).

### graph.json `doc` field

Set `node["doc"]` to the corpus-relative posix path of the doc file (without the leading `.corpus/` prefix):

```
"doc": "docs/corpus/ignore.py.md"
```

This is relative to `.corpus/`, not to the repo root. Consumers prepend `.corpus/` to resolve it.

---

## 6. Implementation order for builder

Build in this order so each step is independently testable:

1. `corpus/llm.py` — `generate(prompt: str, max_tokens: int) -> str`. Gemini primary, Groq fallback on HTTP 429, one retry on malformed response. API keys from `os.environ`. Raise `LLMError` (custom exception) only on total failure (both providers exhausted or both malformed).

2. `corpus/docs.py` — `generate_file_doc(node, graph, repo_root, corpus_dir, config) -> str`. Assembles prompt, calls `llm.generate`, writes the `.md` file, returns the doc text.

3. `_dir.md` generation — `generate_dir_rollup(dir_path, child_docs, corpus_dir)`. Called after all file docs for a directory are written. Reads each child's Purpose first sentence from the already-written doc file (regex: first non-empty line after `## Purpose`).

4. Integration in `corpus/cli.py` `update` command — after `write_graph`, iterate file nodes respecting budget caps, call `generate_file_doc`, collect `{node_id: importance}`, patch `graph["nodes"]` importance and doc fields, call `write_graph` again with the updated graph.

5. Budget enforcement — track `calls_made` as a counter. Before each LLM call: if `calls_made >= config["limits"]["max_calls_per_day"]`, print `Warning: daily call limit reached ({max_calls_per_day}). {N} files not documented.` and break. Set `stale: True` on undocumented nodes.

6. `corpus init` end-of-run message — after scaffolding completes, always print:
   ```
   To register with Claude Code, run:
     claude mcp add corpus -- python -m corpus.mcp
   ```
   This prints even though `corpus.mcp` does not exist yet (Phase 3). It is a forward instruction, not a runnable command in Phase 1c.
