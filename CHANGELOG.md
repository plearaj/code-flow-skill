# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Both the npm
package (`@htst/code-flow-skill`) and the Python package (`htst-code-flow-skill`) ship
from this repository at the same version.

## [1.2.0]

### Added — automated tracing

- **Five static tracers**, installed to `.code-flow/tracers/`: `trace_python.py`,
  `trace_typescript.mjs` (any Node 18+, covering `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`,
  `.cjs`, `.vue` and `.svelte`), `trace_rust.py`, `trace_java.py` and
  `trace_c_family.py` (C, C++, Objective-C and C# in one catalog). Four of the five run
  under any CPython 3.9+. Each reads a repository in one pass and writes one JSON
  document — every function with its `file:line`, signature, purpose, role and export
  status; the resolved call graph between them; the entry points execution arrives
  through; and, for the TypeScript one, the component tree and the routes.
- **`/code-flow.map` runs them before it traces anything** and walks the resulting graph
  instead of re-reading the repository once per entry point. That is the difference
  between finishing a whole-codebase map in one pass and finishing it in four: a run
  that previously traced 10 of 118 flows before running out of room now traces them all.
- **`--tracer auto|on|off`** on `/code-flow.map`, default `auto`: run each tracer whose
  language the repository contains and whose interpreter the machine has, and read
  source where none applies. `on` says so and stops when none could run; `off` never
  runs one, and every step still works by reading, only slower.
- Every tracer is **zero-dependency** — no `typescript` package, no `node_modules`, no
  compiler, no toolchain — because they run inside your repository, not this one, and a
  tracer that needed a working build would be useless on exactly the repository most in
  need of a map. None of them lexes by parsing: comments, string bodies, template text,
  raw and verbatim strings, Java text blocks and C preprocessor lines are blanked in
  place — same length, same line breaks — so a `{` inside a string or a macro cannot
  move a function's boundary. They also leave nothing behind in the tree they read, not
  even a `__pycache__`.
- **Per-language resolution, each with its own honest edge.** Rust resolves through
  `use` paths, `impl` blocks, constructor bindings and struct fields, and leaves `dyn
  Trait` dispatch ambiguous. Java resolves through fields, `extends` chains, static
  imports and constructors, and resolves an interface call to the interface rather than
  guessing an implementation. The C family resolves a bare call **through the headers a
  file includes**, which is what makes a C call graph possible at all, and additionally
  reads C++ constructors with member initializer lists, C# attributes and
  expression-bodied members, and Objective-C methods named by their whole selector.
- **Validated against code this repository did not write.** `trace_python.py` reads the
  Python standard library (670 files, 14,720 functions, 16,887 edges) and
  `trace_c_family.py` reads `/usr/include` (4,145 files, 12,765 functions). That run is
  what caught `namespace std _GLIBCXX_VISIBILITY(default) {` being read as a function:
  three libstdc++ headers each became one six-thousand-line "function" that swallowed
  every real declaration inside it, and fixing it took the catalog from 7,527 functions
  to 12,765 over the same files. A fixture proves a contract and proves nothing about a
  heuristic.
- **One shared core, `_common.py`.** Discovery, the id rule, the skip-reason table, the
  brace-language lexer and the output envelope live in one file rather than once per
  tracer, and `trace_python.py` was moved onto it. Adding a sixth language is a `Flavor`
  and a declaration reader, plus one line in the test table that subjects it to every
  shared contract.
- **Honest resolution.** Every call carries `exact` or `heuristic`; calls that could mean
  several things are listed with their candidates rather than guessed into edges; calls
  that leave the repository are listed separately; and each tracer states what static
  analysis cannot see at all. The map confirms heuristic edges against source before
  drawing them, and never presents a traced map as complete.

### Added — frontend component mapping

- **`--frontend auto|react|vue|angular|svelte|off`** on `/code-flow.map`, default
  `auto`. A repository with a UI is two graphs — functions call functions, components
  render components — and mapping only the calls left the half a user touches
  undocumented.
- Components are recognized per framework by declaration shape: a capitalized
  JSX-returning function or class (React, Preact, Solid), a `.vue` file or options
  object with a `template`, a class decorated `@Component` (Angular), a `.svelte` file.
  Children come from JSX tags resolved through the file's imports, from the
  `<template>` block, or from the selectors an Angular template uses.
- Each component is catalogued in `inventory.json` with its props, events, lifecycle
  hooks, the hooks, composables, stores or services it depends on, the route that
  reaches it, and the components it renders. Custom hooks, composables and injectable
  services get their own kind — `hook`, `service`, `store` — rather than distorting the
  tree as components.
- **New node kind `component` and new edge kind `render`**, rendered distinctly by the
  interactive viewer and the bundle, with matching entries in `.code-flow/theme.css`.

### Added — SOLID and deep modules

- **Six more detectors on `/code-flow.quality`, under two new principles.** `SOLID`
  carries `single-responsibility` (a module reaching into many others),
  `interface-segregation` (a wide export surface no single caller uses much of) and
  `dependency-cycle` (modules depending on each other in a ring). `DEPTH` carries
  Ousterhout's deep-module argument: `shallow-module` (more interface than
  implementation behind it), `pass-through` (a function that only hands its arguments
  to one other) and `internals-coupled-test` (a test reaching past a module's interface
  into its internals, freezing the implementation that module was supposed to stay free
  to change). Every threshold is a number, as everywhere else in this report, so
  findings do not drift toward "medium".
