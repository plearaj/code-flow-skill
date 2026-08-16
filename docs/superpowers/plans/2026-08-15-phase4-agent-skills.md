# Phase 4 — Agent Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship both commands in the Agent Skills open format — one canonical `SKILL.md` per command, installed unchanged to every directory a host discovers skills from — alongside the existing command and prompt files, and fix the dead `mode:` frontmatter key on the way past.

**Architecture:** Each command gets one `SKILL.md` under `templates/shared/<skill-name>/`. Its body is **derived** from the Gemini template's prompt by a documented substitution, not hand-written, so Phase 4 does not add a fourth copy of prose to keep in agreement — a test re-runs the derivation and compares. The installer copies each `SKILL.md` byte-for-byte to `.agents/skills/<name>/SKILL.md` always, and to `.claude/skills/<name>/SKILL.md` when the Claude selection is in play. Nothing is removed: the three host command templates keep working.

**Tech Stack:** Node ≥18 (`bin/install.js`, `node --test`), Python ≥3.11 (`src/code_flow_skill/cli.py`, pytest, `tomllib`). Zero runtime dependencies and zero dev dependencies beyond `pytest>=8.0`.

**Spec:** [`docs/superpowers/specs/2026-08-08-phase4-agent-skills-design.md`](../specs/2026-08-08-phase4-agent-skills-design.md)

---

## Prerequisites, before Task 1

Both must be on `master` before this plan starts:

1. **PR #12 — conditional Gemini install.** The spec's Open Question 2 ruling says it "ships ahead of the rest of this phase", and Task 3 edits the same function in both installers. Merging it after Task 3 is a conflict for no reason.
2. **PR #10 — the Phase 4 spec.** The plan links the spec at a repo-relative path; that link is broken until the spec is on the same branch.

Confirm with:

```bash
git log --oneline master -3 && ls docs/superpowers/specs/2026-08-08-phase4-agent-skills-design.md
```

Then branch:

```bash
git checkout -b feature/phase4-agent-skills master
```

## Global Constraints

- **Zero dependencies, including dev.** `package.json` has no `devDependencies` key and must not gain one. The Python dev group is exactly `pytest>=8.0`. Do not reach for PyYAML to parse frontmatter — Task 2 hand-parses it in nine lines.
- **Templates are LF-only on disk.** `tests/test_template_contracts.py::test_shipped_templates_have_no_crlf` walks `templates/` recursively and reads bytes. On Windows, `Path.write_text()` translates `\n` to `\r\n` silently. **Every step in this plan that writes a template file writes bytes**, never text. This has broken the repository twice.
- **The version stays `1.0.0`** in `package.json` and `pyproject.toml`. Decision 6 as amended holds 1.0.0 until this phase ships, so the skills go out *inside* the first public release. The spec's "What Phase 4 ships" list still says `1.1.0`; that bullet predates the Open Question 1 ruling further down the same document and is stale. `tests/test_packaging.py::test_package_versions_match_and_are_1_0_0` already pins this — do not touch it.
- **Skill names are `code-flow-map` and `code-flow-quality`** — lowercase letters, numbers and hyphens only, 64 characters maximum, `name` equal to the parent directory name. **This is one host's rule, not the format's**, and the spec's Decision 2 overstated it. See "Why hyphens" below before you decide it is arbitrary.
- **Both `SKILL.md` files carry `disable-model-invocation: true`.** See "One call to confirm" below before you write it.
- **Nothing is removed.** `.claude/commands/`, `.gemini/commands/` and `.github/prompts/` all keep shipping. `tests/test_host_parity.py`'s Claude↔Gemini divergence check keeps its current job and its `BASELINE_MAP = 27` / `BASELINE_QUALITY = 0` constants — those templates still exist, so they still need it.
- **The HTML scaffolds stay at `.code-flow/`.** Decision 5: they are read at run time and written into `Code_Flows/`; bundling a thousand-line file as a skill resource would load it into context for nothing.
- **No `git add -A`.** Stage the files each step names.
- **Every task ends with a mutation proof.** Break the rule the new test guards, watch the test fail, restore. A contract test that still passes with its rule deleted is worse than no test, and this repository has shipped one before.

## The hosts, and why hyphens

Five hosts read `.agents/skills/` or `.claude/skills/`. Verified against each host's own documentation on 2026-08-15/16, not inferred from one another:

| Host | Reads | Documented name rule | Explicit invocation |
|---|---|---|---|
| Claude Code | `.claude/skills/`, `.agents/skills/` | none stated; the **directory name** is the command and `name` is only a display label | `/code-flow-map` |
| GitHub Copilot | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | lowercase, digits, hyphens; **no dots**; must match the directory; **invalid names silently fail to load** | `/code-flow-map` |
| Antigravity CLI | `.agents/skills/` | none stated; `name` optional, defaults to the folder | `/code-flow-map` |
| Antigravity IDE | `.agents/skills/` | none stated; `name` optional, defaults to the folder | mention it by name |
| OpenAI Codex | `.agents/skills/` (`$CWD` and `$REPO_ROOT`) | none stated; `name` and `description` both required | `$code-flow-map`, or `/skills` |

**Codex needs no new install target.** Its repository-scope discovery paths are `"$CWD/.agents/skills"` and `"$REPO_ROOT/.agents/skills"` — the directory Task 3 already writes regardless of `--tool`. Nothing in Tasks 1-4 changes for it; it appears in Task 5's documentation and nowhere else.

**Why hyphens, given that four of the five hosts document no restriction.** The spec's Decision 2 said `code-flow.map` is "therefore an invalid skill name". That is too broad — it is invalid on Copilot, and undocumented-but-apparently-fine on the rest, which is why other projects ship dotted names to some hosts and dashed names to others. Two things make one hyphenated name the right call here anyway:

1. **Copilot reads `.claude/skills/` too.** A per-host split that put `code-flow.map/` in `.claude/skills/` would not be seen only by Claude Code — every Copilot user reading that same directory gets a skill that silently does not load, with nothing to search for. A split only helps where the hosts' directories are disjoint, and these two are not.
2. **The dotted name is already taken, by us.** Decision 6 keeps `.claude/commands/code-flow.map.md` shipping, and that file already produces `/code-flow.map` on Claude Code. A skill directory of the same name would be a second thing claiming one command on one host. The hyphen is what lets both forms coexist, which is the entire point of shipping additively.

So this is not "dots are illegal"; it is "the strictest consumer of a shared directory governs it, and the dotted name is spoken for." Keep that reasoning with the constraint — it is what a later reader needs when a sixth host arrives.

## One call to confirm before Task 2

The spec's Decision 3 ruling says to keep `disable-model-invocation: true` "where a host documents it, as a belt alongside those braces". That is what this plan implements. It means:

| Host | Can the model start the skill on its own? |
|---|---|
| Claude Code | No — the field is documented and honoured |
| Copilot | No — the field is documented and honoured |
| Antigravity CLI / IDE | **Yes** — the field is not in their two-key schema |

