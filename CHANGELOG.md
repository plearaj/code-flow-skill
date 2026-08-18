# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Both the npm
package (`@htst/code-flow-skill`) and the Python package (`htst-code-flow-skill`) ship
from this repository at the same version.

## [1.1.0]

### Added

- **`--tool` names every supported host**: `claude`, `copilot`, `codex`, `antigravity`,
  `gemini`, `all`. `codex` and `antigravity` are new — `.agents/skills/` used to install
  unconditionally purely for want of a way to ask for those two hosts.

### Changed

- **`--tool claude` no longer writes `.agents/skills/`.** Claude Code reads
  `.claude/skills/` and not `.agents/`, so those four files were never opened by anything
  in a Claude-only project. Re-running the installer does not remove an `.agents/skills/`
  directory an earlier version created.

### Added — output and appearance

- **`--output files|bundle|both` on `/code-flow.map`**, default `files`. `both` adds
  `Code_Flows/code-flow.html`, one self-contained page carrying the index, every mapped
  flow and the quality report — the file to send someone. `bundle` writes that page and
  no other HTML. **No mode suppresses the JSON artifacts**, which `/code-flow.quality`
  reads. The bundle is rebuilt from those artifacts on every run, so it is never stale.
- **`.code-flow/theme.css`** — every colour the pages use, as CSS custom properties at
  a current default value (the interactive viewer's, where the scaffolds disagree),
  commented out. Uncomment and edit; your values are inlined into
  every generated page after the built-in styles. Absent or untouched, nothing changes.
  Keep both the `:root` and `[data-theme="light"]` blocks or the light/dark toggle will
  appear broken, which is why the shipped file has both. **The installer overwrites this
  file**, so version your edits or keep a copy.
- A bundle carries every flow, so it grows with your map. On a large repository it is a
  large file; the loose pages stay small, which is why `files` is still the default.
- **The detail panel now survives down to 720px viewports**, narrowing from `380px` to
  `300px` between 720px and 900px so a tablet in portrait keeps the ability to inspect a
  node. Only the minimap stays hidden below 900px — it is a navigation luxury, not the
  only way to see a node's detail. Both `templates/shared/viewer.template.html` and
  `templates/shared/bundle.template.html` carry the fix.

### Documentation — and one thing this project got wrong

- **GitHub Copilot is two surfaces, not one, and they read different files.** VS Code
  Copilot Chat reads `.github/prompts/*.prompt.md` and answers to `/code-flow.map`; the
  Copilot CLI reads both, and lists `/code-flow.map` and `/code-flow-map` side by side.
  Both were observed
  working on 2026-08-17 (VS Code 1.132.0, Copilot Chat 0.35.3, Copilot CLI 1.0.10). The
  README presented one Copilot where there are two, which is why its naming looked
  inconsistent.
- **The caveat that `1.0.0` shipped about the dotted prompt-file name is retired.** It
  said this project had "not verified and therefore does not claim" that Copilot Chat
  exposes a dotted filename as a `/`-command. It does.
- A planned `2.0.0` would have **deleted** the Copilot prompt files on the reasoning that
  the skill had replaced them. It had not: skills in VS Code Chat are still experimental
  and did not load, so that release would have left VS Code Copilot users with nothing.
  The plan was overturned before implementation by ten minutes of opening both surfaces.
  See `docs/superpowers/specs/2026-08-17-phase5-copilot-skills-only-design.md`.

## [1.0.0]

The first stable release, and a large jump from `0.2.0`. Everything below was built
across four development milestones that were never published; `1.0.0` is where they
reach a registry together.

> **A note on version numbers in `docs/`.** The design and plan documents under
> `docs/superpowers/` were written against internal milestone numbers `1.0.0` through
> `1.3.0`, and phrases in them like "has shipped since 1.0.0" refer to those milestones,
> not to a published release. Nothing above `0.2.0` was ever published. Those documents
> are dated records of what was decided when, so they have been left as written rather
> than rewritten to match this release.

### Added

- **`/code-flow.map`** — traces an execution flow from an entry point and writes
  `Code_Flows/<flow>.json`, `<flow>.md` and `<flow>.html`, registering each in
  `Code_Flows/index.json`. The JSON is the data; the other two are renderings of it.
- **Whole-codebase mapping** — `--whole-code-base` catalogues every function into
  `Code_Flows/inventory.json`, then discovers entry points and traces flows from them,
  resuming across sessions. `--detail thin|standard` controls how much each inventory
  entry carries.
- **`/code-flow.quality`** — reads the map and reports DRY, KISS and YAGNI findings with
  `file:line` evidence, writing `Code_Flows/quality-report.json`, `.md` and `.html`.
  Four detectors, each with rule-based severity thresholds rather than impressions:
  `duplicate-intent`, `repeated-sequence`, `complexity-hotspot` and `unreached`.
- **`--read-code`** — opens the files findings cite, confirms or drops each against
  current source, corrects `file:line`, and marks survivors `verified`.
- **`Code_Flows/quality-report.html`** — a self-contained viewer for the quality report,
  sibling to the flow viewer. Opens from a `file://` URL with no network.
- **`Code_Flows/index.html`** — the page to start from: every mapped flow as a card, the
  coverage that produced them, and the file census behind it. Rebuilt from `index.json`
  every time the map writes it, and linked from both other viewers, so a set of flows is
  navigable as a set instead of as a directory of loose pages. It reports the gap between
  entry points found and flows traced in words, so a partial map looks partial.
- **Both commands as Agent Skills** — one canonical `SKILL.md` per command,
  installed unchanged to `.agents/skills/` (read by Copilot, both Antigravity
  surfaces, OpenAI Codex and Gemini CLI) and `.claude/skills/` (Claude Code).
  They are named `/code-flow-map` and `/code-flow-quality`, with hyphens, because
  Copilot allows no dot in a skill name and fails to load an invalid one without
  saying so — and it reads the same directories the permissive hosts do. The
  commands and prompt files are unchanged and still ship: this is additive, and
  the format is verified from five hosts' documentation rather than from running
  it, which is why both forms go out together.
- **OpenAI Codex support**, at the cost of one four-line file per skill. Codex
  discovers repository skills from `.agents/skills/`, so every install already
  reaches it, and there is no `--tool codex` because there is no Codex-specific
  command to install. The one thing it does need of its own is
  `agents/openai.yaml`, which is where it reads the invocation policy the other
  hosts take from `SKILL.md` frontmatter.
- **Neither skill starts itself, on every host that offers a way to say so** —
  `disable-model-invocation: true` for Claude Code and Copilot,
  `policy.allow_implicit_invocation: false` for Codex. Explicit invocation is
  unaffected everywhere. Both Antigravity surfaces document no such setting, so
  there the skills' own confirm-before-writing step is the only gate; the README
  says which host is which rather than implying a guarantee that does not hold.
- **Copilot prompt files declare `agent: agent`**, not the undocumented `mode:`
  key they carried through development. `mode` is not a documented prompt-file
  property, and the parity test that was supposed to guard the frontmatter was
  asserting the wrong key.
- **Three-host support** — every command ships for Claude (`.claude/commands/*.md`),
  Gemini (`.gemini/commands/*.toml`) and Copilot (`.github/prompts/*.prompt.md`), saying
  the same things in each host's own register.
- **`--tool all` installs the Gemini CLI templates only where Gemini CLI is in use** —
  detected from a project-level `.gemini/` directory. Google retired Gemini CLI for free,
  Pro, Ultra and individual Code Assist users on 2026-06-18, and its successor does not
  read `.gemini/commands/`; the templates still ship for Code Assist Standard/Enterprise
  licences and paid API keys. When they are skipped the installer says so and prints the
  flag that installs them anyway, and `--tool gemini` always installs regardless.
- **A pre-publish release gate** (`npm run release-check`) covering the one thing no test
  in this repository can: that the HTML scaffolds actually render in a browser, and that
  the links between them go where they claim.

### Honesty rules, which are the point of the quality command

- Coverage leads every report. Reports say **"catalogued"**, never "all" — discovery is
  Glob/Grep/Read, not an AST walk.
- A report with no findings under partial coverage means "clean within what was mapped"
  and says so in words. It never implies a clean bill of health.
- `unreached` is a **candidate**, never a verdict, and no report instructs a deletion.
- A detector that cannot produce its required evidence does not run, and the report names
  it and says why.
- `/code-flow.quality` reads source but **never writes to it**.

### Testing

- **Viewer validation** for every HTML scaffold — the first tests any of them has had.
  Each scaffold's decision logic is a pure `validate(raw, TOKEN)` behind sentinel
  comments, lifted out and driven with no DOM, so the suite takes no browser dependency.
- **Host parity** is enforced by a test rather than by a script re-run by hand.
- **The finding schema is executable**, validated against shipped fixtures, instead of
  living only in prompt prose.

### Known limitation

Nothing in this repository asserts that either HTML page *renders*. There is no DOM in
the test path — a deliberate trade to keep the project at zero dependencies, including
dev dependencies. The mitigation is a manual browser pass before each release, which
`npm run release-check` now enforces on the npm side. See
`docs/superpowers/specs/2026-08-07-phase3b-report-viewer-design.md`, Decision 1.

### Changed — breaking, and the reason this is a major version

Upgrading from `0.x` needs two manual steps the installer cannot do for you. **See
"Upgrading from 0.x to 1.0" at the top of the README for the full procedure**, which is
more detailed than this summary.

- **`/code-flow` is now `/code-flow.map`.** The installer writes the new file but cannot
  know whether the old one is yours to delete, so `.claude/commands/code-flow.md` and
  `.gemini/commands/code-flow.toml` linger until you remove them.
- **Copilot now installs an invocable prompt** at `.github/prompts/code-flow.map.prompt.md`,
  and the installer no longer edits `.github/copilot-instructions.md`. Whether you should
  delete the old `## Code Flow — Documentation Generator` section from that file **depends
  on which Copilot surface you use** — prompt files are a documented VS Code feature, and
  removing the instructions section elsewhere could leave you with no Code Flow skill at
  all. The README explains which case you are in.
- **Flows mapped before 1.0 have no `.json` sidecar** until they are re-mapped.

Otherwise the upgrade is additive: `1.0.0` installs two commands and two viewers under the
same `.claude/`, `.gemini/`, `.github/prompts/` and `.code-flow/` paths. Re-running the
installer is a plain file copy that overwrites templates in place and touches nothing
under `Code_Flows/`.

## [0.2.0]

### Added

- Interactive HTML viewer output alongside the generated Markdown.

## [0.1.0]

### Added

- Initial release: installable Code Flow skill templates for Claude, Gemini and Copilot.
