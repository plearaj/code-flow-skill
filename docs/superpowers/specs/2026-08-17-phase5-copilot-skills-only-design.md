# Design: Phase 5 — per-host `--tool`, a bundled page, and user themes

**Date:** 2026-08-17
**Status:** Amended 2026-08-17. **Decision 1 was overturned by direct observation before implementation — see below.**
**Target version:** `1.1.0` — see Decision 3, as amended
**Extends:** [`2026-08-08-phase4-agent-skills-design.md`](2026-08-08-phase4-agent-skills-design.md)

## How this document was produced

Written after `1.0.0` shipped to npm, in response to two questions from the user that
turned out to be one decision each. Both were ruled before this document existed, so
every section below records a decision rather than proposing one. Where the ruling
differs from what this project previously wrote down, the earlier text is quoted and
the change explained.

## What prompted it

Reviewing the published README, the user observed that the Copilot integration uses a
dotted name (`/code-flow.map`) where the skill form uses hyphens, and asked for the
Copilot side to use hyphens too. Separately, they asked whether the installer should
let someone installing for one assistant avoid the files another assistant reads.

The first question does not have a rename as its answer, for a reason worth stating
before the decisions: **renaming the prompt file collides with the skill.**
`code-flow.map.prompt.md` renamed to `code-flow-map.prompt.md` produces `/code-flow-map`
in VS Code, which is the name the Agent Skill already answers to on the same host. That
is the shadowing hazard Phase 4's Decision 2 identified on Claude Code, reproduced on
Copilot by our own hand. Hyphens on the prompt file only become safe once the prompt
file is gone.

## Decision 1: ~~drop the Copilot prompt files entirely~~ — OVERTURNED BY OBSERVATION

**Overturned 2026-08-17, before any of it was implemented, by the first direct
observation of a live host this project has ever had.** The decision as written is
struck below and kept for audit. What replaces it is at the end of this section.

### What was actually observed

Installed `@htst/code-flow-skill@1.0.0` from npm into a real project with `--tool
copilot`, then opened both Copilot surfaces.

| Surface | Versions | `/code-flow.map` (prompt file) | `/code-flow-map` (skill) |
|---|---|---|---|
| VS Code Copilot Chat | VS Code 1.132.0, Copilot Chat 0.35.3 | **appeared, and ran correctly** | did not appear |
| Copilot CLI | 1.0.10 | **appeared** (execution not tested) | **appeared** (execution not tested) |

The VS Code run executed the map command's step 1 as written — surveyed the project,
proposed five candidate flows, and asked which to trace — so the prompt file is not
merely listed there, it works.

**Corrected 2026-08-17, same day.** A first revision of this table recorded the CLI's
prompt-file row as "not tested" and then argued from VS Code's documentation that the
CLI would not read prompt files at all, because *"agents running on the Agent Host
don't use prompt files"*. Checking the CLI's actual list showed **both** forms present.
Whatever that sentence means, it does not mean the Copilot CLI ignores
`.github/prompts/`. The claim is struck; only the observation stands.

**Deleting the prompt files was still wrong, for a reason the correction does not
touch:** VS Code Copilot Chat lists the prompt file and not the skill, and that is the
surface this project's README spends the most words on. Agent Skills in VS Code are an
*experimental* feature added in 1.108 (December 2025); the test machine runs 1.132 with
no skill settings configured, and the skill did not appear there.

**What the two forms are for, stated only as far as the evidence goes:** the prompt
file is the only form observed on VS Code Chat, and the skill is the only form that
reaches Codex, Antigravity and Gemini CLI, none of which read `.github/prompts/`. On
the Copilot CLI both are listed and neither was run, so which one a CLI user should
prefer is **not established here** — and no sentence in the README should imply it is.

### A second thing the same test settled

`code-flow-quality` was left carrying `disable-model-invocation: true` while
`code-flow-map` had that one line stripped, in the same directory on the same host.
**Both appeared in the Copilot CLI.** So the field does not remove a skill from
explicit invocation there — which is what Phase 4's Decision 3 assumed and could not
check. That assumption is now observed rather than inferred, on one host.

