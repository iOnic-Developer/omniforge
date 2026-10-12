"""MCP server layer: expose tools over the Model Context Protocol.

Reads the current tool list from the database (hot-reloaded), converts each tool
into an MCP tool schema, and routes tool_call requests to the execution engine.
"""

from __future__ import annotations

import json
import time
from typing import Any, List, Optional

from app.database import db, Tool
from app.runner import run_tool


class MCPHandler:
    """Handle JSON-RPC / SSE MCP requests against the live tool registry."""

    def tools(self) -> list[Tool]:
        return [t for t in db.get_tool_list() if t.is_active]

    def list_tools(self) -> dict:
        """Return the MCP tools list in the standard format."""
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": json.loads(t.json_schema_json or "{}"),
                }
                for t in self.tools()
            ]
        }

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Route a tool call to the execution engine and return an MCP result."""
        tool = next((t for t in self.tools() if t.name == name), None)
        if tool is None:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }

        result = run_tool(tool)
        parts = [result.stdout or "(no output)"]
        if result.stderr:
            parts.append(f"[stderr] {result.stderr}")
        if result.exit_code != 0:
            parts.append(f"[exit {result.exit_code}]")
        elif result.timed_out:
            parts.append(f"[timeout]")

        return {
            "content": [{"type": "text", "text": "\n".join(parts)}],
            "isError": result.exit_code != 0 or result.timed_out,
        }

    def initialize(self, protocol_version: str, capabilities: dict) -> dict:
        return {
            "protocolVersion": protocol_version,
            "capabilities": {"tools": {"list": True, "call": True}},
            "serverInfo": {"name": "omniforge-mcp", "version": "0.1.0"},
        }
