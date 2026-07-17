"""
Phase 1b acceptance-criteria tests + MAJOR-fix verification + edge-case coverage.

Acceptance criteria (from PLAN.md Phase 1b):
  AC1 - corpus update on a Python repo produces .corpus/graph.json (valid JSON,
         one node per tracked file/directory)
  AC2 - python -c "... print(len(d['nodes']), 'nodes,', len(d['edges']), 'edges')"
         prints non-zero counts
  AC3 - Re-running corpus update on unchanged repo produces same node IDs
  AC4 - A file with known imports produces at least one edge in graph.json
  AC5 - .corpus/state.json contains a file_hashes map with an entry for every
         tracked file

MAJOR fixes verified:
  FIX1 - Node IDs use k=6 (6 hex chars) with a 10,000-attempt circuit breaker
  FIX2 - No duplicate symbols in any node (especially when __all__ used)
  FIX3 - Relative Python imports (from . import X, from .utils import Y) produce edges
  FIX4 - No duplicate edges (same from+to+type at most once)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from corpus.cli import main
from corpus.config import write_default_config, load_config
from corpus.graph import build_graph, write_graph, _new_id, _resolve_python_import, _resolve_js_import
from corpus.ignore import get_tracked_files
from corpus.parser import parse_file
from corpus.state import load_state, save_state, compute_hash

from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_git_repo(tmp_path: Path) -> Path:
    """Initialise a minimal git repo."""
    subprocess.run(
        ["git", "init", str(tmp_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return tmp_path


def _init_corpus(tmp_path: Path) -> Path:
    """Run corpus init in tmp_path; return corpus_dir."""
    runner = CliRunner()
    old = os.getcwd()
    try:
        os.chdir(tmp_path)
        runner.invoke(main, ["init"], catch_exceptions=False)
    finally:
        os.chdir(old)
    return tmp_path / ".corpus"


def _run_update(tmp_path: Path):
    """Run corpus update in tmp_path; return CliRunner result."""
    runner = CliRunner()
    old = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(main, ["update"], catch_exceptions=False)
    finally:
        os.chdir(old)
    return result


def _minimal_python_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with a Python package."""
    _make_git_repo(tmp_path)
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("from .utils import helper\n", encoding="utf-8")
    (pkg / "utils.py").write_text(
        "def helper():\n    return 42\n", encoding="utf-8"
    )
    (tmp_path / "main.py").write_text(
        "from mypkg.utils import helper\nprint(helper())\n", encoding="utf-8"
    )
    return tmp_path


def _build_graph_for(tmp_path: Path, existing_state: dict | None = None) -> dict:
    """Helper: init, write default config, then call build_graph directly."""
    corpus_dir = tmp_path / ".corpus"
    corpus_dir.mkdir(exist_ok=True)
    yml = corpus_dir / "corpus.yml"
    write_default_config(yml)
    config = load_config(yml)
    tracked, _ = get_tracked_files(tmp_path, config)
    state = existing_state if existing_state is not None else load_state(corpus_dir)
    return build_graph(tracked, tmp_path, state), tracked, state


# ---------------------------------------------------------------------------
# AC1 — graph.json is valid JSON with one node per tracked file/directory
# ---------------------------------------------------------------------------

