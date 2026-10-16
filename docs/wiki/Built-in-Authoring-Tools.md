# Built-in authoring tools

OmniForge always lists two tools of its own at the top of `tools/list`, even when the database is empty. They let an AI client learn the authoring contract and save new tools.

| Tool | Inputs | What it does |
|---|---|---|
| `omniforge_instructions` | none (`{}`) | Returns the authoring contract, two working examples, the workflow and the current limitations as JSON text. Contains no environment values or credentials. |
| `omniforge_create_tool` | see [below](#omniforge_create_tool) | **Saves** a new tool. It doesn't run the code, check its syntax or install packages, and it never overwrites an existing name. |

Neither appears in the dashboard library. Their names are reserved: you can't create, rename to, edit, toggle, delete or run a library tool with either name. Rows with those names left over in an old database are ignored for MCP, so they can't shadow the built-ins.

> [!WARNING]
> `omniforge_create_tool` lets an MCP client save code that it, or any other client, can then run with `tools/call`. **Access to `/mcp` therefore means code execution inside the container**, with the app's environment, including `OMNIFORGE_API_KEY`. Give `/mcp` access only to clients and people you'd trust with a shell in the container.

## `omniforge_instructions`

Call it with no arguments:

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"omniforge_instructions","arguments":{}}}
```

Any argument at all, such as `{"extra": true}`, is rejected. The result text is a JSON document with these keys:

| Key | Contents |
|---|---|
| `workflow` | Five steps: get the user's approval, create, refresh `tools/list`, then call separately. |
| `contract` | Rules for `name`, `language`, `code`, `inputSchema`, `inputs` and `requirements`. They match [Writing tools](Writing-Tools.md) and [Dependencies](Dependencies.md). |
| `examples` | Two ready-to-submit tools, `greet_python` and `greet_node`, each with an `inputSchema` that takes an optional `name`. |
| `call_example` | A `tools/call` request for `greet_python`. |
| `limitations` | The shared-container, unauthenticated-management, partial-transport and resource-limit caveats. |

## `omniforge_create_tool`

### Arguments

| Field | Type | Required | Default | Rules |
|---|---|---|---|---|
| `name` | string | **yes** | | `^[a-zA-Z][a-zA-Z0-9_-]{0,62}$`. Not a built-in name, and not an existing name (including disabled tools). |
| `code` | string | **yes** | | Must contain more than whitespace, and no NUL characters. |
| `description` | string | no | `""` | Shown to AI clients in `tools/list`. |
| `language` | string | no | `python3` | One of `python`, `python3`, `node`, `js` or `javascript`. Stored as `python3` or `node`. |
| `inputSchema` | object | no | no inputs | A JSON Schema Draft 2020-12 object schema with local references only. See [schema rules](Writing-Tools.md#schema-rules). |
| `requirements` | array of strings | no | `[]` | Up to 50 entries. See [accepted forms](Dependencies.md#accepted-forms). |
| `is_active` | boolean | no | `true` | `false` saves the tool without listing it to MCP clients. |

Unknown fields are rejected. Types are strict: `"is_active": "true"` (a string) fails.

### Example

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "omniforge_create_tool",
    "arguments": {
      "name": "sort_unique",
      "description": "Sort a list of numbers and remove duplicates. Returns {\"sorted\": [...]}.",
      "language": "node",
      "code": "const fs = require('node:fs');\nconst _ = require('lodash');\nconst args = JSON.parse(fs.readFileSync(0, 'utf8'));\nconsole.log(JSON.stringify({ sorted: _.sortBy(_.uniq(args.numbers)) }));\n",
      "inputSchema": {
        "type": "object",
        "properties": {"numbers": {"type": "array", "items": {"type": "number"}}},
        "required": ["numbers"],
        "additionalProperties": false
      },
      "requirements": ["lodash@4.17.21"]
    }
  }
}
```

### Success

```json
{
  "content": [{"type": "text", "text": "{\"ok\": true, \"id\": \"3f9c2a1b7d4e\", \"name\": \"sort_unique\", \"is_active\": true, \"executed\": false, \"message\": \"Saved only. Refresh tools/list; execute separately with tools/call.\"}"}],
  "isError": false
}
```

`executed` is always `false`. The client must then:

1. Call `tools/list` again. OmniForge sends no change notification.
2. Call the new tool by name with `tools/call`. Its first run installs `lodash`.

### Errors

Errors come back as normal tool results with `isError: true`. They never echo the submitted values back.

| Text | Cause |
|---|---|
| `Arguments do not match inputSchema` | The arguments fail the tool's own schema: a missing `name` or `code`, a name that doesn't match the pattern, an unsupported `language`, empty `code`, a wrong type (`"is_active": "true"`) or an unknown field. |
| `Tool name already exists; choose another name or edit it in the dashboard` | The name is taken, possibly by a disabled tool. |
| `name: Value error, Tool name is reserved for a built-in tool` | You used a built-in name. |
| `code: Value error, code must be a nonempty script without NUL characters` | The code is only whitespace, or contains `\u0000`. |
| `json_schema: Value error, inputSchema must declare type object` | The `inputSchema` root isn't `"type": "object"`. Other schema problems use the same prefix, for example `Only local inputSchema references are supported` or `Only JSON Schema Draft 2020-12 is supported`. |
| `: Value error, Invalid requirement: use Python name or name==version; …` | A package entry breaks the [accepted forms](Dependencies.md#accepted-forms). The leading `: ` is how the message comes out. |
| `Unable to save tool metadata` | A database error, for example a read-only data volume. |

## Editing and deleting

The built-ins only **create**. To change or remove a tool, use the dashboard or the [REST API](API-Reference.md). An AI client with network access could call that API too, because it has no authentication. That's one more reason to keep OmniForge on a trusted network.

## A sensible workflow with an assistant

1. Ask the assistant to read `omniforge_instructions`.
2. Describe the tool you want. Review the code it proposes **before** it calls `omniforge_create_tool`.
3. Open the new tool in the dashboard's Tool studio, read the code, and **Run / Test** it.
4. Disable it with the switch in **Tools** if you're not happy. Disabled tools can't be called over MCP.

---

← [Home](Home.md) · [Next: PWA and themes →](PWA-and-Themes.md)
