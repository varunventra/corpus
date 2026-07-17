"""
Phase 1c acceptance-criteria tests.

Acceptance criteria (from PLAN.md Phase 1c):
  AC1 - GEMINI_API_KEY=<key> corpus update produces one .md file per tracked
        source file under .corpus/docs/
  AC2 - Each doc has at least a "purpose" paragraph and a "symbols" section
  AC3 - Human-readable prose output (not JSON or raw prompt)
  AC4 - jq '.nodes[] | select(.importance != null) | .importance' .corpus/graph.json
        returns numeric values 1-5 for all file nodes
  AC5 - max_calls_per_day: 0  -> zero LLM calls + budget warning printed
  AC6 - A _dir.md rollup file exists for every directory that contains tracked files

Also tests:
  - corpus init prints the claude mcp add corpus line
  - llm.extract_importance correctly parses "Rating: 3/5 - reason." -> 3
    and returns None for gibberish
"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from corpus.cli import main
from corpus.llm import extract_importance


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

FAKE_DOC = textwrap.dedent("""\
    ## Purpose

    This is a test file that does something useful.

    ## Symbols

    - `test_func` — a test function

    ## Connections

    No notable connections.

    ## Gotchas

    No known gotchas.

    ## Importance

    Rating: 3/5 — test file.
""")


def _make_git_repo(tmp_path: Path) -> Path:
    """Initialise a minimal git repo."""
    subprocess.run(
        ["git", "init", str(tmp_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return tmp_path


def _init_corpus(tmp_path: Path) -> None:
    runner = CliRunner()
    old = os.getcwd()
    try:
        os.chdir(tmp_path)
        runner.invoke(main, ["init"], catch_exceptions=False)
    finally:
        os.chdir(old)


def _run_update(tmp_path: Path, env_overrides: dict | None = None):
    """Run corpus update with a mocked LLM generate call."""
    runner = CliRunner()
    old = os.getcwd()
    base_env = {"GEMINI_API_KEY": "fake-key-for-testing"}
    if env_overrides:
        base_env.update(env_overrides)
    try:
        os.chdir(tmp_path)
        with mock.patch("corpus.llm.generate", return_value=FAKE_DOC) as mock_gen:
            with mock.patch.dict(os.environ, base_env, clear=False):
                result = runner.invoke(main, ["update"], catch_exceptions=False)
        return result, mock_gen
    finally:
        os.chdir(old)


def _make_flat_repo(tmp_path: Path) -> Path:
    """
    Flat repo with 3 Python source files at the root level.
    Returns the repo root.
    """
    _make_git_repo(tmp_path)
    (tmp_path / "alpha.py").write_text("def alpha(): pass\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("def beta(): pass\n", encoding="utf-8")
    (tmp_path / "gamma.py").write_text("def gamma(): pass\n", encoding="utf-8")
    return tmp_path


def _make_nested_repo(tmp_path: Path) -> Path:
    """
    Nested repo:
      src/auth/middleware.py
      src/utils.py
    Returns the repo root.
    """
    _make_git_repo(tmp_path)
    auth_dir = tmp_path / "src" / "auth"
    auth_dir.mkdir(parents=True)
    (auth_dir / "middleware.py").write_text(
        "def check(): pass\n", encoding="utf-8"
    )
    (tmp_path / "src" / "utils.py").write_text(
        "def helper(): pass\n", encoding="utf-8"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# AC1 + AC2 + AC3 — integration test: one .md per tracked file
# ---------------------------------------------------------------------------

class TestAC1DocFilesCreated:
    def test_md_file_created_for_each_tracked_file(self, tmp_path):
        """One .md file must exist under .corpus/docs/ for every tracked Python file."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, f"update failed:\n{result.output}"

        docs_dir = repo / ".corpus" / "docs"
        for name in ["alpha.py", "beta.py", "gamma.py"]:
            doc_path = docs_dir / (name + ".md")
            assert doc_path.exists(), (
                f"Expected doc file {doc_path} but it does not exist.\n"
                f"update output:\n{result.output}"
            )

    def test_doc_path_mirrors_repo_structure(self, tmp_path):
        """Doc file path under .corpus/docs/ must mirror the repo-relative path."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        doc = repo / ".corpus" / "docs" / "alpha.py.md"
        assert doc.exists(), f"{doc} missing"

    def test_update_exit_code_zero_with_api_key(self, tmp_path):
        """corpus update with GEMINI_API_KEY set must exit 0."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

    def test_update_output_mentions_docs_written(self, tmp_path):
        """corpus update output must mention how many files were documented."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert "documented" in result.output.lower(), (
            f"Expected 'documented' in output:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# AC2 — each doc contains ## Purpose and ## Symbols
# ---------------------------------------------------------------------------

class TestAC2DocStructure:
    def test_doc_contains_purpose_heading(self, tmp_path):
        """Every generated doc must contain '## Purpose'."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        docs_dir = repo / ".corpus" / "docs"
        for name in ["alpha.py", "beta.py", "gamma.py"]:
            doc_path = docs_dir / (name + ".md")
            text = doc_path.read_text(encoding="utf-8")
            assert "## Purpose" in text, (
                f"{name}.md missing '## Purpose'. Content:\n{text[:200]}"
            )

    def test_doc_contains_symbols_heading(self, tmp_path):
        """Every generated doc must contain '## Symbols'."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        docs_dir = repo / ".corpus" / "docs"
        for name in ["alpha.py", "beta.py", "gamma.py"]:
            doc_path = docs_dir / (name + ".md")
            text = doc_path.read_text(encoding="utf-8")
            assert "## Symbols" in text, (
                f"{name}.md missing '## Symbols'. Content:\n{text[:200]}"
            )

    def test_doc_has_purpose_paragraph_content(self, tmp_path):
        """The ## Purpose section must have non-empty prose after the heading."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        doc_path = repo / ".corpus" / "docs" / "alpha.py.md"
        text = doc_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        idx = next(
            (i for i, l in enumerate(lines) if l.strip() == "## Purpose"), None
        )
        assert idx is not None, "## Purpose not found"
        # Find first non-blank line after the heading
        content_lines = [
            l for l in lines[idx + 1:] if l.strip() and not l.strip().startswith("##")
        ]
        assert content_lines, "## Purpose has no paragraph content"


