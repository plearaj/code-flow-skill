# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Both the npm
package (`@htst/code-flow-skill`) and the Python package (`htst-code-flow-skill`) ship
from this repository at the same version.

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
- **Three-host support** — every command ships for Claude (`.claude/commands/*.md`),
  Gemini (`.gemini/commands/*.toml`) and Copilot (`.github/prompts/*.prompt.md`), saying
  the same things in each host's own register.
- **A pre-publish release gate** (`npm run release-check`) covering the one thing no test
  in this repository can: that both HTML scaffolds actually render in a browser.

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

- **Viewer validation** for both HTML scaffolds — the first tests either has ever had.
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
