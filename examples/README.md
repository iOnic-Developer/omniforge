# Useful tools, no package installs

Two small, reviewable examples of OmniForge's script contract. Both use only
standard libraries: no network, credentials, pip or npm installation is needed.
These fixtures target the reviewed source API, not an unverified image tag.

| Tool | Runtime | What it does |
|---|---|---|
| [slugify.py](slugify.py) | `python3` | Fold accents, lowercase and normalise punctuation into an ASCII URL slug |
| [summarize-json.cjs](summarize-json.cjs) | `node` (CommonJS) | Summarise a JSON number array: count, total, minimum, maximum and mean |

Each `*.tool.json` is a complete **single-tool HTTP create payload**, not a bulk
import file. Its `code` matches the script beside it; `requirements` is `[]`.
Its `json_schema` validates inputs. The `.input.json` and `.expected.json` files
provide repeatable sample input and parsed stdout expectations.

## Try the scripts locally

From the repository root:

```bash
python3 examples/slugify.py < examples/slugify.input.json
node examples/summarize-json.cjs < examples/summarize-json.input.json
```

The results are `{"slug":"cafe-python-node-tools"}` and
`{"count":4,"total":40,"min":4,"max":16,"mean":10}` respectively (JSON whitespace
may differ). An empty number array returns count/total `0` and null min/max/mean.
Slugifying non-Latin-only text may produce an empty slug: this is ASCII folding,
not a multilingual transliteration library. Direct invocation does not run
OmniForge's schema validation; use the API for validation tests.

## Save, then test through OmniForge

Keep the service local/trusted: management routes are unauthenticated. Saving
does not execute the script. A duplicate name returns HTTP 409; do not overwrite
an existing tool merely to try an example.

```bash
curl --fail-with-body -sS http://localhost:8000/api/tools \
  -H 'Content-Type: application/json' --data-binary @examples/slugify.tool.json
curl --fail-with-body -sS http://localhost:8000/api/tools/slugify/run \
  -H 'Content-Type: application/json' \
  -d '{"arguments":{"text":"Café: Python & Node tools!"}}'

curl --fail-with-body -sS http://localhost:8000/api/tools \
  -H 'Content-Type: application/json' --data-binary @examples/summarize-json.tool.json
curl --fail-with-body -sS http://localhost:8000/api/tools/summarize_json/run \
  -H 'Content-Type: application/json' -d '{"arguments":{"numbers":[4,8,12,16]}}'
```

Check `exit_code: 0`, `timed_out: false` and parsed `stdout`. HTTP 200 alone does
not prove a script succeeded. Invalid inputs return HTTP 422 before execution.
To guard a run against changes, obtain the saved `revision` from `GET /api/tools`
and send it in `If-Match`; a stale revision returns HTTP 412.

For MCP authoring, pass the same fields to `omniforge_create_tool` but rename
**`json_schema` to `inputSchema`**. For calls, use `tools/call` with the saved name
and the input object as `arguments`; send the configured Bearer key on POST
`/mcp`. Saving and running remain separate operations.

[Script contract](../docs/wiki/Writing-Tools.md) ·
[API reference](../docs/wiki/API-Reference.md) ·
[Security](../docs/wiki/Security-and-Limitations.md)
