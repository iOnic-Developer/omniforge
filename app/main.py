"""OmniForge — FastAPI app: dashboard, tool CRUD, and the MCP endpoint.

Endpoints:
  GET  /                 -> web dashboard (tool list + editor)
  POST /api/tools        -> create/update a tool
  PUT    /api/tools/{name} -> update a tool
  DELETE /api/tools/{name} -> delete a tool
  POST /api/tools/{name}/toggle -> enable/disable
  GET  /api/tools        -> JSON list of tools (dashboard API)
  POST /api/tools/{name}/run -> test a tool (runs it, returns output)
  POST /mcp              -> JSON-RPC MCP (tools/list, tools/call)
  GET  /mcp              -> 405 (server push is not offered)
"""

from __future__ import annotations

import os
import json
import hmac
from typing import Annotated
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from pathlib import Path

from app.database import DuplicateToolError, ToolConflictError, db
from app.mcp_server import MCPHandler, BUILTIN_TOOLS
from app.connections import ConnectionStore
from app.scheduling import Scheduler, list_folders
from app.release import VERSION, release_info
from app.runner import run_tool
from app.tool_authoring import ToolIn, save_tool, validate_arguments, validate_name
from pydantic import BaseModel, ConfigDict, Field

API_KEY = os.environ.get("OMNIFORGE_API_KEY", "")
handler = MCPHandler()
connections = ConnectionStore(db)
scheduler = Scheduler(db)
SUPPORTED_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()



app = FastAPI(title="OmniForge", version=VERSION, lifespan=lifespan)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_DIR = Path(__file__).parent / "static"
# Explicit public assets only; do not expose a directory or runtime data.
PUBLIC_ASSETS = {
    "product.css": "text/css", "mark.svg": "image/svg+xml",
    "favicon.svg": "image/svg+xml", "favicon-32.png": "image/png",
    "apple-touch-icon.png": "image/png", "icon-192.png": "image/png",
    "icon-512.png": "image/png", "icon-maskable-512.png": "image/png",
    "manifest.webmanifest": "application/manifest+json",
    "offline.html": "text/html", "fonts/manrope.ttf": "font/ttf",
    "fonts/jetbrains-mono.ttf": "font/ttf", "fonts/museomoderno-latin.woff2": "font/woff2",
    "fonts/OFL-Manrope.txt": "text/plain", "fonts/OFL-JetBrainsMono.txt": "text/plain",
}


@app.get("/assets/{asset:path}")
async def public_asset(asset: str):
    if asset not in PUBLIC_ASSETS:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(STATIC_DIR / asset, media_type=PUBLIC_ASSETS[asset],
                        headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})


@app.get("/sw.js")
async def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/",
                                 "X-Content-Type-Options": "nosniff"})


def _validate_name(name: str) -> str:
    try:
        return validate_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    with open(os.path.join(TEMPLATES_DIR, "dashboard.html")) as fh:
        return HTMLResponse(fh.read(), headers={"Cache-Control": "no-store"})


@app.get("/api/config")
async def api_config():
    """Public connection metadata only: never return credentials."""
    return {
        "mcp_path": "/mcp",
        "transport": "Streamable HTTP (JSON responses; no SSE stream)",
        "auth_enabled": bool(API_KEY),
        "auth_header": "Authorization: Bearer <YOUR_API_KEY>",
        "auth_configuration": "Set OMNIFORGE_API_KEY in the server environment and recreate the container.",
        "dashboard_auth_enabled": False,
        "connection_tracking": True,
        "connection_management_auth_enabled": bool(API_KEY),
        "connections_path": "/api/connections",
        "methods": ["initialize", "tools/list", "tools/call", "ping"],
        "warnings": [
            "Dashboard and tool-management API are unauthenticated. Keep this server on a trusted network.",
            "Scripts share the application container; only run trusted code.",
            "OAuth and server-pushed notifications are not implemented. Connections using the shared server key have session-scoped tool choices; use a named connection for persistent choices.",
        ],
    }


@app.get("/api/version")
async def api_version():
    return release_info()


@app.get("/api/tools")
async def api_list_tools():
    return {"tools": db.get_tool_list()}