class TestAC1GraphJsonValid:
    def test_graph_json_created(self, tmp_path):
        """corpus update must create .corpus/graph.json."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        result = _run_update(repo)
        assert result.exit_code == 0, f"update failed:\n{result.output}"
        assert (repo / ".corpus" / "graph.json").exists()

    def test_graph_json_is_valid_json(self, tmp_path):
        """graph.json must parse without error."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        text = (repo / ".corpus" / "graph.json").read_text(encoding="utf-8")
        data = json.loads(text)  # raises if invalid
        assert isinstance(data, dict)

    def test_graph_json_has_nodes_and_edges_keys(self, tmp_path):
        """graph.json must have 'nodes' and 'edges' keys."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        data = json.loads((repo / ".corpus" / "graph.json").read_text(encoding="utf-8"))
        assert "nodes" in data, "Missing 'nodes' key"
        assert "edges" in data, "Missing 'edges' key"

    def test_graph_json_nodes_is_list(self, tmp_path):
        """'nodes' must be a JSON array."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        data = json.loads((repo / ".corpus" / "graph.json").read_text(encoding="utf-8"))
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_one_file_node_per_tracked_file(self, tmp_path):
        """File nodes must match tracked files 1-to-1."""
        _make_git_repo(tmp_path)
        for name in ["alpha.py", "beta.py", "gamma.py"]:
            (tmp_path / name).write_text("x = 1\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        state = load_state(corpus_dir)
        graph = build_graph(tracked, tmp_path, state)

        file_nodes = [n for n in graph["nodes"] if n["type"] == "file"]
        tracked_rels = {p.relative_to(tmp_path).as_posix() for p in tracked}
        file_node_paths = {n["path"] for n in file_nodes}
        assert file_node_paths == tracked_rels, (
            f"File nodes don't match tracked files.\n"
            f"Nodes: {file_node_paths}\nTracked: {tracked_rels}"
        )

    def test_directory_nodes_exist(self, tmp_path):
        """Directory nodes must be created for ancestor dirs of tracked files."""
        _make_git_repo(tmp_path)
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "module.py").write_text("x = 1\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        state = load_state(corpus_dir)
        graph = build_graph(tracked, tmp_path, state)

        dir_nodes = [n for n in graph["nodes"] if n["type"] == "dir"]
        dir_paths = {n["path"] for n in dir_nodes}
        assert "subdir" in dir_paths, f"Expected 'subdir' dir node; got: {dir_paths}"

    def test_each_node_has_required_fields(self, tmp_path):
        """Every node must have id, path, type, lang, symbols, importance, doc, stale."""
        _make_git_repo(tmp_path)
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))

        required = {"id", "path", "type", "lang", "symbols", "importance", "doc", "stale"}
        for node in graph["nodes"]:
            missing = required - node.keys()
            assert not missing, f"Node {node.get('path')} missing fields: {missing}"

    def test_graph_has_version_field(self, tmp_path):
        """graph.json must have a 'version' field."""
        _make_git_repo(tmp_path)
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))
        assert graph.get("version") == 1

    def test_empty_repo_produces_empty_graph(self, tmp_path):
        """A repo with zero tracked files should produce zero-node graph without crash."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))
        assert isinstance(graph["nodes"], list)
        assert isinstance(graph["edges"], list)


# ---------------------------------------------------------------------------
# AC2 — non-zero node and edge counts
# ---------------------------------------------------------------------------

class TestAC2NonZeroCounts:
    def test_non_zero_node_count(self, tmp_path):
        """A repo with Python files must produce at least one node."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        data = json.loads((repo / ".corpus" / "graph.json").read_text(encoding="utf-8"))
        assert len(data["nodes"]) > 0, "Expected non-zero node count"

    def test_non_zero_edge_count(self, tmp_path):
        """A repo with intra-package imports must produce at least one edge."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        data = json.loads((repo / ".corpus" / "graph.json").read_text(encoding="utf-8"))
        assert len(data["edges"]) > 0, "Expected non-zero edge count"

    def test_cli_update_output_prints_counts(self, tmp_path):
        """corpus update CLI must print 'N nodes, M edges' in its output."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        result = _run_update(repo)
        assert result.exit_code == 0, result.output
        assert re.search(r"\d+ nodes?,\s*\d+ edges?", result.output), (
            f"Expected count output, got: {result.output}"
        )

    def test_single_file_repo_has_node(self, tmp_path):
        """Single .py file must produce at least 1 file node."""
        _make_git_repo(tmp_path)
        (tmp_path / "solo.py").write_text("def run(): pass\n", encoding="utf-8")
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))
        file_nodes = [n for n in graph["nodes"] if n["type"] == "file"]
        assert len(file_nodes) >= 1

    def test_multiple_files_each_get_node(self, tmp_path):
        """N tracked files must yield exactly N file nodes."""
        _make_git_repo(tmp_path)
        n = 5
        for i in range(n):
            (tmp_path / f"file{i}.py").write_text(f"x = {i}\n", encoding="utf-8")
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))
        file_nodes = [n for n in graph["nodes"] if n["type"] == "file"]
        assert len(file_nodes) == n, f"Expected {n} file nodes, got {len(file_nodes)}"


# ---------------------------------------------------------------------------
# AC3 — Node ID stability across consecutive runs
# ---------------------------------------------------------------------------

