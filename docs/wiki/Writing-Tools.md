# Writing tools

A tool is a Python or Node script with a name, a description, an optional list of packages and an optional input schema. This page sets out the exact contract between OmniForge and your script.

## The contract at a glance

| | Behaviour |
|---|---|
| **Input** | One JSON object on **stdin**. It is `{}` when there are no arguments. It is never put into the command line, the shell or environment variables. |
| **Validation** | Arguments are checked against the tool's input schema **before** the script starts. If they don't match, the script never runs. |
| **Output** | Everything printed to **stdout**, with leading and trailing whitespace trimmed, comes back as text. Print JSON if the client needs structure. |
| **Return values** | Not captured. `return {...}` from a function produces nothing. Print it. |
| **Diagnostics** | **stderr** is captured. In MCP results it's appended after stdout as `[stderr] …`, **even when the run succeeds**. |
| **Success** | Exit code `0` and no timeout. Anything else is reported as an error (`isError: true`). |
| **Time limit** | `OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS` + 15 s (45 s by default), counted after packages are ready. |
| **Size limit** | None. Output isn't capped (see [below](#things-to-avoid)). |
| **Memory limit** | None. `OMNIFORGE_MAX_SCRIPT_MEMORY_MB` isn't enforced. |
| **Isolation** | None. The script is a subprocess of the app, with the app's environment, network and files. |

## Inputs: one JSON object on stdin

OmniForge serialises the arguments with `json.dumps(…, allow_nan=False)` and writes them to the script's stdin once. Read all of stdin and parse it.

**Python**

```python
import json
import sys

args = json.load(sys.stdin)
name = args.get("name", "world")
```

**Node (CommonJS)**

```javascript
const fs = require('node:fs');

const args = JSON.parse(fs.readFileSync(0, 'utf8'));
const name = args.name || 'world';
```

Schema `default` values are **not** filled in for you. Always provide fallbacks in code, as above.

## Outputs: print once, print JSON

```python
print(json.dumps({"message": f"Hello {name}"}))
```

```javascript
console.log(JSON.stringify({ message: `Hello ${name}` }));
```

- The MCP client receives the printed text as `{"type": "text", "text": "…"}`. OmniForge doesn't parse it or send `structuredContent`.
- If a run prints nothing, the MCP text is `(no output)`. The dashboard says *"no output — use print() in Python or console.log() in Node"*.
- The dashboard pretty-prints stdout when it's valid JSON and shows it unchanged otherwise.
- **Never print secrets.** Output goes to the AI client and, from there, possibly into a model's context.

## Errors: stderr and exit codes

| Situation | Exit code | `isError` | MCP text |
|---|---|---|---|
| Success | `0` | `false` | stdout, then `[stderr] …` if anything was written to stderr |
| Uncaught exception or `SyntaxError` | `1` | `true` | stdout or `(no output)`, `[stderr] <traceback>`, `[exit 1]` |
| `sys.exit(7)` / `process.exit(7)` | `7` | `true` | … `[exit 7]` |
| Timeout | `124` | `true` | `(no output)`, `[stderr] Script exceeded 30000ms timeout`, `[exit 124]`, `[timeout]` |
| Package install failed | `1` | `true` | `(no output)`, the install error, `[stderr] <same error>`, `[exit 1]` |
| Runtime not found | `1` | `true` | `(no output)`, `no python3 runtime available` or `no node runtime available`, … |

For example, a script that prints `failure details` to stderr and exits with code 7 returns this MCP text:

```text
(no output)
[stderr] failure details
[exit 7]
```

Things to know:

- **Exit code `124` means "timed out"** to OmniForge, because that's how it marks timeouts. A script that exits with 124 on its own is reported as a timeout. Use other codes.
- **Write warnings to stderr only when something is wrong.** If a successful run writes to stderr (a Python `DeprecationWarning`, a Node `ExperimentalWarning`, a progress bar), the MCP text becomes `<your JSON>\n[stderr] <warning>`, and a client that expects pure JSON will fail to parse it. The dashboard's Run / Test shows stderr separately, so this only shows up over MCP.
- **Syntax isn't checked on save.** A broken script saves without complaint and fails on its first run.

## Time limits

- The limit is `OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS / 1000 + 15` seconds: 45 s with the default of 30000.
- The clock starts **after** dependency preparation. A first run with packages can therefore take up to 120 s for the install, plus up to 125 s waiting for a lock, plus the script limit.
- On timeout, OmniForge kills **only the direct child process**. Anything your script started (a `subprocess`, a `child_process.spawn`, a background worker) keeps running inside the container. Any stdout produced so far is discarded.
- The timeout message reports the configured value ("exceeded 30000ms"), not the effective 45 s.
- **While a script runs, the server waits for it.** The run and MCP handlers call the subprocess synchronously, so one slow tool holds up the dashboard and every other client until it finishes or times out. Keep tools quick.

## The environment your script runs in

