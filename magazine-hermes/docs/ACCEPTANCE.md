# Acceptance: 0.1.0-hermes.rc1

Test date: 21 November 2026. This report separates runtime contract checks from
actual task correctness. Tests used small purpose-built cartridges. The user
cancelled the 187-cartridge scenario; it was not run or replaced with a claim of
large-workflow acceptance.

## Environment and evidence

The disposable host used the same installed Hermes 0.23.3 image/build recorded in
`ARCHITECTURE.md`, separate Docker volumes, loopback port 9139 and a disposable
Windows workspace. The installation lifecycle used a second independent volume
and port 9149. Existing projects and other applications were not used as fixtures.

Actual local inference used the original installed weights:

- `custom/hf.co/AtomicChat/Ornith-1.5-35B-A3B-GGUF:Q4_K_M`.
- `custom/bonsai-2:27b` (installed Q2_0).

The configured endpoint was the user's existing local Ollama compatible endpoint.
No weights, quantisation, provider credentials or context settings were changed.
Earlier explicit development probes also used installed Ornith 9B Q8_0 and failed
some native tool/final-format cases. They are not reported as acceptance passes.
There was no silent model substitution within an attempt or run.

`acceptance-results.json` contains each selected real run's model, provider,
attempt/session identity, outcome, times, observed native tool names and reported
token counts. Missing usage dimensions remain null; partial coverage is labelled.
Raw native conversations, full ledgers, histories and artifacts remain private in
the disposable volumes/workspace and are excluded from the release.

Local evidence root: `C:\Codex\Hermes Magazine\evidence`. Main native test volume:
`magazine-hermes-test-data`. The metric-only report deliberately contains no raw
conversations, tool arguments, private prompts or credentials.

## Verified outcomes

| Scenario | Acceptance evidence and outcome |
|---|---|
| DONE, saved sessions and file handover | Run `e5898b9d4d22`: two distinct fresh native worker sessions, actual write_file/read_file calls, committed handover and independently asserted 15-byte/24-byte output files. First cartridge passed on attempt 1; second passed on attempt 3 after two final-format omissions. |
| Exact two-model routing and empty tools | Run `8a06b5c6f6d5`: Ornith 35B then Bonsai 27B, distinct native sessions, exact ledger assignments and no model-facing tools. The historical second cartridge label `ornith9` is only an ID; its actual assigned model is Bonsai as recorded. |
| Authoritative HALT | Run `23970f6fe563`: one HALT attempt; downstream cartridge never admitted. Incidental/quoted HALT cases also pass deterministic parser checks. |
| Lost publication then retry | Run `f7ec533f063e`: test-only publication deletion after a genuine completed native response; fresh retry succeeds, two distinct sessions. |
| Five-attempt exhaustion | Run `88d8e585b0c5`: five genuine fresh sessions with injected publication loss, expected HALTED outcome; an explicit sixth attempt is refused. |
| STOP | Run `32240825b6b5`: real terminal wait interrupted, worker/descendant termination confirmed, downstream never admitted. Earlier run `b5ba9678a756` also supports the two-browser live-view test. |
| Per-attempt timeout | Run `8e6f7af09734`: real terminal sleep, 40-second explicit fixture budget, ATTEMPT_TIMEOUT after confirmed termination, one allowed attempt and no downstream dispatch. Default policy remains 1,800 seconds and five attempts. |
| Antiloop | Run `cd325e66a65a`: three repeated genuine native missing-file errors produce LOOP_DETECTED, confirmed interruption and no downstream dispatch. Complete annotated native errors remain in Chats. |
| Manual recovery | Run `482684a0767b`: predecessor passes; dependent HALTs waiting for an operator flag; explicit recovery stays READY; explicit Start passes the dependent without replaying the predecessor. |
| Sequential | Runs `1386cff2e007`, `0fda827b5d2c`: observed A1,A2,B1,B2 order; recorded attempt intervals do not overlap. |
| Round Robin | Runs `4168fe94475f`, `20a575515ee5`: observed A1,B1,A2,B2 order at committed boundaries; no overlapping attempt intervals. |
| Engine crash | Run `3e8b8701813b` and queued `604b5555980e`: actual isolated engine killed during native tool work; UNKNOWN blocks Start, queue/chats retained, explicit reconciliation and recovery required; no automatic inference. |
| Container restart | Actual idle test-container restart retained completed run, exact ledger and artifact hashes, chats and scheduler state; no automatic inference. It did not restart Docker Desktop. |
| Exports and authentication | Actual ZIP downloads independently checked for exact artifact bytes and valid archives; full JSONL contains distinct saved sessions and execution history; separate ledger/history downloads parse. Missing/wrong native dashboard tokens are denied; engine socket is 0600. |
| Installer lifecycle | Actual install, update, rollback, uninstall and reinstall in its separate volume. Sentinel data and consistent online SQLite backups remain readable. All unrelated configuration keys are preserved. |
| Native service permissions | Final installer tests drop to the real home-owner UID/GID and successfully use private IPC. Magazine code/state/global-lock ownership matches the native runtime without broad home ownership changes. |

