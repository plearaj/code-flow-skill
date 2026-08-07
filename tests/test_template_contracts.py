"""Assertions about template content.

Templates are prompt text, not code, so these tests check that the
instructions a template gives still mention the artifacts it is required to
produce. They catch silent drift between the spec and the prompts.
"""
from __future__ import annotations

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


INDEX_FIELD_NAMES = ("slug", "entry", "nodes", "coverage", "flowsTraced")


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_names_index_fields(repo_root: Path, host: str, name: str) -> None:
    """Each host must at least name every field the index/sidecar contract
    requires.

    Field names are stable identifiers, not prose, so this check is robust
    across the hosts' different voices. What it catches: a host dropping a
    field entirely. What it does NOT catch: a host that names a field but
    omits the rule for how to derive or preserve its value (e.g. this test
    passes as long as the word "entry" appears anywhere, even if the
    template never says which node's `id` to use for it). That class of
    divergence — a present-but-underspecified field — is caught only by
    review, not by this test.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    for field in INDEX_FIELD_NAMES:
        assert field in text, f"{host}/{name} is missing the '{field}' field name"