If instead the intent of "automatic invocation should be fine to have on" was that the model *should* be free to start these skills everywhere, then the field comes out of both files and Task 2 Step 3's frontmatter loses one line, Task 2's `test_skill_disables_model_invocation` is deleted, and Task 5's README table flips. Everything else in this plan is unchanged. **Flag this to your human partner before Task 2 and take their answer.** Do not guess: it is the difference between a file-writing skill that can only be typed and one that can start itself.

## File structure

**Created:**

| Path | Responsibility |
|---|---|
| `templates/shared/code-flow-map/SKILL.md` | The map command in the Agent Skills format. Frontmatter + preamble hand-written; body derived. |
| `templates/shared/code-flow-quality/SKILL.md` | The quality command, same shape. |
| `tests/test_skill_templates.py` | Everything true of a `SKILL.md` that reading it will not tell you: name validity, frontmatter contract, and that the body is still derived rather than drifted. |

**Modified:**

| Path | Change |
|---|---|
| `templates/copilot/code-flow.map.prompt.md` | `mode: agent` → `agent: agent` (Task 1) |
| `templates/copilot/code-flow.quality.prompt.md` | same (Task 1) |
| `tests/test_host_parity.py` | the Copilot frontmatter test re-pointed at `agent:` (Task 1) |
| `bin/install.js` | `installSkills()` and its two calls (Task 3) |
| `src/code_flow_skill/cli.py` | `_install_skills()` and its two calls (Task 3) |
| `tests/test_installer_python.py` | `EXPECTED_ALL` + three placement tests + byte identity (Tasks 3, 4) |
| `test/install.test.js` | the same, in Node (Tasks 3, 4) |
| `tests/test_packaging.py` | `EXPECTED_IN_WHEEL` gains the two `SKILL.md` paths (Task 4) |
| `README.md` | Files-written table (Task 3); invocation section, upgrade note (Task 5) |
| `CHANGELOG.md` | the 1.0.0 entry gains the skills (Task 5) |
| `scripts/prepublish-check.js` | one manual step no test can cover: does the skill load (Task 5) |
| `test/prepublish-check.test.js` | asserts the new step is named (Task 5) |

**Deliberately not changed, and why:**

- **`tests/test_template_contracts.py` gains nothing.** The spec's Testing section says the content contracts "move to the single `SKILL.md` and stop being parametrized over three hosts". That was written for a world where the host templates go away; Decision 6 keeps them, so the three-host parametrizations must stay. Adding `SKILL.md` as a fourth would be forty redundant assertions: the body is byte-identical to the Gemini body after a two-rule substitution, so every contract that holds for Gemini holds for the skill *by construction*, and Task 2's derivation test is what proves the construction. One test, not forty.
- **`tests/test_host_parity.py`'s divergence check.** Same reason. The spec's "re-pointed from divergence-measuring to byte-identity" describes the end state after a later major version removes the command templates.

## Task 1: The dead frontmatter key

`mode` is not a documented prompt-file property. The current properties are `description`, `name`, `argument-hint`, `agent`, `model` and `tools`. `tests/test_host_parity.py:141` asserts `mode: agent` is present — so the test currently guarantees the wrong thing, and will fail any correct change to that frontmatter. It goes first for that reason.

**Files:**
- Modify: `templates/copilot/code-flow.map.prompt.md:2`
- Modify: `templates/copilot/code-flow.quality.prompt.md:2`
- Test: `tests/test_host_parity.py:141-149`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing later tasks import. Task 2 onward assume both Copilot prompts carry `agent: agent`.

- [ ] **Step 1: Rewrite the failing test**

Replace the whole of `test_every_copilot_prompt_declares_agent_mode` in `tests/test_host_parity.py` (lines 141-149) with:

```python
def test_every_copilot_prompt_declares_its_agent(repo_root: Path) -> None:
    """`agent:` in the frontmatter is what makes a `.prompt.md` invocable in
    VS Code Copilot Chat at all. Without it the file installs and does nothing.

    This asserted `mode: agent` until 2026-08-15. `mode` is not a documented
    prompt-file property — the documented set is `description`, `name`,
    `argument-hint`, `agent`, `model` and `tools` — so the test was pinning a key
    that may never have been read, and would have failed any correct fix. The
    negative assertion is the point of the test now: without it, restoring the
    dead key alongside the live one passes.
    """
    prompts = sorted((repo_root / "templates" / "copilot").glob("*.prompt.md"))
    assert prompts, "no Copilot prompts found"
    for path in prompts:
        head = path.read_text(encoding="utf-8").split("---")[1]
        assert "agent: agent" in head, f"{path.name} frontmatter lacks `agent: agent`"
        assert "mode:" not in head, (
            f"{path.name} still carries the undocumented `mode:` key"
        )
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run --group dev pytest tests/test_host_parity.py -v
```

Expected: `test_every_copilot_prompt_declares_its_agent` FAILS twice over — the templates still say `mode: agent`, so both the positive and the negative assertion are wrong.

- [ ] **Step 3: Fix both templates**

In `templates/copilot/code-flow.map.prompt.md`, line 2 becomes:

```yaml
agent: agent
```

Do the same in `templates/copilot/code-flow.quality.prompt.md`, line 2. Nothing else in either file changes.

Use `Edit`, not a shell rewrite — a `sed -i` on Windows Git Bash can rewrite the whole file's line endings and trip `test_shipped_templates_have_no_crlf`.

- [ ] **Step 4: Run the full Python suite**

```bash
uv run --group dev pytest -v
```

Expected: all pass. Watch `test_shipped_templates_have_no_crlf` in particular — it is the one that catches a line-ending accident.

- [ ] **Step 5: Mutation proof**

Put `mode: agent` back into `templates/copilot/code-flow.map.prompt.md` *alongside* `agent: agent`, then:

```bash
uv run --group dev pytest tests/test_host_parity.py::test_every_copilot_prompt_declares_its_agent -v
```

Expected: FAIL on the negative assertion. If it passes, the negative assertion is not doing its job — fix it before continuing. Then remove the line again and re-run to confirm green.

- [ ] **Step 6: Commit**

```bash
git add templates/copilot/code-flow.map.prompt.md templates/copilot/code-flow.quality.prompt.md tests/test_host_parity.py
git commit -m "fix: replace the undocumented Copilot mode: key with agent:"
```

## Task 2: The two SKILL.md templates

The body of each skill is a pure function of the corresponding Gemini template. That is the whole design of this task, and it is worth being explicit about why: Phase 4 ships additively, so after it lands there are four artifacts carrying this prose. A fourth *hand-written* one would make this project's dominant recurring cost worse. A fourth *derived* one costs nothing to keep in agreement.

The Gemini prompt is the right source, not the Claude one. It is already the host-neutral copy by construction — `BASELINE_MAP`'s three documented divergence classes are exactly "Claude-only tool names removed", "plain three-backtick fences instead of four" and "ASCII instead of set-membership symbols". All three of those adaptations are what a body read by four different hosts wants.

**Files:**
- Create: `tests/test_skill_templates.py`
- Create: `templates/shared/code-flow-map/SKILL.md`
- Create: `templates/shared/code-flow-quality/SKILL.md`