# ---------------------------------------------------------------------------
# AC3 — human-readable prose, not JSON
# ---------------------------------------------------------------------------

class TestAC3HumanReadable:
    def test_doc_does_not_start_with_json_brace(self, tmp_path):
        """Doc content must not start with '{' (raw JSON output)."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        docs_dir = repo / ".corpus" / "docs"
        for name in ["alpha.py", "beta.py", "gamma.py"]:
            doc_path = docs_dir / (name + ".md")
            text = doc_path.read_text(encoding="utf-8").strip()
            assert not text.startswith("{"), (
                f"{name}.md appears to be raw JSON:\n{text[:100]}"
            )

    def test_doc_does_not_start_with_json_bracket(self, tmp_path):
        """Doc content must not start with '[' (raw JSON array)."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        docs_dir = repo / ".corpus" / "docs"
        for name in ["alpha.py", "beta.py", "gamma.py"]:
            doc_path = docs_dir / (name + ".md")
            text = doc_path.read_text(encoding="utf-8").strip()
            assert not text.startswith("["), (
                f"{name}.md appears to be a raw JSON array:\n{text[:100]}"
            )

    def test_doc_contains_markdown_heading(self, tmp_path):
        """Docs must contain at least one markdown heading (## ...)."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        doc_path = repo / ".corpus" / "docs" / "alpha.py.md"
        text = doc_path.read_text(encoding="utf-8")
        assert "## " in text, "Doc has no markdown headings at all"


# ---------------------------------------------------------------------------
# AC4 — graph.json importance field is integer 1-5
# ---------------------------------------------------------------------------

class TestAC4ImportanceField:
    def test_file_nodes_with_doc_have_integer_importance(self, tmp_path):
        """All file nodes that have a doc field must have importance as int 1-5."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        graph_path = repo / ".corpus" / "graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))

        file_nodes_with_doc = [
            n for n in graph["nodes"]
            if n.get("type") == "file" and n.get("doc") is not None
        ]
        assert file_nodes_with_doc, "No file nodes with doc field found after update"

        for node in file_nodes_with_doc:
            imp = node.get("importance")
            assert imp is not None, (
                f"Node {node['path']} has doc but importance is None"
            )
            assert isinstance(imp, int), (
                f"Node {node['path']} importance is {type(imp).__name__}, expected int"
            )
            assert 1 <= imp <= 5, (
                f"Node {node['path']} importance={imp} is outside range 1-5"
            )

    def test_importance_written_to_graph_json(self, tmp_path):
        """After mocked update, graph.json must be re-written with importance values."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)

        graph_path = repo / ".corpus" / "graph.json"
        assert graph_path.exists()
        graph = json.loads(graph_path.read_text(encoding="utf-8"))

        importance_values = [
            n["importance"]
            for n in graph["nodes"]
            if n.get("type") == "file" and n.get("importance") is not None
        ]
        assert importance_values, "No importance values set on file nodes"
        for val in importance_values:
            assert val == 3, f"Expected importance=3 (from fake doc), got {val}"

    def test_importance_is_not_string(self, tmp_path):
        """Importance values must be integers, not stringified numbers."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)

        graph = json.loads(
            (repo / ".corpus" / "graph.json").read_text(encoding="utf-8")
        )
        for node in graph["nodes"]:
            if node.get("type") == "file" and node.get("importance") is not None:
                assert not isinstance(node["importance"], str), (
                    f"importance on {node['path']} is a string: {node['importance']!r}"
                )


