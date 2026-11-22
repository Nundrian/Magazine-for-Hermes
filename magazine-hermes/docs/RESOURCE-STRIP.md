# 0.1.0-hermes.rc3: CPU, RAM and Workspace

The bottom-right strip is present across Magazine's seven tabs and follows its
selected appearance. Its CPU and RAM percentages come from the existing
authenticated Hermes `/api/system/stats` endpoint. No monitoring service, Docker
socket mount, model tool or new HTTP backend endpoint is added.

Reads occur every five seconds while visible. Only one read can be in flight;
stalled requests are aborted, missing/error values display an em dash, and a
native zero remains zero. Timers and requests are cleaned up on unmount. Docker
figures describe Hermes' Linux environment/VM, not Windows Task Manager or GPU/
VRAM usage. Tooltips state this scope and show RAM used/total GiB.

Workspace opens a small path/results panel. It shows the mounted `/workspace`
location and a selected run's own `magazine-runs/<run>` folder, offers copying,
links to verified Results, and opens native Hermes Files in a separate tab.
The native file policy is read and explained; this Docker build locks that browser
to `/opt/data`, so a separate workspace mount may be outside it. No filesystem
policy is weakened and no arbitrary new file-reader API is added.

The feature was tested in Firefox and Chromium against native readings across all
seven tabs, Workspace/native Files navigation, narrow layout, and browser-local
fixtures for genuine zero, missing values, HTTP failure and recovery. No inference,
file edits, deletion or production theme changes were used for these checks.
Evidence: `C:\Codex\Hermes Magazine\evidence\resource-update`.

The execution, checkpoint, retry and scheduling contracts are unchanged.