**Interfaces:**
- Consumes: `templates/gemini/code-flow.map.toml`, `templates/gemini/code-flow.quality.toml` (read-only).
- Produces:
  - `derive_skill_body(gemini_template: Path) -> str` in `tests/test_skill_templates.py` — importable as `from tests.test_skill_templates import derive_skill_body`. Step 4 calls it to generate the files.
  - `SKILL_TEMPLATES: tuple[tuple[str, str], ...]` — pairs of `(skill_dir_name, gemini_template_filename)`.
  - The two installed skill directory names, `code-flow-map` and `code-flow-quality`, which Task 3's installers hard-code.

- [ ] **Step 1: Write the test module**

Create `tests/test_skill_templates.py`:

```python
"""Contracts for the two Agent Skills templates.

`templates/shared/code-flow-map/SKILL.md` and
`templates/shared/code-flow-quality/SKILL.md` are the open-standard form of the
two commands, copied unchanged into every directory a host discovers skills
from. Two things have to hold, and reading the files will tell you neither.

**The name must be valid, because an invalid one does not warn.** Of the five
hosts that read these directories, only Copilot documents a rule — "Only
lowercase letters, numbers, and hyphens are allowed... Do not use slashes,
colons, dots, or namespace prefixes", "Maximum 64 characters", "Must match the
parent directory name", and the sentence that makes this a test rather than a
review item: "Names with invalid characters cause the skill to silently fail to
load." Claude Code, both Antigravity surfaces and Codex state no restriction.

The strictest one still governs, because Copilot reads `.claude/skills/`
alongside `.agents/skills/` — there is no directory here that only a permissive
host sees, so there is no name that can be laxer in one place. A user on the
strict host would see the skill simply not exist, with nothing to search for.
The dotted name is separately unavailable: `.claude/commands/code-flow.map.md`
still ships and already answers to `/code-flow.map`.

**The body must stay derived, not hand-maintained.** Phase 4 ships additively, so
the three host templates still exist; a fourth hand-written copy of the same
prose would make this project's oldest and most expensive problem worse rather
than better. The body is therefore a pure function of the Gemini template's
prompt, and ``test_skill_body_is_derived_from_the_gemini_template`` is what holds
it there. Edit the Gemini template and regenerate; never edit a body by hand.

Frontmatter is parsed here by hand rather than with PyYAML. The two files this
reads have flat `key: value` frontmatter and no other shape is legal in them, and
this repository ships zero dependencies including dev ones — a YAML parser is a
large thing to add for nine lines of work.

Only the map skill is required to confirm before it writes. The quality skill
never edits source: it reads the map and writes documents. A confirmation gate on
a read-only report generator is friction that buys no safety.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

# (skill directory name, the Gemini template its body is derived from)
SKILL_TEMPLATES = (
    ("code-flow-map", "code-flow.map.toml"),
    ("code-flow-quality", "code-flow.quality.toml"),
)

# Where both bodies begin, in every host. Same marker `tests/test_host_parity.py`
# compares from, and for the same reason: everything above it is the host's own
# envelope, and everything below it is the shared instructions.
_BODY_START = "#### 1."

# Every character a skill name may contain, and how many.
_VALID_NAME = re.compile(r"^[a-z0-9-]{1,64}$")

# The Anthropic Agent Skills format caps `description` at 1024 characters.
# Claude Code separately truncates the combined description text at 1,536 in its
# skill listing. 1024 satisfies both, so it is the bound asserted here.
_MAX_DESCRIPTION = 1024

# The two rules that turn a Gemini prompt body into a skill body.
#
# 1. Decision 4: the skill format has no `$ARGUMENTS`; it has `argument-hint`,
#    which is display text and not a substitution. The flags survive as things
#    the user may say — only the placeholder goes.
# 2. Decision 2: a skill is invoked by its directory name, and a dot is not a
#    legal character in one. A body that told the user to run `/code-flow.map`
#    would be naming a command that does not exist on any host reading it.
_SUBSTITUTIONS = (
    ("The user's input (`$ARGUMENTS`)", "The user's request"),
    ("code-flow.map", "code-flow-map"),
    ("code-flow.quality", "code-flow-quality"),
)


def derive_skill_body(gemini_template: Path) -> str:
    """Return the skill body for a Gemini template: its prompt from the first
    step onward, with the substitutions above applied.

    Parsed with a real TOML parser rather than by stripping the ``'''``
    delimiters textually, for the reason `tests/test_host_parity.py` gives: a
    textual strip silently accepts a file the Gemini CLI cannot load.
    """
    prompt = tomllib.loads(gemini_template.read_text(encoding="utf-8"))["prompt"]
    body = prompt[prompt.index(_BODY_START) :]
    for old, new in _SUBSTITUTIONS:
        body = body.replace(old, new)
    return body


def _skill_path(repo_root: Path, skill_dir: str) -> Path:
    return repo_root / "templates" / "shared" / skill_dir / "SKILL.md"


def _frontmatter(text: str) -> dict[str, str]:
    """Parse the leading `---` block into a flat dict.

    Deliberately strict: the block must open on the very first line, and a line
    inside it that is not `key: value` is a parse failure rather than something
    to skip. A silently-skipped line is how a typo'd key name would pass every
    assertion below.
    """
    assert text.startswith("---\n"), "SKILL.md does not open with a frontmatter block"
    end = text.index("\n---\n", 3)
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        assert sep, f"frontmatter line is not `key: value`: {line!r}"
        fields[key.strip()] = value.strip().strip('"')
    return fields


@pytest.mark.parametrize("skill_dir,gemini_name", SKILL_TEMPLATES)
def test_skill_name_is_valid_and_matches_its_directory(
    repo_root: Path, skill_dir: str, gemini_name: str
) -> None:
    """An invalid name does not warn — the skill silently fails to load. Both
    halves matter: the character set, and the equality with the directory, which
    is what the host actually invokes."""
    fields = _frontmatter(_skill_path(repo_root, skill_dir).read_text(encoding="utf-8"))
    name = fields.get("name")
    assert name, f"{skill_dir}/SKILL.md has no `name` field"
    assert _VALID_NAME.match(name), (
        f"{skill_dir}/SKILL.md name {name!r} is not [a-z0-9-]{{1,64}} — a name with "
        f"invalid characters causes the skill to silently fail to load"
    )
    assert name == skill_dir, (
        f"{skill_dir}/SKILL.md declares name {name!r}; the name must equal the "
        f"parent directory name"
    )


@pytest.mark.parametrize("skill_dir,gemini_name", SKILL_TEMPLATES)
def test_skill_declares_a_description_within_the_cap(
    repo_root: Path, skill_dir: str, gemini_name: str
) -> None:
    """`description` is how every host decides the skill is relevant, and it is
    the one field all four hosts document as required or recommended."""
    fields = _frontmatter(_skill_path(repo_root, skill_dir).read_text(encoding="utf-8"))
    description = fields.get("description", "")
    assert description, f"{skill_dir}/SKILL.md has no `description` field"
    assert len(description) <= _MAX_DESCRIPTION, (
        f"{skill_dir}/SKILL.md description is {len(description)} characters, "
        f"over the {_MAX_DESCRIPTION} cap"
    )


@pytest.mark.parametrize("skill_dir,gemini_name", SKILL_TEMPLATES)
def test_skill_disables_model_invocation(
    repo_root: Path, skill_dir: str, gemini_name: str
) -> None:
    """Decision 3. Both commands write files; the map command also edits source.
    Where a host documents this field it is what keeps the skill from starting
    because a conversation drifted near its description.

    It is a belt, not the trousers: neither Antigravity surface documents the
    field, and Codex suppresses implicit invocation through its own `openai.yaml`
    metadata instead. On those three hosts the in-skill confirmation is the only
    gate. That asymmetry is disclosed in the README rather than papered over.
    """
    fields = _frontmatter(_skill_path(repo_root, skill_dir).read_text(encoding="utf-8"))
    assert fields.get("disable-model-invocation") == "true", (
        f"{skill_dir}/SKILL.md does not set `disable-model-invocation: true`"
    )


@pytest.mark.parametrize(
    "skill_dir,gemini_name,flags",
    (
        ("code-flow-map", "code-flow.map.toml", ("--whole-code-base", "--detail")),
        ("code-flow-quality", "code-flow.quality.toml", ("--read-code",)),
    ),
)
def test_skill_advertises_its_flags_in_the_argument_hint(
    repo_root: Path, skill_dir: str, gemini_name: str, flags: tuple[str, ...]
) -> None:
    """Decision 4: `$ARGUMENTS` does not survive, so `argument-hint` is the only
    place a host shows the user what this skill accepts. A skill whose flags are
    documented only in its body is one whose flags nobody discovers."""
    fields = _frontmatter(_skill_path(repo_root, skill_dir).read_text(encoding="utf-8"))
    hint = fields.get("argument-hint", "")
    for flag in flags:
        assert flag in hint, f"{skill_dir}/SKILL.md argument-hint does not offer {flag}"


@pytest.mark.parametrize("skill_dir,gemini_name", SKILL_TEMPLATES)
def test_skill_body_is_derived_from_the_gemini_template(
    repo_root: Path, skill_dir: str, gemini_name: str
) -> None:
    """The body is generated, not written. This is the test that makes that true.

    It fails in both directions, which is the point: edit `SKILL.md` by hand and
    it fails; edit the Gemini template without regenerating and it fails. Either
    way the two stop agreeing and somebody has to say which one is right.

    This test is also why `SKILL.md` is absent from the three-host
    parametrizations in `tests/test_template_contracts.py`. Every content
    contract that holds for the Gemini body holds for this one by construction,
    so re-asserting forty of them against a byte-identical string would be
    duplication that reads as coverage.
    """
    text = _skill_path(repo_root, skill_dir).read_text(encoding="utf-8")
    expected = derive_skill_body(repo_root / "templates" / "gemini" / gemini_name)
    assert _BODY_START in text, f"{skill_dir}/SKILL.md has no `{_BODY_START}` body"
    assert text[text.index(_BODY_START) :] == expected, (
        f"{skill_dir}/SKILL.md body has drifted from templates/gemini/{gemini_name}. "
        f"Regenerate it — do not edit the body by hand."
    )


@pytest.mark.parametrize("skill_dir,gemini_name", SKILL_TEMPLATES)
def test_skill_carries_no_arguments_placeholder(
    repo_root: Path, skill_dir: str, gemini_name: str
) -> None:
    """The skill format has no `$ARGUMENTS` substitution, so a surviving
    placeholder ships as literal text a user would read.

    This is the guard on the derivation itself. `_SUBSTITUTIONS` removes the one
    phrasing both templates use today; a future edit that introduces a *different*
    phrasing would sail past that rule and land the placeholder in the shipped
    skill. This assertion is what makes that loud.
    """
    text = _skill_path(repo_root, skill_dir).read_text(encoding="utf-8")
    assert "$ARGUMENTS" not in text, (
        f"{skill_dir}/SKILL.md still contains a $ARGUMENTS placeholder — the skill "
        f"format has no such substitution. Add its phrasing to _SUBSTITUTIONS."
    )


def test_map_skill_confirms_before_it_writes(repo_root: Path) -> None:
    """Decision 3's fallback, and on both Antigravity surfaces the only gate
    there is: no documented field suppresses model invocation on either.

    Scoped to the preamble above the first step, not the whole file — the body
    talks about confirming things too (`unreached` findings are "confirm before
    deleting"), so an unscoped search would stay green with this paragraph
    deleted outright.
    """
    text = _skill_path(repo_root, "code-flow-map").read_text(encoding="utf-8")
    head = text[: text.index(_BODY_START)]
    assert "wait for the user to confirm" in head, (
        "code-flow-map/SKILL.md does not tell the skill to confirm its target "
        "before writing anything"
    )
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run --group dev pytest tests/test_skill_templates.py -v
```

