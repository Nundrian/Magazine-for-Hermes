# 0.1.0-hermes.rc2: follow Hermes appearance

The original Follow Hermes option inherited text colour but referenced Magazine/Pi
surface variables that Hermes does not define. Backgrounds and borders therefore
became transparent, making fields, panels and tabs disappear into the host canvas.

Host mode now explicitly maps the actual installed Hermes theme tokens for the
canvas, cards, secondary surfaces, input/panel borders, selected tabs, primary
buttons, errors, success, text and code. It also respects the native theme font
settings. These are CSS-variable references, so switching Hermes themes updates
Magazine immediately without copying a palette or writing Hermes settings.

Follow Hermes theme is the default for a new browser. Explicit Magazine dark/light
choices remain available and remembered; an existing explicit choice is respected.
The user's existing Follow Hermes selection continues to work after refresh.

Validation used the actual isolated native dashboard in Firefox and Chromium,
switching Hermes Teal, Ember and Midnight through Hermes' own theme picker. Both
browsers verified that the canvas matches the host, panels/fields/tabs have visible
borders and distinct backgrounds, selected tabs remain distinct, changes apply
immediately, manual palettes remain independent, and Follow Hermes survives refresh.
Screenshots were visually reviewed, including the Ember palette from the reported
defect. Device-scaled CSS borders are accepted as visible rather than requiring an
exact one-device-pixel result. No model inference or production theme changes were
used for these checks.

Evidence: `C:\Codex\Hermes Magazine\evidence\theme-update`.
Reproduce the isolated browser check with `scripts/browser_theme.py --browser
firefox --output <directory>` or `--browser chromium`. The script targets only
`magazine-hermes-install-test` on port 9149.

The execution engine, recovery/scheduler behavior, prepared cartridges and native
conversations are unchanged. The rc1 runtime acceptance remains documented in
ACCEPTANCE.md; rc2 is this appearance correction and version metadata.
