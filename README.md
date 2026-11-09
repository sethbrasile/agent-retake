# agent-retake

Make footage from a coding-agent conversation you already had. Ask Claude Code or Codex to find the session, propose a few beats and pace them to your narration. You get a separate silent MOV for each beat, with a terminal window you can position over your own desktop background in the edit.

Retake reads Claude Code, Codex, pi and Grok Build sessions. A hand-editable YAML storyboard connects the conversation to the footage. Review the outline, sensitive strings and preview from chat before the final render.

## Set up on Linux

Install Python 3.11 or later, uv, FFmpeg and ffprobe. Your FFmpeg build needs the `prores_ks` encoder for transparent MOV and `dnxhd` for optional opaque 4K output.

```sh
git clone https://github.com/sethbrasile/agent-retake.git
cd agent-retake
uv sync --locked
uv run playwright install chromium
uv run retake --help
```

For a local wheel, run `uv build` and then `uvx --from ./dist/agent_retake-0.1.0-py3-none-any.whl retake --help`. Install from source or the local wheel until a PyPI release is published. The distribution is `agent-retake` and the command is `retake`.

The checkout provides the retake skill to both harnesses. To use it from other projects, link the canonical skill into your personal skill directory. Run the applicable commands from the checkout:

```sh
mkdir -p ~/.agents/skills ~/.claude/skills
ln -s "$PWD/skills/retake" ~/.agents/skills/retake
ln -s "$PWD/skills/retake" ~/.claude/skills/retake
```

Start a fresh agent session. For example, ask “Make footage from the conversation where we figured out why the orchard harvest changed. Show me the outline first.” Give it the project directory or a transcript file and a **private episode directory outside this checkout**. Tell it where retake is installed.

## Try an invented conversation

From the checkout, set an episode directory to a new private working folder. The fixture contains a user prompt, a search and a reply.

```sh
episode="$(mktemp -d)"
uv run retake gather tests/fixtures/claude/demo.jsonl --out "$episode"
uv run retake storyboard init "$episode/sessions.json" --out "$episode/storyboard.yaml"
```

Give the first beat `start: 0` and `end: 16` in the YAML. Run the scan, inspect the rule decisions and approve them before previewing:

```sh
uv run retake scan "$episode/storyboard.yaml"
# After reviewing the proposed decisions:
uv run retake scan "$episode/storyboard.yaml" --review
uv run retake preview "$episode/storyboard.yaml" --beat 1 --html
uv run retake render "$episode/storyboard.yaml"
```

The default window is 1920×1200 at 30 fps. Each clip opens with the earlier reviewed exchanges still visible above the composer. Older messages are dimmed and scroll up as new messages arrive. Each beat includes a two-second final hold within its duration. The CLI reports each output path. Import the ProRes 4444 clip above a background in Resolve and scrub the rounded edges to check the composite on your system.

## Storyboards and private data

Gather reads explicit files, transcript directories or sessions recorded for a project cwd. Use inclusive ISO timestamps with `--since` and `--until`. Repeat `--keyword` to require all terms somewhere in the session. Each normalized message has a stable ID. Shot selectors accept one ID or `first..last` in the same session.

Each beat has a title, a cue, start/end seconds, and shots. A shot can type a prompt (`typed`), show tool names and counts (`burst`), stream a reply (`full`), show headings and short excerpts (`condensed`), or hold text (`still`). The transcript supplies the speaker for each message. In a full exchange, the user's turn types into the composer and the agent's reply streams into history. Add a `highlight` list to emphasize phrases. Trimmed passages carry an Excerpt label. Condensed shots are labeled separately. To trim one message, supply `span: [start, stop]` as zero-based character offsets into its redacted text, with an exclusive stop. If a beat exceeds readable speed, shorten it or split it.

The scan proposes replacements for identifiers and secret-shaped strings. Read the private sidecar and add editorial rules for sensitive material that needs human judgment. Retake checks the session bytes, decisions, selected shots and visible theme and storyboard text before making a preview or a clip. These checks enforce the review you record. The agent and operator decide which content may appear.

Keep the normalized sessions, summaries, private rules, previews, audio and footage outside the public checkout. A storyboard can itself disclose a cue, title, highlight, inline rule or private path. Review those before sharing it. The bundled fixtures are invented.

To retain source material longer, consider setting `cleanupPeriodDays` in Claude Code's user settings. The CLI default is 30 days; `3650` retains roughly ten years. [Claude Code retention settings](https://code.claude.com/docs/en/settings-reference#cleanupperioddays)

## Align local narration

Use `uv sync --locked --extra align` and supply a local faster-whisper model directory containing its tokenizer, configuration and converted weights. Obtain the model before starting an offline run. A model ID or a directory of original Whisper weights cannot substitute for converted CTranslate2 weights.

```sh
uv run --extra align retake align "$episode/storyboard.yaml" \
  --audio /path/to/narration.wav --model-dir /path/to/local/faster-whisper-model
```

Each cue starts its beat at the matched word. The next cue ends the preceding beat, and the final beat ends at the recording duration. Review any ambiguous cue. For manual timing, set `manual: true` with both `start` and `end` in the beat.

## Configure an episode

Put `retake.yaml` beside the storyboard. It supplies project defaults for the theme and output. Explicit storyboard fields override those defaults. The CLI's `--beat` selection limits which clips are exported. Set `output.shot` to the shot label your editor uses. The sample config sets the palette, font, dimensions and filename template. [Example configuration](examples/retake.yaml)

Set `output.full_frame: true` to also export an opaque 3840×2160 DNxHR HQ MOV. `output.background` accepts a hex color or local PNG, JPEG or WebP path relative to the storyboard. Each render uses an available take number; it preserves existing clips. The transparent window is suitable for placement, scaling and transitions in the editor.

## Development

Run `uv run pytest` for synthetic parser, redaction, browser, alignment and codec tests. Run `uv run python tests/bench_render.py` for the 20-second production-path benchmark. The editor acceptance check is a direct import and composite in Resolve Free on Linux. [Agent instructions](AGENTS.md)