| Aspect | Value |
|---|---|
| Command | `python3 <scratch>/<tool-id>.py` or `node <scratch>/<tool-id>.js`, with no command-line arguments |
| Working directory | `OMNIFORGE_SCRATCH_ROOT` (default `/tmp/omniforge`), shared by all tools |
| User | UID 1000, the same as the app |
| Python | The app's virtualenv interpreter (Python 3.12). Packages the app itself depends on, such as `pydantic`, `httpx` and `jsonschema`, happen to be importable. **Don't rely on this**: declare what you use, because app updates can change those versions. |
| Node | The Debian-packaged Node.js in the image (`docker exec omniforge node --version`). CommonJS. |
| Package path | Your tool's cache directory is placed in front of `PYTHONPATH` or `NODE_PATH` |
| Environment | **The whole application environment**, including `OMNIFORGE_API_KEY` and anything else you passed to the container |
| Network | Whatever the container can reach |
| Files | Write access to `/tmp`, the data volume (**including the SQLite database**) and the package caches. Unless the root filesystem is read-only, also write access to the app code in `/app`, which belongs to the same UID. |

> [!WARNING]
> A tool can read and print `OMNIFORGE_API_KEY`. For example, `import os; print(os.environ.get("OMNIFORGE_API_KEY"))` returns the key to whoever called the tool. A tool can also modify `omniforge.db` directly. Only save code you'd be happy to run as the app itself. See [Security and limitations](Security-and-Limitations.md).

Need a temporary file? Use Python's `tempfile` or Node's `os.tmpdir()`, both of which point under `/tmp`. Don't write next to the script: the scratch directory is shared by all tools, and `<tool-id>.py` is overwritten on every run.

## Examples

### Python, no packages, with inputs: add VAT

```python
import json
import sys
from decimal import Decimal, ROUND_HALF_UP

args = json.load(sys.stdin)
net = Decimal(str(args["net"]))
rate = Decimal(str(args.get("rate", 20)))
vat = (net * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
print(json.dumps({"net": str(net), "rate": str(rate), "vat": str(vat), "gross": str(net + vat)}))
```

Input schema:

```json
{
  "type": "object",
  "properties": {
    "net": {"type": "number", "minimum": 0, "description": "Amount before VAT, in pounds"},
    "rate": {"type": "number", "minimum": 0, "maximum": 100, "description": "VAT rate in percent; defaults to 20"}
  },
  "required": ["net"],
  "additionalProperties": false
}
```

Calling it with `{"net": 99.99}` prints `{"net": "99.99", "rate": "20", "vat": "20.00", "gross": "119.99"}`.

### Python with a package: next UK bank holiday

Packages: `requests==2.32.5`

```python
import json
import sys
from datetime import date

import requests

args = json.load(sys.stdin)
division = args.get("division", "england-and-wales")

try:
    response = requests.get("https://www.gov.uk/bank-holidays.json", timeout=10)
    response.raise_for_status()
except requests.RequestException as exc:
    print(f"Could not fetch bank holidays: {exc}", file=sys.stderr)
    sys.exit(1)

today = date.today().isoformat()
upcoming = [e for e in response.json()[division]["events"] if e["date"] >= today]
print(json.dumps({"division": division, "next": upcoming[0] if upcoming else None}))
```

```json
{
  "type": "object",
  "properties": {
    "division": {"type": "string", "enum": ["england-and-wales", "scotland", "northern-ireland"]}
  },
  "additionalProperties": false
}
```

Set a network timeout shorter than the script limit, as `timeout=10` does here, so that a slow upstream produces a clean error instead of a killed process.

### Node with a package: sort unique numbers

Packages: `lodash@4.17.21`

```javascript
const fs = require('node:fs');
const _ = require('lodash');

const args = JSON.parse(fs.readFileSync(0, 'utf8'));
console.log(JSON.stringify({ sorted: _.sortBy(_.uniq(args.numbers)) }));
```

```json
{
  "type": "object",
  "properties": {
    "numbers": {"type": "array", "items": {"type": "number"}, "maxItems": 1000}
  },
  "required": ["numbers"],
  "additionalProperties": false
}
```

### Node, asynchronous code

Top-level `await` needs ES modules, which OmniForge doesn't support for installed packages. Wrap async work in a function, and make failures exit with a non-zero code:

```javascript
const fs = require('node:fs');

async function main() {
  const args = JSON.parse(fs.readFileSync(0, 'utf8'));
  await new Promise(resolve => setTimeout(resolve, 100)); // your async work here
  console.log(JSON.stringify({ ok: true, received: Object.keys(args) }));
}

main().catch(error => {
  console.error(error.message);
  process.exit(1);
});
```

Use `require`, not `import`. `NODE_PATH` doesn't apply to ES-module resolution, so `import _ from 'lodash'` can't find installed packages. Whether `.js` files containing ESM syntax run at all depends on the Node version in the image.

## Giving a tool inputs

