"""Generate per-file docs and directory rollup files under .corpus/docs/."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from corpus.llm import generate, extract_importance

# Rough token estimate: 1 token ≈ 4 characters of English text.
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN



def _truncate_source(
    source_code: str,
    prompt_without_source: str,
    max_tokens: int,
) -> str:
    """
    Truncate source_code so the assembled prompt fits within 75% of max_tokens.
    Returns the (possibly truncated) source_code string.
    """
    budget_chars = int(max_tokens * 0.75) * _CHARS_PER_TOKEN
    overhead_chars = len(prompt_without_source)
    source_budget_chars = budget_chars - overhead_chars

    if source_budget_chars <= 0:
        return "... [truncated]"

    if len(source_code) <= source_budget_chars:
        return source_code

    return source_code[:source_budget_chars] + "\n... [truncated]"


def generate_file_doc(
    node: dict,
    graph: dict,
    repo_root: Path,
    corpus_dir: Path,
    config: dict,
) -> tuple[str, int | None]:
    """
    Generate and write a doc file for a single graph node (file type only).

    Returns (doc_text, importance_int_or_none).
    """
    max_tokens: int = config.get("limits", {}).get("max_tokens_per_call", 8192)
    rel_path: str = node["path"]
    language: str = node.get("lang") or "unknown"

    # Read source code
    abs_path = repo_root / rel_path
    try:
        source_code = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        source_code = "(file not readable)"

    # Symbol list
    symbols: list[str] = node.get("symbols") or []
    symbol_list = "\n".join(symbols) if symbols else "(none detected)"

    # Resolve edges
    node_id = node["id"]
    id_to_path: dict[str, str] = {n["id"]: n["path"] for n in graph.get("nodes", [])}

    imports_list_parts: list[str] = []
    imported_by_list_parts: list[str] = []
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports":
            continue
        if edge["from"] == node_id:
            target_path = id_to_path.get(edge["to"])
            if target_path:
                imports_list_parts.append(target_path)
        if edge["to"] == node_id:
            src_path = id_to_path.get(edge["from"])
            if src_path:
                imported_by_list_parts.append(src_path)

    imports_list = "\n".join(imports_list_parts) if imports_list_parts else "(none)"
    imported_by_list = (
        "\n".join(imported_by_list_parts) if imported_by_list_parts else "(none)"
    )

    # Build prompt skeleton without source to measure overhead
    prompt_skeleton = (
        f"File: {rel_path}\n"
        f"Language: {language}\n"
        f"\n"
        f"Source code:\n"
        f"```{language}\n"
        f"\n"
        f"```\n"
        f"\n"
        f"Symbols already extracted by static analysis (use these exactly — do not add or remove):\n"
        f"{symbol_list}\n"
        f"\n"
        f"Files that import this file (from the dependency graph):\n"
        f"{imported_by_list}\n"
        f"\n"
        f"Files this file imports (from the dependency graph):\n"
        f"{imports_list}\n"
        f"\n"
        f"Write the documentation for this file. Follow the format in your instructions exactly.\n"
        f"For the Importance section, output this exact line format:\n"
        f"Rating: N/5 — one-sentence reason.\n"
        f"where N is an integer from 1 to 5."
    )

    source_code = _truncate_source(source_code, prompt_skeleton, max_tokens)

    prompt = (
        f"File: {rel_path}\n"
        f"Language: {language}\n"
        f"\n"
        f"Source code:\n"
        f"```{language}\n"
        f"{source_code}\n"
        f"```\n"
        f"\n"
        f"Symbols already extracted by static analysis (use these exactly — do not add or remove):\n"
        f"{symbol_list}\n"
        f"\n"
        f"Files that import this file (from the dependency graph):\n"
        f"{imported_by_list}\n"
        f"\n"
        f"Files this file imports (from the dependency graph):\n"
        f"{imports_list}\n"
        f"\n"
        f"Write the documentation for this file. Follow the format in your instructions exactly.\n"
        f"For the Importance section, output this exact line format:\n"
        f"Rating: N/5 — one-sentence reason.\n"
        f"where N is an integer from 1 to 5."
    )

    doc_text = generate(prompt, max_tokens, config)
    importance = extract_importance(doc_text)

    # Write doc file: .corpus/docs/{rel_path}.md
    doc_rel = f"docs/{rel_path}.md"
    doc_path = corpus_dir / "docs" / rel_path
    doc_path = doc_path.parent / (doc_path.name + ".md")
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(doc_text, encoding="utf-8")

    # Store corpus-relative doc path on node
    node["doc"] = doc_rel

    return doc_text, importance


def _first_sentence_of_purpose(doc_text: str) -> str:
    """
    Extract the first non-empty line after the '## Purpose' heading.
    Returns the line, or an empty string if not found.
    """
    lines = doc_text.splitlines()
    in_purpose = False
    for line in lines:
        stripped = line.strip()
        if stripped == "## Purpose":
            in_purpose = True
            continue
        if in_purpose:
            if stripped.startswith("## "):
                # Next section — nothing found
                break
            if stripped:
                # Return first sentence only (up to the first period)
                dot_idx = stripped.find(".")
                if dot_idx != -1:
                    return stripped[: dot_idx + 1]
                return stripped
    return ""


def generate_dir_rollup(
    dir_path: str,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    """
    Generate a _dir.md rollup for `dir_path` (repo-relative posix path, or '.' for root).

    Reads already-written child file docs to extract Purpose first sentences.
    Writes to .corpus/docs/{dir_path}/_dir.md.
    """
    docs_dir = corpus_dir / "docs"

    if dir_path == ".":
        dir_docs_path = docs_dir
        display_dir = "."
    else:
        dir_docs_path = docs_dir / dir_path
        display_dir = dir_path

    # Collect direct children: subdirs and files documented under this dir
    child_subdirs: list[str] = []
    child_files: list[str] = []

    if dir_docs_path.exists():
        for child in sorted(dir_docs_path.iterdir()):
            if child.name == "_dir.md":
                continue
            if child.is_dir():
                # A subdirectory — record its relative name
                if dir_path == ".":
                    child_subdirs.append(child.name)
                else:
                    child_subdirs.append(child.name)
            elif child.is_file() and child.suffix == ".md":
                child_files.append(child.name)

    child_subdirs.sort()
    child_files.sort()

    contents_lines: list[str] = []

    # Subdirectories first
    for subdir_name in child_subdirs:
        if dir_path == ".":
            subdir_rel = subdir_name
        else:
            subdir_rel = f"{dir_path}/{subdir_name}"

        subdir_dir_md = docs_dir / subdir_rel / "_dir.md"
        first_summary_sentence = ""
        if subdir_dir_md.exists():
            subdir_text = subdir_dir_md.read_text(encoding="utf-8")
            first_summary_sentence = _first_sentence_of_summary(subdir_text)

        entry = f"- `{subdir_name}/`"
        if first_summary_sentence:
            entry += f" — (rollup) {first_summary_sentence}"
        contents_lines.append(entry)

    # Files next
    for md_name in child_files:
        # md_name is like "config.py.md" — strip the trailing .md
        source_name = md_name[:-3] if md_name.endswith(".md") else md_name

        if dir_path == ".":
            file_doc_path = docs_dir / md_name
        else:
            file_doc_path = docs_dir / dir_path / md_name

        first_purpose_sentence = ""
        importance_str = ""
        if file_doc_path.exists():
            doc_text = file_doc_path.read_text(encoding="utf-8")
            first_purpose_sentence = _first_sentence_of_purpose(doc_text)
            imp = extract_importance(doc_text)
            if imp is not None:
                importance_str = f" Importance: {imp}/5."

        entry = f"- `{source_name}`"
        if first_purpose_sentence:
            entry += f" — {first_purpose_sentence}{importance_str}"
        elif importance_str:
            entry += importance_str
        contents_lines.append(entry)

    contents_block = "\n".join(contents_lines) if contents_lines else "- (none)"

    # Summary: synthesize from child purposes
    child_purposes: list[str] = []
    for md_name in child_files:
        if dir_path == ".":
            file_doc_path = docs_dir / md_name
        else:
            file_doc_path = docs_dir / dir_path / md_name
        if file_doc_path.exists():
            doc_text = file_doc_path.read_text(encoding="utf-8")
            sent = _first_sentence_of_purpose(doc_text)
            if sent:
                child_purposes.append(sent)

    if child_purposes:
        summary = " ".join(child_purposes[:4])
    else:
        summary = f"The `{display_dir}` directory contains tracked source files."

    rollup_text = (
        f"## Directory: {display_dir}\n"
        f"\n"
        f"## Contents\n"
        f"\n"
        f"{contents_block}\n"
        f"\n"
        f"## Summary\n"
        f"\n"
        f"{summary}\n"
    )

    out_path = dir_docs_path / "_dir.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rollup_text, encoding="utf-8")


def _first_sentence_of_summary(dir_md_text: str) -> str:
    """
    Extract the first non-empty line in the Summary section of a _dir.md file.
    """
    lines = dir_md_text.splitlines()
    in_summary = False
    for line in lines:
        stripped = line.strip()
        if stripped == "## Summary":
            in_summary = True
            continue
        if in_summary:
            if stripped.startswith("## "):
                break
            if stripped:
                dot_idx = stripped.find(".")
                if dot_idx != -1:
                    return stripped[: dot_idx + 1]
                return stripped
    return ""
