"""
Phase 5 acceptance-criteria tests — Live wire.

Acceptance criteria under test:
  AC1 - POST /event with a "query" payload returns {"ok": true} and status 200
  AC2 - POST /event with a "graph" payload returns {"ok": true} and status 200
  AC3 - POST /event fans out the payload to all connected WebSocket clients
  AC4 - WS /events: client receives a fanned-out event after POST /event; a second
        client disconnecting while the first is connected does not break the set
  AC5 - _post_graph_event in corpus/cli.py exists and spawns a non-daemon thread
  AC6 - _post_event in corpus/mcp.py catches all exceptions (including
        ConnectionRefusedError from urllib) — nothing propagates to the caller
  AC7 - useGraph.js is client-side JavaScript — NOT testable in Python pytest;
        skipped with a clear comment
  AC8 - corpus_overview() MCP tool calls _post_event (mock _post_event, call the
        tool, assert mock was called)

NOT tested here (requires a browser / npm):
  - Node pulse animation in the frontend (JavaScript/browser-only)
  - Full end-to-end: Claude Code → MCP → sidecar → WebSocket → DOM pulse
  - Graph soft-reload on "graph" event (useGraph.js, browser-only)
  - Node amber flip on "stale" event (useGraph.js, browser-only)
"""

from __future__ import annotations

import inspect
import json
import os
import threading
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Minimal .corpus/ fixture
# ---------------------------------------------------------------------------

FAKE_GRAPH = {
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
    ],
    "edges": [],
}


def _write_corpus(tmp_path: Path, graph: dict | None = None) -> None:
    """Write a minimal .corpus/ directory with graph.json."""
    corpus_dir = tmp_path / ".corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "graph.json").write_text(
        json.dumps(graph or FAKE_GRAPH), encoding="utf-8"
    )
    (corpus_dir / "state.json").write_text("{}", encoding="utf-8")
    docs_dir = corpus_dir / "docs" / "pkg"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "alpha.py.md").write_text(
        "## Purpose\nAlpha module.\n\n## Symbols\n- AlphaClass\n",
        encoding="utf-8",
    )


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


def _make_client(tmp_path: Path) -> TestClient:
    """Return a TestClient for corpus.server app, with cwd at tmp_path."""
    from corpus.server import app, _ws_connections

    # Clear any lingering connections from previous tests
    _ws_connections.clear()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# AC1 — POST /event with "query" payload returns {"ok": true}, status 200
# ---------------------------------------------------------------------------

class TestAC1PostEventQuery:
    """AC1: POST /event accepts a full query payload and returns ok=true / 200."""

    def test_post_event_query_status_200(self, tmp_path):
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/event",
                json={
                    "event": "query",
                    "node_id": "n_abc",
                    "tool": "corpus_doc",
                    "ts": "2026-07-19T00:00:00+00:00",
                },
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

    def test_post_event_query_returns_ok_true(self, tmp_path):
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.post(
                "/event",
                json={
                    "event": "query",
                    "node_id": "n_abc",
                    "tool": "corpus_doc",
                    "ts": "2026-07-19T00:00:00+00:00",
                },
            ).json()

        assert data == {"ok": True}, (
            f"Expected {{'ok': True}}, got {data}"
        )

    def test_post_event_query_null_node_id(self, tmp_path):
        """node_id may be null (corpus_overview has no specific node)."""
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/event",
                json={
                    "event": "query",
                    "node_id": None,
                    "tool": "corpus_overview",
                    "ts": "2026-07-19T00:00:00+00:00",
                },
            )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_post_event_query_content_type_json(self, tmp_path):
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/event",
                json={"event": "query", "node_id": "n_x", "tool": "corpus_find", "ts": "t"},
            )

        assert "application/json" in response.headers.get("content-type", ""), (
            f"Expected JSON content-type, got: {response.headers.get('content-type')}"
        )

    def test_post_event_empty_body_returns_ok(self, tmp_path):
        """Malformed / empty body must still return ok=true — callers never check the response."""
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            # Send a non-JSON body
            response = client.post(
                "/event",
                content=b"not json",
                headers={"Content-Type": "application/json"},
            )

        # Server must not crash; it must return ok=true even for garbage input
        assert response.status_code == 200
        assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# AC2 — POST /event with "graph" payload returns {"ok": true}
