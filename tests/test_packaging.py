"""Tests that the built wheel actually carries the template files."""
from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path

EXPECTED_IN_WHEEL = (
    "code_flow_skill/templates/claude/code-flow.map.md",
    "code_flow_skill/templates/claude/code-flow.quality.md",
    "code_flow_skill/templates/gemini/code-flow.map.toml",
    "code_flow_skill/templates/gemini/code-flow.quality.toml",
    "code_flow_skill/templates/copilot/code-flow.map.prompt.md",
    "code_flow_skill/templates/copilot/code-flow.quality.prompt.md",
    "code_flow_skill/templates/shared/viewer.template.html",
    "code_flow_skill/templates/shared/report.template.html",
    "code_flow_skill/templates/shared/index.template.html",
    "code_flow_skill/templates/shared/code-flow-map/SKILL.md",
    "code_flow_skill/templates/shared/code-flow-map/agents/openai.yaml",
    "code_flow_skill/templates/shared/code-flow-quality/SKILL.md",
    "code_flow_skill/templates/shared/code-flow-quality/agents/openai.yaml",
)


def test_wheel_contains_templates(tmp_path: Path, repo_root: Path) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
    missing = [expected for expected in EXPECTED_IN_WHEEL if expected not in names]
    assert not missing, f"wheel is missing template files: {missing}"


def test_source_mirror_is_gone(repo_root: Path) -> None:
    assert not (repo_root / "src" / "code_flow_skill" / "templates").exists()


def test_readme_files_written_table_lists_exactly_the_installed_set(repo_root: Path) -> None:
    """The README's "Files written" table is the canonical answer to "what does
    this put in my repo", and it drifted: it still listed the three
    `code-flow.map.*` paths after the installer began writing six plus the
    viewer. Nothing caught it, because no test read the README.

    Compared against `EXPECTED_ALL` — the same set both installers' own tests
    assert — rather than a second hand-written list, so there is exactly one
    place to update when the installed set changes.

    Scoped to the table's own rows (lines beginning with `|`), not the whole
    section: the prose under the table names `.code-flow/viewer.template.html`
    again, so an unscoped search would pass with that row deleted.
    """
    from .test_installer_python import EXPECTED_ALL

    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    section = re.search(r"\n## Files written\n(.*?)(?=\n## )", readme, re.DOTALL)
    assert section is not None, "README has no '## Files written' section"
    rows = [line for line in section.group(1).splitlines() if line.startswith("|")]
    listed = sorted(
        set(re.findall(r"`((?:\.[\w.-]+)/[^`]+)`", "\n".join(rows)))
    )
    assert listed == sorted(EXPECTED_ALL), (
        "README 'Files written' table does not match the installed file set:\n"
        f"  README:    {listed}\n"
        f"  installer: {sorted(EXPECTED_ALL)}"
    )


def _declared_version(repo_root: Path) -> str:
    """The one version both packages must agree on."""
    npm_version = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))["version"]
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert match is not None, "no version found in pyproject.toml"
    assert npm_version == match.group(1), (
        f"package.json says {npm_version}, pyproject.toml says {match.group(1)}"
    )
    return npm_version


def test_package_versions_match_and_are_1_0_0(repo_root: Path) -> None:
    assert _declared_version(repo_root) == "1.0.0"


def test_changelog_leads_with_the_version_being_shipped(repo_root: Path) -> None:
    """A changelog that lags the version is worse than none — it states, with
    apparent authority, that the release contains what the previous one did.
    Pinned to the *first* version heading rather than to membership anywhere in
    the file, because every past version is in there too."""
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## \[([^\]]+)\]", changelog, re.MULTILINE)
    assert headings, "CHANGELOG.md has no `## [version]` headings"
    assert headings[0] == _declared_version(repo_root), (
        f"CHANGELOG.md leads with {headings[0]}, but the packages declare "
        f"{_declared_version(repo_root)}"
    )


def test_changelog_ships_in_both_packages(repo_root: Path) -> None:
    """It is only a changelog for users if it reaches them."""
    npm_files = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))["files"]
    assert "CHANGELOG.md" in npm_files, "CHANGELOG.md is missing from package.json `files`"
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    sdist = re.search(r"^\[tool\.hatch\.build\.targets\.sdist\]\ninclude = \[([^\]]+)\]",
                      pyproject, re.MULTILINE)
    assert sdist is not None, "no sdist include list found in pyproject.toml"
    assert '"CHANGELOG.md"' in sdist.group(1), "CHANGELOG.md is missing from the sdist include list"