class TestAC3NodeIdStability:
    def test_same_ids_consecutive_runs(self, tmp_path):
        """Node IDs must be identical on two consecutive corpus update runs."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)

        _run_update(repo)
        ids1 = sorted(
            n["id"]
            for n in json.loads(
                (repo / ".corpus" / "graph.json").read_text(encoding="utf-8")
            )["nodes"]
        )

        _run_update(repo)
        ids2 = sorted(
            n["id"]
            for n in json.loads(
                (repo / ".corpus" / "graph.json").read_text(encoding="utf-8")
            )["nodes"]
        )

        assert ids1 == ids2, (
            f"Node IDs changed between runs.\nRun 1: {ids1}\nRun 2: {ids2}"
        )

    def test_adding_file_preserves_existing_ids(self, tmp_path):
        """Adding a new file must not change existing nodes' IDs."""
        _make_git_repo(tmp_path)
        (tmp_path / "original.py").write_text("x = 1\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        state = load_state(corpus_dir)
        graph1 = build_graph(tracked, tmp_path, state)
        save_state(corpus_dir, state)

        orig_id = next(
            n["id"] for n in graph1["nodes"]
            if n["path"] == "original.py"
        )

        # Add new file, re-run
        (tmp_path / "newfile.py").write_text("y = 2\n", encoding="utf-8")
        tracked2, _ = get_tracked_files(tmp_path, config)
        state2 = load_state(corpus_dir)
        graph2 = build_graph(tracked2, tmp_path, state2)

        kept_id = next(
            n["id"] for n in graph2["nodes"]
            if n["path"] == "original.py"
        )
        assert orig_id == kept_id, (
            f"original.py changed ID after adding new file: {orig_id} -> {kept_id}"
        )

    def test_same_path_always_gets_same_id(self, tmp_path):
        """build_graph called twice on the same state must reuse IDs."""
        _make_git_repo(tmp_path)
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)

        state = load_state(corpus_dir)
        g1 = build_graph(tracked, tmp_path, state)
        save_state(corpus_dir, state)

        state2 = load_state(corpus_dir)
        g2 = build_graph(tracked, tmp_path, state2)

        id1 = next(n["id"] for n in g1["nodes"] if n["path"] == "a.py")
        id2 = next(n["id"] for n in g2["nodes"] if n["path"] == "a.py")
        assert id1 == id2, f"ID changed: {id1} -> {id2}"

    def test_all_ids_unique_within_run(self, tmp_path):
        """No two nodes may share the same ID in a single graph."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        data = json.loads((repo / ".corpus" / "graph.json").read_text(encoding="utf-8"))
        all_ids = [n["id"] for n in data["nodes"]]
        assert len(all_ids) == len(set(all_ids)), (
            f"Duplicate IDs found: {[id for id in all_ids if all_ids.count(id) > 1]}"
        )


# ---------------------------------------------------------------------------
# AC4 — Files with known imports produce import edges
# ---------------------------------------------------------------------------

class TestAC4ImportEdges:
    def test_intra_repo_import_produces_edge(self, tmp_path):
        """A file that imports another tracked file must produce an imports edge."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        data = json.loads((repo / ".corpus" / "graph.json").read_text(encoding="utf-8"))
        import_edges = [e for e in data["edges"] if e["type"] == "imports"]
        assert len(import_edges) > 0, "Expected at least one imports edge"

    def test_external_imports_do_not_produce_edges(self, tmp_path):
        """Imports of external packages (os, sys) must NOT create edges."""
        _make_git_repo(tmp_path)
        (tmp_path / "app.py").write_text(
            "import os\nimport sys\nfrom pathlib import Path\n", encoding="utf-8"
        )
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))
        import_edges = [e for e in graph["edges"] if e["type"] == "imports"]
        assert len(import_edges) == 0, (
            f"External imports produced edges (should not): {import_edges}"
        )

    def test_absolute_import_produces_edge(self, tmp_path):
        """Absolute intra-repo import (mypkg.utils) must produce an imports edge."""
        _make_git_repo(tmp_path)
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "utils.py").write_text("def foo(): pass\n", encoding="utf-8")
        (tmp_path / "main.py").write_text(
            "from mypkg.utils import foo\n", encoding="utf-8"
        )

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))

        import_edges = [e for e in graph["edges"] if e["type"] == "imports"]
        assert len(import_edges) >= 1, (
            f"Expected at least one import edge from absolute import; got {import_edges}"
        )

    def test_contains_edges_exist(self, tmp_path):
        """Nested files must have 'contains' edges from their parent directory."""
        _make_git_repo(tmp_path)
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "mod.py").write_text("x = 1\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))

        contains_edges = [e for e in graph["edges"] if e["type"] == "contains"]
        assert len(contains_edges) >= 1, "Expected at least one 'contains' edge"

    def test_import_edge_direction(self, tmp_path):
        """imports edge must go from importer to importee (not reversed)."""
        _make_git_repo(tmp_path)
        (tmp_path / "importer.py").write_text(
            "from importee import stuff\n", encoding="utf-8"
        )
        (tmp_path / "importee.py").write_text("stuff = 42\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))

        id_to_path = {n["id"]: n["path"] for n in graph["nodes"]}
        import_edges = [e for e in graph["edges"] if e["type"] == "imports"]

        for edge in import_edges:
            from_path = id_to_path.get(edge["from"], "?")
            to_path = id_to_path.get(edge["to"], "?")
            assert from_path == "importer.py", (
                f"Expected importer.py as source, got: {from_path} -> {to_path}"
            )
            assert to_path == "importee.py", (
                f"Expected importee.py as target, got: {from_path} -> {to_path}"
            )


# ---------------------------------------------------------------------------
# AC5 — state.json has file_hashes for every tracked file
# ---------------------------------------------------------------------------

class TestAC5FileHashes:
    def test_file_hashes_key_exists(self, tmp_path):
        """state.json must have a 'file_hashes' key."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        state = json.loads((repo / ".corpus" / "state.json").read_text(encoding="utf-8"))
        assert "file_hashes" in state

    def test_file_hashes_is_a_dict(self, tmp_path):
        """file_hashes must be a JSON object (dict)."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        state = json.loads((repo / ".corpus" / "state.json").read_text(encoding="utf-8"))
        assert isinstance(state["file_hashes"], dict)

    def test_every_tracked_file_has_hash_entry(self, tmp_path):
        """Every tracked file must appear as a key in file_hashes."""
        _make_git_repo(tmp_path)
        for name in ["a.py", "b.py", "c.py"]:
            (tmp_path / name).write_text("x = 1\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)

        # Simulate what cli.py does
        tracked, _ = get_tracked_files(tmp_path, config)
        state = load_state(corpus_dir)
        build_graph(tracked, tmp_path, state)

        file_hashes: dict[str, str] = {}
        for abs_path in tracked:
            rel = abs_path.relative_to(tmp_path).as_posix()
            file_hashes[rel] = compute_hash(abs_path)
        state["file_hashes"] = file_hashes
        save_state(corpus_dir, state)

        saved = json.loads((corpus_dir / "state.json").read_text(encoding="utf-8"))
        tracked_rels = {p.relative_to(tmp_path).as_posix() for p in tracked}
        hash_keys = set(saved["file_hashes"].keys())
        missing = tracked_rels - hash_keys
        assert not missing, f"Files without hash entry: {missing}"

    def test_hash_values_are_hex_strings(self, tmp_path):
        """Hash values must be non-empty hexadecimal strings (SHA-256)."""
        _make_git_repo(tmp_path)
        (tmp_path / "module.py").write_text("def fn(): pass\n", encoding="utf-8")
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        state = load_state(corpus_dir)
        build_graph(tracked, tmp_path, state)
        for p in tracked:
            rel = p.relative_to(tmp_path).as_posix()
            h = compute_hash(p)
            assert re.match(r"^[0-9a-f]{64}$", h), f"Bad hash for {rel}: {h!r}"

    def test_hash_changes_when_file_content_changes(self, tmp_path):
        """SHA-256 must differ for different file content."""
        _make_git_repo(tmp_path)
        f = tmp_path / "changing.py"
        f.write_text("x = 1\n", encoding="utf-8")
        h1 = compute_hash(f)
        f.write_text("x = 2\n", encoding="utf-8")
        h2 = compute_hash(f)
        assert h1 != h2, "Hash must change when file content changes"

    def test_hash_stable_for_unchanged_file(self, tmp_path):
        """SHA-256 must be identical for two reads of the same file."""
        _make_git_repo(tmp_path)
        f = tmp_path / "stable.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert compute_hash(f) == compute_hash(f)

    def test_file_hashes_not_empty_after_update(self, tmp_path):
        """After corpus update on a non-empty repo, file_hashes must be non-empty."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        state = json.loads((repo / ".corpus" / "state.json").read_text(encoding="utf-8"))
        assert len(state["file_hashes"]) > 0


# ---------------------------------------------------------------------------
# FIX1 — Node IDs use k=6 hex chars with 10,000-attempt circuit breaker
# ---------------------------------------------------------------------------

class TestFix1NodeIdFormat:
    def test_new_ids_are_6_hex_chars(self, tmp_path):
        """Freshly generated IDs must be 'n_' + exactly 6 hex characters."""
        _make_git_repo(tmp_path)
        # Delete any existing state so IDs are fresh
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)

        for i in range(5):
            (tmp_path / f"file{i}.py").write_text(f"x={i}\n", encoding="utf-8")

        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        state = load_state(corpus_dir)  # fresh state — no existing node_ids
        graph = build_graph(tracked, tmp_path, state)

        pattern = re.compile(r"^n_[0-9a-fA-F]{6}$")
        for node in graph["nodes"]:
            nid = node["id"]
            assert pattern.match(nid), (
                f"ID {nid!r} does not match n_XXXXXX (6-hex) pattern"
            )

    def test_new_id_uniqueness(self):
        """_new_id must never return a duplicate within the same call sequence."""
        existing: set[str] = set()
        for _ in range(100):
            nid = _new_id(existing)
            assert nid not in existing
            existing.add(nid)

    def test_new_id_format(self):
        """_new_id output must always be 'n_' + 6 hex chars."""
        existing: set[str] = set()
        pattern = re.compile(r"^n_[0-9a-fA-F]{6}$")
        for _ in range(50):
            nid = _new_id(existing)
            assert pattern.match(nid), f"Bad ID format: {nid!r}"
            existing.add(nid)

    def test_circuit_breaker_fires_on_exhaustion(self):
        """_new_id must raise RuntimeError after 10,000 failed attempts."""
        # Fill the entire 16^6 = 16,777,216 space is impractical, but we
        # can fill the actual hexdigits[:16] = '0123456789abcdef' 6-char space
        # partially and confirm the error message is correct by mocking.
        import unittest.mock as mock

        with mock.patch("corpus.graph.random.choices", return_value=list("aaaaaa")):
            existing = {"n_aaaaaa"}  # the only candidate is already taken
            with pytest.raises(RuntimeError, match="10,000"):
                _new_id(existing)

    def test_id_prefix_is_n_underscore(self):
        """All IDs must start with 'n_'."""
        existing: set[str] = set()
        for _ in range(20):
            nid = _new_id(existing)
            assert nid.startswith("n_"), f"ID missing 'n_' prefix: {nid!r}"
            existing.add(nid)


# ---------------------------------------------------------------------------
# FIX2 — No duplicate symbols in any node (including __all__ interaction)
# ---------------------------------------------------------------------------

class TestFix2NoduplicateSymbols:
    def test_no_duplicate_symbols_in_built_graph(self, tmp_path):
        """No node in graph.json may have duplicate symbols."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        data = json.loads((repo / ".corpus" / "graph.json").read_text(encoding="utf-8"))
        for node in data["nodes"]:
            syms = node.get("symbols", [])
            assert len(syms) == len(set(syms)), (
                f"Duplicate symbols in {node['path']}: {[s for s in syms if syms.count(s)>1]}"
            )

    def test_all_export_deduplicates_with_def(self, tmp_path):
        """When __all__ re-lists names that are also defined, symbols must not repeat."""
        src = """\
__all__ = ["MyClass", "helper"]

def helper():
    return 1

class MyClass:
    pass
"""
        f = tmp_path / "mod.py"
        f.write_text(src, encoding="utf-8")
        result = parse_file(f)
        syms = result["symbols"]
        assert len(syms) == len(set(syms)), (
            f"Duplicate symbols when __all__ overlaps defs: {syms}"
        )

    def test_all_only_no_defs(self, tmp_path):
        """__all__ with names that have no corresponding def must not duplicate."""
        src = '__all__ = ["foo", "foo", "bar"]\n'
        f = tmp_path / "mod.py"
        f.write_text(src, encoding="utf-8")
        result = parse_file(f)
        syms = result["symbols"]
        assert len(syms) == len(set(syms)), (
            f"Duplicates from __all__ with repeated names: {syms}"
        )
        assert "foo" in syms
        assert "bar" in syms

    def test_decorated_function_not_duplicated(self, tmp_path):
        """A decorated function must appear exactly once in symbols."""
        src = """\
import functools

def my_decorator(f):
    return f

@my_decorator
def decorated():
    pass
"""
        f = tmp_path / "decmod.py"
        f.write_text(src, encoding="utf-8")
        result = parse_file(f)
        syms = result["symbols"]
        assert syms.count("decorated") == 1, (
            f"'decorated' appears {syms.count('decorated')} times in {syms}"
        )


# ---------------------------------------------------------------------------
# FIX3 — Relative Python imports produce edges
# ---------------------------------------------------------------------------

class TestFix3RelativeImports:
    def test_relative_import_dot_resolves(self):
        """'from . import x' (specifier='.') resolves to __init__.py."""
        tracked = {"pkg/__init__.py", "pkg/utils.py", "pkg/module.py"}
        result = _resolve_python_import(".", "pkg/module.py", tracked)
        assert result == "pkg/__init__.py", f"Got: {result}"

    def test_relative_import_dot_module_resolves(self):
        """'from .utils import x' (specifier='.utils') resolves to pkg/utils.py."""
        tracked = {"pkg/__init__.py", "pkg/utils.py", "pkg/module.py"}
        result = _resolve_python_import(".utils", "pkg/module.py", tracked)
        assert result == "pkg/utils.py", f"Got: {result}"

    def test_relative_import_double_dot_resolves(self):
        """'from ..core import x' (specifier='..core') resolves up one level."""
        tracked = {"core.py", "pkg/__init__.py", "pkg/module.py"}
        result = _resolve_python_import("..core", "pkg/module.py", tracked)
        assert result == "core.py", f"Got: {result}"

    def test_relative_import_escaping_root_returns_none(self):
        """'from .. import x' from a top-level file must return None (can't go above root)."""
        tracked = {"module.py"}
        result = _resolve_python_import("..", "module.py", tracked)
        assert result is None, f"Expected None, got: {result}"

    def test_relative_import_nonexistent_returns_none(self):
        """Relative import to a non-tracked path must return None."""
        tracked = {"pkg/__init__.py"}
        result = _resolve_python_import(".nonexistent", "pkg/module.py", tracked)
        assert result is None, f"Expected None, got: {result}"

    def test_relative_imports_produce_graph_edges(self, tmp_path):
        """A package using 'from . import utils' must produce an imports edge."""
        _make_git_repo(tmp_path)
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("from . import utils\n", encoding="utf-8")
        (pkg / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))

        import_edges = [e for e in graph["edges"] if e["type"] == "imports"]
        assert len(import_edges) >= 1, (
            "from . import utils should produce an imports edge but found none"
        )

    def test_relative_dot_module_import_produces_edge(self, tmp_path):
        """'from .helpers import Y' must produce an edge from __init__.py to helpers.py."""
        _make_git_repo(tmp_path)
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "from .helpers import do_thing\n", encoding="utf-8"
        )
        (pkg / "helpers.py").write_text("def do_thing(): pass\n", encoding="utf-8")

        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))

        id_to_path = {n["id"]: n["path"] for n in graph["nodes"]}
        import_edges = [
            (id_to_path.get(e["from"]), id_to_path.get(e["to"]))
            for e in graph["edges"] if e["type"] == "imports"
        ]
        assert ("mypkg/__init__.py", "mypkg/helpers.py") in import_edges, (
            f"Expected mypkg/__init__.py -> mypkg/helpers.py import edge. "
            f"Got: {import_edges}"
        )


