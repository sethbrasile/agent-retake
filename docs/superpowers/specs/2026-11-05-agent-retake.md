# Agent Session Replay (retake)

Public engineering edition of the approved November 5 design. This edition carries the product requirements and omits private production details.

An agent turns previously recorded coding-agent conversations into terminal-window footage for a narrated video. A research conversation, a correction and a decision should be as easy to represent as a code change. The operator drives the process from chat. The editing handoff is a set of silent clips in timeline order.

## Workflow

1. Gather Claude Code, Codex, pi and Grok Build sessions by working directory or explicit file. Support time and keyword filters. Keep sessions contiguous in start-time order, with stable message IDs, linked tool results and addressable subagents and branches.
2. Propose beats with a title and a reason each matters. The operator approves the outline. The editable YAML storyboard references message IDs or inclusive ranges.
3. Scan the private normalized conversation. The agent reviews likely secrets and identifiers, adds judgment calls and shows the proposed decisions to the operator. Require a current scan, complete decisions and review before producing any visual output. Apply the same substitutions to titles, highlights, tool activity, child sessions and every derived rendering mode.
4. Match cues to word timestamps from a local recording. Report uncertain or repeated cues. Accept manual timing. When there is no recording, the agent provides a narration outline and waits for audio.
5. Preview and then render one clip per beat. Each starts with an empty prompt and holds the last frame for a configurable two seconds by default. Narration times set the clip lengths. Overruns fail with the beat and the excess time.

## Rendering contract

Use a deterministic seekable HTML/CSS/JS page, Playwright and FFmpeg. The fixed-size terminal follows the latest line and has transparent surroundings. A neutral dark monospace theme and per-harness identity are configurable. Implement typing, full streaming, compressed tool activity with counts, condensed replies and still holds, plus highlights. Defaults are 18 typed characters per second maximum, about 250 displayed words per minute for condensed text and 1.5 seconds minimum for a burst.

Default delivery is a 1920×1200, 30 fps ProRes 4444 MOV with alpha and no audio. An optional additional 3840×2160 opaque DNxHR HQ MOV composites the window over a supplied image or solid color. A 20-second default clip must finish in under 120 seconds on the reference workstation. The editor handles scale, transitions and the desktop layer in DaVinci Resolve Free on Linux.

## Delivery and acceptance

Ship a Python distribution named `agent-retake`, console script `retake`, optional local alignment extra, an agent-operated skill, synthetic fixtures for all four harnesses and project-local theme, path and filename configuration. The CLI commands are `gather`, `scan`, `storyboard init`, `align`, `preview` and `render`. Keep production-specific defaults in the consuming project. The private acceptance run covers an actual multi-session topic, the operator's recording and redaction review, and direct import and compositing in Resolve. Public examples and test assets are independently authored synthetic material.

An editor GUI, additional harnesses, narration generation, terminal emulation, window animations, Resolve scripting and timeline export are outside v1. The approved visual-design round follows functional acceptance and changes themes and configuration.
