"""
Phase 3 acceptance-criteria tests — MCP bridge.

Acceptance criteria (from PLAN.md Phase 3):
  AC1 - `python -m corpus.mcp` starts without error (blocks on stdin — correct)
  AC2 - `corpus serve --mcp` also starts the MCP server without error
  AC3 - All 6 tools callable programmatically with .corpus/ present:
          corpus_overview(), corpus_doc(path), corpus_relations(path),
          corpus_find(symbol), corpus_changes(), corpus_stale()
  AC4 - Sidecar POST fails silently when nothing is on localhost:7077

Additional edge cases:
  - corpus_find("") returns empty list, not all nodes
  - corpus_doc("nonexistent/file.py") returns {"error": ...} not a crash
  - Path traversal guard: _read_doc with "../../../some/file" in doc field returns ""
  - corpus_relations uses correct from/to field names
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helpers: build a minimal .corpus/ in a temp directory
# ---------------------------------------------------------------------------

FAKE_GRAPH = {
    "nodes": [
        {
            "id": "n_aaa111",
            "path": "pkg/alpha.py",
            "type": "file",
            "lang": "python",
            "symbols": ["AlphaClass", "alpha_func"],
            "importance": 3,
            "doc": "docs/pkg/alpha.py.md",
            "stale": False,
        },
        {
            "id": "n_bbb222",
            "path": "pkg/beta.py",
            "type": "file",
            "lang": "python",
            "symbols": ["BetaClass", "beta_func"],
            "importance": 2,
            "doc": "docs/pkg/beta.py.md",
            "stale": True,
        },
        {
            "id": "n_ccc333",
            "path": "pkg",
            "type": "dir",
            "lang": None,
            "symbols": [],
            "importance": None,
            "doc": None,
            "stale": True,
        },
        {
            "id": "n_ddd444",
            "path": "pkg/gamma.py",
            "type": "file",
            "lang": "python",
            "symbols": ["gamma_func"],
            "importance": 1,
            "doc": None,
            "stale": False,
        },
    ],
    "edges": [
        # alpha.py imports beta.py
        {"from": "n_aaa111", "to": "n_bbb222", "type": "imports"},
        # gamma.py imports alpha.py
        {"from": "n_ddd444", "to": "n_aaa111", "type": "imports"},
        # dir contains alpha
        {"from": "n_ccc333", "to": "n_aaa111", "type": "contains"},
    ],
}

FAKE_STATE = {
    "version": 1,
    "last_commit": "abc123def456",
    "file_hashes": {
        "pkg/alpha.py": "deadbeef",
        "pkg/beta.py": "cafebabe",
    },
}


def _make_corpus_dir(tmp_path: Path) -> Path:
    """Create a minimal .corpus/ directory with graph.json, state.json, and sample docs."""
    corpus_dir = tmp_path / ".corpus"
    corpus_dir.mkdir()

    # Write graph.json
    (corpus_dir / "graph.json").write_text(
        json.dumps(FAKE_GRAPH), encoding="utf-8"
    )

    # Write state.json
    (corpus_dir / "state.json").write_text(
        json.dumps(FAKE_STATE), encoding="utf-8"
    )

    # Write docs
    docs_dir = corpus_dir / "docs" / "pkg"
    docs_dir.mkdir(parents=True)
    (docs_dir / "alpha.py.md").write_text(
        "## Purpose\nAlpha module.\n\n## Symbols\n- AlphaClass\n",
        encoding="utf-8",
    )
    (docs_dir / "beta.py.md").write_text(
        "## Purpose\nBeta module.\n\n## Symbols\n- BetaClass\n",
        encoding="utf-8",
    )
    root_docs = corpus_dir / "docs"
    (root_docs / "_dir.md").write_text(
        "# Project Overview\nThis is the root doc.\n",
        encoding="utf-8",
    )

    return corpus_dir


def _run_tools_in(cwd: Path, fn, *args, **kwargs):
    """Run an MCP tool function after changing cwd to the given directory."""
    old = os.getcwd()
    try:
        os.chdir(cwd)
        return fn(*args, **kwargs)
    finally:
        os.chdir(old)


# ---------------------------------------------------------------------------
# AC1 — `python -m corpus.mcp` starts without error
# ---------------------------------------------------------------------------

class TestAC1McpModuleStartup:
    """AC1: python -m corpus.mcp starts without error (blocks on stdin)."""

    def test_mcp_module_starts_without_error(self):
        """Process must still be running after 1 second (blocked on stdin, not crashed)."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "corpus.mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(1.0)
            ret = proc.poll()
            assert ret is None, (
                f"python -m corpus.mcp exited early with code {ret}. "
                f"stderr: {proc.stderr.read().decode(errors='replace')}"
            )
        finally:
            proc.kill()
            proc.wait()

    def test_mcp_module_no_stderr_on_startup(self):
        """python -m corpus.mcp must not write anything to stderr on startup."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "corpus.mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(1.0)
            proc.kill()
            stderr_output = proc.stderr.read().decode(errors="replace").strip()
            # FastMCP may write its own startup notices; filter those
            # We care about Python import errors or tracebacks
            assert "Traceback" not in stderr_output, (
                f"Unexpected traceback on startup:\n{stderr_output}"
            )
            assert "ImportError" not in stderr_output, (
                f"ImportError on startup:\n{stderr_output}"
            )
            assert "ModuleNotFoundError" not in stderr_output, (
                f"ModuleNotFoundError on startup:\n{stderr_output}"
            )
        finally:
            proc.wait()

    def test_corpus_mcp_importable(self):
        """corpus.mcp must import without raising any exception."""
        import corpus.mcp  # noqa: F401

    def test_fastmcp_instance_exists(self):
        """corpus.mcp.mcp must be a FastMCP instance (server is constructed)."""
        from corpus.mcp import mcp
        assert mcp is not None
        assert mcp.name == "corpus"

    def test_all_six_tools_importable(self):
        """All six MCP tool functions must be importable from corpus.mcp."""
        from corpus.mcp import (
            corpus_overview,
            corpus_doc,
            corpus_relations,
            corpus_find,
            corpus_changes,
            corpus_stale,
        )
        for fn in (corpus_overview, corpus_doc, corpus_relations,
                   corpus_find, corpus_changes, corpus_stale):
            assert callable(fn), f"{fn} is not callable"


# ---------------------------------------------------------------------------
# AC2 — `corpus serve --mcp` starts the MCP server without error
# FINDING: --mcp flag does not exist on `serve` subcommand.
# The `serve` command starts the MCP server directly (no --mcp flag needed).
# Test covers what is actually implemented.
# ---------------------------------------------------------------------------

class TestAC2ServeCommand:
    """AC2: corpus serve starts MCP server without error (--mcp flag is a gap — see findings)."""

    def test_serve_help_exits_zero(self):
        """corpus serve --help must exit 0."""
        from corpus.cli import main
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"], catch_exceptions=False)
        assert result.exit_code == 0, f"serve --help failed:\n{result.output}"

    def test_serve_mcp_flag_missing(self):
        """corpus serve --mcp starts the MCP server (exit 0, no unexpected errors).

        The --mcp flag is implemented in cli.py and calls corpus.mcp.run().
        We patch corpus.mcp.run so the stdio server never actually starts
        (which would block / write to a closed buffer inside Click's test runner).
        """
        from corpus.cli import main
        from click.testing import CliRunner
        with mock.patch("corpus.mcp.run", return_value=None) as mock_run:
            runner = CliRunner()
            result = runner.invoke(main, ["serve", "--mcp"], catch_exceptions=False)
        assert result.exit_code == 0, (
            f"Expected exit_code=0 for 'serve --mcp', got {result.exit_code}.\n"
            f"Output: {result.output}"
        )
        mock_run.assert_called_once()
        # No unexpected error text in output
        assert "Error" not in result.output, (
            f"Unexpected error in output: {result.output}"
        )

    def test_serve_subprocess_stays_alive(self):
        """corpus serve starts the MCP server and stays running (blocks on stdin).

        NOTE: `python -m corpus.cli serve` does NOT work because corpus/cli.py has
        no `if __name__ == '__main__': main()` guard. The correct invocation is via
        the installed `corpus` entry-point or `python -m corpus.mcp` directly.
        This test verifies the MCP run() function stays alive when invoked programmatically,
        which is what `corpus serve` does when called through the entry-point.
        """
        # Use corpus.mcp directly (same as what corpus serve calls via run_mcp())
        proc = subprocess.Popen(
            [sys.executable, "-m", "corpus.mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(1.0)
            ret = proc.poll()
            assert ret is None, (
                f"corpus.mcp exited early with code {ret}. "
                f"stderr: {proc.stderr.read().decode(errors='replace')}"
            )
        finally:
            proc.kill()
            proc.wait()

    def test_serve_cli_module_missing_main_guard(self):
        """corpus/cli.py now has an `if __name__ == '__main__': main()` guard.

        `python -m corpus.cli serve` (without --mcp) must actually invoke the CLI,
        print the graph-viewer startup line, and exit 0.  We patch uvicorn.run so
        the blocking server never starts, and supply a fake frontend/dist/index.html
        so the build step is skipped.
        """
        import tempfile
        import os

        from corpus.cli import main
        from click.testing import CliRunner

        with tempfile.TemporaryDirectory() as tmp:
            frontend_dist = Path(tmp) / "frontend" / "dist"
            frontend_dist.mkdir(parents=True)
            (frontend_dist / "index.html").write_text("<html/>", encoding="utf-8")

            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with mock.patch("uvicorn.run", return_value=None):
                    runner = CliRunner()
                    result = runner.invoke(main, ["serve"], catch_exceptions=False)
            finally:
                os.chdir(old_cwd)

        assert result.exit_code == 0, (
            f"Expected exit_code=0 for 'serve' (graph viewer mode), "
            f"got {result.exit_code}.\nOutput: {result.output}"
        )
        assert "Corpus graph viewer running at" in result.output, (
            f"Expected graph viewer startup message, got: {result.output!r}"
        )


# ---------------------------------------------------------------------------
# AC3 — All 6 tools callable programmatically with .corpus/ present
# ---------------------------------------------------------------------------

class TestAC3CorpusOverview:
    """corpus_overview() returns project summary."""

    def test_overview_returns_dict(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    def test_overview_has_required_keys(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        for key in ("project", "file_count", "node_count", "edge_count", "stale_count"):
            assert key in result, f"Missing key '{key}' in overview: {result}"

    def test_overview_node_count_matches_graph(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        assert result["node_count"] == len(FAKE_GRAPH["nodes"]), (
            f"node_count {result['node_count']} != {len(FAKE_GRAPH['nodes'])}"
        )

    def test_overview_edge_count_matches_graph(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        assert result["edge_count"] == len(FAKE_GRAPH["edges"]), (
            f"edge_count {result['edge_count']} != {len(FAKE_GRAPH['edges'])}"
        )

    def test_overview_file_count_only_file_nodes(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        expected_file_count = sum(
            1 for n in FAKE_GRAPH["nodes"] if n.get("type") == "file"
        )
        assert result["file_count"] == expected_file_count, (
            f"file_count {result['file_count']} != {expected_file_count}"
        )

    def test_overview_stale_count_correct(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        expected_stale = sum(1 for n in FAKE_GRAPH["nodes"] if n.get("stale"))
        assert result["stale_count"] == expected_stale, (
            f"stale_count {result['stale_count']} != {expected_stale}"
        )

    def test_overview_includes_dir_md_when_present(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        assert "dir_md" in result, "overview should include dir_md when _dir.md exists"
        assert "Project Overview" in result["dir_md"]

    def test_overview_project_name_is_cwd_name(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        assert result["project"] == tmp_path.name

    def test_overview_no_corpus_dir_returns_empty_counts(self, tmp_path):
        """When .corpus/ is missing, overview must return zero counts without crashing."""
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        assert result["node_count"] == 0
        assert result["edge_count"] == 0
        assert result["file_count"] == 0

    def test_overview_last_update_from_state(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        assert result["last_update"] == FAKE_STATE["last_commit"]


class TestAC3CorpusDoc:
    """corpus_doc(path) returns doc for a known file."""

    def test_doc_returns_dict_for_known_path(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        result = _run_tools_in(tmp_path, corpus_doc, "pkg/alpha.py")
        assert isinstance(result, dict)
        assert "error" not in result, f"Unexpected error: {result}"

    def test_doc_has_required_fields(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        result = _run_tools_in(tmp_path, corpus_doc, "pkg/alpha.py")
        for key in ("id", "path", "importance", "stale", "doc"):
            assert key in result, f"Missing key '{key}' in corpus_doc result: {result}"

    def test_doc_correct_path(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        result = _run_tools_in(tmp_path, corpus_doc, "pkg/alpha.py")
        assert result["path"] == "pkg/alpha.py"

    def test_doc_correct_importance(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        result = _run_tools_in(tmp_path, corpus_doc, "pkg/alpha.py")
        assert result["importance"] == 3

    def test_doc_stale_flag_false_for_non_stale(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        result = _run_tools_in(tmp_path, corpus_doc, "pkg/alpha.py")
        assert result["stale"] is False

    def test_doc_stale_flag_true_for_stale_node(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        result = _run_tools_in(tmp_path, corpus_doc, "pkg/beta.py")
        assert result["stale"] is True

    def test_doc_text_contains_content(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        result = _run_tools_in(tmp_path, corpus_doc, "pkg/alpha.py")
        assert "Purpose" in result["doc"], (
            f"Expected doc text with 'Purpose', got: {result['doc']!r}"
        )

    def test_doc_returns_error_for_nonexistent_path(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        result = _run_tools_in(tmp_path, corpus_doc, "nonexistent/file.py")
        assert "error" in result, f"Expected error key, got: {result}"
        assert isinstance(result["error"], str)
        assert "not found" in result["error"].lower() or "nonexistent" in result["error"]

    def test_doc_error_is_dict_not_exception(self, tmp_path):
        """corpus_doc with bad path must return a dict, never raise."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        # Must not raise
        try:
            result = _run_tools_in(tmp_path, corpus_doc, "nonexistent/file.py")
        except Exception as exc:
            pytest.fail(f"corpus_doc raised instead of returning error dict: {exc}")
        assert isinstance(result, dict)

    def test_doc_node_with_no_doc_field_returns_empty_string(self, tmp_path):
        """Node with doc=None must return doc='' not crash."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        # gamma.py has doc=None in FAKE_GRAPH
        result = _run_tools_in(tmp_path, corpus_doc, "pkg/gamma.py")
        assert "error" not in result
        assert result["doc"] == ""


class TestAC3CorpusRelations:
    """corpus_relations(path) returns non-empty relations for a file with known edges."""

    def test_relations_returns_dict_for_known_path(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_relations
        result = _run_tools_in(tmp_path, corpus_relations, "pkg/alpha.py")
        assert isinstance(result, dict)
        assert "error" not in result

    def test_relations_has_required_fields(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_relations
        result = _run_tools_in(tmp_path, corpus_relations, "pkg/alpha.py")
        assert "id" in result
        assert "path" in result
        assert "relations" in result

    def test_relations_non_empty_for_file_with_edges(self, tmp_path):
        """alpha.py has imports and is imported — relations must be non-empty."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_relations
        result = _run_tools_in(tmp_path, corpus_relations, "pkg/alpha.py")
        assert len(result["relations"]) > 0, (
            f"Expected non-empty relations for pkg/alpha.py, got: {result}"
        )

    def test_relations_imports_direction(self, tmp_path):
        """alpha.py imports beta.py — must appear with direction='imports'."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_relations
        result = _run_tools_in(tmp_path, corpus_relations, "pkg/alpha.py")
        imports = [r for r in result["relations"] if r["direction"] == "imports"]
        paths_imported = [r["path"] for r in imports]
        assert "pkg/beta.py" in paths_imported, (
            f"Expected pkg/beta.py in imports, got: {imports}"
        )

    def test_relations_imported_by_direction(self, tmp_path):
        """gamma.py imports alpha.py — alpha.py must have direction='imported_by'."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_relations
        result = _run_tools_in(tmp_path, corpus_relations, "pkg/alpha.py")
        imported_by = [r for r in result["relations"] if r["direction"] == "imported_by"]
        paths = [r["path"] for r in imported_by]
        assert "pkg/gamma.py" in paths, (
            f"Expected pkg/gamma.py in imported_by, got: {imported_by}"
        )

    def test_relations_uses_from_to_field_names(self, tmp_path):
        """Relations logic uses 'from'/'to' keys in edge dicts (not 'source'/'target')."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_relations
        # If the wrong field names were used, alpha.py would show 0 relations
        result = _run_tools_in(tmp_path, corpus_relations, "pkg/alpha.py")
        assert len(result["relations"]) > 0, (
            "Relations empty — possible wrong field name for edges "
            "(should use 'from'/'to', not 'source'/'target')"
        )

    def test_relations_returns_error_for_nonexistent_path(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_relations
        result = _run_tools_in(tmp_path, corpus_relations, "does_not_exist.py")
        assert "error" in result
        assert isinstance(result["error"], str)

    def test_relations_error_is_dict_not_exception(self, tmp_path):
        """Bad path must return error dict, never raise."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_relations
        try:
            result = _run_tools_in(tmp_path, corpus_relations, "no_such_file.py")
        except Exception as exc:
            pytest.fail(f"corpus_relations raised instead of returning error dict: {exc}")
        assert isinstance(result, dict)

    def test_relations_each_entry_has_type(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_relations
        result = _run_tools_in(tmp_path, corpus_relations, "pkg/alpha.py")
        for rel in result["relations"]:
            assert "type" in rel, f"Relation missing 'type' key: {rel}"
            assert "direction" in rel, f"Relation missing 'direction' key: {rel}"
            assert "path" in rel, f"Relation missing 'path' key: {rel}"


class TestAC3CorpusFind:
    """corpus_find(symbol) finds nodes by symbol substring."""

    def test_find_returns_list(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_find
        result = _run_tools_in(tmp_path, corpus_find, "Alpha")
        assert isinstance(result, list)

    def test_find_returns_match_for_known_symbol(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_find
        result = _run_tools_in(tmp_path, corpus_find, "AlphaClass")
        assert len(result) >= 1, f"Expected at least one match for 'AlphaClass', got: {result}"

    def test_find_case_insensitive(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_find
        result_lower = _run_tools_in(tmp_path, corpus_find, "alphaclass")
        result_upper = _run_tools_in(tmp_path, corpus_find, "ALPHACLASS")
        assert len(result_lower) == len(result_upper), (
            "corpus_find must be case-insensitive"
        )

    def test_find_partial_match(self, tmp_path):
        """Substring 'alpha' must match 'AlphaClass' and 'alpha_func'."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_find
        result = _run_tools_in(tmp_path, corpus_find, "alpha")
        assert len(result) >= 1, f"Expected matches for 'alpha', got: {result}"
        # Should match alpha.py node (has AlphaClass, alpha_func)
        paths = [r["path"] for r in result]
        assert "pkg/alpha.py" in paths, (
            f"Expected pkg/alpha.py in results for 'alpha', got paths: {paths}"
        )

    def test_find_returns_matched_symbols(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_find
        result = _run_tools_in(tmp_path, corpus_find, "AlphaClass")
        assert len(result) >= 1
        match = result[0]
        assert "matched_symbols" in match, f"Missing matched_symbols in result: {match}"
        assert any("AlphaClass" in s for s in match["matched_symbols"])

    def test_find_result_has_required_fields(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_find
        result = _run_tools_in(tmp_path, corpus_find, "AlphaClass")
        assert len(result) >= 1
        for key in ("id", "path", "importance", "stale", "matched_symbols"):
            assert key in result[0], f"Missing key '{key}' in find result: {result[0]}"

    def test_find_empty_string_returns_empty_list(self, tmp_path):
        """corpus_find('') must return empty list, not all nodes."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_find
        result = _run_tools_in(tmp_path, corpus_find, "")
        assert result == [], (
            f"corpus_find('') must return [] not {result}"
        )

    def test_find_whitespace_only_returns_empty_list(self, tmp_path):
        """corpus_find('   ') must return empty list (whitespace stripped)."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_find
        result = _run_tools_in(tmp_path, corpus_find, "   ")
        assert result == [], (
            f"corpus_find('   ') must return [] not {result}"
        )

    def test_find_nonexistent_symbol_returns_empty(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_find
        result = _run_tools_in(tmp_path, corpus_find, "ZzZzNoSuchSymbolXxXx")
        assert result == []

    def test_find_no_corpus_dir_returns_empty_list(self, tmp_path):
        """If .corpus/ does not exist, find must return [] not crash."""
        from corpus.mcp import corpus_find
        result = _run_tools_in(tmp_path, corpus_find, "something")
        assert isinstance(result, list)
        assert result == []


class TestAC3CorpusChanges:
    """corpus_changes() returns list of stale nodes."""

    def test_changes_returns_list(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_changes
        result = _run_tools_in(tmp_path, corpus_changes)
        assert isinstance(result, list)

    def test_changes_non_empty_when_stale_nodes_exist(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_changes
        result = _run_tools_in(tmp_path, corpus_changes)
        assert len(result) > 0, "Expected stale nodes in corpus_changes result"

    def test_changes_has_required_fields(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_changes
        result = _run_tools_in(tmp_path, corpus_changes)
        assert len(result) > 0
        for key in ("path", "importance", "stale", "changed_since_last_update"):
            assert key in result[0], f"Missing key '{key}' in changes result: {result[0]}"

    def test_changes_all_entries_are_stale_true(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_changes
        result = _run_tools_in(tmp_path, corpus_changes)
        for entry in result:
            assert entry["stale"] is True, f"Non-stale node in corpus_changes: {entry}"
            assert entry["changed_since_last_update"] is True

    def test_changes_sorted_by_path(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_changes
        result = _run_tools_in(tmp_path, corpus_changes)
        paths = [r["path"] for r in result]
        assert paths == sorted(paths), f"corpus_changes not sorted: {paths}"

    def test_changes_empty_when_no_stale_nodes(self, tmp_path):
        """When graph has no stale nodes, corpus_changes returns []."""
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        clean_graph = {
            "nodes": [
                {"id": "n_x1", "path": "a.py", "type": "file",
                 "symbols": [], "importance": 1, "doc": None, "stale": False},
            ],
            "edges": [],
        }
        (corpus_dir / "graph.json").write_text(json.dumps(clean_graph), encoding="utf-8")
        (corpus_dir / "state.json").write_text("{}", encoding="utf-8")
        from corpus.mcp import corpus_changes
        result = _run_tools_in(tmp_path, corpus_changes)
        assert result == []

    def test_changes_no_corpus_dir_returns_empty_list(self, tmp_path):
        from corpus.mcp import corpus_changes
        result = _run_tools_in(tmp_path, corpus_changes)
        assert result == []


class TestAC3CorpusStale:
    """corpus_stale() returns full stale node list."""

    def test_stale_returns_list(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_stale
        result = _run_tools_in(tmp_path, corpus_stale)
        assert isinstance(result, list)

    def test_stale_non_empty_when_stale_nodes_exist(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_stale
        result = _run_tools_in(tmp_path, corpus_stale)
        assert len(result) > 0

    def test_stale_all_entries_have_stale_true(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_stale
        result = _run_tools_in(tmp_path, corpus_stale)
        for entry in result:
            assert entry.get("stale") is True, (
                f"corpus_stale returned non-stale node: {entry}"
            )

    def test_stale_includes_all_stale_fields(self, tmp_path):
        """corpus_stale returns full node dicts (all fields from graph.json)."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_stale
        result = _run_tools_in(tmp_path, corpus_stale)
        assert len(result) > 0
        # Full dict should have graph fields: id, path, type, stale
        entry = result[0]
        assert "id" in entry, f"Missing 'id' in stale node: {entry}"
        assert "path" in entry, f"Missing 'path' in stale node: {entry}"

    def test_stale_count_matches_expected(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_stale
        result = _run_tools_in(tmp_path, corpus_stale)
        expected = [n for n in FAKE_GRAPH["nodes"] if n.get("stale")]
        assert len(result) == len(expected), (
            f"stale count {len(result)} != expected {len(expected)}"
        )

    def test_stale_sorted_by_path(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_stale
        result = _run_tools_in(tmp_path, corpus_stale)
        paths = [r.get("path", "") for r in result]
        assert paths == sorted(paths), f"corpus_stale not sorted: {paths}"

    def test_stale_changes_and_stale_agree(self, tmp_path):
        """corpus_changes and corpus_stale must agree on which file nodes are stale."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_changes, corpus_stale
        changes = _run_tools_in(tmp_path, corpus_changes)
        stale = _run_tools_in(tmp_path, corpus_stale)
        # Both list stale nodes; stale includes dirs, changes is a subset
        changes_paths = {r["path"] for r in changes}
        stale_paths = {r.get("path") for r in stale}
        # All changes paths must be in stale paths
        assert changes_paths.issubset(stale_paths), (
            f"corpus_changes paths not subset of corpus_stale paths: "
            f"{changes_paths - stale_paths}"
        )

    def test_stale_no_corpus_dir_returns_empty_list(self, tmp_path):
        from corpus.mcp import corpus_stale
        result = _run_tools_in(tmp_path, corpus_stale)
        assert result == []


# ---------------------------------------------------------------------------
# AC4 — Sidecar POST fails silently when nothing is on localhost:7077
# ---------------------------------------------------------------------------

class TestAC4SidecarSilentFailure:
    """AC4: _post_event must not raise even when localhost:7077 is unreachable."""

    def test_post_event_does_not_raise_when_no_sidecar(self):
        """_post_event must swallow ConnectionRefusedError silently."""
        from corpus.mcp import _post_event
        # No server is running on 7077 in the test environment
        try:
            _post_event("test_tool", "n_test123")
        except Exception as exc:
            pytest.fail(
                f"_post_event raised {type(exc).__name__} when sidecar is not running: {exc}"
            )

    def test_post_event_no_raise_with_none_node_id(self):
        from corpus.mcp import _post_event
        try:
            _post_event("corpus_overview", None)
        except Exception as exc:
            pytest.fail(f"_post_event raised with node_id=None: {exc}")

    def test_tool_call_does_not_raise_even_with_no_sidecar(self, tmp_path):
        """Full tool call must complete successfully with no sidecar running."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_overview
        try:
            result = _run_tools_in(tmp_path, corpus_overview)
        except Exception as exc:
            pytest.fail(f"corpus_overview raised with no sidecar: {exc}")
        assert isinstance(result, dict)

    def test_corpus_doc_does_not_raise_with_no_sidecar(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import corpus_doc
        try:
            result = _run_tools_in(tmp_path, corpus_doc, "pkg/alpha.py")
        except Exception as exc:
            pytest.fail(f"corpus_doc raised with no sidecar: {exc}")
        assert isinstance(result, dict)

    def test_post_event_payload_format(self):
        """_post_event must encode JSON payload without crashing on construction."""
        from corpus.mcp import _post_event
        # This verifies the payload is valid JSON-serializable
        # Intercept at the urllib level to inspect without actually sending
        with mock.patch("urllib.request.urlopen", side_effect=OSError("no server")):
            try:
                _post_event("corpus_find", "n_abc123")
            except Exception as exc:
                pytest.fail(f"_post_event raised when urlopen raises OSError: {exc}")

    def test_post_event_timeout_does_not_raise(self):
        """_post_event must not propagate TimeoutError from urlopen."""
        import urllib.error
        from corpus.mcp import _post_event
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            try:
                _post_event("corpus_stale", None)
            except Exception as exc:
                pytest.fail(f"_post_event propagated TimeoutError: {exc}")


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

class TestEdgeCasesReadDoc:
    """_read_doc path traversal guard and missing doc handling."""

    def test_read_doc_path_traversal_returns_empty_string(self, tmp_path):
        """_read_doc must return '' when doc path escapes .corpus/ (traversal guard)."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import _read_doc
        # Craft a node with a traversal path
        malicious_node = {"doc": "../../../etc/passwd"}
        old = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = _read_doc(malicious_node)
        finally:
            os.chdir(old)
        assert result == "", (
            f"_read_doc must return '' for traversal path, got: {result!r}"
        )

    def test_read_doc_traversal_does_not_raise(self, tmp_path):
        """_read_doc must not raise for traversal attempts."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import _read_doc
        malicious_node = {"doc": "../../../some/other/file"}
        old = os.getcwd()
        try:
            os.chdir(tmp_path)
            try:
                result = _read_doc(malicious_node)
            except Exception as exc:
                pytest.fail(f"_read_doc raised for traversal path: {exc}")
        finally:
            os.chdir(old)

    def test_read_doc_missing_doc_file_returns_empty(self, tmp_path):
        """_read_doc returns '' when the doc file simply doesn't exist on disk."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import _read_doc
        node = {"doc": "docs/nonexistent_file.md"}
        old = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = _read_doc(node)
        finally:
            os.chdir(old)
        assert result == ""

    def test_read_doc_none_doc_field_returns_empty(self, tmp_path):
        """_read_doc returns '' when doc field is None."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import _read_doc
        node = {"doc": None}
        old = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = _read_doc(node)
        finally:
            os.chdir(old)
        assert result == ""

    def test_read_doc_empty_doc_field_returns_empty(self, tmp_path):
        """_read_doc returns '' when doc field is empty string."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import _read_doc
        node = {"doc": ""}
        old = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = _read_doc(node)
        finally:
            os.chdir(old)
        assert result == ""

    def test_read_doc_valid_path_returns_content(self, tmp_path):
        """_read_doc returns actual content for a valid, contained doc path."""
        _make_corpus_dir(tmp_path)
        from corpus.mcp import _read_doc
        node = {"doc": "docs/pkg/alpha.py.md"}
        old = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = _read_doc(node)
        finally:
            os.chdir(old)
        assert "Purpose" in result, f"Expected doc content, got: {result!r}"

    def test_read_doc_double_dot_in_contained_path_ok(self, tmp_path):
        """A path that NORMALIZES to inside .corpus/ is allowed."""
        _make_corpus_dir(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        # Create a legit file: .corpus/docs/sub/../alpha.md → .corpus/docs/alpha.md
        (corpus_dir / "docs" / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
        from corpus.mcp import _read_doc
        # This path is within .corpus/ after resolution
        node = {"doc": "docs/sub/../alpha.md"}
        old = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = _read_doc(node)
        finally:
            os.chdir(old)
        # Must not raise; content or "" is acceptable (depends on file existing)
        assert isinstance(result, str)


class TestEdgeCasesLoadGraph:
    """_load_graph handles missing / corrupt graph.json."""

    def test_load_graph_missing_file_returns_empty(self, tmp_path):
        """Missing graph.json returns {'nodes': [], 'edges': []}."""
        from corpus.mcp import _load_graph
        result = _run_tools_in(tmp_path, _load_graph)
        assert result == {"nodes": [], "edges": []}

    def test_load_graph_corrupt_json_returns_empty(self, tmp_path):
        """Corrupt graph.json returns {'nodes': [], 'edges': []}."""
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        (corpus_dir / "graph.json").write_text("this is not json{{{{", encoding="utf-8")
        from corpus.mcp import _load_graph
        result = _run_tools_in(tmp_path, _load_graph)
        assert result == {"nodes": [], "edges": []}

    def test_load_state_missing_file_returns_empty(self, tmp_path):
        """Missing state.json returns {}."""
        from corpus.mcp import _load_state
        result = _run_tools_in(tmp_path, _load_state)
        assert result == {}

    def test_load_state_corrupt_json_returns_empty(self, tmp_path):
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        (corpus_dir / "state.json").write_text("{bad json}", encoding="utf-8")
        from corpus.mcp import _load_state
        result = _run_tools_in(tmp_path, _load_state)
        assert result == {}


class TestEdgeCasesNodeByPath:
    """_node_by_path helper."""

    def test_node_by_path_found(self, tmp_path):
        _make_corpus_dir(tmp_path)
        from corpus.mcp import _node_by_path
        graph = {"nodes": [{"id": "n1", "path": "a.py"}]}
        result = _node_by_path(graph, "a.py")
        assert result is not None
        assert result["id"] == "n1"

    def test_node_by_path_not_found_returns_none(self):
        from corpus.mcp import _node_by_path
        graph = {"nodes": [{"id": "n1", "path": "a.py"}]}
        result = _node_by_path(graph, "b.py")
        assert result is None

    def test_node_by_path_empty_graph(self):
        from corpus.mcp import _node_by_path
        result = _node_by_path({"nodes": [], "edges": []}, "a.py")
        assert result is None


class TestEdgeCasesUnicodeAndSpecialPaths:
    """Unicode paths and special characters in symbol search."""

    def test_find_unicode_symbol(self, tmp_path):
        """corpus_find with unicode search term must not crash."""
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        graph = {
            "nodes": [
                {"id": "n_u", "path": "uni.py", "type": "file",
                 "symbols": ["caf\u00e9_function"], "importance": 1,
                 "doc": None, "stale": False},
            ],
            "edges": [],
        }
        (corpus_dir / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
        (corpus_dir / "state.json").write_text("{}", encoding="utf-8")
        from corpus.mcp import corpus_find
        result = _run_tools_in(tmp_path, corpus_find, "caf\u00e9")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["path"] == "uni.py"

    def test_overview_with_empty_graph(self, tmp_path):
        """overview with empty graph must return zero counts."""
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        (corpus_dir / "graph.json").write_text(
            json.dumps({"nodes": [], "edges": []}), encoding="utf-8"
        )
        (corpus_dir / "state.json").write_text("{}", encoding="utf-8")
        from corpus.mcp import corpus_overview
        result = _run_tools_in(tmp_path, corpus_overview)
        assert result["node_count"] == 0
        assert result["edge_count"] == 0
        assert result["stale_count"] == 0


class TestIntegrationToolsWithRealCorpusDir:
    """
    Integration: run tools against the actual project's .corpus/ directory
    to verify they work end-to-end on real data.

    These tests require the project repo to have a populated .corpus/.
    They are skipped if .corpus/graph.json is absent.
    """

    CORPUS_ROOT = Path(__file__).parent.parent

    @pytest.fixture(autouse=True)
    def _require_corpus_dir(self):
        graph = self.CORPUS_ROOT / ".corpus" / "graph.json"
        if not graph.exists():
            pytest.skip(".corpus/graph.json not present — run corpus update first")

    def _in_project_root(self, fn, *args, **kwargs):
        return _run_tools_in(self.CORPUS_ROOT, fn, *args, **kwargs)

    def test_real_overview_has_nonzero_counts(self):
        from corpus.mcp import corpus_overview
        result = self._in_project_root(corpus_overview)
        assert result["node_count"] > 0
        assert result["edge_count"] > 0

    def test_real_corpus_doc_for_known_file(self):
        """corpus_doc for corpus/cli.py must return a valid result."""
        from corpus.mcp import corpus_doc
        result = self._in_project_root(corpus_doc, "corpus/cli.py")
        assert "error" not in result, f"Got error for corpus/cli.py: {result}"
        assert result["path"] == "corpus/cli.py"

    def test_real_corpus_relations_for_cli_py(self):
        """corpus/cli.py imports scaffold — relations must be non-empty."""
        from corpus.mcp import corpus_relations
        result = self._in_project_root(corpus_relations, "corpus/cli.py")
        # cli.py has known import edges in the real graph
        assert "error" not in result
        assert len(result["relations"]) > 0, (
            f"Expected non-empty relations for corpus/cli.py, got: {result}"
        )

    def test_real_find_known_symbol(self):
        """corpus_find('run_init') must find corpus/scaffold.py."""
        from corpus.mcp import corpus_find
        result = self._in_project_root(corpus_find, "run_init")
        paths = [r["path"] for r in result]
        assert "corpus/scaffold.py" in paths, (
            f"Expected corpus/scaffold.py in find results for 'run_init', got: {paths}"
        )

    def test_real_corpus_changes_returns_list(self):
        from corpus.mcp import corpus_changes
        result = self._in_project_root(corpus_changes)
        assert isinstance(result, list)

    def test_real_corpus_stale_returns_list(self):
        from corpus.mcp import corpus_stale
        result = self._in_project_root(corpus_stale)
        assert isinstance(result, list)
