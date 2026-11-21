# Disposable examples

Run `python scripts/build_release.py` to produce ZIPs for these workflows. Import
one ZIP in Magazine, assign an exact installed model, review tools and Prepare.
Only Start executes inference.

`two-files` needs the Hermes `file` toolset. Check actual bytes after completion.
`text` and `halt` need no tools. `halt` must leave `downstream` unstarted.
All file outputs use this run's Magazine-owned workspace directories.

These examples are bounded demonstrations, not acceptance evidence. The real
inference and fault-injection harnesses are in `tests/`; their observed outcomes
are recorded separately in `docs/ACCEPTANCE.md`.