# ---------------------------------------------------------------------------
# AC5 — max_calls_per_day: 0 -> zero LLM calls, budget warning printed
# ---------------------------------------------------------------------------

class TestAC5BudgetCapZero:
    def _make_zero_budget_repo(self, tmp_path: Path) -> Path:
        """Create a repo with max_calls_per_day: 0 in corpus.yml."""
        repo = _make_flat_repo(tmp_path)
        _make_git_repo(repo)
        _init_corpus(repo)
        corpus_yml = repo / ".corpus" / "corpus.yml"
        corpus_yml.write_text(
            textwrap.dedent("""\
                provider: gemini
                gemini_model: gemini-2.5-flash
                groq_model: llama-3.3-70b-versatile
                limits:
                  max_files_per_update: 50
                  max_tokens_per_call: 8192
                  max_calls_per_day: 0
                ignore:
                  - "**/.corpus/**"
                  - "**/.git/**"
                  - "**/*.pyc"
                  - "**/node_modules/**"
                  - "**/__pycache__/**"
                  - "**/*.lock"
            """),
            encoding="utf-8",
        )
        return repo

    def test_zero_budget_exits_zero(self, tmp_path):
        """corpus update with max_calls_per_day=0 must exit 0."""
        repo = self._make_zero_budget_repo(tmp_path)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, (
            f"Expected exit 0 with zero budget, got {result.exit_code}:\n{result.output}"
        )

    def test_zero_budget_llm_not_called(self, tmp_path):
        """With max_calls_per_day=0, llm.generate must not be called at all."""
        repo = self._make_zero_budget_repo(tmp_path)
        result, mock_gen = _run_update(repo)
        assert result.exit_code == 0, result.output
        assert mock_gen.call_count == 0, (
            f"llm.generate was called {mock_gen.call_count} time(s) "
            f"but expected 0 calls with zero budget.\nOutput:\n{result.output}"
        )

    def test_zero_budget_prints_budget_warning(self, tmp_path):
        """With max_calls_per_day=0, output must mention 'daily call limit' or 'budget'."""
        repo = self._make_zero_budget_repo(tmp_path)
        result, _ = _run_update(repo)
        output_lower = result.output.lower()
        assert "daily call limit" in output_lower or "budget" in output_lower, (
            f"Expected budget warning in output but got:\n{result.output}"
        )

    def test_zero_budget_no_doc_files_created(self, tmp_path):
        """With max_calls_per_day=0, no .md doc files should be written."""
        repo = self._make_zero_budget_repo(tmp_path)
        _run_update(repo)

        docs_dir = repo / ".corpus" / "docs"
        md_files = list(docs_dir.rglob("*.py.md")) if docs_dir.exists() else []
        assert md_files == [], (
            f"Expected no .py.md files with zero budget, found: {md_files}"
        )