Expected: 13 failures, every one a `FileNotFoundError` — neither `SKILL.md` exists yet.

- [ ] **Step 3: Write the two frontmatter-and-preamble heads**

These are the hand-written parts. Everything from `#### 1.` onward is generated in Step 4, so write these to scratch files first and let the generator concatenate.

Write `head-map.txt` to your scratch directory, ending with a blank line after `### Instructions`:

```markdown
---
name: code-flow-map
description: Analyze and document the flow of a code feature, generating a markdown file and an interactive HTML page with flow diagrams and function reference tables.
argument-hint: "[functionality name] [--whole-code-base] [--detail thin|standard|verbose]"
disable-model-invocation: true
---

## Code Flow — Documentation Generator

Analyze the codebase and generate flow documentation for the requested functionality.

### Before you write anything

Name the flow you are about to map and wait for the user to confirm it, unless their
own request already named it. This skill writes files under `Code_Flows/` and adds
docstrings to source files that lack them. Some hosts start a skill because a
conversation drifted near its description rather than because anyone asked for it,
and on those hosts this paragraph is the only thing standing between that drift and
an edit to the user's code.

### User Input

The user's request says what to map, and may carry two option flags —
`--whole-code-base` and `--detail thin|standard|verbose`. Step 1 reads them.

### Instructions

```

Write `head-quality.txt` to your scratch directory, likewise ending with a blank line after `Follow these steps exactly.`:

```markdown
---
name: code-flow-quality
description: Report DRY, KISS and YAGNI findings from the persisted code-flow map, with file:line evidence and honest coverage.
argument-hint: "[--read-code]"
disable-model-invocation: true
---

## Code Flow — Quality Report

Read the map this project has already written under `Code_Flows/` and report where
it shows duplicated intent, needless complexity, and code that nothing reaches.

This skill **never edits source code.** `code-flow-map` adds missing docstrings
as it traces; this one writes documents and stops. Consolidating duplicates and
deleting suspected-dead code carry real blast radius, and that call is the user's.

### User Input

The user's request carries at most one flag, `--read-code`. Step 1 reads it.

### Instructions

Follow these steps exactly.

```

- [ ] **Step 4: Generate both files**

Run from the repository root. Set `SCRATCH` on its own line first — a `VAR=x cmd "$VAR"` prefix does not expand for the command's own arguments:

```bash
export SCRATCH="$LOCALAPPDATA/Temp/claude/scratch" && python - "$SCRATCH" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, ".")
from tests.test_skill_templates import SKILL_TEMPLATES, derive_skill_body

scratch = Path(sys.argv[1])
heads = {"code-flow-map": "head-map.txt", "code-flow-quality": "head-quality.txt"}

for skill_dir, gemini_name in SKILL_TEMPLATES:
    head = (scratch / heads[skill_dir]).read_text(encoding="utf-8")
    body = derive_skill_body(Path("templates/gemini") / gemini_name)
    out = Path("templates/shared") / skill_dir / "SKILL.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    # write_bytes, never write_text: on Windows the text path translates "\n"
    # to "\r\n" and ships CRLF templates to every consumer. This repository has
    # been bitten by it twice.
    out.write_bytes((head + body).encode("utf-8"))
    print(f"wrote {out} ({out.stat().st_size} bytes)")
PY
```

Then confirm no CRLF crept in and the heads joined cleanly:

```bash
python -c "import pathlib; [print(p, b'\r\n' in p.read_bytes()) for p in pathlib.Path('templates/shared').rglob('SKILL.md')]"
```

Expected: two lines, both ending `False`.

- [ ] **Step 5: Run the new tests**

```bash
uv run --group dev pytest tests/test_skill_templates.py -v
```

Expected: 13 passed.

- [ ] **Step 6: Run the full Python suite**

```bash
uv run --group dev pytest -v
```

Expected: all pass, including `test_shipped_templates_have_no_crlf`, which now walks two more files.

- [ ] **Step 7: Mutation proof, four ways**

Each of these must fail, and each must be restored before the next:

1. Change `name: code-flow-map` to `name: code-flow.map` in `templates/shared/code-flow-map/SKILL.md`. Run `pytest tests/test_skill_templates.py -v`. Expected: `test_skill_name_is_valid_and_matches_its_directory` FAILS on the character-set assertion. This is the mutation that matters most — it is the exact defect the format fails silently on.
2. Change one word inside the body of `templates/shared/code-flow-quality/SKILL.md`. Expected: `test_skill_body_is_derived_from_the_gemini_template` FAILS.
3. Delete the whole "### Before you write anything" paragraph from the map skill. Expected: `test_map_skill_confirms_before_it_writes` FAILS. If it passes, the assertion is matching body prose — fix the scoping before continuing.
4. Delete the `disable-model-invocation: true` line from either file. Expected: `test_skill_disables_model_invocation` FAILS.

Restore each file with the Step 4 generator (for 1, 2 and 4, which touch generated or frontmatter content, regenerate rather than hand-editing back) and re-run the suite green.

- [ ] **Step 8: Commit**

```bash
git add templates/shared/code-flow-map/SKILL.md templates/shared/code-flow-quality/SKILL.md tests/test_skill_templates.py
git commit -m "feat: add both commands in the Agent Skills format"
```

## Task 3: The installers write the skills

Where each copy goes, and why it is not simply "both, always":

- **`.agents/skills/` installs regardless of `--tool`.** Copilot, Antigravity CLI, Antigravity IDE, OpenAI Codex and the legacy Gemini CLI all discover skills there — every supported host except Claude Code, and Claude Code reads it too. That makes it tool-agnostic in exactly the sense `.code-flow/` already is, so it follows the same rule. It is also the whole of Codex support: Codex has no `--tool` value and needs none.
- **`.claude/skills/` rides on the `claude` selection.** Claude Code is its only consumer that no other path serves. Installing it unconditionally would put a `.claude/` directory into a `--tool gemini` install, breaking a promise `test_tool_selection_installs_only_that_tool` already holds us to and surprising a user who named a different host.

This refines the spec's "copy each skill to `.claude/skills/<name>/SKILL.md` and `.agents/skills/<name>/SKILL.md`", which does not say what `--tool` does to that. Under `--tool all` the outcome is the same two copies the spec describes.

**One disclosed consequence:** under `--tool all`, Copilot reads both directories and therefore sees each skill twice. Whether it dedupes by name is not documented and this repository cannot test it. Task 5 puts it in the release checklist, which is where this project's untestable claims go.

**Files:**
- Modify: `bin/install.js`
- Modify: `src/code_flow_skill/cli.py`
- Modify: `tests/test_installer_python.py`
- Modify: `test/install.test.js`
- Modify: `README.md` (the "Files written" table)

**Interfaces:**
- Consumes: `templates/shared/code-flow-map/SKILL.md` and `templates/shared/code-flow-quality/SKILL.md` from Task 2.
- Produces: four new entries in `EXPECTED_ALL` / `EXPECTED_ALL` (Python and Node), which Task 4 reads.

- [ ] **Step 1: Extend both expected-file lists**

In `tests/test_installer_python.py`, `EXPECTED_ALL` becomes (note `.agents` sorts before `.claude`):

```python
EXPECTED_ALL = [
    ".agents/skills/code-flow-map/SKILL.md",
    ".agents/skills/code-flow-quality/SKILL.md",
    ".claude/commands/code-flow.map.md",
    ".claude/commands/code-flow.quality.md",
    ".claude/skills/code-flow-map/SKILL.md",
    ".claude/skills/code-flow-quality/SKILL.md",
    ".code-flow/index.template.html",
    ".code-flow/report.template.html",
    ".code-flow/viewer.template.html",
    ".gemini/commands/code-flow.map.toml",
    ".gemini/commands/code-flow.quality.toml",
    ".github/prompts/code-flow.map.prompt.md",
    ".github/prompts/code-flow.quality.prompt.md",
]
```

Leave `EXPECTED_WITHOUT_GEMINI` alone — it is derived with `[p for p in EXPECTED_ALL if not p.startswith(".gemini/")]` and picks the new rows up on its own.

Make the identical change to `EXPECTED_ALL` in `test/install.test.js`.

- [ ] **Step 2: Write the placement tests**

Append to `tests/test_installer_python.py`:

```python
def test_agent_skills_install_regardless_of_tool(tmp_path: Path, run_python_installer) -> None:
    """`.agents/skills/` is the open standard's shared location — Copilot, both
    Antigravity surfaces and the legacy Gemini CLI all read it. That makes it
    tool-agnostic in the same sense `.code-flow/` is, so selecting a single host
    must still install it."""
    run_python_installer(tmp_path, tool="copilot")
    for name in ("code-flow-map", "code-flow-quality"):
        assert (tmp_path / ".agents" / "skills" / name / "SKILL.md").is_file(), (
            f".agents/skills/{name}/SKILL.md was not installed"
        )


def test_claude_skills_ride_on_the_claude_selection(
    tmp_path: Path, run_python_installer
) -> None:
    """Claude Code is the only consumer of `.claude/skills/` that no other path
    serves, so it follows the `claude` selection rather than installing
    unconditionally. A `--tool gemini` install must still leave no `.claude/`
    behind — the same promise `test_tool_selection_installs_only_that_tool`
    makes about the command files."""
    run_python_installer(tmp_path, tool="gemini")
    assert (tmp_path / ".agents" / "skills" / "code-flow-map" / "SKILL.md").is_file()
    assert not (tmp_path / ".claude").exists()


def test_claude_selection_installs_both_skill_roots(
    tmp_path: Path, run_python_installer
) -> None:
    run_python_installer(tmp_path, tool="claude")
    for root in (".claude", ".agents"):
        for name in ("code-flow-map", "code-flow-quality"):
            assert (tmp_path / root / "skills" / name / "SKILL.md").is_file(), (
                f"{root}/skills/{name}/SKILL.md was not installed"
            )
```

