# Script execution deadlines

Each tool has an **Execution timeout (seconds)** setting in Tool studio. New and
existing tools default to **120 seconds (2 minutes)**. Set it to **45** for a
45-second deadline, or another whole number from 1 to 3600.

The deadline starts when the saved Python or Node script launches, after package
preparation. No extra 15 seconds are added. At the deadline, the runner kills the
script's process group, including ordinary child processes, and reports a timeout
error. This applies to dashboard tests, MCP calls and scheduled executions.
Dependency installation and its lock wait retain their own separate bounded
limits. The setting is not a limit on total package-preparation time.

An AI can choose the deadline when it registers a tool through MCP:

```json
{
  "name": "my_tool",
  "language": "python3",
  "code": "print('done')",
  "timeout_seconds": 45
}
```

Omit `timeout_seconds` to use 120 seconds. The authoring tool's input schema,
initialization instructions and `omniforge_instructions` all describe the field.
Users can change an AI-selected value in the tool window before saving.

The value is stored with the tool and included in its content revision. Older
clients that omit the field while editing preserve the saved deadline.
`OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS` is a legacy setting and no longer controls
execution. Scripts remain trusted subprocesses sharing the application container;
this setting does not introduce a filesystem or resource sandbox.