### ~~The struck decision~~

~~**Decision: delete `templates/copilot/`. Copilot is served by the Agent Skill alone.**~~

Three things point the same way:

**Copilot is migrating off prompt files, and says so.** Phase 4's spec already recorded
it: *"Agents running on the Agent Host don't use prompt files. To use an existing prompt
with the Copilot agent, convert it to an agent skill."* VS Code ships a one-time
migration that does exactly this conversion. We would be renaming a file the vendor is
retiring.

**We never verified the prompt file worked as a slash command.** The README has said so
since 1.0: the dotted name follows the GitHub Spec Kit naming convention *"rather than
any confirmed Copilot behavior"*, and whether non-VS-Code Copilot surfaces read prompt
files at all was never established. The skill is the better-documented path on more
surfaces.

> **This argument was the load-bearing one, and it was false.** It reasoned from the
> absence of a verification to the absence of the behaviour. The prompt file works in
> VS Code Copilot Chat; nobody had looked. "Unverified" is a statement about us, not
> about the artifact, and this decision quietly treated the two as the same thing.
> That is the mistake worth remembering out of this whole phase.

**One name per host.** After this, Copilot has exactly one Code Flow entry point,
hyphenated, matching every other skill-only host.

**Rejected: rename to hyphens and keep both.** It gives Copilot two things named
`/code-flow-map` with no documented precedence rule between them — the failure Phase 4
went out of its way to avoid.

**Rejected: leave it.** It preserves a dotted name the user asked to remove, on the one
host whose vendor documentation says the mechanism is going away.

### What replaces it

**Decision: keep `templates/copilot/`. Both forms ship, because both are load-bearing,
and the README says which Copilot surface needs which.**

Copilot is not one host. It is at least two, and they do not read the same set:

| Surface | Lists the prompt file | Lists the skill |
|---|---|---|
| VS Code Copilot Chat | yes — `/code-flow.map` | no |
| Copilot CLI | yes — `/code-flow.map` | yes — `/code-flow-map` |

That answers the question that started this phase — *why does Copilot use dots when
everything else uses hyphens?* Because on the surface the README was describing, the
dotted prompt file is the only thing there. **The dot is not an inconsistency; it is VS
Code Chat's only form.** The hyphen is what the skill-reading hosts see. The README was
presenting one Copilot where there are two.

It also explains the four entries a Copilot CLI user sees. `code-flow-map` is not listed
twice — `/code-flow.map` and `/code-flow-map` are two different commands doing the same
job, one from each form, exactly as on Claude Code. There is nothing to de-duplicate,
which is worth writing down because it looked like a bug and was investigated as one.

This also retires a caveat rather than adding one. The README has said since 1.0 that it
does not claim Copilot Chat exposes a dotted filename as a `/`-command. It does, on VS
Code 1.132.0 with Copilot Chat 0.35.3, observed 2026-08-17. That sentence can become a
positive statement with a version and a date on it.

**Deferred, not cancelled.** When Agent Skills leave experimental status in VS Code and a
default install of Copilot Chat reads `.agents/skills/`, the prompt files become genuinely
redundant and Phase 4's Decision 6 removal applies. The trigger is observable — re-run this
same test — and it has not happened.

### ~~What this costs, stated plainly~~ — no longer applicable, kept for audit

~~**Three-host parity becomes two-host parity.**~~ Nothing is deleted, so the parity
machinery is untouched and the 64 Copilot-parametrized tests stay. The paragraph below
described the cost of a removal that is no longer happening.

~~`tests/test_host_parity.py` and the
parametrized contract tests in `tests/test_template_contracts.py` have organized this
project since Phase 1; 64 collected tests currently name Copilot. After this phase,
Claude and Gemini are the only hand-written host templates left, and Copilot's content
guarantee comes from the skill being byte-identical everywhere rather than from a
divergence count. That is a **stronger** guarantee, but it is a different one, and the
machinery that enforced the old one shrinks.~~