# ---------------------------------------------------------------------------
# AC6 — _dir.md rollup exists for every directory that contains tracked files
# ---------------------------------------------------------------------------

class TestAC6DirRollups:
    def test_dir_rollup_created_for_nested_dirs(self, tmp_path):
        """A _dir.md must exist for each directory containing tracked files."""
        repo = _make_nested_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, f"update failed:\n{result.output}"

        # src/auth/middleware.py -> .corpus/docs/src/auth/_dir.md
        auth_dir_md = repo / ".corpus" / "docs" / "src" / "auth" / "_dir.md"
        assert auth_dir_md.exists(), (
            f"Expected {auth_dir_md} to exist but it does not.\n"
            f"update output:\n{result.output}"
        )

        # src/utils.py -> .corpus/docs/src/_dir.md
        src_dir_md = repo / ".corpus" / "docs" / "src" / "_dir.md"
        assert src_dir_md.exists(), (
            f"Expected {src_dir_md} to exist but it does not.\n"
            f"update output:\n{result.output}"
        )

    def test_dir_rollup_contains_contents_heading(self, tmp_path):
        """Every _dir.md must contain '## Contents'."""
        repo = _make_nested_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        for rel in ["src/auth/_dir.md", "src/_dir.md"]:
            dir_md = repo / ".corpus" / "docs" / rel
            assert dir_md.exists(), f"{rel} not found"
            text = dir_md.read_text(encoding="utf-8")
            assert "## Contents" in text, (
                f"{rel} missing '## Contents'. Content:\n{text}"
            )

    def test_dir_rollup_contains_summary_heading(self, tmp_path):
        """Every _dir.md must contain '## Summary'."""
        repo = _make_nested_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        for rel in ["src/auth/_dir.md", "src/_dir.md"]:
            dir_md = repo / ".corpus" / "docs" / rel
            assert dir_md.exists(), f"{rel} not found"
            text = dir_md.read_text(encoding="utf-8")
            assert "## Summary" in text, (
                f"{rel} missing '## Summary'. Content:\n{text}"
            )

    def test_parent_dir_rollup_mentions_child_dir(self, tmp_path):
        """The src/_dir.md must reference the child directory 'auth' in its Contents."""
        repo = _make_nested_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        src_dir_md = repo / ".corpus" / "docs" / "src" / "_dir.md"
        assert src_dir_md.exists()
        text = src_dir_md.read_text(encoding="utf-8")

        # The contents block should mention auth/ (child subdir) or auth
        assert "auth" in text, (
            f"src/_dir.md should mention 'auth' in Contents but doesn't.\n{text}"
        )

    def test_flat_repo_no_dir_rollup_needed_for_root_level_files(self, tmp_path):
        """
        Files at the repo root (no subdirectory) should not generate a nested _dir.md.
        The flat layout means dirs_with_docs contains only '.' which is handled separately
        by the CLI (it does not call generate_dir_rollup for '.').
        """
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        # Root-level files (dir = '.') should NOT produce a _dir.md at .corpus/docs/_dir.md
        # because the CLI loop only adds subdirectory segments (rfind('/') == -1 -> adds '.')
        # but the sorted loop only calls generate_dir_rollup for non-'.' entries.
        # Let's verify: no crash, and root-level doc files exist.
        docs_dir = repo / ".corpus" / "docs"
        for name in ["alpha.py", "beta.py", "gamma.py"]:
            assert (docs_dir / (name + ".md")).exists()

    def test_nested_repo_doc_files_exist(self, tmp_path):
        """After update on a nested repo, the individual doc files must also exist."""
        repo = _make_nested_repo(tmp_path)
        _init_corpus(repo)
        result, _ = _run_update(repo)
        assert result.exit_code == 0, result.output

        docs_dir = repo / ".corpus" / "docs"
        assert (docs_dir / "src" / "auth" / "middleware.py.md").exists(), (
            "src/auth/middleware.py.md not found"
        )
        assert (docs_dir / "src" / "utils.py.md").exists(), (
            "src/utils.py.md not found"
        )


