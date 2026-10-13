"""Limited HTTP JSON-RPC tool discovery, built-in authoring and execution."""

from __future__ import annotations

import json
import sqlite3

from pydantic import ValidationError

from app.database import db, Tool
from app.runner import run_tool
from app.tool_authoring import (
    BUILTIN_NAMES, EMPTY_SCHEMA, ToolIn, save_tool, validate_arguments,
)

CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "pattern": "^[a-zA-Z][a-zA-Z0-9_-]{0,62}$"},
        "description": {"type": "string"},
        "language": {"type": "string", "enum": ["python", "python3", "node", "js", "javascript"], "default": "python3"},
        "code": {"type": "string", "minLength": 1},
        "inputSchema": {"type": "object", "description": "JSON Schema Draft 2020-12, type object; only local references. Omit for no inputs."},
        "requirements": {"type": "array", "items": {"type": "string"}, "maxItems": 50,
                         "description": "Package names: Python name or name==version; Node name or @scope/name with optional @1.2.3. Installed lazily on first execution; URLs, paths, flags and binaries unsupported."},
        "is_active": {"type": "boolean", "default": True},
    },
    "required": ["name", "code"],
    "additionalProperties": False,
}

BUILTIN_TOOLS = [
    {
        "name": "omniforge_instructions",
        "description": "Read how to author and register trusted Python/Node scripts, supply inputs and test them, including current safety and transport limitations.",
        "inputSchema": EMPTY_SCHEMA,
    },
    {
        "name": "omniforge_create_tool",
        "description": "Save a new trusted script as a tool without executing it. Does not overwrite existing names or install dependencies. Read omniforge_instructions first.",
        "inputSchema": CREATE_SCHEMA,
    },
]

INSTRUCTIONS = {
    "workflow": [
        "Only register code the user trusts and has authorised. Obtain approval for the script's intended side effects.",
        "Call omniforge_create_tool with name, code and optional description, language, inputSchema, requirements (optional package-name array), is_active=true.",
        "Creation saves metadata only: it does not run, syntax-check or install anything. Duplicate and built-in names are rejected; edit existing tools in the dashboard.",
        "Call tools/list again after saving: active scripts appear immediately without restarting. There are no list-change notifications; clients may need a refresh.",
        "Execute separately with tools/call using the saved name and arguments. Dashboard Run / Test accepts a JSON object (default {}) and validates it against the saved inputSchema before execution.",
    ],
    "contract": {
        "name": "Start with a letter; then letters, digits, underscores or hyphens; maximum 63 characters. Built-in names are reserved.",
        "language": "python/python3 or node/js/javascript (normalised to python3 or node). Default python3.",
        "code": "Nonempty trusted script. Print JSON to stdout using print(json.dumps(...)) or console.log(JSON.stringify(...)). A returned object alone is not captured. stderr is captured; nonzero exits and timeouts become tool errors.",
        "inputSchema": "JSON Schema Draft 2020-12 with type object. Omitted/{} means no inputs (additionalProperties=false). Only local references are allowed. MCP and dashboard tests validate arguments before execution; format is annotation-only. Schema defaults are not inserted into arguments.",
        "inputs": "One JSON object is supplied on stdin, not interpolated into code, shell commands or environment variables. Do not log credentials in stdout/stderr.",
        "requirements": "Packages install on first execution into persistent per-tool, per-language requirements-hash caches under OMNIFORGE_LIB_ROOT. Python: name or name==version, wheels only from PyPI; Node: name or @scope/name with optional exact @1.2.3 pin, official npm registry, lifecycle scripts disabled. CommonJS require is supported; NODE_PATH does not resolve ESM imports. No URLs, VCS, paths, flags, aliases or system binaries. Install timeout 120 seconds, bounded lock wait 125 seconds, then the existing script timeout. Failed installs never execute the script or publish a cache. Requirements are validated on save; creation does not install.",
    },
    "examples": [
        {
            "name": "greet_python", "description": "Return a greeting as JSON", "language": "python3",
            "code": 'import json, sys\nargs = json.load(sys.stdin)\nprint(json.dumps({"message": "Hello " + args.get("name", "world")}))\n',
            "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "additionalProperties": False},
            "requirements": [],
        },
        {
            "name": "greet_node", "description": "Return a greeting as JSON", "language": "node",
            "code": 'const fs = require("node:fs");\nconst args = JSON.parse(fs.readFileSync(0, "utf8"));\nconsole.log(JSON.stringify({message: "Hello " + (args.name || "world")}));\n',
            "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "additionalProperties": False},
            "requirements": [],
        },
    ],
    "call_example": {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "greet_python", "arguments": {"name": "David"}}},
    "limitations": [
        "Scripts are subprocesses in the shared application container, NOT isolated sandboxes. They inherit the application environment and can access credentials, network and writable data. JSON stdin does not fix this isolation issue.",
        "Dashboard and management API are unauthenticated. Keep the service on a trusted network. Existing optional Bearer auth protects MCP POST only, not management or GET /mcp.",
        "Transport is limited HTTP JSON-RPC POST /mcp, not full MCP Streamable HTTP. OAuth, sessions and list-change notifications are not implemented. GET /mcp is only an initial SSE stub; real-client compatibility must be verified.",
        "Dependency installation is synchronous and can block requests. Runtime timeout is configured duration plus 15 seconds after dependency preparation. Per-script memory limits, process-tree termination and output caps are not implemented.",
    ],
}


