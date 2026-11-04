# Scheduled tools and output folders

A tool can carry a schedule, an output folder, or both. These settings are saved
with the tool, so a tool created through MCP has the same controls in Tool studio.
The Schedule and Folder controls appear when those features have been configured;
you can also add either feature to an existing tool in the editor. Pause a schedule
without losing its cron, timezone, arguments or output location.

## Schedule

Use five cron fields: `minute hour day-of-month month day-of-week`.
For example, `0 2 * * *` runs nightly at 02:00 in the selected IANA timezone,
and `0 */6 * * *` runs every six hours. Select `Europe/London` for UK local time
or `UTC` for a schedule that does not change with daylight saving.

Scheduled arguments are a JSON object and must match the tool's input schema.
The scheduler validates them again before each execution. A disabled tool does not
run on its schedule. Saving a tool stores its metadata; the first scheduled run
is at the next matching cron time. The server must be running for jobs to execute.

Schedule times and the last ten execution summaries appear in the tool's schedule
status. SQLite stores the next due time and up to fifty summaries per tool.
Summaries include times, outcome, exit code and duration, not script stdout or
stderr. Use Run / Test to inspect output when a scheduled run fails.

Missed occurrences are coalesced into one run when the server returns. The next
time is calculated from the current time, so a long outage does not replay every
missed night. A job already running does not overlap another scheduled occurrence
of itself. Transactional SQLite claims and renewable leases coordinate multiple
server workers using the same database. At most four scheduled jobs run at once
per worker. Manual tests remain separately initiated executions.

An execution interrupted by a stopped or crashed process is recorded as
`interrupted` after its lease expires. Its uncertain side effects are not retried
automatically; the next ordinary cron occurrence remains scheduled. Review output
before manually retrying. Disabling or editing a job stops future claims; it does
not forcibly terminate a script already running. If settings or code change after
a claim but before execution starts, that claim is skipped.

At a daylight-saving transition, nonexistent local times are skipped. A time in
the repeated autumn hour runs once, at the first occurrence. For example, a
01:30 job in Europe/London skips the missing spring 01:30 and uses the first
autumn 01:30. A normal 02:00 nightly job retains 02:00 local time across both
transitions. Cron search is bounded to eight years; impossible dates are rejected.

## Output locations

The default allowed output root is `/opt/omniforge/files`. Docker Compose persists
this folder in the `omniforge_files` volume. Choose a subfolder such as
`/opt/omniforge/files/documents` in the tool editor; it is created when that tool
first executes. Saving settings does not create folders or run a script.

The setting `OMNIFORGE_ALLOWED_FOLDERS` controls which roots appear in the folder
picker. Separate multiple roots with the operating system's path separator (`:`
inside the Linux container). Use absolute paths. Parent traversal and symlinks
that resolve outside the configured roots are rejected, including at execution.
The picker lists directories only, up to 500 per location.

To write into a host directory, mount it into the container and allow its
**container path**, for example:

```yaml
services:
  omniforge:
    environment:
      OMNIFORGE_ALLOWED_FOLDERS: /opt/omniforge/files:/downloads
    volumes:
      - /mnt/user/documents/omniforge:/downloads
```

Give the mounted directory write permission for container UID/GID 1000. A host
path is not automatically accessible merely because it is typed into the editor.
On a native Linux installation, configured paths refer directly to that system.

When folder access is enabled, the runner supplies `OMNIFORGE_OUTPUT_DIR` and sets
the script's working directory to the selected location. Python scripts can use
`os.environ['OMNIFORGE_OUTPUT_DIR']`; Node scripts can use
`process.env.OMNIFORGE_OUTPUT_DIR`. Relative files are written in that folder.
The variable is removed from inherited environment settings when the feature is
off, so it cannot accidentally point to another tool's location.

This feature configures trusted scripts; it is not a filesystem sandbox. Scripts
still run inside the existing shared application container, with its environment,
network and writable mounts. Only trusted code belongs in the workspace.

## Create a nightly document downloader through MCP

An AI can call `omniforge_create_tool` with settings like these. Replace the sample
URL with the intended document's actual URL, and ensure its download is authorised.

```json
{
  "name": "download_latest_document",
  "description": "Download the latest document into the configured output folder",
  "language": "python3",
  "code": "import json, os, sys, tempfile\nfrom pathlib import Path\nfrom urllib.request import urlopen\nargs = json.load(sys.stdin)\nfolder = Path(os.environ['OMNIFORGE_OUTPUT_DIR'])\nwith urlopen(args['url'], timeout=20) as response:\n    data = response.read(20 * 1024 * 1024 + 1)\nif len(data) > 20 * 1024 * 1024:\n    raise ValueError('Document exceeds 20 MiB')\nwith tempfile.NamedTemporaryFile(dir=folder, delete=False) as output:\n    output.write(data)\n    temporary = Path(output.name)\ntemporary.replace(folder / 'latest-document.pdf')\nprint(json.dumps({'saved': 'latest-document.pdf', 'bytes': len(data)}))\n",
  "inputSchema": {
    "type": "object",
    "properties": {"url": {"type": "string"}},
    "required": ["url"],
    "additionalProperties": false
  },
  "schedule": {
    "enabled": true,
    "cron": "0 2 * * *",
    "timezone": "Europe/London",
    "arguments": {"url": "https://example.org/latest-document.pdf"}
  },
  "folder_access": {
    "enabled": true,
    "path": "/opt/omniforge/files/documents"
  }
}
```

The Schedule and Folder controls then appear for that tool in the dashboard.
You can change the schedule or location, pause execution, or resume it there.
An AI can leave a feature present but disabled when it needs a person to finish
configuration: `"schedule": {"enabled": false}` or
`"folder_access": {"enabled": false, "path": ""}`.

Omitting these fields while updating an existing tool preserves saved settings.
Sending an explicit `null` removes the corresponding feature and its control.
