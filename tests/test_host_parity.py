"""Host parity, made executable.

"Claude and Gemini carry the same content from `#### 1.` onward" is this
project's strongest binding constraint, and until this module existed the only
thing enforcing it was a script pasted into a plan document that each task
re-ran by hand. After merge, a one-word edit to either template drifts them and
every other suite stays green.

This module also parses the Gemini templates. Nothing else in the repository
did: a stray ``'''`` inside a prompt body would ship a file the Gemini CLI
cannot load, with the whole Python suite passing.

The comparison is ported from the script in
``docs/superpowers/plans/2026-08-07-phase3a-quality-command.md`` (Task 1
Step 8) and its phase-2 predecessor, deliberately unchanged in substance.
"""
from __future__ import annotations

import difflib
import tomllib
from pathlib import Path

import pytest

# --- Baselines -------------------------------------------------------------
#
# BASELINE_QUALITY is 0 **by construction**. The quality templates were written
# in one phase from a single canonical text applied to both hosts, so there is
# no inherited divergence to carry and no legitimate reason for a line to
# differ: the text names no host-specific tool, needs no nested fence, and is
# already ASCII. It must stay 0. A change that raises it is a change that said
# something to one host and not the other — fix the templates, never this
# constant.
BASELINE_QUALITY = 0

# BASELINE_MAP is 27 lines of *inherited* divergence, measured at the phase-2
# branch point and revised twice since (33 -> 29 -> 27). Every one of those
# lines belongs to one of three documented classes:
#
#   1. Claude-only tool names removed for Gemini — Claude says "Use `Glob` to
#      find relevant files"; Gemini says "Search for relevant files by name
#      pattern". Reconciling these would name tools the Gemini host does not
#      have.
#   2. Fence width — Claude wraps examples containing nested fences in
#      four-backtick fences because its own file is markdown; inside Gemini's
#      TOML ''' string that wrapper is unnecessary, so Gemini uses plain
#      three-backtick fences.
#   3. Non-ASCII versus ASCII — Claude writes the set-membership and
#      less-than-or-equal symbols; Gemini writes "is one of" and "up to".
#
# Plus two accepted wording variants, recorded so they are recognized as known
# rather than re-investigated each time: "Analyze the function's code to
# understand..." (Claude) versus "Analyze the function to understand..."
# (Gemini), and step 5b's self-validation note being parenthesized in Claude
# and unparenthesized in Gemini.
#
# Fewer than the baseline means one of the deliberate adaptations was "fixed" —
# restore it. More means new divergence was introduced.
BASELINE_MAP = 27

# The QA and violations templates were written the same way the quality ones were
# — one canonical body applied to every host — so they inherit the same zero, and
# for the same reason: nothing in either body names a host-specific tool, needs a
# nested fence, or is non-ASCII where the other is not.
BASELINE_QA = 0
BASELINE_VIOLATIONS = 0

TEMPLATE_PAIRS = (
    ("quality", "code-flow.quality.md", "code-flow.quality.toml", BASELINE_QUALITY),
    ("map", "code-flow.map.md", "code-flow.map.toml", BASELINE_MAP),
    ("qa", "code-flow.qa.md", "code-flow.qa.toml", BASELINE_QA),
    ("violations", "code-flow.violations.md", "code-flow.violations.toml", BASELINE_VIOLATIONS),
)

# Both bodies are compared from this marker onward. Everything above it is each
# host's own envelope: Claude's YAML frontmatter and "## User Input" block,
# Gemini's `description =` key and its own user-input line.
_BODY_START = "#### 1."


def _gemini_prompt(path: Path) -> str:
    """Extract Gemini's prose with a real TOML parser.

    Stripping the ``'''`` delimiters textually would silently accept a file the
    Gemini CLI cannot load, which is the failure this module exists to catch.
    """
    return tomllib.loads(path.read_text(encoding="utf-8"))["prompt"]


def _divergent_lines(claude_body: str, gemini_body: str) -> list[str]:
    """Return the diff lines between two bodies, one per inserted or deleted line.

    ``autojunk=False`` is REQUIRED, not a preference. difflib's autojunk
    heuristic activates once a sequence reaches 200 elements and treats any line
    occurring in more than 1% of it as junk — which, in a document this size,
    means blank lines. It then stops matching on them and manufactures phantom
    divergences: during phase 2 the count jumped 29 -> 33 with no edit
    responsible. ``difflib.unified_diff`` gives no way to disable it, so this
    uses ``SequenceMatcher`` directly. Do not "simplify" this back.
    """
    c = claude_body.splitlines()
    g = gemini_body.splitlines()
    matcher = difflib.SequenceMatcher(None, c, g, autojunk=False)
    diff: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        diff += ["-" + line for line in c[i1:i2]] + ["+" + line for line in g[j1:j2]]
    return diff


@pytest.mark.parametrize("label,claude_name,gemini_name,baseline", TEMPLATE_PAIRS)
def test_claude_and_gemini_bodies_match_their_baseline(
    repo_root: Path, label: str, claude_name: str, gemini_name: str, baseline: int
) -> None:
    claude = (repo_root / "templates" / "claude" / claude_name).read_text(encoding="utf-8")
    gemini = _gemini_prompt(repo_root / "templates" / "gemini" / gemini_name)
    claude_body = claude[claude.index(_BODY_START) :]
    gemini_body = gemini[gemini.index(_BODY_START) :]
    diff = _divergent_lines(claude_body, gemini_body)
    assert len(diff) == baseline, (
        f"{label} templates: divergent lines: {len(diff)} (baseline {baseline})\n"
        + "\n".join(diff)
    )


def test_the_generated_baselines_are_zero() -> None:
    """Pinned separately from the comparison above so that lowering the bar is
    itself a test failure, not a quiet edit to a constant the diff test reads.

    Three of the four pairs are zero. Only `map` carries inherited divergence,
    and only because it predates the practice of writing one body per command."""
    assert BASELINE_QUALITY == 0
    assert BASELINE_QA == 0
    assert BASELINE_VIOLATIONS == 0
    assert BASELINE_MAP == 27


def _gemini_templates(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "templates" / "gemini").glob("*.toml"))


def test_every_gemini_template_is_loadable_toml(repo_root: Path) -> None:
    """A stray ``'''`` inside a prompt body ships a file the Gemini CLI cannot
    load. Nothing else in this repository parses these files, so that defect
    would pass every other suite."""
    templates = _gemini_templates(repo_root)
    assert templates, "no Gemini templates found"
    for path in templates:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
        assert "prompt" in parsed, f"{path.name} has no `prompt` key"
        assert "description" in parsed, f"{path.name} has no `description` key"


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


def test_every_claude_and_gemini_template_interpolates_arguments(repo_root: Path) -> None:
    """`$ARGUMENTS` is how both hosts pass the user's input into the prompt. A
    template without it silently ignores every flag the user types."""
    paths = sorted((repo_root / "templates" / "claude").glob("*.md")) + _gemini_templates(
        repo_root
    )
    assert paths, "no Claude or Gemini templates found"
    for path in paths:
        assert "$ARGUMENTS" in path.read_text(encoding="utf-8"), (
            f"{path.name} never references $ARGUMENTS"
        )