Append the Node equivalents to `test/install.test.js`:

```js
test("agent skills install regardless of tool", () => {
  const target = tempTarget();
  runInstaller(target, "copilot");
  for (const name of ["code-flow-map", "code-flow-quality"]) {
    assert.ok(
      fs.existsSync(path.join(target, ".agents", "skills", name, "SKILL.md")),
      `.agents/skills/${name}/SKILL.md was not installed`,
    );
  }
});

test("claude skills ride on the claude selection", () => {
  const target = tempTarget();
  runInstaller(target, "gemini");
  assert.ok(fs.existsSync(path.join(target, ".agents", "skills", "code-flow-map", "SKILL.md")));
  assert.ok(!fs.existsSync(path.join(target, ".claude")));
});

test("the claude selection installs both skill roots", () => {
  const target = tempTarget();
  runInstaller(target, "claude");
  for (const root of [".claude", ".agents"]) {
    for (const name of ["code-flow-map", "code-flow-quality"]) {
      assert.ok(
        fs.existsSync(path.join(target, root, "skills", name, "SKILL.md")),
        `${root}/skills/${name}/SKILL.md was not installed`,
      );
    }
  }
});
```

- [ ] **Step 3: Run both suites and watch them fail**

```bash
uv run --group dev pytest tests/test_installer_python.py -v
```

```bash
npm test
```

Expected: in Python, `test_tool_all_installs_exactly_the_expected_file_set` plus the three new tests fail. In Node, the same four. The installers write no skills yet.

- [ ] **Step 4: Teach `bin/install.js` to install skills**

Add after the `toolMap` definition and before the `for (const name of selected)` loop:

```js
// One canonical SKILL.md per command, copied unchanged to every directory a
// host discovers skills from.
//
// `.agents/skills/` is the open standard's shared location — Copilot, both
// Antigravity surfaces, OpenAI Codex and the legacy Gemini CLI all read it — so
// it installs regardless of --tool, the way the .code-flow/ scaffolds do. It is
// also the entirety of Codex support: Codex discovers repository skills from
// $CWD/.agents/skills and $REPO_ROOT/.agents/skills and has no --tool value of
// its own. `.claude/skills/` has exactly one consumer no other path serves,
// Claude Code, so it rides on that selection instead; a `--tool gemini` install
// must still leave no `.claude/` behind. This list and the one in
// src/code_flow_skill/cli.py must stay in step; the installed-file-set tests in
// both languages hold them there.
const skillNames = ["code-flow-map", "code-flow-quality"];

function installSkills(root) {
  for (const name of skillNames) {
    const src = path.join(pkgRoot, "templates", "shared", name, "SKILL.md");
    const dst = path.join(target, root, "skills", name, "SKILL.md");
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
    console.log(`Installed skill: ${dst}`);
  }
}
```

Then, between the end of the `for (const name of selected)` loop and the `installShared();` call:

```js
if (selected.includes("claude")) {
  installSkills(".claude");
}
installSkills(".agents");

installShared();
```

- [ ] **Step 5: Teach `src/code_flow_skill/cli.py` the same**

Add after `_TOOL_LABELS`:

```python
# One canonical SKILL.md per command, copied unchanged to every directory a host
# discovers skills from.
#
# `.agents/skills/` is the open standard's shared location — Copilot, both
# Antigravity surfaces, OpenAI Codex and the legacy Gemini CLI all read it — so
# it installs regardless of --tool, the way the .code-flow/ scaffolds do. It is
# also the entirety of Codex support: Codex discovers repository skills from
# $CWD/.agents/skills and $REPO_ROOT/.agents/skills and has no --tool value of
# its own. `.claude/skills/` has exactly one consumer no other path serves,
# Claude Code, so it rides on that selection instead; a `--tool gemini` install
# must still leave no `.claude/` behind. This table and the one in
# bin/install.js must stay in step; the installed-file-set tests in both
# languages hold them there.
_SKILL_NAMES = ("code-flow-map", "code-flow-quality")


def _install_skills(target: Path, root: str) -> None:
    """Copy both skills into one discovery root.

    A plain copy, deliberately: ``shutil.copyfile`` preserves bytes, where a
    text-mode read/write round-trip would translate "\\n" to "\\r\\n" on Windows
    and silently corrupt every shipped template.
    """
    for name in _SKILL_NAMES:
        out = target / root / "skills" / name / "SKILL.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_template_path("shared", name, "SKILL.md"), out)
        print(f"Installed skill: {out}")
```

In `main()`, between the tool loop and `_install_shared(target)`:

```python
    if "claude" in selected:
        _install_skills(target, ".claude")
    _install_skills(target, ".agents")

    _install_shared(target)
```

- [ ] **Step 6: Run both suites**

```bash
uv run --group dev pytest -v
```

```bash
npm test
```

Expected: Python all pass except `test_readme_files_written_table_lists_exactly_the_installed_set`, which now fails because the README table is four rows short. Node all pass.

- [ ] **Step 7: Update the README's Files-written table**

In `README.md`, the `## Files written` table gains four rows and the paragraph under it gains a sentence. Replace the table and the paragraph following it with:

```markdown
| Tool | Command | Path |
|------|---------|------|
| Claude Code | `/code-flow.map` | `.claude/commands/code-flow.map.md` |
| Claude Code | `/code-flow.quality` | `.claude/commands/code-flow.quality.md` |
| Claude Code | `/code-flow-map` | `.claude/skills/code-flow-map/SKILL.md` |
| Claude Code | `/code-flow-quality` | `.claude/skills/code-flow-quality/SKILL.md` |
| Gemini CLI | `/code-flow.map` | `.gemini/commands/code-flow.map.toml` |
| Gemini CLI | `/code-flow.quality` | `.gemini/commands/code-flow.quality.toml` |
| GitHub Copilot | `/code-flow.map` | `.github/prompts/code-flow.map.prompt.md` |
| GitHub Copilot | `/code-flow.quality` | `.github/prompts/code-flow.quality.prompt.md` |
| Copilot, Antigravity, Codex, Gemini CLI | `/code-flow-map` | `.agents/skills/code-flow-map/SKILL.md` |
| Copilot, Antigravity, Codex, Gemini CLI | `/code-flow-quality` | `.agents/skills/code-flow-quality/SKILL.md` |
| _All tools_ | — | `.code-flow/viewer.template.html` (interactive HTML scaffold) |
| _All tools_ | — | `.code-flow/report.template.html` (quality report viewer scaffold) |
| _All tools_ | — | `.code-flow/index.template.html` (flow index scaffold) |

The `.code-flow/viewer.template.html`, `.code-flow/report.template.html` and `.code-flow/index.template.html` scaffolds are tool-agnostic and are installed regardless of which `--tool` you select, since every command template references one of them.

`.agents/skills/` is installed regardless of `--tool` for the same reason: it is the shared location every supported host reads. `.claude/skills/` is the one directory only Claude Code reads, so it installs with the `claude` selection — `--tool gemini` still leaves no `.claude/` directory in your project.

**OpenAI Codex has no `--tool` value and does not need one.** It discovers repository skills from `.agents/skills/`, which every install writes.
```