~~**Copilot users on 0.x and 1.0 lose a file on reinstall.** The installer does not delete
what it previously wrote, so an existing `.github/prompts/code-flow.map.prompt.md`
lingers until removed by hand. The upgrade note must say so.~~

## Decision 2: `--tool` gains `codex` and `antigravity`, and `.agents/skills/` stops being unconditional

**Decision: `--tool claude|copilot|codex|antigravity|gemini|all`.** `.agents/skills/`
installs when the selection includes any of `copilot`, `codex`, `antigravity` or
`gemini`, and not otherwise.

`.agents/skills/` was unconditional in Phase 4 for a reason that no longer holds: it
serves five hosts and `--tool` had three values, so there was no way to *ask* for Codex
or Antigravity and the only safe default was always. Naming them fixes the cause rather
than the symptom.

The resulting matrix:

| `--tool` | `.claude/commands/` | `.claude/skills/` | `.agents/skills/` | `.gemini/commands/` | `.code-flow/` |
|---|---|---|---|---|---|
| `claude` | yes | yes | — | — | yes |
| `copilot` | — | — | yes | — | yes |
| `codex` | — | — | yes | — | yes |
| `antigravity` | — | — | yes | — | yes |
| `gemini` | — | — | yes | yes | yes |
| `all` | yes | yes | yes | conditional¹ | yes |

¹ Unchanged from Phase 4: under `--tool all`, the Gemini CLI templates install only when
the target has its own `.gemini/` directory. `--tool gemini` is an explicit request and
always installs.

**`agents/openai.yaml` continues to ride along with `.agents/skills/`** rather than
becoming Codex-only. It is 192 bytes, inert on every other host, and making it
conditional would mean a user who adds Codex later needs a reinstall to get a file that
was already harmless to have.

**Note that `--tool copilot` no longer writes `.claude/skills/`,** which Copilot also
reads. That is deliberate and it *resolves* the double-write disclosure Phase 4 added to
the README: a Copilot-only install now writes the skill exactly once, and only `--tool
all` puts it in two directories Copilot scans.

**Rejected: an `--agents-only` / `--no-agents` switch.** Smaller, but it leaves Codex and
Antigravity unnameable, which is the actual gap.

**Rejected: leaving `.agents/skills/` unconditional.** Four files a Claude-only project
never reads is not harmful, but the user asked for the granularity and naming the hosts
is the honest way to give it.

## Decision 3: ~~this is `2.0.0`~~ — this is `1.1.0`

**Amended 2026-08-17 with Decision 1.** Nothing is removed any more, so nothing is
breaking. Decision 2's tool values are additive, and the one behaviour change —
`--tool claude` no longer writing `.agents/skills/` — narrows a set of files that host
never read. **`1.1.0`.**

~~**Decision: major version.** Removing an installed integration is breaking under SemVer,
and Phase 4's Decision 6 already scheduled this exact removal for *"a later major
version"*. `1.0.0` being one hour old does not change what the change is.~~

The gate below is what caught this, and it deserves to be recorded as having worked:

> once the skills are confirmed working against all three hosts **in the wild**, a later
> major version removes `.claude/commands/`, `.gemini/commands/` and `.github/prompts/`

Phase 4 wrote that condition without knowing what it would catch. Ten minutes of a human
opening two Copilot surfaces overturned a decision that three documents, a spec review and
a written implementation plan had all accepted. **The condition was the only thing standing
between this project and shipping a release that broke VS Code Copilot Chat users.** Keep
it attached to any future removal.

The removal it governs is now deferred with an observable trigger: when Agent Skills leave
experimental status in VS Code and a default Copilot Chat install reads `.agents/skills/`,
re-run the same test and the prompt files become redundant for real.

## Decision 4: one bundled page, and the user picks whether to keep the loose ones

**Decision: a new `--output files|bundle|both` flag on `/code-flow.map`, default `files`.**

