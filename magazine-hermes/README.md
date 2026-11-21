# Magazine for Hermes 0.1.0-hermes.rc2

Load a workflow ZIP, review the cartridge prompts, assign exact models and Hermes
toolsets, then **Prepare workflow**. Preparation saves a READY snapshot. Choose
**Start workflow** explicitly to execute. Refresh, import, restoration and recovery
preparation never start inference.

Magazine follows the current Hermes theme by default, including panel, field,
border, tab, button and text colours. Changes in Hermes apply immediately. The
Appearance menu retains optional Magazine dark/light palettes and remembers an
explicit choice per browser.

Overview, Workflows, Set up, Ledger, Chats, Results and Manage preserve the Magazine
application inside Hermes. The detailed ledger shows one cartridge and every
attempt. Chats includes live and historical visible native session records.

The current compatibility gate requires Hermes **0.23.3**, installed code identity
`caafe5389ae585ef77387a962aee05b1bcf17029`. A different image is refused pending
compatibility verification. See [architecture](docs/ARCHITECTURE.md).

Install from Windows PowerShell 5.1:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-Magazine.ps1 -Container hermes
```

Read [INSTALL.md](docs/INSTALL.md) first for backups, maintenance, updates,
rollback and preserving the Docker volume. Build a reproducible release with
`python scripts/build_release.py`. Run Linux safety tests with
`/opt/hermes/.venv/bin/python tests/test_safety.py` inside an isolated container.

This is a single-operator dashboard application. Selected terminal/code tools run
with the Hermes container's authority; a tool allowlist is not an OS sandbox.
Magazine neither changes provider credentials nor downloads model weights.
