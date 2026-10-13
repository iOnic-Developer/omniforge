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
  GET  /mcp              -> SSE stream for MCP
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from app.database import DuplicateToolError, db
from app.mcp_server import MCPHandler
from app.runner import run_tool
from app.tool_authoring import ToolIn, save_tool, validate_name

API_KEY = os.environ.get("OMNIFORGE_API_KEY", "")
handler = MCPHandler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the runtime image exists (build if missing) — handled by compose.
    yield


app = FastAPI(title="OmniForge", version="0.1.0", lifespan=lifespan)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _validate_name(name: str) -> str:
    try:
        return validate_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    with open(os.path.join(TEMPLATES_DIR, "dashboard.html")) as fh:
        return fh.read()


@app.get("/api/config")
async def api_config():
    """Public connection metadata only: never return credentials."""
    return {
        "mcp_path": "/mcp",
        "transport": "HTTP JSON-RPC POST (limited MCP implementation)",
        "auth_enabled": bool(API_KEY),
        "auth_header": "Authorization: Bearer <YOUR_API_KEY>",
        "auth_configuration": "Set OMNIFORGE_API_KEY in the server environment and recreate the container.",
        "dashboard_auth_enabled": False,
        "connection_tracking": False,
        "methods": ["initialize", "tools/list", "tools/call", "ping"],
        "warnings": [
            "Dashboard and tool-management API are unauthenticated. Keep this server on a trusted network.",
            "Scripts share the application container; only run trusted code.",
            "OAuth, client/session tracking and full Streamable HTTP transport are not implemented.",
        ],
    }


@app.get("/api/tools")
async def api_list_tools():
    return {"tools": db.get_tool_list()}


@app.post("/api/tools")
async def api_create_tool(body: ToolIn):
    try:
        tool = save_tool(body)
    except DuplicateToolError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "id": tool.id}


@app.put("/api/tools/{name}")
async def api_update_tool(name: str, body: ToolIn):
    _validate_name(name)
    existing = db.get_tool(name)
    if existing is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    try:
        save_tool(body, existing)
    except DuplicateToolError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@app.delete("/api/tools/{name}")
async def api_delete_tool(name: str):
    _validate_name(name)
    if not db.delete(name):
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"ok": True}


@app.post("/api/tools/{name}/toggle")
async def api_toggle_tool(name: str):
    _validate_name(name)
    if db.get_tool(name) is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    existing = db.get_tool(name)
    db.activate(name, not existing.is_active)
    return {"ok": True}


@app.post("/api/tools/{name}/run")
async def api_run_tool(name: str):
    _validate_name(name)
    tool = db.get_tool(name)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    result = run_tool(tool)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "duration_ms": result.duration_ms,
    }


# --- MCP endpoint -----------------------------------------------------------


@app.post("/mcp")
async def mcp_endpoint(payload: dict, request: Request):
    """JSON-RPC 2.0 endpoint for MCP clients."""
    if not _check_api_key(request):
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": "Unauthorized"}},
            status_code=401,
        )
    return JSONResponse(await _handle_rpc(payload))


@app.get("/mcp")
async def mcp_sse():
    async def stream():
        yield "event: initial-connections\n"
        yield f"data: {{\"protocolVersion\": \"2024-11-05\"}}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")


def _check_api_key(request: Request) -> bool:
    """Validate the Bearer API key from the HTTP Authorization header."""
    if not API_KEY:
        return True
    auth = request.headers.get("Authorization")
    if not auth:
        return False
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else auth
    return token == API_KEY


async def _handle_rpc(payload: dict) -> dict:
    method = payload.get("method")
    params = payload.get("params", {})
    req_id = payload.get("id")
    if not isinstance(params, dict):
        return {"jsonrpc": "2.0", "id": req_id, "error": {
            "code": -32602, "message": "params must be a JSON object"}}

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": handler.initialize(
            params.get("protocolVersion", ""), params.get("capabilities", {}))}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": handler.list_tools()}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        return {"jsonrpc": "2.0", "id": req_id, "result": handler.call_tool(name, arguments)}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": None}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