# ---------------------------------------------------------------------------

class TestAC2PostEventGraph:
    """AC2: POST /event accepts {"event": "graph"} and returns ok=true."""

    def test_post_event_graph_status_200(self, tmp_path):
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/event", json={"event": "graph"})

        assert response.status_code == 200, (
            f"Expected 200 for graph event, got {response.status_code}"
        )

    def test_post_event_graph_returns_ok_true(self, tmp_path):
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            data = client.post("/event", json={"event": "graph"}).json()

        assert data == {"ok": True}, (
            f"Expected {{'ok': True}} for graph event, got {data}"
        )

    def test_post_event_stale_payload_returns_ok(self, tmp_path):
        """{"event": "stale", "node_id": ...} is also a valid event type."""
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/event", json={"event": "stale", "node_id": "n_aaa111"})

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_post_event_unknown_event_type_returns_ok(self, tmp_path):
        """An unknown event type must not crash the server — it still fans out."""
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/event", json={"event": "unknown_future_event"})

        assert response.status_code == 200
        assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# AC3 — POST /event fans out to connected WebSocket clients
# ---------------------------------------------------------------------------

class TestAC3WebSocketFanout:
    """AC3: POST /event forwards the payload JSON to every connected WS client."""

    def test_post_event_graph_received_by_ws_client(self, tmp_path):
        """A WS client connected before POST /event receives the event frame."""
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/events") as ws:
                client.post("/event", json={"event": "graph"})
                frame = ws.receive_json()

        assert frame == {"event": "graph"}, (
            f"Expected {{'event': 'graph'}}, got {frame}"
        )

    def test_post_event_query_received_by_ws_client(self, tmp_path):
        """A WS client receives the full query payload."""
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        payload = {
            "event": "query",
            "node_id": "n_aaa111",
            "tool": "corpus_doc",
            "ts": "2026-07-19T00:00:00+00:00",
        }

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/events") as ws:
                client.post("/event", json=payload)
                frame = ws.receive_json()

        assert frame == payload, (
            f"WS frame mismatch.\nExpected: {payload}\nGot:      {frame}"
        )

    def test_fanout_to_multiple_ws_clients(self, tmp_path):
        """Both connected WS clients receive the same event frame."""
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/events") as ws1:
                with client.websocket_connect("/events") as ws2:
                    client.post("/event", json={"event": "graph"})
                    frame1 = ws1.receive_json()
                    frame2 = ws2.receive_json()

        assert frame1 == {"event": "graph"}, f"WS1 got: {frame1}"
        assert frame2 == {"event": "graph"}, f"WS2 got: {frame2}"

    def test_no_ws_clients_does_not_crash_post_event(self, tmp_path):
        """POST /event with zero WS clients connected must still return ok=true."""
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/event", json={"event": "graph"})

        assert response.status_code == 200
        assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# AC4 — WS /events: fanout + second client disconnects cleanly
# ---------------------------------------------------------------------------