def tool_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


class MCPHandler:
    """Read the current registry on each request; built-ins never depend on DB rows."""

    def tools(self) -> list[Tool]:
        return [t for t in db.get_tool_list() if t.is_active and t.name not in BUILTIN_NAMES]

    def list_tools(self) -> dict:
        return {
            "tools": BUILTIN_TOOLS + [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": json.loads(t.json_schema_json or "{}") or EMPTY_SCHEMA,
                }
                for t in self.tools()
            ]
        }

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Creation and execution are deliberately separate operations."""
        try:
            if not isinstance(name, str) or not name:
                raise ValueError('Tool name must be a nonempty string')
            if not isinstance(arguments, dict):
                raise ValueError('arguments must be a JSON object')
            if name == 'omniforge_instructions':
                validate_arguments(arguments, EMPTY_SCHEMA)
                return tool_result(json.dumps(INSTRUCTIONS, indent=2))
            if name == 'omniforge_create_tool':
                validate_arguments(arguments, CREATE_SCHEMA)
                values = dict(arguments)
                values['json_schema'] = values.pop('inputSchema', {})
                tool = save_tool(ToolIn.model_validate(values))
                return tool_result(json.dumps({
                    'ok': True, 'id': tool.id, 'name': tool.name,
                    'is_active': tool.is_active, 'executed': False,
                    'message': 'Saved only. Refresh tools/list; execute separately with tools/call.',
                }))
            tool = next((t for t in self.tools() if t.name == name), None)
            if tool is None:
                return tool_result('Unknown or inactive tool', True)
            validate_arguments(arguments, json.loads(tool.json_schema_json or '{}'))
        except ValidationError as exc:
            message = '; '.join('.'.join(str(part) for part in error['loc']) + ': ' + error['msg']
                                for error in exc.errors(include_input=False))
            return tool_result(message, True)
        except (ValueError, RecursionError) as exc:
            return tool_result(str(exc), True)
        except sqlite3.Error:
            return tool_result('Unable to save tool metadata', True)

        result = run_tool(tool, arguments)
        parts = [result.stdout or "(no output)"]
        if result.error:
            parts.append(result.error)
        if result.stderr:
            parts.append(f"[stderr] {result.stderr}")
        if result.exit_code != 0:
            parts.append(f"[exit {result.exit_code}]")
        if result.timed_out:
            parts.append("[timeout]")
        return tool_result("\n".join(parts), result.exit_code != 0 or result.timed_out)

    def initialize(self, protocol_version: str, capabilities: dict) -> dict:
        return {
            "protocolVersion": protocol_version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "omniforge-mcp", "version": "0.1.0"},
        }