## Browser acceptance

The actual native Hermes dashboard was tested in Playwright Firefox and Chromium,
at 1440×1000 desktop and 520-pixel narrow width. Final browser journeys cover ZIP
import including magazine.yml, shared/individual/checkbox/group model assignment,
explicit model-plan Apply, empty default tools, Prepare without inference,
single/multiple cartridge selection, the five-attempt ledger, long errors, missing
and partial tokens, complete Chats navigation, inert HTML, JSONL download,
recoverable deletion, light/dark appearance and responsive layout.

The five-attempt/long-error display fixture is explicitly synthetic; genuine
five-attempt execution is separately proved by the publication-loss test.
Both browsers also restored run/panel/cartridge/expanded-attempt selection across
refresh without inference. Both switched live → historical → live while the
native terminal cartridge remained active, without page errors.

Screenshots were reviewed against the Open WebUI reference walkthrough: compact
blue panels, original control hierarchy, native host navigation and the amended
four-column single-cartridge ledger. Hermes supplies the surrounding shell.
Final browser reports/screenshots are in `evidence/firefox-final` and
`evidence/chromium-final`; persistence/live reports are separate.

## Deterministic and native-storage checks

Fourteen safety tests cover strict DONE/HALT/native result parsing, duplicate-key
and nonfinite JSON rejection, the five-attempt ceiling, separate transient I/O
retries, reported-zero/unavailable/partial token states, secret/reasoning
filtering, structured Antiloop, malicious ZIP paths/links/collisions, hardened YAML,
handover identities, read-back/tamper rejection, process locking, SQLite authority
after corrupt JSON cache, and durable-commit recovery without model replay.

Additional actual native-storage checks create a disposable compression lineage,
read the complete visible root-to-tip history, verify final publication reads the
active tip, and exclude reasoning fields. Real-process checks exercise timeout
cleanup without inference and inject a cleanup exception to prove UNKNOWN is
always persisted. Native result normalization retains unknown suffixes unchanged.
Native plugin validation passes with the version-sensitive warnings described in
`ARCHITECTURE.md`. JavaScript syntax checks pass.

## Failed probes, corrections and limits

- Run `c9efa0561893` satisfied the execution contract but failed external task
  acceptance: the model wrote literal backslash-n text. Its files/ledger are
  retained, including `basic-failed-literal-newline-report.json`. A new fixture
  with explicit byte/line-feed requirements passed as documented above. Magazine
  validates declared file existence, identity and integrity; a model's claimed
  checks do not establish arbitrary semantic correctness.
- Timeout run `60de57771ac9` exposed a cleanup exception with a surviving worker.
  The global flock refused a second worker. The exact recorded disposable worker
  and descendants were killed, uncertainty explicitly reconciled, cleanup changed
  to asynchronous process observation, and both real timeout and STOP retests
  passed. An injected cleanup exception now always saves UNKNOWN before exit.
- Antiloop run `00dce496864a` exposed changing Hermes loop-count suffixes masking
  identical errors. Canonical structured JSON comparisons now exclude only known
  Hermes loop annotations, preserve full raw visible text, and distinguish nonzero
  terminal exits as errors. The native retest passed.
- Early publisher-tool development was unreliable through Hermes' progressive
  tool wrapper on the 9B model. The final adapter reads strict saved native final
  records and adds no model-facing publisher tool. Failed probes are retained.
- Browser harness selection/expansion mistakes were corrected; their failed runs
  are not substituted for the final passing browser reports.
- Initial normal-host smoke testing found the private Magazine directory owned by
  Docker's root installer rather than Hermes' service UID. The installer was
  corrected, tested after dropping to the native UID/GID, and updated through the
  same backed-up installation procedure. Normal-host outcomes are separate below.
- A sealed-ZIP smoke check caught an overly broad `dist` exclusion that removed
  dashboard assets even though source-bound browser tests passed. The build filter
  was corrected and release verification now requires the manifest entry and
  frontend module. The extracted release is installed and browser-tested separately
  from the source-bound test host.
- No claim of arbitrary complex-project correctness, arbitrary hostile terminal
  containment, multi-user tenancy, Docker Desktop daemon restart, power-loss
  durability on every host filesystem or compatibility with another Hermes build.
  Model-driven context compaction itself was not forced; the native storage
  lineage contracts were exercised directly.

Normal-host installation and preservation checks are reported separately in
`C:\Codex\Hermes Magazine\Magazine-for-Hermes\DEPLOYMENT.md`.
Authenticated normal-host smoke checks passed in Firefox and Chromium using the
existing basic/password provider. The native tab connected, discovered 23 models
and 20 toolsets, and retained zero active Magazine runs. No normal-host inference
was started. The container/image/mounts/ports/restart policy, non-plugin settings,
gateway/dashboard PIDs and existing native session count remained unchanged.