- [ ] **Step 8: Run the full Python suite**

```bash
uv run --group dev pytest -v
```

Expected: all pass.

- [ ] **Step 9: Run both installers for real**

Not a test — a check that the thing works outside a fixture. Substitute your own scratch directory:

```bash
rm -rf "$LOCALAPPDATA/Temp/claude/wire" && mkdir -p "$LOCALAPPDATA/Temp/claude/wire/js" "$LOCALAPPDATA/Temp/claude/wire/py" && node bin/install.js --target "$LOCALAPPDATA/Temp/claude/wire/js" --tool claude && uv run python -m code_flow_skill.cli --target "$LOCALAPPDATA/Temp/claude/wire/py" --tool copilot && find "$LOCALAPPDATA/Temp/claude/wire" -name SKILL.md | sort
```

Expected: the Node run (`--tool claude`) prints four `Installed skill:` lines and the Python run (`--tool copilot`) prints two, and `find` lists **six** `SKILL.md` files — `js/.claude/skills/` ×2, `js/.agents/skills/` ×2, `py/.agents/skills/` ×2. No `py/.claude/` directory exists, which is the point of the copilot run.

- [ ] **Step 10: Mutation proof, four ways**

Each must fail; restore between each:

1. In `bin/install.js`, change `installSkills(".agents");` to run only when `selected.includes("gemini")`. Expected: `npm test` fails "agent skills install regardless of tool".
2. In `bin/install.js`, make `installSkills(".claude")` unconditional. Expected: `npm test` fails "claude skills ride on the claude selection" *and* "tool selection installs only that tool".
3. In `src/code_flow_skill/cli.py`, delete the `_install_skills(target, ".agents")` call. Expected: pytest fails `test_agent_skills_install_regardless_of_tool` and `test_tool_all_installs_exactly_the_expected_file_set`.
4. Delete one `.agents/` row from the README table. Expected: pytest fails `test_readme_files_written_table_lists_exactly_the_installed_set`.

- [ ] **Step 11: Commit**

```bash
git add bin/install.js src/code_flow_skill/cli.py tests/test_installer_python.py test/install.test.js README.md
git commit -m "feat: install both skills to .agents/skills and .claude/skills"
```

## Task 4: Byte identity and the packages

The installer is a copy, not a transform. Task 3 proved the files land; this proves they land unchanged, and that they reach a built package at all. Both are the class of defect that ships silently: a text-mode round-trip corrupts line endings without changing the file list, and a packaging config that misses a directory produces an installer that works from a checkout and fails from the registry.

**Files:**
- Modify: `tests/test_installer_python.py` (the byte-identity mapping)
- Modify: `test/install.test.js` (a byte-identity test, which the Node side does not have yet)
- Modify: `tests/test_packaging.py` (`EXPECTED_IN_WHEEL`)

**Interfaces:**
- Consumes: the installers from Task 3, `EXPECTED_ALL` from Task 3.
- Produces: nothing later tasks read.

- [ ] **Step 1: Extend the Python byte-identity mapping**

In `tests/test_installer_python.py`, add four entries to the `installed_to_source` dict inside `test_installed_files_are_byte_identical_to_their_templates` — both installed copies of each skill map to the one template:

```python
        tmp_path / ".claude" / "skills" / "code-flow-map" / "SKILL.md":
            repo_root / "templates" / "shared" / "code-flow-map" / "SKILL.md",
        tmp_path / ".agents" / "skills" / "code-flow-map" / "SKILL.md":
            repo_root / "templates" / "shared" / "code-flow-map" / "SKILL.md",
        tmp_path / ".claude" / "skills" / "code-flow-quality" / "SKILL.md":
            repo_root / "templates" / "shared" / "code-flow-quality" / "SKILL.md",
        tmp_path / ".agents" / "skills" / "code-flow-quality" / "SKILL.md":
            repo_root / "templates" / "shared" / "code-flow-quality" / "SKILL.md",
```

That test already calls `(tmp_path / ".gemini").mkdir()` before installing, so `--tool all` takes the Gemini branch and every path in the mapping exists. Leave that line in place.

- [ ] **Step 2: Give the Node side a byte-identity test**

Append to `test/install.test.js`:

```js
test("installed skills are byte-identical to their template", () => {
  const target = tempTarget();
  // .gemini/ makes `--tool all` take the Gemini branch, so the install under
  // test is the full one rather than the reduced set.
  fs.mkdirSync(path.join(target, ".gemini"), { recursive: true });
  runInstaller(target, "all");

  for (const name of ["code-flow-map", "code-flow-quality"]) {
    const source = fs.readFileSync(
      path.join(repoRoot, "templates", "shared", name, "SKILL.md"),
    );
    for (const root of [".claude", ".agents"]) {
      const installed = fs.readFileSync(path.join(target, root, "skills", name, "SKILL.md"));
      assert.deepEqual(
        installed,
        source,
        `${root}/skills/${name}/SKILL.md is not byte-identical to its template`,
      );
    }
  }
});
```

- [ ] **Step 3: Extend the wheel manifest test**

In `tests/test_packaging.py`, `EXPECTED_IN_WHEEL` gains two entries:

```python
    "code_flow_skill/templates/shared/code-flow-map/SKILL.md",
    "code_flow_skill/templates/shared/code-flow-quality/SKILL.md",
```

No change is needed to `pyproject.toml` or `package.json`: hatchling's `force-include` of `"templates"` and npm's `files: ["templates"]` are both recursive. This test is what proves that rather than assuming it.

- [ ] **Step 4: Run everything**

```bash
uv run --group dev pytest -v
```

```bash
npm test
```

Expected: all pass. `test_wheel_contains_templates` shells out to `uv build`, so it is slower than the rest — that is normal.

- [ ] **Step 5: Mutation proof, two ways**

1. In `src/code_flow_skill/cli.py`, change `_install_skills` to read and re-write the file as text instead of `shutil.copyfile`:

   ```python
           out.write_text(_template_path("shared", name, "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
   ```

   Expected on Windows: `test_installed_files_are_byte_identical_to_their_templates` FAILS on line endings. This is the real historical bug, reproduced. Restore `shutil.copyfile`.

2. In `pyproject.toml`, change the force-include line to `"templates/shared" = "code_flow_skill/templates/shared"`. Expected: `test_wheel_contains_templates` FAILS listing the six missing host templates. Restore it.

- [ ] **Step 6: Commit**

```bash
git add tests/test_installer_python.py test/install.test.js tests/test_packaging.py
git commit -m "test: assert installed skills are byte-identical and reach the wheel"
```

## Task 5: What users read, and the gate before publishing

Two invocation forms now exist for the same two commands, with different names and different auto-invocation guarantees per host. Every one of those differences is a thing a user hits and cannot discover from the files.

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `scripts/prepublish-check.js`
- Modify: `test/prepublish-check.test.js`

**Interfaces:**
- Consumes: the installed paths from Task 3.
- Produces: nothing.

- [ ] **Step 1: Add the invocation section to the README**

Insert a new `## Skills and commands` section immediately before `## CLI options`:

