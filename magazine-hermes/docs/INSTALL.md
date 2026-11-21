# Windows Docker Desktop installation, updates and rollback

Use the existing Linux-container Hermes installation. No Docker socket mount,
Windows-wide mount, new model weights or image rebuild is needed. The verified
image/build is pinned in `compatibility.json`; changed builds are refused until
their contracts and acceptance have been checked.

## Install or update

1. Extract the release ZIP. Keep the extracted `magazine` directory accessible to
   Windows. Open PowerShell 5.1 in that directory.
2. Finish or explicitly stop active Magazine work. Reconcile any UNKNOWN attempt.
3. Run:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-Magazine.ps1 -Container hermes
   ```

The script stages only this plugin, checks compatibility, refuses live/uncertain
work, blocks admission during maintenance, and backs up affected configuration,
previous code, plugin state and root native SQLite stores under
`/opt/data/backups/magazine/<UTC timestamp>`. The database copies use SQLite's
online backup API. Credentials remain inside the private existing Docker volume.
The script preserves all unrelated configuration keys, plugins, volumes and mounts.
It enables only `magazine` in the Hermes plugin lists. No inference is started.
Docker normally executes installation as root while Hermes runs as the volume's
owner. The installer assigns Magazine code, private state and execution lock to
that native owner, preserving file modes. It does not recursively change the
Hermes home or unrelated plugin data. The isolated lifecycle test also opens the
private IPC socket after dropping to the actual service UID/GID.

4. Reopen the dashboard. Its discovery rescan endpoint is
   `/api/dashboard/plugins/rescan`. The installed build can mount newly enabled
   plugin routes lazily. If an older compatible dashboard needs a restart, restart
   **only its dashboard service** after checking service supervision; do not
   recreate the Hermes container or replace `hermes-data`.
5. Verify Magazine appears in navigation, exact models/toolsets load, retained
   state is visible, and all prepared runs remain READY until Start.

The source directory for this implementation is
`C:\Codex\Hermes Magazine\Magazine-for-Hermes`. The task's existing writable
workspace was used instead of requiring a new Windows mount/directory permission.

## Uninstall while retaining data

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-Magazine.ps1 -Container hermes -Operation uninstall
```

The plugin code moves into its private backup, enablement is removed, and runtime
state remains in `/opt/data/plugin-data/magazine`. Native conversations and Windows
workspace files are preserved. Refresh plugin discovery/reopen the dashboard.
Do not delete the Docker volume.

## Roll back code

Use the exact backup path printed by the update:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-Magazine.ps1 -Container hermes -Operation rollback -Backup /opt/data/backups/magazine/REPLACE_WITH_EXACT_TIMESTAMP
```

Rollback restores the previous plugin code through the same idle/backup procedure;
it does not overwrite newer state or unrelated Hermes settings. If rolling back
across a future state-schema migration, inspect that release's migration notes and
use a separately restored test volume first. There is no automatic destructive
state downgrade. First-install rollback uses uninstall because there was no
previous plugin.

## Isolated testing and release

The acceptance host uses `magazine-hermes-test-data`, a disposable workspace, and
loopback port 9139. Production remains a separate container/volume. The test token
is generated inside that private volume and never goes into reports/releases.
`tests/start_dashboard.py` is an isolated test harness, not a production launcher.
Use Docker `--init` for a new isolated host to reap children cleanly.

Safety tests (inside the isolated container):

```powershell
docker exec magazine-hermes-test /opt/hermes/.venv/bin/python /opt/data/plugins/magazine/tests/test_safety.py
```

Real inference tests are explicitly labelled in `tests/acceptance.py`,
`tests/scenarios.py` and `tests/fault_scenarios.py`; use only a disposable test
workspace and authorised installed models. Browser tests require Playwright and
Firefox/Chromium. They read the isolated token into memory and do not print it.

Build the release using `python scripts/build_release.py`. It includes only code,
tests, docs, examples and the vendored pure-Python PyYAML 6.0.3 source/license.
It excludes runtime state, private prompts/conversations, test workspaces,
credentials, reference checkouts and test dependencies. `SHA256SUMS.txt` identifies
the ZIP; `SOURCE-SHA256.json` inside it identifies every packaged source file.