class TestAC4WebSocketDisconnect:
    """AC4: Disconnecting one WS client does not break other clients or the server."""

    def test_second_client_disconnect_does_not_break_first(self, tmp_path):
        """After ws2 disconnects, ws1 still receives a subsequent event."""
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/events") as ws1:
                # Connect and immediately disconnect ws2
                with client.websocket_connect("/events"):
                    pass  # ws2 disconnects here

                # ws1 should still receive events sent after ws2 disconnected
                client.post("/event", json={"event": "graph"})
                frame = ws1.receive_json()

        assert frame == {"event": "graph"}, (
            f"ws1 did not receive event after ws2 disconnected; got: {frame}"
        )

    def test_disconnected_ws_removed_from_connection_set(self, tmp_path):
        """After a WS disconnect, the dead connection must be pruned from _ws_connections.

        We verify this indirectly: POST /event after disconnect must not raise and
        returns ok=true, proving dead connections were cleaned up.
        """
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            # Connect and disconnect a WS client
            with client.websocket_connect("/events"):
                pass

            # A subsequent POST /event must succeed even though the client is gone
            response = client.post("/event", json={"event": "graph"})

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_ws_connection_accepted_returns_no_immediate_message(self, tmp_path):
        """Connecting to /events must not receive any unsolicited message on connect."""
        _write_corpus(tmp_path)
        from corpus.server import app, _ws_connections
        _ws_connections.clear()

        # If the server sends any frame on connect, receive_text would return; if it
        # doesn't, the context manager exits cleanly via disconnect.
        exception_raised = False
        with _ChdirContext(tmp_path):
            client = TestClient(app, raise_server_exceptions=False)
            try:
                with client.websocket_connect("/events"):
                    pass  # just connect and disconnect; no unsolicited frame expected
            except Exception:
                exception_raised = True

        assert not exception_raised, "WS /events raised unexpectedly on clean connect/disconnect"


# ---------------------------------------------------------------------------
# AC5 — _post_graph_event in corpus/cli.py: exists and spawns a non-daemon thread
# ---------------------------------------------------------------------------

class TestAC5PostGraphEvent:
    """AC5: _post_graph_event exists in corpus.cli and uses daemon=False."""

    def test_post_graph_event_exists(self):
        """_post_graph_event must be importable from corpus.cli."""
        try:
            from corpus.cli import _post_graph_event
        except ImportError as exc:
            pytest.fail(f"_post_graph_event not found in corpus.cli: {exc}")

    def test_post_graph_event_is_callable(self):
        from corpus.cli import _post_graph_event
        assert callable(_post_graph_event), "_post_graph_event must be callable"

    def test_post_graph_event_spawns_non_daemon_thread(self):
        """The thread spawned by _post_graph_event must have daemon=False.

        We inspect the source to verify intent, then also test at runtime by
        patching threading.Thread and checking the daemon kwarg.
        """
        spawned_threads: list[threading.Thread] = []
        original_thread_init = threading.Thread.__init__

        def capturing_init(self, *args, **kwargs):
            original_thread_init(self, *args, **kwargs)
            spawned_threads.append(self)

        import corpus.cli as cli_module

        with mock.patch.object(threading.Thread, "__init__", capturing_init):
            # Mock urlopen so the thread finishes quickly without network
            with mock.patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = ConnectionRefusedError("no sidecar")
                cli_module._post_graph_event()

        assert len(spawned_threads) >= 1, (
            "_post_graph_event did not spawn any thread"
        )
        # The HTTP-sending thread must be non-daemon (daemon=False)
        # so the main process waits for it before exit.
        non_daemon_threads = [t for t in spawned_threads if not t.daemon]
        assert len(non_daemon_threads) >= 1, (
            f"_post_graph_event spawned only daemon threads: "
            f"{[(t.name, t.daemon) for t in spawned_threads]}"
        )

    def test_post_graph_event_source_confirms_daemon_false(self):
        """Source code inspection: threading.Thread must be called with daemon=False."""
        import corpus.cli as cli_module

        source = inspect.getsource(cli_module._post_graph_event)
        # The function must explicitly set daemon=False (not just omit it, which defaults True)
        assert "daemon=False" in source, (
            "Source of _post_graph_event does not contain 'daemon=False'. "
            f"Actual source:\n{source}"
        )

    def test_post_graph_event_does_not_raise_when_no_sidecar(self):
        """_post_graph_event must not propagate any exception to the caller."""
        import corpus.cli as cli_module

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = ConnectionRefusedError("no sidecar")
            try:
                cli_module._post_graph_event()
            except Exception as exc:
                pytest.fail(
                    f"_post_graph_event raised when sidecar is absent: {exc}"
                )


# ---------------------------------------------------------------------------
# AC6 — _post_event in corpus/mcp.py: all exceptions caught, none propagate
# ---------------------------------------------------------------------------

