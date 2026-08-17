# Design: Phase 5 — Copilot goes skills-only, and `--tool` learns the other hosts

**Date:** 2026-08-17
**Status:** Draft, pending approval
**Target version:** `2.0.0`
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

## Decision 1: drop the Copilot prompt files entirely

**Decision: delete `templates/copilot/`. Copilot is served by the Agent Skill alone.**

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

**One name per host.** After this, Copilot has exactly one Code Flow entry point,
hyphenated, matching every other skill-only host.

**Rejected: rename to hyphens and keep both.** It gives Copilot two things named
`/code-flow-map` with no documented precedence rule between them — the failure Phase 4
went out of its way to avoid.

**Rejected: leave it.** It preserves a dotted name the user asked to remove, on the one
host whose vendor documentation says the mechanism is going away.

### What this costs, stated plainly

**Three-host parity becomes two-host parity.** `tests/test_host_parity.py` and the
parametrized contract tests in `tests/test_template_contracts.py` have organized this
project since Phase 1; 64 collected tests currently name Copilot. After this phase,
Claude and Gemini are the only hand-written host templates left, and Copilot's content
guarantee comes from the skill being byte-identical everywhere rather than from a
divergence count. That is a **stronger** guarantee, but it is a different one, and the
machinery that enforced the old one shrinks.

**Copilot users on 0.x and 1.0 lose a file on reinstall.** The installer does not delete
what it previously wrote, so an existing `.github/prompts/code-flow.map.prompt.md`
lingers until removed by hand. The upgrade note must say so.

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

## Decision 3: this is `2.0.0`

**Decision: major version.** Removing an installed integration is breaking under SemVer,
and Phase 4's Decision 6 already scheduled this exact removal for *"a later major
version"*. `1.0.0` being one hour old does not change what the change is.

Phase 4's Decision 6 also attached a condition to that removal, and **this phase does not
satisfy it:**

> once the skills are confirmed working against all three hosts **in the wild**, a later
> major version removes `.claude/commands/`, `.gemini/commands/` and `.github/prompts/`

Nobody has confirmed the skill loads on Copilot. Deleting the prompt file leaves Copilot
users with the skill or with nothing, and this repository still cannot test which. This
is the single largest risk in the phase and it is not mitigated by anything in it — the
mitigation is a human opening Copilot, which `scripts/prepublish-check.js` item 4 already
asks for and which must be done on **Copilot specifically** before `2.0.0` is published.

Partial removal, not total: `.claude/commands/` and `.gemini/commands/` stay. Decision 6
listed all three together, but Claude Code and Gemini CLI have working, verified command
files and no vendor signal that the mechanism is being retired. Copilot has both.

## What Phase 5 ships

- `templates/copilot/` deleted, both files
- `bin/install.js` and `src/code_flow_skill/cli.py`: `codex` and `antigravity` tool
  values, conditional `.agents/skills/`, no Copilot template copying
- `tests/test_template_contracts.py`: `MAP_TEMPLATES` and `QUALITY_TEMPLATES` drop their
  Copilot entries
- `tests/test_host_parity.py`: `test_every_copilot_prompt_declares_agent_mode` deleted
- `EXPECTED_ALL` (both languages) and `EXPECTED_IN_WHEEL`: Copilot paths removed, tool
  matrix tests added
- README: the per-host table, the Usage section's Copilot block, the manual-install
  fence, the Files-written table, and a 1.0 → 2.0 upgrade note
- `CHANGELOG.md`: a `2.0.0` entry leading with the removal
- Version `2.0.0` in `package.json` and `pyproject.toml`, and
  `tests/test_packaging.py::test_package_versions_match_and_are_1_0_0` re-pointed

## Testing

**The tool matrix is the new contract.** Every row of Decision 2's table gets an
assertion in both languages, against the same expected-path lists that already hold the
two installers in lockstep. A row that installs the wrong set is the defect this phase
can most easily introduce.

**Nothing may still reference `templates/copilot/`.** A test asserting the directory is
absent, so a half-finished revert leaves a failure rather than a stale template that
ships.

**Not tested, disclosed:** that Copilot loads the skill. Unchanged from Phase 4 and now
load-bearing rather than additive, per Decision 3.

## Risks

- **Copilot users could end up with nothing.** Decision 3 states this in full. It is a
  manual gate, not a test.
- **Deleting 64 collected tests' worth of Copilot parametrization removes coverage that
  was doing real work** on the Copilot template's *content*. The skill inherits those
  contracts through `tests/test_skill_templates.py`, which asserts the body is derived
  from the Gemini template — but the derivation covers the body only, and Phase 4 already
  found one honesty rule living in the hand-written head. The head contracts must be
  checked for anything that was previously guaranteed only by the Copilot parametrization.
- **`--tool copilot` changing what it writes** is a silent behavior change for anyone
  scripting the installer.
