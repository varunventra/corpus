"""FastAPI sidecar server for the Corpus graph viewer.

Routes:
  GET  /graph           — return .corpus/graph.json as JSON (503 if missing)
  GET  /doc?path=<p>    — return .corpus/docs/<p>.md as plain text (404 if missing)
  WS   /events          — accept websocket, hold open, never send (Phase 5 stub)
  GET  /                — serve frontend/dist/index.html
  GET  /{path}          — serve frontend/dist/<path> (SPA fallback → index.html)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Corpus sidecar", docs_url=None, redoc_url=None)

# Active WebSocket connections — mutated only inside async coroutines (single event loop)
_ws_connections: set[WebSocket] = set()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _corpus_dir() -> Path:
    """Resolve .corpus/ from the process's cwd (set at launch time)."""
    return Path.cwd() / ".corpus"


def _dist_dir() -> Path:
    """Resolve frontend/dist/ relative to this file's project root."""
    return Path(__file__).parent.parent / "frontend" / "dist"


# ---------------------------------------------------------------------------
# API routes — registered before the static-file catch-all
# ---------------------------------------------------------------------------

@app.get("/graph")
async def get_graph() -> Response:
    graph_path = _corpus_dir() / "graph.json"
    if not graph_path.exists():
        return JSONResponse(
            status_code=503,
            content={"error": "graph.json not found — run corpus update first"},
        )
    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})

    # Normalize edge keys: graph.json stores "from"/"to"; frontend expects "source"/"target"
    normalized_edges = []
    for edge in data.get("edges", []):
        normalized_edges.append({
            "source": edge.get("source") or edge.get("from"),
            "target": edge.get("target") or edge.get("to"),
            "type": edge.get("type"),
        })
    data["edges"] = normalized_edges

    return JSONResponse(content=data)


@app.get("/doc")
async def get_doc(path: str = Query(..., description="Repo-relative file path")) -> Response:
    doc_path = _corpus_dir() / "docs" / (path + ".md")
    docs_root = (_corpus_dir() / "docs").resolve()
    if not doc_path.resolve().is_relative_to(docs_root):
        return JSONResponse(status_code=400, content={"error": "Invalid path"})
    if not doc_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "No doc for this path"},
        )
    try:
        content = doc_path.read_text(encoding="utf-8")
    except OSError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return PlainTextResponse(content=content, media_type="text/plain; charset=utf-8")


@app.post("/event")
async def post_event(request: Request) -> Response:
    """Accept an event from MCP tools or corpus update and fan it out to all WS clients.

    Accepted payloads:
      {"event": "query",  "node_id": str|null, "tool": str, "ts": str}
      {"event": "graph"}
      {"event": "stale",  "node_id": str}

    Always returns {"ok": true} — callers never check the response.
    """
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse(content={"ok": True})

    raw = json.dumps(payload)
    dead: set[WebSocket] = set()
    for ws in list(_ws_connections):
        try:
            await ws.send_text(raw)
        except Exception:  # noqa: BLE001 — client disconnected or errored
            dead.add(ws)
    _ws_connections.difference_update(dead)

    return JSONResponse(content={"ok": True})


@app.websocket("/events")
async def events_ws(websocket: WebSocket) -> None:
    """Real-time event fan-out to browser clients."""
    await websocket.accept()
    _ws_connections.add(websocket)
    try:
        while True:
            # Drain any client messages (ping/pong or close frames); we don't act on them
            await websocket.receive_text()
    except Exception:  # noqa: BLE001 — disconnect or close frame exits cleanly
        pass
    finally:
        _ws_connections.discard(websocket)


# ---------------------------------------------------------------------------
# Static file serving (SPA fallback)
# Must come LAST so API routes above take priority.
# ---------------------------------------------------------------------------

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str) -> Response:
    dist = _dist_dir()
    if not dist.exists():
        return JSONResponse(
            status_code=500,
            content={"error": "Frontend not built. Run: cd frontend && npm run build"},
        )

    # Try to serve the exact file first
    target = dist / full_path if full_path else dist / "index.html"
    if full_path and not target.resolve().is_relative_to(dist.resolve()):
        return JSONResponse(status_code=400, content={"error": "Invalid path"})
    if target.is_file():
        return FileResponse(str(target))

    # SPA fallback → index.html
    index = dist / "index.html"
    if index.is_file():
        return FileResponse(str(index))

    return JSONResponse(
        status_code=500,
        content={"error": "Frontend not built. Run: cd frontend && npm run build"},
    )