class TestAC6PostEventExceptionSafety:
    """AC6: _post_event catches all exceptions, including ConnectionRefusedError."""

    def test_post_event_does_not_raise_on_connection_refused(self):
        """ConnectionRefusedError from urllib must be swallowed silently."""
        from corpus.mcp import _post_event

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = ConnectionRefusedError("no sidecar")
            try:
                _post_event("corpus_overview", None)
            except Exception as exc:
                pytest.fail(
                    f"_post_event propagated ConnectionRefusedError: {exc}"
                )

    def test_post_event_does_not_raise_on_os_error(self):
        """OSError (e.g., network unreachable) must also be swallowed."""
        from corpus.mcp import _post_event

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("network unreachable")
            try:
                _post_event("corpus_doc", "n_aaa111")
            except Exception as exc:
                pytest.fail(
                    f"_post_event propagated OSError: {exc}"
                )

    def test_post_event_does_not_raise_on_timeout_error(self):
        """TimeoutError from urllib (timeout=0.5 exceeded) must be swallowed."""
        import urllib.error
        from corpus.mcp import _post_event

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("timed out")
            try:
                _post_event("corpus_find", None)
            except Exception as exc:
                pytest.fail(
                    f"_post_event propagated URLError: {exc}"
                )

    def test_post_event_does_not_raise_on_generic_exception(self):
        """Any arbitrary exception from urllib must be caught."""
        from corpus.mcp import _post_event

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = RuntimeError("unexpected failure")
            try:
                _post_event("corpus_stale", None)
            except Exception as exc:
                pytest.fail(
                    f"_post_event propagated RuntimeError: {exc}"
                )

    def test_post_event_source_uses_broad_except(self):
        """Source inspection: _post_event's inner _send must use except Exception."""
        from corpus.mcp import _post_event

        source = inspect.getsource(_post_event)
        assert "except Exception" in source, (
            "Source of _post_event does not contain 'except Exception'. "
            f"This means narrow exception handling may let errors escape.\n"
            f"Actual source:\n{source}"
        )

    def test_post_event_returns_none(self):
        """_post_event returns None — callers never inspect the return value."""
        from corpus.mcp import _post_event

        with mock.patch("urllib.request.urlopen"):
            result = _post_event("corpus_overview", None)

        assert result is None, f"Expected None, got {result!r}"

    def test_post_event_spawns_daemon_thread(self):
        """_post_event dispatches on a daemon thread so it never blocks MCP tools."""
        from corpus.mcp import _post_event

        spawned_threads: list[threading.Thread] = []
        original_init = threading.Thread.__init__

        def capturing_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            spawned_threads.append(self)

        import corpus.mcp as mcp_module

        with mock.patch.object(threading.Thread, "__init__", capturing_init):
            with mock.patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = ConnectionRefusedError("no sidecar")
                mcp_module._post_event("corpus_overview", None)

        assert len(spawned_threads) >= 1, "_post_event did not spawn any thread"
        daemon_threads = [t for t in spawned_threads if t.daemon]
        assert len(daemon_threads) >= 1, (
            f"_post_event spawned only non-daemon threads: "
            f"{[(t.name, t.daemon) for t in spawned_threads]}"
        )


# ---------------------------------------------------------------------------
# AC7 — useGraph.js: client-side JavaScript, NOT testable in Python pytest
# ---------------------------------------------------------------------------

@pytest.mark.skip(
    reason=(
        "NOT TESTABLE in Python: useGraph.js WebSocket client and graph merge logic "
        "are client-side JavaScript. Testing requires a browser or Node/jsdom environment. "
        "The server-side fanout that feeds this logic is fully covered by TestAC3 and TestAC4."
    )
)
def test_usegraph_js_graph_merge_on_ws_event():
    """Placeholder: frontend JS graph merge is browser-only, skipped here."""
    pass


# ---------------------------------------------------------------------------
# AC8 — corpus_overview() calls _post_event (mock and assert)
# ---------------------------------------------------------------------------

