# Design: Phase 4 — the Agent Skills standard

**Date:** 2026-08-08 (amended 2026-08-15 with the Antigravity documentation)
**Status:** Draft, pending approval. **Open Question 1 is ruled — see below.**
**Target version:** `1.0.0` — see Decision 6, as amended
**Extends:** [`2026-08-06-dry-kiss-yagni-reporting-design.md`](2026-08-06-dry-kiss-yagni-reporting-design.md)

## How this document was produced

Drafted without the usual question-at-a-time dialogue, at the user's request, while
they finished a separate design pass. Every decision that would normally have been a
question is marked **Decision**, with the reasoning and the alternative that was
rejected, so approval is a matter of ratifying or overturning specific calls.

**Three questions at the end genuinely need a human ruling** and are not decided here.

**Amended 2026-08-15, twice.** The Antigravity documentation was supplied after the
draft was written, and the first amendment got the picture wrong in a way worth
recording rather than quietly fixing.

That amendment treated Antigravity as a *fourth* host alongside Gemini CLI. It is not:
**Antigravity CLI replaced Gemini CLI**, which stopped serving individual users on
2026-06-18. Working only from the IDE documentation, the amendment also concluded that
Antigravity offered no explicit-invocation route for commands this size — wrong, and
the CLI documentation says so plainly: skills become slash commands automatically.

Both errors are struck in place, with the reasoning that produced them left visible,
because a spec whose corrections are invisible cannot be audited. The net effect on the
decisions is smaller than the first amendment implied, but Open Question 3 is real and
survives both revisions.

## What changed upstream

This phase exists because the ground moved under all three host integrations at once.

