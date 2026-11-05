"""Limited HTTP JSON-RPC tool discovery, built-in authoring and execution."""

from __future__ import annotations

import json
import sqlite3

from pydantic import ValidationError

from app.database import db, Tool
from app.runner import run_tool
from app.connections import tool_key, builtin_key
from app.release import VERSION
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
        "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600, "default": 120,
                            "description": "Maximum script execution time in seconds. Default 120 (2 minutes). Set 45 for a 45-second deadline, or another integer from 1 to 3600. Editable in the tool window. The process group is killed at the deadline; dependency installation has its own separate limits."},
        "schedule": {"type": ["object", "null"], "description": "Optional scheduled execution: enabled, five-field cron, IANA timezone, and saved arguments. Use enabled=false to request configurable scheduling without starting it.", "properties": {"enabled": {"type": "boolean"}, "cron": {"type": "string"}, "timezone": {"type": "string"}, "arguments": {"type": "object"}}, "additionalProperties": False},
        "folder_access": {"type": ["object", "null"], "description": "Optional output folder settings: enabled and absolute server-visible path within configured allowed roots. Scripts receive OMNIFORGE_OUTPUT_DIR and run in that folder. Use enabled=false,path='' until a folder is selected.", "properties": {"enabled": {"type": "boolean"}, "path": {"type": "string"}}, "additionalProperties": False},
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
        "Call omniforge_create_tool with name, code and optional description, language, inputSchema, requirements (optional package-name array), is_active=true, timeout_seconds, schedule and folder_access.",
        "Creation saves metadata only: it does not run, syntax-check or install anything immediately. An explicitly enabled schedule runs at its next due time. Duplicate and built-in names are rejected; edit existing tools in the dashboard.",
        "Call tools/list again after saving: active scripts appear immediately without restarting. There are no list-change notifications; clients may need a refresh.",
        "Execute separately with tools/call using the saved name and arguments. Dashboard Run / Test accepts a JSON object (default {}) and validates it against the saved inputSchema before execution.",
    ],
    "contract": {
        "name": "Start with a letter; then letters, digits, underscores or hyphens; maximum 63 characters. Built-in names are reserved.",
        "language": "python/python3 or node/js/javascript (normalised to python3 or node). Default python3.",
        "code": "Nonempty trusted script. Print JSON to stdout using print(json.dumps(...)) or console.log(JSON.stringify(...)). A returned object alone is not captured. stderr is captured; nonzero exits and timeouts become tool errors.",
        "inputSchema": "JSON Schema Draft 2020-12 with type object. Omitted/{} means no inputs (additionalProperties=false). Only local references are allowed. MCP and dashboard tests validate arguments before execution; format is annotation-only. Schema defaults are not inserted into arguments.",
        "inputs": "One JSON object is supplied on stdin, not interpolated into code, shell commands or environment variables. Do not log credentials in stdout/stderr.",
        "timeout_seconds": "Script execution deadline, integer 1 to 3600 seconds. Default 120 (2 minutes). Set timeout_seconds:45 for a 45-second limit, or choose an appropriate duration when authoring the tool. The user can change it in the tool window. The timer starts after dependency preparation; no extra 15 seconds are added. A timeout kills the script process group and returns a tool error. Dependency installation and lock waits retain separate bounded limits.",
        "schedule": "Optional {enabled:false,cron:'0 2 * * *',timezone:'UTC',arguments:{}}. Standard five-field cron with an IANA timezone; saved arguments must satisfy inputSchema. Set enabled=true only when the user has requested recurring execution. The tool window displays configuration and pause/resume controls whenever schedule is present. Missed runs are coalesced, not replayed.",
        "folder_access": "Optional {enabled:false,path:''}. Select an absolute folder beneath the server's OMNIFORGE_ALLOWED_FOLDERS roots (default /opt/omniforge/files). When enabled, scripts run in that folder and receive OMNIFORGE_OUTPUT_DIR in the environment. Python uses os.environ['OMNIFORGE_OUTPUT_DIR']; Node uses process.env.OMNIFORGE_OUTPUT_DIR. Host folders must be mounted into the container first. Only saved configuration selects the folder; runtime arguments do not change it. This is configuration, not a filesystem sandbox.",
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
        "Streamable HTTP uses JSON responses and server-issued sessions. GET /mcp returns 405 (no SSE stream). OAuth, streaming notifications and list-change notifications are not implemented. Clients should refresh tools/list after changing visibility. Named connection credentials preserve tool selections across reconnect; shared master-key sessions have individual transient policies.",
        "Script execution uses each tool's timeout_seconds (default 120) after dependency preparation and kills the process group at that deadline. Per-script memory limits and output caps are not implemented. This remains trusted shared-container execution, not a sandbox.",
    ],
}


def tool_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


class MCPHandler:
    """Read the current registry on each request; built-ins never depend on DB rows."""

    def tools(self, disabled_keys: set[str] | None = None) -> list[Tool]:
        denied = disabled_keys or set()
        return [t for t in db.get_tool_list() if t.is_active and t.name not in BUILTIN_NAMES
                and tool_key(t) not in denied]

    def list_tools(self, disabled_keys: set[str] | None = None) -> dict:
        denied = disabled_keys or set()
        return {
            "tools": [t for t in BUILTIN_TOOLS if builtin_key(t['name']) not in denied] + [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": json.loads(t.json_schema_json or "{}") or EMPTY_SCHEMA,
                }
                for t in self.tools(disabled_keys)
            ]
        }

    def call_tool(self, name: str, arguments: dict, disabled_keys: set[str] | None = None) -> dict:
        """Creation and execution are deliberately separate operations."""
        try:
            if not isinstance(name, str) or not name:
                raise ValueError('Tool name must be a nonempty string')
            if not isinstance(arguments, dict):
                raise ValueError('arguments must be a JSON object')
            if name in BUILTIN_NAMES and builtin_key(name) in (disabled_keys or set()):
                return tool_result('Tool is not available to this connection', True)
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
            tool = next((t for t in self.tools(disabled_keys) if t.name == name), None)
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
            "protocolVersion": protocol_version if protocol_version in ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25") else "2025-06-18",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "omniforge-mcp", "version": VERSION},
            "instructions": "OmniForge runs trusted Python/Node tools. Call omniforge_instructions before creating tools. Set timeout_seconds when authoring a tool: default 120 (2 minutes), allowed 1-3600; execution is killed at that deadline. The tool window can edit this setting. Tools may also declare schedule and folder_access. Connections control tool visibility. Arguments are JSON on stdin.",
        }
