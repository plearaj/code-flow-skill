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
    field, so there the in-skill confirmation is the only gate. Codex has its own
    mechanism, asserted by the next test. That asymmetry is disclosed in the
    README rather than papered over.
    """
    fields = _frontmatter(_skill_path(repo_root, skill_dir).read_text(encoding="utf-8"))
    assert fields.get("disable-model-invocation") == "true", (
        f"{skill_dir}/SKILL.md does not set `disable-model-invocation: true`"
    )


@pytest.mark.parametrize("skill_dir,gemini_name", SKILL_TEMPLATES)
def test_skill_disables_implicit_invocation_on_codex(
    repo_root: Path, skill_dir: str, gemini_name: str
) -> None:
    """The same rule as the test above, for the one host that spells it
    differently. Codex ignores `disable-model-invocation` and reads
    `policy.allow_implicit_invocation` from a sibling `agents/openai.yaml`
    instead — "When `false`, Codex won't implicitly invoke the skill based on
    user prompt; explicit `$skill` invocation still works."

    Parsed as text rather than with a YAML library on purpose: this repository
    has no dependencies, including dev dependencies, and `pyyaml` is not worth
    acquiring for four lines. The assertion is deliberately strict about the
    nesting — a top-level `allow_implicit_invocation: false` outside the
    `policy:` block is a file Codex reads and ignores, which is the failure this
    test exists to catch and the one a looser substring search would miss.
    """
    path = repo_root / "templates" / "shared" / skill_dir / "agents" / "openai.yaml"
    assert path.is_file(), f"{skill_dir} has no agents/openai.yaml"
    text = path.read_text(encoding="utf-8")
    assert re.search(r"^policy:\s*$", text, re.MULTILINE), (
        f"{skill_dir}/agents/openai.yaml has no top-level `policy:` block"
    )
    assert re.search(
        r"^policy:\s*\n(?:[ \t]+.*\n)*?[ \t]+allow_implicit_invocation:\s*false\s*$",
        text,
        re.MULTILINE,
    ), (
        f"{skill_dir}/agents/openai.yaml does not set "
        f"`allow_implicit_invocation: false` inside its `policy:` block"
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
