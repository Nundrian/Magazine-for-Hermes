# Architecture and installed compatibility

## Owning sources

Reference identities are pinned in `reference-identities.json`. The Open WebUI
baseline is 0.3.0-scheduler.rc1; the Pi baseline is 0.1.0-pi.8-ui.3. MIT attribution
is retained. The copied independent core, ZIP importer, handover verification,
recovery decisions, Antiloop, ledger, model-plan validation and read-only frontend
were adapted from those sources. Neither reference checkout is modified.

Visual authority:
[Open WebUI walkthrough](https://github.com/Nundrian/Magazine/blob/main/docs/images/magazine-simple-0.3.0-walkthrough.webp).
The host shell is Hermes; Magazine retains the blue panel palette, typography,
control hierarchy and explicit workflow journey. The amended ledger replaces
the long overview with a four-field selected-cartridge summary and expandable
complete attempt evidence. The seven-panel navigation and Chats viewer retain
the later Pi improvements.

## Installed Hermes surfaces

Inspected image ID: `sha256:3e9fe4c6ef36490f43aa0d0d80f9df64e9c92a576eee3042f1a97c8813c05355`.
Installed stamp: Hermes 0.23.3 at `caafe5389ae585ef77387a962aee05b1bcf17029`.
The mutable `latest` tag is not a compatibility assertion. Source inspection and
real execution apply to this exact installed build; online `main` is a separate
reference recorded in `reference-identities.json`.

| Surface | Installed finding and decision |
|---|---|
| Dashboard SDK | `window.__HERMES_PLUGIN_SDK__` and `__HERMES_PLUGINS__.register`; native Magazine tab verified in the real dashboard. No host bundle rebuild. |
| Backend routes | Manifest `api` loads FastAPI router under `/api/plugins/magazine`; host authentication and enabled-plugin gates remain in force. |
| Python plugins | `plugin.yaml` and `register(ctx)` supported. Magazine adds no global orchestration tools to worker surfaces. |
| Hooks | Lifecycle/tool hooks exist, but are observations rather than orchestration ownership. Magazine owns its independent state machine. |
| Gateway RPC | Installed TUI gateway source exposes native session/model/interrupt/event interfaces. Not required for Magazine execution; it is not silently patched. |
| REST Sessions/Runs | Installed dashboard session routes and `/v1/runs`, events, stop, approval, unknown-resolution and capabilities surfaces exist. API-server exposure depends on gateway configuration. Magazine does not enable a new API server or depend on an unconfigured listener. |
| Python execution | Documented `run_agent.AIAgent.run_conversation` embed, exact constructor overrides, native persistence and tool callbacks. Chosen for bounded process ownership and verified toolsets. |
| Storage | `plugins.plugin_storage.plugin_data_dir('magazine')`; Linux-native persistent volume. Native `persistence_assembly.open_persistence(profile_scope())`, typed session/message reads and compression-lineage tip. No deprecated `SessionDB` facade. Upgrade requires adapter testing. |

Primary documentation examined:
[dashboard extension](https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard),
[plugins](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins),
[programmatic integration](https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration),
[agent embedding](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop),
[API server](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server).
FreeFirst returned an MCP 429 connection error; Firecrawl was used as authorised
fallback. Installed source and runtime acceptance control the compatibility claim.

## Composition

```text
Hermes authenticated dashboard
  └─ Magazine tab + FastAPI bridge (async, blocking work offloaded)
       └─ private Unix socket (0600, no TCP listener)
            └─ one Magazine owner daemon (kernel flock)
                 ├─ SQLite scheduler checkpoint + journal
                 ├─ authoritative core run/STOP/recovery records
                 ├─ immutable prepared prompts/configuration
                 └─ one fresh Hermes worker process per attempt
                      ├─ exact model/provider; fallback disabled
                      ├─ selected toolsets, expanded functions checked
                      ├─ native saved session + visible transcript projection
                      └─ controller publication and verified artifact commit
```

The process owner lock prevents competing engines for the same state. A second
Linux flock gates inference across Magazine processes/profiles sharing a Hermes
root. The unified scheduler is per selected profile; another profile cannot
execute concurrently and fails closed rather than joining that queue silently.
Normal use and acceptance are a single operator/profile.

Hermes configuration and credentials remain under the existing Hermes mechanisms.
Model discovery uses its inventory and the configured compatible endpoint's exact
`/models` IDs. No cloud prompt dispatch occurs during discovery. Context/provider
parameters are inherited, not rewritten. Only the model/provider assignment and
tool surface are selected for a worker. Runtime inference is never silently routed
to a different model. Tools are Hermes **toolsets**, with their expanded function
names shown. No toolset is selected by default; independent cartridge overrides
can explicitly select an empty set. Preparation freezes the expanded set and a
changed set is rejected before inference. The installed tool-search bridge also
enforces the selected underlying toolsets; this was inspected in installed source.

## Hermes result adapter: hermes-v1

Workflow ZIP format remains schema 1.0. `magazine.yaml` and `magazine.yml` are
accepted, including a single enclosing folder. Extended declarations retain
`artifacts.inputs/outputs`, prior-cartridge selectors, retry policy and Antiloop.
Unsupported fields are rejected rather than ignored as if enforced. Constraints
and artifact review fields inherited as advisory are explicitly listed in preview.

The native adapter publishes **strict structured final native-session data** to
the existing `result_file_v1` envelope. A worker ends with:

```json
{"status":"DONE","magazine_result":{"result":{"step":"first","verified":true,"files":[],"checks":[],"note":"Complete deliverable text"}}}
```

The older payload-object plus closing `{"status":"DONE"}` form is also accepted.
Fences or prose before the authoritative closing object are presentation only.
Duplicate keys, non-JSON numbers, missing payloads and incidental quoted statuses
are refused. An authoritative closing HALT prevents publication/advancement.

This differs from Pi's extra publisher tool: the installed Hermes progressive
tool-discovery wrapper caused observed malformed calls on the 9B model. Reading a
validated structured native final record removes that wrapper and preserves a
genuinely empty toolset. Magazine supplies run/cartridge/attempt/session identities,
publishes atomically, emits a receipt, reads back SHA-256, validates declarations,
archives the visible native transcript and copies declared output bytes into a
Linux-native committed checkpoint. Consumers recheck those checkpoint bytes.
Publication does not certify the semantics of the model's answer or claim that a
tool ran. Actual native tool events and independently checked files remain the
execution evidence. Ordinary code blocks are never counted as tool execution.

## Persistence and transcripts

Executable code lives in `plugins/magazine`. State lives separately in
`plugin-data/magazine`. The scheduler's SQLite `synchronous=FULL` transaction is
authoritative; its JSON file is an inspectable export cache. Core state and result
commit records retain fsync/read-back semantics. The Windows workspace holds
accessible `magazine-runs/<run>/<cartridge>` outputs; databases and immutable
checkpoints stay on the Linux volume. Imported workflows and prepared snapshots
are independent. Deleting a template does not delete its saved runs.

Chats is a read-only projection of actual native saved rows plus visible native
stream/tool callbacks while DB flushes catch up. The original Hermes conversation
remains in native storage. No reasoning field is copied. Native final rows replace
temporary stream projections; generation/cursor reset supports reconnection and
replay. Switching chats never attaches an input channel to the worker.

Antiloop compares actual tool arguments and canonical structured results. Hermes
appends changing repetition-count notes to repeated tool errors; the adapter
excludes only recognised native loop annotations from the comparison hash while
retaining full original text and a raw hash. Unknown suffixes remain opaque.
Nonzero native terminal exit codes are also recorded as error outcomes.

Display reads follow the native compression lineage and include compaction-archived
visible messages. Final publication reads the active lineage tip, records its native
session/message identity and hashes that saved final text. The stable root session
continues to identify the attempt. A native-storage fixture verifies this boundary;
bounded real-model tests do not force an actual model context compaction.

Token totals use native cumulative reported counters, once per attempt. Zero is
known only when Hermes recorded a usage object. Missing cache dimensions and
per-call coverage are labelled unavailable/incomplete; no token estimates are
added. Processing time sums actual attempt intervals, including retries; wall-clock
age since preparation is shown separately in run details.