| `--output` | `Code_Flows/` gets |
|---|---|
| `files` (default) | exactly what it gets today: `index.html`, one `<slug>.html` per flow, `quality-report.html` |
| `both` | the above **plus** `Code_Flows/code-flow.html` |
| `bundle` | `Code_Flows/code-flow.html` **only** — no `index.html`, no per-flow pages |

**The JSON artifacts are written in every mode, without exception.** `index.json`,
`<slug>.json`, `inventory.json` and `quality-report.json` are the contract
`/code-flow.quality` consumes and the data every rendering is built from. `--output
bundle` suppresses *pages*, never data. A mode that skipped the JSON would silently
break the quality command, which is the one coupling in this project that nothing else
guards.

**The bundle is rebuilt from the JSON artifacts on every run**, exactly as `index.html`
already is. It is never incrementally patched. That is what makes it safe for an
assistant to write: the operation is "read every `<slug>.json`, read `index.json`, read
`quality-report.json` if it exists, render one page", not "open the existing bundle and
splice a flow into it". It also retires the switcher-staleness limitation the flow pages
carry today, where a page written earlier does not know about flows mapped later — a
bundle has every flow by construction.

**Default stays `files`** so no existing user's output changes shape without asking.

**Rejected: bundle-only as the default.** It is the better artifact for showing someone,
which is the reason this exists, but it is a breaking change to documented output and the
loose pages are better for everything else — you cannot send someone a single flow out of
a bundle.

**Consequence to disclose:** the bundle carries every flow, so a repository with many
mapped flows produces a large file. The three scaffolds are already 107 KB of chrome
before any data. The README must say this rather than letting someone discover it at
50 flows.

## Decision 5: `.code-flow/theme.css`, inlined through a token

**Decision: the installer ships `.code-flow/theme.css`, and every scaffold gains a
`__THEME_CSS__` token that the generator replaces with that file's contents.**

This costs less than it looks like it should, because the scaffolds were already built
for it. All three drive every colour through CSS custom properties — around 25 of them,
`--bg`, `--accent`, `--edge`, `--node-entry` and the rest — declared in a `:root{}` block
and overridden in a `[data-theme="light"]{}` block. A custom theme is those same
properties with different values. Nothing needs restructuring.

The token sits immediately after the `[data-theme="light"]` block in each scaffold, so
user declarations come last and win.

**The shipped `theme.css` must contain both blocks, not just `:root`.** `:root` and
`[data-theme="light"]` have equal CSS specificity, so a user file that sets only `:root`
would override the light palette too and break the light/dark toggle — the page would
render their colours in both modes and the button would appear dead. Shipping a file with
both blocks pre-filled at their current defaults makes the right thing the obvious thing,
and makes the failure hard to reach by accident.

**Absent, empty, or unreadable `theme.css` renders exactly what is rendered today.** The
token becomes an empty string and no error is reported. A theming feature that can break
a page it was not asked to change is worse than no theming feature.

**Rejected: colours in `index.json`.** It limits the user to keys we chose, and puts
presentation into a data file `/code-flow.quality` also reads.

**Not tested, and worth stating plainly:** that any of this *looks* right. No test here
renders a page. A user theme is arbitrary CSS inlined into a document, and the manual
browser pass is the only thing that will ever see the result.

## What Phase 5 ships

Nothing is deleted. `templates/copilot/` stays, both files, and every test parametrized
over it stays with it.

- `bin/install.js` and `src/code_flow_skill/cli.py`: `codex` and `antigravity` tool
  values, and `.agents/skills/` conditional on the selection containing a host that
  reads it
- `EXPECTED_BY_TOOL` in both test suites — one row per `--tool` value, the new contract
- `templates/shared/bundle.template.html`, a fourth scaffold, installed to
  `.code-flow/bundle.template.html`, carrying `__BUNDLE_DATA__` and `__THEME_CSS__`