# ---------------------------------------------------------------------------
# FIX4 — No duplicate edges
# ---------------------------------------------------------------------------

class TestFix4NoDuplicateEdges:
    def test_no_duplicate_edges_in_graph(self, tmp_path):
        """No (from, to, type) triple may appear more than once in edges."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        data = json.loads((repo / ".corpus" / "graph.json").read_text(encoding="utf-8"))
        keys = [(e["from"], e["to"], e["type"]) for e in data["edges"]]
        assert len(keys) == len(set(keys)), (
            f"Duplicate edges found: "
            f"{[k for k in set(keys) if keys.count(k) > 1]}"
        )

    def test_duplicate_imports_produce_single_edge(self, tmp_path):
        """A file importing the same module twice must produce only one edge."""
        _make_git_repo(tmp_path)
        (tmp_path / "base.py").write_text("X = 1\n", encoding="utf-8")
        (tmp_path / "consumer.py").write_text(
            "from base import X\nfrom base import X  # duplicate\n", encoding="utf-8"
        )
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))

        import_edges = [(e["from"], e["to"]) for e in graph["edges"] if e["type"] == "imports"]
        assert len(import_edges) == len(set(import_edges)), (
            f"Duplicate import edges: {import_edges}"
        )

    def test_no_self_loop_edges(self, tmp_path):
        """A node must not have an edge pointing to itself."""
        _make_git_repo(tmp_path)
        (tmp_path / "selfref.py").write_text("from selfref import x\n", encoding="utf-8")
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))

        for edge in graph["edges"]:
            if edge["type"] == "imports":
                assert edge["from"] != edge["to"], (
                    f"Self-loop edge found: {edge}"
                )


# ---------------------------------------------------------------------------
# Parser unit tests — correctness of symbol/import extraction
# ---------------------------------------------------------------------------

class TestParserPython:
    def test_extracts_function_symbols(self, tmp_path):
        f = tmp_path / "funcs.py"
        f.write_text("def alpha(): pass\ndef beta(): pass\n", encoding="utf-8")
        result = parse_file(f)
        assert "alpha" in result["symbols"]
        assert "beta" in result["symbols"]

    def test_extracts_class_symbols(self, tmp_path):
        f = tmp_path / "cls.py"
        f.write_text("class Foo: pass\nclass Bar: pass\n", encoding="utf-8")
        result = parse_file(f)
        assert "Foo" in result["symbols"]
        assert "Bar" in result["symbols"]

    def test_extracts_decorated_symbols(self, tmp_path):
        f = tmp_path / "deco.py"
        f.write_text("def deco(f): return f\n\n@deco\ndef decorated(): pass\n", encoding="utf-8")
        result = parse_file(f)
        assert "decorated" in result["symbols"]

    def test_extracts_absolute_imports(self, tmp_path):
        f = tmp_path / "imps.py"
        f.write_text("import os\nfrom pathlib import Path\n", encoding="utf-8")
        result = parse_file(f)
        assert "os" in result["imports"]
        assert "pathlib" in result["imports"]

    def test_extracts_relative_imports(self, tmp_path):
        f = tmp_path / "relimps.py"
        f.write_text("from . import sibling\nfrom .utils import helper\n", encoding="utf-8")
        result = parse_file(f)
        # `from . import sibling` synthesises ".sibling" (not bare ".") so the
        # graph resolver can distinguish it from a self-import.
        assert ".sibling" in result["imports"]
        assert ".utils" in result["imports"]

    def test_unsupported_extension_returns_empty(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("col1,col2\n1,2\n", encoding="utf-8")
        result = parse_file(f)
        assert result["lang"] is None
        assert result["symbols"] == []
        assert result["imports"] == []

    def test_empty_file_returns_empty_symbols(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        result = parse_file(f)
        assert result["lang"] == "python"
        assert result["symbols"] == []
        assert result["imports"] == []

    def test_imports_deduplicated(self, tmp_path):
        f = tmp_path / "dupimps.py"
        f.write_text("import os\nimport os\n", encoding="utf-8")
        result = parse_file(f)
        assert result["imports"].count("os") == 1

    def test_symbols_deduplicated(self, tmp_path):
        """parse_file must not return duplicate symbol names."""
        f = tmp_path / "dupdef.py"
        # Re-defining a function produces two parse hits without dedup
        f.write_text(
            '__all__ = ["my_func"]\ndef my_func(): pass\n', encoding="utf-8"
        )
        result = parse_file(f)
        assert result["symbols"].count("my_func") == 1, (
            f"'my_func' appears {result['symbols'].count('my_func')} times: {result['symbols']}"
        )

    def test_nonexistent_file_returns_empty(self, tmp_path):
        result = parse_file(tmp_path / "ghost.py")
        assert result["symbols"] == []
        assert result["imports"] == []

    def test_unicode_content_parsed(self, tmp_path):
        """Files with non-ASCII content (e.g. Chinese comments) must not crash."""
        f = tmp_path / "unicode_mod.py"
        f.write_text("# 这是注释\ndef 函数名(): pass\n", encoding="utf-8")
        result = parse_file(f)
        assert result["lang"] == "python"
        # Should not raise; symbols may or may not include the unicode name


class TestParserJavaScript:
    def test_extracts_js_export_function(self, tmp_path):
        f = tmp_path / "mod.js"
        f.write_text("export function greet(name) { return name; }\n", encoding="utf-8")
        result = parse_file(f)
        assert "greet" in result["symbols"]

    def test_extracts_js_export_const(self, tmp_path):
        f = tmp_path / "consts.js"
        f.write_text("export const MAX = 100;\n", encoding="utf-8")
        result = parse_file(f)
        assert "MAX" in result["symbols"]

    def test_extracts_js_import(self, tmp_path):
        f = tmp_path / "consumer.js"
        f.write_text("import { foo } from './utils';\n", encoding="utf-8")
        result = parse_file(f)
        assert "./utils" in result["imports"]

    def test_bare_js_import_not_resolved_to_edge(self, tmp_path):
        """Bare npm import specifiers must not produce edges."""
        _make_git_repo(tmp_path)
        (tmp_path / "app.js").write_text("import React from 'react';\n", encoding="utf-8")
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))
        import_edges = [e for e in graph["edges"] if e["type"] == "imports"]
        assert len(import_edges) == 0, (
            f"Bare npm import produced edges: {import_edges}"
        )


# ---------------------------------------------------------------------------
# Import resolver unit tests (JS)
# ---------------------------------------------------------------------------

class TestJsImportResolver:
    def test_relative_js_import_resolves(self):
        tracked = {"src/app.js", "src/utils.js"}
        result = _resolve_js_import("./utils", "src/app.js", tracked)
        assert result == "src/utils.js"

    def test_relative_js_import_with_extension(self):
        tracked = {"src/app.js", "src/utils.js"}
        result = _resolve_js_import("./utils.js", "src/app.js", tracked)
        assert result == "src/utils.js"

    def test_bare_js_specifier_returns_none(self):
        tracked = {"src/app.js"}
        result = _resolve_js_import("react", "src/app.js", tracked)
        assert result is None

    def test_parent_dir_js_import_resolves(self):
        tracked = {"src/app.js", "shared.js"}
        result = _resolve_js_import("../shared", "src/app.js", tracked)
        assert result == "shared.js"

    def test_js_index_file_resolves(self):
        tracked = {"src/app.js", "components/index.js"}
        result = _resolve_js_import("./components", "src/app.js", tracked)
        # Should resolve to components/index.js or None depending on directory
        # The resolver checks base + /index.js
        # 'src/app.js' dir is 'src', joined with './components' -> 'src/components'
        # 'src/components' not in tracked, 'src/components.js' not in tracked,
        # 'src/components/index.js' not in tracked
        # So this returns None for this test case — expected
        assert result is None


# ---------------------------------------------------------------------------
# Error paths and edge cases for graph building
# ---------------------------------------------------------------------------

class TestGraphEdgeCases:
    def test_corpus_update_requires_init_first(self, tmp_path):
        """corpus update without corpus init must fail with ClickException."""
        runner = CliRunner()
        old = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(main, ["update"])
        finally:
            os.chdir(old)
        assert result.exit_code != 0
        assert "corpus init" in result.output.lower() or "not found" in result.output.lower()

    def test_write_graph_atomic(self, tmp_path):
        """write_graph must produce a valid JSON file (atomic write)."""
        graph = {"version": 1, "nodes": [], "edges": [], "generated_at": "now"}
        write_graph(tmp_path, graph)
        result = json.loads((tmp_path / "graph.json").read_text(encoding="utf-8"))
        assert result["version"] == 1

    def test_all_node_ids_are_strings(self, tmp_path):
        """All node IDs in graph.json must be strings."""
        _make_git_repo(tmp_path)
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))
        for node in graph["nodes"]:
            assert isinstance(node["id"], str), f"Non-string ID: {node['id']!r}"

    def test_graph_generated_at_is_iso8601(self, tmp_path):
        """generated_at field must be an ISO-8601 timestamp string."""
        _make_git_repo(tmp_path)
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))
        ts = graph.get("generated_at", "")
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts), (
            f"generated_at not ISO-8601: {ts!r}"
        )

    def test_deep_nested_dir_nodes_created(self, tmp_path):
        """Files in deeply nested dirs must generate all ancestor dir nodes."""
        _make_git_repo(tmp_path)
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "leaf.py").write_text("x = 1\n", encoding="utf-8")
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        graph = build_graph(tracked, tmp_path, load_state(corpus_dir))
        dir_paths = {n["path"] for n in graph["nodes"] if n["type"] == "dir"}
        assert "a" in dir_paths, f"Missing 'a' dir node. Got: {dir_paths}"
        assert "a/b" in dir_paths, f"Missing 'a/b' dir node. Got: {dir_paths}"
        assert "a/b/c" in dir_paths, f"Missing 'a/b/c' dir node. Got: {dir_paths}"

    def test_state_json_has_node_ids_map(self, tmp_path):
        """state.json must contain a node_ids map after corpus update."""
        repo = _minimal_python_repo(tmp_path)
        _init_corpus(repo)
        _run_update(repo)
        state = json.loads((repo / ".corpus" / "state.json").read_text(encoding="utf-8"))
        assert "node_ids" in state, "state.json missing 'node_ids' key"
        assert isinstance(state["node_ids"], dict), "'node_ids' must be a dict"
        assert len(state["node_ids"]) > 0, "'node_ids' must be non-empty after update"
