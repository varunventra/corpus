"""
Phase 4 acceptance-criteria tests — Static graph viewer (server-side).

Acceptance criteria under test:
  AC1 - `corpus serve` (without --mcp) is wired in the CLI: help text shows the
        command, no syntax errors.
  AC2 - GET /graph returns valid JSON with `nodes` and `edges` arrays;
        returns 503 when graph.json is missing.
  AC3 - GET /doc?path=X returns 404 when the doc doesn't exist;
        returns 400 for path-traversal attempts.
  AC4 - WS /events — connection is accepted and held (stub works).
  AC5 - Static file serving returns 500 (or a meaningful error) when
        frontend/dist/ doesn't exist.
  AC6 - Second GET /graph returns the same data as the first (server is
        stateless for reads).
  AC7 - GET /graph response has edges with `source`/`target` keys (not
        `from`/`to` — edge normalisation).

NOT tested here (requires browser / npm):
  - Browser rendering, pan/zoom, React component behaviour
  - `corpus serve` actually launching uvicorn (blocks; not testable in pytest)
  - useGraph.js polling logic (JavaScript / browser-only)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Minimal fixtures
# ---------------------------------------------------------------------------

# graph.json that uses "from"/"to" keys (raw on-disk format)
GRAPH_FROM_TO = {
    "nodes": [
        {
            "id": "n_aaa111",
            "path": "pkg/alpha.py",
            "type": "file",
            "lang": "python",
            "symbols": ["AlphaClass"],
            "importance": 3,
            "doc": "docs/pkg/alpha.py.md",
            "stale": False,
        },
        {
            "id": "n_bbb222",
            "path": "pkg/beta.py",
            "type": "file",
            "lang": "python",
            "symbols": ["BetaClass"],
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
            "stale": False,
        },
    ],
    "edges": [
        {"from": "n_aaa111", "to": "n_bbb222", "type": "imports"},
        {"from": "n_ccc333", "to": "n_aaa111", "type": "contains"},
    ],
}

# graph.json that already uses "source"/"target" keys
GRAPH_SOURCE_TARGET = {
    "nodes": [
        {
            "id": "n_x1",
            "path": "a.py",
            "type": "file",
            "lang": "python",
            "symbols": [],
            "importance": 1,
            "doc": None,
            "stale": False,
        },
        {
            "id": "n_x2",
            "path": "b.py",
            "type": "file",
            "lang": "python",
            "symbols": [],
            "importance": 1,
            "doc": None,
            "stale": False,
        },
    ],
    "edges": [
        {"source": "n_x1", "target": "n_x2", "type": "imports"},
    ],
}


def _write_corpus(tmp_path: Path, graph: dict) -> None:
    """Write a minimal .corpus/ directory with graph.json and a sample doc."""
    corpus_dir = tmp_path / ".corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "graph.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    # Populate one doc so /doc tests can find it
    docs_dir = corpus_dir / "docs" / "pkg"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "alpha.py.md").write_text(
        "## Purpose\nAlpha module.\n\n## Symbols\n- AlphaClass\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Helper: build a TestClient whose .corpus/ reads come from tmp_path
# ---------------------------------------------------------------------------

def _client(tmp_path: Path) -> TestClient:
    """Return a TestClient bound to the corpus FastAPI app.

    The server resolves .corpus/ from os.getcwd(), so we chdir to tmp_path
    before constructing the client and restore cwd afterwards.
    """
    from corpus.server import app

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        client = TestClient(app, raise_server_exceptions=False)
    finally:
        os.chdir(old_cwd)
    return client, old_cwd


# ---------------------------------------------------------------------------
# Context manager that temporarily chdirs inside a test
# ---------------------------------------------------------------------------

class _ChdirContext:
    """chdir to target for the duration of the with-block."""

    def __init__(self, target: Path) -> None:
        self._target = target
        self._old: str | None = None

    def __enter__(self):
        self._old = os.getcwd()
        os.chdir(self._target)
        return self

    def __exit__(self, *_):
        if self._old is not None:
            os.chdir(self._old)


# ---------------------------------------------------------------------------
# AC1 — CLI wiring: `corpus serve` (without --mcp)
# ---------------------------------------------------------------------------

class TestAC1ServeCliWiring:
    """AC1: corpus serve is wired in the CLI; help text shows the command."""

    def test_corpus_help_lists_serve_command(self):
        """corpus --help output must include 'serve' in the command list."""
        from corpus.cli import main
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(main, ["--help"], catch_exceptions=False)
        assert result.exit_code == 0, f"corpus --help exited {result.exit_code}"
        assert "serve" in result.output, (
            f"'serve' not found in corpus --help output:\n{result.output}"
        )

    def test_serve_help_exits_zero(self):
        """corpus serve --help must exit 0 with no syntax errors."""
        from corpus.cli import main
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"], catch_exceptions=False)
        assert result.exit_code == 0, (
            f"corpus serve --help exited {result.exit_code}:\n{result.output}"
        )

    def test_serve_help_shows_mcp_flag(self):
        """corpus serve --help must describe the --mcp flag."""
        from corpus.cli import main
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"], catch_exceptions=False)
        assert "--mcp" in result.output, (
            f"--mcp flag not documented in serve --help:\n{result.output}"
        )

    def test_serve_help_describes_graph_viewer(self):
        """corpus serve --help must describe the graph viewer in its docstring."""
        from corpus.cli import main
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"], catch_exceptions=False)
        output_lower = result.output.lower()
        assert "graph" in output_lower or "viewer" in output_lower or "mcp" in output_lower, (
            f"No 'graph', 'viewer', or 'mcp' in serve help output:\n{result.output}"
        )

    def test_serve_importable_no_syntax_errors(self):
        """corpus.cli must import without SyntaxError or ImportError."""
        import importlib
        try:
            import corpus.cli
            importlib.reload(corpus.cli)
        except (SyntaxError, ImportError) as exc:
            pytest.fail(f"corpus.cli import raised: {exc}")

    def test_server_module_importable_no_syntax_errors(self):
        """corpus.server must import without SyntaxError or ImportError."""
        import importlib
        try:
            import corpus.server
            importlib.reload(corpus.server)
        except (SyntaxError, ImportError) as exc:
            pytest.fail(f"corpus.server import raised: {exc}")


# ---------------------------------------------------------------------------
# AC2 — GET /graph: valid JSON with nodes + edges; 503 when missing
# ---------------------------------------------------------------------------

class TestAC2GetGraph:
    """AC2: GET /graph returns valid JSON with nodes and edges; 503 when missing."""

    def test_get_graph_returns_200_when_graph_exists(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/graph")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

    def test_get_graph_content_type_is_json(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/graph")

        assert "application/json" in response.headers.get("content-type", ""), (
            f"Expected JSON content-type, got: {response.headers.get('content-type')}"
        )

    def test_get_graph_has_nodes_key(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        assert "nodes" in data, f"'nodes' key missing from /graph response: {data.keys()}"

    def test_get_graph_has_edges_key(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        assert "edges" in data, f"'edges' key missing from /graph response: {data.keys()}"

    def test_get_graph_nodes_is_list(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        assert isinstance(data["nodes"], list), (
            f"'nodes' must be a list, got {type(data['nodes'])}"
        )

    def test_get_graph_edges_is_list(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        assert isinstance(data["edges"], list), (
            f"'edges' must be a list, got {type(data['edges'])}"
        )

    def test_get_graph_node_count_matches_fixture(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        assert len(data["nodes"]) == len(GRAPH_FROM_TO["nodes"]), (
            f"Expected {len(GRAPH_FROM_TO['nodes'])} nodes, got {len(data['nodes'])}"
        )

    def test_get_graph_edge_count_matches_fixture(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        assert len(data["edges"]) == len(GRAPH_FROM_TO["edges"]), (
            f"Expected {len(GRAPH_FROM_TO['edges'])} edges, got {len(data['edges'])}"
        )

    def test_get_graph_returns_503_when_graph_json_missing(self, tmp_path):
        """No .corpus/graph.json → 503."""
        # Do not call _write_corpus — leave .corpus absent
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/graph")

        assert response.status_code == 503, (
            f"Expected 503 when graph.json missing, got {response.status_code}"
        )

    def test_get_graph_503_body_has_error_key(self, tmp_path):
        """503 response body must include an 'error' key explaining what happened."""
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        assert "error" in data, f"503 body missing 'error' key: {data}"

    def test_get_graph_503_when_corpus_dir_exists_but_graph_missing(self, tmp_path):
        """Even if .corpus/ dir exists but graph.json is absent, must still 503."""
        (tmp_path / ".corpus").mkdir()
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/graph")

        assert response.status_code == 503, (
            f"Expected 503, got {response.status_code}"
        )

    def test_get_graph_503_for_corrupt_json(self, tmp_path):
        """Corrupt graph.json must result in a 503, not a 500 crash."""
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        (corpus_dir / "graph.json").write_text("{ this is not valid json {{", encoding="utf-8")
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/graph")

        assert response.status_code == 503, (
            f"Expected 503 for corrupt graph.json, got {response.status_code}: {response.text}"
        )

    def test_get_graph_empty_graph_valid(self, tmp_path):
        """An empty graph (no nodes, no edges) must still return 200."""
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        (corpus_dir / "graph.json").write_text(
            json.dumps({"nodes": [], "edges": []}), encoding="utf-8"
        )
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/graph")

        assert response.status_code == 200, (
            f"Empty graph returned {response.status_code}"
        )
        data = response.json()
        assert data["nodes"] == []
        assert data["edges"] == []


# ---------------------------------------------------------------------------
# AC3 — GET /doc?path=X: 404 for missing doc; 400 for path traversal
# ---------------------------------------------------------------------------

class TestAC3GetDoc:
    """AC3: /doc returns 404 for missing doc; 400 for path traversal."""

    def test_get_doc_returns_200_for_existing_doc(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/doc", params={"path": "pkg/alpha.py"})

        assert response.status_code == 200, (
            f"Expected 200 for existing doc, got {response.status_code}: {response.text}"
        )

    def test_get_doc_returns_doc_text_content(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/doc", params={"path": "pkg/alpha.py"})

        assert "Purpose" in response.text, (
            f"Expected doc text with 'Purpose', got: {response.text!r}"
        )

    def test_get_doc_returns_404_for_nonexistent_path(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/doc", params={"path": "no/such/file.py"})

        assert response.status_code == 404, (
            f"Expected 404 for missing doc, got {response.status_code}: {response.text}"
        )

    def test_get_doc_404_body_has_error_key(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/doc", params={"path": "no/such/file.py"}).json()

        assert "error" in data, f"404 body missing 'error' key: {data}"

    def test_get_doc_400_for_relative_traversal(self, tmp_path):
        """../../../etc/passwd must be rejected with 400."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/doc", params={"path": "../../../etc/passwd"})

        assert response.status_code == 400, (
            f"Expected 400 for path traversal '../../../etc/passwd', "
            f"got {response.status_code}: {response.text}"
        )

    def test_get_doc_400_for_absolute_unix_path(self, tmp_path):
        """/etc/passwd must be rejected with 400."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/doc", params={"path": "/etc/passwd"})

        assert response.status_code == 400, (
            f"Expected 400 for absolute path '/etc/passwd', "
            f"got {response.status_code}: {response.text}"
        )

    def test_get_doc_400_for_double_dot_traversal(self, tmp_path):
        """../../server.py must be rejected with 400."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/doc", params={"path": "../../server.py"})

        assert response.status_code == 400, (
            f"Expected 400 for traversal '../../server.py', "
            f"got {response.status_code}: {response.text}"
        )

    def test_get_doc_400_body_has_error_key(self, tmp_path):
        """400 response body must include 'error'."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/doc", params={"path": "../../../etc/passwd"}).json()

        assert "error" in data, f"400 body missing 'error' key: {data}"

    def test_get_doc_traversal_does_not_read_outside_corpus(self, tmp_path):
        """Traversal path must not actually read a file outside .corpus/docs/."""
        # Write a sentinel outside .corpus/
        sentinel = tmp_path / "secret.txt"
        sentinel.write_text("TOP SECRET", encoding="utf-8")
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            # Attempt to read ../secret (resolves outside docs root)
            response = client.get("/doc", params={"path": "../../.corpus/../secret"})

        assert response.status_code in (400, 404), (
            f"Expected 400 or 404 for traversal, got {response.status_code}: {response.text}"
        )
        assert "TOP SECRET" not in response.text, (
            "Server leaked secret.txt content through path traversal!"
        )

    def test_get_doc_requires_path_param(self, tmp_path):
        """GET /doc without ?path= must return a 4xx error, not crash."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/doc")

        assert 400 <= response.status_code < 500, (
            f"Expected 4xx when ?path= is missing, got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# AC4 — WS /events: connection accepted and held (Phase 4 stub)
# ---------------------------------------------------------------------------

class TestAC4WebSocketEvents:
    """AC4: WS /events accepts a connection and holds it open (Phase 5 stub)."""

    def test_websocket_events_accepts_connection(self, tmp_path):
        """WebSocket handshake must succeed (no immediate rejection)."""
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            # TestClient context manager opens and closes the WS cleanly
            try:
                with client.websocket_connect("/events") as ws:
                    # Connection accepted — stub is working
                    pass
            except Exception as exc:
                pytest.fail(
                    f"WS /events rejected connection or raised unexpectedly: {exc}"
                )

    def test_websocket_events_accepts_text_message(self, tmp_path):
        """Sending a text message to /events must not crash the server."""
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            try:
                with client.websocket_connect("/events") as ws:
                    ws.send_text("ping")
                    # Server stub reads text but doesn't respond; no reply expected
            except Exception as exc:
                pytest.fail(
                    f"WS /events raised after sending a text message: {exc}"
                )

    def test_websocket_events_clean_disconnect(self, tmp_path):
        """Client-initiated close must not leave the server in an error state."""
        from corpus.server import app

        raised = False
        try:
            with _ChdirContext(tmp_path):
                client = TestClient(app, raise_server_exceptions=False)
                with client.websocket_connect("/events"):
                    pass  # disconnect immediately on context exit
        except Exception:
            raised = True

        assert not raised, "WS /events raised on clean client disconnect"


# ---------------------------------------------------------------------------
# AC5 — Static file serving: 500 when frontend/dist/ doesn't exist
# ---------------------------------------------------------------------------

class TestAC5StaticFileServing:
    """AC5: / returns 500 (or meaningful error) when frontend/dist/ doesn't exist."""

    def test_get_root_returns_500_when_dist_missing(self, tmp_path):
        """GET / must return 500 when frontend/dist/ is absent."""
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/")

        assert response.status_code == 500, (
            f"Expected 500 when frontend/dist/ is missing, got {response.status_code}"
        )

    def test_get_root_500_body_has_error_key(self, tmp_path):
        """500 body must contain 'error' to help the developer diagnose."""
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/")

        data = response.json()
        assert "error" in data, (
            f"500 body missing 'error' key when dist missing: {data}"
        )

    def test_get_root_500_mentions_frontend_build(self, tmp_path):
        """Error message must mention the frontend build command."""
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/")

        error_text = response.json().get("error", "")
        assert "frontend" in error_text.lower() or "build" in error_text.lower(), (
            f"Error message should mention 'frontend' or 'build', got: {error_text!r}"
        )

    def test_get_arbitrary_path_returns_500_when_dist_missing(self, tmp_path):
        """GET /some/js/bundle.js must also 500 when dist is missing."""
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/assets/index.js")

        assert response.status_code == 500, (
            f"Expected 500 for /assets/index.js when dist missing, got {response.status_code}"
        )

    def test_api_routes_still_work_when_dist_missing(self, tmp_path):
        """/graph must still return 503 (not 500) even when frontend/dist/ is absent.

        This verifies API routes take priority over the SPA catch-all.
        """
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/graph")

        # /graph is an API route; the missing dist must NOT interfere with it
        assert response.status_code == 503, (
            f"GET /graph should be 503 (no graph.json), not {response.status_code}"
        )


# ---------------------------------------------------------------------------
# AC6 — Stateless reads: second GET /graph returns the same data as the first
# ---------------------------------------------------------------------------

class TestAC6StatelessReads:
    """AC6: GET /graph is stateless; two consecutive calls return identical data."""

    def test_two_graph_calls_return_identical_nodes(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data1 = client.get("/graph").json()
            data2 = client.get("/graph").json()

        assert data1["nodes"] == data2["nodes"], (
            "Second GET /graph returned different nodes than the first"
        )

    def test_two_graph_calls_return_identical_edges(self, tmp_path):
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data1 = client.get("/graph").json()
            data2 = client.get("/graph").json()

        assert data1["edges"] == data2["edges"], (
            "Second GET /graph returned different edges than the first"
        )

    def test_repeated_calls_do_not_mutate_disk(self, tmp_path):
        """Multiple reads must not change graph.json on disk."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        graph_path = tmp_path / ".corpus" / "graph.json"
        original_text = graph_path.read_text(encoding="utf-8")
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            for _ in range(3):
                client.get("/graph")

        after_text = graph_path.read_text(encoding="utf-8")
        assert original_text == after_text, (
            "GET /graph modified graph.json on disk — server must be read-only"
        )

    def test_graph_call_after_doc_call_still_same(self, tmp_path):
        """GET /graph result must be unaffected by intervening GET /doc calls."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data1 = client.get("/graph").json()
            client.get("/doc", params={"path": "pkg/alpha.py"})  # side call
            data2 = client.get("/graph").json()

        assert data1 == data2, (
            "GET /graph result changed after a /doc call — unexpected mutation"
        )


# ---------------------------------------------------------------------------
# AC7 — Edge normalisation: edges have source/target, not from/to
# ---------------------------------------------------------------------------

class TestAC7EdgeNormalization:
    """AC7: GET /graph response edges use source/target keys (not from/to)."""

    def test_edges_have_source_key_not_from(self, tmp_path):
        """All edges in /graph response must have 'source', not 'from'."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        edges = data.get("edges", [])
        assert len(edges) > 0, "No edges in response to check normalization"
        for edge in edges:
            assert "source" in edge, (
                f"Edge missing 'source' key (got 'from' style): {edge}"
            )
            assert "from" not in edge, (
                f"Edge still has 'from' key after normalization: {edge}"
            )

    def test_edges_have_target_key_not_to(self, tmp_path):
        """All edges in /graph response must have 'target', not 'to'."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        edges = data.get("edges", [])
        assert len(edges) > 0, "No edges in response to check normalization"
        for edge in edges:
            assert "target" in edge, (
                f"Edge missing 'target' key (got 'to' style): {edge}"
            )
            assert "to" not in edge, (
                f"Edge still has 'to' key after normalization: {edge}"
            )

    def test_edges_source_value_correct(self, tmp_path):
        """The source ID in the normalized edge must match the original 'from' value."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        edges = data.get("edges", [])
        original_edges = GRAPH_FROM_TO["edges"]
        for returned, original in zip(edges, original_edges):
            expected_source = original.get("source") or original.get("from")
            assert returned["source"] == expected_source, (
                f"Edge source mismatch: got {returned['source']!r}, "
                f"expected {expected_source!r}"
            )

    def test_edges_target_value_correct(self, tmp_path):
        """The target ID must match the original 'to' value."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        edges = data.get("edges", [])
        original_edges = GRAPH_FROM_TO["edges"]
        for returned, original in zip(edges, original_edges):
            expected_target = original.get("target") or original.get("to")
            assert returned["target"] == expected_target, (
                f"Edge target mismatch: got {returned['target']!r}, "
                f"expected {expected_target!r}"
            )

    def test_edge_type_preserved_after_normalization(self, tmp_path):
        """The 'type' field on each edge must survive normalization."""
        _write_corpus(tmp_path, GRAPH_FROM_TO)
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        edges = data.get("edges", [])
        original_edges = GRAPH_FROM_TO["edges"]
        for returned, original in zip(edges, original_edges):
            assert returned.get("type") == original.get("type"), (
                f"Edge type changed during normalization: "
                f"got {returned.get('type')!r}, expected {original.get('type')!r}"
            )

    def test_already_normalised_edges_still_work(self, tmp_path):
        """graph.json that already uses source/target must also be served correctly."""
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir(parents=True, exist_ok=True)
        (corpus_dir / "graph.json").write_text(
            json.dumps(GRAPH_SOURCE_TARGET), encoding="utf-8"
        )
        from corpus.server import app

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.get("/graph").json()

        edges = data.get("edges", [])
        assert len(edges) == 1
        assert edges[0]["source"] == "n_x1"
        assert edges[0]["target"] == "n_x2"


# ---------------------------------------------------------------------------
# NOT TESTABLE — documented skips
# ---------------------------------------------------------------------------

@pytest.mark.skip(
    reason=(
        "NOT TESTABLE in Python: useGraph.js stale polling is client-side JavaScript. "
        "Requires a browser or Node/jsdom test environment. "
        "Server-side statelessness is covered by TestAC6StatelessReads."
    )
)
def test_usegraph_js_polling_logic():
    """Placeholder: useGraph.js polling is browser/JS-only, skipped here."""
    pass


@pytest.mark.skip(
    reason=(
        "NOT TESTABLE in pytest: 'corpus serve' launching uvicorn blocks indefinitely. "
        "The CLI wiring (that the command exists and parses) is covered by TestAC1ServeCliWiring."
    )
)
def test_corpus_serve_launches_uvicorn():
    """Placeholder: uvicorn launch is blocking, skipped here."""
    pass


@pytest.mark.skip(
    reason=(
        "NOT TESTABLE without a browser: React rendering, pan/zoom, force-graph "
        "animation, and click handlers require a headless browser (Playwright/Cypress). "
        "Out of scope for Python pytest."
    )
)
def test_browser_graph_rendering():
    """Placeholder: browser rendering requires Playwright/Cypress, skipped here."""
    pass