- `templates/shared/theme.css`, installed to `.code-flow/theme.css`, holding every custom
  property at its current default in both a `:root` and a `[data-theme="light"]` block
- `__THEME_CSS__` added to `viewer.template.html`, `report.template.html` and
  `index.template.html`, immediately after their `[data-theme="light"]` block
- The `--output files|bundle|both` flag, and the theme-inlining rule, written into the
  map and quality instructions for **every host**: `templates/claude/` ×2,
  `templates/gemini/` ×2, `templates/copilot/` ×2, and the two `SKILL.md` bodies derived
  from Gemini
- README: the per-host table gains the **two Copilot surfaces** as separate rows, the
  Usage section explains which surface reads which file, `## CLI options` documents the
  new tool values, and the "not verified" caveat about the dotted prompt file becomes a
  positive statement with a version and a date
- `CHANGELOG.md`: a `1.1.0` entry
- Version `1.1.0` in `package.json` and `pyproject.toml`, and
  `tests/test_packaging.py::test_package_versions_match_and_are_1_0_0` re-pointed

## Testing

**The tool matrix is the contract.** Every row of Decision 2's table gets an assertion in
both languages, against the same expected-path lists that already hold the two installers
in lockstep. A row that installs the wrong set is the defect this phase can most easily
introduce.

**The bundle's data contract.** `__BUNDLE_DATA__` must carry the registry, every flow,
and the quality report when one exists — asserted against the scaffold the same way the
existing tokens are, and the bundle scaffold gets a `validate()` behind sentinel comments
like its three siblings, lifted and driven with no DOM by `test/viewer-validation.test.js`.

**`--output` and the theme rule in every host.** Contract tests over the existing
`MAP_TEMPLATES` and `QUALITY_TEMPLATES` parametrizations, scoped to the region that states
the rule, so a host that drops one fails rather than drifting.

**Now observed rather than disclosed:** that `/code-flow.map` works in VS Code Copilot
Chat, that `/code-flow-map` works in the Copilot CLI, and that
`disable-model-invocation: true` does not hide a skill from the CLI's list. One machine,
one date, three versions — recorded in Decision 1 with all three, because a single
observation is evidence and not a guarantee. No test in this repository can re-check any
of it.

## Risks

- **`--tool claude` no longer writing `.agents/skills/`** is a silent behaviour change for
  anyone scripting the installer, and it is the one thing in this phase that takes files
  away from an existing configuration. Nothing on Claude Code reads them, which is why
  this is `1.1.0` rather than a major, but a scripted install that greps for
  `.agents/skills/` after `--tool claude` will now find nothing.
- **The Copilot surface split is documented from one observation each.** VS Code Chat
  reading prompt files and the CLI reading skills are each a single data point on a single
  machine. If a future Copilot Chat release starts reading `.agents/skills/`, the README's
  surface table becomes misleading in the safe direction — it would understate what works,
  not overstate it.
- **The deferred removal has no scheduled re-check.** Decision 1 names an observable
  trigger but nothing prompts anyone to look for it. It will be noticed when someone next
  installs into a Copilot project, or not at all.
- **This phase pays the parity tax six times over.** `--output` and the theme rule are
  prose, and prose must be written into six hand-maintained host templates and stay in
  agreement. `tests/test_host_parity.py` catches Claude/Gemini divergence and the derived
  `SKILL.md` bodies inherit Gemini's, but nothing compares Copilot's wording to either.
  This is the largest single prose change since Phase 3a and the most likely place for a
  host to quietly say something different.
- **A fourth scaffold is a fourth thing no test renders.** The bundle does what all three
  existing pages do, in one document, and the manual browser pass is the only check that
  it works. `scripts/prepublish-check.js` must grow to cover it, and the checklist's
  "ALL THREE files" wording becomes wrong the moment this lands.
- **A user theme is arbitrary CSS inlined into a generated page.** Nothing validates it.
  A malformed `theme.css` produces a broken-looking page with no error, and the failure
  surfaces only to whoever opens it.
