# Security, interruption and recovery

## Authority and isolation

The dashboard's own authentication and enabled-plugin permission gate protects
Magazine routes. There is no separate unauthenticated HTTP API. The private engine
socket is mode 0600. The application assumes one trusted dashboard operator; it
does not add multi-tenant ACLs to Hermes. Profile home selection is propagated into
the separate process so credentials/state do not silently use the launch profile.

Each attempt has a new saved native session and an exact model/provider assignment.
Fallback substitution is disabled. Selected Hermes toolsets and their expanded
functions are checked at preparation and worker creation. No tools are selected by
default. A no-tools native final publication adds no hidden model-facing tool.
The queue/controller is never available as a worker tool.

Tool allowlists restrict model tool dispatch, not operating-system authority.
Terminal/code tools can exercise the container's configured authority. File tools
receive a worker-scoped write root for only that Magazine run's accessible output
directory; this is necessary because the image's default `/opt/data` write root
otherwise rejects `/workspace` outputs. The parent profile and other services are
not changed. Unrestricted terminal writes can bypass file-tool policy, so receipts
and hashes are integrity evidence rather than protection from such an agent.

## Input, rendering and exports

The inherited importer validates archive entries before extraction: traversal,
absolute/backslash/drive paths, symlinks/devices, duplicate/case/Unicode collisions,
file/directory conflicts, entry counts, sizes and expansion ratios. Extraction uses
anchored directory descriptors and refuses links. YAML duplicate keys, aliases,
anchors and excessive nesting are rejected. JSON rejects duplicate keys and
non-finite numbers. Inputs and model/tool text are untrusted data.

Client paths cannot select internal files. Run/template/trash/session identities
are validated and resolved from server-owned records. The browser uses text nodes
for model/tool content; code blocks and HTML strings remain inert. Hidden reasoning
fields and assistant think blocks are omitted from Magazine transcripts/exports.
Known credential values and recognised secret assignments are redacted. Release
archives are built from source-only eligible files and contain no runtime exports.

Committed artifact hashes are rechecked before consumption and export. Successful
outputs are copied to Linux-native committed storage; Windows files remain
accessible. Run deletion moves only managed Linux state into recoverable trash and
keeps workspace/project files in place, avoiding cross-filesystem rename semantics.
Workflow deletion and run deletion are independent. Neither removes user projects.

## Retry, STOP and uncertain execution

Five total attempts per cartridge is the default and hard ceiling, including the
initial attempt. The 1,800-second budget restarts for each fresh attempt. Bounded
I/O retries are separate. Completion/publication omissions may retry; authoritative
HALT does not. Tool errors remain visible. Antiloop uses structured tool calls and
results, not reasoning, incidental words, silence or model speed.

STOP halts dispatch, asks the actual agent to interrupt, tears down owned worker
processes and waits for termination. No retry is admitted while termination is
uncertain. A stopped run remains stopped; it is not a pause. Completed predecessor
checkpoints remain available for failed/interrupted-cartridge recovery.

Fresh worker admission records are persisted before inference-triggering bytes
are sent. Kernel locks are inherited into workers. Parent-death handling kills a
worker if its engine disappears. Normal final results are sent only after cleanup
of worker-owned subprocesses. Forced termination snapshots/kills known descendants
and reaps the worker. This does not claim an arbitrary privileged shell cannot
detach a process deliberately; an engine crash has external side-effect uncertainty.

An unclean engine generation with admitted work produces **UNKNOWN** and blocks
all new inference. Inspect the retained native session, attempt ledger, admission
record and any external side effects. The Overview reconciliation control requires
an explicit confirmation and refuses a known worker that remains alive. Then use
Prepare recovery and Start explicitly. Reconciliation never replays the old
admission. If side effects cannot be established, leave it uncertain and inspect
manually; do not merely delete a lock or reset a status file.

Refresh, browser closure, dashboard restart, engine restart and retained queue
restoration do not authorise continuation. SQLite restores queue order and mode;
retained entries require Start. Recovery verifies eligible state and preserves
successful predecessors. Integrity mismatches HALT; hashes establish identity,
not semantic correctness of the deliverable.

## Audit scope

The independent test suite covers policy boundaries and storage faults. Real-model
acceptance covers a bounded local workload, not arbitrary complex-project
correctness. Browser checks use the actual isolated Hermes dashboard in Firefox
and Chromium. Detailed outcomes, failed development probes and remaining limits
are recorded in `ACCEPTANCE.md`; deployment results are separate from isolated
acceptance. A Docker Desktop daemon restart is distinct from a container restart
and is not claimed without direct evidence.
