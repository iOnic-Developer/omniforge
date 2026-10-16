# Product documentation and example checks

A focused, permanent regression gate for the documentation and dependency-free
examples. This is not the full backend suite, browser testing, image certification
or a claim that a published container matches the reviewed source.

## Run

From the repository root, with the application's dependencies already installed:

```bash
python scripts/test-docs.py
```

In the shared development workspace the existing application interpreter is:

```bash
/workspace/omniforge/.venv/bin/python /workspace/omniforge-product-docs/scripts/test-docs.py
```

The script derives the checkout root from `Path(__file__).resolve()`; the current
working directory does not matter. It uses stdlib `unittest` and installs nothing.
Python application requirements and Node must already be available. CI can use
Python 3.12 with the application's existing requirements; `httpx` is optional for
this harness, not a new application dependency.

## Isolation and transport

Before importing any application module, the harness replaces inherited environment
variables with an explicit allowlist. Database, scratch, package-cache, home and
temporary paths live in one disposable temporary directory. The subprocess
`PYTHONPATH` points to this checkout, never the interpreter's neighbouring checkout.
No live key or database configuration is inherited. The only MCP key is a disposable
test value. Python bytecode writes are disabled for test imports.

When `httpx` exists, requests use FastAPI `TestClient`. Otherwise the harness starts
Uvicorn on an ephemeral loopback port and sends real stdlib `urllib` requests with
proxies disabled. It stops the server and deletes temporary state on completion.
No mocked external requests, provider calls, pip/npm installs or live service calls
are involved. Both fixtures must declare `requirements: []` before API execution.
Negative-case request logging and server stdout/stderr are suppressed; only safe
unittest diagnostics and the explicit result summary are printed.

## Checks

- Python and Node CommonJS scripts execute directly with fixture JSON on stdin;
  parsed stdout matches each expected JSON file and stderr is empty.
- Payload code exactly matches its companion script, requirements are empty, and
  the actual application model/schema validator accepts payloads and fixture input.
- Real HTTP create preserves both schemas and code, without executing either tool.
- Duplicate create returns 409. HTTP authoring rejects MCP's `inputSchema` field;
  HTTP payloads must use `json_schema`.
- Run / Test executes both scripts and checks real output, exit code and timeout.
- Seven invalid input cases return 422, leave no runner scratch file, and do not
  echo the test value in schema-validation errors.
- MCP POST without a key returns 401; the dummy Bearer key allows discovery.
  Discovery contains exactly two examples and two built-in authoring helpers,
  with the actual saved schemas. Both examples execute successfully over MCP.
- MCP authoring uses `inputSchema`, saves without execution, and appears in
  discovery. The HTTP-only `json_schema` field and invalid arguments are rejected.
- One focused optimistic-concurrency case updates with `If-Match`, then rejects
  stale save and Run / Test requests with 412, preserving the accepted update.
- Local Markdown/HTML file references in README, Docker Hub copy, docs/wiki,
  documentation and examples resolve. Wiki URLs and extensionless wiki names map
  to actual case-sensitive filenames. External URLs are not fetched; fragment
  anchors are not validated. Fenced code/templates and immutable `docs/review/`
  evidence are deliberately excluded, not rewritten to satisfy the checker.
- Docker Hub copy contains no private GitHub URLs, GitHub Pages links, or positive
  public-hosted-demo claims. This is a focused copy guard, not a network audit.
- PNG headers are read with stdlib `struct`; HTML width/height pairs preserve the
  image's aspect ratio. Bundled Manrope/JetBrains Mono fonts and SIL licence texts
  remain present. No Pillow or image-processing dependency is required.

## Recorded execution — October 16, 2026

Measured in `LibreChat-Workspace` using the existing
`/workspace/omniforge/.venv/bin/python` interpreter:

| Invocation | Tests passed | Failures / errors / skipped | Local file references | Exit |
|---|---:|---|---:|---:|
| Repository-root invocation | 15 | 0 / 0 / 0 | 224 | 0 |
| Absolute script path from `/workspace`, with deliberately invalid inherited DB/scratch/cache/PYTHONPATH settings | 15 | 0 / 0 / 0 | 224 | 0 |

Both executions used **Uvicorn + urllib real loopback HTTP**, because `httpx`
was absent from the existing venv. No dependency was installed. The TestClient
branch and Python 3.12 CI execution remain unverified locally. Counts are unittest
methods; fixture loops and negative input subcases are not inflated into extra tests.

## Scope and handoff

Only `scripts/test-docs.py` and this document are owned by this testing task.
Application code, requirements, CI configuration, reviewed source, font/licence
assets and PR #5 review evidence are not edited. No commit or push is performed.
The parent task owns npm/browser/site checks and workflow integration. TestClient
and Python 3.12 are not claimed as exercised unless separately recorded.
