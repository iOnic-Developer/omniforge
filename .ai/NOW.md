# Active work

| Owner | Work | Owned paths | Next |
| --- | --- | --- | --- |
| Codex parent | Connections, MCP transport, integration and OpenAI client setup | app/main.py, app/mcp_server.py, app/connections.py, tests/test_connections.py, .ai/* | Integrate and verify |
| scheduling_backend | Persistent schedules and folder configuration/execution | app/database.py, app/tool_authoring.py, app/runner.py, app/scheduling.py, app/folder_access.py, tests/test_scheduling.py, requirements.txt, Dockerfile, docker-compose.yml, .env.example, docs/scheduling.md | Backend tests |
| dashboard_features | Existing dashboard feature extension | app/templates/dashboard.html, app/static/product.css, app/static/sw.js, tests/dashboard_ui.cjs, tests/product_browser.cjs | Browser verification |
| Claude Opus 5.5 | Independent architecture and final review | Read-only | Review invariants and findings |