The dashboard **can't create or edit input schemas** yet. A tool saved from the Tool studio gets an empty schema, which means "no inputs". Calling it with any argument fails with `Arguments do not match inputSchema`. To give a tool parameters, use one of these routes. After that, you can keep editing its code in the dashboard: saving from the studio sends the existing schema back unchanged.

### Option 1: REST API

Save this as `add_vat.json`:

```json
{
  "name": "add_vat",
  "description": "Add UK VAT to a net amount and return net, VAT and gross.",
  "language": "python3",
  "code": "import json\nimport sys\nfrom decimal import Decimal, ROUND_HALF_UP\n\nargs = json.load(sys.stdin)\nnet = Decimal(str(args[\"net\"]))\nrate = Decimal(str(args.get(\"rate\", 20)))\nvat = (net * rate / 100).quantize(Decimal(\"0.01\"), rounding=ROUND_HALF_UP)\nprint(json.dumps({\"net\": str(net), \"rate\": str(rate), \"vat\": str(vat), \"gross\": str(net + vat)}))\n",
  "requirements": [],
  "json_schema": {
    "type": "object",
    "properties": {
      "net": {"type": "number", "minimum": 0},
      "rate": {"type": "number", "minimum": 0, "maximum": 100}
    },
    "required": ["net"],
    "additionalProperties": false
  },
  "is_active": true
}
```

Then post it:

```bash
curl -s http://localhost:8000/api/tools \
  -H 'Content-Type: application/json' \
  -d @add_vat.json
```

The REST field is called **`json_schema`**. In MCP it's called **`inputSchema`**.

### Option 2: from an AI client

Ask your assistant to call the built-in `omniforge_create_tool` with an `inputSchema`. See [Built-in authoring tools](Built-in-Authoring-Tools.md).

### Changing the schema of an existing tool

`PUT /api/tools/{name}` replaces **every** field. Anything you leave out goes back to its default, so read the tool first. This needs `jq`:

```bash
HOST=http://localhost:8000
NAME=add_vat
SCHEMA='{"type":"object","properties":{"net":{"type":"number","minimum":0}},"required":["net"],"additionalProperties":false}'

TOOL=$(curl -s "$HOST/api/tools" | jq --arg n "$NAME" '.tools[] | select(.name == $n)')
REV=$(echo "$TOOL" | jq -r .revision)

echo "$TOOL" \
  | jq --argjson schema "$SCHEMA" '{name, description, language, code,
        requirements: (.requirements_json | fromjson), json_schema: $schema, is_active}' \
  | curl -s -X PUT "$HOST/api/tools/$NAME" \
      -H 'Content-Type: application/json' -H "If-Match: $REV" -d @-
```

The `If-Match` header makes the update fail with HTTP 412, rather than overwrite someone else's change, if the tool was edited in the meantime.

### Schema rules

- **JSON Schema Draft 2020-12** only. Leave out `$schema`, or set it to exactly `https://json-schema.org/draft/2020-12/schema`.
- The root must be `"type": "object"`.
- `{}` or a missing schema means **no inputs**. It's stored as `{"type":"object","properties":{},"additionalProperties":false}`.
- `{"type": "object"}` on its own accepts **any** object.
- Only local references (`"$ref": "#/$defs/…"`) are allowed. Remote references are rejected and never fetched. A local reference that doesn't resolve is accepted on save but makes every call fail.
- `format` is annotation-only (not checked), and `default` isn't applied.
- Validation failures return the generic message `Arguments do not match inputSchema`, without saying which field. This stops submitted values from being echoed back. Describe each field clearly so the AI client gets it right first time.

## Names and descriptions

- **Name:** a letter, then up to 62 letters, digits, `_` or `-`, matching `^[a-zA-Z][a-zA-Z0-9_-]{0,62}$`. Names are unique across all saved tools, including disabled ones. `omniforge_instructions` and `omniforge_create_tool` are reserved.
- **Renaming** in the studio keeps the tool's internal ID. Its package cache, enabled state and schema carry over.
- **Description:** this is what the AI reads when deciding whether to use the tool. Say what it does, when to use it and what it returns. For example: *"Add UK VAT to a net amount. Use for invoices and price quotes. Returns net, VAT and gross as strings with two decimal places."*

## Things to avoid

- **Huge output.** stdout and stderr are held in memory in full and sent back whole. A runaway loop that prints can exhaust the container's memory. Keep results to what an AI can use: a few kilobytes is plenty.
- **Long-running work.** It blocks the server for everyone (see [Time limits](#time-limits)).
- **Background processes.** They outlive timeouts and nothing cleans them up.
- **Secrets in code.** `GET /api/tools` returns every tool's source to anyone who can reach the server. Secrets passed in as container variables aren't much safer, because every tool can read every variable.
- **Prompting for input or opening a GUI.** There's no TTY, and stdin closes after the JSON object.

---

← [Home](Home.md) · [Next: Dependencies →](Dependencies.md)