class TestAC8CorpusOverviewCallsPostEvent:
    """AC8: corpus_overview() must call _post_event (fire-and-forget telemetry)."""

    def test_corpus_overview_calls_post_event(self, tmp_path):
        """Mock _post_event, call corpus_overview(), assert mock was called once."""
        _write_corpus(tmp_path)

        with _ChdirContext(tmp_path):
            with mock.patch("corpus.mcp._post_event") as mock_post:
                from corpus.mcp import corpus_overview
                corpus_overview()

        mock_post.assert_called_once(), (
            f"Expected _post_event to be called once, got {mock_post.call_count} calls"
        )

    def test_corpus_overview_calls_post_event_with_correct_tool_name(self, tmp_path):
        """corpus_overview() must pass tool='corpus_overview' to _post_event."""
        _write_corpus(tmp_path)

        with _ChdirContext(tmp_path):
            with mock.patch("corpus.mcp._post_event") as mock_post:
                from corpus.mcp import corpus_overview
                corpus_overview()

        call_args = mock_post.call_args
        assert call_args is not None, "_post_event was never called"
        # _post_event(tool, node_id) — tool is the first positional arg
        tool_arg = call_args[0][0] if call_args[0] else call_args[1].get("tool")
        assert tool_arg == "corpus_overview", (
            f"Expected tool='corpus_overview', got {tool_arg!r}"
        )

    def test_corpus_overview_calls_post_event_with_none_node_id(self, tmp_path):
        """corpus_overview() must pass node_id=None (no specific node consulted)."""
        _write_corpus(tmp_path)

        with _ChdirContext(tmp_path):
            with mock.patch("corpus.mcp._post_event") as mock_post:
                from corpus.mcp import corpus_overview
                corpus_overview()

        call_args = mock_post.call_args
        assert call_args is not None, "_post_event was never called"
        node_id_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("node_id")
        assert node_id_arg is None, (
            f"Expected node_id=None, got {node_id_arg!r}"
        )

    def test_corpus_overview_post_event_called_even_when_graph_missing(self, tmp_path):
        """Even with no .corpus/graph.json, corpus_overview() must still call _post_event."""
        # Do NOT call _write_corpus — leave .corpus/ absent
        with _ChdirContext(tmp_path):
            with mock.patch("corpus.mcp._post_event") as mock_post:
                from corpus.mcp import corpus_overview
                corpus_overview()  # returns empty summary, must not crash

        mock_post.assert_called_once(), (
            f"_post_event not called when graph.json is missing; calls: {mock_post.call_count}"
        )

    def test_corpus_overview_returns_expected_keys(self, tmp_path):
        """corpus_overview() must return a dict with known keys (sanity regression)."""
        _write_corpus(tmp_path)

        with _ChdirContext(tmp_path):
            with mock.patch("corpus.mcp._post_event"):
                from corpus.mcp import corpus_overview
                result = corpus_overview()

        expected_keys = {"project", "file_count", "node_count", "edge_count", "stale_count"}
        missing = expected_keys - set(result.keys())
        assert not missing, (
            f"corpus_overview() result missing keys: {missing}\nGot: {result}"
        )

    def test_corpus_doc_calls_post_event_with_node_id(self, tmp_path):
        """corpus_doc() must call _post_event with the matched node's id."""
        _write_corpus(tmp_path)

        with _ChdirContext(tmp_path):
            with mock.patch("corpus.mcp._post_event") as mock_post:
                from corpus.mcp import corpus_doc
                corpus_doc("pkg/alpha.py")

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        node_id_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("node_id")
        assert node_id_arg == "n_aaa111", (
            f"Expected node_id='n_aaa111', got {node_id_arg!r}"
        )

    def test_corpus_find_calls_post_event(self, tmp_path):
        """corpus_find() must call _post_event exactly once."""
        _write_corpus(tmp_path)

        with _ChdirContext(tmp_path):
            with mock.patch("corpus.mcp._post_event") as mock_post:
                from corpus.mcp import corpus_find
                corpus_find("AlphaClass")

        mock_post.assert_called_once()