# ---------------------------------------------------------------------------
# corpus init MCP hint test
# ---------------------------------------------------------------------------

class TestInitMcpHint:
    def test_init_prints_claude_mcp_add_line(self, tmp_path):
        """corpus init must print a line containing 'claude mcp add corpus'."""
        _make_git_repo(tmp_path)
        runner = CliRunner()
        old = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(main, ["init"], catch_exceptions=False)
        finally:
            os.chdir(old)

        assert result.exit_code == 0, result.output
        assert "claude mcp add corpus" in result.output, (
            f"Expected 'claude mcp add corpus' in init output:\n{result.output}"
        )

    def test_init_mcp_hint_survives_re_init(self, tmp_path):
        """The MCP hint must also appear when re-running init (with 'y' confirmation)."""
        _make_git_repo(tmp_path)
        runner = CliRunner()
        old = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner.invoke(main, ["init"], catch_exceptions=False)
            result = runner.invoke(main, ["init"], input="y\n", catch_exceptions=False)
        finally:
            os.chdir(old)

        assert result.exit_code == 0, result.output
        assert "claude mcp add corpus" in result.output, (
            f"Expected MCP hint on re-init:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# llm.extract_importance unit tests
# ---------------------------------------------------------------------------

class TestExtractImportance:
    def test_parses_rating_3(self):
        """'Rating: 3/5 - reason.' must parse to integer 3."""
        result = extract_importance("## Importance\n\nRating: 3/5 — test file.")
        assert result == 3, f"Expected 3, got {result!r}"

    def test_parses_rating_1(self):
        """Rating: 1/5 must parse to 1."""
        assert extract_importance("Rating: 1/5 — trivial.") == 1

    def test_parses_rating_5(self):
        """Rating: 5/5 must parse to 5."""
        assert extract_importance("Rating: 5/5 — critical.") == 5

    def test_parses_all_valid_ratings(self):
        """All integer values 1 through 5 must parse correctly."""
        for n in range(1, 6):
            text = f"Rating: {n}/5 — reason for rating."
            result = extract_importance(text)
            assert result == n, f"Expected {n}, got {result!r}"

    def test_returns_none_for_gibberish(self):
        """Gibberish text with no Rating: N/5 must return None."""
        assert extract_importance("this is just some random text") is None

    def test_returns_none_for_empty_string(self):
        """Empty string must return None."""
        assert extract_importance("") is None

    def test_returns_none_for_missing_rating(self):
        """Doc with ## Purpose but no Rating line must return None."""
        text = "## Purpose\n\nThis does stuff.\n## Symbols\n\n- foo"
        assert extract_importance(text) is None

    def test_case_insensitive_rating(self):
        """'rating: 3/5' (lowercase) must also parse correctly."""
        result = extract_importance("rating: 3/5 — lower case.")
        assert result == 3, f"Expected 3, got {result!r}"

    def test_rating_in_full_fake_doc(self):
        """extract_importance on the full FAKE_DOC constant must return 3."""
        result = extract_importance(FAKE_DOC)
        assert result == 3, f"Expected 3, got {result!r}"

    def test_returns_none_for_out_of_range_rating(self):
        """
        'Rating: 6/5' should not match (regex anchors to [1-5]).
        Returns None because the pattern does not match.
        """
        result = extract_importance("Rating: 6/5 — out of range.")
        assert result is None, (
            f"Expected None for out-of-range rating 6/5, got {result!r}"
        )

    def test_returns_none_for_rating_zero(self):
        """'Rating: 0/5' is not valid (not in [1-5]). Must return None."""
        result = extract_importance("Rating: 0/5 — zero.")
        assert result is None, (
            f"Expected None for rating 0/5, got {result!r}"
        )

    def test_whitespace_variants_parse(self):
        """'Rating:  3 / 5' with extra spaces around slash must still parse."""
        # The regex uses \s* between components
        result = extract_importance("Rating: 3 / 5 — spaced.")
        assert result == 3, f"Expected 3, got {result!r}"

    def test_embedded_in_multiline_doc(self):
        """Rating line buried in a multiline doc must still be found."""
        doc = (
            "## Purpose\n\nDoes things.\n\n"
            "## Symbols\n\n- x\n\n"
            "## Connections\n\n(none)\n\n"
            "## Gotchas\n\n(none)\n\n"
            "## Importance\n\nRating: 4/5 — important module.\n"
        )
        result = extract_importance(doc)
        assert result == 4, f"Expected 4, got {result!r}"


# ---------------------------------------------------------------------------
# Error path: LLM failure during update
# ---------------------------------------------------------------------------

class TestLLMFailureHandling:
    def test_llm_error_does_not_crash_update(self, tmp_path):
        """If llm.generate raises, corpus update must continue (not propagate crash)."""
        from corpus.llm import LLMError

        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)

        runner = CliRunner()
        old = os.getcwd()
        try:
            os.chdir(repo)
            with mock.patch(
                "corpus.llm.generate", side_effect=LLMError("simulated failure")
            ):
                with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "fake"}, clear=False):
                    result = runner.invoke(main, ["update"], catch_exceptions=False)
        finally:
            os.chdir(old)

        # Must exit 0 (individual file failures are warnings, not fatal)
        assert result.exit_code == 0, (
            f"Expected exit 0 on LLM failure, got {result.exit_code}:\n{result.output}"
        )

    def test_no_api_key_skips_doc_generation(self, tmp_path):
        """Without GEMINI_API_KEY or GROQ_API_KEY set, update must skip doc generation."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)

        runner = CliRunner()
        old = os.getcwd()
        try:
            os.chdir(repo)
            env = {k: v for k, v in os.environ.items()
                   if k not in ("GEMINI_API_KEY", "GROQ_API_KEY")}
            env["GEMINI_API_KEY"] = ""
            env["GROQ_API_KEY"] = ""
            with mock.patch.dict(os.environ, env, clear=True):
                result = runner.invoke(main, ["update"], catch_exceptions=False)
        finally:
            os.chdir(old)

        assert result.exit_code == 0, result.output
        # Docs dir must have no .py.md files
        docs_dir = repo / ".corpus" / "docs"
        py_md_files = list(docs_dir.rglob("*.py.md")) if docs_dir.exists() else []
        assert py_md_files == [], (
            f"Expected no doc files without API key, found: {py_md_files}"
        )

    def test_no_api_key_prints_warning(self, tmp_path):
        """Without API keys, update must print a warning about doc generation being skipped."""
        repo = _make_flat_repo(tmp_path)
        _init_corpus(repo)

        runner = CliRunner()
        old = os.getcwd()
        try:
            os.chdir(repo)
            env = {k: v for k, v in os.environ.items()
                   if k not in ("GEMINI_API_KEY", "GROQ_API_KEY")}
            env["GEMINI_API_KEY"] = ""
            env["GROQ_API_KEY"] = ""
            with mock.patch.dict(os.environ, env, clear=True):
                result = runner.invoke(main, ["update"], catch_exceptions=False)
        finally:
            os.chdir(old)

        output_lower = result.output.lower()
        assert "warning" in output_lower or "skipping" in output_lower, (
            f"Expected warning about no API key:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# docs.py unit tests — _truncate_source and generate_file_doc
# ---------------------------------------------------------------------------

class TestDocsPyTruncation:
    def test_truncate_source_no_truncation_needed(self):
        """Short source should pass through without truncation."""
        from corpus.docs import _truncate_source
        source = "def foo(): pass\n"
        result = _truncate_source(source, "", max_tokens=8192)
        assert result == source

    def test_truncate_source_truncates_long_source(self):
        """Source exceeding budget must be truncated and appended with '[truncated]'."""
        from corpus.docs import _truncate_source
        source = "x" * 100_000
        result = _truncate_source(source, "", max_tokens=100)
        assert "[truncated]" in result
        assert len(result) < len(source)

    def test_truncate_source_zero_budget_returns_placeholder(self):
        """If overhead alone exceeds budget, return the placeholder string."""
        from corpus.docs import _truncate_source
        # overhead > budget forces source_budget_chars <= 0
        overhead = "x" * 10_000
        result = _truncate_source("some source", overhead, max_tokens=1)
        assert result == "... [truncated]"


class TestGenerateFileDoc:
    def test_generate_file_doc_writes_doc_file(self, tmp_path):
        """generate_file_doc must write a .md file under corpus_dir/docs/."""
        _make_git_repo(tmp_path)
        src = tmp_path / "mod.py"
        src.write_text("def run(): pass\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        (corpus_dir / "docs").mkdir()

        node = {
            "id": "n_aabbcc",
            "path": "mod.py",
            "type": "file",
            "lang": "python",
            "symbols": ["run"],
            "importance": None,
            "doc": None,
            "stale": False,
        }
        graph = {"nodes": [node], "edges": []}
        config = {"limits": {"max_tokens_per_call": 8192}}

        from corpus.docs import generate_file_doc

        with mock.patch("corpus.llm.generate", return_value=FAKE_DOC):
            doc_text, importance = generate_file_doc(
                node, graph, tmp_path, corpus_dir, config
            )

        doc_path = corpus_dir / "docs" / "mod.py.md"
        assert doc_path.exists(), f"Expected {doc_path} to be written"
        assert doc_text == FAKE_DOC
        assert importance == 3

    def test_generate_file_doc_sets_node_doc_field(self, tmp_path):
        """generate_file_doc must set node['doc'] to the corpus-relative doc path."""
        _make_git_repo(tmp_path)
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        (corpus_dir / "docs").mkdir()

        node = {
            "id": "n_112233",
            "path": "app.py",
            "type": "file",
            "lang": "python",
            "symbols": [],
            "importance": None,
            "doc": None,
            "stale": False,
        }
        graph = {"nodes": [node], "edges": []}
        config = {"limits": {"max_tokens_per_call": 8192}}

        from corpus.docs import generate_file_doc

        with mock.patch("corpus.llm.generate", return_value=FAKE_DOC):
            generate_file_doc(node, graph, tmp_path, corpus_dir, config)

        assert node["doc"] is not None, "node['doc'] must be set after generate_file_doc"
        assert "app.py" in node["doc"]

    def test_generate_file_doc_unreadable_file(self, tmp_path):
        """generate_file_doc must not crash when source file is unreadable."""
        _make_git_repo(tmp_path)

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        (corpus_dir / "docs").mkdir()

        node = {
            "id": "n_xxyyzz",
            "path": "ghost.py",  # does not exist
            "type": "file",
            "lang": "python",
            "symbols": [],
            "importance": None,
            "doc": None,
            "stale": False,
        }
        graph = {"nodes": [node], "edges": []}
        config = {"limits": {"max_tokens_per_call": 8192}}

        from corpus.docs import generate_file_doc

        with mock.patch("corpus.llm.generate", return_value=FAKE_DOC):
            doc_text, importance = generate_file_doc(
                node, graph, tmp_path, corpus_dir, config
            )
        # Must not raise; doc is still written
        assert doc_text == FAKE_DOC


# ---------------------------------------------------------------------------
# docs.py unit tests — generate_dir_rollup
# ---------------------------------------------------------------------------

class TestGenerateDirRollup:
    def _make_docs_with_file(self, corpus_dir: Path, rel_dir: str, filename: str) -> None:
        """Write a fake doc file at corpus_dir/docs/rel_dir/filename.md."""
        doc_dir = corpus_dir / "docs" / rel_dir if rel_dir != "." else corpus_dir / "docs"
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / (filename + ".md")).write_text(FAKE_DOC, encoding="utf-8")

    def test_rollup_creates_dir_md(self, tmp_path):
        """generate_dir_rollup must create a _dir.md file."""
        from corpus.docs import generate_dir_rollup

        corpus_dir = tmp_path / ".corpus"
        (corpus_dir / "docs" / "mymod").mkdir(parents=True)
        self._make_docs_with_file(corpus_dir, "mymod", "utils.py")

        generate_dir_rollup("mymod", corpus_dir, tmp_path)
        assert (corpus_dir / "docs" / "mymod" / "_dir.md").exists()

    def test_rollup_contains_required_sections(self, tmp_path):
        """Generated _dir.md must contain both ## Contents and ## Summary."""
        from corpus.docs import generate_dir_rollup

        corpus_dir = tmp_path / ".corpus"
        (corpus_dir / "docs" / "pkg").mkdir(parents=True)
        self._make_docs_with_file(corpus_dir, "pkg", "core.py")

        generate_dir_rollup("pkg", corpus_dir, tmp_path)
        text = (corpus_dir / "docs" / "pkg" / "_dir.md").read_text(encoding="utf-8")
        assert "## Contents" in text
        assert "## Summary" in text

    def test_rollup_lists_child_files(self, tmp_path):
        """Contents section of _dir.md must list child doc files."""
        from corpus.docs import generate_dir_rollup

        corpus_dir = tmp_path / ".corpus"
        (corpus_dir / "docs" / "lib").mkdir(parents=True)
        self._make_docs_with_file(corpus_dir, "lib", "parser.py")
        self._make_docs_with_file(corpus_dir, "lib", "lexer.py")

        generate_dir_rollup("lib", corpus_dir, tmp_path)
        text = (corpus_dir / "docs" / "lib" / "_dir.md").read_text(encoding="utf-8")
        assert "parser.py" in text
        assert "lexer.py" in text

    def test_rollup_summary_not_empty(self, tmp_path):
        """The ## Summary section of _dir.md must contain non-blank content."""
        from corpus.docs import generate_dir_rollup

        corpus_dir = tmp_path / ".corpus"
        (corpus_dir / "docs" / "svc").mkdir(parents=True)
        self._make_docs_with_file(corpus_dir, "svc", "handler.py")

        generate_dir_rollup("svc", corpus_dir, tmp_path)
        text = (corpus_dir / "docs" / "svc" / "_dir.md").read_text(encoding="utf-8")

        lines = text.splitlines()
        in_summary = False
        summary_content = []
        for line in lines:
            if line.strip() == "## Summary":
                in_summary = True
                continue
            if in_summary:
                if line.strip().startswith("## "):
                    break
                if line.strip():
                    summary_content.append(line.strip())

        assert summary_content, (
            f"## Summary section is empty in _dir.md:\n{text}"
        )