@app.post("/api/tools")
async def api_create_tool(body: ToolIn):
    try:
        tool = save_tool(body)
    except DuplicateToolError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "id": tool.id, "revision": tool.revision}


@app.put("/api/tools/{name}")
async def api_update_tool(name: str, body: ToolIn,
                          expected_revision: Annotated[str | None, Header(alias="If-Match")] = None):
    _validate_name(name)
    existing = db.get_tool(name, fresh=True)
    if existing is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    try:
        tool = save_tool(body, existing, expected_revision=expected_revision)
    except ToolConflictError as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except DuplicateToolError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "revision": tool.revision}


@app.delete("/api/tools/{name}")
async def api_delete_tool(name: str,
                          expected_revision: Annotated[str | None, Header(alias="If-Match")] = None):
    _validate_name(name)
    try:
        deleted = db.delete(name, expected_revision=expected_revision)
    except ToolConflictError as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"ok": True}


@app.post("/api/tools/{name}/toggle")
async def api_toggle_tool(name: str,
                          expected_revision: Annotated[str | None, Header(alias="If-Match")] = None):
    _validate_name(name)
    try:
        tool = db.toggle(name, expected_revision=expected_revision)
    except ToolConflictError as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"ok": True, "is_active": tool.is_active, "revision": tool.revision}


class RunIn(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    arguments: dict = Field(default_factory=dict)


@app.post("/api/tools/{name}/run")
async def api_run_tool(name: str, body: RunIn | None = None,
                       expected_revision: Annotated[str | None, Header(alias="If-Match")] = None):
    _validate_name(name)
    tool = db.get_tool(name, fresh=True)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    if expected_revision is not None and tool.revision != expected_revision:
        raise HTTPException(status_code=412, detail="Tool changed in another tab or client; reload before testing it")
    arguments = body.arguments if body is not None else {}
    try:
        validate_arguments(arguments, json.loads(tool.json_schema_json or "{}"))
    except (ValueError, RecursionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await run_in_threadpool(run_tool, tool, arguments)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "duration_ms": result.duration_ms,
    }


# --- Scheduled tool configuration and connection management -----------------


@app.get("/api/folders")
async def api_folders(path: str | None = None):
    try:
        return await run_in_threadpool(list_folders, path)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tools/{name}/schedule")
async def api_schedule_status(name: str):
    _validate_name(name)
    tool = db.get_tool(name, fresh=True)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"status": scheduler.get_status(tool.id)}


