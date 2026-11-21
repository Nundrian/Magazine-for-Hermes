# Second critical audit

Reviewed the final composition against the installed source and independently
observed test outcomes, rather than treating completed assistant messages as
acceptance. The references remain clean Git checkouts. No core Hermes files are
patched or rebound.

| Boundary reviewed | Finding / final treatment | Evidence |
|---|---|---|
| Concurrent admission | One persistent scheduler authority, owner flock and inherited global execution flock; exact admission written before inference bytes. | Sequential/Round Robin intervals, process-owner test, global lock refusal during the timeout defect. |
| Timeout and cancellation | A synchronous descendant-wait failure could previously leave a worker without UNKNOWN. Replaced with asynchronous observation/reaping of the owned child; any cleanup exception persists UNKNOWN. | Real timeout and STOP retests; actual subprocess cleanup plus injected cleanup-error test. |
| Crash/restart | Restored queue entries never dispatch automatically. Unknown admitted work blocks every Start. Reconciliation moves lost-owner RUNNING runs to HALTED before recovery. | Actual engine crash and idle container restart; corrupt-cache SQLite restoration test. |
| Commit/advance crash | Existing committed ledger result must be verified and returned before considering a new attempt. No completed predecessor inference replay. | Crash-after-commit and tamper regression; manual recovery real-model test. |
| Native transcript authority | Deprecated SessionDB facade replaced with typed persistence. Display follows compression lineage; final publication reads active tip. Only visible rows/callbacks are projected. | Native lineage fixture and real fresh-session file/routing tests. |
| Tool isolation | Toolsets expanded and frozen at preparation; actual worker schema set checked. No publisher/controller tool is added. | Real no-tools routing; installed tool bridge source inspection and exact surface comparisons. |
| Antiloop | Changing native loop annotations masked repeated error signatures. Compare canonical JSON only when the trailing text is entirely recognised native annotations; preserve original output. | Three repeated real read_file errors now terminate with LOOP_DETECTED. Unknown suffix regression stays opaque. |
| Result authority | Native saved final row, strict closing status/payload, controller identities, publication receipt/read-back, commit hashes and independent file bytes. | Publication-loss retries/exhaustion, identity/tamper tests, real file acceptance. |
| Task correctness | Execution-contract success can coexist with incorrect file content. This is stated in UI/docs; native tool evidence and external task assertions are separate. | Literal-newline failed fixture retained; new explicit-byte fixture passes. |
| Persistence and deletion | Native SQLite and checkpoints stay on Linux volume; imported templates independent of immutable prepared runs. Managed state moves to trash; Windows workspace remains in place. | Installation lifecycle, browser deletion/restoration and cross-filesystem code review. |
| Exports and untrusted text | Anchored files, artifact hash recheck, inert text rendering, redaction of known credentials/recognised secret fields. No reasoning projection. | ZIP/JSONL/history checks, malicious input tests and both browsers' XSS fixture. |
| Host impact | Native plugin routes, asynchronous bridge, private 0600 socket, separate execution process. Provider config remains unchanged and exact build is gated. | Native plugin validator, authentication checks, normal-host baseline/preservation report. |
| Runtime permissions | Initial root-only installer tests missed the dashboard service UID. Installer now assigns only Magazine code/state/global gate to the native home owner and preserves modes; unrelated data is untouched. | Full isolated lifecycle plus actual service-UID private IPC, followed by normal-host authenticated browser checks. |
| Release contents | An overly broad `dist` exclusion initially omitted frontend assets; the filter is corrected and manifest entry/module presence is now mandatory. Explicit source path/type allowlists and normalized metadata exclude private runtime data. | Required-assets/source/reproducibility checks plus browser tests of the actual extracted ZIP installation. |

Remaining limits are recorded in ACCEPTANCE.md and SECURITY-RECOVERY.md. Terminal
tools retain container authority; a malicious privileged detached process is not
an OS-sandbox guarantee. Multi-profile admission fails closed through the global
lock, rather than silently merging independent profile queues. Multi-user tenancy
is not implemented. Compatibility is asserted only for the tested stamped build.

Native `hermes plugins validate` passes but warns about proc-access in the
inherited Linux no-replace rename helper and imports outside the plugin catalog's
narrow allowlist, including the documented AIAgent embedding seam. The installer
and worker enforce exact version/code identity and required signatures. These
warnings are disclosed compatibility risks, not an assertion of future support.
The validator also prints the base image's existing pnpm artifact synchronization
warning; this plugin does not rebuild or alter the image's frontend bundle.