**GitHub Copilot is migrating off prompt files.** VS Code's prompt-file documentation
now says: *"Agents running on the Agent Host don't use prompt files. To use an existing
prompt with the Copilot agent, convert it to an agent skill."* The Agent Customizations
editor ships a one-time migration that converts prompt files to skills.
([prompt files](https://code.visualstudio.com/docs/copilot/customization/prompt-files),
[agent skills](https://code.visualstudio.com/docs/agent-customization/agent-skills))

**Our Copilot frontmatter key no longer exists.** The current documented prompt-file
properties are `description`, `name`, `argument-hint`, `agent`, `model` and `tools`.
The word `mode` does not appear on that page at all. We ship `mode: agent` in both
Copilot templates, and `tests/test_host_parity.py:149` **asserts it is present**. The
successor is `agent:`, whose allowed values are `ask`, `agent`, `plan`, or a custom
agent name. See Decision 0 — this is the one part of this phase that should not wait.

**Gemini CLI has been retired, and this document's Gemini row was out of date before
it was written.** Google announced the transition at I/O on 2026-05-19 and Gemini CLI
stopped serving requests on **2026-06-18** for free users, Google AI Pro and Ultra
subscribers, and individual Gemini Code Assist users. Its successor is **Antigravity
CLI** — a ground-up rewrite in Go, sharing an agent harness with the Antigravity 2.0
desktop application rather than being a rename.
([transition announcement](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/))

**Gemini CLI is not gone, though, and the remnant is what Open Question 2 now turns
on.** Organisations on Gemini Code Assist **Standard or Enterprise** licences, and
users on paid Gemini and Gemini Enterprise Agent Platform API keys, keep Gemini CLI
with continued model and product updates. So `.gemini/commands/*.toml` still has real
users; it just no longer has *growing* ones.

**The Gemini surface is therefore two hosts, both Antigravity.** Both read the same
`SKILL.md` standard and both discover workspace skills from `.agents/skills/`. They
differ only in their global path:

| Surface | Global skills path |
|---|---|
| Antigravity CLI | `~/.gemini/antigravity-cli/skills/` |
| Antigravity IDE | `~/.gemini/antigravity/skills/` |

Documented frontmatter on both is smaller than any other host's: `description`
(required) and `name` (optional, defaulting to the folder name). Nothing else — no
`tools`, no `model`, and **no field for suppressing model invocation.**
([IDE skills](https://antigravity.google/docs/ide/skills/),
[CLI plugins & skills](https://antigravity.google/docs/cli/plugins))

**So does Claude Code**, which is where the `SKILL.md` format originated, discovered
from `.claude/skills/`.

Four hosts have converged on one format. This repository still writes three.

## The problem this actually solves

This project's dominant recurring cost is that every rule must be written three times
and held in agreement by hand. Phase 1 lost four review rounds to host drift. Phase 2
inherited a 27-line Claude/Gemini divergence it could reduce but not remove. Phase 3a
had to commit `tests/test_host_parity.py` because the constraint was otherwise enforced
by a script someone re-ran from memory. Every phase since has paid a parity tax.

A single `SKILL.md` that all three hosts read removes the tax rather than automating it.
That is the case for this phase, and it is a strong one.

The discovery paths overlap usefully:

| Location | Copilot | Antigravity CLI | Antigravity IDE | Gemini CLI (legacy) | Claude Code |
|---|---|---|---|---|---|
| `.claude/skills/` | yes | — | — | — | yes |
| `.agents/skills/` | yes | yes | yes | yes | — |
| `.github/skills/` | yes | — | — | — | — |
| `.gemini/skills/` | — | — | — | yes | — |

**Two installed copies of one file cover every host**: `.claude/skills/` and
`.agents/skills/`. That conclusion survives the Gemini CLI retirement unchanged —
both Antigravity surfaces read `.agents/skills/`, so the successor costs no new
install target and the legacy host is covered by the same copy.

What Antigravity changes is Decision 3 and both open questions, because its
*invocation* model differs from the retired host's in both directions: it is easier
to invoke a skill deliberately, and impossible to stop one being invoked for you.

## Decision 0: fix `mode: agent` now, independently of this phase

`mode` is not a documented prompt-file property. Whether VS Code still honours it for
back-compat is unknown to this repository, and the shipped 1.0.0 Copilot integration
depends on the answer.

**Decision: correct the frontmatter to `agent: agent` and re-point the parity test.**
The test currently guarantees the wrong thing — the precise failure mode this project
keeps finding in itself, this time in the file that guards against it.

**Amended after the Open Question 1 ruling.** This was originally specified as a
standalone fix that must not wait for the rest of Phase 4, because leaving a dead
frontmatter key in a *published* package was the thing to avoid. With 1.0.0 held until
Phase 4 ships, there is no published package to protect, and the argument for splitting
it out disappears. **It folds into the phase as ordinary work.**

The test fix should still land early in the phase rather than late, for a different
reason: while it asserts `mode: agent`, it will actively fail any correct change to that
frontmatter.

## Decision 1: adopt the standard, and make `SKILL.md` the single source of truth

**Decision: one canonical `templates/shared/code-flow-map/SKILL.md` and one
`templates/shared/code-flow-quality/SKILL.md`, installed byte-identically to every
location a host reads.** The installer copies; it does not template per host.

This inverts the current architecture. Today `templates/claude/`, `templates/gemini/`
and `templates/copilot/` each hold a full copy of the same prose, and a test proves
they agree. Under this decision there is one copy, and agreement is structural rather
than asserted.

`tests/test_host_parity.py` does not disappear — it changes job. Instead of measuring
divergence between three hand-written files, it asserts that every installed skill file
is byte-identical to its template, which is a stronger and much cheaper claim.

**Rejected: per-host `SKILL.md` variants.** The whole benefit is that the standard is
the same everywhere. A per-host variant re-creates the drift problem inside the new
format and would be indistinguishable, six months later, from what we have now.

## Decision 2: the names must change, and the failure mode if they don't is silent

Skill names allow **lowercase letters, numbers and hyphens only** — no dots, no slashes,
no namespace prefixes, 64 characters maximum. The Copilot documentation is explicit
that *"Names with invalid characters cause the skill to silently fail to load."*

`code-flow.map` and `code-flow.quality` are therefore invalid skill names.

**Decision: `code-flow-map` and `code-flow-quality`.** The directory name must match
the `name` field, so both change together.

This is user-visible: `/code-flow.map` becomes `/code-flow-map`. See Decision 6 for how
that is sequenced without breaking anyone.

**Worth stating plainly:** an invalid name does not warn, it silently does not load. A
user would see the skill simply not exist, with nothing to search for. That is the exact
class of failure this project spent Phase 3b building tests against, and it argues for a
contract test asserting both names match `^[a-z0-9-]{1,64}$` rather than trusting review.

## Decision 3: invocation semantics differ per host, and the report must say so

This is the sharpest difference and the one most likely to surprise a user.

| Host | How a skill runs |
|---|---|
| Copilot | auto-matched from the description, **and** `/`-invocable |
| Antigravity CLI | auto-activated at the agent's discretion, **and** `/`-invocable: *"Skills convert automatically into slash commands inside the TUI, allowing you to invoke them manually (e.g., typing `/refactor-ui`)"* |
| Antigravity IDE | auto-activated at the agent's discretion; no slash syntax documented — the docs say only that you "can mention a skill by name if you want to ensure it's used" |
| Gemini CLI (legacy) | auto-activated via an `activate_skill` tool call, with a confirmation prompt |
| Claude Code | auto-matched from the description |

**The two halves of this must not be conflated, and an earlier revision of this
document conflated them.** Explicit invocation and suppressed implicit invocation are
different guarantees, and Antigravity grants the first while withholding the second:

- *Can a user run the skill deliberately?* On Antigravity CLI, yes — better than the
  host it replaced. Skills become slash commands for free, with no extra file to
  author or keep in sync.
- *Can the skill be prevented from running when nobody asked?* No. The documented
  frontmatter is two fields, and neither suppresses model invocation, so
  `disable-model-invocation` has nowhere to land on either Antigravity surface even
  if the other hosts honour it.

The retired Gemini CLI's confirmation prompt was the mitigation this decision leaned
on for that host. Its successor does not document a replacement. So the *gap* this
decision exists to close is wider now, even though invocation ergonomics improved.

Today, `/code-flow.map` runs **only when a user types it.** As a skill it may run because
a model decided the description matched what the user was talking about.

That matters more here than for most skills, because these commands are not read-only.
`code-flow.map` writes `Code_Flows/`, updates `index.json`, and **edits source files to
add missing docstrings.** A command with that blast radius should not start because a
conversation drifted near the topic.

**Decision: set `disable-model-invocation: true` on both skills, so they run only when
explicitly invoked.** Copilot documents this field for exactly this purpose. Where a host
has no equivalent, the skill's own first instruction is to confirm the target before
writing anything.

**Rejected: relying on Gemini's confirmation prompt.** It covers one host, is outside our
control, and a confirmation dialog for an action the user never asked for is a worse
experience than the action not starting.

**Consequence to disclose:** `disable-model-invocation` is a Copilot-documented field.
Whether Claude Code honours it is **not verified by this document** and must be tested
before the phase ships. For both Antigravity surfaces the answer is already known and it
is no: the field is not in their documented schema. If a host ignores it, the fallback is
the in-skill confirmation, and the README says which hosts have which guarantee.

**On Antigravity the in-skill confirmation is not a fallback, it is the only gate.** That
is a materially weaker guarantee than this decision was written to provide, and it lands
on the one command that edits source. Open Question 3 is where it gets resolved; it is
no longer hypothetical.

## Decision 4: `$ARGUMENTS` does not survive, and the flags need a new home

The Claude and Gemini templates take `$ARGUMENTS` and parse flags out of it —
`--whole-code-base`, `--detail thin|standard`, `--read-code`. The skill format has no
`$ARGUMENTS`; it has `argument-hint`, which is display text, not a substitution.

**Decision: the flags stay, stated in the skill body as things the user may say, and
`argument-hint` advertises them.** The assistant already parses the flags out of prose
today — no installer or CLI code has ever done it — so this is less of a change than it
looks. What changes is that the skill can no longer rely on a literal `$ARGUMENTS`
placeholder being substituted.

**Rejected: dropping the flags for separate skills** (`code-flow-map-whole-codebase` and
so on). It multiplies the artifact count, splits prose that must stay in agreement, and
recreates the parity problem under new names.

## Decision 5: bundle the HTML scaffolds as skill resources

Skills may bundle supporting files, referenced from `SKILL.md` by relative Markdown link,
with the documented caveat that *"If a file isn't referenced in the instructions, it won't
be loaded."*

**Decision: keep `.code-flow/viewer.template.html` and `.code-flow/report.template.html`
exactly where they are, and do not move them inside the skill directories.**

The scaffolds are read by the assistant at run time and written into `Code_Flows/`. They
are not instructions and do not want to be pulled into a model's context — `viewer.template.html`
is over a thousand lines. Referencing them as skill resources would load them into context
to no benefit.

**Rejected: bundling them.** It reads tidier and costs context on every activation.

## Decision 6: additive, and it ships *inside* `1.0.0`

**Amended after the Open Question 1 ruling.** This decision originally targeted `1.1.0`,
on the assumption that 1.0.0 would already be on the registries. It will not be: 1.0.0 is
held until this phase is implemented, so the skills ship as part of the first public
release rather than as a follow-up to it.

**Decision: Phase 4 installs the skills alongside the existing commands and prompt files.
Nothing is removed. Version stays `1.0.0`.**

Holding the release makes the version question simpler and the naming question moot —
there is no published `/code-flow.map` to rename out from under anyone, because there has
never been a published 1.x at all. The npm registry's latest is `0.2.0`, and PyPI has
nothing. The 0.x → 1.0 upgrade note in the README covers the rename in one place instead
of two.

It does **not** make the additive-versus-replacing question moot, and additive still wins.

Additive also hedges the real uncertainty: **this document has verified the format from
documentation, not from running it.** Shipping skills next to what already works means a
host that behaves differently than documented is a disappointment rather than an outage.

The deprecation path, deliberately not scheduled here: once the skills are confirmed
working against all three hosts in the wild, a later major version removes
`.claude/commands/`, `.gemini/commands/` and `.github/prompts/` and the rename becomes the
only form.

**Rejected: a clean `2.0.0` replacement.** Faster to a single format, and it bets the
whole integration on documentation this repository has not yet tested against three live
hosts. This project's stated posture is that an untested artifact is unknown, not
probably fine.

## What Phase 4 ships

- `templates/shared/code-flow-map/SKILL.md` and `templates/shared/code-flow-quality/SKILL.md`
- Installer changes in `bin/install.js` and `src/code_flow_skill/cli.py` to copy each
  skill to `.claude/skills/<name>/SKILL.md` and `.agents/skills/<name>/SKILL.md`
- `agent: agent` replacing `mode: agent` in both Copilot prompt files (Decision 0, likely
  landed earlier and separately)
- `tests/test_host_parity.py` re-pointed from divergence-measuring to byte-identity
- README: the new invocation forms, which host guarantees explicit invocation, and what
  the existing commands still do
- `CHANGELOG.md` entry
- Version `1.1.0` in `package.json` and `pyproject.toml`

## Testing

**Skill-name validity.** Both names match `^[a-z0-9-]{1,64}$` and the directory name
equals the `name` field. An invalid name fails silently at load, so this must be a test
and not a review item.

**Frontmatter contract.** `name` and `description` present, `description` at most 1024
characters, `disable-model-invocation` present and `true`.

**Byte identity.** Every installed skill file is byte-identical to its template, in both
languages, extending the existing `EXPECTED_ALL` machinery.

**Content contract.** The existing quality-template contract tests move to the single
`SKILL.md` and stop being parametrized over three hosts. The honesty phrasings —
"catalogued", "clean within what was mapped", `unreached` as a candidate — are unchanged
requirements and keep their tests.

**Not tested, disclosed:** that any host actually loads, matches or refuses to
auto-invoke these skills. No test in this repository can observe a host's behavior. This
is the same limitation every phase has disclosed, and Decision 3 depends on it more than
previous phases did — which is why Open Question 3 exists.

## Risks

- **The format is verified from documentation, not from running it.** Antigravity's
  pages document only `name` and `description`, describing workflow rather than a
  field-level `SKILL.md` specification, so frontmatter compatibility across the hosts
  is **assumed, not confirmed**. If Antigravity rejects a field the others require —
  or silently ignores one we depend on — the single-source-of-truth premise weakens and
  Decision 1 needs revisiting. This risk grew: the host documentation is now thinner
  than the retired host's, not richer.
- **`disable-model-invocation` may be Copilot-only.** Decision 3's safety property is
  only as good as the field's support. The in-skill confirmation is the fallback.
- **Auto-invocation on a file-writing command is the highest-consequence risk in this
  phase.** A model deciding on its own to run something that edits source files is worse
  than any parity bug this project has had.
- **Silent failure on a bad name.** Mitigated by a test, listed here because the failure
  gives the user nothing to search for.

## Open questions — these need a ruling

1. ~~**Does the `mode` → `agent` fix hold the 1.0.0 publish?**~~ **Ruled: 1.0.0 is held
   until Phase 4 is implemented.** Broader than the question asked — the whole release
   waits, not just the frontmatter fix. Consequences are folded into Decision 0 and
   Decision 6 above: the fix is no longer split out, and the skills ship inside 1.0.0
   rather than in a follow-up.

   Two consequences worth stating plainly, since holding a release is not free:
   nothing reaches a registry until a phase that is **verified from documentation rather
   than from running it** is finished, so Phase 4's risks are now release-blocking rather
   than additive; and the pre-publish manual browser pass will need re-running at the end
   of Phase 4 regardless of how many times it is run before then.

2. **Do the Gemini TOML commands survive Phase 4, or does Gemini move to skills only?**
   Gemini CLI supports both. Keeping both is more surface to maintain; dropping TOML loses
   explicit slash invocation on that host, which Decision 3 argues is worth something.

   **Answered, once the retirement is accounted for.** `.gemini/commands/*.toml` is a
   Gemini CLI mechanism, and Gemini CLI stopped serving individual users on 2026-06-18.
   Its successor gives us the thing the TOML file existed to provide, for free: on
   Antigravity CLI a skill *becomes* a slash command, with no second file to author or
   hold in parity. **Keeping TOML buys nothing on the successor and costs a fourth
   template.**

   A previous revision of this section reached the opposite conclusion by way of a
   wrong fact. It claimed Antigravity's only explicit-invocation surface was
   **Workflows** — markdown, `/workflow-name`, capped at 12,000 characters — and that
   our 22,041-character map template therefore could not be invoked explicitly there.
   The cap is real and the measurement was right, but the premise was not: Workflows
   are not the route, skills are, and skills have no documented size limit. That
   reasoning is struck.
   ([Antigravity workflows](https://antigravity.google/docs/ide/workflows/))

   **What survives is a smaller question about the remnant.** Gemini CLI is still
   supported for Gemini Code Assist Standard and Enterprise licences and paid API-key
   users. Dropping `.gemini/commands/*.toml` strands those users; keeping it means
   maintaining a template for a host that no longer takes new individual users. The
   recommendation is to **drop it and say so in the README's upgrade notes**, since the
   `.agents/skills/` copy still reaches Gemini CLI and only the slash-invocation
   ergonomics are lost — but the remnant is real and the call is the maintainer's.

3. **Is auto-invocation acceptable at all for `code-flow.map`,** given it edits source
   files to add docstrings? If the answer is no and `disable-model-invocation` turns out
   not to be portable, the honest conclusion is that `code-flow.map` should not be a skill
   on hosts that cannot suppress model invocation — and Phase 4 ships skills for
   `code-flow.quality`, which only writes reports, first.

   **Still the load-bearing question of this phase, for a narrower reason than a previous
   revision claimed.** That revision argued the hazard came from Antigravity having no
   explicit-invocation route; that was wrong, and Question 2 now records why. The hazard
   is the other half: **no documented field suppresses model invocation on either
   Antigravity surface**, and the host whose confirmation prompt used to cover this case
   has been retired without a documented replacement. Being able to type
   `/code-flow.map` does not stop the agent starting it unasked.

   So there is still no configuration in which `code-flow.map` is both available on
   Antigravity and unable to start on its own, and the choice is which of these to accept:

   - ship `code-flow.map` as a skill everywhere and rely on an in-skill confirmation that
     the model is free to skip, on the hosts where nothing else constrains it;
   - ship `code-flow.map` as a skill only on hosts that can suppress model invocation, and
     leave Antigravity with `code-flow.quality` alone — note this now means withholding it
     from the Gemini successor entirely, not from a minor fourth host;
   - make the docstring edit opt-in rather than default, which would shrink the blast
     radius enough that auto-invocation stops being the problem — the largest change of
     the three, and the only one that fixes the underlying hazard instead of routing
     around it. **Recommended**: it is the only option that does not degrade with the next
     host's invocation semantics, and this document has now been wrong twice about what
     those semantics are.

   This is a ruling to make, not a fact to look up.

## Deferred

`code-flow.violations` remains reserved and undesigned, unchanged from the parent.

Removal of the command and prompt-file integrations is deferred to a future major version
and deliberately not scheduled here.
