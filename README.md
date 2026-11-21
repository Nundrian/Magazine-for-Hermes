# Magazine for Hermes

Run pre-authored cartridge workflows inside the native Hermes dashboard. Each
attempt receives a fresh saved Hermes conversation, an exact model/provider and
an explicit toolset. Magazine validates and commits results before advancing.

**Current tested pre-release: 0.1.0-hermes.rc2.**

[Download the plugin ZIP](https://github.com/Nundrian/Magazine-for-Hermes/releases/download/v0.1.0-hermes.rc2/Magazine-for-Hermes-0.1.0-hermes.rc2.zip)
· [Release and example workflows](https://github.com/Nundrian/Magazine-for-Hermes/releases/tag/v0.1.0-hermes.rc2)
· [SHA-256 checksums](https://github.com/Nundrian/Magazine-for-Hermes/releases/download/v0.1.0-hermes.rc2/SHA256SUMS.txt)

## Features

- Native dashboard tab with Overview, Workflows, Set up, Ledger, Chats, Results
  and Manage.
- Shared, individual, checkbox bulk and group model assignment; exact available
  identifiers and explicit Hermes toolsets.
- Sequential and Round Robin scheduling with process-safe execution ownership.
- Verified `result_file_v1` publication, durable artifact checkpoints and guarded
  handovers.
- Five-attempt hard ceiling, separate per-attempt budgets, STOP, HALT, Antiloop,
  explicit recovery and UNKNOWN execution reconciliation.
- Persistent queue, saved native conversations, complete visible tool evidence,
  compact cartridge/attempt ledger, reported usage and processing times.
- ZIP results, complete JSONL/history exports and recoverable deletion.
- Firefox and Chromium support. Magazine follows Hermes theme colours and fonts
  by default, including visible panel, input and tab borders. Optional Magazine
  dark/light palettes remain available.

## Compatibility

This release is verified against **Hermes 0.23.3**, installed code identity
`caafe5389ae585ef77387a962aee05b1bcf17029`. The compatibility gate checks that
identity before execution. Changed Hermes builds require adapter acceptance.

The native runtime/provider configuration supplies credentials, context settings
and model weights. Selected terminal/code tools retain the container's authority.
Magazine is designed for one trusted dashboard operator. See
[architecture and compatibility](magazine-hermes/docs/ARCHITECTURE.md) and
[security and recovery](magazine-hermes/docs/SECURITY-RECOVERY.md).

## Install on Windows Docker Desktop

1. Download and extract the release ZIP.
2. Open PowerShell in the extracted `magazine` directory.
3. Finish or stop active Magazine work, then run:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-Magazine.ps1 -Container hermes
   ```

4. Reload the Hermes dashboard and select **Magazine** in the left sidebar's
   **Plugins** section. Scroll the sidebar if needed.
5. Import a bounded example ZIP, review model/tools and select **Prepare workflow**.
   Select **Start workflow** explicitly when ready.

The installer checks compatibility, refuses active or uncertain work, creates
private backups of affected configuration/state/native SQLite stores and preserves
unrelated settings. Preparing, opening and restoring work never start inference.

[Complete installation, update, uninstall and rollback instructions](magazine-hermes/docs/INSTALL.md).

## Validation

The rc1 execution baseline includes 13 selected real local-model runs and 28
attempts covering DONE, HALT, retry/exhaustion, STOP, timeout, Antiloop, recovery,
scheduling and restart. Fourteen deterministic safety tests and native storage /
process checks cover integrity and failure boundaries. Native-model acceptance
uses the installed Ornith 35B and Bonsai 27B weights.

The rc2 theme correction was checked in actual Firefox and Chromium dashboards
using Hermes Teal, Ember and Midnight, including live switching, visible controls,
manual overrides and refresh persistence. Installed release browser checks are
separate from source-mounted development checks.

- [Acceptance outcomes, failed probes and limits](magazine-hermes/docs/ACCEPTANCE.md)
- [Theme correction](magazine-hermes/docs/THEME-UPDATE.md)
- [Metrics-only acceptance results](magazine-hermes/docs/acceptance-results.json)
- [Second critical audit](magazine-hermes/docs/SECOND-AUDIT.md)

Execution-contract success and artifact hashes establish identity/integrity.
Actual task correctness still requires task-specific checks. The reports retain
this distinction and disclose untested cases, including a Docker Desktop daemon
restart. Full native conversation evidence remains in private local test storage.

## Build and source

The plugin source is in [`magazine-hermes/`](magazine-hermes/). Build from there:

```powershell
python scripts/build_release.py
python scripts/verify_release.py
```

The build creates the plugin ZIP and small example ZIPs under `dist`, with
normalized archive metadata, source hashes and SHA-256 checksums. The verification
script checks required frontend assets, source identity and repeated-build hashes.
Test commands and isolated-host requirements are documented in
[INSTALL.md](magazine-hermes/docs/INSTALL.md).

## License and attribution

[MIT](LICENSE). Magazine reuses and adapts the independent core and interface from
[Magazine for Open WebUI](https://github.com/Nundrian/Magazine) and
[Magazine for Pi WebUI](https://github.com/Nundrian/Magazine-for-Pi-WebUI).
Pinned references and copied-file identities are recorded in
[REUSE.json](magazine-hermes/docs/REUSE.json).