def _bearer(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    return auth[7:].strip() if auth.lower().startswith("bearer ") else auth.strip()


def _require_management_key(request: Request):
    if API_KEY and not hmac.compare_digest(_bearer(request), API_KEY):
        raise HTTPException(status_code=401, detail="Server management key required",
                            headers={"WWW-Authenticate": "Bearer"})


class ConnectionIn(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    client_name: str = Field(min_length=1, max_length=120)


class ConnectionPolicyIn(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    disabled_tools: list[str] = Field(default_factory=list, max_length=10000)


@app.get("/api/connections")
async def api_connections(request: Request):
    _require_management_key(request)
    return connections.list_connections(BUILTIN_TOOLS)


@app.post("/api/connections")
async def api_create_connection(body: ConnectionIn, request: Request):
    _require_management_key(request)
    if not body.client_name.strip():
        raise HTTPException(status_code=422, detail="Connection name must not be blank")
    connection, token = connections.create_named(body.client_name.strip(), BUILTIN_TOOLS)
    return JSONResponse({"ok": True, "connection": connection, "token": token,
                         "auth_header": "Authorization: Bearer " + token},
                        headers={"Cache-Control": "no-store"})


@app.put("/api/connections/{connection_id}")
async def api_update_connection(connection_id: str, body: ConnectionPolicyIn, request: Request):
    _require_management_key(request)
    try:
        connection = connections.update_policy(connection_id, body.disabled_tools, BUILTIN_TOOLS)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found or disconnected")
    return {"ok": True, "connection": connection}


@app.delete("/api/connections/{connection_id}")
async def api_disconnect_connection(connection_id: str, request: Request):
    _require_management_key(request)
    if not connections.disconnect(connection_id):
        raise HTTPException(status_code=404, detail="Connection not found or already disconnected")
    return {"ok": True}


# --- MCP Streamable HTTP with JSON responses and scoped connections ----------


def _check_origin(request: Request):
    origin = request.headers.get("origin")
    if not origin:
        return
    configured = {o.strip().rstrip('/') for o in os.environ.get("OMNIFORGE_ALLOWED_ORIGINS", "").split(',') if o.strip()}
    expected = str(request.base_url).rstrip('/')
    if origin.rstrip('/') not in configured | {expected}:
        raise HTTPException(status_code=403, detail="Origin not allowed")


def _principal(request: Request) -> tuple[str, str | None]:
    token = _bearer(request)
    # A connection credential must never fall through to anonymous access,
    # including when the server has no shared management key configured.
    if token.startswith('ofc_'):
        connection_id = connections.authenticate_named(token)
        if connection_id is None:
            raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Bearer"})
        return token, connection_id
    if API_KEY:
        if not token or not hmac.compare_digest(token, API_KEY):
            raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Bearer"})
        return token, None
    if token:
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Bearer"})
    return 'anonymous', None


def _session(request: Request, principal: str) -> str:
    token = request.headers.get('mcp-session-id', '')
    if not token:
        raise HTTPException(status_code=400, detail="Initialize first and include Mcp-Session-Id")
    connection_id = connections.resolve_session(token, principal)
    if connection_id is None:
        raise HTTPException(status_code=404, detail="Session ended; initialize a new connection")
    return connection_id


@app.post("/mcp")
async def mcp_endpoint(payload: dict, request: Request):
    _check_origin(request)
    principal, named_id = _principal(request)
    protocol = request.headers.get('mcp-protocol-version')
    if protocol and protocol not in SUPPORTED_PROTOCOLS:
        raise HTTPException(status_code=400, detail="Unsupported MCP protocol version")
    if payload.get('jsonrpc') != '2.0':
        return JSONResponse({"jsonrpc": "2.0", "id": payload.get('id'), "error": {
            "code": -32600, "message": "Invalid JSON-RPC request"}}, status_code=400)
    if payload.get('method') == 'initialize':
        if 'id' not in payload or not isinstance(payload.get('params', {}), dict):
            raise HTTPException(status_code=400, detail="Invalid initialize request")
        params = payload.get('params', {})
        client_info = params.get('clientInfo', {})
        if not isinstance(client_info, dict):
            raise HTTPException(status_code=400, detail="clientInfo must be an object")
        try:
            session_token, connection_id = connections.start_session(principal, client_info, named_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        result = await _handle_rpc(payload, connection_id)
        return JSONResponse(result, headers={'Mcp-Session-Id': session_token, 'Cache-Control': 'no-store'})
    connection_id = _session(request, principal)
    if 'id' not in payload or 'method' not in payload:
        return Response(status_code=202)
    return JSONResponse(await _handle_rpc(payload, connection_id), headers={'Cache-Control': 'no-store'})


@app.get("/mcp")
async def mcp_sse(request: Request):
    _check_origin(request)
    principal, _ = _principal(request)
    if request.headers.get('mcp-session-id'):
        _session(request, principal)
    return Response(status_code=405, headers={'Allow': 'POST, DELETE'})


@app.delete("/mcp")
async def mcp_disconnect(request: Request):
    _check_origin(request)
    principal, _ = _principal(request)
    _session(request, principal)
    connections.end_session(request.headers['mcp-session-id'], principal)
    return Response(status_code=204)


def _check_api_key(request: Request) -> bool:
    """Compatibility helper for callers checking the shared server credential."""
    return not API_KEY or hmac.compare_digest(_bearer(request), API_KEY)


async def _handle_rpc(payload: dict, connection_id: str | None = None) -> dict:
    method = payload.get("method")
    params = payload.get("params", {})
    req_id = payload.get("id")
    if not isinstance(params, dict):
        return {"jsonrpc": "2.0", "id": req_id, "error": {
            "code": -32602, "message": "params must be a JSON object"}}
    try:
        disabled = connections.disabled_keys(connection_id) if connection_id else set()
    except ValueError:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": "Connection disconnected"}}
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": handler.initialize(
            params.get("protocolVersion", ""), params.get("capabilities", {}))}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": handler.list_tools(disabled)}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        result = await run_in_threadpool(handler.call_tool, name, arguments, disabled)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
