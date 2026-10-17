# Backup and restore

Everything that matters is in **one SQLite file**: `/opt/omniforge/data/omniforge.db`. It holds every tool's name, description, runtime, code, package list, input schema and enabled state. Package caches can be rebuilt, and the scratch directory is disposable.

## What to back up

| Path (container) | Default volume | Back up? | Why |
|---|---|---|---|
| `/opt/omniforge/data/omniforge.db` | `omniforge_data` | **Yes** | Your tools. Losing it means losing them. |
| `/opt/omniforge/lib` | `omniforge_lib` | Optional | Package caches. Rebuilt automatically on each tool's next run, which can take minutes per tool and needs internet access. |
| `/tmp/omniforge` | none | No | Scratch copies of scripts, rewritten on every run. |
| `/opt/omniforge/scripts` | `omniforge_scripts` (repository compose only) | No | Unused by the current code. |

The database has a single table:

```sql
CREATE TABLE tools (
    id TEXT PRIMARY KEY,                       -- 12 hex characters
    name TEXT NOT NULL,                        -- indexed, not unique at the database level
    description TEXT NOT NULL,
    language TEXT NOT NULL,                    -- python3 | node
    code TEXT NOT NULL,
    requirements_json TEXT NOT NULL DEFAULT '[]',
    json_schema_json TEXT NOT NULL DEFAULT '{}',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,                  -- UTC, e.g. 2026-10-16T09:30:00Z
    updated_at TEXT NOT NULL
);
```

There are no migrations. The schema is created with `CREATE TABLE IF NOT EXISTS` at start-up, so a backup from any version with this table restores cleanly.

## How consistent is a copy?

OmniForge opens SQLite in its default **rollback-journal** mode, not WAL. Writes are short `BEGIN IMMEDIATE` transactions, and during a write SQLite briefly creates `omniforge.db-journal` next to the database. A plain file copy taken **during** a write can be inconsistent. Writes are rare and quick, but you don't need to gamble. Use one of these methods:

| Method | Downtime | Consistency |
|---|---|---|
| [Online backup with SQLite's backup API](#online-backup-recommended) | None | Guaranteed (SQLite takes the right locks) |
| [Stop, copy, start](#offline-volume-backup) | Seconds | Guaranteed |
| Unraid Appdata Backup plugin (it stops containers first) | Seconds | Guaranteed |
| Copying the live file with `cp` or `rsync` | None | **Not guaranteed**. Avoid. |

### Online backup (recommended)

The image has Python but no `sqlite3` command-line tool, so use Python's built-in backup API:

```bash
docker exec omniforge python3 -c "
import sqlite3
src = sqlite3.connect('/opt/omniforge/data/omniforge.db')
dst = sqlite3.connect('/opt/omniforge/data/omniforge-backup.db')
src.backup(dst)
dst.close(); src.close()
"
docker cp omniforge:/opt/omniforge/data/omniforge-backup.db "./omniforge-$(date +%F).db"
docker exec omniforge rm /opt/omniforge/data/omniforge-backup.db
```

The temporary copy is written into the data volume rather than `/tmp`, because `docker cp` can't read files from a tmpfs mount.

Check the copy:

```bash
python3 -c "
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
print(db.execute('PRAGMA integrity_check').fetchone()[0], db.execute('SELECT COUNT(*) FROM tools').fetchone()[0], 'tools')
" "omniforge-$(date +%F).db"
```

Expected output: `ok 5 tools` (with your own count).

### Offline volume backup

```bash
docker stop omniforge
docker run --rm -v omniforge_data:/data:ro -v "$PWD":/backup alpine \
  tar czf "/backup/omniforge_data-$(date +%F).tgz" -C /data .
docker start omniforge
```

Compose prefixes volume names with the project name (for example `myproject_omniforge_data`). Find yours with `docker volume ls | grep omniforge`. For bind mounts, such as Unraid's `/mnt/user/appdata/omniforge/data`, stop the container and copy the directory.

### Scheduling

Save the online-backup commands above as a script, for example `/usr/local/bin/omniforge-backup.sh`. A nightly host cron entry that runs it is enough for most set-ups:

```text
15 3 * * * /usr/local/bin/omniforge-backup.sh >> /var/log/omniforge-backup.log 2>&1
```

Keep several generations, and store at least one off the host.

## Restore

1. **Stop** the container so nothing writes during the swap:

   ```bash
   docker stop omniforge
   ```

2. **Replace the database**, remove any leftover journal, and make sure UID 1000 owns the file:

   ```bash
   docker run --rm -v omniforge_data:/data -v "$PWD":/backup alpine sh -c '
     rm -f /data/omniforge.db-journal &&
     cp /backup/omniforge-2026-10-16.db /data/omniforge.db &&
     chown 1000:1000 /data/omniforge.db'
   ```

   > [!WARNING]
   > Always delete `omniforge.db-journal` when you put a different database file in place. SQLite treats a leftover journal as unfinished work and would try to roll it into the restored file.

3. **Start** it again and reload the dashboard:

   ```bash
   docker start omniforge
   ```

4. **Check.** **Tools** should list everything, and `curl -s http://localhost:8000/api/tools | jq '.tools | length'` should match your count.

Restoring keeps each tool's internal `id`. Package caches are keyed by that ID, so they still match if the `omniforge_lib` volume survived. If it didn't, each tool reinstalls its packages on its next run. Do that from the dashboard before clients call the tools.

## Moving to another host

1. Take an online backup on the old host.
2. Create the volumes on the new host and restore the file as above.
3. Optionally copy the `omniforge_lib` volume as well, to skip reinstalls. Both hosts must be `amd64`.
4. Start the container with the same `OMNIFORGE_API_KEY`, or update your clients.

## Exporting and importing individual tools

`GET /api/tools` returns everything, source code included, as JSON. It's a handy portable export:

```bash
curl -s http://localhost:8000/api/tools > tools-export.json
```

To import into another instance (needs `jq`):

```bash
jq -c '.tools[] | {name, description, language, code,
       requirements: (.requirements_json | fromjson),
       json_schema: (.json_schema_json | fromjson),
       is_active}' tools-export.json |
while read -r tool; do
  curl -s http://new-host:8000/api/tools -H 'Content-Type: application/json' -d "$tool"
  echo
done
```

Imported tools get **new IDs**, and so new package caches. Names that already exist are rejected with HTTP 409 and left unchanged.

> [!CAUTION]
> Exports and backups contain all your tool code. If any tool has a credential written into its code (it shouldn't), the backup has it too. Store backups as carefully as the server.

---

← [Home](Home.md) · [Next: Troubleshooting and FAQ →](Troubleshooting-and-FAQ.md)