- **`open-closed` and `liskov-substitution` run under `--read-code`**, and only there.
  Their evidence was never in the map: a dispatch table, a registry and a polymorphic
  call are all correct answers to the problem open-closed describes, and no call graph
  can tell any of them from a conditional chain. So the map locates candidates — a
  variant family with a caller that selects among it, an override family with a member
  whose body refuses — and the source settles them. A candidate the verify pass does
  not confirm is dropped there, which makes these two the only detectors whose every
  finding is `verified`. Liskov's candidate survives only if the family really shares
  a supertype, a caller really holds one through it, and the member really weakens the
  contract; two unrelated `save` methods are the false positive it is most exposed to,
  and the first check is what removes it.
- **The SOLID group says which of the five it checked.** Under `--read-code` all five
  report; without it the two above are named as not checked, with the flag named as
  the remedy. The sentence is written even when SOLID produced no findings, because
  three principles reported and two never mentioned reads as five principles clean.
- **The three flow detectors gate off when the map registers no traced flows** —
  repeated-sequence, complexity-hotspot and unreached are defined over flow *nodes*,
  and a map built from a tracer's output with no tracing pass has none. `unreached`
  is why the gate has to exist: with nothing reached, subtracting the reached set
  from the catalogued one reports every function in the repository as dead code.
  Both scaffolds now carry a reason for all three, so the banner names the cause and
  the remedy instead of "reason not recorded in this report".
- **The five call-graph detectors gate off when the map has no `calls`**, naming each
  one and the remedy — re-map with `--tracer on` — in the same coverage banner that
  already reports a skipped duplicate-intent. `shallow-module` reads only export counts
  and function lengths, so it still runs on any map that carries an inventory.
- Findings from the new detectors carry the measurement their threshold was applied to,
  the way `complexity-hotspot` carries `metric` and `value`: `module` plus
  `dependencies`/`dependents`, `exports`/`consumers`/`widestConsumerUse`, `cycle`,
  `interface`/`hiddenLoc`, and `internals`. Both HTML scaffolds render them beside the
  cited sites, so a reader can check the number rather than take it.
- **`owner` and `overrides` on every inventory entry, from every tracer.** `owner` is
  the type that declares the function — class, struct, trait, `impl` target, interface,
  `@implementation` — absent for a free function. `overrides` is the supertype
  declarations it implements, nearest first, written `Supertype.member`. Like `calls`,
  neither is inferred by reading: each tracer reads the relationship its own language
  states outright — `impl Trait for Type`, `extends`, `implements`, a base-class list —
  and names a supertype only where that supertype really declares the member, so
  `AdminUserStore extends UserStore` does not make `findAdmin` an override of anything.
  A supertype outside the repository is not named at all. It is a name and not an `id`
  because a Java interface method, a C++ pure virtual and an Objective-C protocol
  selector have no body to catalogue, and an id-only field would report the same
  relationship in one language and stay silent in the next.
- **`liskov-substitution` forms its family from `overrides` where the map carries it.**
  A family is then the set of functions naming the same declaration — stated by the
  source rather than matched by name — and the shared-supertype check, the one doing
  the most work to keep two unrelated `save` methods out of the report, is settled
  before verification starts. Where `overrides` is absent the detector falls back to
  the previous name-and-parameter-count rule and verification does all three checks. A
  function belongs to one family, not two: stated families form first. Every finding
  carries `familyFrom`, `overrides` or `name`, and both scaffolds print it beside the
  family — *stated by the source* or *matched by name* — so a reader never has to
  assume which kind they are looking at.

### Added — checking your own rules

- **`--rules [source ...]`** on `/code-flow.quality`, off by default. A source is a path
  to a document, the word `auto`, or a rule written inline. `auto` looks for `CLAUDE.md`,
  `.claude/CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`,
  `.specify/memory/constitution.md` (Spec Kit), `memory/constitution.md`,
  `CONVENTIONS.md` and `.code-flow/rules.md`.
- **A fifth detector, `rule-violation`, under a fourth principle, `RULES`.** Findings
  carry the same `file:line` evidence as every other finding, plus the rule they rest on
  — quoted, not paraphrased — and the `file:line` it was read from. One rule is one
  finding however many sites break it, and severity comes from the rule's own wording
  (`must`/`never`/`always` are high, `should`/`prefer` medium, `consider`/`may` low)
  rather than from the report's opinion of it.
- **A rule the map has no evidence about is reported as not checked, never as passing.**
  `quality-report.json` gains a `rules` array carrying every rule loaded, checkable or
  not, with the reason where it was not, plus `rulesLoaded`, `rulesChecked` and
  `rulesNotCheckable` in `coverage` so the banner reconciles with the array behind it.

### Changed

- `inventory.json` function entries may now carry `calls` — the resolved call graph a
  tracer established, each with its confidence. Present when a tracer produced it,
  absent otherwise; it is what makes pass 2 a graph walk rather than a second reading of
  the repository.
- `inventory.json` may now carry a `components` array alongside `functions`.
- The interactive viewer, the bundle and the quality report accept the new kinds and the
  new principle; existing artifacts render unchanged.

### Fixed

- **A generated flow page can be shared through corporate mail and chat again.** The
  viewer and the bundle drew their edge arrowheads with an SVG `<marker>`, which can
  only be reached by referencing it as `url(#id)` — a signature several corporate
  gateways quarantine, so sending somebody a flow through Teams failed. Arrowheads are
  now a path per edge, positioned and rotated from geometry the layout already knows.
  The rendering is unchanged, pixel for pixel; no scaffold refers to anything by
  fragment id any more, and a test keeps it that way.

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
