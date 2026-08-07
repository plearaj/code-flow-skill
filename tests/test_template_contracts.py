"""Assertions about template content.

Templates are prompt text, not code, so these tests check that the
instructions a template gives still mention the artifacts it is required to
produce. They catch silent drift between the spec and the prompts.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

MAP_TEMPLATES = (
    ("claude", "code-flow.map.md"),
    ("gemini", "code-flow.map.toml"),
    ("copilot", "code-flow.map.prompt.md"),
)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_requires_json_sidecar(repo_root: Path, host: str, name: str) -> None:
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "<functionality_name>.json" in text


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_requires_index(repo_root: Path, host: str, name: str) -> None:
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "index.json" in text


def test_viewer_scaffold_has_exactly_one_token(repo_root: Path) -> None:
    text = (repo_root / "templates" / "shared" / "viewer.template.html").read_text(
        encoding="utf-8"
    )
    assert text.count("__FLOW_DATA__") == 1


INDEX_FIELD_NAMES = (
    "slug",
    "title",
    "file",
    "entry",
    "nodes",
    "coverage",
    "flowsTraced",
    "schema",
    "mode",
)

# Marks the start of the Step 6 "write the machine-readable artifacts"
# instructions in every host (Claude/Gemini: "#### 6. Write the
# Machine-Readable Artifacts"; Copilot: "**Write the machine-readable
# artifacts.**"). Matched case-insensitively so it doesn't care which of
# those two casings a host uses.
_INDEX_SECTION_START = re.compile(r"machine-readable artifacts", re.IGNORECASE)

# Marks the start of the *next* section/item after Step 6, in every host
# (Claude/Gemini: "#### 7. Finalize"; Copilot: "7. **Report..."). Used as
# the end boundary so the scoped region can't run past Step 6 into
# unrelated text.
_INDEX_SECTION_END = re.compile(r"\n(?:#### 7\.|7\.\s*\*\*Report)")


def _field_reference(field: str) -> re.Pattern[str]:
    """Match a *reference to the field named ``field``*, not the bare word.

    A plain substring search is vacuous for several of these names, because
    the same letters occur in ordinary prose inside the same region: `file`
    appears in "written as a plain file", "These files are the contract" and
    "rewriting the file would silently discard...", and `entry` appears in
    "add or replace the entry for this flow". Deleting the bullet that
    actually derives `file` would leave those prose hits behind and the
    assertion would still pass.

    Every real reference in every host is delimited: the field is either
    JSON-quoted (`"file": "user_login.json"`), wrapped in a markdown code
    span (`` `file` ``), or dotted onto its parent (``coverage.flowsTraced``,
    ``meta.mode``). Requiring one of those three leading delimiters, plus a
    word boundary after the name, keeps the prose occurrences out.
    """
    return re.compile(r"[`\".]" + re.escape(field) + r"\b")


def _index_instructions_region(text: str) -> str:
    """Return only the slice of a map template that gives the Step 6
    index/sidecar instructions.

    `slug`, `entry`, and `nodes` are not unique to Step 6 — they also show
    up incidentally elsewhere in every template (the flow-data JSON's own
    `nodes` array, the node `kind` enum's `entry` value, `meta.slug` in the
    step 5a example). A bare substring search over the whole template would
    pass even if the Step 6 bullets describing the index entry were deleted
    entirely, because those other occurrences would still be there. Scoping
    to the region between the machine-readable-artifacts heading and the
    next section closes that hole.
    """
    start_match = _INDEX_SECTION_START.search(text)
    assert start_match, "template has no machine-readable-artifacts section"
    start = start_match.start()
    end_match = _INDEX_SECTION_END.search(text, start)
    end = end_match.start() if end_match else len(text)
    return text[start:end]


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_names_index_fields(repo_root: Path, host: str, name: str) -> None:
    """Each host's Step 6 instructions must at least name every field the
    index/sidecar contract requires.

    Field names are stable identifiers, not prose, so this check is robust
    across the hosts' different voices. What it catches: a host dropping a
    field from its Step 6 instructions. What it does NOT catch: a host that
    names a field but omits the rule for how to derive or preserve its
    value (e.g. this test passes as long as `entry` is referenced somewhere
    in the Step 6 region, even if that region never says which node's `id`
    to use for it). That class of divergence — a present-but-underspecified
    field — is caught only by review, not by this test.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _index_instructions_region(text)
    for field in INDEX_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host}/{name} Step 6 instructions are missing the '{field}' field name"
        )