```markdown
## Skills and commands

Every host now gets the same two commands twice: as the command or prompt file it
has always had, and as an [Agent Skill](https://code.visualstudio.com/docs/agent-customization/agent-skills)
under `.agents/skills/` (and `.claude/skills/` for Claude Code). Nothing was
removed. If `/code-flow.map` works for you today, it still works.

**This is also how OpenAI Codex is supported.** Codex reads repository skills from
`.agents/skills/`, which every install writes, so it needs no `--tool` value of
its own. There is no Codex-specific command file and there does not need to be.

The two forms differ in three ways worth knowing before you pick one.

**The names differ, and they had to.** The skill form is `/code-flow-map` and
`/code-flow-quality`, with hyphens; the command form keeps `/code-flow.map` and
`/code-flow.quality`, with dots. Only Copilot documents a character rule for skill
names — no dots, and an invalid name silently fails to load — but Copilot reads
the same `.claude/skills/` directory Claude Code does, so there is no directory
where a laxer name would be safe. The dot is also spoken for: on Claude Code
`/code-flow.map` already belongs to the command file, which still ships.

**Who can start them differs by host.** Both skills set
`disable-model-invocation: true`, which asks the host to run them only when you
invoke them yourself. Not every host implements it:

| Host | Skill directory it reads | Can the assistant start the skill unasked? |
|---|---|---|
| Claude Code | `.claude/skills/`, `.agents/skills/` | No |
| GitHub Copilot | `.claude/skills/`, `.agents/skills/` | No |
| Antigravity CLI | `.agents/skills/` | **Yes** — the field is not in its schema |
| Antigravity IDE | `.agents/skills/` | **Yes** — the field is not in its schema |
| OpenAI Codex | `.agents/skills/` | **Yes** — it suppresses implicit invocation through its own `openai.yaml` metadata, not this field |
| Gemini CLI (legacy) | `.agents/skills/` | Yes, with a confirmation prompt |

On Codex, explicit invocation is `$code-flow-map` or the `/skills` menu rather
than a slash command.

On the hosts in the "Yes" rows, `code-flow-map` can begin because the conversation
drifted near what it does, rather than because you asked. That matters more for
this command than most: it writes files under `Code_Flows/` **and adds docstrings
to source files that lack them**. Its first instruction is therefore to name the
flow it is about to map and wait for you to confirm — a gate the assistant is free
to skip, which is why this table is here rather than buried. The edits are
additive, never rewrites or deletions. If that trade is not one you want, use the
command form on those hosts, or don't install the skill.

**The flags work the same in both.** `--whole-code-base`, `--detail
thin|standard|verbose` and `--read-code` are read out of what you type either way.
The skill format has no `$ARGUMENTS` substitution, so the skills advertise their
flags through `argument-hint` instead — your host shows them during autocomplete.
```

- [ ] **Step 2: Extend the README's upgrade note**

In `## Upgrading from 0.x to 1.0`, add this paragraph at the end of the section:

```markdown
**The skills are new in 1.0 and additive.** You do not have to migrate to them.
They install alongside the command and prompt files, under different names
(`/code-flow-map`, not `/code-flow.map`), and both forms read the same
`Code_Flows/` artifacts — a flow mapped by one is readable by the other. See
[Skills and commands](#skills-and-commands) for which host gives which guarantee.
```

- [ ] **Step 3: Add the CHANGELOG entry**

In `CHANGELOG.md`, inside the `### Added` list of `## [1.0.0]`, insert after the `Code_Flows/index.html` bullet:

```markdown
- **Both commands as Agent Skills** — one canonical `SKILL.md` per command,
  installed unchanged to `.agents/skills/` (read by Copilot, both Antigravity
  surfaces, OpenAI Codex and Gemini CLI) and `.claude/skills/` (Claude Code).
  They are named `/code-flow-map` and `/code-flow-quality`, with hyphens, because
  Copilot allows no dot in a skill name and fails to load an invalid one without
  saying so — and it reads the same directories the permissive hosts do. The
  commands and prompt files are unchanged and still ship: this is additive, and
  the format is verified from five hosts' documentation rather than from running
  it, which is why both forms go out together.
- **OpenAI Codex support**, which is the above and nothing else. Codex discovers
  repository skills from `.agents/skills/`, so every install already reaches it.
  There is no `--tool codex`, because there is no Codex-specific file to install.
- **Copilot prompt files declare `agent: agent`**, not the undocumented `mode:`
  key they carried through development. `mode` is not a documented prompt-file
  property, and the parity test that was supposed to guard the frontmatter was
  asserting the wrong key.
```

- [ ] **Step 4: Add the release-check step**

In `scripts/prepublish-check.js`, add a fourth numbered item to `CHECKLIST` after item 3, and amend the closing line:

```js
  4. Install into a scratch project with --tool all and open one host. Confirm
     /code-flow-map appears in its slash menu, and that Copilot — which reads
     both .claude/skills/ and .agents/skills/ — lists it once rather than
     twice. An invalid or duplicated skill name does not warn; the skill just
     silently does not load, or loads twice. No test here can see either.
```

Change the closing line from:

```js
Do this for ALL THREE files. A change to any scaffold's rendering re-opens
the gap, and the suites will not tell you.
```

to:

```js
Do this for ALL THREE files, and do step 4 for at least one host. A change to
any scaffold's rendering — or to a skill's name or frontmatter — re-opens the
gap, and the suites will not tell you.
```

- [ ] **Step 5: Assert the new step is named**

In `test/prepublish-check.test.js`, add to the test that checks the checklist names every manual step:

```js
  assert.match(r.stdout, /slash menu/i, "checklist does not cover skill loading");
  assert.match(r.stdout, /rather than\s+twice/i, "checklist does not cover duplicate registration");
```

- [ ] **Step 6: Run both suites**

```bash
npm test
```

```bash
uv run --group dev pytest -v
```

Expected: all pass.

- [ ] **Step 7: Mutation proof**

Delete item 4 from `CHECKLIST` in `scripts/prepublish-check.js` and run `npm test`. Expected: the prepublish-check test FAILS on both new assertions. Restore it.

- [ ] **Step 8: Confirm the release gate still blocks**

```bash
npm run release-check
```

Expected: the checklist prints with four numbered items, then exits non-zero with "Publish blocked". **Do not set `CODE_FLOW_RELEASE_CHECKED=1`** — that variable attests that a human performed the manual pass, and running it yourself would be a false attestation.

- [ ] **Step 9: Commit**

```bash
git add README.md CHANGELOG.md scripts/prepublish-check.js test/prepublish-check.test.js
git commit -m "docs: document the skill form, its per-host guarantees and its release gate"
```

## After the last task

Run both suites one more time on the merged tree, then use superpowers:finishing-a-development-branch. The base branch is `master`.

Two things are true at the end of this plan and should be said out loud rather than assumed:

1. **Nothing here verifies that any host loads these skills.** Every claim about discovery paths, frontmatter keys and invocation semantics in this plan comes from documentation read on 2026-08-15, not from a host that ran it. That is the same limitation every phase of this project has disclosed, and Task 5's checklist item 4 is the only thing that closes it.
2. **1.0.0 is publishable once this lands**, subject to the manual browser pass and the npm/PyPI credentials, which are the user's to supply.
