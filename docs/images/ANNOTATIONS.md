# Screenshot sources and annotations

The seven `raw/*.png` files are unedited Playwright captures of a real, isolated
Hermes dashboard, not designed interface mockups. The completed two-cartridge run
is `e5898b9d4d22`; its actual saved tool/chat evidence was selected for the guide.
Setup shows configuration preview. No workflow was started for the captures.
The [capture manifest](raw/capture-manifest.json) records the run and target control
coordinates. The [capture script](../../tools/capture-guide.py) also asserts that
the attempt count is unchanged before and after capture.

The seven `*-annotated.png` files were edited with the **built-in imagegen** tool
using the raw screenshot as the edit target. Added numbered callout cards and
mint curved arrows explain the controls; Workflows established the visual style
used as a reference for the remaining images. The tool can re-render fine text
and resize the image, so the annotated versions are illustrations, not pixel-exact
acceptance evidence. Use the raw originals for exact text, recorded values and layout.

[Per-tab annotation prompts and targets](annotation-prompts.json) document the
annotation recipe; [prompt builder](../../tools/image-prompts.py). The Workflows
pilot established the style before this common prompt recipe was produced.
Live CPU/RAM readings are momentary environment readings, not performance benchmarks.

| Tab | Annotated illustration | Original capture |
|---|---|---|
| Overview | [PNG](overview-annotated.png) | [PNG](raw/overview.png) |
| Workflows | [PNG](workflows-annotated.png) | [PNG](raw/workflows.png) |
| Set up | [PNG](setup-annotated.png) | [PNG](raw/setup.png) |
| Ledger | [PNG](ledger-annotated.png) | [PNG](raw/ledger.png) |
| Chats | [PNG](chats-annotated.png) | [PNG](raw/chats.png) |
| Results | [PNG](results-annotated.png) | [PNG](raw/results.png) |
| Manage | [PNG](manage-annotated.png) | [PNG](raw/manage.png) |
